"""Backfill orchestration: push every existing Document into its org's DO KB.

Resumable via do_kb_backfill_progress.last_document_id. Idempotent because
sync_document_to_kb skips documents that already have do_kb_data_source_uuid.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.models.document import Document
from src.models.organization import Organization

from .backfill_model import DOKBBackfillProgress
from .client import DOKnowledgeBaseClient, get_do_kb_client
from .ingest import sync_document_to_kb
from .provisioner import ensure_kb_for_org

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BackfillReport:
    organization_id: str
    completed: int
    failed: int
    skipped: int
    last_document_id: Optional[str]
    finished: bool


async def _load_progress(
    session: AsyncSession, org_id: str
) -> DOKBBackfillProgress:
    progress = await session.get(DOKBBackfillProgress, org_id)
    if progress is None:
        progress = DOKBBackfillProgress(
            organization_id=org_id,
            completed_count=0,
            failed_count=0,
            status="pending",
        )
        session.add(progress)
        await session.flush()
    return progress


async def _next_batch(
    session: AsyncSession,
    org_id: str,
    *,
    after_document_id: Optional[str],
    batch_size: int,
) -> list[Document]:
    stmt = (
        select(Document)
        .where(
            and_(
                Document.organization_id == org_id,
                Document.do_kb_data_source_uuid.is_(None),
            )
        )
        .order_by(Document.id)
        .limit(batch_size)
    )
    if after_document_id is not None:
        stmt = stmt.where(Document.id > after_document_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def backfill_org(
    session: AsyncSession,
    org_id: str,
    *,
    batch_size: int = 25,
    dry_run: bool = False,
    client: Optional[DOKnowledgeBaseClient] = None,
) -> BackfillReport:
    """Backfill all unsynced documents in one organization.

    Caller is responsible for transaction boundaries. We commit progress
    rows so a crash mid-run preserves the cursor.
    """
    if not settings.DO_KB_ENABLED:
        raise RuntimeError("DO_KB_ENABLED must be true to run backfill")

    api = client or get_do_kb_client()
    org = await session.get(Organization, org_id)
    if org is None:
        raise ValueError(f"organization {org_id} not found")

    progress = await _load_progress(session, org_id)
    if progress.status == "completed":
        logger.info(
            "do_kb backfill already complete",
            extra={"org_id": str(org_id)},
        )
        return BackfillReport(
            organization_id=str(org_id),
            completed=progress.completed_count,
            failed=progress.failed_count,
            skipped=0,
            last_document_id=str(progress.last_document_id)
            if progress.last_document_id
            else None,
            finished=True,
        )

    if not dry_run:
        # Ensure KB exists before iterating; cheap idempotent.
        await ensure_kb_for_org(session, org_id, client=api)

    progress.status = "in_progress"
    progress.started_at = progress.started_at or datetime.now(timezone.utc)
    await session.commit()

    completed = 0
    failed = 0
    skipped = 0
    cursor: Optional[str] = (
        str(progress.last_document_id) if progress.last_document_id else None
    )

    while True:
        batch = await _next_batch(
            session, org_id, after_document_id=cursor, batch_size=batch_size
        )
        if not batch:
            break

        for doc in batch:
            cursor = str(doc.id)
            if dry_run:
                skipped += 1
                continue

            ds_uuid = await sync_document_to_kb(
                session, doc, client=api, trigger_indexing=False
            )
            if ds_uuid:
                completed += 1
            else:
                failed += 1

            progress.last_document_id = doc.id
            progress.completed_count = (progress.completed_count or 0) + (
                1 if ds_uuid else 0
            )
            progress.failed_count = (progress.failed_count or 0) + (
                0 if ds_uuid else 1
            )
            await session.commit()

        if dry_run:
            # In dry-run we still iterate every batch but never commit indexing.
            continue

    if not dry_run and org.do_kb_uuid:
        try:
            await api.start_indexing(kb_uuid=org.do_kb_uuid)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "do_kb final indexing kick failed",
                extra={"kb_uuid": org.do_kb_uuid, "error": str(exc)},
            )

    progress.status = "completed" if not dry_run else "dry_run_done"
    progress.finished_at = datetime.now(timezone.utc)
    await session.commit()

    return BackfillReport(
        organization_id=str(org_id),
        completed=completed,
        failed=failed,
        skipped=skipped,
        last_document_id=cursor,
        finished=True,
    )


async def iter_organizations_to_backfill(
    session: AsyncSession,
) -> Iterable[Organization]:
    """All active orgs, ordered by id, for --all runs."""
    stmt = (
        select(Organization)
        .where(Organization.is_active.is_(True))
        .order_by(Organization.id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
