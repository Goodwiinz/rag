"""Regression tests for the replay/fast-path/stream-buffer lifecycle findings
(agent audit round 1, 2026-08-16: M13, L3, L14, L15).

Each pre-fix case is proven to fail against unmodified code before the fix
lands (see the PR description for verbatim runs); the paired control case
pins that the fix doesn't regress the surrounding behavior. Fakes only — no
Postgres/Redis, matching ``tests/agent/test_stream_buffer.py`` /
``tests/api/agent/test_stream_fast_path.py``.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.api.agent import streaming
from src.services.agent import fast_path, stream_buffer

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# M13 — replay_buffered_stream must not go silent during a producer gap
# ---------------------------------------------------------------------------


def _frame(seq: int, event: str = "token") -> stream_buffer.BufferedFrame:
    return stream_buffer.BufferedFrame(
        seq=seq, frame=f"id: {seq}\nevent: {event}\ndata: {{}}\n\n"
    )


class _Request:
    """``request.is_disconnected()`` stub — never disconnects."""

    async def is_disconnected(self) -> bool:
        return False


async def _collect(agen: Any) -> list[Any]:
    return [item async for item in agen]


async def test_replay_emits_keepalive_during_silent_producer_gap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A producer-silent stretch (planner/classifier/reflection, no buffered
    frame to replay) must not leave the follower with zero bytes until the
    terminal frame — that is exactly the gap an idle-timeout proxy kills."""
    monkeypatch.setattr(streaming.asyncio, "sleep", AsyncMock())

    # 12 empty polls (> _SSE_KEEPALIVE_SECONDS=10) before the run's terminal
    # frame lands, modelling a long silent internal phase.
    poll_results: list[list[Any]] = [[] for _ in range(12)] + [[_frame(1, "done")]]

    async def fake_read_after(
        _stream_id: str, _after: int, start_index: int | None = None
    ) -> list[Any]:
        return poll_results.pop(0) if poll_results else []

    monkeypatch.setattr(streaming._stream_buffer, "read_after", fake_read_after)
    monkeypatch.setattr(
        streaming._stream_buffer,
        "active_stream_id",
        AsyncMock(return_value="sid-1"),
    )

    frames = await _collect(
        streaming.replay_buffered_stream(
            _Request(), thread_id="thread-1", stream_id="sid-1"
        )
    )

    keepalives = [f for f in frames if f == ": keepalive\n\n"]
    assert keepalives, f"expected at least one keepalive frame, got {frames!r}"
    assert frames[-1] == _frame(1, "done").frame


async def test_replay_with_steady_frames_never_interleaves_keepalive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Control: while the producer keeps emitting, no keepalive is injected
    mid-batch, and the idle counter doesn't carry over between batches."""
    monkeypatch.setattr(streaming.asyncio, "sleep", AsyncMock())

    poll_results = [
        [_frame(1), _frame(2)],
        [_frame(3, "done")],
    ]

    async def fake_read_after(
        _stream_id: str, _after: int, start_index: int | None = None
    ) -> list[Any]:
        return poll_results.pop(0) if poll_results else []

    monkeypatch.setattr(streaming._stream_buffer, "read_after", fake_read_after)
    monkeypatch.setattr(
        streaming._stream_buffer,
        "active_stream_id",
        AsyncMock(return_value="sid-1"),
    )

    frames = await _collect(
        streaming.replay_buffered_stream(
            _Request(), thread_id="thread-1", stream_id="sid-1"
        )
    )

    assert frames == [_frame(1).frame, _frame(2).frame, _frame(3, "done").frame]


# ---------------------------------------------------------------------------
# L3 — the fast-path LLM iterator must be closed, and a failed persist logged
# ---------------------------------------------------------------------------


class _TrackedAsyncGen:
    """Minimal LLM ``astream`` stand-in: tracks whether ``aclose`` ran."""

    def __init__(self, items: list[Any]) -> None:
        self._items = list(items)
        self.aclose_called = False

    def __aiter__(self) -> Any:
        return self

    async def __anext__(self) -> Any:
        if not self._items:
            # An LLM stream that is still open when the caller walks away —
            # the only way out is an explicit close, never a StopAsyncIteration.
            await asyncio.Event().wait()
        return self._items.pop(0)

    async def aclose(self) -> None:
        self.aclose_called = True


class _StubLLM:
    def __init__(self, gen: Any) -> None:
        self._gen = gen

    def astream(self, _messages: Any, config: Any = None) -> Any:
        return self._gen


async def test_fast_path_closes_llm_iterator_on_early_generator_close() -> None:
    """Closing the fast-path generator mid-stream (client disconnect) must
    close the underlying LLM astream iterator, not abandon it suspended."""
    gen = _TrackedAsyncGen(["chunk-1"])
    llm = _StubLLM(gen)

    chunks = fast_path.stream_fast_path_chunks(
        llm=llm, messages=[], persist_user=AsyncMock(return_value=None)
    )
    first = await anext(chunks)
    assert first == "chunk-1"

    await chunks.aclose()

    assert gen.aclose_called, "LLM astream iterator.aclose() was never awaited"


class _ImmediateErrorGen:
    """LLM stream whose very first pull fails outright (no chunks emitted)."""

    def __aiter__(self) -> Any:
        return self

    async def __anext__(self) -> Any:
        raise RuntimeError("model errored")

    async def aclose(self) -> None:
        return None


async def test_fast_path_logs_persist_failure_instead_of_swallowing_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When the model fails before the belated cleanup-path persist runs, a
    failure in that persist must be logged, not dropped by a bare
    ``contextlib.suppress(Exception)``."""
    persist_started = asyncio.Event()
    persist_may_fail = asyncio.Event()

    async def failing_persist_user() -> None:
        persist_started.set()
        await persist_may_fail.wait()
        raise RuntimeError("db write failed")

    llm = _StubLLM(_ImmediateErrorGen())
    chunks = fast_path.stream_fast_path_chunks(
        llm=llm, messages=[], persist_user=failing_persist_user
    )

    caplog.set_level(logging.ERROR, logger=fast_path.__name__)

    call = asyncio.ensure_future(anext(chunks))
    await asyncio.wait_for(persist_started.wait(), timeout=1)
    persist_may_fail.set()

    with pytest.raises(RuntimeError, match="model errored"):
        await call

    assert any(
        record.levelno >= logging.ERROR and "persist" in record.getMessage().lower()
        for record in caplog.records
    ), f"expected an ERROR log for the failed persist, got {caplog.records!r}"


# ---------------------------------------------------------------------------
# L14 — stream_buffer.append must pipeline rpush/ltrim/expire
# ---------------------------------------------------------------------------


class _RecordingPipeline:
    def __init__(self) -> None:
        self.queued: list[tuple] = []
        self.executed = False

    async def __aenter__(self) -> Any:
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False

    def rpush(self, *args: Any, **kwargs: Any) -> Any:
        self.queued.append(("rpush", args, kwargs))

    def ltrim(self, *args: Any, **kwargs: Any) -> Any:
        self.queued.append(("ltrim", args, kwargs))

    def expire(self, *args: Any, **kwargs: Any) -> Any:
        self.queued.append(("expire", args, kwargs))

    async def execute(self) -> None:
        self.executed = True


class _CallRecordingRedis:
    """Distinguishes top-level (unbatched) calls from pipelined ones."""

    def __init__(self) -> None:
        self.top_level_calls: list[str] = []
        self.pipelines: list[_RecordingPipeline] = []

    async def rpush(self, *_args: Any, **_kwargs: Any) -> Any:
        self.top_level_calls.append("rpush")

    async def ltrim(self, *_args: Any, **_kwargs: Any) -> Any:
        self.top_level_calls.append("ltrim")

    async def expire(self, *_args: Any, **_kwargs: Any) -> Any:
        self.top_level_calls.append("expire")

    def pipeline(self, transaction: bool = True) -> Any:
        pipe = _RecordingPipeline()
        self.pipelines.append(pipe)
        return pipe


async def test_append_pipelines_rpush_ltrim_expire(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A connection drop between separate rpush/ltrim/expire awaits can leave
    a no-TTL key that never expires; they must land as one pipeline."""
    redis = _CallRecordingRedis()

    async def fake_get_redis() -> Any:
        return redis

    monkeypatch.setattr(stream_buffer, "get_redis", fake_get_redis)

    await stream_buffer.append("sid-1", 1, "frame-a")

    assert redis.top_level_calls == [], (
        "rpush/ltrim/expire ran as separate top-level round trips instead of "
        f"one pipeline: {redis.top_level_calls!r}"
    )
    assert len(redis.pipelines) == 1
    pipe = redis.pipelines[0]
    assert pipe.executed
    assert [op for op, _args, _kwargs in pipe.queued] == ["rpush", "ltrim", "expire"]


# ---------------------------------------------------------------------------
# L15 — stream_buffer.read_after should use a start_index hint, with a
# trim-invalidation fallback that never skips frames
# ---------------------------------------------------------------------------


class _ListRedis:
    """Records the exact (start, stop) each lrange call requested."""

    def __init__(self, items: list[str]) -> None:
        self.items = items
        self.lrange_calls: list[tuple[int, int]] = []

    async def lrange(self, _key: str, start: int, stop: int) -> list[str]:
        self.lrange_calls.append((start, stop))
        if stop == -1:
            return self.items[start:]
        return self.items[start : stop + 1]


def _entry(seq: int) -> str:
    return json.dumps({"seq": seq, "frame": f"frame-{seq}"})


async def test_read_after_uses_start_index_hint_on_repeat_poll(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The second poll of an unchanged buffer should slice from the hint
    instead of re-fetching and re-parsing the entire buffer again."""
    redis = _ListRedis([_entry(1), _entry(2), _entry(3)])

    async def fake_get_redis() -> Any:
        return redis

    monkeypatch.setattr(stream_buffer, "get_redis", fake_get_redis)

    first = await stream_buffer.read_after("sid-1", 0, start_index=0)
    assert [f.seq for f in first] == [1, 2, 3]
    assert redis.lrange_calls[-1] == (0, -1)

    redis.items.append(_entry(4))
    second = await stream_buffer.read_after("sid-1", 3, start_index=3)

    assert [f.seq for f in second] == [4]
    start, _stop = redis.lrange_calls[-1]
    assert (
        start > 0
    ), f"expected a hinted (non-zero) slice, got {redis.lrange_calls[-1]!r}"


async def test_read_after_falls_back_to_full_scan_after_trim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Risk case: an LTRIM between polls shifts every list index, so a stale
    start_index must not be trusted — the probe must catch the misalignment
    and re-scan, or a resumed replay silently skips frames past the trim."""
    redis = _ListRedis([_entry(1), _entry(2), _entry(3)])

    async def fake_get_redis() -> Any:
        return redis

    monkeypatch.setattr(stream_buffer, "get_redis", fake_get_redis)

    first = await stream_buffer.read_after("sid-1", 0, start_index=0)
    assert [f.seq for f in first] == [1, 2, 3]

    # LTRIM drops the oldest frame; a new one lands. The caller's hint
    # (start_index=3, from consuming 3 frames) no longer aligns with "index
    # 3 == the frame right after seq 3" in the post-trim list.
    redis.items = redis.items[1:] + [_entry(4)]

    second = await stream_buffer.read_after("sid-1", 3, start_index=3)

    assert [f.seq for f in second] == [
        4
    ], "trim-invalidated hint must fall back to a full scan, not skip frames"
