"""
Conversation endpoints, nested and standalone (Task 4.2 split of the former
monolithic ``backend/src/api/threads/workspaces.py``).
"""

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_db
from src.core.dependencies import get_current_user
from src.models.conversation import Conversation
from src.models.thread import Thread
from src.models.user import User
from src.schemas.chat import (
    ConversationCreate,
    ConversationListResponse,
    ConversationResponse,
    ConversationUpdate,
)

from .dependencies import _get_conversation_or_404, _get_workspace_or_404
from .presenters import _conversation_to_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/workspaces", tags=["workspaces"])

# Standalone router for flat API paths (used by frontend)
standalone_router = APIRouter(prefix="/api/v2", tags=["workspaces-flat"])

# ============================================================================
# Conversation Endpoints
# ============================================================================


@router.post(
    "/{workspace_id}/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    workspace_id: UUID,
    request: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new conversation in a workspace"""
    workspace = await _get_workspace_or_404(db, workspace_id, current_user)

    if not workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    conversation = Conversation(
        workspace_id=workspace_id,
        title=request.title,
        description=request.description,
        created_by_id=current_user.id,
    )
    db.add(conversation)
    await db.commit()

    # Re-fetch with eager-loaded relationships to avoid greenlet errors
    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.threads))
        .where(Conversation.id == conversation.id)
    )
    result = await db.execute(stmt)
    conversation = result.scalars().first()

    logger.info(
        f"Conversation '{conversation.title}' created in workspace {workspace_id}"
    )

    return _conversation_to_response(conversation)


@router.get("/{workspace_id}/conversations", response_model=ConversationListResponse)
async def list_conversations(
    workspace_id: UUID,
    include_archived: bool = Query(False),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List conversations in a workspace"""
    workspace = await _get_workspace_or_404(db, workspace_id, current_user)

    base_conditions = [
        Conversation.workspace_id == workspace_id,
        Conversation.is_deleted == False,
    ]

    if not include_archived:
        base_conditions.append(Conversation.is_archived == False)

    # Count total
    count_stmt = select(func.count(Conversation.id)).where(*base_conditions)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    # Fetch conversations (no thread rows — see the aggregate below)
    offset = (page - 1) * limit
    stmt = (
        select(Conversation)
        .where(*base_conditions)
        .order_by(Conversation.last_activity_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    conversations = result.scalars().all()

    # Size the sidebar badges with ONE grouped COUNT/SUM over this page's
    # conversations instead of selectinload-ing every thread row (all columns)
    # per conversation. Mirrors the unfiltered Conversation.threads relationship
    # (hard-delete cascade, no is_deleted filter), so thread_count matches
    # len(self.threads) and message_count matches the per-thread sum exactly.
    counts: dict[UUID, tuple[int, int]] = {}
    conv_ids = [c.id for c in conversations]
    if conv_ids:
        agg_stmt = (
            select(
                Thread.conversation_id,
                func.count(Thread.id),
                func.coalesce(func.sum(Thread.message_count), 0),
            )
            .where(Thread.conversation_id.in_(conv_ids))
            .group_by(Thread.conversation_id)
        )
        agg_result = await db.execute(agg_stmt)
        counts = {row[0]: (row[1], row[2]) for row in agg_result.all()}

    return ConversationListResponse(
        conversations=[
            _conversation_to_response(
                c,
                thread_count=counts.get(c.id, (0, 0))[0],
                message_count=counts.get(c.id, (0, 0))[1],
            )
            for c in conversations
        ],
        total=total,
        page=page,
        limit=limit,
        has_more=(offset + len(conversations)) < total,
    )


@router.get(
    "/{workspace_id}/conversations/{conversation_id}",
    response_model=ConversationResponse,
)
async def get_conversation(
    workspace_id: UUID,
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get conversation details"""
    conversation = await _get_conversation_or_404(
        db, workspace_id, conversation_id, current_user
    )
    return _conversation_to_response(conversation)


@router.patch(
    "/{workspace_id}/conversations/{conversation_id}",
    response_model=ConversationResponse,
)
async def update_conversation(
    workspace_id: UUID,
    conversation_id: UUID,
    request: ConversationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update conversation details"""
    conversation = await _get_conversation_or_404(
        db, workspace_id, conversation_id, current_user
    )
    workspace = conversation.workspace

    if not workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    if request.title is not None:
        conversation.title = request.title
    if request.description is not None:
        conversation.description = request.description
    if request.is_archived is not None:
        conversation.is_archived = request.is_archived
    if request.is_pinned is not None:
        conversation.is_pinned = request.is_pinned

    conversation.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(conversation)

    return _conversation_to_response(conversation)


@router.delete(
    "/{workspace_id}/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_conversation(
    workspace_id: UUID,
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a conversation"""
    conversation = await _get_conversation_or_404(
        db, workspace_id, conversation_id, current_user
    )
    workspace = conversation.workspace

    if not workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    conversation.is_deleted = True
    conversation.deleted_at = datetime.utcnow()
    await db.commit()


# ============================================================================
# Standalone (Flat) Conversation Routes
# These routes allow direct access without full path hierarchy
# ============================================================================


@standalone_router.get(
    "/conversations/{conversation_id}", response_model=ConversationResponse
)
async def get_conversation_standalone(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get conversation details (standalone route)"""
    conv_stmt = (
        select(Conversation)
        .options(selectinload(Conversation.threads))
        .where(Conversation.id == conversation_id, Conversation.is_deleted == False)
    )
    conv_result = await db.execute(conv_stmt)
    conversation = conv_result.scalars().first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check access via workspace
    workspace = await _get_workspace_or_404(db, conversation.workspace_id, current_user)

    return _conversation_to_response(conversation)


@standalone_router.patch(
    "/conversations/{conversation_id}", response_model=ConversationResponse
)
async def update_conversation_standalone(
    conversation_id: UUID,
    request: ConversationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update conversation details (standalone route)"""
    conv_stmt = (
        select(Conversation)
        .options(selectinload(Conversation.threads))
        .where(Conversation.id == conversation_id, Conversation.is_deleted == False)
    )
    conv_result = await db.execute(conv_stmt)
    conversation = conv_result.scalars().first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    workspace = await _get_workspace_or_404(db, conversation.workspace_id, current_user)

    if not workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    if request.title is not None:
        conversation.title = request.title
    if request.description is not None:
        conversation.description = request.description
    if request.is_archived is not None:
        conversation.is_archived = request.is_archived
    if request.is_pinned is not None:
        conversation.is_pinned = request.is_pinned

    conversation.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(conversation)

    return _conversation_to_response(conversation)


@standalone_router.delete(
    "/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_conversation_standalone(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a conversation (standalone route)"""
    conv_stmt = select(Conversation).where(
        Conversation.id == conversation_id, Conversation.is_deleted == False
    )
    conv_result = await db.execute(conv_stmt)
    conversation = conv_result.scalars().first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    workspace = await _get_workspace_or_404(db, conversation.workspace_id, current_user)

    if not workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    conversation.is_deleted = True
    conversation.deleted_at = datetime.utcnow()
    await db.commit()
