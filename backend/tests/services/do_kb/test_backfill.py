"""Tests for backfill_org orchestration.

Uses fake session/state instead of a real DB. Verifies cursor advance,
resume from progress row, and dry-run side-effect freedom.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.do_kb.backfill import BackfillReport, _next_batch, backfill_org
from src.services.do_kb.backfill_model import DOKBBackfillProgress


class _FakeOrg:
    def __init__(self, org_id: str) -> None:
        self.id = org_id
        self.do_kb_uuid = "kb-1"
        self.is_active = True


class _FakeDoc:
    def __init__(self, doc_id: str) -> None:
        self.id = doc_id
        self.organization_id = "org-1"
        self.storage_backend = "s3"
        self.storage_path = f"docs/{doc_id}.pdf"
        self.content_text = None
        self.do_kb_data_source_uuid: str | None = None
        self.do_kb_indexed_at = None


class _FakeSession:
    """Tracks Documents + DOKBBackfillProgress + Organization in memory."""

    def __init__(
        self,
        org: _FakeOrg,
        documents: list[_FakeDoc],
    ) -> None:
        self._org = org
        self._documents = documents
        self._progress: DOKBBackfillProgress | None = None
        self.commits = 0

    async def get(self, model: Any, pk: Any):
        if model is DOKBBackfillProgress:
            return self._progress
        if hasattr(self._org, "id") and pk == self._org.id:
            return self._org
        return None

    def add(self, obj: Any) -> None:
        if isinstance(obj, DOKBBackfillProgress):
            self._progress = obj

    async def flush(self) -> None:
        return None

    async def execute(self, stmt: Any):  # noqa: ARG002 - we ignore SQL
        # Hand back a result-like that yields _next_batch results via
        # caller-driven monkeypatch of _next_batch in tests.
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        return result

    async def commit(self) -> None:
        self.commits += 1


@pytest.fixture
def stub_settings(monkeypatch):
    from src.services.do_kb import backfill as backfill_module
    from src.services.do_kb import ingest as ingest_module

    fake = MagicMock()
    fake.DO_KB_ENABLED = True
    fake.S3_BUCKET_NAME = "test-bucket"
    monkeypatch.setattr(backfill_module, "settings", fake)
    monkeypatch.setattr(ingest_module, "settings", fake)
    return fake


@pytest.mark.unit
@pytest.mark.asyncio
async def test_backfill_iterates_documents(stub_settings, monkeypatch):
    org = _FakeOrg("org-1")
    docs = [_FakeDoc(f"d{i:02d}") for i in range(3)]
    session = _FakeSession(org, docs)

    batches = [docs, []]

    async def fake_next_batch(*args, **kwargs):
        return batches.pop(0)

    monkeypatch.setattr(
        "src.services.do_kb.backfill._next_batch", fake_next_batch
    )

    sync_calls: list[str] = []

    async def fake_sync(session_, doc, *, client=None, trigger_indexing=True):
        sync_calls.append(doc.id)
        doc.do_kb_data_source_uuid = f"ds-{doc.id}"
        return doc.do_kb_data_source_uuid

    monkeypatch.setattr(
        "src.services.do_kb.backfill.sync_document_to_kb", fake_sync
    )
    monkeypatch.setattr(
        "src.services.do_kb.backfill.ensure_kb_for_org",
        AsyncMock(return_value="kb-1"),
    )

    api = MagicMock()
    api.start_indexing = AsyncMock()

    report = await backfill_org(session, org.id, batch_size=10, client=api)

    assert isinstance(report, BackfillReport)
    assert report.completed == 3
    assert report.failed == 0
    assert sync_calls == ["d00", "d01", "d02"]
    assert report.finished is True
    assert session._progress is not None
    assert session._progress.status == "completed"
    api.start_indexing.assert_awaited_once_with(kb_uuid="kb-1")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_backfill_dry_run_skips_external_calls(stub_settings, monkeypatch):
    org = _FakeOrg("org-1")
    docs = [_FakeDoc("d00"), _FakeDoc("d01")]
    session = _FakeSession(org, docs)

    batches = [docs, []]

    async def fake_next_batch(*args, **kwargs):
        return batches.pop(0)

    monkeypatch.setattr(
        "src.services.do_kb.backfill._next_batch", fake_next_batch
    )

    sync = AsyncMock()
    monkeypatch.setattr("src.services.do_kb.backfill.sync_document_to_kb", sync)
    ensure = AsyncMock(return_value="kb-1")
    monkeypatch.setattr("src.services.do_kb.backfill.ensure_kb_for_org", ensure)

    api = MagicMock()
    api.start_indexing = AsyncMock()

    report = await backfill_org(
        session, org.id, batch_size=10, dry_run=True, client=api
    )

    assert report.skipped == 2
    assert report.completed == 0
    sync.assert_not_called()
    ensure.assert_not_called()
    api.start_indexing.assert_not_called()
    assert session._progress.status == "dry_run_done"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_backfill_short_circuits_when_already_complete(stub_settings, monkeypatch):
    org = _FakeOrg("org-1")
    session = _FakeSession(org, [])
    session._progress = DOKBBackfillProgress(
        organization_id=org.id,
        completed_count=42,
        failed_count=0,
        status="completed",
    )

    sync = AsyncMock()
    monkeypatch.setattr("src.services.do_kb.backfill.sync_document_to_kb", sync)

    api = MagicMock()
    api.start_indexing = AsyncMock()

    report = await backfill_org(session, org.id, client=api)

    assert report.completed == 42
    assert report.finished is True
    sync.assert_not_called()
    api.start_indexing.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_backfill_raises_when_disabled(monkeypatch):
    from src.services.do_kb import backfill as backfill_module

    fake = MagicMock()
    fake.DO_KB_ENABLED = False
    monkeypatch.setattr(backfill_module, "settings", fake)

    session = _FakeSession(_FakeOrg("o"), [])

    with pytest.raises(RuntimeError):
        await backfill_org(session, "o")
