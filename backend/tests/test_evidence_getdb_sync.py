"""Guard: the evidence router must use the sync session, not the async get_db.

`get_db` became `async def get_db(request: Request)` yielding an `AsyncSession`
(database.py:211). The evidence endpoints (`/meter`, `/breakdown`, `/classify`)
are written against the **sync** ORM API — `db.query(...)`, `db.execute(...)`,
`db.commit()`, `db.add(...)`, `db.bind`, `db.rollback()`. On an `AsyncSession`:

- `db.query(...)` raises `AttributeError` — so `GET /api/v1/evidence/breakdown`
  hit its first DB statement and 500'd on every authenticated call (the blanket
  `except Exception` turned it into HTTP 500). The org-scoped filter (the whole
  point of migration ``add_org_id_to_stance_classifications``) never ran.
- `db.execute(...)` / `db.commit()` return un-awaited coroutines — `/meter` and
  `/classify` silently failed to persist stance classifications.

The fix injects `get_db_sync` (database.py:202 → sync `SessionLocal`/`engine`)
so the existing sync-ORM code works unchanged — the same migration applied to
`knowledge_graph.py`, `user_behavior.py`, and `processing.py`. This source guard
keeps the async `get_db` (and any bare `Depends(get_db)`) from creeping back in.
"""

from pathlib import Path

# tests/ -> backend/
ROUTER = Path(__file__).resolve().parents[1] / "src" / "api" / "evidence" / "router.py"


def test_evidence_router_does_not_import_async_get_db():
    source = ROUTER.read_text()
    assert "import get_db_sync" in source, "evidence router must import get_db_sync"
    assert "import get_db\n" not in source and "import get_db " not in source, (
        "evidence router imports the async get_db; its endpoints use the sync ORM "
        "API (db.query/db.commit/db.execute), which 500s / no-ops on an AsyncSession"
    )


def test_evidence_router_uses_get_db_sync_dependency():
    source = ROUTER.read_text()
    assert "Depends(get_db)" not in source, (
        "evidence router still injects the async get_db via Depends(get_db); "
        "use Depends(get_db_sync) so the sync-ORM endpoints get a real Session"
    )
    # All three DB-backed endpoints must inject the sync session.
    assert source.count("Depends(get_db_sync)") >= 3, (
        "expected all three DB endpoints (/meter, /breakdown, /classify) to depend "
        "on get_db_sync"
    )
