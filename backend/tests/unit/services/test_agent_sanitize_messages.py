"""Unit tests for ``_sanitize_messages`` (graph.py).

These regression-test the message-list rebuild that runs before every
LLM call. The OpenAI-compatible API rejects:

- AIMessage with tool_calls not immediately followed by matching
  ToolMessages → BadRequestError("An assistant message with 'tool_calls'
  must be followed by tool messages responding to each").
- ToolMessage not preceded by an AI message with matching tool_call_id
  → BadRequestError("Messages with role 'tool' must be a response to a
  preceding message with 'tool_calls'").

The sanitizer rebuilds the list defensively so neither rejection can
fire even when state is corrupted by cancelled tool runs, abandoned
HITL interrupts, or weird checkpoint restores.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def _ids(tool_calls: list[str]) -> list[dict]:
    return [{"id": tc, "name": "noop", "args": {}} for tc in tool_calls]


def test_already_valid_sequence_passes_through_unchanged():
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    from src.services.agent.graph import _sanitize_messages

    raw = [
        HumanMessage(content="hi"),
        AIMessage(content="", tool_calls=_ids(["c1"])),
        ToolMessage(content='{"ok": true}', tool_call_id="c1"),
        AIMessage(content="done"),
    ]

    out = _sanitize_messages(raw)

    assert len(out) == 4
    assert out[2].content == '{"ok": true}'
    assert out[2].tool_call_id == "c1"


def test_unanswered_tool_call_gets_placeholder():
    from langchain_core.messages import AIMessage, ToolMessage

    from src.services.agent.graph import _sanitize_messages

    raw = [
        AIMessage(content="", tool_calls=_ids(["c1", "c2"])),
        ToolMessage(content='{"ok": true}', tool_call_id="c1"),
    ]

    out = _sanitize_messages(raw)

    assert len(out) == 3
    assert out[0].tool_calls[0]["id"] == "c1"
    # Real TM preserved, placeholder added for c2
    tm_ids = [m.tool_call_id for m in out[1:]]
    assert sorted(tm_ids) == ["c1", "c2"]
    placeholder = next(m for m in out if m.tool_call_id == "c2")
    assert '"skipped"' in placeholder.content


def test_human_message_between_ai_and_tool_message_is_repaired():
    """Cancelled tool + fresh user turn would leave AI(tool_calls) /
    HumanMessage / ToolMessage interleaved — sanitizer must re-anchor."""
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    from src.services.agent.graph import _sanitize_messages

    raw = [
        AIMessage(content="", tool_calls=_ids(["c1"])),
        HumanMessage(content="actually nevermind"),
        ToolMessage(content='{"late": true}', tool_call_id="c1"),
    ]

    out = _sanitize_messages(raw)

    # The AI's TM must come immediately after the AI, not after the
    # HumanMessage. The HumanMessage comes last.
    assert isinstance(out[0], AIMessage)
    assert isinstance(out[1], ToolMessage)
    assert out[1].tool_call_id == "c1"
    assert out[1].content == '{"late": true}'
    assert isinstance(out[2], HumanMessage)


def test_orphan_tool_message_without_parent_is_dropped():
    """A ToolMessage with no matching AI tool_call must not survive —
    OpenAI rejects orphans."""
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    from src.services.agent.graph import _sanitize_messages

    raw = [
        HumanMessage(content="hi"),
        ToolMessage(content='{"orphan": true}', tool_call_id="ghost"),
        AIMessage(content="hello"),
    ]

    out = _sanitize_messages(raw)

    assert all(not isinstance(m, ToolMessage) for m in out)
    assert isinstance(out[0], HumanMessage)
    assert isinstance(out[1], AIMessage)


def test_tool_message_attaches_to_correct_parent_when_two_ais():
    from langchain_core.messages import AIMessage, ToolMessage

    from src.services.agent.graph import _sanitize_messages

    raw = [
        AIMessage(content="", tool_calls=_ids(["c1"])),
        AIMessage(content="", tool_calls=_ids(["c2"])),
        ToolMessage(content='{"r1": true}', tool_call_id="c1"),
        ToolMessage(content='{"r2": true}', tool_call_id="c2"),
    ]

    out = _sanitize_messages(raw)

    assert isinstance(out[0], AIMessage)
    assert isinstance(out[1], ToolMessage) and out[1].tool_call_id == "c1"
    assert isinstance(out[2], AIMessage)
    assert isinstance(out[3], ToolMessage) and out[3].tool_call_id == "c2"


def test_consecutive_human_messages_merged():
    from langchain_core.messages import HumanMessage

    from src.services.agent.graph import _sanitize_messages

    raw = [HumanMessage(content="part 1"), HumanMessage(content="part 2")]

    out = _sanitize_messages(raw)

    assert len(out) == 1
    assert "part 1" in out[0].content
    assert "part 2" in out[0].content


def test_tool_call_without_id_does_not_crash():
    """Some non-OpenAI providers emit tool_calls without explicit ids."""
    from langchain_core.messages import AIMessage, HumanMessage

    from src.services.agent.graph import _sanitize_messages

    ai = AIMessage(content="", tool_calls=[{"id": "", "name": "noop", "args": {}}])
    raw = [ai, HumanMessage(content="hi")]

    out = _sanitize_messages(raw)

    # AI passes through; no placeholder added (no id to address).
    # HumanMessage is preserved.
    assert isinstance(out[0], AIMessage)
    assert isinstance(out[-1], HumanMessage)


def test_duplicate_tool_message_ids_keep_only_one():
    """Defensive: state replay can occasionally double-write a TM.
    Sanitizer should keep one (last wins) and not append twice."""
    from langchain_core.messages import AIMessage, ToolMessage

    from src.services.agent.graph import _sanitize_messages

    raw = [
        AIMessage(content="", tool_calls=_ids(["c1"])),
        ToolMessage(content='{"first": true}', tool_call_id="c1"),
        ToolMessage(content='{"second": true}', tool_call_id="c1"),
    ]

    out = _sanitize_messages(raw)

    tms = [m for m in out if hasattr(m, "tool_call_id")]
    assert len(tms) == 1
    assert tms[0].content == '{"second": true}'
