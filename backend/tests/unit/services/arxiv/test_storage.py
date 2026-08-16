"""Tests for durable arXiv source storage."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.core.config import settings
from src.services.arxiv.storage import delete_arxiv_storage, store_arxiv_pdf


def test_local_backend_copies_pdf_into_upload_directory(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    source_path = cache_dir / "paper.pdf"
    source_path.write_bytes(b"%PDF-local")
    upload_dir = tmp_path / "uploads"
    document = SimpleNamespace(
        filename="paper.pdf",
        mime_type="application/pdf",
        document_metadata={"pdf_path": str(source_path)},
    )

    with (
        patch.object(settings, "STORAGE_BACKEND", "local"),
        patch.object(settings, "UPLOAD_DIR", str(upload_dir)),
    ):
        fields = store_arxiv_pdf(document, "org-1", "doc-1")

    stored_path = Path(str(fields["file_path"]))
    assert stored_path == upload_dir / "documents" / "org-1" / "doc-1" / "paper.pdf"
    assert stored_path.read_bytes() == source_path.read_bytes()
    assert stored_path != source_path


def test_ambiguous_s3_upload_failure_cleans_deterministic_key() -> None:
    document = SimpleNamespace(
        title="Paper",
        content_text="abstract",
        document_metadata={"arxiv_id": "2401.00001v1"},
    )
    helper = MagicMock()
    helper.upload_file.side_effect = RuntimeError("connection dropped after PUT")
    helper.delete_file.return_value = True

    with (
        patch.object(settings, "STORAGE_BACKEND", "s3"),
        patch("src.core.s3_client.S3StorageHelper", return_value=helper),
        pytest.raises(RuntimeError, match="connection dropped"),
    ):
        store_arxiv_pdf(document, "org-1", "doc-1")

    key = "documents/org-1/doc-1/2401.00001v1.txt"
    helper.upload_file.assert_called_once()
    helper.delete_file.assert_called_once_with(key)


def test_compensation_raises_when_backend_reports_delete_failure() -> None:
    helper = MagicMock()
    helper.delete_file.return_value = False

    with (
        patch("src.core.s3_client.S3StorageHelper", return_value=helper),
        pytest.raises(RuntimeError, match="failed to delete S3 object"),
    ):
        delete_arxiv_storage(
            {
                "storage_backend": "s3",
                "storage_path": "documents/org-1/doc-1/paper.pdf",
            }
        )
