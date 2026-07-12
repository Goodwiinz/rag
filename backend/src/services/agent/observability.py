"""Agent observability and tracing helpers.

Provides custom metrics and tracing for agent execution monitoring.
Dual approach: LangSmith for LangGraph tracing + OpenTelemetry/Prometheus for custom metrics.
"""

import asyncio
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

# LangGraph control-flow signals. interrupt() (HITL confirm for destructive
# tools) raises GraphInterrupt, and Send/Command parent-bubbling raises
# ParentCommand; both subclass GraphBubbleUp. They are normal control flow that
# must propagate to the graph runner — NOT node failures. Catching them in the
# node wrapper's generic ``except Exception`` logged a false ERROR and bumped
# AGENT_ERRORS on every HITL confirm. Import is guarded so observability never
# hard-fails if langgraph is absent (metrics are already optional here).
try:
    from langgraph.errors import GraphBubbleUp as _GraphBubbleUp

    _CONTROL_FLOW_EXC: tuple = (_GraphBubbleUp,)
except ImportError:  # pragma: no cover - langgraph always present in app runtime
    _CONTROL_FLOW_EXC = ()

# Cached LangSmith client for run patching (intent tagging). Building one per
# call re-reads env + sets up a session; cache it behind a lock.
_LS_CLIENT: Any = None
_LS_CLIENT_LOCK = threading.Lock()
# Strong refs to in-flight fire-and-forget tag patches so the loop can't GC them.
_TAG_TASKS: set = set()


def _get_ls_client() -> Any:
    global _LS_CLIENT
    if _LS_CLIENT is not None:
        return _LS_CLIENT
    with _LS_CLIENT_LOCK:
        if _LS_CLIENT is None:
            from langsmith import Client

            _LS_CLIENT = Client()
    return _LS_CLIENT


# ---------------------------------------------------------------------------
# LangSmith configuration
# ---------------------------------------------------------------------------

# Map the many ways a deploy env can be spelled onto the canonical suffix used
# in the LangSmith project name. Anything unrecognised (local shells, CI, eval,
# unset) returns None so the caller can fall back instead of inventing a name.
_DEPLOY_ENV_ALIASES = {
    "dev": "dev",
    "development": "dev",
    "staging": "staging",
    "stage": "staging",
    "prod": "prod",
    "production": "prod",
}


def _normalize_deploy_env() -> Optional[str]:
    """Resolve DEPLOY_ENV/ENVIRONMENT to a canonical ``dev|staging|prod`` suffix.

    Returns ``None`` for unknown/unset envs (local, test, CI) so trace project
    naming stays deliberate rather than guessing.
    """
    raw = (
        (os.environ.get("DEPLOY_ENV") or os.environ.get("ENVIRONMENT") or "")
        .strip()
        .lower()
    )
    return _DEPLOY_ENV_ALIASES.get(raw)


def configure_langsmith():
    """Configure LangSmith tracing if an API key is available.

    Accepts either the modern ``LANGSMITH_*`` names (preferred by the current
    ``langsmith`` SDK) or the legacy ``LANGCHAIN_*`` names. Whichever is
    provided, this propagates to both so libraries on either convention pick
    it up.
    """
    api_key = os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY")
    if not api_key:
        logger.debug(
            "LangSmith tracing disabled " "(no LANGSMITH_API_KEY / LANGCHAIN_API_KEY)"
        )
        return

    os.environ.setdefault("LANGSMITH_API_KEY", api_key)
    os.environ.setdefault("LANGCHAIN_API_KEY", api_key)

    # Project name is derived authoritatively from the deploy environment so a
    # stale externally-injected value (e.g. an old Infisical
    # LANGSMITH_PROJECT=rag-agent-dev-local) can't fragment or mis-route traces.
    # For a recognised deploy env we force rag-agent-{dev|staging|prod}; an
    # explicit LANGSMITH_PROJECT_OVERRIDE always wins (escape hatch for one-off
    # namespaces); otherwise we fall back to any provided value or rag-agent-dev.
    norm_env = _normalize_deploy_env()
    override = os.environ.get("LANGSMITH_PROJECT_OVERRIDE")
    if override:
        project = override
    elif norm_env:
        project = f"rag-agent-{norm_env}"
    else:
        project = (
            os.environ.get("LANGSMITH_PROJECT")
            or os.environ.get("LANGCHAIN_PROJECT")
            or "rag-agent-dev"
        )
    # Force (not setdefault) so the derived value overrides a stale injected one.
    os.environ["LANGSMITH_PROJECT"] = project
    os.environ["LANGCHAIN_PROJECT"] = project

    # Both SDK generations read their own flag; set both to "true" by default.
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGSMITH_TRACING", "true")

    # PII guard: outside dev, do NOT upload run inputs/outputs (user prompts,
    # RAG chunks, tool args) to LangSmith — tags, metadata, latency, and token
    # usage still flow, so dashboards keep working. Override with
    # LANGSMITH_HIDE_IO=false to opt back in. Dev keeps full I/O for debugging.
    hide_io_default = "false" if norm_env == "dev" else "true"
    hide_io = os.environ.get("LANGSMITH_HIDE_IO", hide_io_default).lower() == "true"
    if hide_io:
        os.environ.setdefault("LANGCHAIN_HIDE_INPUTS", "true")
        os.environ.setdefault("LANGCHAIN_HIDE_OUTPUTS", "true")

    endpoint = os.environ.get("LANGSMITH_ENDPOINT") or os.environ.get(
        "LANGCHAIN_ENDPOINT"
    )
    if endpoint:
        os.environ.setdefault("LANGSMITH_ENDPOINT", endpoint)
        os.environ.setdefault("LANGCHAIN_ENDPOINT", endpoint)

    logger.info(
        "LangSmith tracing enabled (project: %s, hide_io: %s)", project, hide_io
    )


def get_langsmith_base_url() -> str:
    """Return the configured LangSmith endpoint or the public default."""
    return (
        os.environ.get("LANGSMITH_ENDPOINT")
        or os.environ.get("LANGCHAIN_ENDPOINT")
        or "https://smith.langchain.com"
    )


def tag_trace_intent(intent: str) -> None:
    """Best-effort: tag the current LangSmith ROOT run with the classified
    intent so top-level traces are filterable by intent in the UI.

    The earlier RunTree-walk approach (``add_tags`` on the run reached by
    walking ``parent_run``) did NOT land: under ``astream_events`` the
    ``parent_run`` chain is often not populated, so the walk tagged the
    current node, not the trace root — and even then a local mutation never
    PATCHed the already-uploaded root run. Instead, identify the root by
    ``RunTree.trace_id`` (== the root run's id) and PATCH it directly via
    ``Client.update_run(run_id=trace_id, tags=[...])``.

    Only TAGS are patched (not ``extra``/metadata) so the root's tenant
    metadata (user_id/org_id/thread_id/job_id, set in the invoke config) is
    never clobbered. The root carries no tags by config, so replacing tags
    with ``[intent:<x>]`` is safe.

    The patch is dispatched fire-and-forget (``asyncio.to_thread``) so the
    HTTP call never adds latency to the hot-path node. No-op when intent is
    empty, the SDK is absent, or there is no active run context. Never raises.
    """
    if not intent:
        return
    try:
        from langsmith.run_helpers import get_current_run_tree

        rt = get_current_run_tree()
        if rt is None:
            return
        root_id = getattr(rt, "trace_id", None)
        if root_id is None:
            return

        tag = f"intent:{intent}"
        root_id_str = str(root_id)

        def _patch() -> None:
            try:
                _get_ls_client().update_run(run_id=root_id_str, tags=[tag])
            except Exception:
                logger.debug("tag_trace_intent patch failed", exc_info=True)

        # Fire-and-forget off the hot path. preprocessing_node is always inside
        # a running loop; fall back to inline if somehow not.
        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(asyncio.to_thread(_patch))
            _TAG_TASKS.add(task)
            task.add_done_callback(_TAG_TASKS.discard)
        except RuntimeError:
            _patch()
    except Exception:
        logger.debug("tag_trace_intent failed", exc_info=True)


# ---------------------------------------------------------------------------
# Prometheus metrics (using existing monitoring infrastructure)
# ---------------------------------------------------------------------------

try:
    from prometheus_client import REGISTRY, Counter, Histogram

    def _get_or_create_counter(name: str, doc: str, labels: list[str]) -> Counter:
        """Return an existing Counter (if already registered) or create one.

        Module re-imports during dev hot-reload would otherwise raise
        ``ValueError: Duplicated timeseries`` from the global registry and
        crash the process on restart.
        """
        existing = getattr(REGISTRY, "_names_to_collectors", {}).get(name)
        if existing is not None:
            return existing  # type: ignore[return-value]
        return Counter(name, doc, labels)

    def _get_or_create_histogram(
        name: str, doc: str, labels: list[str], buckets: list[float]
    ) -> Histogram:
        existing = getattr(REGISTRY, "_names_to_collectors", {}).get(name)
        if existing is not None:
            return existing  # type: ignore[return-value]
        return Histogram(name, doc, labels, buckets=buckets)

    AGENT_EXECUTION_DURATION = _get_or_create_histogram(
        "agent_execution_duration_seconds",
        "Duration of agent graph execution",
        ["intent", "status"],
        [0.5, 1, 2, 5, 10, 30, 60, 120],
    )

    AGENT_NODE_DURATION = _get_or_create_histogram(
        "agent_node_duration_seconds",
        "Duration of an individual agent node execution",
        ["node", "status"],
        [0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30],
    )

    AGENT_TOOL_CALLS = _get_or_create_counter(
        "agent_tool_calls_total",
        "Total number of tool calls made by the agent",
        ["tool_name", "status"],
    )

    AGENT_TOKEN_USAGE = _get_or_create_counter(
        "agent_token_usage_total",
        "Total token usage by the agent",
        ["model", "type"],
    )

    AGENT_ERRORS = _get_or_create_counter(
        "agent_error_total",
        "Total number of agent errors",
        # ``node`` records WHERE the error occurred; ``error_type`` records
        # WHAT class of failure it was (kept separate so dashboards don't
        # conflate location with cause).
        ["node", "error_type"],
    )

    # Distribution across classifier paths. Lets dashboards alert when LLM
    # path drops (e.g. Azure 404s) and keyword fallback share rises.
    AGENT_CLASSIFIER_SOURCE = _get_or_create_counter(
        "agent_classifier_source_total",
        "Intent classifier path (llm/keyword/shortcut/fallback) per intent",
        ["source", "intent"],
    )

    # Tool-level error counter with structured category from
    # error_recovery.classify_error (transient/permanent/auth/validation/
    # not_found/...). Lets us separate "search_arxiv timeout spike" from
    # "create_project auth failure" on the same dashboard.
    AGENT_TOOL_ERRORS = _get_or_create_counter(
        "agent_tool_errors_total",
        "Tool execution errors by tool + category",
        ["tool", "category"],
    )

    # Memory recall hit rate — emits 0 (miss) or 1 (hit, >=1 memory returned)
    # per recall call. Use rate() in Prometheus / Grafana to derive hit-rate %.
    AGENT_MEMORY_RECALL = _get_or_create_counter(
        "agent_memory_recall_total",
        "Memory recall outcomes per call",
        ["outcome"],  # "hit" | "miss"
    )

    # Background assistant-row persistence failures — Task 5 of
    # docs/plans/2026-05-13-agent-persist-perf.md. Bumped by the safe
    # wrapper around _persist_assistant_message when the deferred commit
    # raises. Lets dashboards alert when assistant rows are silently lost
    # off the request hot path.
    agent_assistant_persist_failures_total = _get_or_create_counter(
        "agent_assistant_persist_failures_total",
        "Number of background assistant-row persistence failures",
        [],
    )

    # User-turn persistence failures on the agent hot path (P2.6 / audit D3).
    # The user row is a single idempotent INSERT written BEFORE the LLM call;
    # historically its failure was swallowed (warn-and-continue), so the
    # LangGraph checkpoint could accumulate a turn the chat_messages store
    # never recorded — a permanent divergence the user can't see. Bumped by
    # _persist_user_message_guarded after a retry still fails, so the drop is
    # observable instead of silent.
    agent_dualstore_user_turn_persist_failures_total = _get_or_create_counter(
        "agent_dualstore_user_turn_persist_failures_total",
        "User-turn persistence failures after one retry on the agent hot path",
        [],
    )

    # Detected (not repaired) divergence between the LangGraph checkpoint's
    # HumanMessage count and the persisted chat_messages user-row count for a
    # thread (P2.6 / audit D3). Detection only; re-seed repair is a follow-up.
    agent_dualstore_divergence_detected_total = _get_or_create_counter(
        "agent_dualstore_divergence_detected_total",
        "Threads where checkpoint human-count and chat user-row count diverged",
        [],
    )

    # Quality histogram: max similarity score returned per recall call.
    # Trace evidence showed score=null for every recalled item — once the
    # store has a semantic index wired this histogram surfaces whether
    # recalls actually returned ranked, useful memories.
    AGENT_MEMORY_SCORE = _get_or_create_histogram(
        "agent_memory_relevance_score",
        "Max relevance score returned by memory recall",
        [],
        [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0],
    )

    # Degraded-answer signal: the agent hit the tool-loop ceiling and was
    # forced to synthesize from partial tool results. A rising rate means
    # MAX_TOOL_LOOPS is too low or a tool is looping — both hurt answer quality.
    AGENT_LOOP_EXHAUSTION = _get_or_create_counter(
        "agent_loop_exhaustion_total",
        "Turns that hit the tool-loop ceiling and were force-synthesized",
        ["intent", "subgraph"],
    )

    # Reflection gate outcome per turn (proceed vs revise). Rising "revise"
    # share means the agent's first answers are increasingly low-quality.
    AGENT_REFLECTION_DECISION = _get_or_create_counter(
        "agent_reflection_decision_total",
        "Reflection-node decision per turn",
        ["decision", "intent"],  # decision: proceed | revise
    )

    # Intent classifier confidence distribution per source. Low-confidence
    # spikes flag misrouting (wrong subgraph) before users complain.
    AGENT_INTENT_CONFIDENCE = _get_or_create_histogram(
        "agent_intent_confidence",
        "Intent classification confidence by classifier source",
        ["source"],
        [0.0, 0.25, 0.5, 0.7, 0.85, 0.95, 1.0],
    )

    _METRICS_AVAILABLE = True
except ImportError:
    _METRICS_AVAILABLE = False
    logger.debug("prometheus_client not available, metrics disabled")


# ---------------------------------------------------------------------------
# Tracing decorators
# ---------------------------------------------------------------------------


def track_node_execution(node_name: str):
    """Decorator to track node execution time and errors.

    Records both the success and the error paths into Prometheus so node
    latency dashboards have data even when no error is raised.
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            t0 = time.monotonic()
            try:
                result = await func(*args, **kwargs)
                duration = time.monotonic() - t0
                logger.debug("Node %s completed in %.2fs", node_name, duration)
                if _METRICS_AVAILABLE:
                    AGENT_NODE_DURATION.labels(
                        node=node_name, status="success"
                    ).observe(duration)
                return result
            except _CONTROL_FLOW_EXC:
                # HITL interrupt / parent-command bubble-up — control flow, not a
                # node failure. Record the latency under a benign status and
                # re-raise so the graph runner can pause/route; do NOT log ERROR
                # or increment AGENT_ERRORS.
                duration = time.monotonic() - t0
                if _METRICS_AVAILABLE:
                    AGENT_NODE_DURATION.labels(
                        node=node_name, status="interrupted"
                    ).observe(duration)
                raise
            except Exception as e:
                duration = time.monotonic() - t0
                # Keep the traceback for operators (exc_info) but keep the raw
                # exception string out of the indexed primary message — it can
                # carry the user query or DB fragments (PII leak into logs).
                logger.error(
                    "Node %s failed after %.2fs", node_name, duration, exc_info=True
                )
                if _METRICS_AVAILABLE:
                    AGENT_NODE_DURATION.labels(node=node_name, status="error").observe(
                        duration
                    )
                    AGENT_ERRORS.labels(
                        node=node_name, error_type=type(e).__name__
                    ).inc()
                raise

        return wrapper

    return decorator


def record_tool_call(tool_name: str, status: str):
    """Record a tool call metric."""
    if _METRICS_AVAILABLE:
        AGENT_TOOL_CALLS.labels(tool_name=tool_name, status=status).inc()


def record_execution_duration(intent: str, status: str, duration: float):
    """Record agent execution duration."""
    if _METRICS_AVAILABLE:
        AGENT_EXECUTION_DURATION.labels(intent=intent, status=status).observe(duration)


def record_node_duration(node: str, status: str, duration: float) -> None:
    """Record a sub-node / phase duration into the shared node histogram.

    Lets phases that don't go through ``track_node_execution`` (e.g. the
    subtasks ``preprocessing_node`` fans out via ``asyncio.gather``, which
    otherwise emit no traced run) surface on the same
    ``agent_node_duration_seconds`` dashboard.
    """
    if _METRICS_AVAILABLE:
        AGENT_NODE_DURATION.labels(node=node, status=status).observe(duration)


def record_token_usage(model: str, prompt_tokens: int, completion_tokens: int):
    """Record token usage metrics."""
    if _METRICS_AVAILABLE:
        AGENT_TOKEN_USAGE.labels(model=model, type="prompt").inc(prompt_tokens)
        AGENT_TOKEN_USAGE.labels(model=model, type="completion").inc(completion_tokens)


def record_loop_exhaustion(intent: str, subgraph: str = "main"):
    """Record a turn that hit the tool-loop ceiling and was force-synthesized."""
    if _METRICS_AVAILABLE:
        AGENT_LOOP_EXHAUSTION.labels(intent=intent, subgraph=subgraph).inc()


def record_reflection_decision(decision: str, intent: str = "unknown"):
    """Record a reflection-node decision (``proceed`` | ``revise``)."""
    if _METRICS_AVAILABLE:
        AGENT_REFLECTION_DECISION.labels(decision=decision, intent=intent).inc()


def record_intent_confidence(source: str, confidence: float):
    """Record the classifier confidence for a routed intent."""
    if _METRICS_AVAILABLE:
        try:
            AGENT_INTENT_CONFIDENCE.labels(source=source).observe(float(confidence))
        except (TypeError, ValueError):
            pass


def record_error(error_type: str, node: str = "unknown"):
    """Record an agent error.

    ``node`` records WHERE the error happened (which graph node) so
    dashboards can pivot by location independently of the error class
    captured in ``error_type``.
    """
    if _METRICS_AVAILABLE:
        AGENT_ERRORS.labels(node=node, error_type=error_type).inc()


def record_classifier_source(source: str, intent: str) -> None:
    """Record which classifier path produced the intent.

    Source values: llm, keyword, shortcut, fallback.
    """
    if _METRICS_AVAILABLE:
        AGENT_CLASSIFIER_SOURCE.labels(source=source, intent=intent).inc()


def record_tool_error(tool: str, category: str) -> None:
    """Record a tool failure with classified category."""
    if _METRICS_AVAILABLE:
        AGENT_TOOL_ERRORS.labels(tool=tool, category=category).inc()


def record_memory_recall(hit: bool, max_score: float | None = None) -> None:
    """Record memory recall outcome + optional max similarity score.

    ``hit`` increments the counter under outcome="hit" or "miss".
    ``max_score`` (when not None) feeds the relevance histogram so
    dashboards can distinguish "we returned 5 memories with score=0.1"
    from "we returned 5 strong matches".
    """
    if not _METRICS_AVAILABLE:
        return
    AGENT_MEMORY_RECALL.labels(outcome="hit" if hit else "miss").inc()
    if max_score is not None:
        AGENT_MEMORY_SCORE.observe(max_score)


# Backwards-compat alias — earlier code paths referenced the old name.
record_memory_retrieval = record_memory_recall


@asynccontextmanager
async def trace_agent_execution(intent: str = "general"):
    """Context manager to trace a full agent execution."""
    t0 = time.monotonic()
    status = "success"
    try:
        yield
    except Exception:
        status = "error"
        raise
    finally:
        duration = time.monotonic() - t0
        record_execution_duration(intent, status, duration)
        logger.info(
            "Agent execution complete",
            extra={
                "intent": intent,
                "status": status,
                "duration_seconds": round(duration, 2),
            },
        )
