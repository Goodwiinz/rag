"""Regression: thread export must eager-load every relationship it touches.

``has_attachments`` (chat_message.py) reads the ``attachments`` relationship;
when the export query didn't eager-load it, the async session hit a sync
lazy-load and raised MissingGreenlet ("greenlet_spawn has not been called") —
every POST /export/thread 500'd (Sentry JAVASCRIPT-NEXTJS-4Q, 2026-08-12).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.research.export_service import ExportOptions, ExportService


def _loaded_paths(stmt) -> set[str]:
    """Names of relationship paths the statement eager-loads."""
    paths: set[str] = set()
    for opt in stmt._with_options:
        path = getattr(opt, "path", None)
        if path is not None:
            paths.add(str(path))
    return paths


@pytest.mark.unit
@pytest.mark.asyncio
async def test_load_thread_eager_loads_attachments_and_citations():
    db = AsyncMock()
    result = MagicMock()
    result.unique.return_value.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)

    svc = ExportService(db)
    out = await svc._load_thread("t-1", "u-1", ExportOptions())
    assert out is None  # thread not found — fine, we only care about the query

    stmt = db.execute.call_args.args[0]
    paths = _loaded_paths(stmt)
    joined = " | ".join(paths)
    assert "attachments" in joined, joined
    assert "citations" in joined, joined
    assert "conversation" in joined, joined
