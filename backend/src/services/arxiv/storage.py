"""Durable source storage for documents created by arXiv ingestion."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
from uuid import UUID


def store_arxiv_pdf(
    source_document: Any,
    organization_id: str | UUID,
    document_id: str | UUID,
) -> dict[str, Any]:
    """Store an arXiv PDF or its abstract-only text fallback durably.

    ``ArXivIngestionService`` downloads into a pod-local cache and returns the
    path in ``document_metadata.pdf_path``. Deployed pods do not share that
    cache, so persistence callers must promote the file to object storage
    before committing the database row. When PDF retrieval failed, the service
    intentionally returns a useful abstract-only document; persist that content
    as text rather than aborting the whole batch.
    """
    from src.core.config import settings
    from src.models.document import DocumentType

    backend = settings.STORAGE_BACKEND
    if backend not in {"local", "s3", "supabase"}:
        raise ValueError(f"Unsupported storage backend: {backend}")

    metadata = getattr(source_document, "document_metadata", {}) or {}
    local_path_value = metadata.get("pdf_path") if isinstance(metadata, dict) else None
    local_path = Path(local_path_value) if local_path_value else None

    if local_path is not None:
        if not local_path.is_file():
            raise FileNotFoundError(
                f"Downloaded arXiv PDF is unavailable: {local_path_value}"
            )
        file_data = local_path.read_bytes()
        filename = Path(
            getattr(source_document, "filename", "") or local_path.name
        ).name
        mime_type = getattr(source_document, "mime_type", None) or "application/pdf"
        document_type = DocumentType.PDF
    else:
        content_text = getattr(source_document, "content_text", None) or ""
        if not content_text:
            raise FileNotFoundError("arXiv document has neither a PDF nor text content")
        file_data = content_text.encode("utf-8")
        arxiv_id = metadata.get("arxiv_id") if isinstance(metadata, dict) else None
        safe_stem = Path(str(arxiv_id or document_id)).name
        filename = f"{safe_stem}.txt"
        mime_type = "text/plain"
        document_type = DocumentType.TEXT

    key = f"documents/{organization_id}/{document_id}/{filename}"
    common_fields: dict[str, Any] = {
        "filename": filename,
        "file_size_bytes": len(file_data),
        "mime_type": mime_type,
        "document_type": document_type,
        "checksum_sha256": hashlib.sha256(file_data).hexdigest(),
    }

    if backend == "local":
        stored_path = Path(settings.UPLOAD_DIR) / key
        stored_path.parent.mkdir(parents=True, exist_ok=True)
        stored_path.write_bytes(file_data)
        return {
            **common_fields,
            "file_path": str(stored_path),
            "storage_backend": "local",
            "storage_path": None,
        }

    if backend == "s3":
        from src.core.s3_client import S3StorageHelper

        stored_key = S3StorageHelper().upload_file(key, file_data, mime_type)
        return {
            **common_fields,
            "file_path": f"s3://{settings.S3_BUCKET_NAME}/{stored_key}",
            "storage_backend": "s3",
            "storage_path": stored_key,
        }

    if backend == "supabase":
        from src.core.supabase_client import StorageHelper

        bucket = "documents"
        bucket_key = key.removeprefix(f"{bucket}/")
        storage_path = StorageHelper().upload_file(
            bucket, bucket_key, file_data, mime_type
        )
        return {
            **common_fields,
            "file_path": f"supabase://{storage_path}",
            "storage_backend": "supabase",
            "storage_path": storage_path,
        }

    raise AssertionError("validated storage backend was not handled")


def delete_arxiv_storage(storage_fields: dict[str, Any]) -> None:
    """Compensate a promoted source whose database transaction rolled back."""
    backend = storage_fields.get("storage_backend")
    storage_path = storage_fields.get("storage_path")
    file_path = storage_fields.get("file_path")

    if backend == "s3" and storage_path:
        from src.core.s3_client import S3StorageHelper

        S3StorageHelper().delete_file(str(storage_path))
    elif backend == "supabase" and storage_path:
        from src.core.supabase_client import StorageHelper, parse_storage_key

        bucket, key = parse_storage_key(str(storage_path))
        StorageHelper().delete_file(bucket, key)
    elif backend == "local" and file_path:
        Path(str(file_path)).unlink(missing_ok=True)
