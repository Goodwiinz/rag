"""Audit S2-M15 regression: SSE/background-dispatch runs stamped updated_at
once and relied on AGENT_RUN_STALE_AFTER_SECONDS (1800) being larger than the
graph hard timeout (360s) — pure config margin. Any drift (timeout raised,
staleness lowered) let sweep_stale_agent_runs kill a LIVE run and leave the
ledger FAILED after the answer was already delivered.

Fix: live runs heartbeat agent_runs.updated_at while executing (guarded to
non-terminal rows), and the sweeper's effective staleness floor is pinned to
max(AGENT_RUN_STALE_AFTER_SECONDS, 4x heartbeat).
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.models.agent_run import AgentRun
from src.services.agent import agent_execution_service, agent_run_service

pytestmark = pytest.mark.unit

NOW = datetime.now(timezone.utc)


def _aware(dt: Any) -> datetime:
    """SQLite returns naive UTC datetimes; normalize before comparing.

    Takes ``Any``: AgentRun predates ``Mapped[...]`` annotations, so mypy sees
    instance attributes as ``Column[datetime]`` rather than ``datetime``."""
    aware: datetime = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    return aware


@pytest.fixture
async def session_factory(
    tmp_path_factory: pytest.TempPathFactory,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    # A temp FILE, not ":memory:". The heartbeat beats on its own session
    # concurrently with this test's sessions; with an in-memory database the
    # only way to share it is StaticPool's single connection, and SQLite
    # cannot take concurrent use of one connection. The resulting error
    # invalidates it, the pool opens a fresh one — and a fresh ":memory:"
    # connection is a new, table-less database ("no such table: agent_runs",
    # intermittently). A file is opened independently by every connection,
    # so the schema survives and the beats race nothing.
    db_path = tmp_path_factory.mktemp("agent-run-heartbeat") / "heartbeat.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(AgentRun.__table__.create)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def _seed_running(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    updated_at: datetime = NOW,
) -> str:
    job_id = str(uuid.uuid4())
    async with session_factory() as db:
        db.add(
            AgentRun(
                job_id=job_id,
                user_id=uuid.uuid4(),
                status="running",
                created_at=updated_at,
                updated_at=updated_at,
            )
        )
        await db.commit()
    return job_id


async def _row(
    session_factory: async_sessionmaker[AsyncSession], job_id: str
) -> AgentRun:
    async with session_factory() as db:
        run = await db.get(AgentRun, job_id)
        assert run is not None
        db.expunge(run)
        return cast(AgentRun, run)


@pytest.mark.asyncio
async def test_touch_bumps_updated_at_on_non_terminal_row(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    job_id = await _seed_running(
        session_factory, updated_at=NOW - timedelta(minutes=10)
    )

    async with session_factory() as db:
        bumped = await agent_run_service.touch_run_updated_at(db, job_id)
        await db.commit()

    assert bumped is True
    row = await _row(session_factory, job_id)
    assert _aware(row.updated_at) > NOW - timedelta(minutes=10)
    assert row.status == "running"


@pytest.mark.asyncio
async def test_touch_never_resurrects_terminal_row(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    job_id = await _seed_running(
        session_factory, updated_at=NOW - timedelta(minutes=10)
    )
    async with session_factory() as db:
        run = await db.get(AgentRun, job_id)
        assert run is not None
        setattr(run, "status", "completed")
        await db.commit()

    async with session_factory() as db:
        bumped = await agent_run_service.touch_run_updated_at(db, job_id)
        await db.commit()

    assert bumped is False


@pytest.mark.asyncio
async def test_heartbeat_context_keeps_row_fresh_while_block_runs(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    job_id = await _seed_running(
        session_factory, updated_at=NOW - timedelta(minutes=10)
    )
    seeded_at = (await _row(session_factory, job_id)).updated_at
    monkeypatch.setattr(
        "src.services.agent.agent_execution_service.AsyncSessionLocal",
        session_factory,
    )

    async with agent_execution_service._run_heartbeat(job_id, interval_seconds=0.01):
        await asyncio.sleep(0.06)

    row = await _row(session_factory, job_id)
    assert _aware(row.updated_at) > _aware(seeded_at)
    # A late heartbeat must not clobber a terminal write that landed after it.
    async with session_factory() as db:
        run = await db.get(AgentRun, job_id)
        assert run is not None
        setattr(run, "status", "failed")
        await db.commit()
    async with session_factory() as db:
        bumped = await agent_run_service.touch_run_updated_at(db, job_id)
    assert bumped is False
    assert (await _row(session_factory, job_id)).status == "failed"
