"""Unit tests for the DO KB pre-flight PDF guard."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.services.do_kb.pre_flight import should_force_text_extraction


def _cfg(pages: int = 100, size_mb: int = 5) -> SimpleNamespace:
    return SimpleNamespace(
        DO_KB_FORCE_TEXT_PDF_PAGES=pages,
        DO_KB_FORCE_TEXT_PDF_SIZE_MB=size_mb,
    )


def _pdf(*, size_bytes: int, page_count, content_text=None) -> MagicMock:
    doc = MagicMock()
    doc.document_type.value = "pdf"
    doc.file_size_bytes = size_bytes
    doc.page_count = page_count
    doc.content_text = content_text
    return doc


@pytest.mark.unit
def test_force_when_over_size_threshold():
    """PDF over the size threshold (page_count absent) is flagged."""
    doc = _pdf(size_bytes=6 * 1024 * 1024, page_count=None)  # 6 MB
    assert should_force_text_extraction(doc, _cfg()) is True


@pytest.mark.unit
def test_force_when_over_page_threshold():
    """PDF under size but over the page threshold is flagged."""
    doc = _pdf(size_bytes=1 * 1024 * 1024, page_count=150)  # 1 MB, 150 pages
    assert should_force_text_extraction(doc, _cfg()) is True


@pytest.mark.unit
def test_no_force_when_already_has_content_text():
    """Existing content_text means no extraction needed, even for a huge PDF."""
    doc = _pdf(size_bytes=50 * 1024 * 1024, page_count=500, content_text="done")
    assert should_force_text_extraction(doc, _cfg()) is False


@pytest.mark.unit
def test_no_force_for_non_pdf():
    """Non-PDF documents are never flagged."""
    doc = MagicMock()
    doc.document_type.value = "txt"
    doc.file_size_bytes = 100
    doc.page_count = None
    doc.content_text = None
    assert should_force_text_extraction(doc, _cfg()) is False


@pytest.mark.unit
def test_no_force_when_under_both_thresholds():
    """Small PDF under both thresholds is not flagged."""
    doc = _pdf(size_bytes=2 * 1024 * 1024, page_count=30)  # 2 MB, 30 pages
    assert should_force_text_extraction(doc, _cfg()) is False


def _minimal_pdf_bytes(text: str) -> bytes:
    """Smallest valid PDF that pypdf can extract ``text`` from."""
    content = b"BT /F1 12 Tf 20 100 Td (%s) Tj ET\n" % text.encode()
    objs = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]"
        b"/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
        b"<</Length %d>>stream\n" % len(content) + content + b"endstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objs) + 1,
        xref,
    )
    return bytes(out)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_content_text_actually_extracts(tmp_path):
    """R2-H4: the forced-extraction path must run and populate content_text.

    Regressed on `FileService()` (missing required `db`), whose TypeError the
    broad except swallowed — so this path silently never ran.
    """
    from src.models.document import DocumentType
    from src.services.do_kb.pre_flight import ensure_content_text_for_kb

    pdf_path = tmp_path / "big.pdf"
    pdf_path.write_bytes(_minimal_pdf_bytes("PREFLIGHT OK"))

    doc = SimpleNamespace(
        id="doc-1",
        document_type=DocumentType.PDF,
        content_text=None,
        page_count=None,
        file_size_bytes=50 * 1024 * 1024,  # over the size threshold
        filename="big.pdf",
        storage_backend="local",
        file_path=str(pdf_path),
    )

    assert await ensure_content_text_for_kb(doc) is True
    assert "PREFLIGHT OK" in (doc.content_text or "")
