"""Guard: get_rbac_service must inject the sync session, not the async get_db.

`RBACService` is entirely synchronous — every method uses `self.db.query`,
`self.db.execute`, `self.db.commit`, `self.db.refresh`, `self.db.delete`. The
FastAPI factory `get_rbac_service` injected the async `get_db` (database.py:211,
yields an `AsyncSession`), so `rbac_service.db.query(...)` raised
`AttributeError: 'AsyncSession' object has no attribute 'query'` — every
`/api/v1/rbac` endpoint that touched the DB (list/create/update/delete roles,
assign/revoke user roles, list permissions, …) 500'd on every call.

Fix: inject `get_db_sync` (database.py:202 → sync `SessionLocal`). This source
guard keeps the async `get_db` from being reintroduced into the factory.
"""

from pathlib import Path

# tests/ -> backend/
SERVICE = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "services"
    / "security"
    / "rbac_service.py"
)


def test_get_rbac_service_uses_sync_session():
    source = SERVICE.read_text()
    assert "def get_rbac_service(db: Session = Depends(get_db_sync))" in source, (
        "get_rbac_service must inject get_db_sync; RBACService uses the sync ORM "
        "API (self.db.query/.commit), which raises AttributeError on an AsyncSession"
    )


def test_rbac_service_does_not_import_async_get_db():
    source = SERVICE.read_text()
    assert "import get_db_sync" in source, "rbac_service must import get_db_sync"
    assert "import get_db\n" not in source and "import get_db " not in source, (
        "rbac_service imports the async get_db; the sync RBACService must be given "
        "a sync session"
    )
    assert (
        "Depends(get_db)" not in source
    ), "get_rbac_service still injects the async get_db via Depends(get_db)"
