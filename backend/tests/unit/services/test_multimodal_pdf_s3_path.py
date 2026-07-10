"""Regression: `MultimodalProcessingService.process_pdf` must not treat
`document.file_path` as a local path.

`process_pdf` used `fitz.open(document.file_path)` directly. On the deployed
s3 backend `document.file_path` is `s3://bucket/key`, which PyMuPDF cannot
open, raising and falling through to the pdfplumber fallback (which also
fails on the same path). `process_pdf` now wraps its body in
`local_file_for_document(document)`, which downloads s3 content to a temp
file first.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import fitz
import pytest

from src.services.processing import multimodal_processing_service as mod
from src.services.processing.multimodal_processing_service import (
    MultimodalProcessingService,
)

pytestmark = pytest.mark.unit


def _make_pdf(path: str) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "hello table world")
    doc.save(path)
    doc.close()


class _StubS3Helper:
    """Stands in for `S3StorageHelper`; `download_to_tempfile` hands back the
    on-disk PDF `local_pdf_path` was pointed at instead of hitting the network."""

    local_pdf_path: str = ""

    def __init__(self, *args, **kwargs):
        pass

    def download_to_tempfile(self, key: str, suffix: str = "") -> str:
        return _StubS3Helper.local_pdf_path


def _svc():
    # Skip __init__ (it wants a db session + service wiring); process_pdf only
    # touches its argument and module-level fitz.
    return object.__new__(MultimodalProcessingService)


@pytest.mark.asyncio
async def test_process_pdf_s3_document_extracts_text(monkeypatch, tmp_path):
    pdf_path = tmp_path / "x.pdf"
    _make_pdf(str(pdf_path))
    _StubS3Helper.local_pdf_path = str(pdf_path)

    monkeypatch.setattr("src.core.s3_client.S3StorageHelper", _StubS3Helper)
    # Isolate this test from the (unrelated) optional pdfplumber dependency —
    # process_pdf's primary path only needs fitz, which is installed.
    monkeypatch.setattr(mod, "OCR_AVAILABLE", True)

    s3_document = SimpleNamespace(
        storage_backend="s3",
        storage_path="org/doc/x.pdf",
        file_path="s3://b/org/doc/x.pdf",
        filename="x.pdf",
        id=uuid4(),
    )

    results = await _svc().process_pdf(s3_document, job=MagicMock())

    assert "hello table world" in results["text_content"]
    assert results["page_count"] == 1
