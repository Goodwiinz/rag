"""agent_run_service — the durable Postgres projection of agent jobs.

Covers the audit P1.2 contract on a throwaway sqlite engine (only the
``agent_runs`` table is created — the shared Base carries postgres-only
types elsewhere, so never ``create_all`` the full metadata):

- upsert: create, status update, legacy "error" normalization, tenancy
  backfill-only semantics, absorbing terminal states, ownerless-insert skip
- get_run: mandatory organization_id + user_id tenancy filter (null-safe)
- claim/release lease: atomic compare-and-claim, re-entrant renewal,
  expired-lease takeover
- list_stale_runs: sweeper candidate listing (non-terminal, stale, unleased)
- record_job_status: the log-and-continue write-through entry point
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.models.agent_run import AgentRun
from src.services.agent import agent_run_service as svc
from src.shared.enums import JobStatus

pytestmark = pytest.mark.unit

ORG_A = uuid.uuid4()
ORG_B = uuid.uuid4()
USER_A = uuid.uuid4()
USER_B = uuid.uuid4()


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(AgentRun.__table__.create)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


def _job_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# upsert_run
# ---------------------------------------------------------------------------


async def test_upsert_creates_then_updates(session_factory):
    job_id = _job_id()
    async with session_factory() as db:
        run = await svc.upsert_run(
            db,
            job_id=job_id,
            status=JobStatus.RUNNING,
            organization_id=str(ORG_A),
            user_id=str(USER_A),
            thread_id="t-1",
        )
        assert run is not None
        assert run.status == "running"
        assert run.organization_id == ORG_A
        assert run.user_id == USER_A

        run = await svc.upsert_run(db, job_id=job_id, status=JobStatus.COMPLETED)
        assert run.status == "completed"
        # Tenancy survives a replace-style write that omitted it.
        assert run.organization_id == ORG_A
        assert run.thread_id == "t-1"


async def test_upsert_normalizes_legacy_error_alias(session_factory):
    """A pre-collapse writer's "error" is stored as canonical "failed"."""
    job_id = _job_id()
    async with session_factory() as db:
        run = await svc.upsert_run(
            db,
            job_id=job_id,
            status="error",
            user_id=str(USER_A),
            error="boom",
        )
        assert run.status == "failed"
        assert run.error == "boom"


async def test_upsert_drops_unknown_status(session_factory):
    async with session_factory() as db:
        assert (
            await svc.upsert_run(
                db, job_id=_job_id(), status="exploded", user_id=str(USER_A)
            )
            is None
        )


async def test_upsert_skips_ownerless_insert(session_factory):
    """No row + no user_id → skip (an ownerless row is unreadable anyway)."""
    job_id = _job_id()
    async with session_factory() as db:
        assert await svc.upsert_run(db, job_id=job_id, status=JobStatus.RUNNING) is None
        assert await db.get(AgentRun, job_id) is None


async def test_terminal_states_are_absorbing(session_factory):
    """A delayed non-terminal projection must not resurrect a finished run."""
    job_id = _job_id()
    async with session_factory() as db:
        await svc.upsert_run(
            db, job_id=job_id, status=JobStatus.COMPLETED, user_id=str(USER_A)
        )
        run = await svc.upsert_run(db, job_id=job_id, status=JobStatus.RUNNING)
        assert run.status == "completed"

        # Non-terminal ↔ non-terminal stays free-form (confirm / re-park).
        job2 = _job_id()
        await svc.upsert_run(
            db,
            job_id=job2,
            status=JobStatus.AWAITING_CONFIRMATION,
            user_id=str(USER_A),
        )
        run2 = await svc.upsert_run(db, job_id=job2, status=JobStatus.RUNNING)
        assert run2.status == "running"


@pytest.mark.parametrize(
    "status",
    [
        JobStatus.QUEUED,
        JobStatus.RUNNING,
        JobStatus.AWAITING_CONFIRMATION,
        JobStatus.STOPPING,
    ],
)
def test_non_terminal_run_statuses(status: JobStatus) -> None:
    assert status.is_terminal is False


@pytest.mark.parametrize(
    "status", [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]
)
def test_terminal_run_statuses(status: JobStatus) -> None:
    assert status.is_terminal is True


async def test_terminal_absorbs_stopping(session_factory):
    """A delayed ``stopping`` projection must not resurrect a cancelled run."""
    job_id = _job_id()
    async with session_factory() as db:
        await svc.upsert_run(
            db, job_id=job_id, status=JobStatus.CANCELLED, user_id=str(USER_A)
        )
        run = await svc.upsert_run(db, job_id=job_id, status=JobStatus.STOPPING)
        assert run.status == "cancelled"


async def test_queued_to_running_transition(session_factory):
    job_id = _job_id()
    async with session_factory() as db:
        await svc.upsert_run(
            db, job_id=job_id, status=JobStatus.QUEUED, user_id=str(USER_A)
        )
        run = await svc.upsert_run(db, job_id=job_id, status=JobStatus.RUNNING)
        assert run.status == "running"


async def test_upsert_backfills_but_never_overwrites_tenancy(session_factory):
    job_id = _job_id()
    async with session_factory() as db:
        await svc.upsert_run(
            db, job_id=job_id, status=JobStatus.RUNNING, user_id=str(USER_A)
        )
        run = await svc.upsert_run(
            db,
            job_id=job_id,
            status=JobStatus.RUNNING,
            organization_id=str(ORG_A),  # backfills NULL org
            user_id=str(USER_B),  # must NOT overwrite existing owner
        )
        assert run.organization_id == ORG_A
        assert run.user_id == USER_A


# ---------------------------------------------------------------------------
# get_run — tenancy
# ---------------------------------------------------------------------------


async def test_get_run_filters_org_and_user(session_factory):
    job_id = _job_id()
    async with session_factory() as db:
        await svc.upsert_run(
            db,
            job_id=job_id,
            status=JobStatus.RUNNING,
            organization_id=ORG_A,
            user_id=USER_A,
        )

        found = await svc.get_run(db, job_id, organization_id=ORG_A, user_id=USER_A)
        assert found is not None and found.job_id == job_id

        # Wrong org, wrong user, or an org-less caller → fail closed.
        assert (
            await svc.get_run(db, job_id, organization_id=ORG_B, user_id=USER_A) is None
        )
        assert (
            await svc.get_run(db, job_id, organization_id=ORG_A, user_id=USER_B) is None
        )
        assert (
            await svc.get_run(db, job_id, organization_id=None, user_id=USER_A) is None
        )


async def test_get_run_orgless_caller_matches_only_orgless_row(session_factory):
    job_id = _job_id()
    async with session_factory() as db:
        await svc.upsert_run(
            db, job_id=job_id, status=JobStatus.RUNNING, user_id=USER_A
        )
        found = await svc.get_run(db, job_id, organization_id=None, user_id=USER_A)
        assert found is not None
        assert (
            await svc.get_run(db, job_id, organization_id=ORG_A, user_id=USER_A) is None
        )


# ---------------------------------------------------------------------------
# claim_lease / release_lease / list_stale_runs (sweeper API)
# ---------------------------------------------------------------------------


async def test_claim_lease_is_exclusive_and_reentrant(session_factory):
    job_id = _job_id()
    async with session_factory() as db:
        await svc.upsert_run(
            db, job_id=job_id, status=JobStatus.RUNNING, user_id=USER_A
        )

        assert await svc.claim_lease(db, job_id, lease_owner="sweeper-1")
        # A rival cannot steal a live lease…
        assert not await svc.claim_lease(db, job_id, lease_owner="sweeper-2")
        # …but the holder can renew (heartbeat).
        assert await svc.claim_lease(db, job_id, lease_owner="sweeper-1")


async def test_claim_lease_takes_over_expired_lease(session_factory):
    job_id = _job_id()
    async with session_factory() as db:
        await svc.upsert_run(
            db, job_id=job_id, status=JobStatus.RUNNING, user_id=USER_A
        )
        # Lease that expired in the past.
        assert await svc.claim_lease(
            db, job_id, lease_owner="dead-worker", lease_seconds=-5
        )
        assert await svc.claim_lease(db, job_id, lease_owner="sweeper-2")
        run = await db.get(AgentRun, job_id)
        assert run.lease_owner == "sweeper-2"


async def test_claim_lease_missing_row_is_false(session_factory):
    async with session_factory() as db:
        assert not await svc.claim_lease(db, _job_id(), lease_owner="s")


async def test_release_lease_only_for_holder(session_factory):
    job_id = _job_id()
    async with session_factory() as db:
        await svc.upsert_run(
            db, job_id=job_id, status=JobStatus.RUNNING, user_id=USER_A
        )
        await svc.claim_lease(db, job_id, lease_owner="sweeper-1")

        assert not await svc.release_lease(db, job_id, lease_owner="intruder")
        assert await svc.release_lease(db, job_id, lease_owner="sweeper-1")
        run = await db.get(AgentRun, job_id)
        assert run.lease_owner is None and run.lease_expires_at is None


async def test_list_stale_runs_selects_sweepable_candidates(session_factory):
    now = datetime.now(timezone.utc)
    async with session_factory() as db:
        stale_running = _job_id()
        await svc.upsert_run(
            db, job_id=stale_running, status=JobStatus.RUNNING, user_id=USER_A
        )
        terminal = _job_id()
        await svc.upsert_run(
            db, job_id=terminal, status=JobStatus.COMPLETED, user_id=USER_A
        )
        leased = _job_id()
        await svc.upsert_run(
            db, job_id=leased, status=JobStatus.RUNNING, user_id=USER_A
        )
        await svc.claim_lease(db, leased, lease_owner="other", lease_seconds=600)

        # Everything above was just written, so with a future cutoff the
        # stale + leased rows are "old enough"; only lease/status filter out.
        cutoff = now + timedelta(hours=1)
        found = {r.job_id for r in await svc.list_stale_runs(db, updated_before=cutoff)}
        assert stale_running in found
        assert terminal not in found  # terminal — nothing to sweep
        assert leased not in found  # live lease — another worker owns it

        # A recent-only cutoff excludes even the running row.
        past_cutoff = now - timedelta(hours=1)
        assert await svc.list_stale_runs(db, updated_before=past_cutoff) == []


# ---------------------------------------------------------------------------
# record_job_status — the write-through entry point
# ---------------------------------------------------------------------------


async def test_record_job_status_projects_job_store_payload(session_factory):
    job_id = _job_id()
    payload = {
        "status": "completed",
        "user_id": str(USER_A),
        "organization_id": str(ORG_A),
        "thread_id": None,
        "request": {"thread_id": "thread-9"},
        "error": None,
    }
    with patch("src.core.database.AsyncSessionLocal", session_factory):
        await svc.record_job_status(job_id, payload)

    async with session_factory() as db:
        run = await db.get(AgentRun, job_id)
        assert run is not None
        assert run.status == "completed"
        assert run.organization_id == ORG_A
        assert run.thread_id == "thread-9"  # extracted from nested request


async def test_record_job_status_never_raises(session_factory):
    """Postgres failure is swallowed — Redis stays authoritative."""

    def _boom(*a, **k):
        raise RuntimeError("db down")

    with patch("src.core.database.AsyncSessionLocal", _boom):
        await svc.record_job_status(_job_id(), {"status": "running", "user_id": "u"})


async def test_record_job_status_ignores_statusless_payload(session_factory):
    with patch("src.core.database.AsyncSessionLocal", session_factory):
        await svc.record_job_status(_job_id(), {"user_id": str(USER_A)})
    async with session_factory() as db:
        assert (await db.execute(AgentRun.__table__.select())).first() is None
