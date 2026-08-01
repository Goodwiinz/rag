"""Shared doubles + frame helpers for the agent SSE stream tests.

Two classes of avoidable test debt live here so they can be fixed once:

1. **Request doubles that drift from the wire model.** Several stream tests
   hand-rolled a ``SimpleNamespace`` with just the four attributes they knew
   the generator touched. When ``perf(agent): add durable Luna fast path``
   (cfcc7f0) made the router read ``request_body.use_rag`` — a field the real
   ``AgentExecuteRequest`` has always carried with ``default=True`` — eleven
   tests died on ``AttributeError`` for a field production always supplies.
   ``make_stream_request`` builds the REAL pydantic model, so a double can
   never again be short an attribute the generator legitimately reads.

2. **Positional frame assertions.** ``events[0] is trace`` breaks the moment a
   new non-workflow frame is prepended (cfcc7f0 added a leading
   ``status``/``accepted`` progress frame). Assert relative order over
   ``workflow_frames`` instead of an index, and the next progress frame costs
   zero test edits.
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping, Optional, Sequence

from src.services.agent.schemas import (
    AgentExecuteRequest,
    AgentMessage,
    PageContextRequest,
)

__all__ = [
    "PROGRESS_EVENTS",
    "frames_of_type",
    "make_stream_request",
    "sse_data",
    "sse_event_name",
    "sse_seq",
    "workflow_frames",
]

# Frames that report on the run rather than carry it. They may be added,
# reordered, or dropped without changing what the client renders, so ordering
# assertions about the actual workflow must look past them.
PROGRESS_EVENTS = frozenset({"status", "heartbeat"})

_DEFAULT_MESSAGES: tuple[Mapping[str, Any], ...] = ({"role": "user", "content": "hi"},)


def make_stream_request(
    *,
    messages: Optional[Sequence[Mapping[str, Any]]] = None,
    page_context: Optional[Mapping[str, Any]] = None,
    **overrides: Any,
) -> AgentExecuteRequest:
    """Build a real ``AgentExecuteRequest`` for ``stream_event_generator``.

    Every field the caller does not override keeps the schema default, which
    is exactly what the router hands the generator in production.
    """
    return AgentExecuteRequest(
        messages=[
            AgentMessage(**dict(message))
            for message in (_DEFAULT_MESSAGES if messages is None else messages)
        ],
        page_context=PageContextRequest(
            **dict(page_context if page_context is not None else {"type": "general"})
        ),
        **overrides,
    )


def sse_event_name(frame: str) -> str:
    """Return the ``event:`` name of a single SSE frame ("" if malformed).

    Anchored to the event line rather than a substring search: streamed token
    text can contain the literal ``event: done``.
    """
    for line in frame.split("\n"):
        if line.startswith("event: "):
            return line.removeprefix("event: ")
    return ""


def sse_data(frame: str) -> Any:
    """Parse the ``data:`` payload of a single SSE frame."""
    for line in frame.split("\n"):
        if line.startswith("data: "):
            return json.loads(line.removeprefix("data: "))
    raise AssertionError(f"frame carries no data line: {frame!r}")


def sse_seq(frame: str) -> Optional[int]:
    """Return the resumable-stream cursor (``id:`` line), or None if absent.

    Only the pre-ownership ``status``/``accepted`` frame is legitimately
    id-less — it is emitted before the client-supplied thread id is trusted,
    so it never reaches the Redis buffer that backs ``GET /stream/resume``.
    """
    first, _, _ = frame.partition("\n")
    if not first.startswith("id: "):
        return None
    return int(first.removeprefix("id: "))


def frames_of_type(events: Iterable[str], event_type: str) -> list[str]:
    """All frames whose event line is ``event_type``."""
    return [frame for frame in events if sse_event_name(frame) == event_type]


def workflow_frames(events: Iterable[str]) -> list[str]:
    """Frames minus progress chatter — what the ordering contracts are about."""
    return [frame for frame in events if sse_event_name(frame) not in PROGRESS_EVENTS]
