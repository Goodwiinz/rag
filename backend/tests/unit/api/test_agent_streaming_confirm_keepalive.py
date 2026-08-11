"""Confirm stream must emit heartbeat frames during long silent resume phases,
like the main /stream path — otherwise a proxy idle-timeout cuts the connection
with no done/error and the client hangs."""

import asyncio
import time
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


class _TokenThenHangIterator:
    def __init__(self):
        self.calls = 0
        self.cancelled = asyncio.Event()
        self._never = asyncio.Event()

    def __aiter__(self):
        return self

    async def __anext__(self):
        self.calls += 1
        if self.calls == 1:
            return {"event": "token"}
        try:
            await self._never.wait()
        finally:
            self.cancelled.set()
        raise StopAsyncIteration


@pytest.mark.asyncio
async def test_graph_keepalive_polls_disconnect_while_next_event_is_pending(
    monkeypatch,
):
    import src.api.agent.streaming as st

    graph = _TokenThenHangIterator()
    request = SimpleNamespace(
        # Disconnect immediately after the check that starts the hanging pull.
        is_disconnected=AsyncMock(side_effect=[False, False, True])
    )
    monkeypatch.setattr(st, "_SSE_KEEPALIVE_SECONDS", 0.2)
    monkeypatch.setattr(st, "_SSE_DISCONNECT_POLL_SECONDS", 0.01, raising=False)

    events = st._graph_events_with_keepalive(graph, request)
    assert await anext(events) == {"type": "event", "event": {"event": "token"}}

    started = time.monotonic()
    assert await asyncio.wait_for(anext(events), timeout=0.1) == {"type": "disconnect"}
    assert time.monotonic() - started < 0.1
    with pytest.raises(StopAsyncIteration):
        await anext(events)
    assert graph.cancelled.is_set()


@pytest.mark.asyncio
async def test_graph_keepalive_does_not_emit_heartbeat_at_disconnect_poll_cadence(
    monkeypatch,
):
    import src.api.agent.streaming as st

    graph = _TokenThenHangIterator()
    graph.calls = 1
    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
    monkeypatch.setattr(st, "_SSE_KEEPALIVE_SECONDS", 0.05)
    monkeypatch.setattr(st, "_SSE_DISCONNECT_POLL_SECONDS", 0.005, raising=False)

    events = st._graph_events_with_keepalive(graph, request)
    next_item = asyncio.create_task(anext(events))
    await asyncio.sleep(0.02)
    assert not next_item.done()
    assert (await asyncio.wait_for(next_item, timeout=0.1))["type"] == "keepalive"
    await events.aclose()
    assert graph.cancelled.is_set()


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
            "src.services.agent.graph.compile_agent_graph",
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
