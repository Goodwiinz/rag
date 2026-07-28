"""Sanitization utilities for the agent layer.

Two related defenses share this module:

- ``_sanitize_prompt_field``: neutralises user-controlled text before it is
  interpolated into LLM system prompts (prompt-injection defence).
- ``_sanitize_messages``: rebuilds a checkpointed message list so it
  satisfies the OpenAI tool-call invariants (every assistant ``tool_calls``
  answered by matching ``ToolMessage``s, orphans dropped, consecutive
  HumanMessages collapsed). Moved here from ``graph.py``.

Public API
----------
_PROMPT_FIELD_MAX_CHARS : int
    Maximum character length for any sanitised field.
_sanitize_prompt_field(value: str) -> str
    Truncate, escape braces, and collapse newlines in *value*.
_sanitize_messages(raw: list) -> list
    Rebuild a message list to satisfy LLM API tool-call invariants.
"""

from typing import Any, Optional

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

# Maximum length (chars) for any user-supplied string interpolated into a
# classifier system prompt.  Truncating + neutralising braces/newlines is the
# minimum defence against prompt-injection via previous_turn / prior_tool /
# page_context.  Longer values are clipped with an ellipsis.
_PROMPT_FIELD_MAX_CHARS = 400


def _sanitize_prompt_field(value: str) -> str:
    """Neutralise user-controlled text before interpolating into a prompt.

    Strips characters that could either break the ``str.format()`` call
    (``{`` / ``}``) or attempt to escape the surrounding section header in
    the system prompt (newlines, markdown headings). Truncates to
    ``_PROMPT_FIELD_MAX_CHARS`` so an attacker cannot drown the actual
    classification prompt by stuffing thousands of tokens through one of
    the dynamic context fields.
    """
    if not value:
        return ""
    text = str(value)
    if len(text) > _PROMPT_FIELD_MAX_CHARS:
        text = text[:_PROMPT_FIELD_MAX_CHARS] + "..."
    # ``str.format`` interprets ``{`` / ``}`` as field delimiters — escape
    # them to literal braces.
    text = text.replace("{", "{{").replace("}", "}}")
    # Collapse newlines so dynamic content cannot start a new markdown
    # heading and visually impersonate prompt sections.
    text = text.replace("\r", " ").replace("\n", " ")
    return text


_TOOL_PLACEHOLDER_CONTENT = '{"status": "skipped"}'


def _tool_call_id(tc: Any) -> Optional[str]:
    """Extract the ``id`` field from a tool_call entry, tolerating dict or attr form."""
    if isinstance(tc, dict):
        tc_id = tc.get("id")
    else:
        tc_id = getattr(tc, "id", None)
    return tc_id if isinstance(tc_id, str) and tc_id else None


def _sanitize_messages(raw: list) -> list:
    """Ensure the message list is valid for LLM APIs.

    OpenAI-compatible chat APIs require:
    1. Every assistant message with ``tool_calls`` must be IMMEDIATELY
       followed by ``ToolMessage`` entries answering each call.
    2. Every ``ToolMessage`` must follow an assistant message whose
       ``tool_calls`` includes its ``tool_call_id``.

    Real-world checkpoint state can violate both invariants — e.g. a
    cancelled tool execution leaves an unanswered ``tool_call``, or a
    HumanMessage gets inserted between an AI's tool_calls and the
    ToolMessages answering them. We rebuild the message list defensively:

    - Index every ``ToolMessage`` by its ``tool_call_id`` (last wins).
    - Walk the raw list, skipping standalone ToolMessages — they're
      re-emitted right after their parent AIMessage (or replaced with a
      ``"skipped"`` placeholder if no real one exists).
    - ToolMessages whose ``tool_call_id`` doesn't match any AI tool_call
      are dropped — they're orphans that confuse the API.
    - Consecutive HumanMessages are merged into one (LangGraph state
      occasionally appends them separately on retries / interrupts).

    The placeholder content stays ``'{"status": "skipped"}'`` because
    the compactor recognises that exact string to skip synthetic items.
    """
    # Pass 1: index ToolMessages by tool_call_id (last occurrence wins)
    tm_by_id: dict[str, ToolMessage] = {}
    for msg in raw:
        if isinstance(msg, ToolMessage) and msg.tool_call_id:
            tm_by_id[msg.tool_call_id] = msg

    # Pass 2: rebuild list, putting each AI's ToolMessages right after it
    rebuilt: list = []
    placed_tm_ids: set[str] = set()
    for msg in raw:
        if isinstance(msg, ToolMessage):
            # Standalone TMs are re-inserted via their parent AI (below)
            # or dropped if no parent claims them.
            continue
        rebuilt.append(msg)
        if not (isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None)):
            continue
        for tc in msg.tool_calls:
            tc_id = _tool_call_id(tc)
            if not tc_id or tc_id in placed_tm_ids:
                continue
            tm = tm_by_id.get(tc_id)
            if tm is None:
                tm = ToolMessage(content=_TOOL_PLACEHOLDER_CONTENT, tool_call_id=tc_id)
            rebuilt.append(tm)
            placed_tm_ids.add(tc_id)

    # Pass 3: collapse consecutive HumanMessages.
    #
    # When a previous turn is interrupted (CancelledError from the user
    # aborting the stream by typing a new message), the unanswered
    # HumanMessage stays in the checkpoint. The next user input arrives
    # as a second consecutive HumanMessage. The previous concatenation
    # behavior caused the LLM to see both as a single combined intent
    # (trace 019e1885: "Find recent transformer papers" + "hi" → LLM
    # answered the older cancelled query). Treat consecutive Human
    # messages as supersession: keep only the latest. The earlier
    # message had no AI response, so the user clearly abandoned it.
    merged: list = []
    for msg in rebuilt:
        if (
            merged
            and isinstance(merged[-1], HumanMessage)
            and isinstance(msg, HumanMessage)
        ):
            merged[-1] = msg
        else:
            merged.append(msg)
    return merged
