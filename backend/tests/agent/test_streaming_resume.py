"""Resumable-stream plumbing: sequence-numbered SSE frames teed into the
Redis stream buffer, with finish_stream after the terminal frame."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.api.agent import streaming
from src.api.agent.streaming import _format_sse_event


def test_format_sse_event_with_seq_prepends_id_line():
    frame = _format_sse_event("token", {"content": "hi"}, seq=7)
    assert frame.startswith("id: 7\n")
    assert "event: token\n" in frame
    assert frame.endswith("\n\n")


def test_format_sse_event_without_seq_is_legacy_format():
    frame = _format_sse_event("token", {"content": "hi"})
    assert frame == 'event: token\ndata: {"content": "hi"}\n\n'


class _RecordingBuffer:
    def __init__(self):
        self.appends: list[tuple[str, int, str]] = []
        self.finished: list[tuple[str, str]] = []

    def install(self, monkeypatch):
        async def start_stream(thread_id):
            return f"sid-{thread_id}"

        async def append(sid, seq, frame):
            self.appends.append((sid, seq, frame))

        async def finish_stream(thread_id, sid):
            self.finished.append((thread_id, sid))

        monkeypatch.setattr(streaming._stream_buffer, "start_stream", start_stream)
        monkeypatch.setattr(streaming._stream_buffer, "append", append)
        monkeypatch.setattr(streaming._stream_buffer, "finish_stream", finish_stream)


class _FakeGraph:
    """Emits one user-facing token chunk, then ends with an AI answer."""

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
async def test_stream_frames_carry_ids_and_are_buffered(monkeypatch):
    buf = _RecordingBuffer()
    buf.install(monkeypatch)

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
        async for event in streaming.stream_event_generator(
            body, request, current_user
        ):
            events.append(event)

    # Every yielded frame carries a strictly increasing id: line.
    ids = [int(e.split("\n", 1)[0].removeprefix("id: ")) for e in events]
    assert all(e.startswith("id: ") for e in events), events
    assert ids == sorted(ids) and len(set(ids)) == len(ids)

    # Every frame was appended to the buffer (no heartbeats in this run),
    # with matching seq numbers.
    assert [(seq, frame) for _, seq, frame in buf.appends] == list(
        zip(ids, events)
    )
    assert buf.appends[0][0] == "sid-thread-123"

    # done is the terminal frame and finish_stream was called after it.
    assert "event: done\n" in events[-1]
    assert buf.finished == [("thread-123", "sid-thread-123")]
