"""Guard: the evaluation router must inject the *sync* DB session.

`api/infrastructure/evaluation.py` is written entirely against a synchronous
SQLAlchemy session — every endpoint uses `db.query(...)`, `db.add(...)`,
`db.commit()`, `db.refresh(...)`, and the `rag_evaluation_service.*` methods run
sync ORM internally (no `await db`). The router historically injected the async
`get_db` (`Depends(get_db)`), which broke the whole subsystem:

  - GET endpoints (`/jobs`, `/jobs/{id}`, `/jobs/{id}/metrics`, `/comparisons`,
    `/reports`, `/metrics/summary`, ...) called `db.query(...)` on an
    AsyncSession → `AttributeError` → 500.
  - POST endpoints (`/jobs`, `/jobs/batch`) called `db.commit()`, which on an
    AsyncSession returns an un-awaited coroutine → silently DID NOT persist.

The fix mirrors the search/rbac PRs: inject `get_db_sync` so the sync ORM API
works. This source guard keeps the router from regressing back to the async
`get_db`. It intentionally does not import the app (the full app can't import in
CI-lite envs); it only reads the router source.
"""

from pathlib import Path

# tests/ -> backend/
ROUTER = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "api"
    / "infrastructure"
    / "evaluation.py"
)


def _source() -> str:
    return ROUTER.read_text()


def test_router_imports_get_db_sync():
    source = _source()
    assert "get_db_sync" in source, (
        "evaluation.py must import and use get_db_sync; the endpoints run the "
        "sync SQLAlchemy ORM API (db.query/db.add/db.commit)"
    )


def test_router_does_not_import_async_get_db():
    source = _source()
    # The async get_db is imported as a bare name; catch both the end-of-line
    # and the ", " continuation forms so an accidental re-add regresses the test.
    assert "import get_db\n" not in source, (
        "evaluation.py must not import the async get_db; it breaks every "
        "endpoint (db.query -> AttributeError, db.commit -> un-awaited coroutine)"
    )
    assert (
        "import get_db " not in source
    ), "evaluation.py must not import the async get_db alongside other names"


def test_router_uses_only_sync_depends():
    source = _source()
    assert "Depends(get_db)" not in source, (
        "evaluation.py must inject Depends(get_db_sync), never Depends(get_db) — "
        "the async session breaks the sync ORM calls"
    )
    assert (
        "Depends(get_db_sync)" in source
    ), "evaluation.py endpoints must inject Depends(get_db_sync)"
