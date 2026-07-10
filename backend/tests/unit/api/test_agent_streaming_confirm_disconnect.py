"""Regression: stream/confirm cancels the resumed run on client disconnect.

stream_confirm_event_generator previously `break`-ed out of the
astream_events loop on disconnect WITHOUT aclose()-ing the iterator, leaving
the resumed graph run (which may execute destructive tools) running into a dead
socket. It must aclose() the iterator and stop without emitting further events.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest


class _DisconnectGraph:
    """astream_events yields one event; on client disconnect the generator must
    aclose() the iterator (cancelling the resumed run) and stop without emitting
    the confirmation/done events."""

    def __init__(self):
        self.aclosed = False
        self._sent = False

    def astream_events(self, *args, **kwargs):
        return self

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._sent:
            self._sent = True
            return {
                "event": "on_chat_model_stream",
                "name": "llm_node",
                "metadata": {"langgraph_node": "llm_node"},
                "data": {"chunk": SimpleNamespace(content="x")},
            }
        raise StopAsyncIteration

    async def aclose(self):
        self.aclosed = True

    async def aget_state(self, config):
        # Populated + owned by the requesting user so the pre-loop ownership
        # snapshot passes and execution reaches the stream loop.
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
async def test_confirm_stream_acloses_graph_on_disconnect():
    from src.api.agent.streaming import stream_confirm_event_generator

    graph = _DisconnectGraph()
    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=True))
    body = SimpleNamespace(thread_id="thread-789", confirmed=True, model="")
    current_user = Mock(id="user-1", organization_id="org-1")

    with (
        # Force the legacy (no stream buffer) path: these tests cover the
        # Redis-down disconnect behavior.
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
            "src.api.agent.streaming.AsyncSessionLocal",
            return_value=AsyncMock(),
        ),
    ):
        events = []
        async for event in stream_confirm_event_generator(body, request, current_user):
            events.append(event)

    assert graph.aclosed is True  # resumed run cancelled
    # Early-returned before the post-loop snapshot/emit path.
    assert not any(
        "event: done" in e or "event: confirmation" in e
        for e in events
    )


@pytest.mark.asyncio
async def test_confirm_stream_persists_partial_on_disconnect():
    """A destructive HITL tool may have already committed; the partial
    assistant answer streamed before the disconnect must be persisted
    (stopped=True), mirroring the main stream's disconnect branch.

    NOTE: unlike the aclose-only test above, ``is_disconnected`` returns
    False on the first poll (so the "x" token is streamed + accumulated),
    then True — modelling the real scenario (a token was delivered, THEN
    the client hung up). A permanently-disconnected client never receives a
    token to persist, so this ordering is required to exercise the persist
    path.
    """
    from src.api.agent.streaming import stream_confirm_event_generator

    graph = _DisconnectGraph()
    request = SimpleNamespace(
        is_disconnected=AsyncMock(side_effect=[False, True, True])
    )
    body = SimpleNamespace(thread_id="thread-789", confirmed=True, model="")
    current_user = Mock(id="user-1", organization_id="org-1")

    persist = AsyncMock(return_value="assistant-row-1")
    with (
        # Force the legacy (no stream buffer) path: these tests cover the
        # Redis-down disconnect behavior.
        patch(
            "src.api.agent.streaming._stream_buffer.start_stream",
            new=AsyncMock(side_effect=RuntimeError("redis down")),
        ),
        patch(
            "src.services.agent.observability.configure_langsmith",
            return_value=None,
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
            "src.api.agent.streaming._jobs_mod._persist_assistant_message_safe",
            new=persist,
        ),
        patch(
            "src.api.agent.streaming._latest_user_client_message_id",
            new=AsyncMock(return_value="user-cmid-1"),
        ),
        patch(
            "src.api.agent.streaming.AsyncSessionLocal",
            return_value=AsyncMock(),
        ),
    ):
        async for _ in stream_confirm_event_generator(body, request, current_user):
            pass

    persist.assert_awaited_once()
    kwargs = persist.await_args.kwargs
    assert kwargs["content"] == "x"
    assert kwargs["stopped"] is True
    assert kwargs["thread_id"] == "thread-789"
    # idempotency key derived from the original user turn's client_message_id
    assert kwargs["client_message_id"] is not None
