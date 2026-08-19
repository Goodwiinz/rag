"""R4-L4: Document.to_dict() must never leak internal storage/dedup fields.

``to_dict()`` already popped ``file_path`` (the raw ``s3://bucket/key`` /
``supabase://...`` / local-path URI). It did NOT pop the sibling fields that
are just as internal: ``storage_path`` (bare object key), ``storage_backend``
(s3/supabase/local layout selector), ``checksum_sha256`` (internal dedup
key), and ``do_kb_data_source_uuid`` (internal DO Knowledge Base identifier).
None of these are part of the public document API contract.
"""

from datetime import datetime, timezone

from src.models.document import Document, DocumentType, ProcessingStatus

_LEAKED_FIELDS = (
    "file_path",
    "storage_path",
    "storage_backend",
    "checksum_sha256",
    "do_kb_data_source_uuid",
)


def _make_document() -> Document:
    """Build a transient (unpersisted) Document with every internal field set.

    ``BaseModel.to_dict()`` reads straight off ``__table__.columns`` via
    ``getattr``, so this works without a DB session — no fixtures needed.
    """
    doc = Document()
    doc.title = "Test Document"
    doc.filename = "test.pdf"
    doc.file_path = "s3://rag-system-storage/org-1/test.pdf"
    doc.file_size_bytes = 1024
    doc.mime_type = "application/pdf"
    doc.document_type = DocumentType.PDF
    doc.storage_path = "org-1/test.pdf"
    doc.storage_backend = "s3"
    doc.checksum_sha256 = "a" * 64
    doc.do_kb_data_source_uuid = "do-kb-data-source-uuid-value"
    doc.processing_status = ProcessingStatus.COMPLETED
    doc.created_at = datetime.now(timezone.utc)
    doc.updated_at = datetime.now(timezone.utc)
    return doc


def test_to_dict_excludes_internal_storage_and_dedup_fields() -> None:
    data = _make_document().to_dict()

    leaked = [field for field in _LEAKED_FIELDS if field in data]
    assert leaked == [], f"to_dict() leaked internal fields: {leaked}"


def test_to_dict_with_content_still_excludes_internal_fields() -> None:
    data = _make_document().to_dict(include_content=True)

    leaked = [field for field in _LEAKED_FIELDS if field in data]
    assert (
        leaked == []
    ), f"to_dict(include_content=True) leaked internal fields: {leaked}"
