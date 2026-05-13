"""LangGraph agent graph definition.

Builds a ``StateGraph`` that chains:
  START -> rag_node -> llm_node -> [conditional] -> tool_node -> llm_node (loop) | END
"""

import asyncio
import json
import logging
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional

# Matches a UUID anywhere in a string. Used to extract project IDs from URLs
# or raw UUIDs that the user pastes into the conversation so the agent can
# carry the context forward across turns.
from src.services.agent._uuid import UUID_SEARCH_RE as _UUID_RE


def _extract_project_id_from_text(text: str) -> Optional[str]:
    """Return the first project UUID found in *text*, preferring ``/projects/<uuid>``.

    Falls back to any standalone UUID in the text. Returns ``None`` if no
    UUID is present.
    """
    if not text:
        return None
    project_url_match = re.search(
        r"/projects/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
        text,
    )
    if project_url_match:
        return project_url_match.group(1).lower()
    bare_match = _UUID_RE.search(text)
    return bare_match.group(1).lower() if bare_match else None


from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph


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
                tm = ToolMessage(
                    content=_TOOL_PLACEHOLDER_CONTENT, tool_call_id=tc_id
                )
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


from langgraph.types import RetryPolicy, interrupt, Command

from src.core.config import get_settings
from src.core.openai_endpoint import classify_openai_endpoint
from src.services.agent.compactor import make_compactor_node
from src.services.agent.error_recovery import (
    ToolError,
    classify_error,
    classify_error_from_payload,
    retry_transient,
)
from src.services.agent.observability import track_node_execution
from src.services.agent.planner import make_planner_node
from src.services.agent.reflection import make_reflection_gate
from src.services.agent.state import AgentState
from src.services.agent.tools import ALL_TOOLS

# Lazy reference for execute_tool (avoids circular import, enables patching)
execute_tool = None  # type: ignore[assignment]
_default_execute_tool = None  # type: ignore[assignment]
_execute_tool_lock = threading.Lock()


def _get_execute_tool():
    """Lazily import execute_tool and keep it patch-friendly.

    The agent tests patch both ``src.services.agent.graph.execute_tool`` and
    the backward-compatible re-export at ``src.api.agent.execute.execute_tool``.
    After the API split, caching the first imported callable caused later
    re-export patches to be ignored. We only refresh the cached callable when
    graph.py is still pointing at the last default import.
    """
    global execute_tool, _default_execute_tool  # noqa: PLW0603

    with _execute_tool_lock:
        if execute_tool is None:
            from src.api.agent.execute import execute_tool as _et

            execute_tool = _et
            _default_execute_tool = _et
            return execute_tool

        from src.api.agent.execute import execute_tool as _et

        if execute_tool is _default_execute_tool:
            execute_tool = _et
            _default_execute_tool = _et

        return execute_tool


logger = logging.getLogger(__name__)

MAX_TOOL_LOOPS = 10


def _safe_json_loads(s: str) -> Any:
    """Parse JSON, returning a fallback dict if parsing fails."""
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return {"raw": s}


def _escape_like(s: str) -> str:
    """Escape SQL LIKE wildcards in untrusted strings.

    Storage keys come from the DO Knowledge Base API — an external service.
    Backslash escapes both ``%`` (multi-char wildcard) and ``_`` (single
    char) so a malformed/malicious key cannot broaden the suffix match.
    Use with ``Column.like(pattern, escape='\\\\')``.
    """
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ---------------------------------------------------------------------------
# LLM construction
# ---------------------------------------------------------------------------

_LLM_CACHE: dict[tuple[str, str], BaseChatModel] = {}


def _build_llm(model_override: str | None = None):
    """Build a LangChain chat model from the existing Azure/OpenAI config.

    ``model_override`` lets a per-request deployment name win over the configured
    default — used to make the agent honor ``request.model`` from the API.

    Clients are cached by ``(endpoint_type, deployment)`` to avoid rebuilding
    the HTTP client on every ``llm_node`` invocation (~30-50 ms each).
    """
    settings = get_settings()

    endpoint = (
        settings.AZURE_OPENAI_CHAT_ENDPOINT or settings.AZURE_OPENAI_ENDPOINT or ""
    )
    api_key = settings.AZURE_OPENAI_CHAT_API_KEY or settings.AZURE_OPENAI_API_KEY or ""
    api_version = (
        settings.AZURE_OPENAI_CHAT_API_VERSION or settings.AZURE_OPENAI_API_VERSION
    )
    deployment = (
        model_override
        or settings.AZURE_OPENAI_CHAT_DEPLOYMENT_NAME
        or settings.AZURE_OPENAI_DEPLOYMENT_NAME
    )

    if not endpoint or not api_key:
        raise RuntimeError(
            "Azure/OpenAI chat endpoint and API key must be configured. "
            "Set AZURE_OPENAI_CHAT_ENDPOINT + AZURE_OPENAI_CHAT_API_KEY "
            "(or the non-CHAT variants)."
        )

    if not deployment:
        raise RuntimeError(
            "Chat deployment name must be configured. Set "
            "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME (or AZURE_OPENAI_DEPLOYMENT_NAME)."
        )

    endpoint_type = classify_openai_endpoint(endpoint)
    cache_key = (endpoint_type, deployment)
    if cache_key in _LLM_CACHE:
        return _LLM_CACHE[cache_key]

    # All gpt-5 family deployments (gpt-5, gpt-5-mini, gpt-5-nano, etc.)
    # reject custom temperature — Azure returns 400. Drop it for the whole
    # family rather than per-deployment allowlist.
    temperature = None if deployment.startswith("gpt-5") else 0.7

    # gpt-5 family supports reasoning_effort to trade reasoning depth for
    # latency. Defaults to "low" for fast agent loops; raise via settings
    # for harder reasoning tasks. Non-gpt-5 deployments ignore this kwarg.
    reasoning_effort = settings.AGENT_MAIN_REASONING_EFFORT
    is_gpt5_family = deployment.startswith("gpt-5") if deployment else False

    # Force Chat Completions API. langchain-openai auto-routes gpt-5 family
    # with reasoning_effort to the Azure Responses API, which currently rejects
    # the agent's tool_call message history with "Unsupported data type". The
    # Chat Completions path handles tool_calls reliably and supports
    # reasoning_effort on gpt-5 deployments via api-version 2024-10-21+.
    # Bound LLM call wall-clock + cap retries. Prevents the model-router hang
    # observed in LangSmith (traces with end_time=null blocking root 70s+).
    request_timeout = settings.AGENT_LLM_REQUEST_TIMEOUT
    max_retries = settings.AGENT_LLM_MAX_RETRIES

    if endpoint_type == "openai_compatible":
        from langchain_openai import ChatOpenAI

        kwargs: dict = dict(
            model=deployment,
            api_key=api_key,
            base_url=endpoint,
            max_tokens=4096,
            use_responses_api=False,
            request_timeout=request_timeout,
            max_retries=max_retries,
        )
        if temperature is not None:
            kwargs["temperature"] = temperature
        if is_gpt5_family and reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
        llm = ChatOpenAI(**kwargs)
    else:
        from langchain_openai import AzureChatOpenAI

        kwargs = dict(
            azure_deployment=deployment,
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
            max_tokens=4096,
            use_responses_api=False,
            request_timeout=request_timeout,
            max_retries=max_retries,
        )
        if temperature is not None:
            kwargs["temperature"] = temperature
        if is_gpt5_family and reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
        llm = AzureChatOpenAI(**kwargs)

    _LLM_CACHE[cache_key] = llm
    return llm


# ---------------------------------------------------------------------------
# Memory nodes
# ---------------------------------------------------------------------------


# Memory recall/save nodes now live in _nodes_memory. Re-export so
# legacy imports (`from src.services.agent.graph import memory_save_node`)
# keep working without rewriting tests/callers.
from src.services.agent._nodes_memory import (  # noqa: E402
    memory_retrieval_node,
    memory_save_node,
)


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------


# rag_node + DO KB / hybrid search helpers + conversational fast-path
# heuristics live in _nodes_rag. Re-export so legacy callers
# (`from src.services.agent.graph import rag_node`) keep working.
from src.services.agent._nodes_rag import (  # noqa: E402
    _is_retrieval_query,
    _legacy_hybrid_search_fallback,
    _shape_do_kb_context,
    _try_primary_do_kb_read,
    rag_node,
)


# ---------------------------------------------------------------------------
# Intent classification
# ---------------------------------------------------------------------------

# Weighted keywords: (keyword, weight)
# Action verbs get higher weight; ambiguous nouns get lower weight
# Classifier hints live in _prompts; re-exported here so legacy imports
# (`from src.services.agent.graph import INTENT_KEYWORDS, INTENT_PRIORITY`)
# keep working without churn.
from src.services.agent._prompts import (  # noqa: E402  (re-export)
    INTENT_KEYWORDS,
    INTENT_PRIORITY,
)


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

    last_user_msg = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            last_user_msg = msg.content
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
            previous_turn = msg.content
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
    }
    for result, default in zip(results, defaults):
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


# ---------------------------------------------------------------------------
# Intent-specific tool subsets + main LLM node — moved to _nodes_llm.
# Re-export so legacy callers
# (`from src.services.agent.graph import llm_node, RESEARCH_TOOLS_NAMES`)
# keep working unchanged.
# ---------------------------------------------------------------------------

from src.services.agent._nodes_llm import (  # noqa: E402
    GENERAL_TOOLS_NAMES,
    KG_TOOLS_NAMES,
    RESEARCH_TOOLS_NAMES,
    WRITING_TOOLS_NAMES,
    _get_tools_for_intent,
    llm_node,
)

# Prompt content (re-exported for subgraphs/tests/classifier).
from src.services.agent._prompts import (  # noqa: E402
    INTENT_PROMPTS,
    SHARED_AGENT_RULES,
    _LLM_NODE_STATIC_PROMPT,
)


# Tool execution + interrupt + concurrency constants now live in
# _nodes_tools. Re-export so legacy imports
# (`from src.services.agent.graph import tool_node, interrupt_node,
# DESTRUCTIVE_TOOLS, AGENT_LLM_TIMEOUT_SECONDS, TOOL_TIMEOUT_SECONDS,
# make_filtered_tool_node`) keep working without rewriting subgraphs/tests.
from src.services.agent._nodes_tools import (  # noqa: E402
    AGENT_LLM_TIMEOUT_SECONDS,
    DESTRUCTIVE_TOOLS,
    TOOL_TIMEOUT_SECONDS,
    _execute_single_tool,
    _get_tool_semaphore,
    _NO_OUTER_RETRY_TOOLS,
    _SLOW_TOOL_TIMEOUT_SECONDS,
    _SLOW_TOOLS,
    interrupt_node,
    make_filtered_tool_node,
    tool_node,
)


# ---------------------------------------------------------------------------
# Conditional edge
# ---------------------------------------------------------------------------


MAX_ERRORS = 3


def should_continue(state: AgentState) -> str:
    """Decide whether to route to tool_node, interrupt_node, or reflection_gate (then END)."""
    # Bail out if too many errors have accumulated
    if state.get("error_count", 0) >= MAX_ERRORS:
        logger.warning(
            "Agent reached max error count (%d), stopping. Last error: %s",
            MAX_ERRORS,
            state.get("last_error", ""),
        )
        return "reflection_gate"

    last = state["messages"][-1] if state["messages"] else None
    if (
        isinstance(last, AIMessage)
        and last.tool_calls
        and state.get("tool_loop_count", 0) < MAX_TOOL_LOOPS
    ):
        # Check if any tool call is destructive — route through interrupt
        has_destructive = any(tc["name"] in DESTRUCTIVE_TOOLS for tc in last.tool_calls)
        if has_destructive:
            return "interrupt_node"
        return "tool_node"
    return "reflection_gate"


# ---------------------------------------------------------------------------
# Graph builders
# ---------------------------------------------------------------------------


def after_interrupt(state: AgentState) -> str:
    """Route after interrupt: proceed to tool_node if confirmed, else reflection gate and end."""
    if state.get("user_confirmed", False):
        return "tool_node"
    return "reflection_gate"


_RETRY_POLICY = RetryPolicy(max_attempts=3)


def build_agent_graph() -> StateGraph:
    """Build the uncompiled agent state graph.

    Flow:
      START -> preprocessing_node (RAG + classify + memory in parallel)
        -> [route_by_intent]
        -> research_subgraph | writing_subgraph | data_subgraph | general path

      General path:
        planner_node -> llm_node -> [should_continue]
          -> tool_node -> compactor_node -> llm_node (loop)
          -> interrupt_node -> [after_interrupt] -> tool_node | reflection_gate
          -> reflection_gate -> [reflection_route] -> memory_save_node | llm_node (revise)

      Sub-graphs (internal planner + compactor + reflection) -> memory_save_node -> END
    """
    from src.services.agent.subgraphs.data_agent import build_data_subgraph
    from src.services.agent.subgraphs.research_agent import build_research_subgraph
    from src.services.agent.subgraphs.writing_agent import build_writing_subgraph

    # General-path v2 nodes
    tool_names = [t.name for t in ALL_TOOLS]
    planner_node_fn = make_planner_node(tool_names)
    compactor_node_fn = make_compactor_node()
    reflection_node_fn, reflection_route_fn = make_reflection_gate()

    graph = StateGraph(AgentState)

    graph.add_node("preprocessing_node", preprocessing_node)
    graph.add_node("planner_node", planner_node_fn)
    graph.add_node("llm_node", llm_node, retry=_RETRY_POLICY)
    graph.add_node("tool_node", tool_node)
    graph.add_node("compactor_node", compactor_node_fn)
    graph.add_node("interrupt_node", interrupt_node)
    graph.add_node("reflection_gate", reflection_node_fn)
    graph.add_node("memory_save_node", memory_save_node, retry=_RETRY_POLICY)

    # Sub-graphs compiled as nodes (they have internal planner/compactor/reflection)
    graph.add_node("research_subgraph", build_research_subgraph().compile())
    graph.add_node("writing_subgraph", build_writing_subgraph().compile())
    graph.add_node("data_subgraph", build_data_subgraph().compile())

    graph.set_entry_point("preprocessing_node")

    # Route by intent after parallel preprocessing
    graph.add_conditional_edges(
        "preprocessing_node",
        route_by_intent,
        {
            "research_subgraph": "research_subgraph",
            "writing_subgraph": "writing_subgraph",
            "data_subgraph": "data_subgraph",
            "llm_node": "planner_node",
        },
    )

    # Sub-graphs (with internal reflection) -> memory_save_node -> END
    graph.add_edge("research_subgraph", "memory_save_node")
    graph.add_edge("writing_subgraph", "memory_save_node")
    graph.add_edge("data_subgraph", "memory_save_node")

    # General path: planner -> llm
    graph.add_edge("planner_node", "llm_node")

    # General path: llm_node -> conditional
    graph.add_conditional_edges(
        "llm_node",
        should_continue,
        {
            "tool_node": "tool_node",
            "interrupt_node": "interrupt_node",
            "reflection_gate": "reflection_gate",
        },
    )
    graph.add_conditional_edges(
        "interrupt_node",
        after_interrupt,
        {"tool_node": "tool_node", "reflection_gate": "reflection_gate"},
    )

    # General path: tool_node -> compactor_node -> llm_node (loop)
    graph.add_edge("tool_node", "compactor_node")
    graph.add_edge("compactor_node", "llm_node")

    # Reflection gate routes: proceed -> memory_save, revise -> llm_node
    graph.add_conditional_edges(
        "reflection_gate",
        reflection_route_fn,
        {"proceed": "memory_save_node", "revise": "llm_node"},
    )
    graph.add_edge("memory_save_node", END)

    return graph


def compile_agent_graph(checkpointer=None, store=None, **kwargs):
    """Compile the agent graph, optionally with a checkpointer and store.

    ``checkpointer`` may be ``None`` (no checkpointing), an instance of
    ``BaseCheckpointSaver``, or ``True`` to opt into the default in-memory
    saver. Anything else is rejected with a clear error rather than
    silently passing a bool to ``graph.compile()`` (which would crash with
    ``AttributeError`` deep inside LangGraph at runtime).

    ``store`` is an optional ``BaseStore`` for long-term, cross-thread
    memory (user preferences, facts).  When provided, LangGraph injects it
    into nodes that accept a ``Runtime`` parameter so they can use
    ``runtime.store`` instead of importing the singleton directly.
    """
    graph = build_agent_graph()
    from langgraph.checkpoint.base import BaseCheckpointSaver

    compile_kwargs: dict = {}
    if store is not None:
        compile_kwargs["store"] = store

    if checkpointer is None or checkpointer is False:
        return graph.compile(**compile_kwargs)

    if checkpointer is True:
        # Convenience: ``True`` opts into the in-memory default so callers
        # don't have to import MemorySaver themselves.
        from langgraph.checkpoint.memory import MemorySaver

        return graph.compile(checkpointer=MemorySaver(), **compile_kwargs)

    if isinstance(checkpointer, BaseCheckpointSaver):
        return graph.compile(checkpointer=checkpointer, **compile_kwargs)

    raise TypeError(
        "compile_agent_graph(checkpointer=...) must be None, True, False, "
        f"or a BaseCheckpointSaver instance — got {type(checkpointer).__name__}"
    )


def create_graph():
    """No-arg entry point for langgraph dev (langgraph.json)."""
    return compile_agent_graph(checkpointer=True)
