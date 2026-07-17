"""Tests for durable arXiv source storage."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.core.config import settings
from src.services.arxiv.storage import store_arxiv_pdf


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
