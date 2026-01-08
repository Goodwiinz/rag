"""
Threads API endpoints for Terminal Observatory chat system.

Provides REST endpoints for thread and message management.
"""

from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..models.user import User
from ..models.thread import ThreadStatus
from ..services.chat_service import ChatService, get_chat_service
from ..schemas.chat import (
    # Thread schemas
    ThreadCreate,
    ThreadUpdate,
    ThreadResponse,
    ThreadDetailResponse,
    ThreadListResponse,
    # Message schemas
    ChatMessageCreate,
    ChatMessageUpdate,
    ChatMessageResponse,
    ChatMessageListResponse,
    CitationResponse,
    MessageAttachmentResponse,
)

router = APIRouter(prefix="/threads", tags=["Threads"])


# =============================================================================
# Thread Endpoints
# =============================================================================

@router.post("", response_model=ThreadResponse, status_code=status.HTTP_201_CREATED)
async def create_thread(
    data: ThreadCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new thread in a conversation.

    A thread is a specific line of inquiry within a conversation
    (e.g., "Revenue Forecast Investigation").
    """
    service = get_chat_service(db)
    thread = service.create_thread(data, current_user.id)

    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or insufficient permissions"
        )

    return ThreadResponse(
        id=thread.id,
        conversation_id=thread.conversation_id,
        title=thread.title,
        summary=thread.summary,
        status=thread.status,
        last_message_at=thread.last_message_at,
        message_count=thread.message_count,
        token_count=thread.token_count,
        created_by_id=thread.created_by_id,
        created_at=thread.created_at,
        updated_at=thread.updated_at
    )


@router.get("", response_model=ThreadListResponse)
async def list_threads(
    conversation_id: UUID = Query(..., description="Conversation ID to list threads from"),
    status_filter: Optional[ThreadStatus] = Query(None, description="Filter by thread status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List threads in a conversation.
    """
    service = get_chat_service(db)
    threads, total = service.list_threads(
        conversation_id=conversation_id,
        user_id=current_user.id,
        status_filter=status_filter,
        limit=limit,
        offset=offset
    )

    page = (offset // limit) + 1 if limit > 0 else 1
    has_more = (offset + len(threads)) < total

    return ThreadListResponse(
        threads=[
            ThreadResponse(
                id=t.id,
                conversation_id=t.conversation_id,
                title=t.title or t.generate_title(),
                summary=t.summary,
                status=t.status,
                last_message_at=t.last_message_at,
                message_count=t.message_count,
                token_count=t.token_count,
                created_by_id=t.created_by_id,
                created_at=t.created_at,
                updated_at=t.updated_at
            )
            for t in threads
        ],
        total=total,
        page=page,
        limit=limit,
        has_more=has_more
    )


@router.get("/{thread_id}", response_model=ThreadDetailResponse)
async def get_thread(
    thread_id: UUID,
    include_messages: bool = Query(True, description="Include messages in response"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get thread details by ID, optionally including messages.
    """
    service = get_chat_service(db)
    thread = service.get_thread(thread_id, current_user.id, include_messages=include_messages)

    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found or access denied"
        )

    messages = []
    if include_messages and thread.messages:
        messages = [
            _format_message_response(m)
            for m in thread.messages
            if not m.is_deleted
        ]

    return ThreadDetailResponse(
        id=thread.id,
        conversation_id=thread.conversation_id,
        title=thread.title or thread.generate_title(),
        summary=thread.summary,
        status=thread.status,
        last_message_at=thread.last_message_at,
        message_count=thread.message_count,
        token_count=thread.token_count,
        created_by_id=thread.created_by_id,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        messages=messages
    )


@router.patch("/{thread_id}", response_model=ThreadResponse)
async def update_thread(
    thread_id: UUID,
    data: ThreadUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update thread properties.
    """
    service = get_chat_service(db)
    thread = service.update_thread(thread_id, data, current_user.id)

    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found or insufficient permissions"
        )

    return ThreadResponse(
        id=thread.id,
        conversation_id=thread.conversation_id,
        title=thread.title,
        summary=thread.summary,
        status=thread.status,
        last_message_at=thread.last_message_at,
        message_count=thread.message_count,
        token_count=thread.token_count,
        created_by_id=thread.created_by_id,
        created_at=thread.created_at,
        updated_at=thread.updated_at
    )


@router.delete("/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread(
    thread_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a thread (soft delete).
    """
    service = get_chat_service(db)
    success = service.delete_thread(thread_id, current_user.id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found or insufficient permissions"
        )


@router.post("/{thread_id}/resolve", response_model=ThreadResponse)
async def resolve_thread(
    thread_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark a thread as resolved.
    """
    return await update_thread(
        thread_id,
        ThreadUpdate(status=ThreadStatus.RESOLVED),
        current_user,
        db
    )


@router.post("/{thread_id}/reopen", response_model=ThreadResponse)
async def reopen_thread(
    thread_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Reopen a resolved thread.
    """
    return await update_thread(
        thread_id,
        ThreadUpdate(status=ThreadStatus.ACTIVE),
        current_user,
        db
    )


@router.post("/{thread_id}/archive", response_model=ThreadResponse)
async def archive_thread(
    thread_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Archive a thread.
    """
    return await update_thread(
        thread_id,
        ThreadUpdate(status=ThreadStatus.ARCHIVED),
        current_user,
        db
    )


@router.get("/{thread_id}/context")
async def get_thread_context(
    thread_id: UUID,
    max_messages: int = Query(20, ge=1, le=100),
    max_tokens: int = Query(4000, ge=100, le=16000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get thread messages formatted for LLM context.

    Returns messages in the format expected by LLM APIs, limited by count or tokens.
    """
    service = get_chat_service(db)
    context = service.get_thread_context(
        thread_id=thread_id,
        user_id=current_user.id,
        max_messages=max_messages,
        max_tokens=max_tokens
    )

    if not context:
        # Could be empty thread or no access
        thread = service.get_thread(thread_id, current_user.id)
        if not thread:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Thread not found or access denied"
            )

    return {
        "thread_id": str(thread_id),
        "messages": context,
        "message_count": len(context)
    }


# =============================================================================
# Message Endpoints
# =============================================================================

@router.post("/{thread_id}/messages", response_model=ChatMessageResponse, status_code=status.HTTP_201_CREATED)
async def create_message(
    thread_id: UUID,
    data: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new message in a thread.
    """
    # Ensure thread_id matches
    if data.thread_id != thread_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Thread ID in path must match thread_id in body"
        )

    service = get_chat_service(db)
    message = service.create_message(data, current_user.id)

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found or insufficient permissions"
        )

    return _format_message_response(message)


@router.get("/{thread_id}/messages", response_model=ChatMessageListResponse)
async def list_messages(
    thread_id: UUID,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    before_id: Optional[UUID] = Query(None, description="Get messages before this message ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List messages in a thread.
    """
    service = get_chat_service(db)
    messages, total = service.list_messages(
        thread_id=thread_id,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        before_id=before_id
    )

    page = (offset // limit) + 1 if limit > 0 else 1
    has_more = (offset + len(messages)) < total

    return ChatMessageListResponse(
        messages=[_format_message_response(m) for m in messages],
        total=total,
        page=page,
        limit=limit,
        has_more=has_more
    )


@router.get("/{thread_id}/messages/{message_id}", response_model=ChatMessageResponse)
async def get_message(
    thread_id: UUID,
    message_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific message by ID.
    """
    service = get_chat_service(db)
    message = service.get_message(message_id, current_user.id)

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found or access denied"
        )

    # Verify thread matches
    if message.thread_id != thread_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found in this thread"
        )

    return _format_message_response(message)


@router.patch("/{thread_id}/messages/{message_id}", response_model=ChatMessageResponse)
async def update_message_feedback(
    thread_id: UUID,
    message_id: UUID,
    data: ChatMessageUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update message feedback (rating and text).

    Note: Message content cannot be edited, only feedback can be updated.
    """
    service = get_chat_service(db)
    message = service.update_message_feedback(message_id, data, current_user.id)

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found or access denied"
        )

    # Verify thread matches
    if message.thread_id != thread_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found in this thread"
        )

    return _format_message_response(message)


@router.delete("/{thread_id}/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    thread_id: UUID,
    message_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a message (soft delete).

    Only the message author or workspace admin can delete messages.
    """
    service = get_chat_service(db)

    # First verify the message belongs to this thread
    message = service.get_message(message_id, current_user.id)
    if message and message.thread_id != thread_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found in this thread"
        )

    success = service.delete_message(message_id, current_user.id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found or insufficient permissions"
        )


# =============================================================================
# Helper Functions
# =============================================================================

def _format_message_response(message) -> ChatMessageResponse:
    """Format a ChatMessage model to ChatMessageResponse schema"""
    citations = []
    if message.citations:
        citations = [
            CitationResponse(
                id=c.id,
                document_id=c.document_id,
                external_reference_id=c.external_reference_id,  # For arXiv IDs, etc.
                chunk_index=c.chunk_index,
                chunk_id=c.chunk_id,
                snippet=c.snippet,
                snippet_preview=c.snippet_preview,
                page_number=c.page_number,
                score=c.score,
                rerank_score=c.rerank_score,
                # Use stored title/type for external refs, or get from document relationship
                document_title=c.document_title or (c.document.title if hasattr(c, 'document') and c.document else None),
                document_type=c.document_type or (c.document.type.value if hasattr(c, 'document') and c.document and c.document.type else None)
            )
            for c in message.citations
        ]

    attachments = []
    if message.attachments:
        attachments = [
            MessageAttachmentResponse(
                id=a.id,
                document_id=a.document_id,
                display_name=a.display_name,
                thumbnail_url=a.thumbnail_url,
                document_title=a.document.title if hasattr(a, 'document') and a.document else None,
                document_type=a.document.type.value if hasattr(a, 'document') and a.document and a.document.type else None,
                mime_type=a.document.mime_type if hasattr(a, 'document') and a.document else None
            )
            for a in message.attachments
        ]

    return ChatMessageResponse(
        id=message.id,
        thread_id=message.thread_id,
        user_id=message.user_id,
        role=message.role,
        content=message.content,
        token_count=message.token_count,
        latency_ms=message.latency_ms,
        model_name=message.model_name,
        model_version=message.model_version,
        tool_name=message.tool_name,
        tool_call_id=message.tool_call_id,
        feedback_rating=message.feedback_rating,
        feedback_text=message.feedback_text,
        created_at=message.created_at,
        updated_at=message.updated_at,
        citations=citations,
        attachments=attachments
    )
