"""Count-filter-parity + has_more regressions for the files list endpoint.

Audit C10: the repo's recurring bug class is a paginated list whose COUNT query
applies different filters than its RESULT query — the count over-reports
``total`` and the endpoint advertises phantom "next" pages. ``list_files`` now
routes both queries through the single ``_list_files_filters`` helper; these
tests lock that in by capturing the two SQL statements the endpoint executes and
asserting their WHERE clauses are byte-identical, plus that ``has_more`` reflects
the true total.
"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from src.api.documents import files as files_mod
from src.shared.pagination import PaginationParams

pytestmark = pytest.mark.unit


def _where_sql(stmt) -> str:
    """Compiled WHERE clause with literal values inlined, for equality checks."""
    where = stmt.whereclause
    assert where is not None, "statement had no WHERE clause"
    compiled = where.compile(
        dialect=postgresql.dialect(),
        compile_kwargs={"literal_binds": True},
    )
    return str(compiled)


class _RecordingDB:
    """Async db stub that records every executed statement in order.

    ``list_files`` executes the count query first, then the result query. The
    stub returns a scalar for the first call and an (empty by default) scalars
    list for the second.
    """

    def __init__(self, total: int, rows: list):
        self.total = total
        self.rows = rows
        self.statements: list = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        res = MagicMock()
        if len(self.statements) == 1:
            res.scalar.return_value = self.total
        else:
            res.scalars.return_value.all.return_value = self.rows
        return res


def _user():
    u = MagicMock()
    u.id = "user-1"
    return u


def _org():
    o = MagicMock()
    o.id = uuid.uuid4()
    return o


def _run(db, **kwargs):
    defaults = dict(
        pagination=PaginationParams(page=1, size=20),
        document_type=None,
        processing_status=None,
        search=None,
        current_user=_user(),
        organization=_org(),
        db=db,
    )
    defaults.update(kwargs)
    return asyncio.run(files_mod.list_files(**defaults))


@pytest.mark.parametrize(
    "kwargs",
    [
        {},  # no filters
        {"search": "quantum"},  # LIKE branch
        {"processing_status": "indexed"},  # enum-translated branch
        {"search": "a%b_c", "processing_status": "queued"},  # combined + escaping
    ],
)
def test_count_and_result_share_identical_filters(kwargs):
    db = _RecordingDB(total=0, rows=[])
    _run(db, **kwargs)

    assert len(db.statements) == 2, "expected a count query then a result query"
    count_stmt, result_stmt = db.statements
    # The whole point of C10: the two queries filter on exactly the same
    # predicates. If a future edit adds a filter to only one, this diverges.
    assert _where_sql(count_stmt) == _where_sql(result_stmt)


def test_response_reports_has_more_from_true_total():
    # 3 rows returned on page 1 of size 20 but total says 50 -> more remain.
    rows = [MagicMock(**{"to_dict.return_value": {"id": i}}) for i in range(3)]
    db = _RecordingDB(total=50, rows=rows)
    resp = _run(db, pagination=PaginationParams(page=1, size=20))
    assert resp.total == 50
    assert resp.has_more is True
    assert len(resp.files) == 3


def test_response_has_no_more_on_last_page():
    rows = [MagicMock(**{"to_dict.return_value": {"id": i}}) for i in range(5)]
    # page 1, size 20, total 5 -> everything fits, no next page.
    db = _RecordingDB(total=5, rows=rows)
    resp = _run(db, pagination=PaginationParams(page=1, size=20))
    assert resp.has_more is False
    assert resp.total == 5


def test_result_query_uses_validated_offset_and_limit():
    rows = []
    db = _RecordingDB(total=0, rows=rows)
    _run(db, pagination=PaginationParams(page=3, size=25))
    _, result_stmt = db.statements
    # offset = (3-1)*25 = 50, limit = 25
    assert result_stmt._offset == 50
    assert result_stmt._limit == 25
