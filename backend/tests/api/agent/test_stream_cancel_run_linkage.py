"""A cancelled run must name the stopped partial row that holds its output.

``run.completed`` has always carried ``assistant_message_id``, so a normal turn
leaves ``AgentRun.assistant_message_id`` populated. The cancellation path did
not: ``persist_partial_stop()`` discarded the id returned by
``_persist_assistant_message_safe()``, and ``RunCancelledPayload`` had no field
to carry one anyway (payloads are ``extra="forbid"``). Every cancelled run
therefore ended with a stopped partial row that nothing pointed at — 3/3 trials
in the cancellation benchmark (evals/AGENT_FLOW_BASELINE.md, P1).

This drives the real generator to a cancel and asserts on the payload handed to
``_finalize_run``, which is what projects onto the durable run row.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.chat_message import ChatMessage, MessageRole
from src.services.agent.run_event_types import RunEventType, validate_payload

pytestmark = pytest.mark.integration


class _FakeGraphTokenThenHang:
    """Streams one user-facing token, then a second that triggers the cancel."""

    def __init__(self) -> None:
        self._snapshot = SimpleNamespace(values={"messages": []}, tasks=())

    async def astream_events(
        self, *_args: object, **_kwargs: object
    ) -> AsyncIterator[dict[str, object]]:
        for chunk in ("partial answer", "STOP"):
            yield {
                "event": "on_chat_model_stream",
                "name": "llm",
                "metadata": {"langgraph_node": "llm_node"},
                "data": {"chunk": SimpleNamespace(content=chunk)},
            }

    async def aget_state(self, _config: object) -> SimpleNamespace:
        return self._snapshot


async def test_cancelled_run_payload_links_the_stopped_partial(
    db_session: Any,
    thread_factory: Any,
    user_factory: Any,
    _engine: Any,
) -> None:
    user = await user_factory()
    thread = await thread_factory(user=user)

    from src.api.agent import streaming as streaming_mod
    from src.api.agent.execute import AgentExecuteRequest, AgentMessage
    from src.services.agent import agent_execution_service as jobs_mod

    body = AgentExecuteRequest(
        messages=[AgentMessage(role="user", content="ping", client_message_id=uuid4())],
        thread_id=str(thread.id),
    )
    fastapi_request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))

    TestSessionLocal = async_sessionmaker(_engine, expire_on_commit=False)

    finalize_calls: list[dict] = []

    async def spy_finalize_run(*_args: object, **kwargs: object) -> None:
        finalize_calls.append(kwargs)

    real_emit: Any = streaming_mod._SeqEmitter.emit

    async def emit_then_cancel(
        self: Any,
        event_type: str,
        data: dict[str, Any],
        *args: object,
        **kwargs: object,
    ) -> Any:
        if (
            event_type == streaming_mod.AgentStreamEvent.TOKEN
            and (data or {}).get("content") == "STOP"
        ):
            raise asyncio.CancelledError()
        return await real_emit(self, event_type, data, *args, **kwargs)

    with (
        patch.object(streaming_mod, "AsyncSessionLocal", TestSessionLocal),
        patch.object(jobs_mod, "AsyncSessionLocal", TestSessionLocal),
        patch.object(streaming_mod._SeqEmitter, "emit", emit_then_cancel),
        patch.object(streaming_mod, "_finalize_run", spy_finalize_run),
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
            new=lambda **_kwargs: _FakeGraphTokenThenHang(),
        ),
    ):
        with pytest.raises(asyncio.CancelledError):
            async for _event in streaming_mod.stream_event_generator(
                body, fastapi_request, user
            ):
                pass

    await db_session.commit()
    row = (
        await db_session.execute(
            select(ChatMessage)
            .where(ChatMessage.thread_id == thread.id)
            .where(ChatMessage.role == MessageRole.ASSISTANT)
        )
    ).scalar_one_or_none()
    assert row is not None, "the cancelled turn must persist its stopped partial"
    db_session.info["_created"]["chat_messages"].append(row.id)

    cancelled = [
        call
        for call in finalize_calls
        if call.get("event_type") is RunEventType.RUN_CANCELLED
    ]
    assert cancelled, f"expected a run.cancelled finalize, got {finalize_calls!r}"

    payload = cancelled[-1]["payload"]
    assert payload.get("assistant_message_id") == str(row.id), (
        "the cancelled run must point at the stopped partial row it persisted; "
        f"payload={payload!r} row={row.id!r}"
    )
    # The payload must also survive the wire contract it will be stored under.
    validate_payload(RunEventType.RUN_CANCELLED.value, payload)


async def test_cancel_before_any_token_omits_the_link(
    db_session: Any,
    thread_factory: Any,
    user_factory: Any,
    _engine: Any,
) -> None:
    """Nothing streamed means no partial row, so no id to link — and no null key."""
    user = await user_factory()
    thread = await thread_factory(user=user)

    from src.api.agent import streaming as streaming_mod
    from src.api.agent.execute import AgentExecuteRequest, AgentMessage
    from src.services.agent import agent_execution_service as jobs_mod

    class _FakeGraphCancelsImmediately:
        def __init__(self) -> None:
            self._snapshot = SimpleNamespace(values={"messages": []}, tasks=())

        async def astream_events(
            self, *_args: object, **_kwargs: object
        ) -> AsyncIterator[dict[str, object]]:
            raise asyncio.CancelledError()
            yield {}  # pragma: no cover  (make this an async generator)

        async def aget_state(self, _config: object) -> SimpleNamespace:
            return self._snapshot

    body = AgentExecuteRequest(
        messages=[AgentMessage(role="user", content="ping", client_message_id=uuid4())],
        thread_id=str(thread.id),
    )
    fastapi_request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
    TestSessionLocal = async_sessionmaker(_engine, expire_on_commit=False)

    finalize_calls: list[dict] = []

    async def spy_finalize_run(*_args: object, **kwargs: object) -> None:
        finalize_calls.append(kwargs)

    with (
        patch.object(streaming_mod, "AsyncSessionLocal", TestSessionLocal),
        patch.object(jobs_mod, "AsyncSessionLocal", TestSessionLocal),
        patch.object(streaming_mod, "_finalize_run", spy_finalize_run),
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
            new=lambda **_kwargs: _FakeGraphCancelsImmediately(),
        ),
    ):
        with pytest.raises(asyncio.CancelledError):
            async for _event in streaming_mod.stream_event_generator(
                body, fastapi_request, user
            ):
                pass

    cancelled = [
        call
        for call in finalize_calls
        if call.get("event_type") is RunEventType.RUN_CANCELLED
    ]
    assert cancelled, f"expected a run.cancelled finalize, got {finalize_calls!r}"
    payload = cancelled[-1]["payload"]
    assert "assistant_message_id" not in payload, (
        "no partial row was persisted, so the key must be absent rather than "
        f"an explicit null; payload={payload!r}"
    )
    validate_payload(RunEventType.RUN_CANCELLED.value, payload)
