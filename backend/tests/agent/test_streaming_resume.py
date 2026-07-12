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


class _DisconnectThenHangGraph:
    """One token, then (post-disconnect, mid-drain) a timeout."""

    async def astream_events(self, *args, **kwargs):
        yield {
            "event": "on_chat_model_stream",
            "name": "llm_node",
            "metadata": {"langgraph_node": "llm_node"},
            "data": {"chunk": SimpleNamespace(content="partial answer")},
        }
        raise TimeoutError("graph hung during drain")

    async def aget_state(self, config):  # pragma: no cover - not reached
        return SimpleNamespace(values={}, tasks=())


@pytest.mark.asyncio
async def test_drain_timeout_after_disconnect_persists_partial(monkeypatch):
    """Regression: a graph death mid-drain (client already gone, buffer
    active) must persist the accumulated partial with stopped=True instead of
    silently losing it in the generic error handler."""
    buf = _RecordingBuffer()
    buf.install(monkeypatch)

    # Connected for the first event, gone afterwards -> drain mode.
    request = SimpleNamespace(
        is_disconnected=AsyncMock(side_effect=[False, True, True, True])
    )
    body = SimpleNamespace(
        messages=[SimpleNamespace(role="user", content="hi")],
        page_context={"type": "general"},
        thread_id="thread-timeout",
        model=None,
    )
    current_user = Mock(id="user-1", organization_id="org-1")
    persist = AsyncMock(return_value="row-1")
    thread_obj = SimpleNamespace(id="thread-timeout")

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
            return_value=_DisconnectThenHangGraph(),
        ),
        patch(
            "src.api.agent.streaming._resolve_thread",
            new=AsyncMock(return_value=(thread_obj, None)),
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
            "src.api.agent.streaming._jobs_mod._persist_assistant_message_safe",
            new=persist,
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

    # Partial persisted with stopped=True, exactly once.
    persist.assert_awaited_once()
    kwargs = persist.await_args.kwargs
    assert kwargs["content"] == "partial answer"
    assert kwargs["stopped"] is True
    assert kwargs["thread_id"] == "thread-timeout"
    # Error frame buffered but not yielded to the dead client.
    assert not any("event: error" in e for e in events)
    assert any("event: error" in frame for _, _, frame in buf.appends)


# ---------------------------------------------------------------------------
# GET /stream/resume/{thread_id}
# ---------------------------------------------------------------------------

from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.agent import execute as execute_mod
from src.core.database import get_db
from src.core.dependencies import get_current_user
from src.services.agent.stream_buffer import BufferedFrame

THREAD_ID = str(uuid4())


def _client(owns_thread=True):
    app = FastAPI()
    app.include_router(execute_mod.router)

    user = Mock(id="user-1", organization_id="org-1")
    thread = SimpleNamespace(id=THREAD_ID) if owns_thread else None
    db = AsyncMock()
    db.execute.return_value = Mock(scalar_one_or_none=Mock(return_value=thread))

    async def override_db():
        yield db

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def _frames():
    return [
        BufferedFrame(seq=1, frame='id: 1\nevent: token\ndata: {"c": "a"}\n\n'),
        BufferedFrame(seq=2, frame='id: 2\nevent: token\ndata: {"c": "b"}\n\n'),
        BufferedFrame(seq=3, frame='id: 3\nevent: done\ndata: {}\n\n'),
    ]


def test_resume_no_active_stream_returns_204(monkeypatch):
    monkeypatch.setattr(
        execute_mod._stream_buffer, "active_stream_id", AsyncMock(return_value=None)
    )
    resp = _client().get(f"/api/v1/agent/stream/resume/{THREAD_ID}")
    assert resp.status_code == 204


def test_resume_replays_frames_and_stops_after_done(monkeypatch):
    monkeypatch.setattr(
        execute_mod._stream_buffer, "active_stream_id", AsyncMock(return_value="sid-1")
    )

    async def read_after(sid, after_seq):
        assert sid == "sid-1"
        return [f for f in _frames() if f.seq > after_seq]

    monkeypatch.setattr(execute_mod._stream_buffer, "read_after", read_after)
    resp = _client().get(f"/api/v1/agent/stream/resume/{THREAD_ID}")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    body = resp.text
    assert body.index("id: 1\n") < body.index("id: 2\n") < body.index("event: done")


def test_resume_unowned_thread_returns_404(monkeypatch):
    monkeypatch.setattr(
        execute_mod._stream_buffer, "active_stream_id", AsyncMock(return_value="sid-1")
    )
    resp = _client(owns_thread=False).get(f"/api/v1/agent/stream/resume/{THREAD_ID}")
    assert resp.status_code == 404


def test_resume_excludes_frames_at_or_below_after(monkeypatch):
    monkeypatch.setattr(
        execute_mod._stream_buffer, "active_stream_id", AsyncMock(return_value="sid-1")
    )

    async def read_after(sid, after_seq):
        return [f for f in _frames() if f.seq > after_seq]

    monkeypatch.setattr(execute_mod._stream_buffer, "read_after", read_after)
    resp = _client().get(f"/api/v1/agent/stream/resume/{THREAD_ID}?after=2")
    assert "id: 1" not in resp.text and "id: 2\n" not in resp.text
    assert "event: done" in resp.text


def test_resume_token_containing_terminal_text_does_not_stop_replay(monkeypatch):
    # LLM token text is unconstrained: a token frame whose data contains the
    # literal string "event: done" must not terminate the replay early.
    monkeypatch.setattr(
        execute_mod._stream_buffer, "active_stream_id", AsyncMock(return_value="sid-1")
    )
    frames = [
        BufferedFrame(
            seq=1,
            frame='id: 1\nevent: token\ndata: {"c": "the SSE frame is event: done"}\n\n',
        ),
        BufferedFrame(seq=2, frame='id: 2\nevent: token\ndata: {"c": "more"}\n\n'),
        BufferedFrame(seq=3, frame='id: 3\nevent: done\ndata: {}\n\n'),
    ]

    async def read_after(sid, after_seq):
        return [f for f in frames if f.seq > after_seq]

    monkeypatch.setattr(execute_mod._stream_buffer, "read_after", read_after)
    resp = _client().get(f"/api/v1/agent/stream/resume/{THREAD_ID}")
    body = resp.text
    assert "id: 2\n" in body  # replay continued past the decoy token frame
    assert body.rstrip().endswith("event: done\ndata: {}")
