"""Single source of truth for linking a chat thread to a project.

Background: a thread→project link lives in TWO places — the scalar
``thread.source_project_id`` (+ ``rag_document_scope``) and a ``project_threads``
join row. Three call sites historically wrote these independently with
divergent ``link_type``s, and the create-thread path swallowed errors, so the
two could desync (row but no column, or neither). The agent then forgot the
attached project. This helper writes BOTH in the caller's transaction so they
land together or not at all, and is idempotent so re-linking repairs a desync
instead of erroring.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import CollectionDocument, ProjectThread


async def get_project_document_scope(project_id: UUID, db: AsyncSession) -> list[str]:
    """Return non-deleted document IDs linked to a project (RAG scope)."""
    rows = await db.execute(
        select(CollectionDocument.document_id).where(
            and_(
                CollectionDocument.collection_id == project_id,
                CollectionDocument.is_deleted == False,  # noqa: E712
            )
        )
    )
    return [str(r[0]) for r in rows.all()]


async def attach_thread_to_project(
    db: AsyncSession,
    thread,
    project_id: UUID,
    *,
    link_type: str,
    linked_by_id: Optional[UUID] = None,
    context_note: Optional[str] = None,
) -> ProjectThread:
    """Link ``thread`` to ``project_id`` atomically (caller commits).

    Sets ``thread.source_project_id`` + ``rag_document_scope`` AND upserts the
    ``ProjectThread`` join row in one unit of work. Idempotent: if a link for
    ``(project_id, thread.id)`` already exists it is reused (and the scalar
    column is still (re)written, repairing a prior desync). Does NOT commit —
    the caller owns the transaction so both writes succeed or roll back together.
    """
    thread.source_project_id = project_id
    thread.rag_document_scope = {
        "document_ids": await get_project_document_scope(project_id, db)
    }

    existing = (
        await db.execute(
            select(ProjectThread).where(
                and_(
                    ProjectThread.project_id == project_id,
                    ProjectThread.thread_id == thread.id,
                )
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    link = ProjectThread(
        project_id=project_id,
        thread_id=thread.id,
        link_type=link_type,
        linked_by_id=linked_by_id,
        context_note=context_note,
    )
    db.add(link)
    return link
