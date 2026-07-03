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
