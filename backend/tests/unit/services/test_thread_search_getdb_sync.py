"""thread_message_search_service must use the sync session factory.

get_db was changed to `async def get_db(request: Request)`, so `db = next(get_db())`
raises TypeError (async generator + missing request arg) before any query runs.
search_threads / search_messages / combined_search do that in their
`if db is None:` DEFENSIVE fallback. The mounted /api/v2 thread-search endpoints
all inject `Depends(get_db_sync)` and pass db=db, so the fallback is currently
unreachable (not a live 500) — but the branch is genuinely broken and would
TypeError the moment any caller passes db=None. Swap it to the sync generator
get_db_sync (these methods run raw sync `db.execute(text(...))`). This source
guard pins the fix and blocks regression.
"""

from __future__ import annotations

import pathlib

import pytest

pytestmark = pytest.mark.unit

_SRC = (
    pathlib.Path(__file__).resolve().parents[3]
    / "src"
    / "services"
    / "threads"
    / "thread_message_search_service.py"
).read_text()


def test_no_broken_next_get_db():
    # the async get_db cannot be advanced with next() — must never appear
    assert "next(get_db())" not in _SRC


def test_uses_sync_session_factory():
    assert "from src.core.database import get_db_sync" in _SRC
    assert _SRC.count("next(get_db_sync())") == 3


def test_no_async_get_db_import():
    # importing the async get_db here would invite the same bug back
    assert "from src.core.database import get_db\n" not in _SRC
