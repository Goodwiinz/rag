"""Schema contract for the durable run-event store (Hermes event runtime).

Pins the ``agent_run_events`` table shape (append-only ordered facts, unique
``(run_id, seq)``) and the expanded ``agent_runs`` columns the run lifecycle
service depends on. A column or constraint rename here is a wire/migration
break, not a refactor. See docs/plans/2026-07-20-hermes-event-runtime-design.md.
"""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.models.agent_run import AgentRun
from src.models.agent_run_event import AgentRunEvent

pytestmark = pytest.mark.unit


def test_event_identity_and_ordering() -> None:
    table = AgentRunEvent.__table__
    assert {"id", "run_id", "seq", "event_type", "payload", "created_at"} <= set(
        table.c.keys()
    )
    assert any(
        constraint.name == "uq_agent_run_events_run_seq"
        for constraint in table.constraints
    )
    assert any(index.name == "idx_agent_run_events_run_seq" for index in table.indexes)
    fk = next(iter(table.c.run_id.foreign_keys))
    assert fk.column.table.name == "agent_runs"
    assert fk.ondelete == "CASCADE"


def test_run_table_carries_durable_lifecycle_columns() -> None:
    cols = set(AgentRun.__table__.c.keys())
    assert {
        "conversation_id",
        "project_id",
        "thread_id",
        "user_message_id",
        "assistant_message_id",
        "runtime_snapshot_id",
        "client_message_id",
        "last_event_seq",
        "started_at",
        "completed_at",
        "cancel_requested_at",
        "error_code",
        "error",
        "usage",
        "run_metadata",
        "lease_generation",
    } <= cols
    # thread_id graduated from a free-form correlation string to a real FK.
    fk = next(iter(AgentRun.__table__.c.thread_id.foreign_keys))
    assert fk.column.table.name == "threads"


def test_one_active_run_per_thread_partial_index() -> None:
    index = next(
        idx
        for idx in AgentRun.__table__.indexes
        if idx.name == "uq_agent_runs_active_thread"
    )
    assert index.unique
    where = str(index.dialect_options["postgresql"]["where"]).lower()
    for status in ("queued", "running", "awaiting_confirmation", "stopping"):
        assert status in where
    for status in ("completed", "failed", "cancelled"):
        assert status not in where


def test_status_check_constraint_covers_new_lifecycle() -> None:
    from src.models.agent_run import AGENT_RUN_STATUS_CHECK

    assert "'queued'" in AGENT_RUN_STATUS_CHECK
    assert "'stopping'" in AGENT_RUN_STATUS_CHECK


def test_idempotency_uniqueness_is_tenant_scoped() -> None:
    index = next(
        idx
        for idx in AgentRun.__table__.indexes
        if idx.name == "uq_agent_runs_user_idempotency_key"
    )
    assert index.unique
    assert [c.name for c in index.columns] == ["user_id", "idempotency_key"]
    # The old global single-column unique index must be gone.
    assert not any(
        idx.name == "uq_agent_runs_idempotency_key"
        for idx in AgentRun.__table__.indexes
    )


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(AgentRun.__table__.create)
        await conn.run_sync(AgentRunEvent.__table__.create)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def test_duplicate_sequence_is_rejected(session_factory) -> None:
    job_id = str(uuid.uuid4())
    async with session_factory() as db:
        db.add(AgentRun(job_id=job_id, status="queued", user_id=uuid.uuid4()))
        db.add(
            AgentRunEvent(run_id=job_id, seq=1, event_type="run.created", payload={})
        )
        await db.commit()

        db.add(
            AgentRunEvent(run_id=job_id, seq=1, event_type="run.started", payload={})
        )
        with pytest.raises(IntegrityError):
            await db.commit()


async def test_last_event_seq_defaults_to_zero(session_factory) -> None:
    job_id = str(uuid.uuid4())
    async with session_factory() as db:
        db.add(AgentRun(job_id=job_id, status="queued", user_id=uuid.uuid4()))
        await db.commit()
        run = await db.get(AgentRun, job_id)
        assert run.last_event_seq == 0
        assert run.lease_generation == 0
