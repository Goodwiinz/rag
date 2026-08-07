"""JSON-safe evidence serialization shared by Harbor eval tasks.

Consumed only by tasks added after 2026-08-07; the three original tasks are
digest-pinned and keep their inline copies. `json_safe` is the canonical
variant from `evals/agent-direct-project-action-v1/environment/run_agent.py`
plus the `datetime` branch from the stream-cancel task's `run_agent.py`.

The LangChain message branch is optional: this module stays importable (and
selftestable) in environments without `langchain_core` installed.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

try:  # pragma: no cover - depends on the runtime image
    from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
except ImportError:  # pragma: no cover - pure-python fallback
    AIMessage = BaseMessage = ToolMessage = None  # type: ignore[assignment]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def json_safe(value: Any) -> Any:
    """Convert LangChain/LangGraph values into bounded JSON-safe evidence."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        aware = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return aware.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if BaseMessage is not None and isinstance(value, BaseMessage):
        payload: dict[str, Any] = {
            "type": value.type,
            "id": getattr(value, "id", None),
            "content": json_safe(value.content),
        }
        if isinstance(value, AIMessage):
            payload["tool_calls"] = json_safe(value.tool_calls or [])
            payload["usage_metadata"] = json_safe(value.usage_metadata or {})
            payload["response_metadata"] = json_safe(value.response_metadata or {})
        if isinstance(value, ToolMessage):
            payload["tool_call_id"] = value.tool_call_id
            payload["status"] = getattr(value, "status", None)
        return payload
    if dataclasses.is_dataclass(value):
        return json_safe(dataclasses.asdict(value))
    if hasattr(value, "model_dump"):
        try:
            return json_safe(value.model_dump(mode="json"))
        except Exception:
            return json_safe(value.model_dump())
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if hasattr(value, "value"):
        try:
            return json_safe(value.value)
        except Exception:
            pass
    return str(value)
