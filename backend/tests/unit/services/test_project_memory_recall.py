"""Unit tests for project-memory recall (the agent read path).

Recall is best-effort: it must never raise and must return a clean list of
non-empty strings. These tests exercise guard paths with stubs and a throwaway
SQLite database.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.services.research.project_memory_service import (
    MAX_AGENT_MEMORIES,
    load_project_memories,
)


class _FakeScalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return _FakeScalars(self._rows)


class _FakeDB:
    """Minimal async DB stub returning preset rows (or raising)."""

    def __init__(self, rows=None, raise_exc=None):
        self._rows = rows or []
        self._raise = raise_exc

    async def execute(self, _query):
        if self._raise:
            raise self._raise
        return _FakeResult(self._rows)


@pytest.mark.asyncio
async def test_returns_empty_without_db_or_project():
    assert await load_project_memories(None, "p1") == []
    assert await load_project_memories(_FakeDB(), "") == []


@pytest.mark.asyncio
async def test_strips_and_drops_blank_rows():
    db = _FakeDB(rows=["  cite in APA  ", "", "   ", "focus post-2020"])
    out = await load_project_memories(db, "proj-1")
    assert out == ["cite in APA", "focus post-2020"]


@pytest.mark.asyncio
async def test_never_raises_on_db_error():
    db = _FakeDB(raise_exc=RuntimeError("boom"))
    assert await load_project_memories(db, "proj-1") == []


@pytest.mark.asyncio
async def test_limit_is_capped():
    # limit above the hard cap is clamped; loader still returns what the
    # (stubbed) query yields, but the cap guards the query size.
    db = _FakeDB(rows=["a", "b"])
    out = await load_project_memories(db, "proj-1", limit=10_000)
    assert out == ["a", "b"]
    assert MAX_AGENT_MEMORIES == 25


@pytest.mark.asyncio
async def test_scoped_recall_excludes_other_org_and_user_memories():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    user_a, user_a_peer, user_b = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    project_id = uuid.uuid4()

    try:
        async with engine.begin() as conn:
            await conn.exec_driver_sql(
                "CREATE TABLE users (id CHAR(36) PRIMARY KEY, organization_id CHAR(36))"
            )
            await conn.exec_driver_sql(
                "CREATE TABLE project_memories ("
                "id CHAR(36) PRIMARY KEY, "
                "project_id CHAR(36) NOT NULL, "
                "user_id CHAR(36) NOT NULL, "
                "content TEXT NOT NULL, "
                "created_at DATETIME NOT NULL"
                ")"
            )
            await conn.exec_driver_sql(
                "INSERT INTO users (id, organization_id) VALUES (?, ?)",
                [
                    (str(user_a), str(org_a)),
                    (str(user_a_peer), str(org_a)),
                    (str(user_b), str(org_b)),
                ],
            )
            await conn.exec_driver_sql(
                "INSERT INTO project_memories "
                "(id, project_id, user_id, content, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                [
                    (
                        str(uuid.uuid4()),
                        str(project_id),
                        str(user_a),
                        "org A memory",
                        "2026-01-03 00:00:00",
                    ),
                    (
                        str(uuid.uuid4()),
                        str(project_id),
                        str(user_a_peer),
                        "org A peer memory",
                        "2026-01-02 00:00:00",
                    ),
                    (
                        str(uuid.uuid4()),
                        str(project_id),
                        str(user_b),
                        "org B secret",
                        "2026-01-01 00:00:00",
                    ),
                ],
            )

        async with AsyncSession(engine, expire_on_commit=False) as db:
            assert await load_project_memories(
                db, str(project_id), organization_id=org_a
            ) == ["org A memory", "org A peer memory"]
            assert await load_project_memories(
                db, str(project_id), organization_id=org_a, user_id=user_a
            ) == ["org A memory"]
    finally:
        await engine.dispose()
