"""ASGI response cancellation must durably stop an accepted agent run."""

from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest
from starlette.responses import StreamingResponse
from starlette.types import Message, Scope

from src.models.user import User
from src.services.agent.agent_submission_service import AcceptedSubmission
from src.services.agent.runtime_snapshot import empty_runtime_snapshot
from src.shared.enums import JobStatus
from tests.utils.agent_stream import make_stream_request


class _BlockingGraph:
    def __init__(self) -> None:
        self.aclosed = False
        self._sent = False
        self._never = asyncio.Event()

    def astream_events(self, *_args: Any, **_kwargs: Any) -> _BlockingGraph:
        return self

    def __aiter__(self) -> _BlockingGraph:
        return self

    async def __anext__(self) -> dict[str, Any]:
        if not self._sent:
            self._sent = True
            return {
                "event": "on_chat_model_stream",
                "name": "llm_node",
                "metadata": {"langgraph_node": "llm_node"},
                "data": {"chunk": SimpleNamespace(content="partial")},
            }
        await self._never.wait()
        raise StopAsyncIteration

    async def aclose(self) -> None:
        self.aclosed = True

    async def aget_state(self, _config: Any) -> Any:
        return SimpleNamespace(values={"messages": []}, tasks=())


@pytest.mark.parametrize("buffer_available", [False, True])
@pytest.mark.asyncio
async def test_streaming_response_abort_finalizes_cancelled_without_completion(
    buffer_available: bool,
) -> None:
    from src.api.agent import streaming as streaming_mod

    user_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    org_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    thread_id = uuid.UUID("33333333-3333-3333-3333-333333333333")
    client_message_id = uuid.UUID("44444444-4444-4444-4444-444444444444")
    request_id = "response-cancel-request"
    current_user = cast(User, SimpleNamespace(id=user_id, organization_id=org_id))
    thread = SimpleNamespace(id=thread_id)
    body = make_stream_request(
        messages=[
            {
                "role": "user",
                "content": "generate a long synthetic answer",
                "client_message_id": str(client_message_id),
            }
        ],
        thread_id=str(thread_id),
    )
    request = SimpleNamespace(
        state=SimpleNamespace(request_id=request_id),
        is_disconnected=AsyncMock(return_value=False),
    )
    acceptance = AcceptedSubmission(
        run_id="55555555-5555-5555-5555-555555555555",
        thread_id=str(thread_id),
        user_message_id="66666666-6666-6666-6666-666666666666",
        outbox_id="outbox-1",
        idempotency_key="idem-1",
    )
    graph = _BlockingGraph()
    db = SimpleNamespace(close=AsyncMock())
    persist = AsyncMock(return_value="partial-message")
    finalize = AsyncMock(return_value=None)
    finish_stream = AsyncMock(return_value=None)
    appended = AsyncMock(return_value=None)

    if buffer_available:
        start_stream = AsyncMock(return_value="stream-buffer-1")
    else:
        start_stream = AsyncMock(side_effect=RuntimeError("redis unavailable"))

    with (
        patch.object(streaming_mod, "AsyncSessionLocal", return_value=db),
        patch.object(
            streaming_mod,
            "_resolve_thread",
            new=AsyncMock(return_value=(thread, "conversation-1")),
        ),
        patch.object(
            streaming_mod,
            "accept_submission",
            new=AsyncMock(return_value=acceptance),
        ),
        patch.object(
            streaming_mod,
            "mark_submission_dispatched",
            new=AsyncMock(return_value=None),
        ),
        patch.object(
            streaming_mod,
            "_resolve_and_bind_project",
            new=AsyncMock(return_value=None),
        ),
        patch.object(
            streaming_mod,
            "_clear_stale_pending_confirmation",
            new=AsyncMock(return_value=None),
        ),
        patch.object(streaming_mod, "_finalize_run", new=finalize),
        patch.object(
            streaming_mod._jobs_mod,
            "_persist_assistant_message_safe",
            new=persist,
        ),
        patch.object(streaming_mod._stream_buffer, "start_stream", new=start_stream),
        patch.object(streaming_mod._stream_buffer, "append", new=appended),
        patch.object(streaming_mod._stream_buffer, "finish_stream", new=finish_stream),
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
        patch("src.services.agent.graph.compile_agent_graph", return_value=graph),
        patch(
            "src.services.agent.fast_path.classify_fast_path_turn",
            return_value=SimpleNamespace(eligible=False),
        ),
        patch(
            "src.services.agent.runtime_snapshot.create_runtime_snapshot",
            new=AsyncMock(return_value=empty_runtime_snapshot()),
        ),
    ):
        response = StreamingResponse(
            streaming_mod.stream_event_generator(body, request, current_user),
            media_type="text/event-stream",
        )
        disconnect = asyncio.Event()
        sent: list[Message] = []
        received_request = False

        async def receive() -> Message:
            nonlocal received_request
            if not received_request:
                received_request = True
                return {"type": "http.request", "body": b"", "more_body": False}
            await disconnect.wait()
            return {"type": "http.disconnect"}

        async def send(message: Message) -> None:
            sent.append(message)
            if message.get("type") == "http.response.body" and b"event: token" in (
                message.get("body") or b""
            ):
                disconnect.set()

        scope = cast(
            Scope,
            {
                "type": "http",
                "asgi": {"version": "3.0", "spec_version": "2.3"},
                "http_version": "1.1",
                "method": "POST",
                "scheme": "http",
                "path": "/api/agent/stream",
                "raw_path": b"/api/agent/stream",
                "query_string": b"",
                "headers": [],
                "client": ("127.0.0.1", 1),
                "server": ("testserver", 80),
            },
        )
        await asyncio.wait_for(response(scope, receive, send), timeout=2)

    assert graph.aclosed is True
    persist.assert_awaited_once()
    persist_call = persist.await_args
    assert persist_call is not None
    assert persist_call.kwargs["content"] == "partial"
    assert persist_call.kwargs["stopped"] is True
    finalize.assert_awaited_once()
    finalize_call = finalize.await_args
    assert finalize_call is not None
    assert finalize_call.kwargs["status"] is JobStatus.CANCELLED
    assert finalize_call.kwargs["payload"] == {
        "reason": "client_disconnected",
        "request_id": request_id,
        # The cancellation path persists the stopped partial inline and links
        # the cancelled run to it (persist returns ``partial-message`` above).
        "assistant_message_id": "partial-message",
    }
    bodies = b"".join(
        message.get("body", b"")
        for message in sent
        if message.get("type") == "http.response.body"
    )
    assert b"event: done" not in bodies
    if buffer_available:
        appended.assert_awaited()
        finish_stream.assert_awaited_once_with(str(thread_id), "stream-buffer-1")
    else:
        finish_stream.assert_not_awaited()
    db.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_repeated_cancellation_waits_for_graph_cleanup() -> None:
    from src.api.agent import streaming as streaming_mod

    user_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    org_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    thread_id = uuid.UUID("33333333-3333-3333-3333-333333333333")
    current_user = cast(User, SimpleNamespace(id=user_id, organization_id=org_id))
    thread = SimpleNamespace(id=thread_id)
    body = make_stream_request(
        messages=[
            {
                "role": "user",
                "content": "generate a long synthetic answer",
                "client_message_id": "44444444-4444-4444-4444-444444444444",
            }
        ],
        thread_id=str(thread_id),
    )
    request = SimpleNamespace(
        state=SimpleNamespace(request_id="repeated-cancel-request"),
        is_disconnected=AsyncMock(return_value=False),
    )
    acceptance = AcceptedSubmission(
        run_id="55555555-5555-5555-5555-555555555555",
        thread_id=str(thread_id),
        user_message_id="66666666-6666-6666-6666-666666666666",
        outbox_id="outbox-1",
        idempotency_key="idem-1",
    )
    graph = _BlockingGraph()
    db = SimpleNamespace(close=AsyncMock())
    persist = AsyncMock(return_value="partial-message")
    finish_stream = AsyncMock(return_value=None)
    token_yielded = asyncio.Event()
    cleanup_started = asyncio.Event()
    allow_cleanup = asyncio.Event()
    finalize_calls: list[dict[str, Any]] = []

    async def blocking_finalize(*_args: Any, **kwargs: Any) -> None:
        cleanup_started.set()
        await allow_cleanup.wait()
        finalize_calls.append(kwargs)

    with (
        patch.object(streaming_mod, "AsyncSessionLocal", return_value=db),
        patch.object(
            streaming_mod,
            "_resolve_thread",
            new=AsyncMock(return_value=(thread, "conversation-1")),
        ),
        patch.object(
            streaming_mod,
            "accept_submission",
            new=AsyncMock(return_value=acceptance),
        ),
        patch.object(
            streaming_mod,
            "mark_submission_dispatched",
            new=AsyncMock(return_value=None),
        ),
        patch.object(
            streaming_mod,
            "_resolve_and_bind_project",
            new=AsyncMock(return_value=None),
        ),
        patch.object(
            streaming_mod,
            "_clear_stale_pending_confirmation",
            new=AsyncMock(return_value=None),
        ),
        patch.object(streaming_mod, "_finalize_run", new=blocking_finalize),
        patch.object(
            streaming_mod._jobs_mod,
            "_persist_assistant_message_safe",
            new=persist,
        ),
        patch.object(
            streaming_mod._stream_buffer,
            "start_stream",
            new=AsyncMock(return_value="stream-buffer-1"),
        ),
        patch.object(
            streaming_mod._stream_buffer, "append", new=AsyncMock(return_value=None)
        ),
        patch.object(streaming_mod._stream_buffer, "finish_stream", new=finish_stream),
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
        patch("src.services.agent.graph.compile_agent_graph", return_value=graph),
        patch(
            "src.services.agent.fast_path.classify_fast_path_turn",
            return_value=SimpleNamespace(eligible=False),
        ),
        patch(
            "src.services.agent.runtime_snapshot.create_runtime_snapshot",
            new=AsyncMock(return_value=empty_runtime_snapshot()),
        ),
    ):

        async def consume_response() -> None:
            async for _event in streaming_mod.stream_event_generator(
                body, request, current_user
            ):
                if "event: token" in _event:
                    token_yielded.set()

        response_task = asyncio.create_task(consume_response())
        await asyncio.wait_for(token_yielded.wait(), timeout=1)
        response_task.cancel("original-cancel")
        await asyncio.wait_for(cleanup_started.wait(), timeout=1)
        finished_during_cleanup = []
        for repeat in range(1, 4):
            response_task.cancel(f"repeat-{repeat}")
            await asyncio.sleep(0)
            finished_during_cleanup.append(response_task.done())
        allow_cleanup.set()
        with pytest.raises(asyncio.CancelledError) as cancelled:
            await response_task

    assert finished_during_cleanup == [False, False, False]
    assert cancelled.value.args == ("original-cancel",)
    assert graph.aclosed is True
    persist.assert_awaited_once()
    assert persist.await_args.kwargs["stopped"] is True
    finish_stream.assert_awaited_once_with(str(thread_id), "stream-buffer-1")
    assert len(finalize_calls) == 1
    assert finalize_calls[0]["status"] is JobStatus.CANCELLED
    db.close.assert_awaited_once()
