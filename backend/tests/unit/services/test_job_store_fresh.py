"""get_job_fresh — Redis-first job read for cross-process freshness (P1.3).

In Celery dispatch mode the run's status writes come from the worker process,
so an API pod's L1 seed goes permanently stale (a "running" entry would spin
the poller and 409 every confirm until the 1h TTL). get_job_fresh consults
Redis first, folds the result into L1 under the monotonic guard, and degrades
to the plain L1 read when Redis is unavailable.
"""

import json
import time
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from src.services.agent import job_store as js

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _clear_l1():
    js._l1.clear()
    yield
    js._l1.clear()


def _fake_redis(record: dict | None):
    client = AsyncMock()
    client.get = AsyncMock(
        return_value=json.dumps(record, default=str) if record is not None else None
    )
    return client


async def test_redis_copy_wins_over_stale_l1_and_reseeds():
    job_id = str(uuid.uuid4())
    js._l1[job_id] = {"status": "running", "created_at": time.time() - 100}
    newer = {"status": "completed", "created_at": time.time()}

    with patch.object(js, "_get_redis", AsyncMock(return_value=_fake_redis(newer))):
        job = await js.get_job_fresh(job_id)

    assert job["status"] == "completed"
    assert js._l1[job_id]["status"] == "completed"  # L1 reseeded


async def test_newer_local_l1_write_is_not_clobbered():
    """A delayed Redis copy (older created_at) must not stomp an in-flight
    newer local write — the monotonic guard applies both ways."""
    job_id = str(uuid.uuid4())
    js._l1[job_id] = {"status": "failed", "created_at": time.time()}
    older = {"status": "running", "created_at": time.time() - 100}

    with patch.object(js, "_get_redis", AsyncMock(return_value=_fake_redis(older))):
        job = await js.get_job_fresh(job_id)

    assert job["status"] == "failed"
    assert js._l1[job_id]["status"] == "failed"


async def test_redis_miss_falls_back_to_l1():
    job_id = str(uuid.uuid4())
    js._l1[job_id] = {"status": "running", "created_at": time.time()}
    with patch.object(js, "_get_redis", AsyncMock(return_value=_fake_redis(None))):
        job = await js.get_job_fresh(job_id)
    assert job["status"] == "running"


async def test_redis_unavailable_degrades_to_l1():
    job_id = str(uuid.uuid4())
    js._l1[job_id] = {"status": "running", "created_at": time.time()}
    with patch.object(js, "_get_redis", AsyncMock(return_value=None)):
        job = await js.get_job_fresh(job_id)
    assert job["status"] == "running"


async def test_both_layers_missing_is_none():
    with patch.object(js, "_get_redis", AsyncMock(return_value=None)):
        assert await js.get_job_fresh(str(uuid.uuid4())) is None


async def test_expired_l1_record_is_dropped():
    job_id = str(uuid.uuid4())
    js._l1[job_id] = {"status": "running", "created_at": time.time() - 4000}
    with patch.object(js, "_get_redis", AsyncMock(return_value=None)):
        assert await js.get_job_fresh(job_id) is None
    assert job_id not in js._l1


# ---------------------------------------------------------------------------
# Poll endpoint: a stale L1 "running" record must not mask the worker's
# terminal write (the exact celery-mode failure this function exists for).
# ---------------------------------------------------------------------------


async def test_poll_endpoint_sees_worker_terminal_write_through_stale_l1():
    from types import SimpleNamespace

    from src.api.agent.execute import get_job_status
    from src.shared.enums import JobStatus

    user = SimpleNamespace(id=uuid.uuid4(), organization_id=uuid.uuid4())
    job_id = str(uuid.uuid4())
    # Stale local seed from dispatch time…
    js._l1[job_id] = {
        "status": "running",
        "user_id": str(user.id),
        "created_at": time.time() - 60,
    }
    # …while the worker already completed the run in Redis.
    done = {
        "status": "completed",
        "user_id": str(user.id),
        "result": None,
        "created_at": time.time(),
    }
    with patch.object(js, "_get_redis", AsyncMock(return_value=_fake_redis(done))):
        resp = await get_job_status(job_id=job_id, current_user=user)

    assert resp.status is JobStatus.COMPLETED


async def test_poll_endpoint_trusts_terminal_l1_without_redis_roundtrip():
    from types import SimpleNamespace

    from src.api.agent.execute import get_job_status
    from src.shared.enums import JobStatus

    user = SimpleNamespace(id=uuid.uuid4(), organization_id=uuid.uuid4())
    job_id = str(uuid.uuid4())
    js._l1[job_id] = {
        "status": "completed",
        "user_id": str(user.id),
        "created_at": time.time(),
    }
    get_redis = AsyncMock(return_value=None)
    with patch.object(js, "_get_redis", get_redis):
        resp = await get_job_status(job_id=job_id, current_user=user)

    assert resp.status is JobStatus.COMPLETED
    get_redis.assert_not_awaited()  # terminal L1 records are immutable
