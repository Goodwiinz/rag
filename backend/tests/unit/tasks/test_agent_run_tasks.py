"""run_agent_job — the Celery execution backend for /execute turns (P1.3).

The one-shot execution claim is the idempotency mechanism: a duplicate
delivery (acks_late redelivery, broker retry, double publish) must no-op
instead of double-running a turn whose tools may have side effects. Covered
here directly against the async runner (_execute_agent_job) on sqlite, plus
the wiring (dedicated queue, beat entries, persistent worker loop reuse).
"""

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.models.agent_run import AgentRun
from src.models.user import User
from src.services.agent import agent_run_service as svc
from src.shared.enums import JobStatus
from src.tasks import agent_run_tasks as tasks_mod

pytestmark = pytest.mark.unit


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(AgentRun.__table__.create)
        await conn.run_sync(User.__table__.create)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def _seed_user(session_factory, *, active=True):
    user_id = uuid.uuid4()
    # first_name/last_name are encrypted-at-bind columns; the unit-test env
    # has no PII key, so store plaintext (the read path treats plaintext as
    # the documented graceful fallback for encryption-disabled writes).
    with patch(
        "src.models.encrypted_fields.encrypt_sensitive_field",
        side_effect=lambda value, field_name: value,
    ):
        async with session_factory() as db:
            db.add(
                User(
                    id=user_id,
                    email=f"{user_id}@example.com",
                    password_hash="x",
                    first_name="Test",
                    last_name="User",
                    is_active=active,
                )
            )
            await db.commit()
    return user_id


async def _seed_run(session_factory, job_id, user_id, status=JobStatus.QUEUED):
    async with session_factory() as db:
        await svc.upsert_run(db, job_id=job_id, status=status, user_id=user_id)


def _payload():
    return {
        "messages": [{"role": "user", "content": "hello"}],
        "page_context": {"type": "unknown"},
    }


@pytest.mark.asyncio
async def test_first_delivery_claims_and_runs(session_factory):
    user_id = await _seed_user(session_factory)
    job_id = str(uuid.uuid4())
    await _seed_run(session_factory, job_id, user_id)

    runner = AsyncMock()
    with (
        patch("src.core.database.AsyncSessionLocal", session_factory),
        patch("src.services.agent.agent_execution_service._run_agent_graph", runner),
        patch.object(tasks_mod, "_mark_job_running", new=AsyncMock()) as mark_running,
    ):
        result = await tasks_mod._execute_agent_job(
            job_id, _payload(), str(user_id), lease_owner="celery:w1"
        )

    assert result["outcome"] == "ran"
    runner.assert_awaited_once()
    # The shared runner got the reconstructed request + the DB user.
    args = runner.await_args.args
    assert args[0] == job_id
    assert args[1].messages[0].content == "hello"
    assert args[2].id == user_id
    mark_running.assert_awaited_once()
    async with session_factory() as db:
        run = await db.get(AgentRun, job_id)
        assert run.status == JobStatus.RUNNING.value
        assert run.started_at is not None
        assert run.lease_owner == "celery:w1"  # claim stamped, never released


@pytest.mark.asyncio
async def test_duplicate_delivery_noops(session_factory):
    """Second delivery of the same job: claim already taken → runner NOT
    invoked a second time and the job record is left alone."""
    user_id = await _seed_user(session_factory)
    job_id = str(uuid.uuid4())
    await _seed_run(session_factory, job_id, user_id)

    runner = AsyncMock()
    with (
        patch("src.core.database.AsyncSessionLocal", session_factory),
        patch("src.services.agent.agent_execution_service._run_agent_graph", runner),
        patch.object(tasks_mod, "_mark_job_running", new=AsyncMock()) as mark_running,
    ):
        first = await tasks_mod._execute_agent_job(
            job_id, _payload(), str(user_id), lease_owner="celery:w1"
        )
        second = await tasks_mod._execute_agent_job(
            job_id, _payload(), str(user_id), lease_owner="celery:w2"
        )

    assert first["outcome"] == "ran"
    assert second["outcome"] == "duplicate-noop"
    runner.assert_awaited_once()
    mark_running.assert_awaited_once()


@pytest.mark.asyncio
async def test_legacy_running_row_is_claimed_during_rolling_upgrade(session_factory):
    """New workers must drain jobs published by an older API pod."""
    user_id = await _seed_user(session_factory)
    job_id = str(uuid.uuid4())
    await _seed_run(
        session_factory,
        job_id,
        user_id,
        status=JobStatus.RUNNING,
    )

    runner = AsyncMock()
    with (
        patch("src.core.database.AsyncSessionLocal", session_factory),
        patch("src.services.agent.agent_execution_service._run_agent_graph", runner),
        patch.object(tasks_mod, "_mark_job_running", new=AsyncMock()),
    ):
        result = await tasks_mod._execute_agent_job(
            job_id, _payload(), str(user_id), lease_owner="celery:new-worker"
        )

    assert result["outcome"] == "ran"
    runner.assert_awaited_once()
    async with session_factory() as db:
        run = await db.get(AgentRun, job_id)
        assert run.status == JobStatus.RUNNING.value
        assert run.lease_owner == "celery:new-worker"


@pytest.mark.asyncio
async def test_terminal_run_noops(session_factory):
    """A late redelivery after the run finished (terminal status) no-ops even
    though nothing holds the lease."""
    user_id = await _seed_user(session_factory)
    job_id = str(uuid.uuid4())
    await _seed_run(session_factory, job_id, user_id, status=JobStatus.COMPLETED)

    runner = AsyncMock()
    with (
        patch("src.core.database.AsyncSessionLocal", session_factory),
        patch("src.services.agent.agent_execution_service._run_agent_graph", runner),
    ):
        result = await tasks_mod._execute_agent_job(
            job_id, _payload(), str(user_id), lease_owner="celery:w1"
        )

    assert result["outcome"] == "duplicate-noop"
    runner.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_row_refuses_to_run_and_fails_job(session_factory):
    """No agent_runs row ⇒ no idempotency guarantee ⇒ never run the turn;
    the job record is failed so the poller stops."""
    user_id = await _seed_user(session_factory)
    job_id = str(uuid.uuid4())  # row never created

    runner = AsyncMock()
    fail_record = AsyncMock()
    with (
        patch("src.core.database.AsyncSessionLocal", session_factory),
        patch("src.services.agent.agent_execution_service._run_agent_graph", runner),
        patch.object(tasks_mod, "_fail_job_record", fail_record),
    ):
        result = await tasks_mod._execute_agent_job(
            job_id, _payload(), str(user_id), lease_owner="celery:w1"
        )

    assert result["outcome"] == "unclaimed-missing"
    runner.assert_not_awaited()
    fail_record.assert_awaited_once()


@pytest.mark.asyncio
async def test_unknown_user_fails_job_without_running(session_factory):
    job_id = str(uuid.uuid4())
    ghost = uuid.uuid4()
    await _seed_run(session_factory, job_id, ghost)

    runner = AsyncMock()
    fail_record = AsyncMock()
    with (
        patch("src.core.database.AsyncSessionLocal", session_factory),
        patch("src.services.agent.agent_execution_service._run_agent_graph", runner),
        patch.object(tasks_mod, "_fail_job_record", fail_record),
    ):
        result = await tasks_mod._execute_agent_job(
            job_id, _payload(), str(ghost), lease_owner="celery:w1"
        )

    assert result["outcome"] == "user-unavailable"
    runner.assert_not_awaited()
    fail_record.assert_awaited_once()


@pytest.mark.asyncio
async def test_inactive_user_fails_job_without_running(session_factory):
    user_id = await _seed_user(session_factory, active=False)
    job_id = str(uuid.uuid4())
    await _seed_run(session_factory, job_id, user_id)

    runner = AsyncMock()
    with (
        patch("src.core.database.AsyncSessionLocal", session_factory),
        patch("src.services.agent.agent_execution_service._run_agent_graph", runner),
        patch.object(tasks_mod, "_fail_job_record", AsyncMock()),
    ):
        result = await tasks_mod._execute_agent_job(
            job_id, _payload(), str(user_id), lease_owner="celery:w1"
        )

    assert result["outcome"] == "user-unavailable"
    runner.assert_not_awaited()


@pytest.mark.asyncio
async def test_fail_job_record_preserves_owner_and_projects(session_factory):
    """_fail_job_record merges into the existing job record (ownership must
    survive) and writes the durable projection."""
    user_id = await _seed_user(session_factory)
    job_id = str(uuid.uuid4())
    await _seed_run(session_factory, job_id, user_id)
    existing = {"status": "running", "user_id": str(user_id), "request": {"a": 1}}

    set_job = AsyncMock()
    with (
        patch("src.core.database.AsyncSessionLocal", session_factory),
        patch(
            "src.services.agent.job_store.get_job",
            new=AsyncMock(return_value=existing),
        ),
        patch("src.services.agent.job_store.set_job", set_job),
    ):
        await tasks_mod._fail_job_record(job_id, "boom", user_id=str(user_id))

    written = set_job.await_args.args[1]
    assert written["status"] == JobStatus.FAILED
    assert written["error"] == "boom"
    assert written["user_id"] == str(user_id)
    assert written["request"] == {"a": 1}  # merge, not replace
    async with session_factory() as db:
        run = await db.get(AgentRun, job_id)
        assert run.status == "failed"
        assert run.error == "boom"


@pytest.mark.asyncio
async def test_mark_job_running_updates_live_store_after_claim():
    user = SimpleNamespace(id=uuid.uuid4(), organization_id=uuid.uuid4())
    request_payload = _payload()
    set_job = AsyncMock()

    with patch("src.services.agent.job_store.set_job", set_job):
        await tasks_mod._mark_job_running("job-1", request_payload, user)

    written = set_job.await_args.args[1]
    assert written == {
        "status": JobStatus.RUNNING,
        "tool_executions": [],
        "user_id": str(user.id),
        "organization_id": str(user.organization_id),
        "request": request_payload,
    }


# ---------------------------------------------------------------------------
# Worker loop + wiring
# ---------------------------------------------------------------------------


def test_agent_tasks_route_through_shared_run_async_one_loop():
    """The agent Celery task drives coroutines through the shared run_async
    boundary, and two sync→async hops land on the SAME persistent loop — so the
    loop-bound singletons (checkpointer pool, redis client, async engine) survive
    across tasks. Consolidated onto ``_async_utils.run_async`` (was this module's
    own ``_run_coro``); asserting the identity keeps the single-boundary contract
    from silently regressing to a second bespoke loop."""
    from src.tasks._async_utils import run_async as shared_run_async

    # The module routes through the one shared helper (single loop + boundary).
    assert tasks_mod.run_async is shared_run_async
    assert not hasattr(tasks_mod, "_run_coro")

    async def _loop_id():
        return id(asyncio.get_running_loop())

    first = tasks_mod.run_async(_loop_id(), timeout=5)
    second = tasks_mod.run_async(_loop_id(), timeout=5)
    assert first == second


def test_run_agent_job_routed_to_dedicated_queue():
    from src.tasks.celery_app import celery_app

    route = celery_app.conf.task_routes["src.tasks.agent_run_tasks.run_agent_job"]
    assert route == {"queue": "agent_runs"}
    assert "agent_runs" in celery_app.conf.task_queues


def test_sweepers_are_beat_scheduled_and_registered():
    import src.tasks.agent_run_tasks  # noqa: F401
    import src.tasks.processing_tasks  # noqa: F401
    from src.tasks.celery_app import celery_app

    schedule = celery_app.conf.beat_schedule
    for key, task_path in (
        ("sweep-stale-agent-runs", "src.tasks.agent_run_tasks.sweep_stale_agent_runs"),
        (
            "sweep-stuck-processing-jobs",
            "src.tasks.processing_tasks.sweep_stuck_processing_jobs",
        ),
    ):
        assert schedule[key]["task"] == task_path
        assert task_path in celery_app.tasks
