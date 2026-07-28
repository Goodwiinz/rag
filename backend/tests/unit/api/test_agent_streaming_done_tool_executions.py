"""Regression: the main /stream ``done`` frame must carry the graph-final
``tool_executions`` (args redacted) so the client's committed turn renders
tools without a page reload.

Previously the committed in-memory turn's tools came only from the live
``tool_start``/``tool_end`` frames; a dropped frame left the bubble tool-less
until a refresh re-read the persisted row. The confirm stream already carried
tools in its done payload — this pins the same for the main stream.
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest


class _FakeGraphWithTool:
    """Graph that emits no on_chat_model_stream but whose final state carries a
    settled tool execution (as if the live frames were never delivered)."""

    async def astream_events(self, *args, **kwargs):
        yield {
            "event": "on_chain_end",
            "name": "llm_node",
            "metadata": {"langgraph_node": "llm_node"},
            "data": {"output": {}},
        }

    async def aget_state(self, config):
        return SimpleNamespace(
            values={
                "user_id": "user-1",
                "messages": [SimpleNamespace(type="ai", content="Answer.")],
                "tool_executions": [
                    {
                        "id": "t1",
                        "tool_name": "search_documents",
                        "tool_display_name": "Search Documents",
                        "args": {"query": "photosynthesis"},
                        "status": "completed",
                        "result": {"message": "found 3 docs"},
                        "duration_ms": 4321,
                    }
                ],
            },
            tasks=(),
        )


def _parse_done(events):
    frame = next(e for e in events if "event: done\n" in e)
    data_line = next(ln for ln in frame.splitlines() if ln.startswith("data: "))
    return json.loads(data_line[len("data: ") :])


@pytest.mark.asyncio
async def test_done_frame_carries_tool_executions():
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
            "src.services.agent._builders.compile_agent_graph",
            return_value=_FakeGraphWithTool(),
        ),
        patch(
            "src.api.agent.streaming.AsyncSessionLocal",
            return_value=AsyncMock(),
        ),
        patch(
            "src.api.agent.streaming._resolve_thread",
            new=AsyncMock(
                return_value=(SimpleNamespace(id="thread-resolved-1"), "conv-1")
            ),
        ),
        patch(
            "src.api.agent.streaming._persist_user_message_guarded",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "src.api.agent.streaming._resolve_and_bind_project",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "src.services.agent.agent_execution_service._persist_assistant_message_safe",
            new=AsyncMock(return_value="assistant-msg-1"),
        ),
    ):
        events = []
        async for event in stream_event_generator(body, request, current_user):
            events.append(event)

    done = _parse_done(events)
    assert done["status"] == "complete"
    assert len(done["tool_executions"]) == 1
    te = done["tool_executions"][0]
    assert te["tool_name"] == "search_documents"
    assert te["duration_ms"] == 4321
