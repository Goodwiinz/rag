"""Regression test for the L1 job-store cleanup throttle (audit fix #9).

``set_job`` previously ran the O(n) ``_l1_cleanup`` under ``_l1_lock`` on
every write; it now uses the throttled ``_l1_maybe_cleanup`` (already used by
``get_job``), so the full scan runs at most once per throttle window.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


@pytest.mark.unit
@pytest.mark.asyncio
async def test_set_job_uses_throttled_cleanup(monkeypatch):
    """Many writes in one window must not each trigger the full L1 cleanup."""
    import src.services.agent.job_store as js

    # No Redis dependency — isolate the L1 path.
    monkeypatch.setattr(js, "set_job_redis_only", AsyncMock())

    calls = {"n": 0}
    real_cleanup = js._l1_cleanup

    def _counting_cleanup():
        calls["n"] += 1
        real_cleanup()

    monkeypatch.setattr(js, "_l1_cleanup", _counting_cleanup)
    # Fresh throttle window so the 60s gate has just elapsed.
    monkeypatch.setattr(js, "_LAST_L1_CLEANUP", js.time.time())

    for i in range(50):
        await js.set_job(f"job-{i}", {"status": "running"})

    # Throttled: not one full O(n) cleanup per write within the <60s window.
    assert calls["n"] <= 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_job_prefers_fresher_redis_over_stale_l1(monkeypatch):
    """Redis is cross-worker truth: a stale local L1 entry must not shadow a
    newer Redis value (codex audit on #1405 — resume/failure paths acted on
    stale L1 reads after another worker advanced the job)."""
    import json

    from src.services.agent import job_store

    stale = {"status": "running", "created_at": 1e12, "_seq": 1}
    fresh = {"status": "cancelled", "created_at": 1e12, "_seq": 2}

    monkeypatch.setattr(job_store, "_l1", {"job-1": dict(stale)})
    redis_client = AsyncMock()
    redis_client.get = AsyncMock(return_value=json.dumps(fresh))
    monkeypatch.setattr(job_store, "_get_redis", AsyncMock(return_value=redis_client))
    # created_at is a future timestamp so the TTL check cannot expire the entry.
    monkeypatch.setattr(job_store.time, "time", lambda: 1e12)

    result = await job_store.get_job("job-1")

    assert result is not None and result["status"] == "cancelled"
    assert job_store._l1["job-1"]["_seq"] == 2  # L1 reseeded from Redis


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_job_keeps_newer_local_writethrough(monkeypatch):
    """The one legitimate L1 win: this worker's write-through is newer than
    the Redis read (its async projection hasn't landed) — newer seq wins."""
    import json

    from src.services.agent import job_store

    local = {"status": "completed", "created_at": 1e12, "_seq": 3}
    lagging = {"status": "running", "created_at": 1e12, "_seq": 2}

    monkeypatch.setattr(job_store, "_l1", {"job-1": dict(local)})
    redis_client = AsyncMock()
    redis_client.get = AsyncMock(return_value=json.dumps(lagging))
    monkeypatch.setattr(job_store, "_get_redis", AsyncMock(return_value=redis_client))
    monkeypatch.setattr(job_store.time, "time", lambda: 1e12)

    result = await job_store.get_job("job-1")

    assert result is not None and result["status"] == "completed"
