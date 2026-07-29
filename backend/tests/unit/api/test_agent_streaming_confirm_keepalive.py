"""Confirm stream must emit heartbeat frames during long silent resume phases,
like the main /stream path — otherwise a proxy idle-timeout cuts the connection
with no done/error and the client hangs."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest


class _SilentThenDoneGraph:
    def __init__(self):
        self._items = iter(
            [
                {
                    "event": "on_chat_model_stream",
                    "name": "llm_node",
                    "metadata": {"langgraph_node": "llm_node"},
                    "data": {"chunk": SimpleNamespace(content="hi")},
                },
            ]
        )

    def astream_events(self, *a, **k):
        return self

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._items)
        except StopIteration:
            raise StopAsyncIteration

    async def aclose(self):
        pass

    async def aget_state(self, config):
        return SimpleNamespace(
            values={
                "user_id": "user-1",
                "page_context": {},
                "messages": [SimpleNamespace(type="ai", content="hi")],
                "tool_executions": [],
            },
            tasks=(),
        )


@pytest.mark.asyncio
async def test_confirm_stream_emits_heartbeat_from_keepalive():
    import src.api.agent.streaming as st

    async def fake_keepalive(event_iter, request, **kwargs):
        # One keepalive, then forward the real event, then stop.
        yield {"type": "keepalive", "elapsed_ms": 123}
        async for e in event_iter:
            yield {"type": "event", "event": e}

    graph = _SilentThenDoneGraph()
    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
    body = SimpleNamespace(thread_id="t-1", confirmed=True, model="")
    current_user = Mock(id="user-1", organization_id="org-1")

    with (
        patch.object(st, "_graph_events_with_keepalive", fake_keepalive),
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
            "src.services.agent._builders.compile_agent_graph",
            return_value=graph,
        ),
        patch(
            "src.api.agent.streaming._jobs_mod._persist_assistant_message_safe",
            new=AsyncMock(return_value="a1"),
        ),
        patch(
            "src.api.agent.streaming._latest_user_client_message_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "src.api.agent.streaming.AsyncSessionLocal",
            return_value=AsyncMock(),
        ),
    ):
        events = [
            e
            async for e in st.stream_confirm_event_generator(
                body, request, current_user
            )
        ]

    assert any("event: heartbeat" in e for e in events)
