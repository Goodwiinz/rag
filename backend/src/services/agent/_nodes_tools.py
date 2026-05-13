"""Tool execution + interrupt nodes for the agent graph.

Extracted from ``graph.py`` so the orchestration module stays under the
800-line house rule. ``graph.py`` re-exports every public name so legacy
imports (``from src.services.agent.graph import tool_node, interrupt_node,
make_filtered_tool_node, DESTRUCTIVE_TOOLS, AGENT_LLM_TIMEOUT_SECONDS,
TOOL_TIMEOUT_SECONDS``) keep working without rewriting subgraphs/tests.

Contracts:
- ``tool_node`` / ``filtered_tool_node`` execute pending tool_calls in
  parallel under a per-loop semaphore, with per-call timeout + retry,
  and emit a ``ToolMessage`` for every ``tool_call`` in the originating
  ``AIMessage`` (OpenAI contract).
- ``interrupt_node`` pauses the graph via LangGraph ``interrupt()`` when
  the pending tool calls include any destructive tool.

Why these constants live here:
- ``TOOL_TIMEOUT_SECONDS`` / ``_SLOW_TOOL_TIMEOUT_SECONDS`` / ``_SLOW_TOOLS``
  control per-call wall-clock and which tools deserve the extended budget.
- ``_NO_OUTER_RETRY_TOOLS`` skips the outer ``retry_transient`` for tools
  whose internal client already retries (arxiv) — trace ``019e040b``
  showed stacking pushed search_arxiv to ~85s.
- ``AGENT_LLM_TIMEOUT_SECONDS`` is consumed by every LLM node (main +
  subgraphs) so it must be importable from a single canonical location.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import weakref
from typing import List

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt

from src.services.agent.error_recovery import (
    classify_error,
    classify_error_from_payload,
    retry_transient,
)
from src.services.agent.observability import track_node_execution
from src.services.agent.state import AgentState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Destructive-tool gate (consumed by ``interrupt_node``)
# ---------------------------------------------------------------------------

DESTRUCTIVE_TOOLS = {
    "ingest_arxiv_papers",
    "add_document_to_project",
    "create_project",
    "create_project_note",
    "create_draft",
    "execute_code",
}


@track_node_execution("interrupt_node")
async def interrupt_node(state: AgentState, config: RunnableConfig) -> dict:
    """Check if pending tool calls are destructive and interrupt for confirmation."""
    last_message = state["messages"][-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {}

    destructive_calls = [
        tc for tc in last_message.tool_calls if tc["name"] in DESTRUCTIVE_TOOLS
    ]

    if not destructive_calls:
        return {"pending_confirmation": {}, "user_confirmed": True}

    confirmation_details = {
        "tools": [{"name": tc["name"], "args": tc["args"]} for tc in destructive_calls],
        "message": f"The agent wants to execute {len(destructive_calls)} action(s) that modify your data. Please confirm.",
    }

    # LangGraph interrupt — pauses graph, saves state, returns to caller
    user_response = interrupt(confirmation_details)

    if user_response and user_response.get("confirmed"):
        return {"pending_confirmation": {}, "user_confirmed": True}

    # User denied — add a message explaining and skip tool execution
    return {
        "messages": [
            AIMessage(
                content="Action cancelled by user. Let me know if you'd like to proceed differently."
            ),
        ],
        "pending_confirmation": {},
        "user_confirmed": False,
    }


# ---------------------------------------------------------------------------
# Tool execution timeouts + concurrency
# ---------------------------------------------------------------------------

TOOL_TIMEOUT_SECONDS = 30
_SLOW_TOOL_TIMEOUT_SECONDS = 120  # ingest, draft generation, etc.
_SLOW_TOOLS = {"ingest_arxiv_papers", "create_draft", "compare_documents"}

# Tools that already handle their own retry/backoff internally. Outer
# retry_transient stacks on top and amplifies wall-clock — trace 019e040b
# showed search_arxiv at 85.5s = (3s rate gate + 20s httpx + 30s outer
# wait_for) × 2 attempts + 1s backoff. arxiv_service.py has its own 429
# loop + exponential backoff; ingest_arxiv_papers downloads with retry
# (arxiv_service._download_pdf). One outer attempt is enough.
_NO_OUTER_RETRY_TOOLS = {
    "search_arxiv",
    "ingest_arxiv_papers",
}

# Wall-clock cap for any agent-LLM invocation (main llm_node + subgraph
# LLM nodes). Without this, a stalled Azure/OpenAI socket leaves the node
# task unbounded on the server even after the SSE client cancels (~30s
# default), surfacing as CancelledError in LangSmith with no recovery.
# Trace 019e04fc showed writing_llm_node cancelled at exactly 30s with no
# fallback message. Picked at 90s: gpt-5 reasoning + tool synthesis can
# legitimately take ~70s (trace 019e191a).
AGENT_LLM_TIMEOUT_SECONDS = 90


def _resolve_tool_concurrency(default: int = 3) -> int:
    """Read AGENT_TOOL_CONCURRENCY from env, falling back to *default*."""
    raw = os.getenv("AGENT_TOOL_CONCURRENCY")
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(1, value)


# Per-event-loop semaphore. Module-scope Semaphore captures the FIRST
# loop it sees (binds at import time) — pytest creates a fresh loop per
# test → RuntimeError "got Future attached to a different loop". Multi-
# worker uvicorn under spawn mode hits the same issue. Lazy-init per loop
# via WeakKeyDictionary so the right semaphore is reused for the lifetime
# of each loop without leaking references after the loop is closed.
_TOOL_SEMAPHORES: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore]" = (
    weakref.WeakKeyDictionary()
)


def _get_tool_semaphore() -> asyncio.Semaphore:
    """Return the tool concurrency semaphore bound to the current loop."""
    loop = asyncio.get_running_loop()
    sem = _TOOL_SEMAPHORES.get(loop)
    if sem is None:
        sem = asyncio.Semaphore(_resolve_tool_concurrency(default=3))
        _TOOL_SEMAPHORES[loop] = sem
    return sem


def _record_tool_metrics(tool_name: str, status: str):
    """Record tool call metrics if observability is available."""
    try:
        from src.services.agent.observability import record_tool_call

        record_tool_call(tool_name, status)
    except Exception:
        pass


def _record_tool_error_category(tool_name: str, category: str) -> None:
    """Record classified tool error for dashboard pivots."""
    try:
        from src.services.agent.observability import record_tool_error

        record_tool_error(tool=tool_name, category=category)
    except Exception:
        pass


async def _execute_single_tool(
    tc: dict,
    config: RunnableConfig,
    page_context: dict,
) -> dict:
    """Execute a single tool call with timeout, retry, and structured error recovery."""
    # Lazy imports avoid circular dep with graph.py (which exposes the
    # tool executor + the json-safe parser used in tool_executions).
    from src.services.agent.graph import _get_execute_tool, _safe_json_loads

    tool_executor = _get_execute_tool()

    tool_name = tc["name"]
    tool_args = dict(tc["args"])
    tool_call_id = tc["id"]

    # Auto-fill project_id from page context if not provided by LLM
    if (
        "project_id" not in tool_args
        and page_context.get("type") == "project"
        and page_context.get("project_id")
    ):
        tool_args["project_id"] = page_context["project_id"]

    t0 = time.monotonic()
    error_increment = 0
    error_text = ""
    error_info: dict = {}

    timeout = (
        _SLOW_TOOL_TIMEOUT_SECONDS if tool_name in _SLOW_TOOLS else TOOL_TIMEOUT_SECONDS
    )

    async with _get_tool_semaphore():
        try:
            configurable = config.get("configurable", {})

            current_user = configurable.get("current_user")

            async def _call_tool(args: dict):
                return await asyncio.wait_for(
                    tool_executor(
                        tool_name=tool_name,
                        args=args,
                        user_id=str(current_user.id) if current_user else "",
                        db=configurable.get("db"),
                        current_user=current_user,
                    ),
                    timeout=timeout,
                )

            # Wrap with langsmith.traceable so per-tool spans land in LangSmith
            # as run_type="tool". Previously zero tool spans existed because
            # the tool_executor isn't a LangChain Tool — LangSmith had no
            # visibility into arXiv 429s, KG latency, Qdrant retrieval, etc.
            # Dynamic name keeps each tool distinguishable in the trace tree.
            from langsmith import traceable as _ls_traceable

            traced_call = _ls_traceable(run_type="tool", name=tool_name)(_call_tool)

            # retry_transient handles TimeoutError/ConnectionError with backoff.
            # max_attempts dropped from 3 → 2 after trace 019e1910 showed
            # arxiv API hung 93s (3 × 30s timeout + backoff) which exceeded
            # the CLI 90s idle window. Failing faster surfaces the issue
            # while keeping one safety-net retry for genuine transient blips.
            # Tools that retry internally (arxiv) skip the outer retry to
            # avoid 2× wall-clock amplification (trace 019e040b: 85.5s).
            _outer_attempts = 1 if tool_name in _NO_OUTER_RETRY_TOOLS else 2
            result = await retry_transient(
                lambda: traced_call(tool_args),
                max_attempts=_outer_attempts,
                base_delay=1.0,
            )

            result_content = (
                json.dumps(result) if isinstance(result, dict) else str(result)
            )
            status = "completed"

            # Check if the result payload itself indicates an error
            if isinstance(result, dict) and "error" in result:
                tool_error = classify_error_from_payload(tool_name, result)
                if tool_error.category != "transient":
                    status = "failed"
                    error_increment = 1
                    error_text = tool_error.message
                    error_info = tool_error.to_state_info()
                    result_content = tool_error.to_tool_message_content()
                    _record_tool_error_category(tool_name, tool_error.category)
                # Transient payload errors: already retried by retry_transient above
        except Exception as e:
            tool_error = classify_error(tool_name, e)
            logger.error(
                "Tool %s failed (%s): %s",
                tool_name,
                tool_error.category,
                e,
                exc_info=True,
            )
            status = "failed"
            error_increment = 1 if tool_error.category != "transient" else 0
            error_text = tool_error.message
            error_info = tool_error.to_state_info()
            result_content = tool_error.to_tool_message_content()
            _record_tool_error_category(tool_name, tool_error.category)

    duration_ms = int((time.monotonic() - t0) * 1000)
    _record_tool_metrics(tool_name, status)

    return {
        "message": ToolMessage(content=result_content, tool_call_id=tool_call_id),
        "execution": {
            "id": tool_call_id,
            "tool_name": tool_name,
            "tool_display_name": tool_name.replace("_", " ").title(),
            "args": tool_args,
            "status": status,
            "result": _safe_json_loads(result_content),
            "duration_ms": duration_ms,
        },
        "error_increment": error_increment,
        "error_text": error_text,
        "error_info": error_info,
    }


@track_node_execution("tool_node")
async def tool_node(state: AgentState, config: RunnableConfig) -> dict:
    """Execute tool calls from the last AIMessage in parallel."""
    last_message = state["messages"][-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {"messages": [], "tool_executions": []}

    tool_executions: List[dict] = list(state.get("tool_executions", []))
    error_count = state.get("error_count", 0)
    last_error = state.get("last_error", "")
    last_error_info = state.get("last_error_info", {})
    page_context = state.get("page_context", {})

    # Per-turn dedupe: skip tool_calls whose (name, args) already ran this
    # turn. The cached result is returned with a "[deduped...]" prefix so
    # the model sees both the data and a stop signal.
    from src.services.agent.tool_dedupe import (
        build_deduped_execution_entry,
        build_deduped_tool_message,
        find_cached_tool_results,
    )

    cached = find_cached_tool_results(
        last_message.tool_calls, state["messages"], tool_executions
    )
    fresh_calls = [
        tc for tc in last_message.tool_calls if tc["id"] not in cached
    ]

    # Execute all NEW tool calls concurrently with semaphore limiting
    tasks = [_execute_single_tool(tc, config, page_context) for tc in fresh_calls]
    fresh_results = await asyncio.gather(*tasks, return_exceptions=True)
    fresh_by_id = {tc["id"]: r for tc, r in zip(fresh_calls, fresh_results)}

    tool_messages: List[ToolMessage] = []
    any_failure = False
    all_success = True
    # Iterate in the original tool_calls order so ToolMessage ids line up
    # with the AIMessage's tool_calls array as the OpenAI API requires.
    for tc in last_message.tool_calls:
        if tc["id"] in cached:
            prior = cached[tc["id"]]
            tool_messages.append(build_deduped_tool_message(tc["id"], prior))
            tool_executions.append(
                build_deduped_execution_entry(tc["id"], tc, prior)
            )
            continue
        r = fresh_by_id.get(tc["id"])
        if r is None:
            # Defensive: every fresh_call should map to a result. If a
            # future change drops one (cancellation, gather edge case),
            # emit a synthetic error ToolMessage so the OpenAI contract
            # "every tool_call.id must be answered" still holds.
            logger.error(
                "tool_node: missing result for tool_call %s; emitting synthetic error",
                tc["id"],
            )
            error_count += 1
            last_error = "tool execution lost (internal)"
            any_failure = True
            all_success = False
            tool_messages.append(
                ToolMessage(
                    content=json.dumps({"error": last_error}),
                    tool_call_id=tc["id"],
                )
            )
            continue
        if isinstance(r, BaseException):
            logger.error("Parallel tool execution error: %s", r)
            error_count += 1
            last_error = str(r)
            any_failure = True
            all_success = False
            tool_messages.append(
                ToolMessage(
                    content=json.dumps({"error": str(r)}),
                    tool_call_id=tc["id"],
                )
            )
            continue
        tool_messages.append(r["message"])
        tool_executions.append(r["execution"])
        error_count += r["error_increment"]
        if r["error_text"]:
            last_error = r["error_text"]
        if r.get("error_info"):
            last_error_info = r["error_info"]
        if r["error_increment"] != 0:
            any_failure = True
            all_success = False

    # Reset the consecutive-error counter ONLY when every tool in this
    # batch succeeded. A mixed-success batch (some succeed, some fail) is
    # still a failing batch from the circuit-breaker's perspective —
    # otherwise an LLM stuck in a "1 success + N failures" loop would
    # keep zeroing out the counter and never trip MAX_ERRORS.
    if all_success and not any_failure:
        error_count = 0
        last_error = ""

    # Prune to last 20 entries to prevent unbounded growth
    tool_executions = tool_executions[-20:]

    return {
        "messages": tool_messages,
        "tool_executions": tool_executions,
        "error_count": error_count,
        "last_error": last_error,
        "last_error_info": last_error_info,
        "tool_loop_count": state.get("tool_loop_count", 0) + 1,
    }


def make_filtered_tool_node(allowed_tool_names: set[str]):
    """Create a tool_node wrapper that only executes tools in the allowed set.

    Tool calls not in the allowed set are skipped with a warning ToolMessage.
    """

    @track_node_execution("filtered_tool_node")
    async def filtered_tool_node(state: AgentState, config: RunnableConfig) -> dict:
        last_message = state["messages"][-1]
        if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
            return {"messages": [], "tool_executions": []}

        # Filter tool calls
        allowed_calls = []
        skipped_messages = []
        for tc in last_message.tool_calls:
            if tc["name"] in allowed_tool_names:
                allowed_calls.append(tc)
            else:
                logger.warning(
                    "Subgraph skipping out-of-scope tool call: %s (allowed: %s)",
                    tc["name"],
                    allowed_tool_names,
                )
                skipped_messages.append(
                    ToolMessage(
                        content=json.dumps(
                            {
                                "error": f"Tool '{tc['name']}' is not available in this context. "
                                f"Available tools: {', '.join(sorted(allowed_tool_names))}"
                            }
                        ),
                        tool_call_id=tc["id"],
                    )
                )

        if not allowed_calls:
            return {
                "messages": skipped_messages,
                "tool_executions": list(state.get("tool_executions", [])),
                "error_count": state.get("error_count", 0),
                "last_error": state.get("last_error", ""),
                "tool_loop_count": state.get("tool_loop_count", 0) + 1,
            }

        # Execute allowed tools using existing tool_node logic
        tool_executions = list(state.get("tool_executions", []))
        error_count = state.get("error_count", 0)
        last_error = state.get("last_error", "")
        last_error_info: dict = {}
        page_context = state.get("page_context", {})

        # Per-turn dedupe — mirrors tool_node. Keeps research subgraph in
        # sync with the main graph's dedupe semantics.
        from src.services.agent.tool_dedupe import (
            build_deduped_execution_entry,
            build_deduped_tool_message,
            find_cached_tool_results,
        )

        cached = find_cached_tool_results(
            allowed_calls, state["messages"], tool_executions
        )
        fresh_calls = [tc for tc in allowed_calls if tc["id"] not in cached]

        tasks = [_execute_single_tool(tc, config, page_context) for tc in fresh_calls]
        fresh_results = await asyncio.gather(*tasks, return_exceptions=True)
        fresh_by_id = {tc["id"]: r for tc, r in zip(fresh_calls, fresh_results)}

        tool_messages = list(skipped_messages)
        any_failure = False
        all_success = True
        for tc in allowed_calls:
            if tc["id"] in cached:
                prior = cached[tc["id"]]
                tool_messages.append(build_deduped_tool_message(tc["id"], prior))
                tool_executions.append(
                    build_deduped_execution_entry(tc["id"], tc, prior)
                )
                continue
            r = fresh_by_id.get(tc["id"])
            if r is None:
                logger.error(
                    "filtered_tool_node: missing result for tool_call %s; "
                    "emitting synthetic error",
                    tc["id"],
                )
                error_count += 1
                last_error = "tool execution lost (internal)"
                any_failure = True
                all_success = False
                tool_messages.append(
                    ToolMessage(
                        content=json.dumps({"error": last_error}),
                        tool_call_id=tc["id"],
                    )
                )
                continue
            if isinstance(r, BaseException):
                logger.error("Parallel tool execution error: %s", r)
                error_count += 1
                last_error = str(r)
                any_failure = True
                all_success = False
                tool_messages.append(
                    ToolMessage(
                        content=json.dumps({"error": str(r)}),
                        tool_call_id=tc["id"],
                    )
                )
                continue
            tool_messages.append(r["message"])
            tool_executions.append(r["execution"])
            error_count += r["error_increment"]
            if r["error_text"]:
                last_error = r["error_text"]
            if r.get("error_info"):
                last_error_info = r["error_info"]
            if r["error_increment"] != 0:
                any_failure = True
                all_success = False

        # Reset the consecutive-error counter only when EVERY tool in
        # this batch succeeded (mirrors the main ``tool_node`` logic so
        # the subgraph circuit-breaker behaves identically).
        if all_success and not any_failure:
            error_count = 0
            last_error = ""

        # Prune to last 20 entries to prevent unbounded growth
        tool_executions = tool_executions[-20:]

        return {
            "messages": tool_messages,
            "tool_executions": tool_executions,
            "error_count": error_count,
            "last_error": last_error,
            "last_error_info": last_error_info,
            "tool_loop_count": state.get("tool_loop_count", 0) + 1,
        }

    return filtered_tool_node


__all__ = [
    "DESTRUCTIVE_TOOLS",
    "interrupt_node",
    "tool_node",
    "make_filtered_tool_node",
    "TOOL_TIMEOUT_SECONDS",
    "AGENT_LLM_TIMEOUT_SECONDS",
    "_SLOW_TOOL_TIMEOUT_SECONDS",
    "_SLOW_TOOLS",
    "_NO_OUTER_RETRY_TOOLS",
    "_execute_single_tool",
    "_get_tool_semaphore",
]
