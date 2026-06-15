"""Unit tests for project-memory recall (the agent read path).

Recall is best-effort: it must never raise and must return a clean list of
non-empty strings. These tests exercise the guard paths without a real DB.
"""

import pytest

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
