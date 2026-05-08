"""Unit tests for sync_document_to_kb dual-write helper.

Failure isolation is the load-bearing property here: every external call
can fail and the helper must still return None gracefully without raising.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.do_kb.client import DOKnowledgeBaseError
from src.services.do_kb.models import DataSource, IndexingJob


class _FakeDoc:
    def __init__(
        self,
        *,
        doc_id: str = "doc-1",
        org_id: str = "org-1",
        storage_backend: str = "s3",
        storage_path: str = "documents/doc-1.pdf",
        content_text: str | None = None,
    ) -> None:
        self.id = doc_id
        self.organization_id = org_id
        self.storage_backend = storage_backend
        self.storage_path = storage_path
        self.content_text = content_text
        self.do_kb_data_source_uuid: str | None = None
        self.do_kb_indexed_at: datetime | None = None


class _FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


@pytest.fixture
def stub_settings(monkeypatch):
    from src.services.do_kb import ingest as ingest_module

    fake = MagicMock()
    fake.DO_KB_ENABLED = True
    fake.S3_BUCKET_NAME = "test-bucket"
    monkeypatch.setattr(ingest_module, "settings", fake)
    return fake


@pytest.mark.unit
@pytest.mark.asyncio
async def test_returns_none_when_disabled(monkeypatch):
    from src.services.do_kb import ingest as ingest_module
    from src.services.do_kb.ingest import sync_document_to_kb

    fake = MagicMock()
    fake.DO_KB_ENABLED = False
    monkeypatch.setattr(ingest_module, "settings", fake)

    result = await sync_document_to_kb(_FakeSession(), _FakeDoc())
    assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_returns_existing_uuid_when_already_synced(stub_settings):
    from src.services.do_kb.ingest import sync_document_to_kb

    doc = _FakeDoc()
    doc.do_kb_data_source_uuid = "ds-existing"

    client = MagicMock()
    result = await sync_document_to_kb(_FakeSession(), doc, client=client)

    assert result == "ds-existing"
    client.add_spaces_data_source.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_happy_path_uses_s3_source(stub_settings):
    from src.services.do_kb.ingest import sync_document_to_kb

    session = _FakeSession()
    doc = _FakeDoc()

    client = MagicMock()
    client.add_spaces_data_source = AsyncMock(
        return_value=DataSource(uuid="ds-fresh")
    )
    client.start_indexing = AsyncMock(
        return_value=IndexingJob(uuid="job-1", status="PENDING")
    )

    with patch(
        "src.services.do_kb.ingest.ensure_kb_for_org",
        AsyncMock(return_value="kb-1"),
    ):
        result = await sync_document_to_kb(session, doc, client=client)

    assert result == "ds-fresh"
    assert doc.do_kb_data_source_uuid == "ds-fresh"
    assert doc.do_kb_indexed_at is not None
    assert doc.do_kb_indexed_at.tzinfo == timezone.utc
    client.add_spaces_data_source.assert_awaited_once_with(
        kb_uuid="kb-1", bucket="test-bucket", key="documents/doc-1.pdf"
    )
    client.start_indexing.assert_awaited_once_with(kb_uuid="kb-1")
    assert session.commits == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_falls_back_to_text_upload_when_no_storage_path(stub_settings):
    from src.services.do_kb.ingest import sync_document_to_kb

    session = _FakeSession()
    doc = _FakeDoc(storage_backend="local", storage_path=None, content_text="hello")

    client = MagicMock()
    client.add_spaces_data_source = AsyncMock(
        return_value=DataSource(uuid="ds-text")
    )
    client.start_indexing = AsyncMock(
        return_value=IndexingJob(uuid="job-1")
    )

    helper = MagicMock()
    helper.bucket = "test-bucket"
    helper.upload_file = MagicMock(return_value="ok")

    with patch(
        "src.services.do_kb.ingest.ensure_kb_for_org",
        AsyncMock(return_value="kb-1"),
    ), patch(
        "src.core.s3_client.S3StorageHelper", return_value=helper
    ):
        result = await sync_document_to_kb(session, doc, client=client)

    assert result == "ds-text"
    helper.upload_file.assert_called_once()
    args, kwargs = client.add_spaces_data_source.call_args
    assert kwargs["bucket"] == "test-bucket"
    assert kwargs["key"] == f"do-kb-content/{doc.id}.txt"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_skips_when_no_source_available(stub_settings):
    from src.services.do_kb.ingest import sync_document_to_kb

    session = _FakeSession()
    doc = _FakeDoc(storage_backend="local", storage_path=None, content_text=None)

    client = MagicMock()
    client.add_spaces_data_source = AsyncMock()

    with patch(
        "src.services.do_kb.ingest.ensure_kb_for_org",
        AsyncMock(return_value="kb-1"),
    ):
        result = await sync_document_to_kb(session, doc, client=client)

    assert result is None
    client.add_spaces_data_source.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_provisioning_failure_is_swallowed(stub_settings):
    from src.services.do_kb.ingest import sync_document_to_kb

    session = _FakeSession()
    doc = _FakeDoc()

    client = MagicMock()
    client.add_spaces_data_source = AsyncMock()

    with patch(
        "src.services.do_kb.ingest.ensure_kb_for_org",
        AsyncMock(side_effect=DOKnowledgeBaseError("boom")),
    ):
        result = await sync_document_to_kb(session, doc, client=client)

    assert result is None
    client.add_spaces_data_source.assert_not_called()
    # Document untouched
    assert doc.do_kb_data_source_uuid is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_add_data_source_failure_is_swallowed(stub_settings):
    from src.services.do_kb.ingest import sync_document_to_kb

    session = _FakeSession()
    doc = _FakeDoc()

    client = MagicMock()
    client.add_spaces_data_source = AsyncMock(
        side_effect=DOKnowledgeBaseError("api 500")
    )
    client.start_indexing = AsyncMock()

    with patch(
        "src.services.do_kb.ingest.ensure_kb_for_org",
        AsyncMock(return_value="kb-1"),
    ):
        result = await sync_document_to_kb(session, doc, client=client)

    assert result is None
    client.start_indexing.assert_not_called()
    assert session.commits == 0
    assert doc.do_kb_data_source_uuid is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_indexing_kick_failure_does_not_fail_sync(stub_settings):
    from src.services.do_kb.ingest import sync_document_to_kb

    session = _FakeSession()
    doc = _FakeDoc()

    client = MagicMock()
    client.add_spaces_data_source = AsyncMock(
        return_value=DataSource(uuid="ds-1")
    )
    client.start_indexing = AsyncMock(side_effect=DOKnowledgeBaseError("queue full"))

    with patch(
        "src.services.do_kb.ingest.ensure_kb_for_org",
        AsyncMock(return_value="kb-1"),
    ):
        result = await sync_document_to_kb(session, doc, client=client)

    # Sync still succeeds — indexing is fire-and-forget.
    assert result == "ds-1"
    assert doc.do_kb_data_source_uuid == "ds-1"
    assert session.commits == 1
