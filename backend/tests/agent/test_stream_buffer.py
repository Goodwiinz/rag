"""Tests for the Redis-backed SSE stream buffer primitive."""

from __future__ import annotations

import json

import pytest

from src.services.agent import stream_buffer


class _FakePipeline:
    """WATCH/MULTI stub: snapshots watched keys, raises WatchError on drift."""

    def __init__(self, redis):
        self.redis = redis
        self.watched: dict = {}
        self.queued_deletes: list = []
        self.queued_sets: list = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def watch(self, key):
        self.watched[key] = self.redis.store.get(key)

    async def get(self, key):
        return self.redis.store.get(key)

    def multi(self):
        if self.redis.on_multi is not None:
            self.redis.on_multi()

    def delete(self, key):
        self.queued_deletes.append(key)

    def set(self, key, value, ex=None):
        self.queued_sets.append((key, value))

    async def execute(self):
        from redis.exceptions import WatchError

        for key, snapshot in self.watched.items():
            if self.redis.store.get(key) != snapshot:
                raise WatchError("watched key changed")
        for key in self.queued_deletes:
            self.redis.store.pop(key, None)
        for key, value in self.queued_sets:
            self.redis.store[key] = value

    async def reset(self):
        self.watched.clear()
        self.queued_deletes.clear()
        self.queued_sets.clear()


class _FakeRedis:
    """Minimal async Redis stub: strings + lists, TTL ignored."""

    def __init__(self):
        self.store: dict = {}
        self.on_multi = None  # test hook: interleave a write mid-transaction

    def pipeline(self, transaction=True):
        return _FakePipeline(self)

    async def ltrim(self, key, start, stop):
        if key in self.store:
            self.store[key] = self.store[key][start:]

    async def set(self, key, value, ex=None):
        self.store[key] = value

    async def get(self, key):
        return self.store.get(key)

    async def delete(self, key):
        self.store.pop(key, None)

    async def rpush(self, key, value):
        self.store.setdefault(key, []).append(value)

    async def expire(self, key, ttl):
        pass

    async def lrange(self, key, start, stop):
        return self.store.get(key, [])


@pytest.fixture
def fake_redis(monkeypatch):
    r = _FakeRedis()

    async def _get():
        return r

    monkeypatch.setattr(stream_buffer, "get_redis", _get)
    return r


@pytest.mark.unit
@pytest.mark.asyncio
async def test_append_and_read_after_filters_by_seq(fake_redis):
    sid = await stream_buffer.start_stream("thread-1")
    await stream_buffer.append(sid, 1, "frame-a")
    await stream_buffer.append(sid, 2, "frame-b")
    await stream_buffer.append(sid, 3, "frame-c")

    frames = await stream_buffer.read_after(sid, 1)
    assert [(f.seq, f.frame) for f in frames] == [(2, "frame-b"), (3, "frame-c")]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_active_pointer_lifecycle(fake_redis):
    sid = await stream_buffer.start_stream("thread-1")
    assert await stream_buffer.active_stream_id("thread-1") == sid

    await stream_buffer.finish_stream("thread-1", sid)
    assert await stream_buffer.active_stream_id("thread-1") is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_start_stream_records_run_and_thread_mappings(fake_redis):
    sid = await stream_buffer.start_stream("thread-1", run_id="run-1")

    assert await stream_buffer.stream_id_for_run("run-1") == sid
    assert await stream_buffer.thread_id_for_stream(sid) == "thread-1"

    await stream_buffer.finish_stream("thread-1", sid)
    assert await stream_buffer.stream_id_for_run("run-1") == sid
    assert await stream_buffer.thread_id_for_stream(sid) == "thread-1"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_finish_stream_with_stale_sid_keeps_newer_pointer(fake_redis):
    old_sid = await stream_buffer.start_stream("thread-1")
    new_sid = await stream_buffer.start_stream("thread-1")

    await stream_buffer.finish_stream("thread-1", old_sid)
    assert await stream_buffer.active_stream_id("thread-1") == new_sid


@pytest.mark.unit
@pytest.mark.asyncio
async def test_finish_stream_race_mid_transaction_keeps_new_pointer(fake_redis):
    """A start_stream landing between WATCH/GET and EXEC must survive."""
    sid = await stream_buffer.start_stream("thread-1")
    key = "agent:stream:active:thread-1"

    def interleave():
        fake_redis.store[key] = "newer-sid"  # concurrent start_stream

    fake_redis.on_multi = interleave
    await stream_buffer.finish_stream("thread-1", sid)
    assert fake_redis.store[key] == "newer-sid"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_append_caps_buffer_at_5000(fake_redis):
    sid = await stream_buffer.start_stream("thread-1")
    key = f"agent:stream:{sid}"
    fake_redis.store[key] = [json.dumps({"seq": i, "frame": "x"}) for i in range(5000)]
    await stream_buffer.append(sid, 5000, "last")
    frames = await stream_buffer.read_after(sid, -1)
    assert len(frames) == 5000
    assert frames[0].seq == 1  # oldest frame dropped
    assert frames[-1].frame == "last"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_read_after_unknown_sid_returns_empty(fake_redis):
    assert await stream_buffer.read_after("nope", 0) == []
