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

# MAX_TOOL_LOOPS lives in _builders alongside MAX_ERRORS; re-exported at
# the bottom of this module via the builders import.


def _safe_json_loads(s: str) -> Any:
    """Parse JSON, returning a fallback dict if parsing fails."""
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return {"raw": s}



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
    is_conversational,
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

# Prompt content + render helpers (re-exported for subgraphs/tests/classifier).
# Subgraph LLM nodes look these up via lazy import on every call, so they
# must resolve from graph.py for back-compat with pre-T2.1 wiring.
from src.services.agent._prompts import (  # noqa: E402
    INTENT_PROMPTS,
    SHARED_AGENT_RULES,
    _LLM_NODE_STATIC_PROMPT,
    _build_page_context_line,
    _merge_run_config,
    _runtime_model_line,
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
# Intent classification + parallel preprocessing — moved to _nodes_classify.
# Re-export for callers (`from src.services.agent.graph import
# preprocessing_node, route_by_intent`) and for tests patching
# the classifier path.
# ---------------------------------------------------------------------------

from src.services.agent._nodes_classify import (  # noqa: E402
    _classify_core,
    _extract_prior_tool,
    intent_classifier_node,
    preprocessing_node,
    route_by_intent,
)


# ---------------------------------------------------------------------------
# Graph builders + conditional edges — moved to _builders. Re-export so
# langgraph.json's `create_graph`, jobs.compile_agent_graph callers, and
# tests importing `should_continue` / `MAX_ERRORS` / `MAX_TOOL_LOOPS`
# keep working unchanged.
# ---------------------------------------------------------------------------

from src.services.agent._builders import (  # noqa: E402
    MAX_ERRORS,
    MAX_TOOL_LOOPS,
    after_interrupt,
    build_agent_graph,
    compile_agent_graph,
    create_graph,
    should_continue,
)
