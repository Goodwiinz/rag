"""Unit tests for the DO KB document repair script."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.unit
@pytest.mark.asyncio
async def test_repair_document_unsyncs_and_resyncs():
    """repair_document calls unsync then sync when content_text exists."""
    doc_id = uuid.uuid4()

    # Mock the document
    mock_doc = MagicMock()
    mock_doc.id = doc_id
    mock_doc.title = "Test PDF"
    mock_doc.content_text = "existing text"
    mock_doc.do_kb_data_source_uuid = "ds-old"
    mock_doc.do_kb_indexed_at = None
    mock_doc.is_embedded = False

    # Mock the session
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=mock_doc)
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "src.core.database.AsyncSessionLocal",
            return_value=mock_ctx,
        ),
        patch(
            "src.services.do_kb.unsync_document_from_kb",
            new=AsyncMock(return_value=True),
        ) as unsync_mock,
        patch(
            "src.services.do_kb.sync_document_to_kb",
            new=AsyncMock(return_value="ds-new"),
        ) as sync_mock,
    ):
        import scripts.maintenance.repair_do_kb_document as mod

        result = await mod.repair_document(str(doc_id))

    assert result["status"] == "repaired"
    assert result["new_ds_uuid"] == "ds-new"
    unsync_mock.assert_awaited_once()
    sync_mock.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_repair_document_stops_when_unsync_fails():
    doc_id = uuid.uuid4()
    mock_doc = MagicMock(
        id=doc_id,
        title="Test PDF",
        content_text="existing text",
        do_kb_data_source_uuid="ds-old",
    )
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=mock_doc)
    mock_session.refresh = AsyncMock()
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    sync_mock = AsyncMock()

    with (
        patch("src.core.database.AsyncSessionLocal", return_value=mock_ctx),
        patch(
            "src.services.do_kb.unsync_document_from_kb",
            new=AsyncMock(return_value=False),
        ),
        patch("src.services.do_kb.sync_document_to_kb", new=sync_mock),
    ):
        import scripts.maintenance.repair_do_kb_document as mod

        result = await mod.repair_document(str(doc_id))

    assert result["status"] == "unsync_failed"
    mock_session.refresh.assert_not_awaited()
    sync_mock.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_repair_document_not_found():
    """repair_document returns not_found for missing document."""
    doc_id = uuid.uuid4()

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=None)

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("src.core.database.AsyncSessionLocal", return_value=mock_ctx):
        import scripts.maintenance.repair_do_kb_document as mod

        result = await mod.repair_document(str(doc_id))

    assert result["status"] == "not_found"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_repair_document_dry_run():
    """repair_document in dry-run mode doesn't call unsync/sync."""
    doc_id = uuid.uuid4()

    mock_doc = MagicMock()
    mock_doc.id = doc_id
    mock_doc.title = "Test PDF"
    mock_doc.content_text = "existing text"
    mock_doc.do_kb_data_source_uuid = "ds-old"

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=mock_doc)
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("src.core.database.AsyncSessionLocal", return_value=mock_ctx),
        patch(
            "src.services.do_kb.unsync_document_from_kb",
            new=AsyncMock(),
        ) as unsync_mock,
        patch(
            "src.services.do_kb.sync_document_to_kb",
            new=AsyncMock(),
        ) as sync_mock,
    ):
        import scripts.maintenance.repair_do_kb_document as mod

        result = await mod.repair_document(str(doc_id), dry_run=True)

    assert result["status"] == "dry_run"
    unsync_mock.assert_not_awaited()
    sync_mock.assert_not_awaited()
