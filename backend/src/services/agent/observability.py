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
    """Configure LangSmith tracing if API key is available.

    Set LANGCHAIN_TRACING_V2=true and LANGCHAIN_API_KEY for automatic tracing.
    """
    api_key = os.environ.get("LANGCHAIN_API_KEY", "")
    if api_key:
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
        os.environ.setdefault("LANGCHAIN_PROJECT", "rag-agent")
        logger.info("LangSmith tracing enabled (project: rag-agent)")
    else:
        logger.debug("LangSmith tracing disabled (no LANGCHAIN_API_KEY)")


def get_langsmith_base_url() -> str:
    """Return the configured LangSmith endpoint or the public default."""
    return (
        os.environ.get("LANGCHAIN_ENDPOINT")
        or os.environ.get("LANGSMITH_ENDPOINT")
        or "https://smith.langchain.com"
    )


# ---------------------------------------------------------------------------
# Prometheus metrics (using existing monitoring infrastructure)
# ---------------------------------------------------------------------------

try:
    from prometheus_client import Counter, Histogram

    AGENT_EXECUTION_DURATION = Histogram(
        "agent_execution_duration_seconds",
        "Duration of agent graph execution",
        ["intent", "status"],
        buckets=[0.5, 1, 2, 5, 10, 30, 60, 120],
    )

    AGENT_TOOL_CALLS = Counter(
        "agent_tool_calls_total",
        "Total number of tool calls made by the agent",
        ["tool_name", "status"],
    )

    AGENT_TOKEN_USAGE = Counter(
        "agent_token_usage_total",
        "Total token usage by the agent",
        ["model", "type"],
    )

    AGENT_ERRORS = Counter(
        "agent_error_total",
        "Total number of agent errors",
        ["error_type"],
    )

    _METRICS_AVAILABLE = True
except ImportError:
    _METRICS_AVAILABLE = False
    logger.debug("prometheus_client not available, metrics disabled")


# ---------------------------------------------------------------------------
# Tracing decorators
# ---------------------------------------------------------------------------


def track_node_execution(node_name: str):
    """Decorator to track node execution time and errors."""
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
                    AGENT_ERRORS.labels(error_type=node_name).inc()
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


def record_error(error_type: str):
    """Record an agent error."""
    if _METRICS_AVAILABLE:
        AGENT_ERRORS.labels(error_type=error_type).inc()


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
