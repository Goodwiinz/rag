"""Tests for the Redis-backed SSE stream buffer primitive."""

from __future__ import annotations

import json

import pytest

from src.services.agent import stream_buffer


class _FakeRedis:
    """Minimal async Redis stub: strings + lists, TTL ignored."""

    def __init__(self):
        self.store: dict = {}

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
async def test_finish_stream_with_stale_sid_keeps_newer_pointer(fake_redis):
    old_sid = await stream_buffer.start_stream("thread-1")
    new_sid = await stream_buffer.start_stream("thread-1")

    await stream_buffer.finish_stream("thread-1", old_sid)
    assert await stream_buffer.active_stream_id("thread-1") == new_sid


@pytest.mark.unit
@pytest.mark.asyncio
async def test_read_after_unknown_sid_returns_empty(fake_redis):
    assert await stream_buffer.read_after("nope", 0) == []
