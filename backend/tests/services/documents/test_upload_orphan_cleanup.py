"""Regression: a commit failure after upload must not orphan the storage object.

EnhancedFileService.upload_file uploads the object BEFORE db.commit(). If the
commit fails, the old except only did rollback()+raise, orphaning the uploaded
object (and, with org-scoped content-hash dedup, a stale orphan can block
re-uploading the same content). The except now calls _best_effort_delete_object.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.services.documents.enhanced_file_service import EnhancedFileService


def _svc():
    # Skip __init__ (filesystem setup); we only exercise the cleanup helper.
    return object.__new__(EnhancedFileService)


@pytest.mark.unit
def test_s3_object_deleted_on_cleanup():
    svc = _svc()
    doc = MagicMock(storage_backend="s3", storage_path="documents/o/d/key.pdf")
    with patch("src.core.s3_client.S3StorageHelper") as MockHelper:
        svc._best_effort_delete_object(doc)
    MockHelper.return_value.delete_file.assert_called_once_with("documents/o/d/key.pdf")


@pytest.mark.unit
def test_local_object_deleted_on_cleanup():
    svc = _svc()
    doc = MagicMock(
        storage_backend="local",
        storage_path=None,
        file_path="/tmp/uploads/doc.pdf",
    )
    with (
        patch(
            "src.services.documents.enhanced_file_service.os.path.exists",
            return_value=True,
        ),
        patch("src.services.documents.enhanced_file_service.os.remove") as mock_remove,
    ):
        svc._best_effort_delete_object(doc)
    mock_remove.assert_called_once_with("/tmp/uploads/doc.pdf")


@pytest.mark.unit
def test_cleanup_never_raises():
    svc = _svc()
    doc = MagicMock(storage_backend="s3", storage_path="k")
    with patch("src.core.s3_client.S3StorageHelper") as MockHelper:
        MockHelper.return_value.delete_file.side_effect = RuntimeError("boom")
        # Must swallow — cleanup is best-effort and runs inside an except.
        svc._best_effort_delete_object(doc)
