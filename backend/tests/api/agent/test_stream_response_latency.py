"""The SSE 'done' event must not be blocked by the assistant-row commit.

Task 5 of ``docs/plans/2026-05-13-agent-persist-perf.md``.

Direct-invokes ``stream_event_generator`` with a fake graph that yields
nothing (so the stream proceeds straight to the post-stream finalize),
a stubbed ``_persist_assistant_message_safe`` that sleeps 300 ms, and a
``MockBackgroundTasks`` that captures ``add_task`` calls. The behavior
under test: scheduling the assistant write through ``BackgroundTasks``
means the stream's ``done`` event is yielded immediately, without
waiting for the slow persist. Under the old behaviour (inline ``await``
of the persist helper) the stream blocks for ~300 ms before ``done``.
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
        return self._snapshot


class _MockBackgroundTasks:
    """Captures ``add_task`` calls so the test can run the deferred work
    out-of-band after measuring the stream's ``done`` latency.
    """

    def __init__(self):
        self.scheduled: list[tuple] = []

    def add_task(self, func, *args, **kwargs):
        self.scheduled.append((func, args, kwargs))


async def test_done_event_does_not_wait_on_commit(
    db_session, thread_factory, user_factory, _engine
):
    """The SSE ``done`` event must release before the slow persist runs."""
    user = await user_factory()
    thread = await thread_factory(user=user)

    slowdown = 0.3  # 300 ms
    real_persist_called = asyncio.Event()

    async def slow_persist(*_args, **_kwargs):
        await asyncio.sleep(slowdown)
        real_persist_called.set()

    from src.api.agent.execute import AgentExecuteRequest, AgentMessage

    body = AgentExecuteRequest(
        messages=[
            AgentMessage(
                role="user", content="ping", client_message_id=uuid4()
            )
        ],
        thread_id=str(thread.id),
    )

    fastapi_request = SimpleNamespace(
        is_disconnected=AsyncMock(return_value=False)
    )

    TestSessionLocal = async_sessionmaker(_engine, expire_on_commit=False)

    bg = _MockBackgroundTasks()

    from src.api.agent import jobs as jobs_mod
    from src.api.agent import streaming as streaming_mod

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
            if event.startswith("event: done"):
                done_seen_at = time.perf_counter() - t0
                break

        assert done_seen_at is not None, "stream never emitted a 'done' event"
        assert done_seen_at < slowdown / 2, (
            f"stream blocked on assistant commit: done emitted at "
            f"{done_seen_at:.3f}s (slowdown was {slowdown:.3f}s)"
        )

        # Exactly one persist task should have been scheduled.
        assert len(bg.scheduled) == 1, (
            f"expected one background task, got {len(bg.scheduled)}: "
            f"{bg.scheduled!r}"
        )
        scheduled_fn, scheduled_args, scheduled_kwargs = bg.scheduled[0]

        # Run the deferred task and confirm the original (slow) callable
        # was invoked. We compare to ``slow_persist`` to verify the safe
        # wrapper was passed through unchanged.
        assert scheduled_fn is slow_persist
        await scheduled_fn(*scheduled_args, **scheduled_kwargs)
        try:
            await asyncio.wait_for(real_persist_called.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            pytest.fail("background persist never ran")
