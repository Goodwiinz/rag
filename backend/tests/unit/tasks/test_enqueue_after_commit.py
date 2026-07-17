"""Contract for ``enqueue_after_commit`` (PR 1, Task 1.2).

The helper closes the worker-reads-before-commit race: a Celery enqueue is
deferred to fire *after* the owning ``AsyncSession`` commits, and is dropped if
the session rolls back. Pinned behaviors:

- fires ``task.delay(*args, **kwargs)`` only after a successful commit;
- dropped on rollback (never fires), and a later commit can't resurrect it;
- a raising ``delay`` is logged (``enqueue_after_commit_failed``) without
  corrupting the session or blocking sibling registrations;
- multiple registrations fire in registration order;
- a second commit does not re-fire an already-fired registration.

Uses an in-memory aiosqlite async session (mirrors the pattern in
``test_agent_run_tasks``) and a stub task (``name`` + ``delay`` mock) — no real
Celery broker.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import AsyncIterator
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.tasks.enqueue import (
    enqueue_after_commit,
    enqueue_after_commit_apply_async,
)

pytestmark = pytest.mark.unit


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


def _task(name: str = "my.task") -> SimpleNamespace:
    return SimpleNamespace(name=name, delay=MagicMock())


async def _work(db: AsyncSession) -> None:
    # Open a real transaction so rollback emits after_rollback (an empty
    # rollback is a no-op that fires nothing).
    await db.execute(text("SELECT 1"))


async def test_fires_only_after_commit(db: AsyncSession) -> None:
    task = _task()
    enqueue_after_commit(db, task, "doc-1", priority="high")

    # Registration alone must not enqueue.
    task.delay.assert_not_called()

    await _work(db)
    await db.commit()

    task.delay.assert_called_once_with("doc-1", priority="high")


async def test_dropped_on_rollback(db: AsyncSession) -> None:
    task = _task()
    enqueue_after_commit(db, task)

    await _work(db)
    await db.rollback()
    task.delay.assert_not_called()

    # A later commit must not resurrect the dropped registration.
    await _work(db)
    await db.commit()
    task.delay.assert_not_called()


async def test_multiple_fire_in_registration_order(db: AsyncSession) -> None:
    order: list[str] = []
    tasks = []
    for name in ("t1", "t2", "t3"):
        t = SimpleNamespace(
            name=name,
            delay=MagicMock(side_effect=lambda *a, _n=name, **k: order.append(_n)),
        )
        tasks.append(t)
        enqueue_after_commit(db, t)

    await _work(db)
    await db.commit()

    assert order == ["t1", "t2", "t3"]


async def test_raising_task_logs_without_corrupting_session(db: AsyncSession) -> None:
    boom = SimpleNamespace(
        name="boom.task", delay=MagicMock(side_effect=RuntimeError("broker down"))
    )
    after = _task("after.task")
    enqueue_after_commit(db, boom)
    enqueue_after_commit(db, after)

    with patch("src.tasks.enqueue.logger") as mock_logger:
        await _work(db)
        await db.commit()  # must NOT raise despite boom.delay raising

    mock_logger.exception.assert_called_once_with(
        "enqueue_after_commit_failed", task="boom.task"
    )
    # A raising registration must not block the ones after it.
    after.delay.assert_called_once_with()

    # Session is still usable after the swallowed error.
    await _work(db)
    await db.commit()


async def test_apply_async_variant_fires_with_options_after_commit(
    db: AsyncSession,
) -> None:
    task = SimpleNamespace(name="kg.task", apply_async=MagicMock())
    enqueue_after_commit_apply_async(
        db, task, args=["kg-1"], queue="entity_processing"
    )

    # Registration alone must not enqueue.
    task.apply_async.assert_not_called()

    await _work(db)
    await db.commit()

    task.apply_async.assert_called_once_with(
        args=["kg-1"], kwargs=None, queue="entity_processing"
    )


async def test_apply_async_variant_dropped_on_rollback(db: AsyncSession) -> None:
    task = SimpleNamespace(name="kg.task", apply_async=MagicMock())
    enqueue_after_commit_apply_async(db, task, args=["kg-1"], queue="q")

    await _work(db)
    await db.rollback()
    task.apply_async.assert_not_called()


async def test_second_commit_does_not_refire(db: AsyncSession) -> None:
    first = _task("first")
    enqueue_after_commit(db, first)

    await _work(db)
    await db.commit()
    first.delay.assert_called_once()

    # Commit again with no new registration — must not re-fire.
    await _work(db)
    await db.commit()
    first.delay.assert_called_once()

    # A fresh registration fires on the next commit; the earlier one stays put.
    second = _task("second")
    enqueue_after_commit(db, second)
    await _work(db)
    await db.commit()
    second.delay.assert_called_once()
    first.delay.assert_called_once()
