from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest


class _FakeGraph:
    def __init__(self, snapshot=None):
        self._snapshot = snapshot or SimpleNamespace(values={"messages": []}, tasks=())

    async def astream_events(self, *args, **kwargs):
        if False:
            yield {}

    async def aget_state(self, config):
        return self._snapshot


@pytest.mark.asyncio
async def test_stream_event_generator_bootstraps_langsmith_before_compile():
    from src.api.agent.streaming import stream_event_generator

    configured = False

    def fake_configure_langsmith():
        nonlocal configured
        configured = True

    def fake_compile_agent_graph(*, checkpointer, store=None):
        assert configured, "configure_langsmith must run before graph compilation"
        return _FakeGraph()

    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=True))
    body = SimpleNamespace(messages=[], page_context={"type": "general"}, thread_id="", model=None)
    current_user = Mock(id="user-1", organization_id="org-1")

    with (
        patch(
            "src.services.agent.observability.configure_langsmith",
            side_effect=fake_configure_langsmith,
        ),
        patch(
            "src.services.agent.checkpointer.get_checkpointer",
            new=AsyncMock(return_value=object()),
        ),
        patch(
            "src.services.agent.graph.compile_agent_graph",
            side_effect=fake_compile_agent_graph,
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
        async for event in stream_event_generator(body, request, current_user):
            events.append(event)

    assert configured is True
    assert events[-1].startswith("event: done")


@pytest.mark.asyncio
async def test_stream_confirm_event_generator_bootstraps_langsmith_before_compile():
    from src.api.agent.streaming import stream_confirm_event_generator

    configured = False

    def fake_configure_langsmith():
        nonlocal configured
        configured = True

    def fake_compile_agent_graph(*, checkpointer, store=None):
        assert configured, "configure_langsmith must run before graph compilation"
        return _FakeGraph(current_snapshot)

    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=True))
    body = SimpleNamespace(thread_id="thread-1", confirmed=True)
    current_user = Mock(id="user-1", organization_id="org-1")

    current_snapshot = SimpleNamespace(
        values={"page_context": {"type": "general"}, "user_id": "user-1"},
        tasks=(),
    )

    with (
        patch(
            "src.services.agent.observability.configure_langsmith",
            side_effect=fake_configure_langsmith,
        ),
        patch(
            "src.services.agent.checkpointer.get_checkpointer",
            new=AsyncMock(return_value=object()),
        ),
        patch(
            "src.services.agent.graph.compile_agent_graph",
            side_effect=fake_compile_agent_graph,
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
        async for event in stream_confirm_event_generator(
            body, request, current_user
        ):
            events.append(event)

    assert configured is True
    assert events[-1].startswith("event: done")
