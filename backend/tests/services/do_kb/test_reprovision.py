"""Tests for --reprovision recovery (deleted-KB restore).

Codifies the manual surgery from the deleted-KB incident: when an org's DO KB
is gone on DO's side, ``reprovision_org`` must null the org's cached uuid +
every non-deleted doc's data-source uuid + reset progress BEFORE backfill runs,
so backfill provisions a fresh KB. Uses fake session/state (no real DB).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from scripts import backfill_do_kb
from src.services.do_kb.backfill import ReprovisionResult, reprovision_org
from src.services.do_kb.backfill_model import DOKBBackfillProgress


class _FakeOrg:
    def __init__(self, org_id: str) -> None:
        self.id = org_id
        self.do_kb_uuid: str | None = "dead-kb-uuid"
        self.do_kb_provisioned_at: Any = "2026-01-01T00:00:00Z"


class _FakeDoc:
    def __init__(self, doc_id: str, *, is_deleted: bool = False) -> None:
        self.id = doc_id
        self.organization_id = "org-1"
        self.is_deleted = is_deleted
        self.do_kb_data_source_uuid: str | None = f"dead-ds-{doc_id}"
        self.do_kb_indexed_at: Any = "2026-01-01T00:00:00Z"
        self.do_kb_index_status: str | None = "indexed"


class _FakeSession:
    """In-memory org + docs + progress. Applies the bulk Document UPDATE from
    reprovision_org to the matching in-memory docs (non-deleted, uuid set)."""

    def __init__(self, org: _FakeOrg, documents: list[_FakeDoc]) -> None:
        self._org = org
        self._documents = documents
        self._progress: DOKBBackfillProgress | None = None
        self.commits = 0

    async def get(self, model: Any, pk: Any):
        if model is DOKBBackfillProgress:
            return self._progress
        if pk == self._org.id:
            return self._org
        return None

    def add(self, obj: Any) -> None:
        if isinstance(obj, DOKBBackfillProgress):
            self._progress = obj

    async def flush(self) -> None:
        return None

    async def execute(self, stmt: Any):
        # Emulate the bulk `update(Document)...values(...)` reset: apply to every
        # non-deleted doc that still has a data-source uuid, count them.
        reset = 0
        for doc in self._documents:
            if not doc.is_deleted and doc.do_kb_data_source_uuid is not None:
                doc.do_kb_data_source_uuid = None
                doc.do_kb_indexed_at = None
                doc.do_kb_index_status = None
                reset += 1
        result = MagicMock()
        result.rowcount = reset
        return result

    async def commit(self) -> None:
        self.commits += 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_reprovision_nulls_org_docs_and_progress():
    org = _FakeOrg("org-1")
    docs = [_FakeDoc("d00"), _FakeDoc("d01"), _FakeDoc("d02")]
    session = _FakeSession(org, docs)

    result = await reprovision_org(session, org.id)

    assert isinstance(result, ReprovisionResult)
    assert result.old_kb_uuid == "dead-kb-uuid"
    assert result.docs_reset == 3

    # Org uuid + provisioned_at cleared → ensure_kb_for_org will provision fresh.
    assert org.do_kb_uuid is None
    assert org.do_kb_provisioned_at is None

    # Every doc's dead KB state nulled → backfill re-adds them.
    for doc in docs:
        assert doc.do_kb_data_source_uuid is None
        assert doc.do_kb_indexed_at is None
        assert doc.do_kb_index_status is None

    # Progress reset so the batch loop re-processes everything.
    assert session._progress is not None
    assert session._progress.status == "pending"
    assert session._progress.last_document_id is None
    assert session._progress.completed_count == 0
    assert session._progress.failed_count == 0
    assert session.commits == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_reprovision_skips_deleted_docs():
    org = _FakeOrg("org-1")
    docs = [_FakeDoc("d00"), _FakeDoc("d01", is_deleted=True)]
    session = _FakeSession(org, docs)

    result = await reprovision_org(session, org.id)

    # Only the live doc is reset; the deleted one keeps its (dead) uuid untouched.
    assert result.docs_reset == 1
    assert docs[0].do_kb_data_source_uuid is None
    assert docs[1].do_kb_data_source_uuid == "dead-ds-d01"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_reprovision_missing_org_raises():
    session = _FakeSession(_FakeOrg("org-1"), [])
    with pytest.raises(ValueError):
        await reprovision_org(session, "nonexistent-org")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cli_reprovision_resets_before_backfill(monkeypatch):
    """The CLI must call reprovision_org (nulling org uuid + doc uuids +
    progress) BEFORE backfill_org for the target org."""
    org = _FakeOrg("org-1")
    docs = [_FakeDoc("d00"), _FakeDoc("d01")]
    session = _FakeSession(org, docs)

    call_order: list[str] = []

    async def spy_reprovision(session_, org_id):
        call_order.append("reprovision")
        return await reprovision_org(session_, org_id)

    async def fake_backfill_org(session_, org_id, **kwargs):
        call_order.append("backfill")
        # By the time backfill runs, the reset must already be applied.
        assert org.do_kb_uuid is None
        assert all(d.do_kb_data_source_uuid is None for d in docs)
        assert session_._progress.status == "pending"
        return backfill_do_kb.BackfillReport(
            organization_id=org_id,
            completed=2,
            failed=0,
            skipped=0,
            last_document_id="d01",
            finished=True,
            indexing_started=True,
        )

    # DO_KB must be enabled for _run to proceed.
    fake_settings = MagicMock()
    fake_settings.DO_KB_ENABLED = True
    monkeypatch.setattr(backfill_do_kb, "settings", fake_settings)
    monkeypatch.setattr(backfill_do_kb, "reprovision_org", spy_reprovision)
    monkeypatch.setattr(backfill_do_kb, "backfill_org", fake_backfill_org)

    # AsyncSessionLocal() used as an async context manager yielding our session.
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(backfill_do_kb, "AsyncSessionLocal", lambda: cm)

    args = MagicMock()
    args.org_id = "org-1"
    args.reprovision = True
    args.dry_run = False
    args.yes = False
    args.batch_size = 25

    rc = await backfill_do_kb._run(args)

    assert rc == 0
    assert call_order == ["reprovision", "backfill"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cli_reprovision_all_without_yes_refused(monkeypatch):
    """--reprovision --all (no --org-id) without --yes is destructive → refuse."""
    fake_settings = MagicMock()
    fake_settings.DO_KB_ENABLED = True
    monkeypatch.setattr(backfill_do_kb, "settings", fake_settings)

    backfill_spy = AsyncMock()
    reprovision_spy = AsyncMock()
    monkeypatch.setattr(backfill_do_kb, "backfill_org", backfill_spy)
    monkeypatch.setattr(backfill_do_kb, "reprovision_org", reprovision_spy)

    args = MagicMock()
    args.org_id = None
    args.reprovision = True
    args.dry_run = False
    args.yes = False
    args.batch_size = 25

    rc = await backfill_do_kb._run(args)

    assert rc == 2
    backfill_spy.assert_not_called()
    reprovision_spy.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cli_reprovision_with_dry_run_refused(monkeypatch):
    """--reprovision mutates state; combining with --dry-run is contradictory."""
    fake_settings = MagicMock()
    fake_settings.DO_KB_ENABLED = True
    monkeypatch.setattr(backfill_do_kb, "settings", fake_settings)

    reprovision_spy = AsyncMock()
    monkeypatch.setattr(backfill_do_kb, "reprovision_org", reprovision_spy)

    args = MagicMock()
    args.org_id = "org-1"
    args.reprovision = True
    args.dry_run = True
    args.yes = False
    args.batch_size = 25

    rc = await backfill_do_kb._run(args)

    assert rc == 2
    reprovision_spy.assert_not_called()
