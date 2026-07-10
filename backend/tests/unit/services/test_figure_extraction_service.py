"""Unit tests for the shared PyMuPDF figure-extraction helper.

`extract_figures_for_document` is called from both ingestion pipelines
(multimodal_processing_service's PDF branch and processing_tasks' Step 1b);
these tests exercise the helper directly with a fake sync Session so no real
DB/engine is needed, and generate PDFs in-test with fitz (no binary
fixtures).
"""

from __future__ import annotations

import io
from types import SimpleNamespace
from uuid import uuid4

import fitz
import pytest
from PIL import Image

from src.models.document import DocumentType
from src.models.document_processing import ContentType
from src.services.processing import figure_extraction_service as svc
from src.services.processing.figure_extraction_service import (
    EXTRACTION_METHOD,
    extract_figures_for_document,
    merge_captions_into_text,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeQuery:
    def __init__(self, model):
        self.model = model
        self.filters: list = []
        self.synchronize_session = "unset"

    def filter(self, *criteria):
        self.filters.extend(criteria)
        return self

    def delete(self, synchronize_session=None):
        self.synchronize_session = synchronize_session
        return 0


class _FakeSession:
    def __init__(self):
        self.added: list = []
        self.queries: list = []

    def query(self, model):
        q = _FakeQuery(model)
        self.queries.append(q)
        return q

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        pass

    def rollback(self):
        pass


class _UnconfiguredS3Helper:
    """Mirrors real S3StorageHelper.__init__ raising when S3 env is unset."""

    def __init__(self, *args, **kwargs):
        raise RuntimeError("S3 client not available.")


def _document(pdf_path, **overrides):
    fields = dict(
        storage_backend="local",
        storage_path=None,
        file_path=str(pdf_path),
        filename="doc.pdf",
        id=uuid4(),
        organization_id=uuid4(),
        document_type=DocumentType.PDF,
    )
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _png_bytes(size=(200, 150), color=(255, 0, 0)) -> bytes:
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_pdf_with_figure(path, image_size=(200, 150), with_caption=True) -> None:
    doc = fitz.open()
    page = doc.new_page()
    w, h = image_size
    rect = fitz.Rect(72, 100, 72 + w, 100 + h)
    page.insert_image(rect, stream=_png_bytes(image_size))
    if with_caption:
        page.insert_text((72, 100 + h + 10), "Figure 1: The caption")
    doc.save(str(path))
    doc.close()


def _make_pdf_two_figures(path) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_image(
        fitz.Rect(72, 100, 272, 250), stream=_png_bytes((200, 150), (255, 0, 0))
    )
    page.insert_image(
        fitz.Rect(72, 300, 272, 450), stream=_png_bytes((200, 150), (0, 255, 0))
    )
    doc.save(str(path))
    doc.close()


def _make_pdf_caption_only(path) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Figure 2: Standalone figure, no crop")
    doc.save(str(path))
    doc.close()


@pytest.fixture()
def unconfigured_s3(monkeypatch):
    """Deterministic 'S3 unconfigured' stand-in, regardless of the real env."""
    monkeypatch.setattr("src.core.s3_client.S3StorageHelper", _UnconfiguredS3Helper)


@pytest.fixture(autouse=True)
def enable_flag(monkeypatch):
    monkeypatch.setattr(svc.settings, "FIGURE_EXTRACTION_ENABLED", True)


# ---------------------------------------------------------------------------
# 1. Raster figure + caption -> 1 candidate, caption matched, bbox/dims populated.
# ---------------------------------------------------------------------------


def test_raster_figure_with_caption(tmp_path, unconfigured_s3):
    pdf_path = tmp_path / "fig.pdf"
    _make_pdf_with_figure(pdf_path)
    document = _document(pdf_path)
    db = _FakeSession()

    result = extract_figures_for_document(db, document)

    assert result["figures_extracted"] == 1
    assert result["captions_found"] == 1
    assert "[Figure 1, p.1]" in result["captions_text"]
    assert len(db.added) == 1

    row = db.added[0]
    assert row.content_metadata["figure_label"] == "Figure 1"
    assert row.content_metadata["page"] == 1
    assert row.content_metadata["bbox"] == [72.0, 100.0, 272.0, 250.0]
    assert row.media_dimensions == {"width": 200, "height": 150}


# ---------------------------------------------------------------------------
# 2. 16x16 image -> filtered out (MIN_DIM_PX).
# ---------------------------------------------------------------------------


def test_tiny_image_filtered_out(tmp_path, unconfigured_s3):
    pdf_path = tmp_path / "tiny.pdf"
    _make_pdf_with_figure(pdf_path, image_size=(16, 16), with_caption=False)
    document = _document(pdf_path)
    db = _FakeSession()

    result = extract_figures_for_document(db, document)

    assert result["figures_extracted"] == 0
    assert result["captions_found"] == 0
    assert db.added == []


# ---------------------------------------------------------------------------
# 3. Caption text with no image on page -> caption-only candidate.
# ---------------------------------------------------------------------------


def test_caption_only_candidate_no_image(tmp_path, unconfigured_s3):
    pdf_path = tmp_path / "caption_only.pdf"
    _make_pdf_caption_only(pdf_path)
    document = _document(pdf_path)
    db = _FakeSession()

    result = extract_figures_for_document(db, document)

    assert result["figures_extracted"] == 0
    assert result["captions_found"] == 1
    assert len(db.added) == 1

    row = db.added[0]
    assert row.content_metadata["storage_key"] is None
    assert row.media_dimensions is None
    assert row.media_format is None


# ---------------------------------------------------------------------------
# 4. merge_captions_into_text applied twice -> exactly one section.
# ---------------------------------------------------------------------------


def test_merge_captions_into_text_idempotent():
    captions = "\n\n## Extracted figures\n[Figure 1, p.1] The caption\n"

    once = merge_captions_into_text("Body text.", captions)
    twice = merge_captions_into_text(once, captions)

    assert once == twice
    assert twice.count("## Extracted figures") == 1
    assert twice.startswith("Body text.")


# ---------------------------------------------------------------------------
# 5. Compensating delete on upload failure.
# ---------------------------------------------------------------------------


def test_compensating_delete_on_upload_failure(tmp_path, monkeypatch):
    pdf_path = tmp_path / "two.pdf"
    _make_pdf_two_figures(pdf_path)
    document = _document(pdf_path)
    db = _FakeSession()

    class _FailingS3Helper:
        uploaded: list = []
        deleted: list = []

        def __init__(self, *args, **kwargs):
            pass

        def upload_file(self, key, data, content_type="application/octet-stream"):
            _FailingS3Helper.uploaded.append(key)
            if len(_FailingS3Helper.uploaded) == 2:
                raise RuntimeError("upload boom")
            return key

        def delete_file(self, key):
            _FailingS3Helper.deleted.append(key)
            return True

    monkeypatch.setattr("src.core.s3_client.S3StorageHelper", _FailingS3Helper)

    with pytest.raises(RuntimeError, match="upload boom"):
        extract_figures_for_document(db, document)

    assert _FailingS3Helper.deleted == [_FailingS3Helper.uploaded[0]]


# ---------------------------------------------------------------------------
# 6. S3 unconfigured -> degrades to caption-only, no raise.
# ---------------------------------------------------------------------------


def test_s3_unconfigured_degrades_gracefully(tmp_path, unconfigured_s3):
    pdf_path = tmp_path / "fig.pdf"
    _make_pdf_with_figure(pdf_path)
    document = _document(pdf_path)
    db = _FakeSession()

    result = extract_figures_for_document(db, document)

    assert result["figures_extracted"] == 1
    row = db.added[0]
    assert row.content_metadata["storage_key"] is None


# ---------------------------------------------------------------------------
# 7. Flag off -> skipped, no DB writes.
# ---------------------------------------------------------------------------


def test_flag_off_skips_with_no_db_writes(monkeypatch, tmp_path):
    monkeypatch.setattr(svc.settings, "FIGURE_EXTRACTION_ENABLED", False)
    document = _document(tmp_path / "unused.pdf")
    db = _FakeSession()

    result = extract_figures_for_document(db, document)

    assert result == {"skipped": "disabled"}
    assert db.queries == []
    assert db.added == []


# ---------------------------------------------------------------------------
# 8. Delete-before-insert keyed on extraction_method + tenancy on rows.
# ---------------------------------------------------------------------------


def test_delete_before_insert_and_row_tenancy(tmp_path, unconfigured_s3):
    pdf_path = tmp_path / "fig.pdf"
    _make_pdf_with_figure(pdf_path)
    document = _document(pdf_path)
    db = _FakeSession()

    extract_figures_for_document(db, document)

    assert len(db.queries) == 1
    query = db.queries[0]
    assert query.synchronize_session is False

    method_filters = [
        c for c in query.filters if getattr(c.left, "key", None) == "extraction_method"
    ]
    assert method_filters, "delete query must filter on extraction_method"
    assert method_filters[0].right.value == EXTRACTION_METHOD

    assert len(db.added) == 1
    row = db.added[0]
    assert row.organization_id == document.organization_id
    assert row.content_type == ContentType.IMAGE
