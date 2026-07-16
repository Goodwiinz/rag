"""
Cross-handler scope/access helpers shared by every workspace resource route.

Task 4.2 split ``backend/src/api/threads/workspaces.py`` by resource. Task 4.3
moved the actual query/predicate logic these functions wrap into
``src/services/threads/workspace_access.py`` (the one funnel implementation,
also used directly by ``ChatService``); these HTTPException-raising
wrappers stay here, with the same names and signatures every route handler
already calls, so route bodies and existing tests that ``mock.patch`` these
names by their module path are unaffected by the underlying consolidation.
"""

from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.collection import Collection
from src.models.conversation import Conversation
from src.models.document import Document
from src.models.thread import Thread
from src.models.user import User
from src.models.workspace import Workspace
from src.services.threads import workspace_access


async def _get_workspace_or_404(
    db: AsyncSession, workspace_id: UUID, current_user: User
) -> Workspace:
    """Get workspace or raise 404, checking access"""
    workspace = await workspace_access.get_workspace(db, workspace_id, current_user.id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


async def _get_conversation_or_404(
    db: AsyncSession, workspace_id: UUID, conversation_id: UUID, current_user: User
) -> Conversation:
    """Get conversation or raise 404"""
    conversation = await workspace_access.get_conversation(
        db, conversation_id, current_user.id, workspace_id=workspace_id
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


async def _get_thread_or_404(
    db: AsyncSession,
    workspace_id: UUID,
    conversation_id: UUID,
    thread_id: UUID,
    current_user: User,
) -> Thread:
    """Get thread or raise 404"""
    thread = await workspace_access.get_thread(
        db,
        thread_id,
        current_user.id,
        conversation_id=conversation_id,
        workspace_id=workspace_id,
        include_messages=True,
    )
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread


async def _get_collection_or_404(
    db: AsyncSession, workspace_id: UUID, collection_id: UUID, current_user: User
) -> Collection:
    """Get collection or raise 404"""
    collection = await workspace_access.get_collection(
        db, collection_id, current_user.id, workspace_id=workspace_id
    )
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    return collection


async def _get_accessible_document_or_none(
    db: AsyncSession,
    document_id: UUID,
    current_user: User,
) -> Optional[Document]:
    """Return a document only if it belongs to the current user's organization."""
    return await workspace_access.get_accessible_document_or_none(
        db, document_id, current_user.id, getattr(current_user, "organization_id", None)
    )
