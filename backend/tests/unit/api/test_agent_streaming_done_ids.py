"""Regression: in canonical-persistence mode the MAIN /stream `done` frame must
carry thread_id + assistant_message_id + client_message_id so the client can
reconcile its optimistic bubble with the server-persisted row.

The confirm stream already pins this (test_agent_streaming_confirm_persistence.py
::test_confirm_done_carries_assistant_message_id_in_canonical_mode). The main
`stream_event_generator` ON branch (streaming.py done_payload) mirrors it but was
untested — this closes that gap. Canonical mode is enabled in the dev cluster
(AGENT_CANONICAL_PERSISTENCE=true), so this is the live path.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from tests.utils.agent_stream import frames_of_type, make_stream_request, sse_data


class _FakeGraph:
    """No streamed tokens; final state carries an AI answer (canonical persist
    writes the row, id rides the done payload)."""

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
                "tool_executions": [],
            },
            tasks=(),
        )


def _parse_done(events):
    # assert-then-index, never a bare next(): inside an async test a
    # StopIteration surfaces as "RuntimeError: coroutine raised StopIteration"
    # and hides which frame was actually missing.
    done_frames = frames_of_type(events, "done")
    assert done_frames, f"no done frame in: {events}"
    return sse_data(done_frames[0])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("persisted_id", "terminal_event"),
    [("assistant-msg-1", "done"), (None, "error")],
)
async def test_main_canonical_completion_requires_persisted_assistant(
    persisted_id, terminal_event
):
    from src.api.agent.streaming import stream_event_generator

    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
    body = make_stream_request(
        messages=[
            {
                "role": "user",
                "content": "hi",
                "client_message_id": "11111111-1111-1111-1111-111111111111",
            }
        ],
        thread_id="11111111-1111-1111-1111-111111111112",
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
            "src.services.agent.memory.get_memory_store",
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
        patch(
            "src.api.agent.streaming._resolve_thread",
            new=AsyncMock(
                return_value=(
                    SimpleNamespace(id="thread-resolved-1"),
                    "conv-1",
                )
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
            new=AsyncMock(return_value=persisted_id),
        ),
        patch(
            "src.api.agent.streaming._canonical_persistence_enabled",
            return_value=True,
        ),
    ):
        events = []
        async for event in stream_event_generator(body, request, current_user):
            events.append(event)

    terminal_frames = frames_of_type(events, terminal_event)
    assert len(terminal_frames) == 1
    if persisted_id is None:
        assert not frames_of_type(events, "done")
        return

    done = sse_data(terminal_frames[0])
    assert done["status"] == "complete"
    assert done["thread_id"] == "thread-resolved-1"
    assert done["assistant_message_id"] == "assistant-msg-1"
    # client_message_id is the deterministic uuid5 derived from the user cmid.
    assert done["client_message_id"]
