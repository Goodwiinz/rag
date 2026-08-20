"""Pre-flight guard: force text extraction for large/complex PDFs before DO KB sync.

DO KB has a server-side processing time limit for individual files. Large or
complex PDFs (many pages, scanned images, heavy graphics) can exceed this limit
and fail to index. This module detects such PDFs and extracts their text locally
(PyMuPDF) before syncing, so the canonical ``.txt`` mirror path is used instead
of the raw PDF.

Kept defensive: the Document model has no ``page_count`` column today, so the
page threshold degrades to a no-op via ``getattr`` and the size threshold
(``file_size_bytes``, a real column) is the primary guard.
"""

from __future__ import annotations

import logging

from src.core.config import Settings
from src.core.config import settings as global_settings

logger = logging.getLogger(__name__)


def should_force_text_extraction(document, cfg=None) -> bool:
    """Return True if this document needs local text extraction before DO KB sync.

    Triggers when the document is a PDF, has no ``content_text`` yet, and exceeds
    EITHER the page-count threshold OR the size threshold. Non-PDFs and documents
    that already have extracted text are never flagged.
    """
    s = cfg or global_settings

    doc_type = getattr(document, "document_type", None)
    type_value = doc_type.value if hasattr(doc_type, "value") else str(doc_type)
    if type_value != "pdf":
        return False

    if getattr(document, "content_text", None):
        return False

    page_count = getattr(document, "page_count", None) or 0
    file_size_mb = (getattr(document, "file_size_bytes", 0) or 0) / (1024 * 1024)

    if page_count and page_count >= s.DO_KB_FORCE_TEXT_PDF_PAGES:
        return True
    if file_size_mb >= s.DO_KB_FORCE_TEXT_PDF_SIZE_MB:
        return True
    return False


async def ensure_content_text_for_kb(document) -> bool:
    """If the guard flags this document, extract text locally (PyMuPDF).

    Returns True when the document ends up with ``content_text`` (pre-existing or
    freshly extracted), False if extraction was needed but failed. Called from
    ``sync_document_to_kb`` before source resolution so large PDFs transparently
    take the canonical ``.txt`` path. Never raises — a failure just leaves the
    document as-is (the raw-PDF fallback still applies, preserving old behavior).
    """
    if not should_force_text_extraction(document):
        return True

    logger.info(
        "do_kb pre-flight: forcing text extraction for document %s "
        "(pages=%s, size_mb=%.1f)",
        getattr(document, "id", "?"),
        getattr(document, "page_count", "?"),
        (getattr(document, "file_size_bytes", 0) or 0) / (1024 * 1024),
    )

    try:
        from src.services.documents.file_service import FileService
        from src.services.documents.storage_utils import local_file_for_document

        with local_file_for_document(document) as file_path:
            # Static: no AsyncSession is in scope on the sync path, and
            # FileService() without one raised TypeError that the except
            # below swallowed — so this path never ran.
            text = FileService._extract_text_from_path(file_path, document)

        if text and text.strip():
            document.content_text = text
            logger.info(
                "do_kb pre-flight: extracted %d chars for document %s",
                len(text),
                getattr(document, "id", "?"),
            )
            return True

        logger.warning(
            "do_kb pre-flight: text extraction returned empty for document %s",
            getattr(document, "id", "?"),
        )
        return False
    except (TypeError, AttributeError, ImportError):
        # Our own bad call site (wrong signature / missing attribute / bad
        # import), not a bad document. Still non-fatal, but logged at error
        # with a traceback so it can't hide as "extraction returned empty".
        logger.error(
            "do_kb pre-flight: extraction call site is broken for document %s",
            getattr(document, "id", "?"),
            exc_info=True,
        )
        return False
    except Exception as exc:  # noqa: BLE001 - guard must never block sync
        logger.warning(
            "do_kb pre-flight: text extraction failed for document %s: %s",
            getattr(document, "id", "?"),
            exc,
        )
        return False
