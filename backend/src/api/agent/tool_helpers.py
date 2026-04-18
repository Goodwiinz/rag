"""Shared helper functions used by tool implementations.

Contains document/project resolution, metadata sanitization, and
other utilities referenced across multiple _tool_* functions.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.collection import Collection
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


async def _resolve_document_id(
    document_id: str,
    db: AsyncSession,
    current_user: User,
) -> Optional[Document]:
    """Resolve a document_id string (UUID or title) to a Document.

    Accepts either a UUID string or a document title. Returns None if not found.
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
