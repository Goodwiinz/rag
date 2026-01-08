"""
Thread-centric Workspace API endpoints for Terminal Observatory
Provides CRUD operations for Workspaces, Conversations, Threads, Messages, and Collections
"""

from typing import Optional, List
from datetime import datetime
from uuid import UUID
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func

from src.core.database import get_db
from src.core.dependencies import get_current_user
from src.models.user import User
from src.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from src.models.conversation import Conversation
from src.models.thread import Thread, ThreadStatus
from src.models.chat_message import ChatMessage, MessageRole
from src.models.citation import Citation
from src.models.collection import Collection, CollectionDocument
from src.models.document import Document
from src.schemas.chat import (
    # Workspace schemas
    WorkspaceCreate, WorkspaceUpdate, WorkspaceResponse, WorkspaceDetailResponse,
    WorkspaceMemberCreate, WorkspaceMemberUpdate, WorkspaceMemberResponse,
    # Conversation schemas
    ConversationCreate, ConversationUpdate, ConversationResponse, ConversationListResponse,
    # Thread schemas
    ThreadCreate, ThreadUpdate, ThreadResponse, ThreadDetailResponse, ThreadListResponse,
    # Message schemas
    ChatMessageCreate, ChatMessageUpdate, ChatMessageResponse, ChatMessageListResponse,
    CitationResponse, MessageAttachmentResponse,
    # Collection schemas
    CollectionCreate, CollectionUpdate, CollectionResponse, CollectionDetailResponse,
    CollectionListResponse, CollectionDocumentAdd, CollectionDocumentRemove,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/workspaces", tags=["workspaces"])

# Standalone router for flat API paths (used by frontend)
standalone_router = APIRouter(prefix="/api/v2", tags=["workspaces-flat"])

# ============================================================================
# Workspace Endpoints
# ============================================================================

@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    request: WorkspaceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new workspace"""
    workspace = Workspace(
        name=request.name,
        description=request.description,
        is_public=request.is_public,
        owner_id=current_user.id,
        organization_id=request.organization_id
    )
    db.add(workspace)

    # Add owner as member with OWNER role
    member = WorkspaceMember(
        workspace=workspace,
        user_id=current_user.id,
        role=WorkspaceRole.OWNER
    )
    db.add(member)

    db.commit()
    db.refresh(workspace)

    logger.info(f"Workspace '{workspace.name}' created by user {current_user.id}")

    return _workspace_to_response(workspace)


@router.get("", response_model=List[WorkspaceResponse])
async def list_workspaces(
    include_archived: bool = Query(False, description="Include archived workspaces"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List workspaces accessible by the current user"""
    query = db.query(Workspace).join(WorkspaceMember).filter(
        WorkspaceMember.user_id == current_user.id,
        Workspace.is_deleted == False
    )

    if not include_archived:
        query = query.filter(Workspace.is_archived == False)

    workspaces = query.order_by(Workspace.updated_at.desc()).offset(offset).limit(limit).all()

    return [_workspace_to_response(w) for w in workspaces]


@router.get("/{workspace_id}", response_model=WorkspaceDetailResponse)
async def get_workspace(
    workspace_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get workspace details with members"""
    workspace = _get_workspace_or_404(db, workspace_id, current_user)

    return _workspace_to_detail_response(workspace)


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: UUID,
    request: WorkspaceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update workspace details"""
    workspace = _get_workspace_or_404(db, workspace_id, current_user)

    # Check permission
    if not workspace.can_user_admin(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    # Update fields
    if request.name is not None:
        workspace.name = request.name
    if request.description is not None:
        workspace.description = request.description
    if request.is_public is not None:
        workspace.is_public = request.is_public
    if request.is_archived is not None:
        workspace.is_archived = request.is_archived

    workspace.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(workspace)

    return _workspace_to_response(workspace)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    workspace_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Soft-delete a workspace"""
    workspace = _get_workspace_or_404(db, workspace_id, current_user)

    # Only owner can delete
    if str(workspace.owner_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Only the owner can delete a workspace")

    workspace.is_deleted = True
    workspace.deleted_at = datetime.utcnow()
    db.commit()

    logger.info(f"Workspace {workspace_id} deleted by user {current_user.id}")


# ============================================================================
# Workspace Member Endpoints
# ============================================================================

@router.post("/{workspace_id}/members", response_model=WorkspaceMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_workspace_member(
    workspace_id: UUID,
    request: WorkspaceMemberCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a member to a workspace"""
    workspace = _get_workspace_or_404(db, workspace_id, current_user)

    if not workspace.can_user_admin(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions to add members")

    # Check if user already a member
    existing = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == request.user_id,
        WorkspaceMember.is_deleted == False
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="User is already a member")

    member = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=request.user_id,
        role=request.role,
        invited_by_id=current_user.id
    )
    db.add(member)
    db.commit()
    db.refresh(member)

    return _member_to_response(member)


@router.patch("/{workspace_id}/members/{user_id}", response_model=WorkspaceMemberResponse)
async def update_member_role(
    workspace_id: UUID,
    user_id: UUID,
    request: WorkspaceMemberUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a member's role"""
    workspace = _get_workspace_or_404(db, workspace_id, current_user)

    if not workspace.can_user_admin(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    member = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == user_id,
        WorkspaceMember.is_deleted == False
    ).first()

    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    # Prevent changing owner role
    if member.role == WorkspaceRole.OWNER:
        raise HTTPException(status_code=400, detail="Cannot change owner role")

    member.role = request.role
    member.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(member)

    return _member_to_response(member)


@router.delete("/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_workspace_member(
    workspace_id: UUID,
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove a member from a workspace"""
    workspace = _get_workspace_or_404(db, workspace_id, current_user)

    # Users can remove themselves, admins can remove others
    if str(user_id) != str(current_user.id) and not workspace.can_user_admin(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    member = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == user_id,
        WorkspaceMember.is_deleted == False
    ).first()

    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    # Prevent removing owner
    if member.role == WorkspaceRole.OWNER:
        raise HTTPException(status_code=400, detail="Cannot remove workspace owner")

    member.is_deleted = True
    member.deleted_at = datetime.utcnow()
    db.commit()


# ============================================================================
# Conversation Endpoints
# ============================================================================

@router.post("/{workspace_id}/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    workspace_id: UUID,
    request: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new conversation in a workspace"""
    workspace = _get_workspace_or_404(db, workspace_id, current_user)

    if not workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    conversation = Conversation(
        workspace_id=workspace_id,
        title=request.title,
        description=request.description,
        created_by_id=current_user.id
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    logger.info(f"Conversation '{conversation.title}' created in workspace {workspace_id}")

    return _conversation_to_response(conversation)


@router.get("/{workspace_id}/conversations", response_model=ConversationListResponse)
async def list_conversations(
    workspace_id: UUID,
    include_archived: bool = Query(False),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List conversations in a workspace"""
    workspace = _get_workspace_or_404(db, workspace_id, current_user)

    query = db.query(Conversation).filter(
        Conversation.workspace_id == workspace_id,
        Conversation.is_deleted == False
    )

    if not include_archived:
        query = query.filter(Conversation.is_archived == False)

    total = query.count()
    offset = (page - 1) * limit
    conversations = query.order_by(Conversation.last_activity_at.desc()).offset(offset).limit(limit).all()

    return ConversationListResponse(
        conversations=[_conversation_to_response(c) for c in conversations],
        total=total,
        page=page,
        limit=limit,
        has_more=(offset + len(conversations)) < total
    )


@router.get("/{workspace_id}/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    workspace_id: UUID,
    conversation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get conversation details"""
    conversation = _get_conversation_or_404(db, workspace_id, conversation_id, current_user)
    return _conversation_to_response(conversation)


@router.patch("/{workspace_id}/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    workspace_id: UUID,
    conversation_id: UUID,
    request: ConversationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update conversation details"""
    conversation = _get_conversation_or_404(db, workspace_id, conversation_id, current_user)
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
    db.commit()
    db.refresh(conversation)

    return _conversation_to_response(conversation)


@router.delete("/{workspace_id}/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    workspace_id: UUID,
    conversation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Soft-delete a conversation"""
    conversation = _get_conversation_or_404(db, workspace_id, conversation_id, current_user)
    workspace = conversation.workspace

    if not workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    conversation.is_deleted = True
    conversation.deleted_at = datetime.utcnow()
    db.commit()


# ============================================================================
# Thread Endpoints
# ============================================================================

@router.post("/{workspace_id}/conversations/{conversation_id}/threads", response_model=ThreadResponse, status_code=status.HTTP_201_CREATED)
async def create_thread(
    workspace_id: UUID,
    conversation_id: UUID,
    request: ThreadCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new thread in a conversation"""
    conversation = _get_conversation_or_404(db, workspace_id, conversation_id, current_user)

    if not conversation.workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    thread = Thread(
        conversation_id=conversation_id,
        title=request.title,
        created_by_id=current_user.id
    )
    db.add(thread)

    # Create initial message if provided
    if request.initial_message:
        message = ChatMessage(
            thread=thread,
            user_id=current_user.id,
            role=MessageRole.USER,
            content=request.initial_message
        )
        db.add(message)
        thread.message_count = 1

    # Update conversation activity
    conversation.last_activity_at = datetime.utcnow()

    db.commit()
    db.refresh(thread)

    return _thread_to_response(thread)


@router.get("/{workspace_id}/conversations/{conversation_id}/threads", response_model=ThreadListResponse)
async def list_threads(
    workspace_id: UUID,
    conversation_id: UUID,
    status_filter: Optional[str] = Query(None, description="Filter by status: active, resolved, archived"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List threads in a conversation"""
    conversation = _get_conversation_or_404(db, workspace_id, conversation_id, current_user)

    query = db.query(Thread).filter(
        Thread.conversation_id == conversation_id,
        Thread.is_deleted == False
    )

    if status_filter:
        try:
            status_enum = ThreadStatus(status_filter)
            query = query.filter(Thread.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status_filter}")

    total = query.count()
    offset = (page - 1) * limit
    threads = query.order_by(Thread.last_message_at.desc()).offset(offset).limit(limit).all()

    return ThreadListResponse(
        threads=[_thread_to_response(t) for t in threads],
        total=total,
        page=page,
        limit=limit,
        has_more=(offset + len(threads)) < total
    )


@router.get("/{workspace_id}/conversations/{conversation_id}/threads/{thread_id}", response_model=ThreadDetailResponse)
async def get_thread(
    workspace_id: UUID,
    conversation_id: UUID,
    thread_id: UUID,
    include_messages: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get thread details with messages"""
    thread = _get_thread_or_404(db, workspace_id, conversation_id, thread_id, current_user)

    return _thread_to_detail_response(thread, include_messages)


@router.patch("/{workspace_id}/conversations/{conversation_id}/threads/{thread_id}", response_model=ThreadResponse)
async def update_thread(
    workspace_id: UUID,
    conversation_id: UUID,
    thread_id: UUID,
    request: ThreadUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update thread details"""
    thread = _get_thread_or_404(db, workspace_id, conversation_id, thread_id, current_user)

    if not thread.conversation.workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    if request.title is not None:
        thread.title = request.title
    if request.summary is not None:
        thread.summary = request.summary
    if request.status is not None:
        thread.status = ThreadStatus(request.status.value)

    thread.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(thread)

    return _thread_to_response(thread)


@router.delete("/{workspace_id}/conversations/{conversation_id}/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread(
    workspace_id: UUID,
    conversation_id: UUID,
    thread_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Soft-delete a thread"""
    thread = _get_thread_or_404(db, workspace_id, conversation_id, thread_id, current_user)

    if not thread.conversation.workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    thread.is_deleted = True
    thread.deleted_at = datetime.utcnow()
    db.commit()


# ============================================================================
# Message Endpoints
# ============================================================================

@router.post("/{workspace_id}/conversations/{conversation_id}/threads/{thread_id}/messages", response_model=ChatMessageResponse, status_code=status.HTTP_201_CREATED)
async def create_message(
    workspace_id: UUID,
    conversation_id: UUID,
    thread_id: UUID,
    request: ChatMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new message in a thread"""
    thread = _get_thread_or_404(db, workspace_id, conversation_id, thread_id, current_user)

    if not thread.conversation.workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    message = ChatMessage(
        thread_id=thread_id,
        user_id=current_user.id if request.role.value == "user" else None,
        role=MessageRole(request.role.value),
        content=request.content
    )
    db.add(message)
    db.flush()  # Flush to get message.id for citations

    # Handle citations (for assistant messages with RAG sources)
    if request.citations:
        for cit in request.citations:
            citation = Citation(
                message_id=message.id,
                document_id=cit.document_id,  # May be None for external refs
                external_reference_id=cit.external_reference_id,
                document_title=cit.document_title,
                document_type=cit.document_type,
                chunk_index=cit.chunk_index,
                chunk_id=cit.chunk_id,
                snippet=cit.snippet,
                page_number=cit.page_number,
                score=cit.score,
                rerank_score=cit.rerank_score
            )
            db.add(citation)

    # Update thread stats
    thread.message_count = (thread.message_count or 0) + 1
    thread.last_message_at = datetime.utcnow()

    # Update conversation activity
    thread.conversation.last_activity_at = datetime.utcnow()

    db.commit()
    
    # Re-query with eager loading to get citations with document info
    message = db.query(ChatMessage).options(
        joinedload(ChatMessage.citations).joinedload(Citation.document),
        joinedload(ChatMessage.attachments)
    ).filter(ChatMessage.id == message.id).first()

    return _message_to_response(message)


@router.get("/{workspace_id}/conversations/{conversation_id}/threads/{thread_id}/messages", response_model=ChatMessageListResponse)
async def list_messages(
    workspace_id: UUID,
    conversation_id: UUID,
    thread_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List messages in a thread"""
    thread = _get_thread_or_404(db, workspace_id, conversation_id, thread_id, current_user)

    # Count total messages first (without joinedload for efficiency)
    total = db.query(ChatMessage).filter(
        ChatMessage.thread_id == thread_id,
        ChatMessage.is_deleted == False
    ).count()

    # Query with eager loading of citations and their documents
    offset = (page - 1) * limit
    messages = db.query(ChatMessage).options(
        joinedload(ChatMessage.citations).joinedload(Citation.document),
        joinedload(ChatMessage.attachments)
    ).filter(
        ChatMessage.thread_id == thread_id,
        ChatMessage.is_deleted == False
    ).order_by(ChatMessage.created_at.asc()).offset(offset).limit(limit).all()

    return ChatMessageListResponse(
        messages=[_message_to_response(m) for m in messages],
        total=total,
        page=page,
        limit=limit,
        has_more=(offset + len(messages)) < total
    )


@router.patch("/{workspace_id}/conversations/{conversation_id}/threads/{thread_id}/messages/{message_id}", response_model=ChatMessageResponse)
async def update_message_feedback(
    workspace_id: UUID,
    conversation_id: UUID,
    thread_id: UUID,
    message_id: UUID,
    request: ChatMessageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update message feedback"""
    thread = _get_thread_or_404(db, workspace_id, conversation_id, thread_id, current_user)

    message = db.query(ChatMessage).filter(
        ChatMessage.id == message_id,
        ChatMessage.thread_id == thread_id,
        ChatMessage.is_deleted == False
    ).first()

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    if request.feedback_rating is not None:
        message.feedback_rating = request.feedback_rating
    if request.feedback_text is not None:
        message.feedback_text = request.feedback_text

    message.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(message)

    return _message_to_response(message)


# ============================================================================
# Collection Endpoints
# ============================================================================

@router.post("/{workspace_id}/collections", response_model=CollectionResponse, status_code=status.HTTP_201_CREATED)
async def create_collection(
    workspace_id: UUID,
    request: CollectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new collection in a workspace"""
    workspace = _get_workspace_or_404(db, workspace_id, current_user)

    if not workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    collection = Collection(
        workspace_id=workspace_id,
        name=request.name,
        description=request.description,
        color=request.color,
        icon=request.icon
    )
    db.add(collection)

    # Add initial documents if provided
    if request.document_ids:
        for i, doc_id in enumerate(request.document_ids):
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if doc:
                collection_doc = CollectionDocument(
                    collection=collection,
                    document_id=doc_id,
                    sort_order=i
                )
                db.add(collection_doc)

    db.commit()
    db.refresh(collection)

    return _collection_to_response(collection)


@router.get("/{workspace_id}/collections", response_model=CollectionListResponse)
async def list_collections(
    workspace_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List collections in a workspace"""
    workspace = _get_workspace_or_404(db, workspace_id, current_user)

    query = db.query(Collection).filter(
        Collection.workspace_id == workspace_id,
        Collection.is_deleted == False
    )

    total = query.count()
    offset = (page - 1) * limit
    collections = query.order_by(Collection.name).offset(offset).limit(limit).all()

    return CollectionListResponse(
        collections=[_collection_to_response(c) for c in collections],
        total=total,
        page=page,
        limit=limit,
        has_more=(offset + len(collections)) < total
    )


@router.get("/{workspace_id}/collections/{collection_id}", response_model=CollectionDetailResponse)
async def get_collection(
    workspace_id: UUID,
    collection_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get collection details with documents"""
    collection = _get_collection_or_404(db, workspace_id, collection_id, current_user)

    return _collection_to_detail_response(collection)


@router.patch("/{workspace_id}/collections/{collection_id}", response_model=CollectionResponse)
async def update_collection(
    workspace_id: UUID,
    collection_id: UUID,
    request: CollectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update collection details"""
    collection = _get_collection_or_404(db, workspace_id, collection_id, current_user)
    workspace = collection.workspace

    if not workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    if request.name is not None:
        collection.name = request.name
    if request.description is not None:
        collection.description = request.description
    if request.color is not None:
        collection.color = request.color
    if request.icon is not None:
        collection.icon = request.icon

    collection.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(collection)

    return _collection_to_response(collection)


@router.delete("/{workspace_id}/collections/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(
    workspace_id: UUID,
    collection_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Soft-delete a collection"""
    collection = _get_collection_or_404(db, workspace_id, collection_id, current_user)

    if not collection.workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    collection.is_deleted = True
    collection.deleted_at = datetime.utcnow()
    db.commit()


@router.post("/{workspace_id}/collections/{collection_id}/documents", response_model=CollectionDetailResponse)
async def add_documents_to_collection(
    workspace_id: UUID,
    collection_id: UUID,
    request: CollectionDocumentAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add documents to a collection"""
    collection = _get_collection_or_404(db, workspace_id, collection_id, current_user)

    if not collection.workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    # Get current max sort order
    max_order = db.query(func.max(CollectionDocument.sort_order)).filter(
        CollectionDocument.collection_id == collection_id
    ).scalar() or 0

    for i, doc_id in enumerate(request.document_ids):
        # Check if document exists
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            continue

        # Check if already in collection
        existing = db.query(CollectionDocument).filter(
            CollectionDocument.collection_id == collection_id,
            CollectionDocument.document_id == doc_id,
            CollectionDocument.is_deleted == False
        ).first()

        if not existing:
            collection_doc = CollectionDocument(
                collection_id=collection_id,
                document_id=doc_id,
                sort_order=max_order + i + 1
            )
            db.add(collection_doc)

    db.commit()
    db.refresh(collection)

    return _collection_to_detail_response(collection)


@router.delete("/{workspace_id}/collections/{collection_id}/documents", response_model=CollectionDetailResponse)
async def remove_documents_from_collection(
    workspace_id: UUID,
    collection_id: UUID,
    request: CollectionDocumentRemove,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove documents from a collection"""
    collection = _get_collection_or_404(db, workspace_id, collection_id, current_user)

    if not collection.workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    for doc_id in request.document_ids:
        collection_doc = db.query(CollectionDocument).filter(
            CollectionDocument.collection_id == collection_id,
            CollectionDocument.document_id == doc_id,
            CollectionDocument.is_deleted == False
        ).first()

        if collection_doc:
            collection_doc.is_deleted = True
            collection_doc.deleted_at = datetime.utcnow()

    db.commit()
    db.refresh(collection)

    return _collection_to_detail_response(collection)


# ============================================================================
# Helper Functions
# ============================================================================

def _get_workspace_or_404(db: Session, workspace_id: UUID, current_user: User) -> Workspace:
    """Get workspace or raise 404, checking access"""
    workspace = db.query(Workspace).options(
        joinedload(Workspace.members)
    ).filter(
        Workspace.id == workspace_id,
        Workspace.is_deleted == False
    ).first()

    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Check if user is a member or if workspace is public
    if not workspace.is_public and not workspace.is_member(str(current_user.id)):
        if str(workspace.owner_id) != str(current_user.id):
            raise HTTPException(status_code=404, detail="Workspace not found")

    return workspace


def _get_conversation_or_404(db: Session, workspace_id: UUID, conversation_id: UUID, current_user: User) -> Conversation:
    """Get conversation or raise 404"""
    workspace = _get_workspace_or_404(db, workspace_id, current_user)

    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.workspace_id == workspace_id,
        Conversation.is_deleted == False
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return conversation


def _get_thread_or_404(db: Session, workspace_id: UUID, conversation_id: UUID, thread_id: UUID, current_user: User) -> Thread:
    """Get thread or raise 404"""
    conversation = _get_conversation_or_404(db, workspace_id, conversation_id, current_user)

    thread = db.query(Thread).options(
        joinedload(Thread.messages)
    ).filter(
        Thread.id == thread_id,
        Thread.conversation_id == conversation_id,
        Thread.is_deleted == False
    ).first()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    return thread


def _get_collection_or_404(db: Session, workspace_id: UUID, collection_id: UUID, current_user: User) -> Collection:
    """Get collection or raise 404"""
    workspace = _get_workspace_or_404(db, workspace_id, current_user)

    collection = db.query(Collection).options(
        joinedload(Collection.documents)
    ).filter(
        Collection.id == collection_id,
        Collection.workspace_id == workspace_id,
        Collection.is_deleted == False
    ).first()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    return collection


def _workspace_to_response(workspace: Workspace) -> WorkspaceResponse:
    """Convert Workspace model to response schema"""
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        description=workspace.description,
        is_public=workspace.is_public,
        is_archived=workspace.is_archived,
        owner_id=workspace.owner_id,
        organization_id=workspace.organization_id,
        member_count=len(workspace.members) if workspace.members else 0,
        conversation_count=len(workspace.conversations) if workspace.conversations else 0,
        collection_count=len(workspace.collections) if workspace.collections else 0,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at
    )


def _workspace_to_detail_response(workspace: Workspace) -> WorkspaceDetailResponse:
    """Convert Workspace model to detail response schema"""
    return WorkspaceDetailResponse(
        id=workspace.id,
        name=workspace.name,
        description=workspace.description,
        is_public=workspace.is_public,
        is_archived=workspace.is_archived,
        owner_id=workspace.owner_id,
        organization_id=workspace.organization_id,
        member_count=len(workspace.members) if workspace.members else 0,
        conversation_count=len(workspace.conversations) if workspace.conversations else 0,
        collection_count=len(workspace.collections) if workspace.collections else 0,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
        members=[_member_to_response(m) for m in workspace.members if not m.is_deleted]
    )


def _member_to_response(member: WorkspaceMember) -> WorkspaceMemberResponse:
    """Convert WorkspaceMember model to response schema"""
    return WorkspaceMemberResponse(
        id=member.id,
        workspace_id=member.workspace_id,
        user_id=member.user_id,
        role=member.role.value if member.role else "viewer",
        joined_at=member.joined_at,
        invited_by_id=member.invited_by_id,
        created_at=member.created_at,
        updated_at=member.updated_at,
        user_email=member.user.email if member.user else None,
        user_name=member.user.full_name if member.user else None
    )


def _conversation_to_response(conversation: Conversation) -> ConversationResponse:
    """Convert Conversation model to response schema"""
    return ConversationResponse(
        id=conversation.id,
        workspace_id=conversation.workspace_id,
        title=conversation.title,
        description=conversation.description,
        is_archived=conversation.is_archived,
        is_pinned=conversation.is_pinned,
        last_activity_at=conversation.last_activity_at,
        created_by_id=conversation.created_by_id,
        thread_count=conversation.thread_count,
        message_count=sum(t.message_count or 0 for t in conversation.threads) if conversation.threads else 0,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at
    )


def _thread_to_response(thread: Thread) -> ThreadResponse:
    """Convert Thread model to response schema"""
    return ThreadResponse(
        id=thread.id,
        conversation_id=thread.conversation_id,
        title=thread.title or thread.generate_title(),
        summary=thread.summary,
        status=thread.status.value if thread.status else "active",
        last_message_at=thread.last_message_at,
        message_count=thread.message_count or 0,
        token_count=thread.token_count or 0,
        created_by_id=thread.created_by_id,
        created_at=thread.created_at,
        updated_at=thread.updated_at
    )


def _thread_to_detail_response(thread: Thread, include_messages: bool = True) -> ThreadDetailResponse:
    """Convert Thread model to detail response schema"""
    messages = []
    if include_messages and thread.messages:
        messages = [_message_to_response(m) for m in thread.messages if not m.is_deleted]

    return ThreadDetailResponse(
        id=thread.id,
        conversation_id=thread.conversation_id,
        title=thread.title or thread.generate_title(),
        summary=thread.summary,
        status=thread.status.value if thread.status else "active",
        last_message_at=thread.last_message_at,
        message_count=thread.message_count or 0,
        token_count=thread.token_count or 0,
        created_by_id=thread.created_by_id,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        messages=messages
    )


def _message_to_response(message: ChatMessage) -> ChatMessageResponse:
    """Convert ChatMessage model to response schema"""
    return ChatMessageResponse(
        id=message.id,
        thread_id=message.thread_id,
        user_id=message.user_id,
        role=message.role.value if message.role else "user",
        content=message.content,
        token_count=message.token_count or 0,
        latency_ms=message.latency_ms,
        model_name=message.model_name,
        model_version=message.model_version,
        tool_name=message.tool_name,
        tool_call_id=message.tool_call_id,
        feedback_rating=message.feedback_rating,
        feedback_text=message.feedback_text,
        citations=[_citation_to_response(c) for c in message.citations] if message.citations else [],
        attachments=[_attachment_to_response(a) for a in message.attachments] if message.attachments else [],
        created_at=message.created_at,
        updated_at=message.updated_at
    )


def _citation_to_response(citation) -> CitationResponse:
    """Convert Citation model to response schema"""
    return CitationResponse(
        id=citation.id,
        document_id=citation.document_id,
        chunk_index=citation.chunk_index,
        chunk_id=citation.chunk_id,
        snippet=citation.snippet,
        snippet_preview=citation.snippet[:200] + "..." if citation.snippet and len(citation.snippet) > 200 else citation.snippet,
        page_number=citation.page_number,
        score=citation.score,
        rerank_score=citation.rerank_score,
        document_title=citation.document.title if citation.document else None,
        document_type=citation.document.document_type.value if citation.document and citation.document.document_type else None
    )


def _attachment_to_response(attachment) -> MessageAttachmentResponse:
    """Convert MessageAttachment model to response schema"""
    return MessageAttachmentResponse(
        id=attachment.id,
        document_id=attachment.document_id,
        display_name=attachment.display_name,
        thumbnail_url=attachment.thumbnail_url,
        document_title=attachment.document.title if attachment.document else None,
        document_type=attachment.document.document_type.value if attachment.document and attachment.document.document_type else None,
        mime_type=attachment.document.mime_type if attachment.document else None
    )


def _collection_to_response(collection: Collection) -> CollectionResponse:
    """Convert Collection model to response schema"""
    return CollectionResponse(
        id=collection.id,
        workspace_id=collection.workspace_id,
        name=collection.name,
        description=collection.description,
        color=collection.color,
        icon=collection.icon,
        document_count=collection.document_count,
        created_at=collection.created_at,
        updated_at=collection.updated_at
    )


def _collection_to_detail_response(collection: Collection) -> CollectionDetailResponse:
    """Convert Collection model to detail response schema"""
    documents = []
    if collection.documents:
        for cd in collection.documents:
            if not cd.is_deleted and cd.document:
                documents.append({
                    "id": str(cd.document.id),
                    "title": cd.document.title,
                    "document_type": cd.document.document_type.value if cd.document.document_type else None,
                    "sort_order": cd.sort_order
                })

    return CollectionDetailResponse(
        id=collection.id,
        workspace_id=collection.workspace_id,
        name=collection.name,
        description=collection.description,
        color=collection.color,
        icon=collection.icon,
        document_count=collection.document_count,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
        documents=documents
    )


# ============================================================================
# Standalone (Flat) API Routes
# These routes allow direct access without full path hierarchy
# ============================================================================

@standalone_router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation_standalone(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get conversation details (standalone route)"""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.is_deleted == False
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check access via workspace
    workspace = _get_workspace_or_404(db, conversation.workspace_id, current_user)

    return _conversation_to_response(conversation)


@standalone_router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation_standalone(
    conversation_id: UUID,
    request: ConversationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update conversation details (standalone route)"""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.is_deleted == False
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    workspace = _get_workspace_or_404(db, conversation.workspace_id, current_user)

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
    db.commit()
    db.refresh(conversation)

    return _conversation_to_response(conversation)


@standalone_router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation_standalone(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Soft-delete a conversation (standalone route)"""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.is_deleted == False
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    workspace = _get_workspace_or_404(db, conversation.workspace_id, current_user)

    if not workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    conversation.is_deleted = True
    conversation.deleted_at = datetime.utcnow()
    db.commit()


@standalone_router.post("/threads", response_model=ThreadResponse, status_code=status.HTTP_201_CREATED)
async def create_thread_standalone(
    request: ThreadCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new thread (standalone route - uses conversation_id from request body)"""
    conversation = db.query(Conversation).filter(
        Conversation.id == request.conversation_id,
        Conversation.is_deleted == False
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    workspace = _get_workspace_or_404(db, conversation.workspace_id, current_user)

    if not workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    thread = Thread(
        conversation_id=request.conversation_id,
        title=request.title,
        created_by_id=current_user.id
    )
    db.add(thread)

    # Create initial message if provided
    if request.initial_message:
        message = ChatMessage(
            thread=thread,
            user_id=current_user.id,
            role=MessageRole.USER,
            content=request.initial_message
        )
        db.add(message)
        thread.message_count = 1

    # Update conversation activity
    conversation.last_activity_at = datetime.utcnow()

    db.commit()
    db.refresh(thread)

    logger.info(f"Thread created in conversation {conversation.id}")

    return _thread_to_response(thread)


@standalone_router.get("/threads/{thread_id}", response_model=ThreadDetailResponse)
async def get_thread_standalone(
    thread_id: UUID,
    include_messages: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get thread details with messages (standalone route)"""
    thread = db.query(Thread).options(
        joinedload(Thread.messages)
    ).filter(
        Thread.id == thread_id,
        Thread.is_deleted == False
    ).first()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Verify access via conversation -> workspace
    conversation = db.query(Conversation).filter(
        Conversation.id == thread.conversation_id,
        Conversation.is_deleted == False
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    workspace = _get_workspace_or_404(db, conversation.workspace_id, current_user)

    return _thread_to_detail_response(thread, include_messages)


@standalone_router.patch("/threads/{thread_id}", response_model=ThreadResponse)
async def update_thread_standalone(
    thread_id: UUID,
    request: ThreadUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update thread details (standalone route)"""
    thread = db.query(Thread).filter(
        Thread.id == thread_id,
        Thread.is_deleted == False
    ).first()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    conversation = db.query(Conversation).filter(
        Conversation.id == thread.conversation_id,
        Conversation.is_deleted == False
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    workspace = _get_workspace_or_404(db, conversation.workspace_id, current_user)

    if not workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    if request.title is not None:
        thread.title = request.title
    if request.summary is not None:
        thread.summary = request.summary
    if request.status is not None:
        thread.status = ThreadStatus(request.status.value)

    thread.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(thread)

    return _thread_to_response(thread)


@standalone_router.delete("/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread_standalone(
    thread_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Soft-delete a thread (standalone route)"""
    thread = db.query(Thread).filter(
        Thread.id == thread_id,
        Thread.is_deleted == False
    ).first()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    conversation = db.query(Conversation).filter(
        Conversation.id == thread.conversation_id,
        Conversation.is_deleted == False
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    workspace = _get_workspace_or_404(db, conversation.workspace_id, current_user)

    if not workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    thread.is_deleted = True
    thread.deleted_at = datetime.utcnow()
    db.commit()


@standalone_router.get("/threads/{thread_id}/messages", response_model=ChatMessageListResponse)
async def list_messages_standalone(
    thread_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List messages in a thread (standalone route)"""
    thread = db.query(Thread).filter(
        Thread.id == thread_id,
        Thread.is_deleted == False
    ).first()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    conversation = db.query(Conversation).filter(
        Conversation.id == thread.conversation_id,
        Conversation.is_deleted == False
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    workspace = _get_workspace_or_404(db, conversation.workspace_id, current_user)

    # Count total messages first (without joinedload for efficiency)
    total = db.query(ChatMessage).filter(
        ChatMessage.thread_id == thread_id,
        ChatMessage.is_deleted == False
    ).count()

    # Query with eager loading of citations and their documents
    offset = (page - 1) * limit
    messages = db.query(ChatMessage).options(
        joinedload(ChatMessage.citations).joinedload(Citation.document),
        joinedload(ChatMessage.attachments)
    ).filter(
        ChatMessage.thread_id == thread_id,
        ChatMessage.is_deleted == False
    ).order_by(ChatMessage.created_at.asc()).offset(offset).limit(limit).all()

    return ChatMessageListResponse(
        messages=[_message_to_response(m) for m in messages],
        total=total,
        page=page,
        limit=limit,
        has_more=(offset + len(messages)) < total
    )


@standalone_router.post("/messages", response_model=ChatMessageResponse, status_code=status.HTTP_201_CREATED)
async def create_message_standalone(
    request: ChatMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new message (standalone route - uses thread_id from request body)"""
    thread = db.query(Thread).filter(
        Thread.id == request.thread_id,
        Thread.is_deleted == False
    ).first()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    conversation = db.query(Conversation).filter(
        Conversation.id == thread.conversation_id,
        Conversation.is_deleted == False
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    workspace = _get_workspace_or_404(db, conversation.workspace_id, current_user)

    if not workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    message = ChatMessage(
        thread_id=request.thread_id,
        user_id=current_user.id if request.role.value == "user" else None,
        role=MessageRole(request.role.value),
        content=request.content
    )
    db.add(message)
    db.flush()  # Flush to get message.id for citations

    # Handle citations (for assistant messages with RAG sources)
    if request.citations:
        for cit in request.citations:
            citation = Citation(
                message_id=message.id,
                document_id=cit.document_id,  # May be None for external refs
                external_reference_id=cit.external_reference_id,
                document_title=cit.document_title,
                document_type=cit.document_type,
                chunk_index=cit.chunk_index,
                chunk_id=cit.chunk_id,
                snippet=cit.snippet,
                page_number=cit.page_number,
                score=cit.score,
                rerank_score=cit.rerank_score
            )
            db.add(citation)

    # Update thread stats
    thread.message_count = (thread.message_count or 0) + 1
    thread.last_message_at = datetime.utcnow()

    # Update conversation activity
    conversation.last_activity_at = datetime.utcnow()

    db.commit()
    
    # Re-query with eager loading to get citations with document info
    message = db.query(ChatMessage).options(
        joinedload(ChatMessage.citations).joinedload(Citation.document),
        joinedload(ChatMessage.attachments)
    ).filter(ChatMessage.id == message.id).first()

    return _message_to_response(message)


@standalone_router.get("/messages/{message_id}", response_model=ChatMessageResponse)
async def get_message_standalone(
    message_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get message details (standalone route)"""
    message = db.query(ChatMessage).filter(
        ChatMessage.id == message_id,
        ChatMessage.is_deleted == False
    ).first()

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Verify access via thread -> conversation -> workspace
    thread = db.query(Thread).filter(
        Thread.id == message.thread_id,
        Thread.is_deleted == False
    ).first()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    conversation = db.query(Conversation).filter(
        Conversation.id == thread.conversation_id,
        Conversation.is_deleted == False
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    workspace = _get_workspace_or_404(db, conversation.workspace_id, current_user)

    return _message_to_response(message)


@standalone_router.patch("/messages/{message_id}", response_model=ChatMessageResponse)
async def update_message_standalone(
    message_id: UUID,
    request: ChatMessageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update message feedback (standalone route)"""
    message = db.query(ChatMessage).filter(
        ChatMessage.id == message_id,
        ChatMessage.is_deleted == False
    ).first()

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Verify access via thread -> conversation -> workspace
    thread = db.query(Thread).filter(
        Thread.id == message.thread_id,
        Thread.is_deleted == False
    ).first()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    conversation = db.query(Conversation).filter(
        Conversation.id == thread.conversation_id,
        Conversation.is_deleted == False
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    workspace = _get_workspace_or_404(db, conversation.workspace_id, current_user)

    if request.feedback_rating is not None:
        message.feedback_rating = request.feedback_rating
    if request.feedback_text is not None:
        message.feedback_text = request.feedback_text

    message.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(message)

    return _message_to_response(message)


@standalone_router.delete("/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message_standalone(
    message_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Soft-delete a message (standalone route)"""
    message = db.query(ChatMessage).filter(
        ChatMessage.id == message_id,
        ChatMessage.is_deleted == False
    ).first()

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Verify access via thread -> conversation -> workspace
    thread = db.query(Thread).filter(
        Thread.id == message.thread_id,
        Thread.is_deleted == False
    ).first()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    conversation = db.query(Conversation).filter(
        Conversation.id == thread.conversation_id,
        Conversation.is_deleted == False
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    workspace = _get_workspace_or_404(db, conversation.workspace_id, current_user)

    if not workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    message.is_deleted = True
    message.deleted_at = datetime.utcnow()

    # Update thread message count
    thread.message_count = max((thread.message_count or 1) - 1, 0)

    db.commit()


@standalone_router.get("/conversations/{conversation_id}/threads", response_model=ThreadListResponse)
async def list_threads_standalone(
    conversation_id: UUID,
    status_filter: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List threads in a conversation (standalone route)"""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.is_deleted == False
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    workspace = _get_workspace_or_404(db, conversation.workspace_id, current_user)

    query = db.query(Thread).filter(
        Thread.conversation_id == conversation_id,
        Thread.is_deleted == False
    )

    if status_filter:
        try:
            status_enum = ThreadStatus(status_filter)
            query = query.filter(Thread.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status_filter}")

    total = query.count()
    offset = (page - 1) * limit
    threads = query.order_by(Thread.last_message_at.desc()).offset(offset).limit(limit).all()

    return ThreadListResponse(
        threads=[_thread_to_response(t) for t in threads],
        total=total,
        page=page,
        limit=limit,
        has_more=(offset + len(threads)) < total
    )


@standalone_router.post("/collections", response_model=CollectionResponse, status_code=status.HTTP_201_CREATED)
async def create_collection_standalone(
    request: CollectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new collection (standalone route - uses workspace_id from request body)"""
    workspace = _get_workspace_or_404(db, request.workspace_id, current_user)

    if not workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    collection = Collection(
        workspace_id=request.workspace_id,
        name=request.name,
        description=request.description,
        color=request.color,
        icon=request.icon
    )
    db.add(collection)

    # Add initial documents if provided
    if request.document_ids:
        for i, doc_id in enumerate(request.document_ids):
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if doc:
                collection_doc = CollectionDocument(
                    collection=collection,
                    document_id=doc_id,
                    sort_order=i
                )
                db.add(collection_doc)

    db.commit()
    db.refresh(collection)

    return _collection_to_response(collection)


@standalone_router.get("/collections/{collection_id}", response_model=CollectionDetailResponse)
async def get_collection_standalone(
    collection_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get collection details with documents (standalone route)"""
    collection = db.query(Collection).options(
        joinedload(Collection.documents)
    ).filter(
        Collection.id == collection_id,
        Collection.is_deleted == False
    ).first()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    workspace = _get_workspace_or_404(db, collection.workspace_id, current_user)

    return _collection_to_detail_response(collection)


@standalone_router.patch("/collections/{collection_id}", response_model=CollectionResponse)
async def update_collection_standalone(
    collection_id: UUID,
    request: CollectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update collection details (standalone route)"""
    collection = db.query(Collection).filter(
        Collection.id == collection_id,
        Collection.is_deleted == False
    ).first()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    workspace = _get_workspace_or_404(db, collection.workspace_id, current_user)

    if not workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    if request.name is not None:
        collection.name = request.name
    if request.description is not None:
        collection.description = request.description
    if request.color is not None:
        collection.color = request.color
    if request.icon is not None:
        collection.icon = request.icon

    collection.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(collection)

    return _collection_to_response(collection)


@standalone_router.delete("/collections/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection_standalone(
    collection_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Soft-delete a collection (standalone route)"""
    collection = db.query(Collection).filter(
        Collection.id == collection_id,
        Collection.is_deleted == False
    ).first()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    workspace = _get_workspace_or_404(db, collection.workspace_id, current_user)

    if not workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    collection.is_deleted = True
    collection.deleted_at = datetime.utcnow()
    db.commit()


@standalone_router.post("/collections/{collection_id}/documents", response_model=CollectionDetailResponse)
async def add_documents_to_collection_standalone(
    collection_id: UUID,
    request: CollectionDocumentAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add documents to a collection (standalone route)"""
    collection = db.query(Collection).options(
        joinedload(Collection.documents)
    ).filter(
        Collection.id == collection_id,
        Collection.is_deleted == False
    ).first()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    workspace = _get_workspace_or_404(db, collection.workspace_id, current_user)

    if not workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    # Get current max sort order
    max_order = db.query(func.max(CollectionDocument.sort_order)).filter(
        CollectionDocument.collection_id == collection_id
    ).scalar() or 0

    for i, doc_id in enumerate(request.document_ids):
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            continue

        existing = db.query(CollectionDocument).filter(
            CollectionDocument.collection_id == collection_id,
            CollectionDocument.document_id == doc_id,
            CollectionDocument.is_deleted == False
        ).first()

        if not existing:
            collection_doc = CollectionDocument(
                collection_id=collection_id,
                document_id=doc_id,
                sort_order=max_order + i + 1
            )
            db.add(collection_doc)

    db.commit()
    db.refresh(collection)

    return _collection_to_detail_response(collection)


@standalone_router.delete("/collections/{collection_id}/documents", response_model=CollectionDetailResponse)
async def remove_documents_from_collection_standalone(
    collection_id: UUID,
    request: CollectionDocumentRemove,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove documents from a collection (standalone route)"""
    collection = db.query(Collection).options(
        joinedload(Collection.documents)
    ).filter(
        Collection.id == collection_id,
        Collection.is_deleted == False
    ).first()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    workspace = _get_workspace_or_404(db, collection.workspace_id, current_user)

    if not workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    for doc_id in request.document_ids:
        collection_doc = db.query(CollectionDocument).filter(
            CollectionDocument.collection_id == collection_id,
            CollectionDocument.document_id == doc_id,
            CollectionDocument.is_deleted == False
        ).first()

        if collection_doc:
            collection_doc.is_deleted = True
            collection_doc.deleted_at = datetime.utcnow()

    db.commit()
    db.refresh(collection)

    return _collection_to_detail_response(collection)
