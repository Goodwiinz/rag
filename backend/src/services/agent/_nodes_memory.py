"""Memory recall + save nodes for the agent graph.

Extracted from ``graph.py`` so the orchestration module stays under the
800-line house rule. ``graph.py`` re-exports both functions for legacy
imports (``from src.services.agent.graph import memory_save_node``).

Both nodes share two contracts:
- They never raise. Memory is a best-effort enrichment; an outage here
  must not break a turn.
- They mutate state only via the returned dict (LangGraph reducer).

Save gate trace anchor: 019e066b-2a35 saved a greeting "hi" that later
trace 019e040b recalled for a technical query. Gate now skips writes for
general-intent + no-tool turns.
"""

from __future__ import annotations

import asyncio
import logging

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from src.services.agent._nodes_rag import _coerce_text, is_conversational
from src.services.agent._pii_redact import redact_pii
from src.services.agent.observability import track_node_execution
from src.services.agent.state import AgentState

logger = logging.getLogger(__name__)


@track_node_execution("memory_retrieval_node")
async def memory_retrieval_node(state: AgentState, config: RunnableConfig) -> dict:
    """Retrieve relevant long-term memories before the LLM call."""
    configurable = config.get("configurable", {})
    current_user = configurable.get("current_user")

    if not current_user:
        return {"user_memories": []}

    # Find the last user message for memory search.
    last_user_msg = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            last_user_msg = msg.content
            break

    # Greeting / acknowledgement fast-path. Conversational turns ("hi",
    # "thanks", "ok") never benefit from long-term recall, and the save gate
    # in ``memory_save_node`` never persists them — so there is provably
    # nothing to retrieve. Skip the Cohere query-embedding + Postgres
    # semantic search (~0.5-2s on the parallel-preprocessing critical path).
    # Shares the predicate with ``rag_node`` so both nodes agree on what
    # counts as small talk. (Trace 019e9ef7: "hi" embedded the query and
    # recalled 5 sub-0.5-score noise memories.)
    if is_conversational(last_user_msg):
        return {"user_memories": []}

    try:
        from src.services.agent.memory import get_memory_store, search_memories

        store = await get_memory_store()
        if not store:
            return {"user_memories": []}

        memories = await search_memories(
            store, str(current_user.id), last_user_msg, limit=5
        )
        # Defense-in-depth — search_memories already passes limit=5 to the
        # store, but a misbehaving backend (or a future bump in callers)
        # could return more. Sorting by score puts the ranked entries
        # first so the LLM prompt only carries the strongest matches.
        memories.sort(key=lambda m: m.get("score") or 0.0, reverse=True)
        memories = memories[:5]
        try:
            from src.services.agent import observability as _obs

            max_score = (
                max((m.get("score") or 0.0) for m in memories)
                if memories
                else None
            )
            _obs.record_memory_recall(hit=bool(memories), max_score=max_score)
        except Exception:
            pass
        return {"user_memories": memories}
    except Exception as e:
        logger.warning("Memory recall failed: %s", e)
        return {"user_memories": []}


@track_node_execution("memory_save_node")
async def memory_save_node(state: AgentState, config: RunnableConfig) -> dict:
    """Save relevant information from the conversation to long-term memory."""
    configurable = config.get("configurable", {})
    current_user = configurable.get("current_user")

    # Append per-turn iteration record (audit trail) before any early
    # return — even no-user turns (test fixtures, anonymous probes) get
    # logged when AGENT_LEDGER_DIR is set. Best-effort, never raises.
    try:
        from src.services.agent.iteration_ledger import write_iteration

        thread_id = configurable.get("thread_id") or state.get("thread_id") or ""
        if thread_id:
            # Offload the synchronous ledger write (mkdir/write_text/os.replace)
            # so it never blocks the event loop / token streaming.
            await asyncio.to_thread(write_iteration, thread_id, dict(state))
    except Exception as _ledger_exc:  # noqa: BLE001 - observability must not crash
        logger.debug("ledger write skipped: %s", _ledger_exc)

    if not current_user:
        return {}

    # Save gate. Trace evidence (019e066b-2a35) showed every greeting
    # ("hi", "thanks") was persisted and later recalled as noise on
    # technical queries. Only persist turns that either committed to a
    # specialised intent OR ran a tool — those are the turns whose
    # recall has any chance of helping a future query.
    intent = state.get("intent") or ""
    tool_executions = state.get("tool_executions") or []
    if intent in ("", "general") and not tool_executions:
        return {}

    try:
        from src.services.agent.memory import get_memory_store, save_memory

        store = await get_memory_store()
        if not store:
            return {}

        # Extract the last assistant message for memory. Coerce: multimodal
        # content is a list of blocks, and the slice/encode below would
        # raise on it (the save is best-effort, so the memory would just be
        # silently lost).
        last_ai_content = ""
        last_user_content = ""
        for msg in reversed(state["messages"]):
            if isinstance(msg, AIMessage) and msg.content and not last_ai_content:
                last_ai_content = _coerce_text(msg.content)
            if isinstance(msg, HumanMessage) and not last_user_content:
                last_user_content = _coerce_text(msg.content)
            if last_ai_content and last_user_content:
                break

        if not last_user_content:
            return {}

        # Save a condensed memory of the interaction
        import hashlib
        from datetime import datetime, timezone

        mem_key = hashlib.md5(
            last_user_content[:100].encode(), usedforsecurity=False
        ).hexdigest()[:12]

        thread_id = (
            configurable.get("thread_id") or state.get("thread_id") or ""
        )
        turn_index = len(
            [m for m in state["messages"] if isinstance(m, HumanMessage)]
        )

        await save_memory(
            store,
            str(current_user.id),
            mem_key,
            {
                "query": redact_pii(last_user_content)[:200],
                "intent": intent,
                "tools_used": [
                    te.get("tool_name", "")
                    for te in tool_executions[-3:]
                ],
                "thread_id": thread_id,
                "turn_index": turn_index,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        # Insight extraction every N turns. Cheap LLM call distills
        # the conversation into preference-shaped strings that are
        # far more useful for future recall than echoed user input.
        from src.core.config import get_settings

        every_n = get_settings().AGENT_INSIGHT_EVERY_N_TURNS
        if every_n > 0 and turn_index > 0 and turn_index % every_n == 0:
            try:
                from src.services.agent.memory_store import extract_insights

                serialised = [
                    {"role": "user" if isinstance(m, HumanMessage) else "assistant",
                     "content": m.content}
                    for m in state["messages"]
                    if getattr(m, "content", "")
                ]
                insights = await extract_insights(serialised, config)
                for i, insight in enumerate(insights):
                    if not insight or len(insight) < 10:
                        continue
                    insight_key = hashlib.md5(
                        f"insight:{turn_index}:{i}:{insight[:60]}".encode(),
                        usedforsecurity=False,
                    ).hexdigest()[:12]
                    await save_memory(
                        store,
                        str(current_user.id),
                        insight_key,
                        {
                            "query": redact_pii(insight)[:300],
                            "intent": "insight",
                            "tools_used": [],
                            "thread_id": thread_id,
                            "turn_index": turn_index,
                            "created_at": datetime.now(timezone.utc).isoformat(),
                            "memory_type": "insight",
                        },
                    )
            except Exception as exc:  # noqa: BLE001
                logger.debug("insight extraction skipped: %s", exc)
        return {}
    except Exception as e:
        logger.warning("Memory save failed: %s", e)
        return {}


__all__ = ["memory_retrieval_node", "memory_save_node"]
