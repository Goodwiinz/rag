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


async def _seed_run(session_factory, job_id, user_id, status=JobStatus.RUNNING):
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
        patch("src.api.agent.jobs._run_agent_graph", runner),
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
    async with session_factory() as db:
        run = await db.get(AgentRun, job_id)
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
        patch("src.api.agent.jobs._run_agent_graph", runner),
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
        patch("src.api.agent.jobs._run_agent_graph", runner),
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
        patch("src.api.agent.jobs._run_agent_graph", runner),
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
        patch("src.api.agent.jobs._run_agent_graph", runner),
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
        patch("src.api.agent.jobs._run_agent_graph", runner),
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


# ---------------------------------------------------------------------------
# Worker loop + wiring
# ---------------------------------------------------------------------------


def test_run_coro_reuses_one_persistent_loop():
    """Two sync→async hops must land on the SAME loop — loop-bound singletons
    (checkpointer pool, redis client, async engine) survive across tasks."""

    async def _loop_id():
        return id(asyncio.get_running_loop())

    first = tasks_mod._run_coro(_loop_id(), timeout=5)
    second = tasks_mod._run_coro(_loop_id(), timeout=5)
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
