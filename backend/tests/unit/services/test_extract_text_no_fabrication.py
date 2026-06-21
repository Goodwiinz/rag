"""Regression: text extraction fails loudly instead of indexing an error string.

extract_text_content / _extract_text_from_path previously returned
"Error extracting text: ..." (or "Spreadsheet processing not available") on
failure, which the pipeline stored as document.content_text and marked the doc
COMPLETED/indexed. Failures must raise (so the doc is failed); capability gaps
return "" (empty), never a fabricated content string.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.models.document import DocumentType
from src.services.documents import file_service as fs_mod
from src.services.documents.file_service import FileService


def _svc():
    return FileService(db=None)


@pytest.mark.unit
def test_text_extraction_failure_raises_not_error_string():
    svc = _svc()
    doc = SimpleNamespace(id="d1", document_type=DocumentType.TEXT)
    # Nonexistent path → open() raises → must propagate, not return a string.
    with pytest.raises(Exception):
        svc._extract_text_from_path("/no/such/file.txt", doc)


@pytest.mark.unit
def test_spreadsheet_capability_gap_returns_empty_not_string():
    svc = _svc()
    doc = SimpleNamespace(id="d2", document_type=DocumentType.SPREADSHEET)
    with patch.object(fs_mod, "PANDAS_AVAILABLE", False):
        result = svc._extract_text_from_path("/whatever.xlsx", doc)
    assert result == ""
    assert "not available" not in result
