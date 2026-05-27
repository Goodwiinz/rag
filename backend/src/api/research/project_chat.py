"""
Project-Chat Integration API endpoints.

Enables linking research projects to chat threads for:
- Starting chat from project with document context
- Linking/unlinking existing threads
- Viewing project-related conversations
- Saving thread content to project notes
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from structlog import get_logger

from src.core.database import get_db
from src.models import (
    ChatMessage,
    Collection,
    CollectionDocument,
    Conversation,
    MessageRole,
    ProjectThread,
    ProjectThreadLinkType,
    Thread,
    User,
    Workspace,
)
from src.schemas.chat import ThreadCreate
from src.core.dependencies import get_current_user
from src.shared.research_schemas import (
    LinkThreadRequest,
    NoteCreate,
    NoteResponse,
    ProjectThreadListResponse,
    ProjectThreadResponse,
    SaveThreadToNoteRequest,
    StartChatFromProjectRequest,
    StartChatFromProjectResponse,
)

logger = get_logger()
router = APIRouter(prefix="/api/v1/projects", tags=["project-chat-integration"])


# =========================================================================
# Helper Functions
# =========================================================================


async def _get_project_with_auth(
    project_id: UUID,
    current_user: User,
    db: AsyncSession,
) -> Collection:
    """Get project with authorization check.

    Raises:
        HTTPException: If not found or not authorized
    """
    query = (
        select(Collection)
        .options(selectinload(Collection.documents))
        .join(Workspace, Collection.workspace_id == Workspace.id)
        .where(
            and_(
                Collection.id == project_id,
                Workspace.owner_id == current_user.id,
            )
        )
    )
    result = await db.execute(query)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied",
        )

    return project


async def _get_thread_with_auth(
    thread_id: UUID,
    current_user: User,
    db: AsyncSession,
) -> Thread:
    """Get thread with authorization check.

    Raises:
        HTTPException: If not found or not authorized
    """
    query = (
        select(Thread)
        .options(selectinload(Thread.conversation))
        .join(Conversation, Thread.conversation_id == Conversation.id)
        .join(Workspace, Conversation.workspace_id == Workspace.id)
        .where(
            and_(
                Thread.id == thread_id,
                Workspace.owner_id == current_user.id,
            )
        )
    )
    result = await db.execute(query)
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found or access denied",
        )

    return thread


async def _get_project_document_scope(
    project_id: UUID,
    db: AsyncSession,
) -> List[str]:
    """Return non-deleted document IDs linked to a project."""
    doc_query = select(CollectionDocument.document_id).where(
        and_(
            CollectionDocument.collection_id == project_id,
            CollectionDocument.is_deleted == False,
        )
    )
    doc_result = await db.execute(doc_query)
    return [str(row[0]) for row in doc_result.all()]


# =========================================================================
# Start Chat from Project
# =========================================================================


@router.post("/{project_id}/chat/start", response_model=StartChatFromProjectResponse)
async def start_chat_from_project(
    project_id: UUID,
    request: StartChatFromProjectRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Start a new chat thread from a project with document context.

    Creates a new thread (or uses existing conversation) and automatically
    links it to the project. The thread's RAG context is scoped to the
    project's documents.

    Args:
        project_id: Project ID to start chat from
        request: Chat start request with initial message
        current_user: Authenticated user
        db: Database session

    Returns:
        Thread details with document scope
    """
    try:
        # Verify project access
        project = await _get_project_with_auth(project_id, current_user, db)

        # Get project's documents for RAG scope
        document_ids = await _get_project_document_scope(project_id, db)

        if not document_ids:
            logger.warning(
                "starting_chat_from_project_with_no_documents",
                project_id=str(project_id),
            )

        # Get or create conversation
        conversation_id = request.conversation_id
        if not conversation_id:
            # Create new conversation in project's workspace
            conversation = Conversation(
                workspace_id=project.workspace_id,
                title=f"Chat: {project.name}",
                created_by_id=current_user.id,
            )
            db.add(conversation)
            await db.flush()  # Get conversation ID
            conversation_id = conversation.id
        else:
            # Verify conversation exists and user has access
            conv_query = (
                select(Conversation)
                .join(Workspace, Conversation.workspace_id == Workspace.id)
                .where(
                    and_(
                        Conversation.id == conversation_id,
                        Workspace.owner_id == current_user.id,
                    )
                )
            )
            conv_result = await db.execute(conv_query)
            conversation = conv_result.scalar_one_or_none()
            if not conversation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found or access denied",
                )
            if conversation.workspace_id != project.workspace_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Conversation and project must be in the same workspace",
                )

        # Create thread with project context
        thread = Thread(
            conversation_id=conversation_id,
            title=request.thread_title or f"Discussion: {project.name}",
            created_by_id=current_user.id,
            source_project_id=project_id,  # Link to originating project
            rag_document_scope={"document_ids": document_ids},  # Store RAG scope
        )
        db.add(thread)
        await db.flush()  # Get thread ID

        # Create project-thread link
        project_thread = ProjectThread(
            project_id=project_id,
            thread_id=thread.id,
            link_type=ProjectThreadLinkType.AUTO.value,
            linked_by_id=current_user.id,
            context_note="Auto-linked when starting chat from project",
        )
        db.add(project_thread)

        # Create initial message if provided
        if request.initial_message:
            message = ChatMessage(
                thread_id=thread.id,
                user_id=current_user.id,
                role=MessageRole.USER,
                content=request.initial_message,
            )
            db.add(message)
            thread.message_count = 1

        await db.commit()
        await db.refresh(thread)
        await db.refresh(project_thread)

        logger.info(
            "chat_started_from_project",
            project_id=str(project_id),
            thread_id=str(thread.id),
            document_count=len(document_ids),
            user_id=str(current_user.id),
        )

        return StartChatFromProjectResponse(
            thread_id=thread.id,
            conversation_id=conversation_id,
            project_thread_id=project_thread.id,
            document_scope=[UUID(doc_id) for doc_id in document_ids],
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(
            "start_chat_from_project_failed", error=str(e), project_id=str(project_id)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start chat from project: {str(e)}",
        )


# =========================================================================
# Link Existing Thread
# =========================================================================


@router.post("/{project_id}/chat/link", response_model=ProjectThreadResponse)
async def link_thread_to_project(
    project_id: UUID,
    request: LinkThreadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Link an existing thread to a project.

    Args:
        project_id: Project ID to link to
        request: Thread link request
        current_user: Authenticated user
        db: Database session

    Returns:
        Created project-thread link
    """
    try:
        # Verify project access
        project = await _get_project_with_auth(project_id, current_user, db)

        # Verify thread access
        thread = await _get_thread_with_auth(request.thread_id, current_user, db)

        # Verify thread and project are in same workspace
        if thread.conversation.workspace_id != project.workspace_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Thread and project must be in the same workspace",
            )

        # Check if link already exists
        existing_query = select(ProjectThread).where(
            and_(
                ProjectThread.project_id == project_id,
                ProjectThread.thread_id == request.thread_id,
            )
        )
        existing_result = await db.execute(existing_query)
        if existing_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Thread is already linked to this project",
            )

        # Create link
        document_ids = await _get_project_document_scope(project_id, db)
        thread.source_project_id = project_id
        thread.rag_document_scope = {"document_ids": document_ids}

        project_thread = ProjectThread(
            project_id=project_id,
            thread_id=request.thread_id,
            link_type=ProjectThreadLinkType.MANUAL.value,
            linked_by_id=current_user.id,
            context_note=request.context_note,
        )
        db.add(project_thread)
        await db.commit()
        await db.refresh(project_thread)

        logger.info(
            "thread_linked_to_project",
            project_id=str(project_id),
            thread_id=str(request.thread_id),
            user_id=str(current_user.id),
        )

        return ProjectThreadResponse(
            id=project_thread.id,
            project_id=project_thread.project_id,
            thread_id=project_thread.thread_id,
            thread_title=thread.title or thread.generate_title(),
            conversation_id=thread.conversation_id,
            link_type=project_thread.link_type,
            linked_at=project_thread.linked_at,
            linked_by_id=project_thread.linked_by_id,
            context_note=project_thread.context_note,
            message_count=thread.message_count,
            last_message_at=thread.last_message_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("link_thread_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to link thread: {str(e)}",
        )


# =========================================================================
# List Project Threads
# =========================================================================


@router.get("/{project_id}/chat/threads", response_model=ProjectThreadListResponse)
async def list_project_threads(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all threads linked to a project.

    Args:
        project_id: Project ID
        current_user: Authenticated user
        db: Database session

    Returns:
        List of linked threads with metadata
    """
    try:
        # Verify project access
        await _get_project_with_auth(project_id, current_user, db)

        # Get linked threads with thread details
        query = (
            select(ProjectThread)
            .options(selectinload(ProjectThread.thread))
            .where(ProjectThread.project_id == project_id)
            .order_by(ProjectThread.linked_at.desc())
        )
        result = await db.execute(query)
        project_threads = result.scalars().all()

        threads_response = []
        for pt in project_threads:
            if pt.thread and not pt.thread.is_deleted:
                threads_response.append(
                    ProjectThreadResponse(
                        id=pt.id,
                        project_id=pt.project_id,
                        thread_id=pt.thread_id,
                        thread_title=pt.thread.title or pt.thread.generate_title(),
                        conversation_id=pt.thread.conversation_id,
                        link_type=pt.link_type,
                        linked_at=pt.linked_at,
                        linked_by_id=pt.linked_by_id,
                        context_note=pt.context_note,
                        message_count=pt.thread.message_count,
                        last_message_at=pt.thread.last_message_at,
                    )
                )

        return ProjectThreadListResponse(
            threads=threads_response,
            total=len(threads_response),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("list_project_threads_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list threads: {str(e)}",
        )


# =========================================================================
# Unlink Thread
# =========================================================================


@router.delete(
    "/{project_id}/chat/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def unlink_thread_from_project(
    project_id: UUID,
    thread_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Unlink a thread from a project.

    Args:
        project_id: Project ID
        thread_id: Thread ID to unlink
        current_user: Authenticated user
        db: Database session
    """
    try:
        # Verify project access
        await _get_project_with_auth(project_id, current_user, db)

        # Find and delete the link
        query = select(ProjectThread).where(
            and_(
                ProjectThread.project_id == project_id,
                ProjectThread.thread_id == thread_id,
            )
        )
        result = await db.execute(query)
        project_thread = result.scalar_one_or_none()

        if not project_thread:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Thread link not found",
            )

        thread = await _get_thread_with_auth(thread_id, current_user, db)
        await db.delete(project_thread)

        if getattr(thread, "source_project_id", None) == project_id:
            remaining_query = (
                select(ProjectThread)
                .where(
                    and_(
                        ProjectThread.thread_id == thread_id,
                        ProjectThread.project_id != project_id,
                    )
                )
                .order_by(ProjectThread.linked_at.desc())
            )
            remaining_result = await db.execute(remaining_query)
            remaining_link = remaining_result.scalars().first()
            if remaining_link:
                document_ids = await _get_project_document_scope(
                    remaining_link.project_id, db
                )
                thread.source_project_id = remaining_link.project_id
                thread.rag_document_scope = {"document_ids": document_ids}
            else:
                thread.source_project_id = None
                thread.rag_document_scope = None

        await db.commit()

        logger.info(
            "thread_unlinked_from_project",
            project_id=str(project_id),
            thread_id=str(thread_id),
            user_id=str(current_user.id),
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("unlink_thread_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unlink thread: {str(e)}",
        )


# =========================================================================
# Save Thread to Note
# =========================================================================


@router.post("/{project_id}/chat/save-to-note", response_model=NoteResponse)
async def save_thread_to_note(
    project_id: UUID,
    request: SaveThreadToNoteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Save thread content to a project note.

    Args:
        project_id: Project ID
        request: Save to note request
        current_user: Authenticated user
        db: Database session

    Returns:
        Created note
    """
    try:
        # Verify project access
        await _get_project_with_auth(project_id, current_user, db)

        # Verify thread access and get messages
        thread = await _get_thread_with_auth(request.thread_id, current_user, db)

        # Get messages with eager-loaded citations to avoid lazy-load in async context
        message_query = (
            select(ChatMessage)
            .options(selectinload(ChatMessage.citations))  # Eager load citations
            .where(
                and_(
                    ChatMessage.thread_id == request.thread_id,
                    ChatMessage.is_deleted == False,
                )
            )
            .order_by(ChatMessage.created_at.asc())
        )
        message_result = await db.execute(message_query)
        messages = message_result.scalars().all()

        # Build note content from messages
        # Use thread title directly (avoid generate_title() which causes lazy-load issues)
        thread_title = thread.title or f"Thread {str(thread.id)[:8]}"
        content_parts = [f"# {thread_title}\n"]

        # Format date safely
        date_str = (
            thread.last_message_at.strftime("%Y-%m-%d")
            if thread.last_message_at
            else "Unknown date"
        )
        content_parts.append(f"*Saved from chat thread on {date_str}*\n\n")

        for msg in messages:
            role_label = msg.role.value.title()
            content_parts.append(f"## {role_label}\n\n{msg.content}\n\n")

            # Add citations if requested
            if request.include_citations and msg.citations:
                content_parts.append("**Citations:**\n")
                for citation in msg.citations:
                    if citation.document_title:
                        content_parts.append(f"- {citation.document_title}\n")
                content_parts.append("\n")

        note_content = "".join(content_parts)

        # Create note using existing notes API
        from src.models import ProjectNote

        note = ProjectNote(
            project_id=project_id,
            user_id=current_user.id,
            title=request.note_title,
            content=note_content,
            linked_document_ids=[],
            tags=["chat-thread"],
            is_pinned=False,
        )

        db.add(note)
        await db.commit()
        await db.refresh(note)

        logger.info(
            "thread_saved_to_note",
            project_id=str(project_id),
            thread_id=str(request.thread_id),
            note_id=str(note.id),
            user_id=str(current_user.id),
        )

        # Import here to avoid circular dependency
        from src.api.research.projects import _to_note_response

        return _to_note_response(note)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("save_thread_to_note_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save thread to note: {str(e)}",
        )
