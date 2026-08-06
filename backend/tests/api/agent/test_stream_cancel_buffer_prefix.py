"""Cancelling mid-token must not persist text the replay buffer never got.

``streamed_parts`` is the source of the stopped partial assistant row;
``emitter.emit()`` is what puts a token into the resumable Redis buffer the
client replays from. The streaming loop used to append to ``streamed_parts``
*before* awaiting ``emit()``, so a cancellation landing inside that await
persisted a chunk that was never buffered — the durable partial ran ahead of
every client-visible copy of the turn.

The cancellation benchmark caught this: one of three trials persisted
``The arX`` while the Redis token history ended at ``The ar``
(evals/AGENT_FLOW_BASELINE.md, P1).

The invariant this pins is directional: the persisted partial must always be a
*prefix* of what was buffered. Persisting less than was buffered is a benign
race (the client saw one more token than the server durably kept); persisting
more is a correctness failure, because it fabricates output no replay can
justify.
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

pytestmark = pytest.mark.integration

_CHUNKS = ["The ar", "X", "tefact"]


class _FakeGraphMultiToken:
    """Streams several user-facing tokens and never terminates on its own."""

    def __init__(self) -> None:
        self._snapshot = SimpleNamespace(values={"messages": []}, tasks=())

    async def astream_events(
        self, *_args: object, **_kwargs: object
    ) -> AsyncIterator[dict[str, object]]:
        for chunk in _CHUNKS:
            yield {
                "event": "on_chat_model_stream",
                "name": "llm",
                "metadata": {"langgraph_node": "llm_node"},
                "data": {"chunk": SimpleNamespace(content=chunk)},
            }

    async def aget_state(self, _config: object) -> SimpleNamespace:
        return self._snapshot


async def test_cancel_during_emit_never_persists_unbuffered_text(
    db_session: Any,
    thread_factory: Any,
    user_factory: Any,
    _engine: Any,
) -> None:
    """Cancel inside the second token's emit; the persisted row must stop at the first."""
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

    buffered: list[str] = []
    real_emit: Any = streaming_mod._SeqEmitter.emit

    async def emit_then_cancel(
        self: Any,
        event_type: str,
        data: dict[str, Any],
        *args: object,
        **kwargs: object,
    ) -> Any:
        """Record what reaches the buffer; abort partway through the 2nd token.

        Raising *before* delegating models the real window precisely: the
        cancellation lands inside the awaited emit, so this chunk never reaches
        the buffer. Under the old append-then-emit ordering it was already in
        ``streamed_parts`` by this point and got persisted anyway.
        """
        if event_type == streaming_mod.AgentStreamEvent.TOKEN:
            content = (data or {}).get("content", "")
            if content == "X":
                raise asyncio.CancelledError()
            buffered.append(content)
        return await real_emit(self, event_type, data, *args, **kwargs)

    with (
        patch.object(streaming_mod, "AsyncSessionLocal", TestSessionLocal),
        patch.object(jobs_mod, "AsyncSessionLocal", TestSessionLocal),
        patch.object(streaming_mod._SeqEmitter, "emit", emit_then_cancel),
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
            new=lambda **_kwargs: _FakeGraphMultiToken(),
        ),
    ):
        with pytest.raises(asyncio.CancelledError):
            async for _event in streaming_mod.stream_event_generator(
                body, fastapi_request, user
            ):
                pass

    assert buffered == ["The ar"], (
        "harness precondition: only the first token should have reached the "
        f"buffer before the cancel, got {buffered!r}"
    )

    await db_session.commit()
    row = (
        await db_session.execute(
            select(ChatMessage)
            .where(ChatMessage.thread_id == thread.id)
            .where(ChatMessage.role == MessageRole.ASSISTANT)
        )
    ).scalar_one_or_none()

    assert row is not None, "the cancelled turn must still persist its partial"
    db_session.info["_created"]["chat_messages"].append(row.id)

    buffered_text = "".join(buffered)
    assert buffered_text.startswith(row.content), (
        "persisted partial must be a prefix of the buffered stream; "
        f"persisted {row.content!r} is not a prefix of buffered {buffered_text!r}"
    )
    assert row.content == "The ar"
