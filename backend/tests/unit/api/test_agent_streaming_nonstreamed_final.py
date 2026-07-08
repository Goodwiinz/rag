"""Regression: the SSE stream must surface a final answer that was produced
WITHOUT streaming (greeting fast-path, templated/degraded reply, force_synthesis).

Those paths set the AIMessage directly and emit no ``on_chat_model_stream``
chunks, so without the fallback the client receives zero ``token`` events and
renders an empty response ("stream completed without any tokens").
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest


class _FakeGraphNoStream:
    """Graph that emits NO on_chat_model_stream events (e.g. greeting fast-path)
    but whose final state carries an AI answer."""

    async def astream_events(self, *args, **kwargs):
        # A non-token chain event — no on_chat_model_stream is ever yielded.
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
                "messages": [
                    SimpleNamespace(
                        type="ai",
                        content="Hi — how can I help with your research today?",
                    )
                ],
                "tool_executions": [],
            },
            tasks=(),
        )


@pytest.mark.asyncio
async def test_stream_emits_nonstreamed_final_answer_as_token():
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
            return_value=_FakeGraphNoStream(),
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

    # Exactly one token event, carrying the non-streamed final answer.
    token_events = [e for e in events if "event: token\n" in e]
    assert len(token_events) == 1, f"expected one fallback token, got {events}"
    assert "how can I help with your research today" in token_events[0]
    # And it must come before `done`.
    assert "event: done\n" in events[-1]
    done_idx = next(i for i, e in enumerate(events) if "event: done\n" in e)
    token_idx = next(i for i, e in enumerate(events) if "event: token\n" in e)
    assert token_idx < done_idx
