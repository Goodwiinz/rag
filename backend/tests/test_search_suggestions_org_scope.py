"""Guard: GET /api/v1/search/suggestions must scope to the caller's org.

`FulltextSearchService._get_search_suggestions(query, db, organization_id=None)`
fails closed — it returns `[]` unless given an `organization_id` (title
suggestions would otherwise leak other tenants' document titles). The endpoint
call site historically dropped the arg entirely, so the endpoint returned `[]`
for every user — a 100% dead auto-complete feature.

Two coupled defects were fixed at `api/search/search.py`:
  1. the call passed only `(q, db)` → org defaulted to None → guard returned [].
  2. the endpoint injected the async `get_db`; the service runs a *sync*
     `db.execute(text(...))`, which on an AsyncSession returns an un-awaited
     coroutine and silently fails. The endpoint now injects `get_db_sync`.

These source guards keep both from regressing; the behavioral test pins the
fail-closed contract (no org → no suggestions).
"""

from pathlib import Path

import pytest

# tests/ -> backend/
ROUTER = Path(__file__).resolve().parents[1] / "src" / "api" / "search" / "search.py"


def _suggestions_endpoint_block() -> str:
    """Return the source of the get_search_suggestions endpoint."""
    source = ROUTER.read_text()
    start = source.index("async def get_search_suggestions(")
    # up to the next top-level route decorator
    end = source.index('@router.get("/history")', start)
    return source[start:end]


def test_suggestions_call_passes_organization_id():
    block = _suggestions_endpoint_block()
    assert "organization_id=" in block, (
        "get_search_suggestions must pass organization_id to "
        "_get_search_suggestions; without it the service fail-closes to []"
    )
    # The bare 2-arg call `(q, db)` is the regression we are guarding against.
    assert "_get_search_suggestions(q, db)" not in block, (
        "get_search_suggestions drops organization_id (bare `(q, db)` call) — "
        "the endpoint will always return []"
    )


def test_suggestions_uses_sync_session():
    block = _suggestions_endpoint_block()
    assert "Depends(get_db_sync)" in block, (
        "get_search_suggestions must inject get_db_sync; the service uses the "
        "sync db.execute API, which silently fails on the async get_db session"
    )


def test_service_suggestions_fail_closed_without_org():
    """No organization_id → no suggestions (never touches the DB)."""
    mod = pytest.importorskip("src.services.search.fulltext_search_service")
    svc = mod.FullTextSearchService()

    class _BoomSession:
        def execute(self, *a, **k):  # must not be reached
            raise AssertionError("DB queried despite missing organization_id")

    assert svc._get_search_suggestions("neural", _BoomSession(), None) == []
    assert svc._get_search_suggestions("neural", _BoomSession()) == []
