"""Regression: table extraction must not treat `document.file_path` as a local
path.

Both `TableExtractionService` public methods used to accept a raw `pdf_path`
string and validate it against `settings.UPLOAD_DIR` via `_safe_pdf_path`.
On the deployed s3 backend `document.file_path` is `s3://bucket/key`, which
`_safe_pdf_path` rejected with `ValueError("... outside the upload
directory")` before PyMuPDF/Camelot ever ran. Both methods now take the
`Document` and route through `local_file_for_document`, which downloads s3
content to a temp file first; `_safe_pdf_path` only runs for the local
backend, where the traversal guard still matters.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import fitz
import pytest

from src.services.processing.table_extraction_service import TableExtractionService

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


@pytest.fixture()
def s3_document(tmp_path):
    pdf_path = tmp_path / "x.pdf"
    _make_pdf(str(pdf_path))
    _StubS3Helper.local_pdf_path = str(pdf_path)
    return SimpleNamespace(
        storage_backend="s3",
        storage_path="org/doc/x.pdf",
        file_path="s3://b/org/doc/x.pdf",
        filename="x.pdf",
        id=uuid4(),
    )


@pytest.mark.asyncio
async def test_extract_region_s3_document_downloads_and_extracts(
    monkeypatch, s3_document
):
    monkeypatch.setattr("src.core.s3_client.S3StorageHelper", _StubS3Helper)

    service = TableExtractionService()
    result = await service.extract_region(
        document=s3_document, page=1, x1=0, y1=0, x2=600, y2=800
    )

    assert "hello table world" in result["content"]


@pytest.mark.asyncio
async def test_extract_region_local_traversal_still_rejected():
    local_document = SimpleNamespace(
        storage_backend="local",
        storage_path=None,
        file_path="/etc/passwd",
        filename="passwd",
        id=uuid4(),
    )

    service = TableExtractionService()
    with pytest.raises(ValueError):
        await service.extract_region(
            document=local_document, page=1, x1=0, y1=0, x2=600, y2=800
        )
