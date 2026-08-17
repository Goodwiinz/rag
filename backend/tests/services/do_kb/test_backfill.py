"""Tests for backfill_org orchestration.

Uses fake session/state instead of a real DB. Verifies cursor advance,
resume from progress row, and dry-run side-effect freedom.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.document import ProcessingStatus
from src.services.do_kb.backfill import BackfillReport, _next_batch, backfill_org
from src.services.do_kb.backfill_model import DOKBBackfillProgress


class _FakeOrg:
    def __init__(self, org_id: str) -> None:
        self.id = org_id
        self.do_kb_uuid = "kb-1"
        self.is_active = True


class _FakeDoc:
    def __init__(self, doc_id: str, *, is_deleted: bool = False) -> None:
        self.id = doc_id
        self.organization_id = "org-1"
        self.storage_backend = "s3"
        self.storage_path = f"docs/{doc_id}.pdf"
        self.content_text = None
        self.do_kb_data_source_uuid: str | None = None
        self.do_kb_indexed_at = None
        self.do_kb_sync_status: str | None = None
        self.is_deleted = is_deleted
        self.processing_status = ProcessingStatus.COMPLETED


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

    monkeypatch.setattr("src.services.do_kb.backfill._next_batch", fake_next_batch)

    sync_calls: list[str] = []

    async def fake_sync(session_, doc, *, client=None, trigger_indexing=True):
        sync_calls.append(doc.id)
        doc.do_kb_data_source_uuid = f"ds-{doc.id}"
        return doc.do_kb_data_source_uuid

    monkeypatch.setattr("src.services.do_kb.backfill.sync_document_to_kb", fake_sync)
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

    monkeypatch.setattr("src.services.do_kb.backfill._next_batch", fake_next_batch)

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
    # R2-M19: dry-run must never write/commit the progress row.
    assert session._progress is None
    assert session.commits == 0
    # Dry-run never attempts the kick → CLI warning must not fire.
    assert report.indexing_attempted is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_backfill_short_circuits_when_already_complete(
    stub_settings, monkeypatch
):
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
    # Idempotent re-run: no kick attempted this run, so the CLI must NOT emit
    # the "not queryable" warning despite completed>0 + indexing_started=False.
    assert report.indexing_attempted is False
    assert report.indexing_started is False


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


@pytest.mark.unit
@pytest.mark.asyncio
async def test_backfill_commits_once_per_batch_not_per_doc(stub_settings, monkeypatch):
    """Audit A2: a batch of N docs must produce ONE commit, not N. Total commits =
    in_progress(1) + per-batch(1) + final(1) = 3 for a single 3-doc batch."""
    org = _FakeOrg("org-1")
    docs = [_FakeDoc(f"d{i:02d}") for i in range(3)]
    session = _FakeSession(org, docs)

    batches = [docs, []]

    async def fake_next_batch(*args, **kwargs):
        return batches.pop(0)

    async def fake_sync(session_, doc, *, client=None, trigger_indexing=True):
        doc.do_kb_data_source_uuid = f"ds-{doc.id}"
        return doc.do_kb_data_source_uuid

    monkeypatch.setattr("src.services.do_kb.backfill._next_batch", fake_next_batch)
    monkeypatch.setattr("src.services.do_kb.backfill.sync_document_to_kb", fake_sync)
    monkeypatch.setattr(
        "src.services.do_kb.backfill.ensure_kb_for_org",
        AsyncMock(return_value="kb-1"),
    )

    api = MagicMock()
    api.start_indexing = AsyncMock()

    await backfill_org(session, org.id, batch_size=10, client=api)

    # 3 docs in one batch → 3 commits (NOT 5 = 1+3+1 the old per-doc path).
    assert session.commits == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_backfill_reports_indexing_not_started_when_kick_fails(
    stub_settings, monkeypatch
):
    """FIX C1: when the final start_indexing kick raises, the report must say
    indexing_started=False even though completed>0 — data sources uploaded but
    docs are NOT queryable yet. Status still flips to 'completed' (resumable)."""
    org = _FakeOrg("org-1")
    docs = [_FakeDoc(f"d{i:02d}") for i in range(2)]
    session = _FakeSession(org, docs)

    batches = [docs, []]

    async def fake_next_batch(*args, **kwargs):
        return batches.pop(0)

    async def fake_sync(session_, doc, *, client=None, trigger_indexing=True):
        doc.do_kb_data_source_uuid = f"ds-{doc.id}"
        return doc.do_kb_data_source_uuid

    monkeypatch.setattr("src.services.do_kb.backfill._next_batch", fake_next_batch)
    monkeypatch.setattr("src.services.do_kb.backfill.sync_document_to_kb", fake_sync)
    monkeypatch.setattr(
        "src.services.do_kb.backfill.ensure_kb_for_org",
        AsyncMock(return_value="kb-1"),
    )

    api = MagicMock()
    # The indexing kick 400s — the incident this fix prevents.
    api.start_indexing = AsyncMock(side_effect=RuntimeError("400 Bad Request"))

    report = await backfill_org(session, org.id, batch_size=10, client=api)

    assert report.completed == 2
    assert report.failed == 0
    assert report.indexing_started is False
    # The kick was attempted and failed — this IS the case the CLI warns on.
    assert report.indexing_attempted is True
    # Resumability preserved: status is still 'completed', not a failure state.
    assert session._progress.status == "completed"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_backfill_reports_indexing_started_on_success(stub_settings, monkeypatch):
    """Happy path: a successful kick reports indexing_started=True."""
    org = _FakeOrg("org-1")
    docs = [_FakeDoc("d00")]
    session = _FakeSession(org, docs)

    batches = [docs, []]

    async def fake_next_batch(*args, **kwargs):
        return batches.pop(0)

    async def fake_sync(session_, doc, *, client=None, trigger_indexing=True):
        doc.do_kb_data_source_uuid = f"ds-{doc.id}"
        return doc.do_kb_data_source_uuid

    monkeypatch.setattr("src.services.do_kb.backfill._next_batch", fake_next_batch)
    monkeypatch.setattr("src.services.do_kb.backfill.sync_document_to_kb", fake_sync)
    monkeypatch.setattr(
        "src.services.do_kb.backfill.ensure_kb_for_org",
        AsyncMock(return_value="kb-1"),
    )

    api = MagicMock()
    api.start_indexing = AsyncMock()

    report = await backfill_org(session, org.id, batch_size=10, client=api)

    assert report.completed == 1
    assert report.indexing_started is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_next_batch_excludes_deleted_and_non_completed_docs(stub_settings):
    """R2-H11: _next_batch must mirror reprovision_org's is_deleted filter plus
    only select COMPLETED docs — otherwise soft-deleted or PENDING/FAILED docs
    get ingested into DO KB and stay retrievable after the user deleted them."""

    class _CaptureSession:
        async def execute(self, stmt):
            self.stmt = stmt
            result = MagicMock()
            result.scalars.return_value.all.return_value = []
            return result

    session = _CaptureSession()
    await _next_batch(session, "org-1", after_document_id=None, batch_size=10)

    compiled = str(session.stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "is_deleted" in compiled
    assert "processing_status" in compiled


@pytest.mark.unit
@pytest.mark.asyncio
async def test_backfill_marks_failed_doc_sync_status(stub_settings, monkeypatch):
    """R2-M20: a per-doc sync failure must be recorded on the document
    (do_kb_sync_status='failed') so the scheduled reconciler re-drives it —
    otherwise the cursor advances past it and a re-run short-circuits on
    status='completed', permanently skipping the doc."""
    org = _FakeOrg("org-1")
    good = _FakeDoc("d00")
    bad = _FakeDoc("d01")
    docs = [good, bad]
    session = _FakeSession(org, docs)

    batches = [docs, []]

    async def fake_next_batch(*args, **kwargs):
        return batches.pop(0)

    async def fake_sync(session_, doc, *, client=None, trigger_indexing=True):
        if doc.id == "d00":
            doc.do_kb_data_source_uuid = "ds-d00"
            return "ds-d00"
        return None

    monkeypatch.setattr("src.services.do_kb.backfill._next_batch", fake_next_batch)
    monkeypatch.setattr("src.services.do_kb.backfill.sync_document_to_kb", fake_sync)
    monkeypatch.setattr(
        "src.services.do_kb.backfill.ensure_kb_for_org",
        AsyncMock(return_value="kb-1"),
    )

    api = MagicMock()
    api.start_indexing = AsyncMock()

    report = await backfill_org(session, org.id, batch_size=10, client=api)

    assert report.completed == 1
    assert report.failed == 1
    assert bad.do_kb_sync_status == "failed"
    assert good.do_kb_sync_status is None
    # Distinct status so a re-run doesn't short-circuit past the failed doc.
    assert session._progress.status == "completed_with_failures"
