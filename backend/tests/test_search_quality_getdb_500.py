"""Guard: search_quality_service must not call the async get_db as a sync generator.

`get_db` became `async def get_db(request: Request)` (database.py), so
`next(get_db())` raises `TypeError: 'coroutine' object is not an iterator`.

In `SearchQualityService.get_quality_analytics` that call was the first statement
inside the try block, so it crashed on *every* request. The broad `except
Exception` swallowed the TypeError into `{"error": str(e)}`, and the mounted
endpoint (`GET /api/v1/search-quality/analytics`) turns any `"error"` key into
`raise HTTPException(status_code=500, ...)` -- so the analytics endpoint returned
HTTP 500 for all callers and never produced its analytics payload.

The session was never used (the method returns mock analytics), so the fix
removes the dead `with next(get_db()) as db:` context manager entirely rather
than swapping it for the sync `get_db_sync`. This source-level guard keeps the
broken pattern (and its now-unused import) from reappearing.
"""

from pathlib import Path

# tests/ -> backend/
SERVICE = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "services"
    / "search"
    / "search_quality_service.py"
)


def test_no_next_get_db_in_search_quality_service():
    source = SERVICE.read_text()
    assert "next(get_db())" not in source, (
        "search_quality_service calls next(get_db()); get_db is async, so this "
        "raises TypeError and 500s GET /api/v1/search-quality/analytics"
    )


def test_no_bare_get_db_import_in_search_quality_service():
    source = SERVICE.read_text()
    assert "from src.core.database import get_db" not in source, (
        "search_quality_service imports the async get_db; it no longer uses a DB "
        "session (mock analytics), so the import must stay removed"
    )
