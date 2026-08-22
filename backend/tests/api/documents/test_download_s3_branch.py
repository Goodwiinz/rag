"""Regression: GET /files/{id}/download must serve S3-backed documents inline.

Two faults are pinned here. First, download_file branched only on
storage_backend == 'supabase' and then fell through to
os.path.exists(document.file_path); S3 docs have file_path='s3://bucket/key',
which never exists on disk, so every S3-backed document 404'd — and S3 (DO
Spaces) is the deployed default. Second, the fix for that returned a 302 to a
presigned bucket URL, which a browser navigation can follow but the inline
viewer's fetch().blob() cannot: the bucket sends no Access-Control-Allow-Origin,
so the cross-origin redirect target is CORS-blocked. The endpoint now serves the
bytes from this origin.
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
    d.filename = "object.pdf"
    d.mime_type = "application/pdf"
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
def test_s3_document_is_served_from_this_origin():
    doc = _doc(mime_type="application/pdf", filename="paper.pdf")
    db = _db_returning(doc)
    org = MagicMock()
    org.id = "org-1"

    with patch("src.core.s3_client.S3StorageHelper") as MockHelper:
        MockHelper.return_value.object_exists.return_value = True
        MockHelper.return_value.download_file.return_value = b"%PDF-1.4 bytes"
        resp = asyncio.run(
            files_mod.download_file(
                "doc-1", current_user=MagicMock(), organization=org, db=db
            )
        )

    # Same-origin bytes, not a redirect the browser would CORS-block.
    assert resp.status_code == 200
    assert resp.body == b"%PDF-1.4 bytes"
    assert resp.media_type == "application/pdf"
    assert "paper.pdf" in resp.headers["content-disposition"]
    assert resp.headers["content-disposition"].startswith("attachment;")
    assert "location" not in resp.headers
    MockHelper.return_value.download_file.assert_called_once_with(doc.storage_path)


@pytest.mark.unit
def test_s3_missing_object_is_a_clean_404():
    doc = _doc()
    db = _db_returning(doc)
    org = MagicMock()
    org.id = "org-1"

    with patch("src.core.s3_client.S3StorageHelper") as MockHelper:
        MockHelper.return_value.object_exists.return_value = False
        with pytest.raises(Exception) as exc:
            asyncio.run(
                files_mod.download_file(
                    "doc-1", current_user=MagicMock(), organization=org, db=db
                )
            )

    assert getattr(exc.value, "status_code", None) == 404
    MockHelper.return_value.download_file.assert_not_called()


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
        MockHelper.return_value.object_exists.return_value = True
        MockHelper.return_value.download_file.return_value = b"bytes"
        asyncio.run(
            files_mod.download_file(
                "doc-1", current_user=MagicMock(), organization=org, db=db
            )
        )

    # The S3 path must NOT fall through to the on-disk existence check.
    mock_exists.assert_not_called()


@pytest.mark.unit
def test_scriptable_upload_is_served_as_opaque_download():
    """Stored HTML/SVG must not come back with its own type.

    The bytes are user-uploaded and are now served from the API's own origin
    rather than the bucket's, so echoing back text/html or image/svg+xml would
    be stored XSS against this origin.
    """
    for stored_type in ("text/html", "image/svg+xml", "application/xhtml+xml"):
        doc = _doc(mime_type=stored_type, filename="payload.html")
        db = _db_returning(doc)
        org = MagicMock()
        org.id = "org-1"

        with patch("src.core.s3_client.S3StorageHelper") as MockHelper:
            MockHelper.return_value.object_exists.return_value = True
            MockHelper.return_value.download_file.return_value = b"<script>x()</script>"
            resp = asyncio.run(
                files_mod.download_file(
                    "doc-1", current_user=MagicMock(), organization=org, db=db
                )
            )

        assert resp.media_type == "application/octet-stream", stored_type
        assert resp.headers["content-disposition"].startswith("attachment;")
        assert resp.headers["x-content-type-options"] == "nosniff"
        assert "sandbox" in resp.headers["content-security-policy"]
