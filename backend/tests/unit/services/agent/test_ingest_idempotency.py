"""Re-ingesting a paper the org already has must reuse it, not kill the batch.

Live failure (dev, 2026-07-26), on a clean single-job run::

    asyncpg.exceptions.UniqueViolationError: duplicate key value violates
    unique constraint "uq_documents_org_checksum_live"
    DETAIL: Key (organization_id, checksum_sha256)=(1d759a12-…, bdfaa68d…)
            already exists.

``documents`` already held that paper — "Attention Is All You Need", ingested
2026-07-18 with a valid s3 ``storage_path``. Content-hash dedup did its job;
the ingest tool had no answer for it. Because the batch commits inside one
atomic ``begin()``, the violation destroyed **every** paper in the request, so
one familiar paper would lose nine new ones.

The user asked for the paper to be in their library. It is. That is success —
and the project link still has to happen, which is why the reused id is
appended to ``document_ids`` rather than dropped.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

pytestmark = pytest.mark.unit


class _Result:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value


class _DB:
    """Captures the statement so we can assert what was filtered on."""

    def __init__(self, found: Any) -> None:
        self.found = found
        self.executed: list[Any] = []

    async def execute(self, stmt: Any) -> _Result:
        self.executed.append(stmt)
        return _Result(self.found)


async def test_existing_copy_is_found_by_org_and_checksum() -> None:
    from src.services.agent.tools_impl import _existing_document_id

    existing = uuid4()
    db = _DB(found=existing)

    got = await _existing_document_id(db, uuid4(), "abc123")

    assert got == existing
    sql = str(db.executed[0]).lower()
    assert "organization_id" in sql, "dedup is per-tenant; org must be filtered"
    assert "checksum_sha256" in sql
    assert "is_deleted" in sql, (
        "the unique index is partial (live rows only) — a soft-deleted copy "
        "must not block a re-ingest"
    )


async def test_no_existing_copy_returns_none() -> None:
    from src.services.agent.tools_impl import _existing_document_id

    assert await _existing_document_id(_DB(found=None), uuid4(), "abc123") is None


async def test_missing_checksum_skips_the_lookup_entirely() -> None:
    """No checksum means nothing to collide with; don't spend a query."""
    from src.services.agent.tools_impl import _existing_document_id

    db = _DB(found=uuid4())

    assert await _existing_document_id(db, uuid4(), None) is None
    assert await _existing_document_id(db, uuid4(), "") is None
    assert db.executed == []


def test_the_constraint_this_mirrors_still_exists() -> None:
    """If the index is renamed or dropped, this guard silently stops matching."""
    from pathlib import Path

    migration = (
        Path(__file__).resolve().parents[4]
        / "alembic"
        / "versions"
        / "uq_documents_org_checksum.py"
    )
    text = migration.read_text()
    assert "uq_documents_org_checksum_live" in text
    assert "organization_id" in text and "checksum_sha256" in text
