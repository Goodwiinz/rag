"""Regression: GET /files/{id} must serve S3-backed documents.

download_file branched only on storage_backend == 'supabase' and then fell
through to os.path.exists(document.file_path); S3 docs have
file_path='s3://bucket/key', which never exists on disk, so every S3-backed
document 404'd — and S3 (DO Spaces) is the deployed default. The fix adds an
's3' branch that redirects to a presigned URL. This pins that branch.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.documents import files as files_mod


def _doc(**over):
    d = MagicMock()
    d.id = "doc-1"
    d.organization_id = "org-1"
    d.is_deleted = False
    d.storage_backend = "s3"
    d.storage_path = "documents/org-1/doc-1/object.pdf"
    d.file_path = "s3://rag-system-storage/documents/org-1/doc-1/object.pdf"
    for k, v in over.items():
        setattr(d, k, v)
    return d


def _db_returning(doc):
    db = MagicMock()
    result = MagicMock()
    result.scalars.return_value.first.return_value = doc
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.unit
def test_s3_document_redirects_to_presigned_url():
    doc = _doc()
    db = _db_returning(doc)
    org = MagicMock()
    org.id = "org-1"

    with patch("src.core.s3_client.S3StorageHelper") as MockHelper:
        MockHelper.return_value.create_signed_url.return_value = (
            "https://signed.example/x"
        )
        resp = asyncio.run(
            files_mod.download_file(
                "doc-1", current_user=MagicMock(), organization=org, db=db
            )
        )

    # 302 redirect to the presigned URL keyed by the stored object key.
    assert resp.status_code == 302
    assert resp.headers["location"] == "https://signed.example/x"
    MockHelper.return_value.create_signed_url.assert_called_once_with(
        doc.storage_path, expires_in=3600
    )


@pytest.mark.unit
def test_s3_branch_does_not_touch_local_disk():
    doc = _doc()
    db = _db_returning(doc)
    org = MagicMock()
    org.id = "org-1"

    with (
        patch("src.core.s3_client.S3StorageHelper") as MockHelper,
        patch("src.api.documents.files.os.path.exists") as mock_exists,
    ):
        MockHelper.return_value.create_signed_url.return_value = (
            "https://signed.example/y"
        )
        asyncio.run(
            files_mod.download_file(
                "doc-1", current_user=MagicMock(), organization=org, db=db
            )
        )

    # The S3 path must NOT fall through to the on-disk existence check.
    mock_exists.assert_not_called()
