"""Dual-write ingest: push existing Documents into the org's DO KB.

Failure-isolated: every exception is swallowed and logged. The existing
Qdrant write path remains the source of truth during Phase 2.

Source-key strategy:
1. If document.storage_backend == "s3" and storage_path is set, use it directly.
2. Else if content_text is present, upload it as a fallback object under
   `do-kb-content/{document_id}.txt` so DO KB still has source data to index.
3. Else log + skip (no source).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.models.document import Document

from .client import DOKnowledgeBaseClient, DOKnowledgeBaseError, get_do_kb_client
from .provisioner import ensure_kb_for_org

logger = logging.getLogger(__name__)

_FALLBACK_KEY_PREFIX = "do-kb-content"


def _record_metric(status: str) -> None:
    """Best-effort Prometheus counter; tolerate missing prometheus_client."""
    try:
        from src.observability import metrics  # type: ignore[attr-defined]

        counter = getattr(metrics, "agent_do_kb_ingest_total", None)
        if counter is not None:
            counter.labels(status=status).inc()
    except Exception:  # pragma: no cover - observability is optional
        pass


def _resolve_spaces_source(document: Document) -> Optional[tuple[str, str]]:
    """Return (bucket, key) when document points at a Spaces object, else None."""
    backend = getattr(document, "storage_backend", None)
    storage_path = getattr(document, "storage_path", None)
    if backend == "s3" and storage_path:
        return settings.S3_BUCKET_NAME, storage_path
    return None


def _upload_text_fallback(document: Document) -> Optional[tuple[str, str]]:
    """Upload content_text to Spaces and return (bucket, key). None on failure."""
    text = getattr(document, "content_text", None)
    if not text:
        return None
    try:
        from src.core.s3_client import S3StorageHelper

        helper = S3StorageHelper()
        key = f"{_FALLBACK_KEY_PREFIX}/{document.id}.txt"
        helper.upload_file(
            key,
            text.encode("utf-8"),
            content_type="text/plain; charset=utf-8",
        )
        return helper.bucket, key
    except Exception as exc:
        logger.warning(
            "do_kb fallback text upload failed",
            extra={"document_id": str(document.id), "error": str(exc)},
        )
        return None


async def sync_document_to_kb(
    session: AsyncSession,
    document: Document,
    *,
    client: Optional[DOKnowledgeBaseClient] = None,
    trigger_indexing: bool = True,
) -> Optional[str]:
    """Add the document to its organization's DO KB and persist the data source UUID.

    Returns the data source UUID on success, or None if skipped/failed.
    Always swallows exceptions — Qdrant remains source of truth in Phase 2.
    """
    if not settings.DO_KB_ENABLED:
        return None

    if document.do_kb_data_source_uuid:
        return document.do_kb_data_source_uuid

    api = client or get_do_kb_client()

    try:
        kb_uuid = await ensure_kb_for_org(
            session, document.organization_id, client=api
        )
    except DOKnowledgeBaseError as exc:
        logger.warning(
            "do_kb provisioning skipped",
            extra={"document_id": str(document.id), "error": str(exc)},
        )
        _record_metric("provision_failed")
        return None
    except Exception as exc:  # noqa: BLE001 - failure isolation is intentional
        logger.warning(
            "do_kb provisioning unexpected error",
            extra={"document_id": str(document.id), "error": str(exc)},
        )
        _record_metric("provision_error")
        return None

    source = _resolve_spaces_source(document) or _upload_text_fallback(document)
    if source is None:
        logger.info(
            "do_kb skip — no source",
            extra={"document_id": str(document.id), "kb_uuid": kb_uuid},
        )
        _record_metric("skipped_no_source")
        return None

    bucket, key = source

    try:
        data_source = await api.add_spaces_data_source(
            kb_uuid=kb_uuid, bucket=bucket, key=key
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "do_kb add_data_source failed",
            extra={
                "document_id": str(document.id),
                "kb_uuid": kb_uuid,
                "error": str(exc),
            },
        )
        _record_metric("add_data_source_failed")
        return None

    document.do_kb_data_source_uuid = data_source.uuid
    document.do_kb_indexed_at = datetime.now(timezone.utc)

    try:
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "do_kb persist failed",
            extra={"document_id": str(document.id), "error": str(exc)},
        )
        _record_metric("persist_failed")
        return None

    if trigger_indexing:
        try:
            await api.start_indexing(kb_uuid=kb_uuid)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "do_kb start_indexing failed (non-fatal)",
                extra={"kb_uuid": kb_uuid, "error": str(exc)},
            )
            _record_metric("indexing_kick_failed")

    _record_metric("ok")
    return data_source.uuid


async def sync_documents_to_kb(
    session: AsyncSession,
    documents: list[Document],
    *,
    client: Optional[DOKnowledgeBaseClient] = None,
) -> list[Optional[str]]:
    """Bulk variant: one indexing kick after all data sources are added."""
    if not settings.DO_KB_ENABLED or not documents:
        return [None] * len(documents)

    api = client or get_do_kb_client()
    results: list[Optional[str]] = []
    seen_kbs: set[str] = set()

    for doc in documents:
        ds_uuid = await sync_document_to_kb(
            session, doc, client=api, trigger_indexing=False
        )
        results.append(ds_uuid)
        if ds_uuid:
            org_kb = getattr(doc.organization, "do_kb_uuid", None) if hasattr(
                doc, "organization"
            ) else None
            if isinstance(org_kb, str):
                seen_kbs.add(org_kb)

    for kb_uuid in seen_kbs:
        try:
            await api.start_indexing(kb_uuid=kb_uuid)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "do_kb bulk start_indexing failed",
                extra={"kb_uuid": kb_uuid, "error": str(exc)},
            )
            _record_metric("indexing_kick_failed")

    return results
