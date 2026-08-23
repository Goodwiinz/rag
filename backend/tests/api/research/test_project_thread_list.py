"""B8: list_project_threads must filter soft-deleted threads in SQL.

The endpoint used to load EVERY live ProjectThread link row for the project
and then drop rows whose thread was soft-deleted in Python — unbounded load
that grows with every dead thread. The Thread.is_deleted exclusion belongs in
the query itself; ``total`` must then match the returned rows exactly.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.research.project_chat import list_project_threads
from src.models import ProjectThread, Thread


def _pt_row(thread):
    pt = MagicMock(spec=ProjectThread)
    pt.id = uuid4()
    pt.project_id = uuid4()
    pt.thread = thread
    pt.thread_id = thread.id if thread else uuid4()
    pt.link_type = "manual"
    pt.linked_at = datetime(2026, 8, 23, tzinfo=timezone.utc)
    pt.linked_by_id = None
    pt.context_note = None
    return pt


def _thread(title="T"):
    t = MagicMock(spec=Thread)
    t.id = uuid4()
    t.title = title
    t.generate_title.return_value = title
    t.is_deleted = False
    t.conversation_id = uuid4()
    t.message_count = 0
    t.last_message_at = None
    return t


@pytest.mark.asyncio
async def test_list_filters_soft_deleted_threads_in_sql():
    """The ProjectThread select joins Thread and excludes is_deleted there."""
    statements = []
    db = AsyncMock(spec=AsyncSession)

    async def _capture(stmt, *args, **kwargs):
        statements.append(stmt)
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        return result

    db.execute.side_effect = _capture

    with patch(
        "src.api.research.project_chat._get_project_with_auth",
        new=AsyncMock(return_value=MagicMock()),
    ):
        response = await list_project_threads(uuid4(), current_user=MagicMock(), db=db)

    assert response.total == 0
    assert len(statements) == 1
    stmt = statements[0]

    # Join on Thread + is_deleted exclusion must appear in WHERE (compiling
    # only the whereclause: is_deleted is also in every SELECT column list).
    where_sql = str(stmt.whereclause.compile(dialect=pg.dialect())).lower()
    assert "is_deleted" in where_sql, (
        "list_project_threads does not exclude soft-deleted threads in SQL "
        "(audit B8: unbounded Python-side filtering)"
    )
    from_sql = str(stmt.compile(dialect=pg.dialect())).lower()
    assert (
        "threads" in from_sql and "join" in from_sql
    ), "expected an inner join onto the threads table"


@pytest.mark.asyncio
async def test_list_total_matches_rows_and_shape_preserved():
    """Response keeps {threads, total} shape; total equals returned rows."""
    live_a, live_b = _thread("A"), _thread("B")
    db = AsyncMock(spec=AsyncSession)

    async def _rows(stmt, *args, **kwargs):
        result = MagicMock()
        result.scalars.return_value.all.return_value = [
            _pt_row(live_a),
            _pt_row(live_b),
        ]
        return result

    db.execute.side_effect = _rows

    with patch(
        "src.api.research.project_chat._get_project_with_auth",
        new=AsyncMock(return_value=MagicMock()),
    ):
        response = await list_project_threads(uuid4(), current_user=MagicMock(), db=db)

    assert [t.thread_title for t in response.threads] == ["A", "B"]
    assert response.total == 2 == len(response.threads)


@pytest.mark.asyncio
async def test_list_skips_links_with_missing_thread_relation():
    """Defensive: a NULL thread relation still can't crash mapping."""
    db = AsyncMock(spec=AsyncSession)

    async def _rows(stmt, *args, **kwargs):
        result = MagicMock()
        result.scalars.return_value.all.return_value = [
            _pt_row(None),  # inner join should prevent this, but stay safe
            _pt_row(_thread("C")),
        ]
        return result

    db.execute.side_effect = _rows

    with patch(
        "src.api.research.project_chat._get_project_with_auth",
        new=AsyncMock(return_value=MagicMock()),
    ):
        response = await list_project_threads(uuid4(), current_user=MagicMock(), db=db)

    assert [t.thread_title for t in response.threads] == ["C"]
    assert response.total == 1
