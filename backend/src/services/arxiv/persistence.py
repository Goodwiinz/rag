"""Tenant-safe durable persistence shared by every arXiv ingest entry point."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Iterable, Optional
from uuid import UUID, uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document import Document, ProcessingStatus

from .storage import delete_arxiv_storage, store_arxiv_pdf

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ArxivPersistenceResult:
    document_ids: list[str]
    reused_document_ids: set[str]
    kb_sync_failed: bool = False


def _arxiv_id(source_document: Any) -> Optional[str]:
    metadata = getattr(source_document, "document_metadata", None)
    if not isinstance(metadata, dict):
        return None
    value = metadata.get("arxiv_id")
    return str(value).strip() if value else None


def _arxiv_document_title(source_document: Any) -> str:
    metadata = getattr(source_document, "document_metadata", None)
    metadata_title = metadata.get("title") if isinstance(metadata, dict) else None
    title = metadata_title or getattr(source_document, "title", None)
    return " ".join(str(title or "Untitled").split())


async def existing_arxiv_document_id(
    db: AsyncSession, organization_id: Any, arxiv_id: Optional[str]
) -> Optional[Any]:
    """Return this tenant's live document for the exact arXiv revision."""
    if not arxiv_id:
        return None
    stmt = (
        select(Document.id)
        .where(
            Document.organization_id == organization_id,
            Document.document_metadata["arxiv_id"].as_string() == arxiv_id,
            Document.is_deleted.is_(False),
        )
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def existing_document_id(
    db: AsyncSession, organization_id: Any, checksum: Optional[str]
) -> Optional[Any]:
    """Return this tenant's live document for the content checksum."""
    if not checksum:
        return None
    stmt = (
        select(Document.id)
        .where(
            Document.organization_id == organization_id,
            Document.checksum_sha256 == checksum,
            Document.is_deleted.is_(False),
        )
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _delete_promoted(storage_fields: dict[str, Any]) -> None:
    await asyncio.to_thread(delete_arxiv_storage, storage_fields)


async def _cleanup_promoted(storage_items: Iterable[dict[str, Any]]) -> None:
    for storage_fields in reversed(list(storage_items)):
        try:
            await _delete_promoted(storage_fields)
        except Exception:  # noqa: BLE001 - preserve the original ingest failure
            logger.warning(
                "arxiv ingest rollback left an orphaned object: %s",
                storage_fields.get("storage_path") or storage_fields.get("file_path"),
                exc_info=True,
            )


async def persist_arxiv_documents(
    source_documents: Iterable[Any],
    *,
    user_id: str | UUID,
    organization_id: str | UUID,
) -> ArxivPersistenceResult:
    """Persist arXiv documents once, with durable storage and KB dual-write."""
    from src.core.database import AsyncSessionLocal

    sources = list(source_documents)
    document_ids_by_index: list[Optional[str]] = [None] * len(sources)
    reused_document_ids: set[str] = set()
    persisted_documents: list[Document] = []
    promoted_storage: list[dict[str, Any]] = []
    staged_documents: list[tuple[int, Any, str, UUID, dict[str, Any]]] = []
    discarded_storage: list[dict[str, Any]] = []

    try:
        # Close the read transaction before potentially slow object-storage I/O.
        pending_sources: list[tuple[int, Any, str]] = []
        async with AsyncSessionLocal() as lookup_db:
            for index, source_document in enumerate(sources):
                arxiv_id = _arxiv_id(source_document)
                if not arxiv_id:
                    logger.warning("arxiv ingest skipped document without arxiv_id")
                    continue

                existing_id = await existing_arxiv_document_id(
                    lookup_db, organization_id, arxiv_id
                )
                if existing_id is not None:
                    document_id = str(existing_id)
                    document_ids_by_index[index] = document_id
                    reused_document_ids.add(document_id)
                    continue
                pending_sources.append((index, source_document, arxiv_id))

        # Promotion happens outside a database transaction. If a later write
        # fails, promoted_storage is the complete compensation manifest.
        for index, source_document, arxiv_id in pending_sources:
            document_uuid = uuid4()
            storage_fields = await asyncio.to_thread(
                store_arxiv_pdf,
                source_document,
                organization_id,
                document_uuid,
            )
            promoted_storage.append(storage_fields)
            staged_documents.append(
                (index, source_document, arxiv_id, document_uuid, storage_fields)
            )

        if staged_documents:
            async with AsyncSessionLocal() as db:
                async with db.begin():
                    for (
                        index,
                        source_document,
                        arxiv_id,
                        document_uuid,
                        storage_fields,
                    ) in staged_documents:
                        existing_id = await existing_document_id(
                            db,
                            organization_id,
                            storage_fields.get("checksum_sha256"),
                        )
                        if existing_id is not None:
                            discarded_storage.append(storage_fields)
                            document_id = str(existing_id)
                            document_ids_by_index[index] = document_id
                            reused_document_ids.add(document_id)
                            continue

                        document = Document(
                            id=document_uuid,
                            title=_arxiv_document_title(source_document),
                            **storage_fields,
                            content_text=getattr(source_document, "content_text", None),
                            content_summary=getattr(
                                source_document, "content_summary", None
                            ),
                            document_metadata=jsonable_encoder(
                                getattr(source_document, "document_metadata", {})
                            ),
                            processing_status=ProcessingStatus.COMPLETED,
                            uploaded_by_user_id=user_id,
                            organization_id=organization_id,
                            is_public=False,
                        )

                        try:
                            # Keep a concurrent checksum loser from rolling back the
                            # other papers in this batch.
                            async with db.begin_nested():
                                db.add(document)
                                await db.flush()
                        except IntegrityError:
                            existing_id = await existing_arxiv_document_id(
                                db, organization_id, arxiv_id
                            ) or await existing_document_id(
                                db,
                                organization_id,
                                storage_fields.get("checksum_sha256"),
                            )
                            if existing_id is None:
                                raise
                            discarded_storage.append(storage_fields)
                            document_id = str(existing_id)
                            document_ids_by_index[index] = document_id
                            reused_document_ids.add(document_id)
                            continue

                        document_ids_by_index[index] = str(document.id)
                        persisted_documents.append(document)

                    if persisted_documents:
                        try:
                            from src.services.search.fulltext_search_service import (
                                fulltext_search_service,
                            )

                            await fulltext_search_service.async_update_document_search_vectors(
                                [str(document.id) for document in persisted_documents],
                                db,
                            )
                        except Exception as exc:  # noqa: BLE001 - search is best-effort
                            logger.warning(
                                "arxiv ingest: search_vector update failed: %s", exc
                            )

        # The committed rows own every promoted object except checksum/race
        # losers. Keep only those losers in the compensation manifest.
        promoted_storage[:] = discarded_storage
        await _cleanup_promoted(promoted_storage)
        promoted_storage.clear()
    except Exception:
        await _cleanup_promoted(promoted_storage)
        raise

    kb_sync_failed = False
    from src.core.config import settings

    if settings.DO_KB_ENABLED and persisted_documents:
        from src.services.do_kb import sync_documents_to_kb
        from src.shared.enums import SatelliteSyncStatus

        try:
            async with AsyncSessionLocal() as kb_db:
                merged = [await kb_db.merge(doc) for doc in persisted_documents]
                for document in merged:
                    document.do_kb_sync_status = SatelliteSyncStatus.PENDING.value
                await kb_db.commit()

                try:
                    results = await sync_documents_to_kb(kb_db, merged)
                except Exception:
                    for document in merged:
                        document.do_kb_sync_status = SatelliteSyncStatus.FAILED.value
                    await kb_db.commit()
                    raise
                for document, data_source_uuid in zip(merged, results):
                    document.do_kb_sync_status = (
                        SatelliteSyncStatus.COMPLETED.value
                        if data_source_uuid
                        else SatelliteSyncStatus.FAILED.value
                    )
                await kb_db.commit()
                kb_sync_failed = any(result is None for result in results)
        except Exception as exc:  # noqa: BLE001 - PostgreSQL remains authoritative
            kb_sync_failed = True
            logger.warning("do_kb dual-write skipped for arxiv ingest: %s", exc)

    return ArxivPersistenceResult(
        document_ids=[
            document_id
            for document_id in document_ids_by_index
            if document_id is not None
        ],
        reused_document_ids=reused_document_ids,
        kb_sync_failed=kb_sync_failed,
    )
