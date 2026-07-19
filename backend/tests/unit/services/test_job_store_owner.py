"""Job-store owner carry-forward.

``set_job`` REPLACES the job record. Terminal status writes used to omit
``user_id``, which dropped the owner from the record; combined with the old
fail-open GET guard this leaked completed job results across users. These
tests pin the carry-forward in both write paths (async ``set_job`` and the
sync ``_set_job`` wrapper) so an ownerless overwrite can never orphan a job.
"""

from __future__ import annotations

import pytest

from src.services.agent import job_store


@pytest.fixture(autouse=True)
def _clean_l1():
    with job_store._l1_lock:
        job_store._l1.clear()
    yield
    with job_store._l1_lock:
        job_store._l1.clear()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_set_job_preserves_user_id_on_overwrite(monkeypatch):
    monkeypatch.setattr(job_store, "_get_redis", _no_redis)
    await job_store.set_job("j1", {"status": "running", "user_id": "u1"})
    await job_store.set_job("j1", {"status": "completed", "result": {}})

    job = await job_store.get_job("j1")
    assert job["status"] == "completed"
    assert job["user_id"] == "u1"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_set_job_explicit_user_id_wins(monkeypatch):
    monkeypatch.setattr(job_store, "_get_redis", _no_redis)
    await job_store.set_job("j1", {"status": "running", "user_id": "u1"})
    await job_store.set_job("j1", {"status": "failed", "user_id": "u1", "error": "x"})

    job = await job_store.get_job("j1")
    assert job["user_id"] == "u1"


@pytest.mark.unit
def test_sync_set_job_preserves_user_id_on_overwrite():
    from src.api.agent.jobs import _get_job, _set_job

    _set_job("j2", {"status": "running", "user_id": "u2"})
    _set_job("j2", {"status": "completed", "result": {}})

    job = _get_job("j2")
    assert job["status"] == "completed"
    assert job["user_id"] == "u2"


async def _no_redis():
    return None
