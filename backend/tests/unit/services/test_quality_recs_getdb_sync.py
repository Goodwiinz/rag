"""quality_recommendations_service must use the sync session factory.

get_db is now `async def get_db(request: Request)`, so `db = next(get_db())`
raises TypeError before any query. _analyze_relevance_insights and
_analyze_response_time_insights did that UNCONDITIONALLY, and both are called by
analyze_quality_insights — which backs the mounted GET
/api/v1/analytics/recommendations/insights and /metrics endpoints. So those two
endpoints returned 500 (live). The methods run raw sync `db.execute(text(...))`
and `db.close()` (no await), so the sync generator get_db_sync is the fix. This
source guard pins it and blocks regression.
"""

from __future__ import annotations

import pathlib

import pytest

pytestmark = pytest.mark.unit

_SRC = (
    pathlib.Path(__file__).resolve().parents[3]
    / "src"
    / "services"
    / "quality"
    / "quality_recommendations_service.py"
).read_text()


def test_no_broken_next_get_db():
    assert "next(get_db())" not in _SRC


def test_uses_sync_session_factory():
    assert "from src.core.database import get_db_sync" in _SRC
    assert _SRC.count("next(get_db_sync())") == 2


def test_no_async_get_db_import():
    assert "from src.core.database import get_db\n" not in _SRC
