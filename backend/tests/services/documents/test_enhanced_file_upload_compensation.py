"""Regression: EnhancedFileService.upload_file must compensate a post-commit
failure the same way the canonical FileService does (audit B3 / P4.4).

The storage object is committed BEFORE the DB rows, and the DB writes span two
commits (the document row, then the org quota update). If the SECOND commit
fails, the document row is already live: a bare rollback leaves a PENDING row
whose content hash blocks re-upload (uq_documents_org_checksum_live), and
deleting the object then strands that row from its backing file.

The fix mirrors FileService.upload_file: soft-delete the committed row first,
and delete the storage object only if that reversal succeeds.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.document import DocumentType
from src.services.documents.enhanced_file_service import (
    EnhancedFileService,
    FileStorageError,
)


def _service():
    # Bypass __init__ (touches the filesystem); wire only what upload_file uses.
    svc = object.__new__(EnhancedFileService)
    svc.db = MagicMock()
    svc._storage_backend = "s3"
    # s3_helper / storage_helper are lazy properties backed by these fields.
    svc._s3_helper = MagicMock()
    svc._storage_helper = MagicMock()
    # No pre-existing duplicate — exercise the happy insert path up to the commit.
    svc._find_org_duplicate = MagicMock(return_value=None)
    svc._best_effort_delete_object = MagicMock()
    return svc


def _upload_args():
    file = MagicMock()
    file.filename = "paper.pdf"
    file.read = AsyncMock(return_value=b"content-bytes")
    file.file = MagicMock()

    user = MagicMock()
    user.id = uuid.uuid4()
    organization = MagicMock()
    organization.id = uuid.uuid4()

    validation_result = {
        "basic_validation": {
            "detected_mime_type": "application/pdf",
            "document_type": DocumentType.PDF,
            "file_size": 123,
        },
        "security_scan": {"ok": True},
        "integrity_check": {"ok": True},
    }
    return dict(
        file=file,
        title="Paper",
        description=None,
        user=user,
        organization=organization,
        tags=[],
        is_public=False,
        custom_metadata={},
        validation_result=validation_result,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_post_commit_failure_soft_deletes_row_then_deletes_object():
    svc = _service()
    # commit #1 (document row) succeeds → row is live; commit #2 (quota) fails;
    # commit #3 (reversal soft-delete) succeeds.
    svc.db.commit.side_effect = [None, RuntimeError("quota commit failed"), None]

    with pytest.raises(FileStorageError):
        await svc.upload_file(**_upload_args())

    # The uploaded object must be compensated (no orphan object).
    assert svc._best_effort_delete_object.call_count == 1
    doc = svc._best_effort_delete_object.call_args.args[0]
    # The committed PENDING row must be reversed so the content hash no longer
    # blocks re-upload (uq_documents_org_checksum_live is WHERE is_deleted=false).
    assert doc.is_deleted is True
    # Reversal ran on its own commit (3 total: row, failed quota, reversal).
    assert svc.db.commit.call_count == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_reversal_failure_keeps_object_as_sweepable_orphan():
    svc = _service()
    # Both the quota commit AND the reversal commit fail: we must NOT delete the
    # object, or we would strand a still-live PENDING row from its backing file.
    svc.db.commit.side_effect = [
        None,
        RuntimeError("quota commit failed"),
        RuntimeError("reversal commit failed"),
    ]

    with pytest.raises(FileStorageError):
        await svc.upload_file(**_upload_args())

    svc._best_effort_delete_object.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pre_commit_failure_deletes_object():
    svc = _service()
    # The FIRST commit (document row) fails — the row never went live, so the
    # object is safe to delete outright.
    svc.db.commit.side_effect = [RuntimeError("insert failed")]

    with pytest.raises(FileStorageError):
        await svc.upload_file(**_upload_args())

    assert svc._best_effort_delete_object.call_count == 1
