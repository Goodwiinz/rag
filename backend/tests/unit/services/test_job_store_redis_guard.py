"""Regression tests for the L2 (Redis) monotonic write guard (audit fix #5).

``_redis_write_if_newer`` must skip a write when Redis already holds a strictly
newer job state, so a delayed fire-and-forget write cannot stomp a job that has
since completed.
"""

from __future__ import annotations

import json

import pytest


class _FakeRedis:
    """Minimal async Redis stub backing a single job key."""

    def __init__(self, existing=None):
        self.value = json.dumps(existing) if existing is not None else None
        self.setex_calls = []

    async def get(self, key):
        return self.value

    async def setex(self, key, ttl, payload):
        self.setex_calls.append((key, ttl, payload))
        self.value = payload


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_write_skipped_when_existing_is_newer():
    """A stale (older) write must not overwrite a newer stored state."""
    from src.services.agent.job_store import _redis_write_if_newer

    redis = _FakeRedis(existing={"status": "completed", "created_at": 100.0})
    await _redis_write_if_newer(
        redis, "job-1", {"status": "running", "created_at": 50.0}
    )
    assert redis.setex_calls == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_write_applied_when_newer():
    """A newer write proceeds and replaces the older stored state."""
    from src.services.agent.job_store import _redis_write_if_newer

    redis = _FakeRedis(existing={"status": "running", "created_at": 50.0})
    await _redis_write_if_newer(
        redis, "job-1", {"status": "completed", "created_at": 100.0}
    )
    assert len(redis.setex_calls) == 1
    assert json.loads(redis.setex_calls[0][2])["status"] == "completed"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_write_applied_when_absent():
    """First write for a job (no existing value) proceeds."""
    from src.services.agent.job_store import _redis_write_if_newer

    redis = _FakeRedis(existing=None)
    await _redis_write_if_newer(
        redis, "job-1", {"status": "running", "created_at": 1.0}
    )
    assert len(redis.setex_calls) == 1
