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
    """astream_events yields one event; the generator should aclose() it the
    moment the client is seen disconnected, before aget_state is reached."""

    def __init__(self):
        self.aclosed = False
        self.aget_state_called = False
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
        self.aget_state_called = True
        return SimpleNamespace(values={}, tasks=())


@pytest.mark.asyncio
async def test_confirm_stream_acloses_graph_on_disconnect():
    from src.api.agent.streaming import stream_confirm_event_generator

    graph = _DisconnectGraph()
    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=True))
    body = SimpleNamespace(thread_id="thread-789", confirmed=True)
    current_user = Mock(id="user-1", organization_id="org-1")

    with (
        patch(
            "src.services.agent.observability.configure_langsmith", return_value=None
        ),
        patch(
            "src.services.agent.checkpointer.get_checkpointer",
            new=AsyncMock(return_value=object()),
        ),
        patch(
            "src.services.agent.graph.compile_agent_graph",
            return_value=graph,
        ),
        patch(
            "src.api.agent.streaming._persist_thread_messages",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "src.api.agent.streaming.AsyncSessionLocal",
            return_value=AsyncMock(),
        ),
    ):
        events = []
        async for event in stream_confirm_event_generator(body, request, current_user):
            events.append(event)

    assert graph.aclosed is True
    assert graph.aget_state_called is False  # skipped the snapshot/emit path
    assert not any(
        e.startswith("event: done") or e.startswith("event: confirmation")
        for e in events
    )
