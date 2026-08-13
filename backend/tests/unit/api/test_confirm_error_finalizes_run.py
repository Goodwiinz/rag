"""Regression (R2-H1): stream/confirm finalizes the durable run as FAILED
when the resumed graph errors.

stream_confirm_event_generator's ``except Exception`` handler previously
emitted an ERROR frame and finished the emitter but never finalized the
durable run — the job stayed ``awaiting_confirmation`` forever and the
thread read as blocked. It must finalize the run as FAILED (mirroring the
cancellation path's finalize-as-CANCELLED behavior) before returning.
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest


class _ErroringGraph:
    """astream_events raises before yielding any event, modelling a resume
    failure (e.g. the graph invocation itself blows up)."""

    def __init__(self) -> None:
        pass

    def astream_events(self, *args: object, **kwargs: object) -> "Any":
        return self

    def __aiter__(self) -> "Any":
        return self

    async def __anext__(self) -> None:
        raise RuntimeError("resume boom")

    async def aclose(self) -> None:
        pass

    async def aget_state(self, config: object) -> "Any":
        return SimpleNamespace(
            values={
                "user_id": "user-1",
                "page_context": {},
                "messages": [],
                "tool_executions": [],
            },
            tasks=(),
        )


@pytest.mark.asyncio
async def test_confirm_stream_finalizes_run_as_failed_on_error() -> None:
    import src.api.agent.streaming as streaming_mod
    from src.shared.enums import JobStatus

    graph = _ErroringGraph()
    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
    body = SimpleNamespace(thread_id="thread-789", confirmed=True, model="")
    current_user = Mock(id="user-1", organization_id="org-1")
    active_run = SimpleNamespace(
        job_id="run-abc-123", user_message_id=None, client_message_id=None
    )

    finalize_mock = AsyncMock()

    with (
        patch(
            "src.api.agent.streaming._stream_buffer.start_stream",
            new=AsyncMock(side_effect=RuntimeError("redis down")),
        ),
        patch(
            "src.services.agent.observability.configure_langsmith", return_value=None
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
            return_value=graph,
        ),
        patch(
            "src.api.agent.streaming.get_active_run_for_thread",
            new=AsyncMock(return_value=active_run),
        ),
        patch.object(streaming_mod, "_finalize_run_id", new=finalize_mock),
        patch(
            "src.api.agent.streaming.AsyncSessionLocal",
            return_value=AsyncMock(),
        ),
    ):
        events = []
        async for event in streaming_mod.stream_confirm_event_generator(
            body, request, current_user
        ):
            events.append(event)

    assert any("event: error" in e for e in events)
    finalize_mock.assert_awaited_once()
    assert finalize_mock.await_args is not None
    args, kwargs = finalize_mock.await_args
    assert args[1] == "run-abc-123"
    assert kwargs["status"] == JobStatus.FAILED
    assert kwargs["payload"]["reason"] == "confirm_error"
