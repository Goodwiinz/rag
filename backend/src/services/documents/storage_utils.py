"""
Shared storage utilities for document processing services.

Provides a context manager for transparently accessing files regardless of
whether they are stored locally or in Supabase Storage.
"""

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

import structlog

from src.core.config import settings

logger = structlog.get_logger(__name__)


@contextmanager
def local_file_for_document(document):
    """Context manager that provides a local file path for a document.

    Supports three storage backends:
    - "s3": Downloads from S3/DO Spaces to a temp file.
    - "supabase": Downloads from Supabase Storage to a temp file.
    - "local" (default): Yields the existing file_path directly.

    On exit, temp files are cleaned up automatically.

    Usage::

        with local_file_for_document(document) as file_path:
            with open(file_path, 'rb') as f:
                process(f)
    """
    backend = getattr(document, "storage_backend", "local")
    suffix = Path(document.filename).suffix if document.filename else ""

    if backend == "s3" and document.storage_path:
        from src.core.s3_client import S3StorageHelper

        helper = S3StorageHelper()
        temp_path = helper.download_to_tempfile(document.storage_path, suffix=suffix)

        logger.info(
            "s3_temp_file_created",
            document_id=str(document.id),
            temp_path=temp_path,
        )
        try:
            yield temp_path
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
                logger.debug(
                    "s3_temp_file_cleaned",
                    document_id=str(document.id),
                    temp_path=temp_path,
                )

    elif backend == "supabase" and document.storage_path:
        from src.core.supabase_client import StorageHelper, parse_storage_key

        bucket, key = parse_storage_key(document.storage_path)
        helper = StorageHelper()
        temp_path = helper.download_to_tempfile(bucket, key, suffix=suffix)

        logger.info(
            "storage_temp_file_created",
            document_id=str(document.id),
            temp_path=temp_path,
        )
        try:
            yield temp_path
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
                logger.debug(
                    "storage_temp_file_cleaned",
                    document_id=str(document.id),
                    temp_path=temp_path,
                )
    else:
        # Local file — yield directly, no cleanup
        yield document.file_path


def download_document_bytes(document) -> bytes:
    """Download document content as bytes regardless of storage backend.

    Supports s3, supabase, and local backends.
    """
    backend = getattr(document, "storage_backend", "local")

    if backend == "s3" and document.storage_path:
        from src.core.s3_client import S3StorageHelper

        helper = S3StorageHelper()
        return helper.download_file(document.storage_path)

    elif backend == "supabase" and document.storage_path:
        from src.core.supabase_client import StorageHelper, parse_storage_key

        bucket, key = parse_storage_key(document.storage_path)
        helper = StorageHelper()
        return helper.download_file(bucket, key)

    else:
        with open(document.file_path, "rb") as f:
            return f.read()


def ensure_storage_temp_dir():
    """Ensure the Supabase Storage temp directory exists (call on worker startup)."""
    temp_dir = settings.SUPABASE_STORAGE_TEMP_DIR
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir
