"""Shared helper functions used by tool implementations.

Contains document/project resolution, metadata sanitization, and
other utilities referenced across multiple _tool_* functions.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, Iterable, Optional
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.collection import Collection, CollectionDocument
from src.models.document import Document
from src.models.user import User
from src.models.workspace import Workspace

logger = logging.getLogger(__name__)


def _sanitize_metadata(metadata: Any) -> dict:
    """Convert datetime objects in metadata dict to ISO strings for JSON serialization."""
    if not isinstance(metadata, dict):
        return {}
    sanitized = {}
    for k, v in metadata.items():
        if isinstance(v, datetime):
            sanitized[k] = v.isoformat()
        elif isinstance(v, dict):
            sanitized[k] = _sanitize_metadata(v)
        elif isinstance(v, list):
            sanitized[k] = [
                item.isoformat() if isinstance(item, datetime) else item
                for item in v
            ]
        else:
            sanitized[k] = v
    return sanitized


_ARXIV_ID_RE = re.compile(r"^(\d{4}\.\d{4,5})(v\d+)?$")


async def _resolve_document_id(
    document_id: str,
    db: AsyncSession,
    current_user: User,
) -> Optional[Document]:
    """Resolve a document_id string (UUID, arXiv ID, or title) to a Document.

    Resolution order:
      1. UUID parse → match Document.id
      2. arXiv ID pattern (e.g. ``2303.15563`` or ``2303.15563v1``) →
         match Document.filename containing the bare ID OR
         document_metadata->>'arxiv_id' equals the bare ID.
      3. Title ILIKE fallback.

    Returns None if not found. Trace 019e1569 showed the agent passing the
    raw arXiv ID where the tool expected an internal UUID — without this
    branch the user got "Document not found or access denied".
    """
    # Try as UUID first
    try:
        doc_uuid = UUID(document_id)
        stmt = select(Document).where(
            Document.id == doc_uuid,
            Document.organization_id == current_user.organization_id,
            Document.is_deleted == False,
        )
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()
        if doc:
            return doc
    except (ValueError, AttributeError):
        pass

    # Try arXiv ID pattern (strip version suffix for the lookup)
    arxiv_match = _ARXIV_ID_RE.match(document_id.strip()) if document_id else None
    if arxiv_match:
        bare_id = arxiv_match.group(1)
        try:
            stmt = (
                select(Document)
                .where(
                    Document.organization_id == current_user.organization_id,
                    Document.is_deleted == False,
                    (
                        Document.filename.ilike(f"%{bare_id}%")
                        | (
                            Document.document_metadata["arxiv_id"].astext == bare_id
                        )
                    ),
                )
                .order_by(desc(Document.created_at))
                .limit(1)
            )
            result = await db.execute(stmt)
            doc = result.scalar_one_or_none()
            if doc:
                return doc
        except Exception:
            logger.debug(
                "arxiv_id resolution failed for %r", bare_id, exc_info=True
            )

    # Try by title (case-insensitive)
    if document_id:
        try:
            stmt = (
                select(Document)
                .where(
                    Document.title.ilike(document_id),
                    Document.organization_id == current_user.organization_id,
                    Document.is_deleted == False,
                )
                .order_by(desc(Document.created_at))
                .limit(1)
            )
            result = await db.execute(stmt)
            doc = result.scalar_one_or_none()
            if doc:
                return doc
        except Exception:
            pass

    return None


async def _resolve_project_id(
    project_id: str,
    db: AsyncSession,
    current_user: User,
) -> Optional[UUID]:
    """Resolve a project_id string to a UUID.

    Accepts either a UUID string or a project name. Returns None if not found.
    """
    # Try as UUID first
    try:
        return UUID(project_id)
    except (ValueError, AttributeError):
        pass

    # Try by name (case-insensitive)
    if project_id and db and current_user:
        try:
            stmt = (
                select(Collection.id)
                .join(Workspace, Collection.workspace_id == Workspace.id)
                .where(
                    Collection.name.ilike(project_id),
                    Collection.is_deleted == False,
                    Workspace.owner_id == current_user.id,
                )
                .limit(1)
            )
            result = await db.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                return row
        except Exception:
            pass

    return None


async def _verify_project_ownership(
    project_id: str,
    db: AsyncSession,
    current_user: User,
) -> Optional[Collection]:
    """Verify a project (collection) exists and belongs to the current user."""
    proj_uuid = await _resolve_project_id(project_id, db, current_user)
    if not proj_uuid:
        return None

    stmt = (
        select(Collection)
        .join(Workspace, Collection.workspace_id == Workspace.id)
        .where(
            Collection.id == proj_uuid,
            Collection.is_deleted == False,
            Workspace.owner_id == current_user.id,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _link_documents_to_project(
    db: AsyncSession,
    project: Collection,
    document_ids: Iterable[str],
) -> Dict[str, Any]:
    """Idempotently link documents to a project.

    Uses ``INSERT ... ON CONFLICT DO NOTHING`` against the
    ``(collection_id, document_id)`` unique constraint so concurrent
    ingests of the same paper don't race the existence check, and so we
    avoid an N+1 ``SELECT`` per document.

    Returns ``{"linked": int, "already_linked": int}`` — caller decides
    how to surface the result.
    """
    ids = [str(d) for d in document_ids if d]
    if not ids:
        return {"linked": 0, "already_linked": 0}

    existing_stmt = select(CollectionDocument.document_id).where(
        CollectionDocument.collection_id == project.id,
        CollectionDocument.document_id.in_(ids),
    )
    existing = {
        str(row[0]) for row in (await db.execute(existing_stmt)).all()
    }

    new_rows = [
        {"collection_id": project.id, "document_id": doc_id}
        for doc_id in ids
        if doc_id not in existing
    ]

    if new_rows:
        await db.execute(
            pg_insert(CollectionDocument)
            .values(new_rows)
            .on_conflict_do_nothing(
                index_elements=["collection_id", "document_id"]
            )
        )

    return {
        "linked": len(new_rows),
        "already_linked": len(existing),
    }
