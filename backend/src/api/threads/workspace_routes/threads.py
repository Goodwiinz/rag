"""
Thread endpoints, nested and standalone (Task 4.2 split of the former
monolithic ``backend/src/api/threads/workspaces.py``).

``standalone_list_router`` (``list_threads_standalone``) is kept as a separate
router object from ``standalone_router`` (thread CRUD) purely to preserve the
exact route registration order the 4.1 contract test
(``backend/tests/unit/api/test_workspace_route_contract.py``) pins: in the
original file, ``list_threads_standalone`` was defined *after* the standalone
message routes, not alongside the other standalone thread routes.
``workspace_routes/__init__.py`` composes it into ``standalone_router`` at
that same later position.
"""

import logging
import uuid as uuid_mod
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_db
from src.core.dependencies import get_current_user
from src.models.chat_message import ChatMessage, MessageRole
from src.models.conversation import Conversation
from src.models.thread import Thread, ThreadStatus
from src.models.user import User
from src.schemas.chat import (
    ThreadCreate,
    ThreadDetailResponse,
    ThreadListResponse,
    ThreadResponse,
    ThreadUpdate,
)

from .dependencies import (
    _get_conversation_or_404,
    _get_thread_or_404,
    _get_workspace_or_404,
)
from .presenters import (
    _last_message_preview_expression,
    _thread_to_detail_response,
    _thread_to_response,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/workspaces", tags=["workspaces"])

# Standalone router for flat API paths (used by frontend) — thread CRUD.
standalone_router = APIRouter(prefix="/api/v2", tags=["workspaces-flat"])

# See module docstring: list_threads_standalone registers later in the
# original file's order (after the standalone message routes), so it is
# composed into the final standalone_router at that position separately.
standalone_list_router = APIRouter(prefix="/api/v2", tags=["workspaces-flat"])

# ============================================================================
# Thread Endpoints
# ============================================================================


@router.post(
    "/{workspace_id}/conversations/{conversation_id}/threads",
    response_model=ThreadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_thread(
    workspace_id: UUID,
    conversation_id: UUID,
    request: ThreadCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new thread in a conversation"""
    conversation = await _get_conversation_or_404(
        db, workspace_id, conversation_id, current_user
    )

    if not conversation.workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    thread_id = uuid_mod.uuid4()
    thread = Thread(
        id=thread_id,
        conversation_id=conversation_id,
        title=request.title,
        created_by_id=current_user.id,
    )
    db.add(thread)

    # Create initial message if provided
    if request.initial_message:
        message = ChatMessage(
            thread_id=thread_id,
            user_id=current_user.id,
            role=MessageRole.USER,
            content=request.initial_message,
        )
        db.add(message)
        thread.message_count = 1

    # Update conversation activity
    conversation.last_activity_at = datetime.utcnow()

    await db.commit()
    await db.refresh(thread)

    return _thread_to_response(thread)


@router.get(
    "/{workspace_id}/conversations/{conversation_id}/threads",
    response_model=ThreadListResponse,
)
async def list_threads(
    workspace_id: UUID,
    conversation_id: UUID,
    status_filter: Optional[str] = Query(
        None, description="Filter by status: active, resolved, archived"
    ),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List threads in a conversation"""
    conversation = await _get_conversation_or_404(
        db, workspace_id, conversation_id, current_user
    )

    base_conditions = [
        Thread.conversation_id == conversation_id,
        Thread.is_deleted == False,
    ]

    if status_filter:
        try:
            status_enum = ThreadStatus(status_filter)
            base_conditions.append(Thread.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid status: {status_filter}"
            )

    # Count total
    count_stmt = select(func.count(Thread.id)).where(*base_conditions)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    # Fetch threads
    offset = (page - 1) * limit
    preview_expr = _last_message_preview_expression()
    stmt = (
        select(Thread, preview_expr)
        .where(*base_conditions)
        .order_by(Thread.last_message_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    thread_rows = result.all()

    return ThreadListResponse(
        threads=[
            _thread_to_response(thread, last_message_preview=preview)
            for thread, preview in thread_rows
        ],
        total=total,
        page=page,
        limit=limit,
        has_more=(offset + len(thread_rows)) < total,
    )


@router.get(
    "/{workspace_id}/conversations/{conversation_id}/threads/{thread_id}",
    response_model=ThreadDetailResponse,
)
async def get_thread(
    workspace_id: UUID,
    conversation_id: UUID,
    thread_id: UUID,
    include_messages: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get thread details with messages"""
    thread = await _get_thread_or_404(
        db, workspace_id, conversation_id, thread_id, current_user
    )

    return _thread_to_detail_response(thread, include_messages)


@router.patch(
    "/{workspace_id}/conversations/{conversation_id}/threads/{thread_id}",
    response_model=ThreadResponse,
)
async def update_thread(
    workspace_id: UUID,
    conversation_id: UUID,
    thread_id: UUID,
    request: ThreadUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update thread details"""
    thread = await _get_thread_or_404(
        db, workspace_id, conversation_id, thread_id, current_user
    )

    if not thread.conversation.workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    if request.title is not None:
        thread.title = request.title
    if request.summary is not None:
        thread.summary = request.summary
    if request.status is not None:
        thread.status = ThreadStatus(request.status.value)

    thread.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(thread)

    return _thread_to_response(thread)


@router.delete(
    "/{workspace_id}/conversations/{conversation_id}/threads/{thread_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_thread(
    workspace_id: UUID,
    conversation_id: UUID,
    thread_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a thread"""
    thread = await _get_thread_or_404(
        db, workspace_id, conversation_id, thread_id, current_user
    )

    if not thread.conversation.workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    thread.is_deleted = True
    thread.deleted_at = datetime.utcnow()
    await db.commit()


# ============================================================================
# Standalone (Flat) Thread Routes
# These routes allow direct access without full path hierarchy
# ============================================================================


@standalone_router.post(
    "/threads", response_model=ThreadResponse, status_code=status.HTTP_201_CREATED
)
async def create_thread_standalone(
    request: ThreadCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new thread (standalone route - uses conversation_id from request body)"""
    conv_stmt = select(Conversation).where(
        Conversation.id == request.conversation_id, Conversation.is_deleted == False
    )
    conv_result = await db.execute(conv_stmt)
    conversation = conv_result.scalars().first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    workspace = await _get_workspace_or_404(db, conversation.workspace_id, current_user)

    if not workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    thread_id = uuid_mod.uuid4()
    thread = Thread(
        id=thread_id,
        conversation_id=request.conversation_id,
        title=request.title,
        created_by_id=current_user.id,
    )
    db.add(thread)

    # Create initial message if provided
    if request.initial_message:
        message = ChatMessage(
            thread_id=thread_id,
            user_id=current_user.id,
            role=MessageRole.USER,
            content=request.initial_message,
        )
        db.add(message)
        thread.message_count = 1

    # Update conversation activity
    conversation.last_activity_at = datetime.utcnow()

    await db.commit()
    await db.refresh(thread)

    logger.info(f"Thread created in conversation {conversation.id}")

    return _thread_to_response(thread)


@standalone_router.get("/threads/{thread_id}", response_model=ThreadDetailResponse)
async def get_thread_standalone(
    thread_id: UUID,
    include_messages: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get thread details with messages (standalone route)"""
    thread_stmt = (
        select(Thread)
        .options(selectinload(Thread.messages))
        .where(Thread.id == thread_id, Thread.is_deleted == False)
    )
    thread_result = await db.execute(thread_stmt)
    thread = thread_result.scalars().first()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Verify access via conversation -> workspace
    conv_stmt = select(Conversation).where(
        Conversation.id == thread.conversation_id, Conversation.is_deleted == False
    )
    conv_result = await db.execute(conv_stmt)
    conversation = conv_result.scalars().first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    workspace = await _get_workspace_or_404(db, conversation.workspace_id, current_user)

    return _thread_to_detail_response(thread, include_messages)


@standalone_router.patch("/threads/{thread_id}", response_model=ThreadResponse)
async def update_thread_standalone(
    thread_id: UUID,
    request: ThreadUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update thread details (standalone route)"""
    thread_stmt = select(Thread).where(
        Thread.id == thread_id, Thread.is_deleted == False
    )
    thread_result = await db.execute(thread_stmt)
    thread = thread_result.scalars().first()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    conv_stmt = select(Conversation).where(
        Conversation.id == thread.conversation_id, Conversation.is_deleted == False
    )
    conv_result = await db.execute(conv_stmt)
    conversation = conv_result.scalars().first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    workspace = await _get_workspace_or_404(db, conversation.workspace_id, current_user)

    if not workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    if request.title is not None:
        thread.title = request.title
    if request.summary is not None:
        thread.summary = request.summary
    if request.status is not None:
        thread.status = ThreadStatus(request.status.value)

    thread.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(thread)

    return _thread_to_response(thread)


@standalone_router.delete(
    "/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_thread_standalone(
    thread_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a thread (standalone route)"""
    thread_stmt = select(Thread).where(
        Thread.id == thread_id, Thread.is_deleted == False
    )
    thread_result = await db.execute(thread_stmt)
    thread = thread_result.scalars().first()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    conv_stmt = select(Conversation).where(
        Conversation.id == thread.conversation_id, Conversation.is_deleted == False
    )
    conv_result = await db.execute(conv_stmt)
    conversation = conv_result.scalars().first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    workspace = await _get_workspace_or_404(db, conversation.workspace_id, current_user)

    if not workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    thread.is_deleted = True
    thread.deleted_at = datetime.utcnow()
    await db.commit()


@standalone_list_router.get(
    "/conversations/{conversation_id}/threads", response_model=ThreadListResponse
)
async def list_threads_standalone(
    conversation_id: UUID,
    status_filter: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List threads in a conversation (standalone route)"""
    conv_stmt = select(Conversation).where(
        Conversation.id == conversation_id, Conversation.is_deleted == False
    )
    conv_result = await db.execute(conv_stmt)
    conversation = conv_result.scalars().first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    workspace = await _get_workspace_or_404(db, conversation.workspace_id, current_user)

    base_conditions = [
        Thread.conversation_id == conversation_id,
        Thread.is_deleted == False,
    ]

    if status_filter:
        try:
            status_enum = ThreadStatus(status_filter)
            base_conditions.append(Thread.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid status: {status_filter}"
            )

    # Count total
    count_stmt = select(func.count(Thread.id)).where(*base_conditions)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    # Fetch threads
    offset = (page - 1) * limit
    preview_expr = _last_message_preview_expression()
    stmt = (
        select(Thread, preview_expr)
        .where(*base_conditions)
        .order_by(Thread.last_message_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    thread_rows = result.all()

    return ThreadListResponse(
        threads=[
            _thread_to_response(thread, last_message_preview=preview)
            for thread, preview in thread_rows
        ],
        total=total,
        page=page,
        limit=limit,
        has_more=(offset + len(thread_rows)) < total,
    )
