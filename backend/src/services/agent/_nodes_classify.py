"""Intent classification + parallel preprocessing for the agent graph.

Extracted from ``graph.py`` so the orchestration module stays under the
800-line house rule. ``graph.py`` re-exports the public names so legacy
imports keep working.

Two execution paths live here:

* **``_classify_core``** — the bare LLM-with-keyword-fallback intent
  classifier. Also exposed as ``intent_classifier_node`` (the
  ``@track_node_execution``-wrapped variant) for callers that prefer
  per-node Prometheus metrics.
* **``preprocessing_node``** — kicks off RAG retrieval, classification,
  and memory recall in parallel via ``asyncio.gather`` and resets per-
  turn ephemeral state so values carried by the checkpointer cannot
  poison the new turn.

``route_by_intent`` lives here too because it is the conditional edge
fired immediately after ``preprocessing_node``.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from src.services.agent._nodes_memory import memory_retrieval_node
from src.services.agent._nodes_rag import _coerce_text, rag_node
from src.services.agent.observability import track_node_execution
from src.services.agent.state import AgentState

logger = logging.getLogger(__name__)


def _extract_prior_tool(messages: List[Any]) -> Optional[Dict[str, Any]]:
    """Walk *messages* backwards and return the most recent tool call.

    Returns a dict with keys ``name``, ``args``, and ``result`` (the matching
    ToolMessage content as a string), or ``None`` if no tool call exists in
    the conversation. Used to pass retry context to the intent classifier so
    short follow-ups like "try again" route to the same intent as the prior
    tool.
    """
    for ai_idx in range(len(messages) - 1, -1, -1):
        msg = messages[ai_idx]
        if not isinstance(msg, AIMessage):
            continue
        tool_calls = getattr(msg, "tool_calls", None)
        if not tool_calls:
            continue
        first = tool_calls[0]
        tool_call_id = first.get("id")
        result = ""
        # Only scan AFTER the AIMessage we found — otherwise a stale
        # ToolMessage from a previous turn that happens to share an id
        # (or a synthetic placeholder) gets returned, misleading the
        # classifier about what just happened.
        for follow in messages[ai_idx + 1 :]:
            if isinstance(follow, ToolMessage) and follow.tool_call_id == tool_call_id:
                result = str(follow.content)
                break
        return {
            "name": first.get("name", ""),
            "args": first.get("args", {}) or {},
            "result": result,
        }
    return None


async def _classify_core(state: AgentState, config: RunnableConfig) -> dict:
    """Classify user intent using LLM with keyword fallback.

    Used directly inside ``preprocessing_node`` (which composes its own
    parallel tracking) and indirectly via ``intent_classifier_node``,
    which wraps this with ``@track_node_execution`` for callers that
    invoke it as a graph node.
    """
    from src.services.agent.classifier import classify_intent_with_fallback

    # Coerce: multimodal content is a list of blocks; the classifier's
    # keyword path calls .lower()/.split() on it, which would raise and be
    # swallowed by the gather(return_exceptions=True) in preprocessing_node,
    # silently defaulting the intent to "general".
    last_user_msg = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            last_user_msg = _coerce_text(msg.content)
            break

    if not last_user_msg:
        return {"intent": "general", "intent_confidence": 0.0}

    previous_turn = ""
    found_user = False
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            if found_user:
                break
            found_user = True
            continue
        if found_user and isinstance(msg, AIMessage) and msg.content:
            previous_turn = _coerce_text(msg.content)
            break

    prior_tool = _extract_prior_tool(state["messages"])
    page_context = config.get("configurable", {}).get("page_context", {})
    result = await classify_intent_with_fallback(
        query=last_user_msg,
        page_context=page_context,
        previous_turn=previous_turn,
        prior_tool=prior_tool,
    )
    logger.debug(
        "Classified intent: %s (confidence=%.2f, source=%s)",
        result.intent,
        result.confidence,
        result.source,
    )
    try:
        from src.services.agent.observability import record_classifier_source

        record_classifier_source(source=result.source, intent=result.intent)
    except Exception:
        pass
    return {"intent": result.intent, "intent_confidence": result.confidence}


# ``intent_classifier_node`` is the tracked graph-node version of
# ``_classify_core``. Production wiring uses ``_classify_core`` directly via
# ``preprocessing_node``; the tracked alias is kept for tests and any future
# wiring that wants the per-node Prometheus metrics.
intent_classifier_node = track_node_execution("intent_classifier_node")(_classify_core)


@track_node_execution("preprocessing_node")
async def preprocessing_node(state: AgentState, config: RunnableConfig) -> dict:
    """Run RAG retrieval, intent classification, and memory retrieval in parallel.

    Also resets per-turn ephemeral state (``plan``, ``reflection_count``,
    ``_reflection_result``, ``tool_loop_count``, ``error_count``,
    ``user_confirmed``) so that values carried over from the previous turn
    via the checkpointer cannot:

    - block the planner from re-planning against the new query (H-11);
    - trigger a spurious revision at the start of the next turn from a
      stale ``_reflection_result`` (H-01 / M-06);
    - bypass the destructive-tool HITL gate via a stale ``user_confirmed``
      flag (H-17);
    - count this turn's first error against last turn's accumulated
      ``error_count``.
    """
    rag_task = asyncio.create_task(rag_node(state, config))
    classify_task = asyncio.create_task(_classify_core(state, config))
    memory_task = asyncio.create_task(memory_retrieval_node(state, config))

    results = await asyncio.gather(
        rag_task, classify_task, memory_task, return_exceptions=True
    )

    defaults = [
        {"retrieved_contexts": []},
        {"intent": "general", "intent_confidence": 0.0},
        {"user_memories": []},
    ]
    merged: dict = {
        # Per-turn resets — must come BEFORE merging subtask results so a
        # subtask that explicitly sets one of these keys still wins.
        "plan": [],
        "reflection_count": 0,
        "_reflection_result": None,
        "tool_loop_count": 0,
        "error_count": 0,
        "last_error": "",
        "last_error_info": {},
        "user_confirmed": False,
        "pending_confirmation": {},
        # compaction_count is documented "reset per turn" (state.py) but was
        # omitted, so it accumulated for the life of the thread. _force_-
        # synthesis_fired is last-write-wins and, left True from a prior turn,
        # permanently disables forced synthesis (empty-content + orphan
        # tool_calls "no response" exit). Reset both per turn.
        "compaction_count": 0,
        "_force_synthesis_fired": False,
    }
    for result, default in zip(results, defaults):
        if isinstance(result, asyncio.CancelledError):
            # CancelledError is BaseException (not Exception) since 3.8, so the
            # check below would skip it and merged.update(<exc>) would raise
            # TypeError. The caller aborted — propagate, don't swallow (house
            # pattern: jobs.py / classifier.py / error_recovery.py).
            raise result
        if isinstance(result, Exception):
            logger.warning("Preprocessing subtask failed: %s", result)
            merged.update(default)
        else:
            merged.update(result)
    return merged


def route_by_intent(state: AgentState) -> str:
    """Route to the appropriate sub-graph based on classified intent."""
    intent = state.get("intent", "general")
    if intent == "research":
        return "research_subgraph"
    if intent == "writing":
        return "writing_subgraph"
    if intent == "knowledge_graph":
        return "data_subgraph"
    return "llm_node"


__all__ = [
    "_extract_prior_tool",
    "_classify_core",
    "intent_classifier_node",
    "preprocessing_node",
    "route_by_intent",
]
