"""Allow-listed, bounded identifiers attached to root agent traces."""

import os
from enum import Enum
from typing import Any

MAX_TRACE_METADATA_VALUE_CHARS = 128
TRACE_SOURCE_METADATA_KEY = "trace_source"

try:  # exported by langsmith >= 0.9; older versions accept the literal key
    from langsmith import LS_MESSAGE_VIEW_EXCLUDE  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - depends on installed langsmith version
    LS_MESSAGE_VIEW_EXCLUDE = "ls_message_view_exclude"


def internal_llm_config(config: Any = None) -> dict[str, Any]:
    """RunnableConfig hiding an internal LLM call from the LangSmith Messages view.

    Classification, planning, reflection, compaction, evidence summarization
    and other routing/bookkeeping LLM calls are not conversational turns; the
    ``ls_message_view_exclude`` metadata key keeps them out of the Messages
    view transcript while leaving them visible in the regular trace view.

    When ``config`` (an existing RunnableConfig) is given, its keys are
    preserved and only the metadata is extended, so callbacks and tracing
    context pass through unchanged.
    """
    merged: dict[str, Any] = dict(config) if isinstance(config, dict) else {}
    metadata = dict(merged.get("metadata") or {})
    metadata[LS_MESSAGE_VIEW_EXCLUDE] = True
    merged["metadata"] = metadata
    return merged


class TraceSource(str, Enum):
    """Bounded root source categories used to scope trace consumers."""

    GRAPH = "graph"
    NON_GRAPH = "non_graph"


def build_trace_metadata(
    *,
    trace_source: TraceSource,
    user_id: Any = None,
    org_id: Any = None,
    thread_id: Any = None,
    request_id: Any = None,
    agent_run_id: Any = None,
    user_message_id: Any = None,
    client_message_id: Any = None,
) -> dict[str, str]:
    """Build correlation-only metadata inherited by an agent's child runs.

    The explicit signature is part of the safety boundary: callers cannot add
    prompts, tool results, or arbitrary request fields without changing this
    contract. Empty values are omitted and every emitted value is bounded.
    """
    git_sha = (os.getenv("GIT_SHA") or "").strip()
    app_version = (os.getenv("APP_VERSION") or "").strip()
    image_tag = (os.getenv("IMAGE_TAG") or "").strip()
    values = {
        TRACE_SOURCE_METADATA_KEY: trace_source.value,
        "user_id": user_id,
        "org_id": org_id,
        "thread_id": thread_id,
        "request_id": request_id,
        "agent_run_id": agent_run_id,
        "user_message_id": user_message_id,
        "client_message_id": client_message_id,
        "deployment_sha": git_sha or app_version,
        "image_tag": image_tag,
    }
    metadata: dict[str, str] = {}
    for key, value in values.items():
        if value is None:
            continue
        bounded = str(value).strip()[:MAX_TRACE_METADATA_VALUE_CHARS]
        if bounded:
            metadata[key] = bounded
    return metadata


__all__ = [
    "LS_MESSAGE_VIEW_EXCLUDE",
    "internal_llm_config",
    "MAX_TRACE_METADATA_VALUE_CHARS",
    "TRACE_SOURCE_METADATA_KEY",
    "TraceSource",
    "build_trace_metadata",
]
