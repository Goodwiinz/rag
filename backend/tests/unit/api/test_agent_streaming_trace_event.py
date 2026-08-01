"""The ``trace`` frame must precede every WORKFLOW frame on both stream
generators.

``status`` progress frames are deliberately outside that contract: the first
one (``phase: accepted``) is emitted before the thread id has passed the
ownership check, i.e. before a trace payload can honestly name a thread. The
assertions below therefore run over ``workflow_frames`` rather than raw
indices, so adding another progress frame cannot re-break them.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from tests.utils.agent_stream import (
    make_stream_request,
    sse_event_name,
    workflow_frames,
)


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
                "user_id": "user-1",
                "messages": [SimpleNamespace(type="ai", content="hello")],
                "tool_executions": [],
            },
            tasks=(),
        )


@pytest.mark.asyncio
async def test_stream_event_generator_emits_trace_event_before_workflow_events():
    from src.api.agent.streaming import stream_event_generator

    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
    body = make_stream_request(thread_id="thread-123")
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
            "src.api.agent.streaming.AsyncSessionLocal",
            return_value=AsyncMock(),
        ),
    ):
        events = []
        async for event in stream_event_generator(body, request, current_user):
            events.append(event)

    # The very first frame on the main stream is the pre-ownership progress
    # signal; trace still leads everything the client renders as workflow.
    assert sse_event_name(events[0]) == "status"
    workflow = workflow_frames(events)
    assert sse_event_name(workflow[0]) == "trace"
    assert sse_event_name(workflow[1]) == "token"
    trace_payload = workflow[0].split("data: ", 1)[1].strip()
    assert '"thread_id": "thread-123"' in trace_payload
    assert '"cli_session_id": ""' in trace_payload
    assert '"langsmith_run_id": ""' in trace_payload
    assert '"langsmith_url": ""' in trace_payload
    assert "event: done\n" in events[-1]


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
            "src.api.agent.streaming.AsyncSessionLocal",
            return_value=AsyncMock(),
        ),
    ):
        events = []
        async for event in stream_confirm_event_generator(body, request, current_user):
            events.append(event)

    workflow = workflow_frames(events)
    assert sse_event_name(workflow[0]) == "trace"
    assert sse_event_name(workflow[1]) == "token"
    trace_payload = workflow[0].split("data: ", 1)[1].strip()
    assert '"thread_id": "thread-456"' in trace_payload
    assert '"cli_session_id": ""' in trace_payload
    assert '"langsmith_run_id": ""' in trace_payload
    assert '"langsmith_url": ""' in trace_payload
    assert "event: done\n" in events[-1]
