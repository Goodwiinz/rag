"""Verifies the user row is persisted *before* the LLM call so an early
client disconnect (or a mid-stream graph error) leaves the user message
durable.

Task 4 of ``docs/plans/2026-05-13-agent-persist-perf.md``.

Direct-invokes ``stream_event_generator`` with a fake graph whose
``astream_events`` raises after yielding nothing, simulating an abrupt
mid-stream failure. Under the *old* behavior (user row written after
the stream completes) the failure prevents persistence and the row is
missing. Under the *new* behavior (user row written up-front, before
the graph runs) the row must already exist when the exception fires.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.chat_message import ChatMessage, MessageRole


pytestmark = pytest.mark.integration


class _FakeGraph:
    """Graph stub that fails on ``astream_events`` after the first token-shaped event.

    Mirrors a real client disconnect that prevents the post-stream
    finalization from running (the existing implementation's
    ``_persist_thread_messages`` call sits in the same ``try`` block that
    swallows the failure via the outer ``except Exception``).
    """

    def __init__(self):
        self._snapshot = SimpleNamespace(values={"messages": []}, tasks=())

    async def astream_events(self, *_args, **_kwargs):
        # Raise immediately so the post-stream persistence path never runs.
        raise RuntimeError("simulated mid-stream failure")
        yield {}  # pragma: no cover  (make this an async generator)

    async def aget_state(self, _config):
        return self._snapshot


async def test_user_message_persists_before_llm_call(
    db_session, thread_factory, user_factory, _engine
):
    """A mid-stream failure must still leave the user row durable."""
    user = await user_factory()
    thread = await thread_factory(user=user)

    cmid = uuid4()

    # Build a request body mirroring AgentExecuteRequest shape (we use
    # SimpleNamespace + the real AgentMessage so .role / .content /
    # .client_message_id attribute access works the way the helpers expect).
    from src.api.agent.execute import AgentExecuteRequest, AgentMessage

    body = AgentExecuteRequest(
        messages=[
            AgentMessage(role="user", content="ping", client_message_id=cmid)
        ],
        thread_id=str(thread.id),
    )

    fastapi_request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))

    # Bind a sessionmaker to the *test* engine so the streaming handler's
    # internal ``AsyncSessionLocal()`` opens a session against the same DB
    # the fixtures wrote to.
    TestSessionLocal = async_sessionmaker(
        _engine, expire_on_commit=False
    )

    from src.api.agent import streaming as streaming_mod

    with (
        patch.object(streaming_mod, "AsyncSessionLocal", TestSessionLocal),
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
        events = []
        async for event in streaming_mod.stream_event_generator(
            body, fastapi_request, user
        ):
            events.append(event)

    # The simulated failure must have surfaced as an SSE error event.
    assert any(e.startswith("event: error") for e in events), events

    # Use the test-fixture session (separate connection / transaction) to
    # verify the row landed in the DB.
    await db_session.commit()  # release any held snapshot
    row = (
        await db_session.execute(
            select(ChatMessage)
            .where(ChatMessage.thread_id == thread.id)
            .where(ChatMessage.role == MessageRole.USER)
        )
    ).scalar_one_or_none()

    assert row is not None, (
        "user row must exist even when the LangGraph stream fails before "
        "the post-stream persist call runs"
    )

    # Track row for fixture cleanup.
    db_session.info["_created"]["chat_messages"].append(row.id)
