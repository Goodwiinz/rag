"""Agent observability and tracing helpers.

Provides custom metrics and tracing for agent execution monitoring.
Dual approach: LangSmith for LangGraph tracing + OpenTelemetry/Prometheus for custom metrics.
"""

import logging
import os
import time
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LangSmith configuration
# ---------------------------------------------------------------------------


def configure_langsmith():
    """Configure LangSmith tracing if an API key is available.

    Accepts either the modern ``LANGSMITH_*`` names (preferred by the current
    ``langsmith`` SDK) or the legacy ``LANGCHAIN_*`` names. Whichever is
    provided, this propagates to both so libraries on either convention pick
    it up.
    """
    api_key = os.environ.get("LANGSMITH_API_KEY") or os.environ.get(
        "LANGCHAIN_API_KEY"
    )
    if not api_key:
        logger.debug(
            "LangSmith tracing disabled "
            "(no LANGSMITH_API_KEY / LANGCHAIN_API_KEY)"
        )
        return

    os.environ.setdefault("LANGSMITH_API_KEY", api_key)
    os.environ.setdefault("LANGCHAIN_API_KEY", api_key)

    project = (
        os.environ.get("LANGSMITH_PROJECT")
        or os.environ.get("LANGCHAIN_PROJECT")
        or "rag-agent"
    )
    os.environ.setdefault("LANGSMITH_PROJECT", project)
    os.environ.setdefault("LANGCHAIN_PROJECT", project)

    # Both SDK generations read their own flag; set both to "true" by default.
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGSMITH_TRACING", "true")

    endpoint = os.environ.get("LANGSMITH_ENDPOINT") or os.environ.get(
        "LANGCHAIN_ENDPOINT"
    )
    if endpoint:
        os.environ.setdefault("LANGSMITH_ENDPOINT", endpoint)
        os.environ.setdefault("LANGCHAIN_ENDPOINT", endpoint)

    logger.info("LangSmith tracing enabled (project: %s)", project)


def get_langsmith_base_url() -> str:
    """Return the configured LangSmith endpoint or the public default."""
    return (
        os.environ.get("LANGSMITH_ENDPOINT")
        or os.environ.get("LANGCHAIN_ENDPOINT")
        or "https://smith.langchain.com"
    )


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

    # Memory recall hit rate — emits 0 (miss) or 1 (hit, ≥1 memory returned)
    # per memory_retrieval_node call. Use rate() in Prometheus / Grafana
    # to derive hit-rate %.
    AGENT_MEMORY_RETRIEVAL = _get_or_create_counter(
        "agent_memory_retrieval_total",
        "Memory retrieval outcomes per call",
        ["outcome"],  # "hit" | "miss"
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
                logger.debug(
                    "Node %s completed in %.2fs", node_name, duration
                )
                if _METRICS_AVAILABLE:
                    AGENT_NODE_DURATION.labels(
                        node=node_name, status="success"
                    ).observe(duration)
                return result
            except Exception as e:
                duration = time.monotonic() - t0
                logger.error(
                    "Node %s failed after %.2fs: %s",
                    node_name,
                    duration,
                    e,
                )
                if _METRICS_AVAILABLE:
                    AGENT_NODE_DURATION.labels(
                        node=node_name, status="error"
                    ).observe(duration)
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
        AGENT_EXECUTION_DURATION.labels(intent=intent, status=status).observe(
            duration
        )


def record_token_usage(model: str, prompt_tokens: int, completion_tokens: int):
    """Record token usage metrics."""
    if _METRICS_AVAILABLE:
        AGENT_TOKEN_USAGE.labels(model=model, type="prompt").inc(prompt_tokens)
        AGENT_TOKEN_USAGE.labels(model=model, type="completion").inc(
            completion_tokens
        )


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


def record_memory_retrieval(hit: bool) -> None:
    """Record memory recall outcome — hit (>=1 memory) or miss."""
    if _METRICS_AVAILABLE:
        AGENT_MEMORY_RETRIEVAL.labels(outcome="hit" if hit else "miss").inc()


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
