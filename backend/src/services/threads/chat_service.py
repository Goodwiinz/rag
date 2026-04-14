"""
Chat Service for Terminal Observatory thread-centric chat persistence.

Provides CRUD operations for workspaces, conversations, threads, and messages.
"""

import logging
import uuid as uuid_mod
from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models import (
    ChatMessage,
    Citation,
    Collection,
    CollectionDocument,
    Conversation,
    MessageAttachment,
    MessageRole,
    Thread,
    ThreadStatus,
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceRole,
)
from src.schemas.chat import (
    ChatMessageCreate,
    ChatMessageUpdate,
    CollectionCreate,
    CollectionUpdate,
    ConversationCreate,
    ConversationUpdate,
    ThreadCreate,
    ThreadUpdate,
    WorkspaceCreate,
    WorkspaceUpdate,
)

logger = logging.getLogger(__name__)


class ChatService:
    """
    Service layer for chat persistence operations.

    Handles all CRUD operations for the thread-centric chat schema:
    - Workspaces (project containers)
    - Conversations (topic containers)
    - Threads (inquiry lines)
    - Messages (chat entries)
    - Collections (document groupings)
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # Workspace Operations
    # =========================================================================

    async def create_workspace(
        self, data: WorkspaceCreate, owner_id: UUID
    ) -> Workspace:
        """Create a new workspace"""
        workspace = Workspace(
            name=data.name,
            description=data.description,
            is_public=data.is_public,
            owner_id=owner_id,
            organization_id=data.organization_id,
        )
        self.db.add(workspace)

        # Add owner as a member with OWNER role
        member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=owner_id,
            role=WorkspaceRole.OWNER,
            joined_at=datetime.utcnow(),
        )
        self.db.add(member)

        await self.db.commit()
        await self.db.refresh(workspace)

        logger.info(f"Created workspace: {workspace.id} - {workspace.name}")
        return workspace

    async def get_workspace(
        self, workspace_id: UUID, user_id: UUID
    ) -> Optional[Workspace]:
        """Get workspace by ID if user has access"""
        stmt = (
            select(Workspace)
            .options(
                selectinload(Workspace.members), selectinload(Workspace.conversations)
            )
            .where(Workspace.id == workspace_id, Workspace.is_deleted == False)
        )
        result = await self.db.execute(stmt)
        workspace = result.scalars().first()

        if not workspace:
            return None

        # Check access
        if not self._user_can_access_workspace(workspace, user_id):
            return None

        return workspace

    async def list_workspaces(
        self,
        user_id: UUID,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Workspace], int]:
        """List workspaces accessible to user"""
        base_conditions = [
            WorkspaceMember.user_id == user_id,
            Workspace.is_deleted == False,
        ]

        if not include_archived:
            base_conditions.append(Workspace.is_archived == False)

        # Count total
        count_stmt = (
            select(func.count(Workspace.id))
            .join(WorkspaceMember)
            .where(*base_conditions)
        )
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        # Fetch workspaces
        stmt = (
            select(Workspace)
            .join(WorkspaceMember)
            .where(*base_conditions)
            .order_by(desc(Workspace.updated_at))
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        workspaces = result.scalars().all()

        return workspaces, total

    async def update_workspace(
        self, workspace_id: UUID, data: WorkspaceUpdate, user_id: UUID
    ) -> Optional[Workspace]:
        """Update workspace"""
        workspace = await self.get_workspace(workspace_id, user_id)
        if not workspace:
            return None

        # Check permission
        if not workspace.can_user_admin(str(user_id)):
            return None

        if data.name is not None:
            workspace.name = data.name
        if data.description is not None:
            workspace.description = data.description
        if data.is_public is not None:
            workspace.is_public = data.is_public
        if data.is_archived is not None:
            workspace.is_archived = data.is_archived

        workspace.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(workspace)

        return workspace

    async def delete_workspace(self, workspace_id: UUID, user_id: UUID) -> bool:
        """Soft delete workspace"""
        workspace = await self.get_workspace(workspace_id, user_id)
        if not workspace:
            return False

        # Only owner can delete
        if str(workspace.owner_id) != str(user_id):
            return False

        workspace.is_deleted = True
        workspace.updated_at = datetime.utcnow()
        await self.db.commit()

        logger.info(f"Deleted workspace: {workspace_id}")
        return True

    def _user_can_access_workspace(self, workspace: Workspace, user_id: UUID) -> bool:
        """Check if user can access workspace"""
        if workspace.is_public:
            return True
        if str(workspace.owner_id) == str(user_id):
            return True
        return workspace.is_member(str(user_id))

    # =========================================================================
    # Conversation Operations
    # =========================================================================

    async def create_conversation(
        self, data: ConversationCreate, user_id: UUID
    ) -> Optional[Conversation]:
        """Create a new conversation in a workspace"""
        # Verify workspace access
        workspace = await self.get_workspace(data.workspace_id, user_id)
        if not workspace:
            return None

        # Check edit permission
        if not workspace.can_user_edit(str(user_id)):
            return None

        conversation = Conversation(
            workspace_id=data.workspace_id,
            title=data.title,
            description=data.description,
            created_by_id=user_id,
            last_activity_at=datetime.utcnow(),
        )
        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(conversation)

        logger.info(f"Created conversation: {conversation.id} - {conversation.title}")
        return conversation

    async def get_conversation(
        self, conversation_id: UUID, user_id: UUID
    ) -> Optional[Conversation]:
        """Get conversation by ID"""
        stmt = (
            select(Conversation)
            .options(
                selectinload(Conversation.threads),
                selectinload(Conversation.workspace).selectinload(Workspace.members),
            )
            .where(Conversation.id == conversation_id, Conversation.is_deleted == False)
        )
        result = await self.db.execute(stmt)
        conversation = result.scalars().first()

        if not conversation:
            return None

        # Check workspace access
        if not self._user_can_access_workspace(conversation.workspace, user_id):
            return None

        return conversation

    async def list_conversations(
        self,
        workspace_id: UUID,
        user_id: UUID,
        include_archived: bool = False,
        search_query: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Conversation], int]:
        """List conversations in a workspace"""
        # Verify workspace access
        workspace = await self.get_workspace(workspace_id, user_id)
        if not workspace:
            return [], 0

        base_conditions = [
            Conversation.workspace_id == workspace_id,
            Conversation.is_deleted == False,
        ]

        if not include_archived:
            base_conditions.append(Conversation.is_archived == False)

        if search_query:
            search_pattern = f"%{search_query}%"
            base_conditions.append(
                or_(
                    Conversation.title.ilike(search_pattern),
                    Conversation.description.ilike(search_pattern),
                )
            )

        # Count total
        count_stmt = select(func.count(Conversation.id)).where(*base_conditions)
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        # Fetch conversations
        stmt = (
            select(Conversation)
            .where(*base_conditions)
            .order_by(desc(Conversation.is_pinned), desc(Conversation.last_activity_at))
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        conversations = result.scalars().all()

        return conversations, total

    async def update_conversation(
        self, conversation_id: UUID, data: ConversationUpdate, user_id: UUID
    ) -> Optional[Conversation]:
        """Update conversation"""
        conversation = await self.get_conversation(conversation_id, user_id)
        if not conversation:
            return None

        # Check permission
        if not conversation.workspace.can_user_edit(str(user_id)):
            return None

        if data.title is not None:
            conversation.title = data.title
        if data.description is not None:
            conversation.description = data.description
        if data.is_archived is not None:
            conversation.is_archived = data.is_archived
        if data.is_pinned is not None:
            conversation.is_pinned = data.is_pinned

        conversation.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(conversation)

        return conversation

    async def delete_conversation(self, conversation_id: UUID, user_id: UUID) -> bool:
        """Soft delete conversation"""
        conversation = await self.get_conversation(conversation_id, user_id)
        if not conversation:
            return False

        # Check permission
        if not conversation.workspace.can_user_admin(str(user_id)):
            return False

        conversation.is_deleted = True
        conversation.updated_at = datetime.utcnow()
        await self.db.commit()

        logger.info(f"Deleted conversation: {conversation_id}")
        return True

    # =========================================================================
    # Thread Operations
    # =========================================================================

    async def create_thread(
        self, data: ThreadCreate, user_id: UUID
    ) -> Optional[Thread]:
        """Create a new thread in a conversation"""
        # Verify conversation access
        conversation = await self.get_conversation(data.conversation_id, user_id)
        if not conversation:
            return None

        # Check edit permission
        if not conversation.workspace.can_user_edit(str(user_id)):
            return None

        thread_id = uuid_mod.uuid4()
        thread = Thread(
            id=thread_id,
            conversation_id=data.conversation_id,
            title=data.title,
            status=ThreadStatus.ACTIVE,
            created_by_id=user_id,
            last_message_at=datetime.utcnow(),
            message_count=0,
            token_count=0,
        )
        self.db.add(thread)

        # Create initial message if provided
        if data.initial_message:
            initial_msg = ChatMessage.create_user_message(
                thread_id=thread_id, user_id=str(user_id), content=data.initial_message
            )
            self.db.add(initial_msg)
            thread.message_count = 1

        # Update conversation activity
        conversation.update_activity()

        await self.db.commit()
        await self.db.refresh(thread)

        logger.info(f"Created thread: {thread.id}")
        return thread

    async def get_thread(
        self, thread_id: UUID, user_id: UUID, include_messages: bool = False
    ) -> Optional[Thread]:
        """Get thread by ID"""
        options = [
            selectinload(Thread.conversation)
            .selectinload(Conversation.workspace)
            .selectinload(Workspace.members)
        ]

        if include_messages:
            options.extend(
                [
                    selectinload(Thread.messages)
                    .selectinload(ChatMessage.citations)
                    .selectinload(Citation.document),
                    selectinload(Thread.messages).selectinload(ChatMessage.attachments).selectinload(MessageAttachment.document),
                ]
            )

        stmt = (
            select(Thread)
            .options(*options)
            .where(Thread.id == thread_id, Thread.is_deleted == False)
        )
        result = await self.db.execute(stmt)
        thread = result.scalars().first()

        if not thread:
            return None

        # Check workspace access
        if not self._user_can_access_workspace(thread.conversation.workspace, user_id):
            return None

        return thread

    async def list_threads(
        self,
        conversation_id: UUID,
        user_id: UUID,
        status_filter: Optional[ThreadStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Thread], int]:
        """List threads in a conversation"""
        # Verify conversation access
        conversation = await self.get_conversation(conversation_id, user_id)
        if not conversation:
            return [], 0

        base_conditions = [
            Thread.conversation_id == conversation_id,
            Thread.is_deleted == False,
        ]

        if status_filter:
            base_conditions.append(Thread.status == status_filter)

        # Count total
        count_stmt = select(func.count(Thread.id)).where(*base_conditions)
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        # Fetch threads
        stmt = (
            select(Thread)
            .where(*base_conditions)
            .order_by(desc(Thread.last_message_at))
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        threads = result.scalars().all()

        return threads, total

    async def update_thread(
        self, thread_id: UUID, data: ThreadUpdate, user_id: UUID
    ) -> Optional[Thread]:
        """Update thread"""
        thread = await self.get_thread(thread_id, user_id)
        if not thread:
            return None

        # Check permission
        if not thread.conversation.workspace.can_user_edit(str(user_id)):
            return None

        if data.title is not None:
            thread.title = data.title
        if data.summary is not None:
            thread.summary = data.summary

        # Track if status is changing to resolved
        status_changing_to_resolved = (
            data.status is not None
            and data.status == ThreadStatus.RESOLVED
            and thread.status != ThreadStatus.RESOLVED
        )

        if data.status is not None:
            thread.status = data.status

        thread.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(thread)

        # Trigger final summary on resolution
        if status_changing_to_resolved:
            try:
                from src.tasks.summarize_thread_task import (
                    summarize_thread_on_resolve_task,
                )

                summarize_thread_on_resolve_task.delay(str(thread_id))
            except Exception as e:
                logger.warning(
                    f"Failed to queue resolution summary for thread {thread_id}: {e}"
                )

        return thread

    async def delete_thread(self, thread_id: UUID, user_id: UUID) -> bool:
        """Soft delete thread"""
        thread = await self.get_thread(thread_id, user_id)
        if not thread:
            return False

        # Check permission
        if not thread.conversation.workspace.can_user_edit(str(user_id)):
            return False

        thread.is_deleted = True
        thread.updated_at = datetime.utcnow()
        await self.db.commit()

        logger.info(f"Deleted thread: {thread_id}")
        return True

    # ========================================================================
    # Bulk Thread Operations
    # ========================================================================

    async def bulk_update_threads(
        self,
        thread_ids: List[UUID],
        data: "ThreadUpdate",
        user_id: UUID,
        atomic: bool = False,
    ) -> List[Tuple[UUID, bool, Optional[str], Optional["Thread"]]]:
        """Bulk update multiple threads with same data.

        Args:
            thread_ids: List of thread UUIDs to update
            data: ThreadUpdate data to apply
            user_id: User performing the operation
            atomic: If True, all succeed or all fail. If False, best-effort.

        Returns:
            List of (thread_id, success, error_msg, thread) tuples.
        """
        results = []

        if atomic:
            # Atomic mode: all succeed or all fail
            try:
                # Start a savepoint for atomic operation
                async with self.db.begin_nested():
                    updated_threads = []

                    for thread_id in thread_ids:
                        thread = await self.get_thread(thread_id, user_id)
                        if not thread:
                            raise ValueError(f"Thread {thread_id} not found")

                        if not thread.conversation.workspace.can_user_edit(
                            str(user_id)
                        ):
                            raise PermissionError(
                                f"No permission to edit thread {thread_id}"
                            )

                        # Apply updates without committing
                        if data.title is not None:
                            thread.title = data.title
                        if data.summary is not None:
                            thread.summary = data.summary

                        status_changing_to_resolved = (
                            data.status is not None
                            and data.status == ThreadStatus.RESOLVED
                            and thread.status != ThreadStatus.RESOLVED
                        )

                        if data.status is not None:
                            thread.status = data.status

                        thread.updated_at = datetime.utcnow()
                        updated_threads.append(
                            (thread_id, thread, status_changing_to_resolved)
                        )

                # Commit after savepoint context exits
                await self.db.commit()

                # Build results and trigger any post-update tasks
                for thread_id, thread, status_changing_to_resolved in updated_threads:
                    await self.db.refresh(thread)
                    results.append((thread_id, True, None, thread))

                    if status_changing_to_resolved:
                        try:
                            from src.tasks.summarize_thread_task import (
                                summarize_thread_on_resolve_task,
                            )

                            summarize_thread_on_resolve_task.delay(str(thread_id))
                        except Exception as e:
                            logger.warning(
                                f"Failed to queue resolution summary for thread {thread_id}: {e}"
                            )

            except Exception as e:
                # Rollback on any error
                await self.db.rollback()
                logger.error(f"Atomic bulk update failed: {e}")
                # Return all as failed
                for thread_id in thread_ids:
                    results.append(
                        (thread_id, False, f"Atomic operation failed: {str(e)}", None)
                    )
        else:
            # Best-effort mode: continue on errors
            for thread_id in thread_ids:
                try:
                    thread = await self.update_thread(thread_id, data, user_id)
                    if thread:
                        results.append((thread_id, True, None, thread))
                    else:
                        results.append(
                            (
                                thread_id,
                                False,
                                "Thread not found or insufficient permissions",
                                None,
                            )
                        )
                except Exception as e:
                    logger.error(f"Error updating thread {thread_id}: {e}")
                    results.append((thread_id, False, str(e), None))

        return results

    async def bulk_delete_threads(
        self, thread_ids: List[UUID], user_id: UUID, atomic: bool = False
    ) -> List[Tuple[UUID, bool, Optional[str]]]:
        """Bulk soft delete multiple threads.

        Args:
            thread_ids: List of thread UUIDs to delete
            user_id: User performing the operation
            atomic: If True, all succeed or all fail. If False, best-effort.

        Returns:
            List of (thread_id, success, error_msg) tuples.
        """
        results = []

        if atomic:
            # Atomic mode: all succeed or all fail
            try:
                # Start a savepoint for atomic operation
                async with self.db.begin_nested():
                    deleted_ids = []

                    for thread_id in thread_ids:
                        thread = await self.get_thread(thread_id, user_id)
                        if not thread:
                            raise ValueError(f"Thread {thread_id} not found")

                        if not thread.conversation.workspace.can_user_edit(
                            str(user_id)
                        ):
                            raise PermissionError(
                                f"No permission to delete thread {thread_id}"
                            )

                        # Apply soft delete without committing
                        thread.is_deleted = True
                        thread.updated_at = datetime.utcnow()
                        deleted_ids.append(thread_id)

                # Commit after savepoint context exits
                await self.db.commit()

                # Build results
                for thread_id in deleted_ids:
                    results.append((thread_id, True, None))
                    logger.info(f"Deleted thread: {thread_id}")

            except Exception as e:
                # Rollback on any error
                await self.db.rollback()
                logger.error(f"Atomic bulk delete failed: {e}")
                # Return all as failed
                for thread_id in thread_ids:
                    results.append(
                        (thread_id, False, f"Atomic operation failed: {str(e)}")
                    )
        else:
            # Best-effort mode: continue on errors
            for thread_id in thread_ids:
                try:
                    success = await self.delete_thread(thread_id, user_id)
                    if success:
                        results.append((thread_id, True, None))
                    else:
                        results.append(
                            (
                                thread_id,
                                False,
                                "Thread not found or insufficient permissions",
                            )
                        )
                except Exception as e:
                    logger.error(f"Error deleting thread {thread_id}: {e}")
                    results.append((thread_id, False, str(e)))

        return results

    async def bulk_summarize_threads(
        self, thread_ids: List[UUID], user_id: UUID
    ) -> List[Tuple[UUID, bool, Optional[str], Optional["Thread"]]]:
        """Bulk trigger AI summarization for multiple threads.

        Args:
            thread_ids: List of thread UUIDs to summarize
            user_id: User performing the operation

        Returns:
            List of (thread_id, success, error_msg, thread) tuples.
        """
        results = []

        for thread_id in thread_ids:
            try:
                thread = await self.get_thread(thread_id, user_id)
                if not thread:
                    results.append(
                        (
                            thread_id,
                            False,
                            "Thread not found or insufficient permissions",
                            None,
                        )
                    )
                    continue

                # Trigger async summarization task
                # We use force=True to ensure a fresh summary is generated for manual bulk requests
                try:
                    from src.tasks.summarize_thread_task import summarize_thread_task

                    summarize_thread_task.delay(str(thread_id), force=True)
                    results.append((thread_id, True, None, thread))
                except Exception as e:
                    logger.error(
                        f"Failed to queue summarization for thread {thread_id}: {e}"
                    )
                    results.append(
                        (thread_id, False, f"Failed to queue task: {str(e)}", thread)
                    )

            except Exception as e:
                logger.error(f"Error in bulk summarize for thread {thread_id}: {e}")
                results.append((thread_id, False, str(e), None))

        return results

    # =========================================================================
    # Message Operations
    # =========================================================================

    async def create_message(
        self, data: ChatMessageCreate, user_id: UUID
    ) -> Optional[ChatMessage]:
        """Create a new message in a thread"""
        # Verify thread access
        thread = await self.get_thread(data.thread_id, user_id)
        if not thread:
            return None

        # Check edit permission
        if not thread.conversation.workspace.can_user_edit(str(user_id)):
            return None

        # Count tokens for the message using fast estimation to avoid blocking
        # on large messages (tiktoken encoding can be slow for long content)
        from src.utils.token_counter import count_message_tokens

        message_token_count = count_message_tokens(
            data.content, data.role.value, estimate_only=True
        )

        message = ChatMessage(
            thread_id=data.thread_id,
            user_id=user_id if data.role == MessageRole.USER else None,
            role=data.role,
            content=data.content,
            token_count=message_token_count,
        )
        self.db.add(message)
        await self.db.flush()  # Flush to get message.id for citations/attachments

        # Handle attachments
        if data.attachment_ids:
            for doc_id in data.attachment_ids:
                attachment = MessageAttachment(
                    message_id=message.id, document_id=doc_id
                )
                self.db.add(attachment)

        # Handle citations (for assistant messages with RAG sources)
        if data.citations:
            for cit in data.citations:
                citation = Citation(
                    message_id=message.id,
                    document_id=cit.document_id,
                    external_reference_id=cit.external_reference_id,
                    chunk_index=cit.chunk_index,
                    chunk_id=cit.chunk_id,
                    snippet=cit.snippet,
                    page_number=cit.page_number,
                    score=cit.score,
                    rerank_score=cit.rerank_score,
                    document_title=cit.document_title,
                    document_type=cit.document_type,
                )
                self.db.add(citation)

        # Update thread stats
        thread.message_count += 1
        thread.token_count += message_token_count
        thread.last_message_at = datetime.utcnow()

        # Update conversation activity
        thread.conversation.update_activity()

        await self.db.commit()
        await self.db.refresh(message)

        return message

    async def create_assistant_message(
        self,
        thread_id: UUID,
        content: str,
        model_name: Optional[str] = None,
        token_count: int = 0,
        latency_ms: Optional[int] = None,
        citations: Optional[List[dict]] = None,
    ) -> Optional[ChatMessage]:
        """Create an assistant message with optional citations"""
        message = ChatMessage.create_assistant_message(
            thread_id=str(thread_id),
            content=content,
            model_name=model_name,
            token_count=token_count,
            latency_ms=latency_ms,
        )
        self.db.add(message)
        await self.db.flush()  # Flush to get message.id for citations

        # Add citations if provided
        if citations:
            for cit in citations:
                # Validate document_id is a valid UUID, otherwise set to None
                doc_id = cit.get("document_id")
                if doc_id:
                    try:
                        import uuid as _uuid
                        _uuid.UUID(str(doc_id))
                    except (ValueError, AttributeError):
                        logger.warning(f"Invalid document_id '{doc_id}', setting to None")
                        doc_id = None

                try:
                    citation = Citation(
                        message_id=message.id,
                        document_id=doc_id,
                        external_reference_id=cit.get("external_reference_id"),
                        chunk_index=cit.get("chunk_index"),
                        chunk_id=cit.get("chunk_id"),
                        snippet=cit.get("snippet"),
                        page_number=cit.get("page_number"),
                        score=cit.get("score"),
                        rerank_score=cit.get("rerank_score"),
                        document_title=cit.get("document_title"),
                        document_type=cit.get("document_type"),
                    )
                    self.db.add(citation)
                except Exception as cit_exc:
                    logger.warning(f"Failed to create citation: {cit_exc}")

        # Update thread stats (eagerly load conversation to avoid lazy-load
        # MissingGreenlet errors in async context)
        stmt = (
            select(Thread)
            .options(selectinload(Thread.conversation))
            .where(Thread.id == thread_id)
        )
        result = await self.db.execute(stmt)
        thread = result.scalars().first()
        if thread:
            thread.message_count += 1
            thread.token_count += token_count
            thread.last_message_at = datetime.utcnow()
            thread.conversation.update_activity()

        await self.db.commit()
        await self.db.refresh(message)

        # Trigger async summarization if thread has enough messages
        if thread and thread.message_count >= 3:
            try:
                from src.tasks.summarize_thread_task import summarize_thread_task

                summarize_thread_task.delay(str(thread_id))
            except Exception as e:
                # Don't fail message creation if summarization queue fails
                logger.warning(
                    f"Failed to queue summarization for thread {thread_id}: {e}"
                )

        return message

    async def get_message(
        self, message_id: UUID, user_id: UUID
    ) -> Optional[ChatMessage]:
        """Get message by ID"""
        stmt = (
            select(ChatMessage)
            .options(
                selectinload(ChatMessage.citations).selectinload(Citation.document),
                selectinload(ChatMessage.attachments).selectinload(MessageAttachment.document),
                selectinload(ChatMessage.thread)
                .selectinload(Thread.conversation)
                .selectinload(Conversation.workspace)
                .selectinload(Workspace.members),
            )
            .where(ChatMessage.id == message_id, ChatMessage.is_deleted == False)
        )
        result = await self.db.execute(stmt)
        message = result.scalars().first()

        if not message:
            return None

        # Check workspace access
        if not self._user_can_access_workspace(
            message.thread.conversation.workspace, user_id
        ):
            return None

        return message

    async def list_messages(
        self,
        thread_id: UUID,
        user_id: UUID,
        limit: int = 100,
        offset: int = 0,
        before_id: Optional[UUID] = None,
    ) -> Tuple[List[ChatMessage], int]:
        """List messages in a thread"""
        # Verify thread access
        thread = await self.get_thread(thread_id, user_id)
        if not thread:
            return [], 0

        base_conditions = [
            ChatMessage.thread_id == thread_id,
            ChatMessage.is_deleted == False,
        ]

        if before_id:
            # Get messages before a specific message (for pagination)
            before_stmt = select(ChatMessage).where(ChatMessage.id == before_id)
            before_result = await self.db.execute(before_stmt)
            before_msg = before_result.scalars().first()
            if before_msg:
                base_conditions.append(ChatMessage.created_at < before_msg.created_at)

        # Count total
        count_stmt = select(func.count(ChatMessage.id)).where(*base_conditions)
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        # Fetch messages
        stmt = (
            select(ChatMessage)
            .options(
                selectinload(ChatMessage.citations).selectinload(Citation.document),
                selectinload(ChatMessage.attachments).selectinload(MessageAttachment.document),
            )
            .where(*base_conditions)
            .order_by(ChatMessage.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        messages = result.scalars().all()

        return messages, total

    async def update_message_feedback(
        self, message_id: UUID, data: ChatMessageUpdate, user_id: UUID
    ) -> Optional[ChatMessage]:
        """Update message feedback"""
        message = await self.get_message(message_id, user_id)
        if not message:
            return None

        if data.feedback_rating is not None:
            message.feedback_rating = data.feedback_rating
        if data.feedback_text is not None:
            message.feedback_text = data.feedback_text

        message.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(message)

        return message

    async def delete_message(self, message_id: UUID, user_id: UUID) -> bool:
        """Soft delete message"""
        message = await self.get_message(message_id, user_id)
        if not message:
            return False

        # Only message author or admin can delete
        if str(message.user_id) != str(user_id):
            if not message.thread.conversation.workspace.can_user_admin(str(user_id)):
                return False

        message.is_deleted = True
        message.updated_at = datetime.utcnow()

        # Update thread count
        message.thread.message_count = max(0, message.thread.message_count - 1)

        await self.db.commit()

        logger.info(f"Deleted message: {message_id}")
        return True

    # =========================================================================
    # Collection Operations
    # =========================================================================

    async def create_collection(
        self, data: CollectionCreate, user_id: UUID
    ) -> Optional[Collection]:
        """Create a new collection in a workspace"""
        # Verify workspace access
        workspace = await self.get_workspace(data.workspace_id, user_id)
        if not workspace:
            return None

        # Check edit permission
        if not workspace.can_user_edit(str(user_id)):
            return None

        collection = Collection(
            workspace_id=data.workspace_id,
            name=data.name,
            description=data.description,
            color=data.color,
            icon=data.icon,
        )
        self.db.add(collection)

        # Add initial documents if provided
        if data.document_ids:
            for idx, doc_id in enumerate(data.document_ids):
                coll_doc = CollectionDocument(
                    collection_id=collection.id, document_id=doc_id, sort_order=idx
                )
                self.db.add(coll_doc)
            # Note: document_count is computed automatically from documents relationship

        await self.db.commit()
        await self.db.refresh(collection)

        logger.info(f"Created collection: {collection.id} - {collection.name}")
        return collection

    async def get_collection(
        self, collection_id: UUID, user_id: UUID
    ) -> Optional[Collection]:
        """Get collection by ID"""
        stmt = (
            select(Collection)
            .options(
                selectinload(Collection.workspace).selectinload(Workspace.members),
                selectinload(Collection.documents),
            )
            .where(Collection.id == collection_id, Collection.is_deleted == False)
        )
        result = await self.db.execute(stmt)
        collection = result.scalars().first()

        if not collection:
            return None

        # Check workspace access
        if not self._user_can_access_workspace(collection.workspace, user_id):
            return None

        return collection

    async def list_collections(
        self, workspace_id: UUID, user_id: UUID, limit: int = 50, offset: int = 0
    ) -> Tuple[List[Collection], int]:
        """List collections in a workspace"""
        # Verify workspace access
        workspace = await self.get_workspace(workspace_id, user_id)
        if not workspace:
            return [], 0

        base_conditions = [
            Collection.workspace_id == workspace_id,
            Collection.is_deleted == False,
        ]

        # Count total
        count_stmt = select(func.count(Collection.id)).where(*base_conditions)
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        # Fetch collections
        stmt = (
            select(Collection)
            .where(*base_conditions)
            .order_by(Collection.name)
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        collections = result.scalars().all()

        return collections, total

    async def add_documents_to_collection(
        self, collection_id: UUID, document_ids: List[UUID], user_id: UUID
    ) -> Optional[Collection]:
        """Add documents to a collection"""
        collection = await self.get_collection(collection_id, user_id)
        if not collection:
            return None

        # Check permission
        if not collection.workspace.can_user_edit(str(user_id)):
            return None

        # Get current max position
        max_pos_stmt = select(func.max(CollectionDocument.sort_order)).where(
            CollectionDocument.collection_id == collection_id
        )
        max_pos_result = await self.db.execute(max_pos_stmt)
        max_pos = max_pos_result.scalar() or -1

        for doc_id in document_ids:
            # Check if already in collection
            existing_stmt = select(CollectionDocument).where(
                CollectionDocument.collection_id == collection_id,
                CollectionDocument.document_id == doc_id,
            )
            existing_result = await self.db.execute(existing_stmt)
            existing = existing_result.scalars().first()

            if not existing:
                max_pos += 1
                coll_doc = CollectionDocument(
                    collection_id=collection_id, document_id=doc_id, sort_order=max_pos
                )
                self.db.add(coll_doc)
                # Note: document_count is computed automatically from documents relationship

        collection.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(collection)

        return collection

    async def remove_documents_from_collection(
        self, collection_id: UUID, document_ids: List[UUID], user_id: UUID
    ) -> Optional[Collection]:
        """Remove documents from a collection"""
        collection = await self.get_collection(collection_id, user_id)
        if not collection:
            return None

        # Check permission
        if not collection.workspace.can_user_edit(str(user_id)):
            return None

        from sqlalchemy import delete

        removed = 0
        for doc_id in document_ids:
            delete_stmt = delete(CollectionDocument).where(
                CollectionDocument.collection_id == collection_id,
                CollectionDocument.document_id == doc_id,
            )
            result = await self.db.execute(delete_stmt)
            removed += result.rowcount

        # Note: document_count is computed automatically from documents relationship
        collection.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(collection)

        return collection

    # =========================================================================
    # Utility Methods
    # =========================================================================

    async def get_thread_context(
        self,
        thread_id: UUID,
        user_id: UUID,
        max_messages: Optional[int] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
    ) -> dict:
        """
        Get thread messages formatted for LLM context.

        Returns messages in chronological order, limited by count or tokens,
        with metadata about context usage and truncation.

        Args:
            thread_id: Thread UUID
            user_id: User UUID for access control
            max_messages: Override default max messages (uses config if None)
            max_tokens: Override default max tokens (uses config if None)
            model: Model name for model-aware token limits

        Returns:
            Dictionary with messages and context metadata
        """
        from src.core.config import settings
        from src.utils.token_counter import count_tokens

        # Use config defaults if not specified
        effective_max_messages = max_messages or settings.THREAD_DEFAULT_MAX_MESSAGES
        effective_max_tokens = max_tokens or settings.THREAD_DEFAULT_MAX_TOKENS

        # If model specified, use model-aware token limit
        if model and max_tokens is None:
            model_key = model.lower()
            for key, limit in settings.MODEL_CONTEXT_LIMITS.items():
                if key in model_key:
                    # Use 75% of model limit for context (leave room for response)
                    effective_max_tokens = int(limit * 0.75)
                    break

        thread = await self.get_thread(thread_id, user_id, include_messages=True)
        if not thread:
            # Return complete metadata structure matching the full response schema
            return {
                "messages": [],
                "metadata": {
                    "truncated": False,
                    "total_tokens": 0,
                    "max_tokens": effective_max_tokens,
                    "message_count": 0,
                    "total_messages": 0,
                    "usage_ratio": 0.0,
                    "approaching_limit": False,
                },
            }

        messages = []
        total_tokens = 0
        all_message_count = len([m for m in thread.messages if not m.is_deleted])
        truncated = False

        # Get messages in reverse order (newest first) for token limiting
        for msg in reversed(thread.messages):
            if msg.is_deleted:
                continue

            # Use accurate token counting
            msg_tokens = msg.token_count if msg.token_count else 0

            if total_tokens + msg_tokens > effective_max_tokens:
                truncated = True
                break

            messages.insert(0, msg.to_llm_format())
            total_tokens += msg_tokens

            if len(messages) >= effective_max_messages:
                truncated = True
                break

        # Calculate context usage ratio for warning
        usage_ratio = (
            total_tokens / effective_max_tokens if effective_max_tokens > 0 else 0
        )
        approaching_limit = usage_ratio >= settings.THREAD_CONTEXT_WARN_THRESHOLD

        return {
            "messages": messages,
            "metadata": {
                "truncated": truncated,
                "total_tokens": total_tokens,
                "max_tokens": effective_max_tokens,
                "message_count": len(messages),
                "total_messages": all_message_count,
                "usage_ratio": round(usage_ratio, 2),
                "approaching_limit": approaching_limit,
            },
        }

    async def search_conversations(
        self, workspace_id: UUID, user_id: UUID, query: str, limit: int = 20
    ) -> List[Conversation]:
        """Search conversations by title/description"""
        workspace = await self.get_workspace(workspace_id, user_id)
        if not workspace:
            return []

        search_pattern = f"%{query}%"

        stmt = (
            select(Conversation)
            .where(
                Conversation.workspace_id == workspace_id,
                Conversation.is_deleted == False,
                or_(
                    Conversation.title.ilike(search_pattern),
                    Conversation.description.ilike(search_pattern),
                ),
            )
            .order_by(desc(Conversation.last_activity_at))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        conversations = result.scalars().all()

        return conversations

    async def get_workspace_stats(
        self, workspace_id: UUID, user_id: UUID
    ) -> Optional[dict]:
        """Get workspace statistics"""
        workspace = await self.get_workspace(workspace_id, user_id)
        if not workspace:
            return None

        # Count conversations
        conv_count_stmt = select(func.count(Conversation.id)).where(
            Conversation.workspace_id == workspace_id, Conversation.is_deleted == False
        )
        conv_count_result = await self.db.execute(conv_count_stmt)
        conv_count = conv_count_result.scalar()

        # Count threads
        thread_count_stmt = (
            select(func.count(Thread.id))
            .join(Conversation)
            .where(
                Conversation.workspace_id == workspace_id, Thread.is_deleted == False
            )
        )
        thread_count_result = await self.db.execute(thread_count_stmt)
        thread_count = thread_count_result.scalar()

        # Count messages
        msg_count_stmt = (
            select(func.count(ChatMessage.id))
            .join(Thread)
            .join(Conversation)
            .where(
                Conversation.workspace_id == workspace_id,
                ChatMessage.is_deleted == False,
            )
        )
        msg_count_result = await self.db.execute(msg_count_stmt)
        msg_count = msg_count_result.scalar()

        # Count collections
        coll_count_stmt = select(func.count(Collection.id)).where(
            Collection.workspace_id == workspace_id, Collection.is_deleted == False
        )
        coll_count_result = await self.db.execute(coll_count_stmt)
        coll_count = coll_count_result.scalar()

        return {
            "workspace_id": str(workspace_id),
            "conversation_count": conv_count,
            "thread_count": thread_count,
            "message_count": msg_count,
            "collection_count": coll_count,
            "member_count": len(workspace.members),
        }


def get_chat_service(db: AsyncSession) -> ChatService:
    """Dependency injection helper for ChatService"""
    return ChatService(db)
