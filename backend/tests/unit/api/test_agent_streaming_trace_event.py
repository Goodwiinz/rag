from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest


class _FakeGraph:
    async def astream_events(self, *args, **kwargs):
        yield {
            "event": "on_chat_model_stream",
            "name": "llm_node",
            "metadata": {"langgraph_node": "llm_node"},
            "data": {"chunk": SimpleNamespace(content="hello")},
        }

    async def aget_state(self, config):
        return SimpleNamespace(
            values={
                "messages": [SimpleNamespace(type="ai", content="hello")],
                "tool_executions": [],
            },
            tasks=(),
        )


@pytest.mark.asyncio
async def test_stream_event_generator_emits_trace_event_before_workflow_events():
    from src.api.agent.streaming import stream_event_generator

    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
    body = SimpleNamespace(
        messages=[SimpleNamespace(role="user", content="hi")],
        page_context={"type": "general"},
        thread_id="thread-123",
        model=None,
    )
    current_user = Mock(id="user-1", organization_id="org-1")

    with (
        patch(
            "src.services.agent.observability.configure_langsmith",
            return_value=None,
        ),
        patch(
            "src.services.agent.checkpointer.get_checkpointer",
            new=AsyncMock(return_value=object()),
        ),
        patch(
            "src.services.agent.graph.compile_agent_graph",
            return_value=_FakeGraph(),
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

    assert events[0].startswith("event: trace\n")
    assert events[1].startswith("event: token\n")
    trace_payload = events[0].split("data: ", 1)[1].strip()
    assert '"thread_id": "thread-123"' in trace_payload
    assert '"cli_session_id": ""' in trace_payload
    assert '"langsmith_run_id": ""' in trace_payload
    assert '"langsmith_url": ""' in trace_payload
    assert events[-1].startswith("event: done\n")


@pytest.mark.asyncio
async def test_stream_confirm_event_generator_emits_trace_event_before_workflow_events():
    from src.api.agent.streaming import stream_confirm_event_generator

    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
    body = SimpleNamespace(thread_id="thread-456", confirmed=True)
    current_user = Mock(id="user-1", organization_id="org-1")

    with (
        patch(
            "src.services.agent.observability.configure_langsmith",
            return_value=None,
        ),
        patch(
            "src.services.agent.checkpointer.get_checkpointer",
            new=AsyncMock(return_value=object()),
        ),
        patch(
            "src.services.agent.graph.compile_agent_graph",
            return_value=_FakeGraph(),
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

    assert events[0].startswith("event: trace\n")
    assert events[1].startswith("event: token\n")
    trace_payload = events[0].split("data: ", 1)[1].strip()
    assert '"thread_id": "thread-456"' in trace_payload
    assert '"cli_session_id": ""' in trace_payload
    assert '"langsmith_run_id": ""' in trace_payload
    assert '"langsmith_url": ""' in trace_payload
    assert events[-1].startswith("event: done\n")
