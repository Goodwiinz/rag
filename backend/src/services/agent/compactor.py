"""Context compactor for the agent graph.

Summarises older ToolMessage payloads using gpt-4o-mini so that the
conversation stays within the context window while preserving all
referenced IDs (UUIDs and arXiv IDs).
"""

import logging
import re
from typing import Any, Callable

from langchain_core.messages import AIMessage, BaseMessage, RemoveMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from src.core.config import get_settings
from src.core.openai_endpoint import classify_openai_endpoint
from src.services.agent.state import AgentState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)
_ARXIV_RE = re.compile(r"\d{4}\.\d{4,5}(?:v\d+)?")

_COMPACTED_PREFIX = "[Compacted]"

# Synthetic placeholder content emitted by ``_sanitize_messages`` when an
# AIMessage tool_call has no matching ToolMessage. These placeholders are
# already minimal (~25 chars) and contain no useful content to summarise,
# so they're filtered out of compaction candidates.
_PLACEHOLDER_CONTENTS: frozenset[str] = frozenset({'{"status": "skipped"}'})

# Cap the LLM compaction summary length. Generous enough that summaries do not
# get cut mid-sentence, but small enough to deliver meaningful token savings.
_COMPACT_MAX_TOKENS = 320


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------


def estimate_tool_message_tokens(messages: list[ToolMessage]) -> int:
    """Estimate total tokens across all ToolMessages.

    Uses a simple heuristic of ``len(content) // 4`` per message.
    """
    total = 0
    for msg in messages:
        content = msg.content if isinstance(msg.content, str) else ""
        total += len(content) // 4
    return total


# ---------------------------------------------------------------------------
# ID extraction
# ---------------------------------------------------------------------------


def extract_ids(text: str) -> tuple[set[str], set[str]]:
    """Extract UUIDs and arXiv IDs from *text*.

    Returns ``(uuids, arxiv_ids)`` as two sets of strings.
    """
    uuids = set(_UUID_RE.findall(text))
    arxiv_ids = set(_ARXIV_RE.findall(text))
    return uuids, arxiv_ids


# ---------------------------------------------------------------------------
# Compaction predicate
# ---------------------------------------------------------------------------


def should_compact(
    messages: list[BaseMessage],
    compaction_count: int,
    threshold: int = 8000,
) -> bool:
    """Return ``True`` if estimated tool-message tokens exceed *threshold*."""
    tool_msgs = [m for m in messages if isinstance(m, ToolMessage)]
    return estimate_tool_message_tokens(tool_msgs) > threshold


# ---------------------------------------------------------------------------
# Candidate selection
# ---------------------------------------------------------------------------


def find_compaction_candidates(messages: list[BaseMessage]) -> list[ToolMessage]:
    """Find ToolMessages that are safe to compact.

    The most recent AIMessage with ``tool_calls`` and its corresponding
    ToolMessages are *protected* (never compacted).  All older ToolMessages
    that are not already ``[Compacted]``-prefixed are returned as candidates.
    """
    # Walk backward to find the most recent AIMessage with tool_calls.
    latest_ai_idx: int | None = None
    for idx in range(len(messages) - 1, -1, -1):
        msg = messages[idx]
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            latest_ai_idx = idx
            break

    if latest_ai_idx is None:
        return []

    # Collect tool_call_ids for the latest protected batch.
    latest_ai: AIMessage = messages[latest_ai_idx]  # type: ignore[assignment]
    protected_tc_ids: set[str] = {tc["id"] for tc in latest_ai.tool_calls}

    candidates: list[ToolMessage] = []
    for msg in messages[:latest_ai_idx]:
        if not isinstance(msg, ToolMessage):
            continue
        content = msg.content if isinstance(msg.content, str) else ""
        if content.startswith(_COMPACTED_PREFIX):
            continue
        if content.strip() in _PLACEHOLDER_CONTENTS:
            # Synthetic skipped-tool placeholder — nothing to summarise.
            continue
        if msg.tool_call_id in protected_tc_ids:
            continue
        candidates.append(msg)

    return candidates


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_and_fix_compacted(
    compacted: str,
    original_ids: tuple[set[str], set[str]],
) -> str:
    """Ensure all IDs from *original_ids* appear in *compacted*.

    If any are missing, append a ``Referenced IDs:`` line listing them.
    """
    uuids, arxiv_ids = original_ids
    all_original = uuids | arxiv_ids
    if not all_original:
        return compacted

    present_uuids, present_arxiv = extract_ids(compacted)
    present = present_uuids | present_arxiv
    missing = all_original - present

    if not missing:
        return compacted

    return f"{compacted}\nReferenced IDs: {', '.join(sorted(missing))}"


# ---------------------------------------------------------------------------
# LLM helper (mirrors graph.py _build_llm but targets gpt-4o-mini)
# ---------------------------------------------------------------------------


def _build_compactor_llm():
    """Build a lightweight LLM for compaction summaries.

    Uses the same Azure/OpenAI config pattern as ``graph._build_llm`` but
    targets **gpt-4o-mini** with ``temperature=0`` for deterministic,
    cost-efficient summarisation.
    """
    settings = get_settings()

    endpoint = (
        settings.AZURE_OPENAI_CHAT_ENDPOINT or settings.AZURE_OPENAI_ENDPOINT or ""
    )
    api_key = (
        settings.AZURE_OPENAI_CHAT_API_KEY or settings.AZURE_OPENAI_API_KEY or ""
    )
    api_version = (
        settings.AZURE_OPENAI_CHAT_API_VERSION or settings.AZURE_OPENAI_API_VERSION
    )

    if not endpoint or not api_key:
        raise RuntimeError(
            "Azure/OpenAI chat endpoint and API key must be configured. "
            "Set AZURE_OPENAI_CHAT_ENDPOINT + AZURE_OPENAI_CHAT_API_KEY "
            "(or the non-CHAT variants)."
        )

    if classify_openai_endpoint(endpoint) == "openai_compatible":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model="gpt-4o-mini",
            api_key=api_key,
            base_url=endpoint,
            temperature=0,
            max_tokens=_COMPACT_MAX_TOKENS,
        )
    else:
        from langchain_openai import AzureChatOpenAI

        return AzureChatOpenAI(
            azure_deployment="gpt-4o-mini",
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
            temperature=0,
            max_tokens=_COMPACT_MAX_TOKENS,
        )


# ---------------------------------------------------------------------------
# Compaction logic
# ---------------------------------------------------------------------------

_COMPACTION_SYSTEM_PROMPT = (
    "You are a context compactor. Summarise the following tool output in "
    "under 200 tokens. Preserve ALL document IDs (UUIDs), arXiv IDs, "
    "titles, status codes, and key facts. Omit verbose formatting."
)


async def compact_messages(
    candidates: list[ToolMessage],
    config: RunnableConfig,
) -> list[ToolMessage]:
    """Compact each candidate ToolMessage via gpt-4o-mini.

    For each candidate:
    1. Extract IDs from original content
    2. Call gpt-4o-mini to summarise (failure is isolated per-item — a
       single LLM error skips that candidate but allows the rest to
       proceed)
    3. Validate/fix compacted output
    4. Return new ToolMessage with ``[Compacted]`` prefix and the same
       ``id`` as the original (so the LangGraph reducer can replace it).
    """
    llm = _build_compactor_llm()
    compacted: list[ToolMessage] = []

    from langchain_core.messages import HumanMessage, SystemMessage

    for msg in candidates:
        original_content = msg.content if isinstance(msg.content, str) else ""
        original_ids = extract_ids(original_content)

        try:
            response = await llm.ainvoke(
                [
                    SystemMessage(content=_COMPACTION_SYSTEM_PROMPT),
                    HumanMessage(content=original_content),
                ],
                config=config,
            )
        except Exception:
            logger.warning(
                "Compaction LLM call failed for tool_call_id=%s; "
                "leaving original message intact",
                msg.tool_call_id,
                exc_info=True,
            )
            continue

        summary = (
            response.content if isinstance(response.content, str) else str(response.content)
        )
        summary = validate_and_fix_compacted(summary, original_ids)

        compacted.append(
            ToolMessage(
                content=f"{_COMPACTED_PREFIX} {summary}",
                tool_call_id=msg.tool_call_id,
                id=msg.id,
            )
        )

    return compacted


# ---------------------------------------------------------------------------
# Graph node factory
# ---------------------------------------------------------------------------


def make_compactor_node() -> Callable:
    """Return a graph node function for context compaction.

    The returned async function:
    1. Checks ``should_compact()`` — passes through if no.
    2. Finds compaction candidates.
    3. Compacts them via LLM.
    4. Returns replacement messages and bumped ``compaction_count``.
    """

    async def compactor_node(
        state: AgentState,
        config: RunnableConfig,
    ) -> dict[str, Any]:
        messages: list[BaseMessage] = state["messages"]
        compaction_count: int = state.get("compaction_count", 0)  # type: ignore[arg-type]

        if not should_compact(messages, compaction_count):
            return {}

        candidates = find_compaction_candidates(messages)
        if not candidates:
            return {}

        compacted = await compact_messages(candidates, config)

        if not compacted:
            return {}

        # The ``messages`` channel uses the ``add_messages`` reducer which
        # APPENDS new messages by default and only replaces existing ones
        # when the new message's ``id`` matches an existing message's ``id``.
        # Returning the full reconstructed list here would have doubled the
        # history (every untouched message is appended again — and the
        # `add_messages` dedup-by-id only catches messages with explicit
        # IDs). The correct pattern is to emit ``RemoveMessage`` deletions
        # for each compacted candidate followed by the replacement
        # ToolMessages.
        compacted_ids = {m.id for m in compacted if m.id is not None}
        removes: list[BaseMessage] = [
            RemoveMessage(id=msg.id)
            for msg in candidates
            if msg.id is not None and msg.id in compacted_ids
        ]

        return {
            "messages": removes + list(compacted),
            "compaction_count": compaction_count + 1,
        }

    return compactor_node
