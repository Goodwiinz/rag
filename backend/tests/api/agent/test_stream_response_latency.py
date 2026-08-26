"""The SSE 'done' event must follow the assistant-row commit.

Task 5 of ``docs/plans/2026-05-13-agent-persist-perf.md``.

Direct-invokes ``stream_event_generator`` with a fake final answer and a
stubbed ``_persist_assistant_message_safe`` that sleeps 300 ms. ``done`` is a
durability claim, so the row must exist before that terminal frame is yielded.
Token streaming has already completed at this point; only the acknowledgement
waits for the commit.
"""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

pytestmark = pytest.mark.integration


class _FakeGraph:
    """Graph stub that produces no events and a non-interrupt snapshot."""

    def __init__(self):
        self._snapshot = SimpleNamespace(values={"messages": []}, tasks=())

    async def astream_events(self, *_args, **_kwargs):
        if False:  # pragma: no cover  (make this an async generator)
            yield {}
        return

    async def aget_state(self, _config):
        return SimpleNamespace(
            values={
                "messages": [SimpleNamespace(type="ai", content="answer")],
                "tool_executions": [],
            },
            tasks=(),
        )


class _MockBackgroundTasks:
    """Captures accidental attempts to defer terminal persistence."""

    def __init__(self):
        self.scheduled: list[tuple] = []

    def add_task(self, func, *args, **kwargs):
        self.scheduled.append((func, args, kwargs))


async def test_done_event_waits_on_commit(
    db_session, thread_factory, user_factory, _engine
):
    """The SSE ``done`` event must not precede the slow persist."""
    user = await user_factory()
    thread = await thread_factory(user=user)

    slowdown = 0.3  # 300 ms
    real_persist_called = asyncio.Event()

    async def slow_persist(*_args, **_kwargs):
        await asyncio.sleep(slowdown)
        real_persist_called.set()
        return "assistant-row-1"

    from src.api.agent.execute import AgentExecuteRequest, AgentMessage

    body = AgentExecuteRequest(
        messages=[AgentMessage(role="user", content="ping", client_message_id=uuid4())],
        thread_id=str(thread.id),
    )

    fastapi_request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))

    TestSessionLocal = async_sessionmaker(_engine, expire_on_commit=False)

    bg = _MockBackgroundTasks()

    from src.api.agent import streaming as streaming_mod
    from src.services.agent import agent_execution_service as jobs_mod

    with (
        patch.object(streaming_mod, "AsyncSessionLocal", TestSessionLocal),
        patch.object(jobs_mod, "AsyncSessionLocal", TestSessionLocal),
        patch.object(jobs_mod, "_persist_assistant_message_safe", slow_persist),
        patch(
            "src.services.agent.observability.configure_langsmith",
            new=lambda: None,
        ),
        patch(
            "src.services.agent.checkpointer.get_checkpointer",
            new=AsyncMock(return_value=object()),
        ),
        patch(
            "src.services.agent.memory.get_memory_store",
            new=AsyncMock(return_value=object()),
        ),
        patch(
            "src.services.agent.graph.compile_agent_graph",
            new=lambda **_kwargs: _FakeGraph(),
        ),
    ):
        t0 = time.perf_counter()
        done_seen_at: float | None = None
        async for event in streaming_mod.stream_event_generator(
            body, fastapi_request, user, background_tasks=bg
        ):
            if "event: done" in event:
                done_seen_at = time.perf_counter() - t0
                break

        assert done_seen_at is not None, "stream never emitted a 'done' event"
        assert real_persist_called.is_set(), "done preceded assistant persistence"
        assert done_seen_at >= slowdown, (
            f"done emitted before the {slowdown:.3f}s persist completed: "
            f"{done_seen_at:.3f}s"
        )
        assert bg.scheduled == []
