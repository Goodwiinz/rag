"""GET /agent/jobs/{id} — Postgres fallback on Redis miss (audit X1/D7).

The job record used to live only in Redis (TTL 1h): after a failover every
poller got a hard 404 and the run became untrackable. The endpoint now falls
back to the durable ``agent_runs`` projection — status + error survive, the
poller can stop cleanly — while a genuine unknown job (or another tenant's
job) still 404s.

Calls the endpoint function directly with the store layers patched out, the
same style as the other agent job unit tests.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from src.api.agent.execute import JobStatusResponse, get_job_status
from src.shared.enums import JobStatus

pytestmark = pytest.mark.unit


def _user(org=None):
    return SimpleNamespace(id=uuid.uuid4(), organization_id=org or uuid.uuid4())


def _patch_stores(l1_job=None, redis_job=None):
    """Patch the L1 and Redis read layers of the poll endpoint.

    The endpoint reads L1 first and, for non-terminal (or missing) records,
    revalidates through ``get_job_fresh`` (Redis-first, L1 fallback — P1.3
    cross-process freshness). The fake mirrors that contract: the Redis copy
    when present, else the L1 record.
    """
    return (
        patch("src.api.agent.execute._get_job", return_value=l1_job),
        patch(
            "src.services.agent.job_store.get_job_fresh",
            new=AsyncMock(return_value=redis_job if redis_job is not None else l1_job),
        ),
    )


@pytest.mark.asyncio
async def test_redis_miss_falls_back_to_agent_runs_projection():
    user = _user()
    run = SimpleNamespace(status="completed", error=None)
    p1, p2 = _patch_stores()
    with (
        p1,
        p2,
        patch(
            "src.services.agent.agent_run_service.get_run_fallback",
            new=AsyncMock(return_value=run),
        ) as fallback,
    ):
        resp = await get_job_status(job_id=str(uuid.uuid4()), current_user=user)

    assert isinstance(resp, JobStatusResponse)
    assert resp.status is JobStatus.COMPLETED
    # Tenancy must flow into the projection read (org + user).
    kwargs = fallback.call_args.kwargs
    assert kwargs["organization_id"] == user.organization_id
    assert kwargs["user_id"] == user.id


@pytest.mark.asyncio
async def test_redis_miss_and_projection_miss_is_404():
    p1, p2 = _patch_stores()
    with (
        p1,
        p2,
        patch(
            "src.services.agent.agent_run_service.get_run_fallback",
            new=AsyncMock(return_value=None),
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            await get_job_status(job_id=str(uuid.uuid4()), current_user=_user())
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_fallback_normalizes_legacy_error_status():
    """A projection row written by a pre-collapse release reads as FAILED."""
    run = SimpleNamespace(status="error", error="boom")
    p1, p2 = _patch_stores()
    with (
        p1,
        p2,
        patch(
            "src.services.agent.agent_run_service.get_run_fallback",
            new=AsyncMock(return_value=run),
        ),
    ):
        resp = await get_job_status(job_id=str(uuid.uuid4()), current_user=_user())
    assert resp.status is JobStatus.FAILED
    assert resp.error == "boom"


@pytest.mark.asyncio
async def test_redis_hit_never_touches_postgres():
    user = _user()
    job = {
        "status": "running",
        "user_id": str(user.id),
        "tool_executions": [],
    }
    p1, p2 = _patch_stores(l1_job=job)
    with (
        p1,
        p2,
        patch(
            "src.services.agent.agent_run_service.get_run_fallback",
            new=AsyncMock(return_value=None),
        ) as fallback,
    ):
        resp = await get_job_status(job_id=str(uuid.uuid4()), current_user=user)
    assert resp.status is JobStatus.RUNNING
    fallback.assert_not_awaited()


@pytest.mark.asyncio
async def test_redis_hit_with_legacy_error_status_normalizes():
    """In-Redis records written pre-collapse still poll back as FAILED."""
    user = _user()
    job = {"status": "error", "error": "old pod", "user_id": str(user.id)}
    p1, p2 = _patch_stores(l1_job=job)
    with p1, p2:
        resp = await get_job_status(job_id=str(uuid.uuid4()), current_user=user)
    assert resp.status is JobStatus.FAILED
    assert resp.error == "old pod"


@pytest.mark.asyncio
async def test_owner_mismatch_still_404s_without_fallback_leak():
    """A Redis hit owned by someone else must 404 — and must NOT consult the
    projection (which would only be reachable via the caller's own tenancy)."""
    job = {"status": "completed", "user_id": "someone-else"}
    p1, p2 = _patch_stores(l1_job=job)
    with (
        p1,
        p2,
        patch(
            "src.services.agent.agent_run_service.get_run_fallback",
            new=AsyncMock(return_value=None),
        ) as fallback,
    ):
        with pytest.raises(HTTPException) as exc:
            await get_job_status(job_id=str(uuid.uuid4()), current_user=_user())
    assert exc.value.status_code == 404
    fallback.assert_not_awaited()
