"""
Cross-handler scope/access helpers shared by every workspace resource route.

Task 4.2 split ``backend/src/api/threads/workspaces.py`` by resource. These
nested access helpers form a chain (thread -> conversation -> workspace) that
no single resource module owns exclusively, so they live in one shared module
instead of being duplicated or partitioned across resource files.
"""

from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.collection import Collection
from src.models.conversation import Conversation
from src.models.document import Document
from src.models.thread import Thread
from src.models.user import User
from src.models.workspace import Workspace


async def _get_workspace_or_404(
    db: AsyncSession, workspace_id: UUID, current_user: User
) -> Workspace:
    """Get workspace or raise 404, checking access"""
    stmt = (
        select(Workspace)
        .options(
            selectinload(Workspace.members),
            selectinload(Workspace.conversations),
            selectinload(Workspace.collections),
        )
        .where(Workspace.id == workspace_id, Workspace.is_deleted == False)
    )
    result = await db.execute(stmt)
    workspace = result.scalars().first()

    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Check if user is a member or if workspace is public
    if not workspace.is_public and not workspace.is_member(str(current_user.id)):
        if str(workspace.owner_id) != str(current_user.id):
            raise HTTPException(status_code=404, detail="Workspace not found")

    return workspace


async def _get_conversation_or_404(
    db: AsyncSession, workspace_id: UUID, conversation_id: UUID, current_user: User
) -> Conversation:
    """Get conversation or raise 404"""
    workspace = await _get_workspace_or_404(db, workspace_id, current_user)

    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.threads))
        .where(
            Conversation.id == conversation_id,
            Conversation.workspace_id == workspace_id,
            Conversation.is_deleted == False,
        )
    )
    result = await db.execute(stmt)
    conversation = result.scalars().first()

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
    conversation = await _get_conversation_or_404(
        db, workspace_id, conversation_id, current_user
    )

    stmt = (
        select(Thread)
        .options(selectinload(Thread.messages))
        .where(
            Thread.id == thread_id,
            Thread.conversation_id == conversation_id,
            Thread.is_deleted == False,
        )
    )
    result = await db.execute(stmt)
    thread = result.scalars().first()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    return thread


async def _get_collection_or_404(
    db: AsyncSession, workspace_id: UUID, collection_id: UUID, current_user: User
) -> Collection:
    """Get collection or raise 404"""
    workspace = await _get_workspace_or_404(db, workspace_id, current_user)

    stmt = (
        select(Collection)
        .options(selectinload(Collection.documents))
        .where(
            Collection.id == collection_id,
            Collection.workspace_id == workspace_id,
            Collection.is_deleted == False,
        )
    )
    result = await db.execute(stmt)
    collection = result.scalars().first()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    return collection


async def _get_accessible_document_or_none(
    db: AsyncSession,
    document_id: UUID,
    current_user: User,
) -> Optional[Document]:
    """Return a document only if it belongs to the current user's organization."""
    filters = [
        Document.id == document_id,
        Document.is_deleted == False,
    ]
    user_org_id = getattr(current_user, "organization_id", None)
    if user_org_id is not None:
        filters.append(Document.organization_id == user_org_id)
    else:
        filters.append(Document.uploaded_by_user_id == current_user.id)

    doc_stmt = select(Document).where(*filters)
    doc_result = await db.execute(doc_stmt)
    return doc_result.scalars().first()
