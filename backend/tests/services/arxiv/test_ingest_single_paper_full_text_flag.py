"""Tests for honest full-text metadata on arXiv single-paper ingest.

`_ingest_single_paper` marks the document COMPLETED even when the PDF
download/extract fails — legitimate graceful degradation, since the
abstract/title/authors are still real content. But before this fix the
persisted metadata gave downstream consumers (and the agent) no way to tell an
abstract-only ingest apart from a full-text one, so the model could narrate "I
read the paper" over an abstract-only doc. These tests pin the honest-metadata
contract: `has_full_text` reflects reality on every path, and
`pdf_extraction_failed` is stamped only when the PDF path actually raised.
"""

import pytest

from src.models.document import ProcessingStatus
from src.services.arxiv.arxiv_service import ArXivIngestionService

pytestmark = pytest.mark.unit


def _paper() -> dict:
    return {
        "id": "1706.03762",
        "title": "Attention Is All You Need",
        "abstract": "We propose the Transformer, a model architecture.",
        "authors": ["Vaswani", "Shazeer"],
        "published": "2017-06-12T00:00:00Z",
        "categories": ["cs.CL"],
        "primary_category": "cs.CL",
        "links": {"pdf": "https://arxiv.org/pdf/1706.03762"},
    }


@pytest.mark.asyncio
async def test_full_text_success_sets_has_full_text_true(monkeypatch):
    svc = ArXivIngestionService()

    async def _fake_download(paper_id, url):
        return b"%PDF-1.4 fake bytes"

    async def _fake_extract(pdf_bytes):
        return {"full_text": "Full body text of the paper.", "num_pages": 11}

    monkeypatch.setattr(svc, "download_paper_pdf", _fake_download)
    monkeypatch.setattr(svc, "extract_pdf_content", _fake_extract)

    doc = await svc._ingest_single_paper(
        _paper(), download_pdfs=True, extract_content=True
    )

    assert doc.status == ProcessingStatus.COMPLETED
    md = doc.document_metadata
    assert md["has_full_text"] is True
    assert "pdf_extraction_failed" not in md
    assert md["num_pages"] == 11


@pytest.mark.asyncio
async def test_pdf_failure_keeps_completed_but_flags_metadata(monkeypatch):
    svc = ArXivIngestionService()

    async def _boom(paper_id, url):
        raise RuntimeError("PDF fetch 404")

    monkeypatch.setattr(svc, "download_paper_pdf", _boom)

    doc = await svc._ingest_single_paper(
        _paper(), download_pdfs=True, extract_content=True
    )

    # Graceful degradation: still COMPLETED, with the abstract preserved as
    # real content (this is why the doc stays COMPLETED, not FAILED).
    assert doc.status == ProcessingStatus.COMPLETED
    assert "We propose the Transformer" in doc.content_text
    md = doc.document_metadata
    assert md["has_full_text"] is False
    assert md["pdf_extraction_failed"] is True


@pytest.mark.asyncio
async def test_metadata_only_ingest_sets_has_full_text_false(monkeypatch):
    svc = ArXivIngestionService()

    # download_pdfs=False → PDF path skipped entirely; no failure, but also no
    # full text. has_full_text must still be recorded (False), and the failure
    # flag must NOT be set (nothing failed).
    doc = await svc._ingest_single_paper(
        _paper(), download_pdfs=False, extract_content=False
    )

    assert doc.status == ProcessingStatus.COMPLETED
    md = doc.document_metadata
    assert md["has_full_text"] is False
    assert "pdf_extraction_failed" not in md


@pytest.mark.asyncio
async def test_pdf_with_empty_extracted_text_is_not_full_text(monkeypatch):
    """PDF downloaded + extracted OK but the extract has no usable text
    (scanned/image PDF). No exception raised, but has_full_text stays False and
    no failure flag is stamped (extraction itself didn't fail)."""
    svc = ArXivIngestionService()

    async def _fake_download(paper_id, url):
        return b"%PDF-1.4 fake bytes"

    async def _fake_extract(pdf_bytes):
        return {"full_text": "", "num_pages": 3}

    monkeypatch.setattr(svc, "download_paper_pdf", _fake_download)
    monkeypatch.setattr(svc, "extract_pdf_content", _fake_extract)

    doc = await svc._ingest_single_paper(
        _paper(), download_pdfs=True, extract_content=True
    )

    md = doc.document_metadata
    assert md["has_full_text"] is False
    assert "pdf_extraction_failed" not in md
