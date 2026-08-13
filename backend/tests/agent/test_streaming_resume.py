"""Resumable-stream plumbing: sequence-numbered SSE frames teed into the
Redis stream buffer, with finish_stream after the terminal frame."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.api.agent import streaming
from src.api.agent.streaming import _format_sse_event
from tests.utils.agent_stream import (
    make_stream_request,
    sse_data,
    sse_event_name,
    sse_seq,
)


def test_format_sse_event_with_seq_prepends_id_line():
    frame = _format_sse_event("token", {"content": "hi"}, seq=7)
    assert frame.startswith("id: 7\n")
    assert "event: token\n" in frame
    assert frame.endswith("\n\n")


def test_format_sse_event_without_seq_is_legacy_format():
    frame = _format_sse_event("token", {"content": "hi"})
    assert frame == 'event: token\ndata: {"content": "hi"}\n\n'


def _frame_data(frame: str) -> dict:
    data_line = next(line for line in frame.splitlines() if line.startswith("data: "))
    return json.loads(data_line.removeprefix("data: "))


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
    body = make_stream_request(thread_id="thread-123", use_rag=False)
    current_user = Mock(id="user-1", organization_id="org-1")
    thread_obj = SimpleNamespace(id="thread-123")

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
        patch(
            "src.api.agent.streaming._resolve_thread",
            new=AsyncMock(return_value=(thread_obj, None)),
        ),
        patch(
            "src.api.agent.streaming._persist_user_message_guarded",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "src.api.agent.streaming._resolve_and_bind_project",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "src.api.agent.streaming._jobs_mod._persist_assistant_message_safe",
            new=AsyncMock(return_value="assistant-row-1"),
        ),
    ):
        events = []
        async for event in streaming.stream_event_generator(
            body, request, current_user
        ):
            events.append(event)

    # One documented exception to "every frame is sequenced and buffered": the
    # leading status/accepted frame is emitted BEFORE the client-supplied
    # thread id has passed the ownership check, so it must not touch the
    # thread's Redis pointer. It consumes seq 1 but is deliberately UNBUFFERED:
    # the buffer legitimately starts at seq 2, so `after=1` replays 2..N and a
    # resuming client loses nothing. Pinned here so it can only ever be that
    # one frame.
    assert sse_event_name(events[0]) == "status"
    assert sse_data(events[0])["phase"] == "accepted"
    assert sse_seq(events[0]) == 1

    # Every frame after it carries a strictly increasing id: line.
    sequenced = events[1:]
    ids = [sse_seq(e) for e in sequenced]
    assert all(seq is not None for seq in ids), sequenced
    assert ids == sorted(ids) and len(set(ids)) == len(ids)

    # And each was appended to the buffer (no heartbeats in this run), with
    # matching seq numbers — the resume replay is lossless from here on.
    assert [(seq, frame) for _, seq, frame in buf.appends] == list(zip(ids, sequenced))
    assert buf.appends[0][0] == "sid-thread-123"

    payloads = [_frame_data(frame) for frame in events]
    trace_ids = {payload["trace_id"] for payload in payloads}
    assert len(trace_ids) == 1
    for frame, payload in zip(events, payloads):
        seq = sse_seq(frame)
        assert payload["schema_version"] == "1.0"
        assert payload["sequence"] == seq
        assert payload["event_id"] == f"{payload['trace_id']}:{seq}"
        assert payload["occurred_at"].endswith("Z")
        assert payload["route"] in {"pending", "graph"}
    assert payloads[0]["thread_id"] is None
    assert payloads[0]["route"] == "pending"
    assert all(payload["thread_id"] == "thread-123" for payload in payloads[1:])
    assert all(payload["route"] == "graph" for payload in payloads[1:])

    # done is the terminal frame and finish_stream was called after it.
    assert "event: done\n" in events[-1]
    assert buf.finished == [("thread-123", "sid-thread-123")]


class _DisconnectThenHangGraph:
    """One token, then a timeout unless the caller closes the stream."""

    def __init__(self):
        self.closed = False
        self.timeout_raised = False

    async def astream_events(self, *args, **kwargs):
        try:
            yield {
                "event": "on_chat_model_stream",
                "name": "llm_node",
                "metadata": {"langgraph_node": "llm_node"},
                "data": {"chunk": SimpleNamespace(content="partial answer")},
            }
            self.timeout_raised = True
            raise TimeoutError("graph timed out while the client was connected")
        finally:
            self.closed = True

    async def aget_state(self, config):  # pragma: no cover - not reached
        return SimpleNamespace(values={}, tasks=())


@pytest.mark.asyncio
async def test_connected_graph_timeout_persists_partial_and_emits_error(monkeypatch):
    """A graph timeout with a connected client keeps the failure contract."""
    buf = _RecordingBuffer()
    buf.install(monkeypatch)

    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
    body = make_stream_request(thread_id="thread-timeout", use_rag=False)
    current_user = Mock(id="user-1", organization_id="org-1")
    persist = AsyncMock(return_value="row-1")
    thread_obj = SimpleNamespace(id="thread-timeout")
    graph = _DisconnectThenHangGraph()

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
            return_value=graph,
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
    assert graph.timeout_raised is True
    assert graph.closed is True
    # A connected client receives the terminal error, and it is replayable.
    assert any("event: error" in e for e in events)
    assert any("event: error" in frame for _, _, frame in buf.appends)


@pytest.mark.asyncio
async def test_buffered_disconnect_cancels_and_persists_partial(monkeypatch):
    """Browser Stop is terminal even when the Redis stream buffer is active."""
    buf = _RecordingBuffer()
    buf.install(monkeypatch)

    request_id = "buffered-stop-request"
    request = SimpleNamespace(
        state=SimpleNamespace(request_id=request_id),
        # Connected for the token, disconnected before the graph can raise.
        is_disconnected=AsyncMock(side_effect=[False, True, True]),
    )
    thread_id = "33333333-3333-3333-3333-333333333333"
    body = make_stream_request(thread_id=thread_id, use_rag=False)
    current_user = Mock(id="user-1", organization_id="org-1")
    persist = AsyncMock(return_value="row-1")
    finalize = AsyncMock(return_value=None)
    graph = _DisconnectThenHangGraph()
    thread_obj = SimpleNamespace(id=thread_id)
    acceptance = streaming.AcceptedSubmission(
        run_id="55555555-5555-5555-5555-555555555555",
        thread_id=thread_id,
        user_message_id="66666666-6666-6666-6666-666666666666",
        outbox_id="outbox-buffered-stop",
        idempotency_key="buffered-stop",
    )

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
            return_value=graph,
        ),
        patch(
            "src.api.agent.streaming._resolve_thread",
            new=AsyncMock(return_value=(thread_obj, None)),
        ),
        patch(
            "src.api.agent.streaming.accept_submission",
            new=AsyncMock(return_value=acceptance),
        ),
        patch(
            "src.api.agent.streaming.mark_submission_dispatched",
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
            "src.api.agent.streaming._finalize_run",
            new=finalize,
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

    persist.assert_awaited_once()
    kwargs = persist.await_args.kwargs
    assert kwargs["content"] == "partial answer"
    assert kwargs["stopped"] is True
    assert kwargs["thread_id"] == thread_id
    assert graph.closed is True
    assert graph.timeout_raised is False
    assert not any("event: error" in frame for frame in events)
    assert not any("event: done" in frame for frame in events)
    assert not any("event: error" in frame for _, _, frame in buf.appends)
    assert not any("event: done" in frame for _, _, frame in buf.appends)
    assert buf.finished == [(thread_id, f"sid-{thread_id}")]
    finalize.assert_awaited_once()
    assert finalize.await_args.kwargs["status"] is streaming.JobStatus.CANCELLED
    assert (
        finalize.await_args.kwargs["event_type"] is streaming.RunEventType.RUN_CANCELLED
    )
    assert finalize.await_args.kwargs["payload"] == {
        "reason": "client_disconnected",
        "request_id": request_id,
        # The cancellation path persists the stopped partial inline and links
        # the cancelled run to it (persist returns ``row-1`` above).
        "assistant_message_id": "row-1",
    }


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
        BufferedFrame(seq=3, frame="id: 3\nevent: done\ndata: {}\n\n"),
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


def test_resume_uses_last_event_id_header_as_cursor(monkeypatch):
    monkeypatch.setattr(
        execute_mod._stream_buffer, "active_stream_id", AsyncMock(return_value="sid-1")
    )
    cursors: list[int] = []

    async def read_after(sid, after_seq):
        cursors.append(after_seq)
        return [f for f in _frames() if f.seq > after_seq]

    monkeypatch.setattr(execute_mod._stream_buffer, "read_after", read_after)
    resp = _client().get(
        f"/api/v1/agent/stream/resume/{THREAD_ID}?after=1",
        headers={"Last-Event-ID": "2"},
    )

    assert resp.status_code == 200
    assert cursors[0] == 2
    assert "id: 1" not in resp.text and "id: 2\n" not in resp.text
    assert "event: done" in resp.text


def test_resume_rejects_invalid_last_event_id(monkeypatch):
    monkeypatch.setattr(
        execute_mod._stream_buffer, "active_stream_id", AsyncMock(return_value="sid-1")
    )
    resp = _client().get(
        f"/api/v1/agent/stream/resume/{THREAD_ID}",
        headers={"Last-Event-ID": "not-a-sequence"},
    )
    assert resp.status_code == 400
    assert "Last-Event-ID" in resp.json()["detail"]


def test_resume_rejects_negative_legacy_query_cursor():
    resp = _client().get(
        f"/api/v1/agent/stream/resume/{THREAD_ID}?after=-1",
    )
    assert resp.status_code == 422


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
        BufferedFrame(seq=3, frame="id: 3\nevent: done\ndata: {}\n\n"),
    ]

    async def read_after(sid, after_seq):
        return [f for f in frames if f.seq > after_seq]

    monkeypatch.setattr(execute_mod._stream_buffer, "read_after", read_after)
    resp = _client().get(f"/api/v1/agent/stream/resume/{THREAD_ID}")
    body = resp.text
    assert "id: 2\n" in body  # replay continued past the decoy token frame
    assert body.rstrip().endswith("event: done\ndata: {}")


def test_latest_turn_assistant_text_stops_at_human_boundary():
    """Turn-scoped scan must return '' for a turn with no AI text — never the
    PREVIOUS turn's answer (live dup: thread 014caf59, 2026-08-12)."""
    from types import SimpleNamespace as NS

    from src.api.agent.streaming import _latest_turn_assistant_text

    msgs = [
        NS(type="human", content="turn 1"),
        NS(type="ai", content="answer 1"),
        NS(type="human", content="turn 2 (parked on interrupt)"),
        NS(type="ai", content="", tool_calls=[{"name": "ingest_arxiv_papers"}]),
    ]
    assert _latest_turn_assistant_text(msgs) == ""


def test_latest_turn_assistant_text_returns_current_turn_answer():
    from types import SimpleNamespace as NS

    from src.api.agent.streaming import _latest_turn_assistant_text

    msgs = [
        NS(type="human", content="turn 1"),
        NS(type="ai", content="answer 1"),
        NS(type="human", content="turn 2"),
        NS(type="ai", content=""),
        NS(type="tool", content="{}"),
        NS(type="ai", content="answer 2"),
    ]
    assert _latest_turn_assistant_text(msgs) == "answer 2"


def test_latest_turn_assistant_text_empty_messages():
    from src.api.agent.streaming import _latest_turn_assistant_text

    assert _latest_turn_assistant_text([]) == ""
    assert _latest_turn_assistant_text(None) == ""
