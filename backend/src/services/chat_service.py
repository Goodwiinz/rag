"""
Chat Service for Terminal Observatory thread-centric chat persistence.

Provides CRUD operations for workspaces, conversations, threads, and messages.
"""

import logging
from typing import Optional, List, Tuple
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, desc

from ..models import (
    Workspace, WorkspaceMember, WorkspaceRole,
    Conversation, Thread, ThreadStatus,
    ChatMessage, MessageRole,
    Citation, MessageAttachment,
    Collection, CollectionDocument,
    User
)
from ..schemas.chat import (
    WorkspaceCreate, WorkspaceUpdate,
    ConversationCreate, ConversationUpdate,
    ThreadCreate, ThreadUpdate,
    ChatMessageCreate, ChatMessageUpdate,
    CollectionCreate, CollectionUpdate
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

    def __init__(self, db: Session):
        self.db = db

    # =========================================================================
    # Workspace Operations
    # =========================================================================

    def create_workspace(
        self,
        data: WorkspaceCreate,
        owner_id: UUID
    ) -> Workspace:
        """Create a new workspace"""
        workspace = Workspace(
            name=data.name,
            description=data.description,
            is_public=data.is_public,
            owner_id=owner_id,
            organization_id=data.organization_id
        )
        self.db.add(workspace)

        # Add owner as a member with OWNER role
        member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=owner_id,
            role=WorkspaceRole.OWNER,
            joined_at=datetime.utcnow()
        )
        self.db.add(member)

        self.db.commit()
        self.db.refresh(workspace)

        logger.info(f"Created workspace: {workspace.id} - {workspace.name}")
        return workspace

    def get_workspace(
        self,
        workspace_id: UUID,
        user_id: UUID
    ) -> Optional[Workspace]:
        """Get workspace by ID if user has access"""
        workspace = self.db.query(Workspace).options(
            joinedload(Workspace.members),
            joinedload(Workspace.conversations)
        ).filter(
            Workspace.id == workspace_id,
            Workspace.is_deleted == False
        ).first()

        if not workspace:
            return None

        # Check access
        if not self._user_can_access_workspace(workspace, user_id):
            return None

        return workspace

    def list_workspaces(
        self,
        user_id: UUID,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Workspace], int]:
        """List workspaces accessible to user"""
        query = self.db.query(Workspace).join(
            WorkspaceMember
        ).filter(
            WorkspaceMember.user_id == user_id,
            Workspace.is_deleted == False
        )

        if not include_archived:
            query = query.filter(Workspace.is_archived == False)

        total = query.count()
        workspaces = query.order_by(
            desc(Workspace.updated_at)
        ).offset(offset).limit(limit).all()

        return workspaces, total

    def update_workspace(
        self,
        workspace_id: UUID,
        data: WorkspaceUpdate,
        user_id: UUID
    ) -> Optional[Workspace]:
        """Update workspace"""
        workspace = self.get_workspace(workspace_id, user_id)
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
        self.db.commit()
        self.db.refresh(workspace)

        return workspace

    def delete_workspace(
        self,
        workspace_id: UUID,
        user_id: UUID
    ) -> bool:
        """Soft delete workspace"""
        workspace = self.get_workspace(workspace_id, user_id)
        if not workspace:
            return False

        # Only owner can delete
        if str(workspace.owner_id) != str(user_id):
            return False

        workspace.is_deleted = True
        workspace.updated_at = datetime.utcnow()
        self.db.commit()

        logger.info(f"Deleted workspace: {workspace_id}")
        return True

    def _user_can_access_workspace(
        self,
        workspace: Workspace,
        user_id: UUID
    ) -> bool:
        """Check if user can access workspace"""
        if workspace.is_public:
            return True
        if str(workspace.owner_id) == str(user_id):
            return True
        return workspace.is_member(str(user_id))

    # =========================================================================
    # Conversation Operations
    # =========================================================================

    def create_conversation(
        self,
        data: ConversationCreate,
        user_id: UUID
    ) -> Optional[Conversation]:
        """Create a new conversation in a workspace"""
        # Verify workspace access
        workspace = self.get_workspace(data.workspace_id, user_id)
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
            last_activity_at=datetime.utcnow()
        )
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)

        logger.info(f"Created conversation: {conversation.id} - {conversation.title}")
        return conversation

    def get_conversation(
        self,
        conversation_id: UUID,
        user_id: UUID
    ) -> Optional[Conversation]:
        """Get conversation by ID"""
        conversation = self.db.query(Conversation).options(
            joinedload(Conversation.threads),
            joinedload(Conversation.workspace)
        ).filter(
            Conversation.id == conversation_id,
            Conversation.is_deleted == False
        ).first()

        if not conversation:
            return None

        # Check workspace access
        if not self._user_can_access_workspace(conversation.workspace, user_id):
            return None

        return conversation

    def list_conversations(
        self,
        workspace_id: UUID,
        user_id: UUID,
        include_archived: bool = False,
        search_query: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Conversation], int]:
        """List conversations in a workspace"""
        # Verify workspace access
        workspace = self.get_workspace(workspace_id, user_id)
        if not workspace:
            return [], 0

        query = self.db.query(Conversation).filter(
            Conversation.workspace_id == workspace_id,
            Conversation.is_deleted == False
        )

        if not include_archived:
            query = query.filter(Conversation.is_archived == False)

        if search_query:
            search_pattern = f"%{search_query}%"
            query = query.filter(
                or_(
                    Conversation.title.ilike(search_pattern),
                    Conversation.description.ilike(search_pattern)
                )
            )

        total = query.count()
        conversations = query.order_by(
            desc(Conversation.is_pinned),
            desc(Conversation.last_activity_at)
        ).offset(offset).limit(limit).all()

        return conversations, total

    def update_conversation(
        self,
        conversation_id: UUID,
        data: ConversationUpdate,
        user_id: UUID
    ) -> Optional[Conversation]:
        """Update conversation"""
        conversation = self.get_conversation(conversation_id, user_id)
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
        self.db.commit()
        self.db.refresh(conversation)

        return conversation

    def delete_conversation(
        self,
        conversation_id: UUID,
        user_id: UUID
    ) -> bool:
        """Soft delete conversation"""
        conversation = self.get_conversation(conversation_id, user_id)
        if not conversation:
            return False

        # Check permission
        if not conversation.workspace.can_user_admin(str(user_id)):
            return False

        conversation.is_deleted = True
        conversation.updated_at = datetime.utcnow()
        self.db.commit()

        logger.info(f"Deleted conversation: {conversation_id}")
        return True

    # =========================================================================
    # Thread Operations
    # =========================================================================

    def create_thread(
        self,
        data: ThreadCreate,
        user_id: UUID
    ) -> Optional[Thread]:
        """Create a new thread in a conversation"""
        # Verify conversation access
        conversation = self.get_conversation(data.conversation_id, user_id)
        if not conversation:
            return None

        # Check edit permission
        if not conversation.workspace.can_user_edit(str(user_id)):
            return None

        thread = Thread(
            conversation_id=data.conversation_id,
            title=data.title,
            status=ThreadStatus.ACTIVE,
            created_by_id=user_id,
            last_message_at=datetime.utcnow(),
            message_count=0,
            token_count=0
        )
        self.db.add(thread)

        # Create initial message if provided
        if data.initial_message:
            initial_msg = ChatMessage.create_user_message(
                thread_id=thread.id,
                user_id=str(user_id),
                content=data.initial_message
            )
            self.db.add(initial_msg)
            thread.message_count = 1

        # Update conversation activity
        conversation.update_activity()

        self.db.commit()
        self.db.refresh(thread)

        logger.info(f"Created thread: {thread.id}")
        return thread

    def get_thread(
        self,
        thread_id: UUID,
        user_id: UUID,
        include_messages: bool = False
    ) -> Optional[Thread]:
        """Get thread by ID"""
        query = self.db.query(Thread).options(
            joinedload(Thread.conversation).joinedload(Conversation.workspace)
        )

        if include_messages:
            query = query.options(
                joinedload(Thread.messages).joinedload(ChatMessage.citations).joinedload(Citation.document),
                joinedload(Thread.messages).joinedload(ChatMessage.attachments)
            )

        thread = query.filter(
            Thread.id == thread_id,
            Thread.is_deleted == False
        ).first()

        if not thread:
            return None

        # Check workspace access
        if not self._user_can_access_workspace(thread.conversation.workspace, user_id):
            return None

        return thread

    def list_threads(
        self,
        conversation_id: UUID,
        user_id: UUID,
        status_filter: Optional[ThreadStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Thread], int]:
        """List threads in a conversation"""
        # Verify conversation access
        conversation = self.get_conversation(conversation_id, user_id)
        if not conversation:
            return [], 0

        query = self.db.query(Thread).filter(
            Thread.conversation_id == conversation_id,
            Thread.is_deleted == False
        )

        if status_filter:
            query = query.filter(Thread.status == status_filter)

        total = query.count()
        threads = query.order_by(
            desc(Thread.last_message_at)
        ).offset(offset).limit(limit).all()

        return threads, total

    def update_thread(
        self,
        thread_id: UUID,
        data: ThreadUpdate,
        user_id: UUID
    ) -> Optional[Thread]:
        """Update thread"""
        thread = self.get_thread(thread_id, user_id)
        if not thread:
            return None

        # Check permission
        if not thread.conversation.workspace.can_user_edit(str(user_id)):
            return None

        if data.title is not None:
            thread.title = data.title
        if data.summary is not None:
            thread.summary = data.summary
        if data.status is not None:
            thread.status = data.status

        thread.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(thread)

        return thread

    def delete_thread(
        self,
        thread_id: UUID,
        user_id: UUID
    ) -> bool:
        """Soft delete thread"""
        thread = self.get_thread(thread_id, user_id)
        if not thread:
            return False

        # Check permission
        if not thread.conversation.workspace.can_user_edit(str(user_id)):
            return False

        thread.is_deleted = True
        thread.updated_at = datetime.utcnow()
        self.db.commit()

        logger.info(f"Deleted thread: {thread_id}")
        return True

    # =========================================================================
    # Message Operations
    # =========================================================================

    def create_message(
        self,
        data: ChatMessageCreate,
        user_id: UUID
    ) -> Optional[ChatMessage]:
        """Create a new message in a thread"""
        # Verify thread access
        thread = self.get_thread(data.thread_id, user_id)
        if not thread:
            return None

        # Check edit permission
        if not thread.conversation.workspace.can_user_edit(str(user_id)):
            return None

        # Count tokens for the message
        from ..utils.token_counter import count_message_tokens
        message_token_count = count_message_tokens(data.content, data.role.value)

        message = ChatMessage(
            thread_id=data.thread_id,
            user_id=user_id if data.role == MessageRole.USER else None,
            role=data.role,
            content=data.content,
            token_count=message_token_count
        )
        self.db.add(message)

        # Handle attachments
        if data.attachment_ids:
            for doc_id in data.attachment_ids:
                attachment = MessageAttachment(
                    message_id=message.id,
                    document_id=doc_id
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
                    snippet_preview=cit.snippet_preview,
                    page_number=cit.page_number,
                    score=cit.score,
                    rerank_score=cit.rerank_score,
                    document_title=cit.document_title,
                    document_type=cit.document_type
                )
                self.db.add(citation)

        # Update thread stats
        thread.message_count += 1
        thread.token_count += message_token_count
        thread.last_message_at = datetime.utcnow()

        # Update conversation activity
        thread.conversation.update_activity()

        self.db.commit()
        self.db.refresh(message)

        return message

    def create_assistant_message(
        self,
        thread_id: UUID,
        content: str,
        model_name: Optional[str] = None,
        token_count: int = 0,
        latency_ms: Optional[int] = None,
        citations: Optional[List[dict]] = None
    ) -> Optional[ChatMessage]:
        """Create an assistant message with optional citations"""
        message = ChatMessage.create_assistant_message(
            thread_id=str(thread_id),
            content=content,
            model_name=model_name,
            token_count=token_count,
            latency_ms=latency_ms
        )
        self.db.add(message)

        # Add citations if provided
        if citations:
            for cit in citations:
                citation = Citation(
                    message_id=message.id,
                    document_id=cit.get('document_id'),
                    external_reference_id=cit.get('external_reference_id'),
                    chunk_index=cit.get('chunk_index'),
                    chunk_id=cit.get('chunk_id'),
                    snippet=cit.get('snippet'),
                    snippet_preview=cit.get('snippet_preview'),
                    page_number=cit.get('page_number'),
                    score=cit.get('score'),
                    rerank_score=cit.get('rerank_score'),
                    document_title=cit.get('document_title'),
                    document_type=cit.get('document_type')
                )
                self.db.add(citation)

        # Update thread stats
        thread = self.db.query(Thread).filter(Thread.id == thread_id).first()
        if thread:
            thread.message_count += 1
            thread.token_count += token_count
            thread.last_message_at = datetime.utcnow()
            thread.conversation.update_activity()

        self.db.commit()
        self.db.refresh(message)

        return message

    def get_message(
        self,
        message_id: UUID,
        user_id: UUID
    ) -> Optional[ChatMessage]:
        """Get message by ID"""
        message = self.db.query(ChatMessage).options(
            joinedload(ChatMessage.citations).joinedload(Citation.document),
            joinedload(ChatMessage.attachments),
            joinedload(ChatMessage.thread).joinedload(Thread.conversation).joinedload(Conversation.workspace)
        ).filter(
            ChatMessage.id == message_id,
            ChatMessage.is_deleted == False
        ).first()

        if not message:
            return None

        # Check workspace access
        if not self._user_can_access_workspace(message.thread.conversation.workspace, user_id):
            return None

        return message

    def list_messages(
        self,
        thread_id: UUID,
        user_id: UUID,
        limit: int = 100,
        offset: int = 0,
        before_id: Optional[UUID] = None
    ) -> Tuple[List[ChatMessage], int]:
        """List messages in a thread"""
        # Verify thread access
        thread = self.get_thread(thread_id, user_id)
        if not thread:
            return [], 0

        query = self.db.query(ChatMessage).options(
            joinedload(ChatMessage.citations).joinedload(Citation.document),
            joinedload(ChatMessage.attachments)
        ).filter(
            ChatMessage.thread_id == thread_id,
            ChatMessage.is_deleted == False
        )

        if before_id:
            # Get messages before a specific message (for pagination)
            before_msg = self.db.query(ChatMessage).filter(
                ChatMessage.id == before_id
            ).first()
            if before_msg:
                query = query.filter(ChatMessage.created_at < before_msg.created_at)

        total = query.count()
        messages = query.order_by(
            ChatMessage.created_at.asc()
        ).offset(offset).limit(limit).all()

        return messages, total

    def update_message_feedback(
        self,
        message_id: UUID,
        data: ChatMessageUpdate,
        user_id: UUID
    ) -> Optional[ChatMessage]:
        """Update message feedback"""
        message = self.get_message(message_id, user_id)
        if not message:
            return None

        if data.feedback_rating is not None:
            message.feedback_rating = data.feedback_rating
        if data.feedback_text is not None:
            message.feedback_text = data.feedback_text

        message.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(message)

        return message

    def delete_message(
        self,
        message_id: UUID,
        user_id: UUID
    ) -> bool:
        """Soft delete message"""
        message = self.get_message(message_id, user_id)
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

        self.db.commit()

        logger.info(f"Deleted message: {message_id}")
        return True

    # =========================================================================
    # Collection Operations
    # =========================================================================

    def create_collection(
        self,
        data: CollectionCreate,
        user_id: UUID
    ) -> Optional[Collection]:
        """Create a new collection in a workspace"""
        # Verify workspace access
        workspace = self.get_workspace(data.workspace_id, user_id)
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
            icon=data.icon
        )
        self.db.add(collection)

        # Add initial documents if provided
        if data.document_ids:
            for idx, doc_id in enumerate(data.document_ids):
                coll_doc = CollectionDocument(
                    collection_id=collection.id,
                    document_id=doc_id,
                    position=idx
                )
                self.db.add(coll_doc)
            collection.document_count = len(data.document_ids)

        self.db.commit()
        self.db.refresh(collection)

        logger.info(f"Created collection: {collection.id} - {collection.name}")
        return collection

    def get_collection(
        self,
        collection_id: UUID,
        user_id: UUID
    ) -> Optional[Collection]:
        """Get collection by ID"""
        collection = self.db.query(Collection).options(
            joinedload(Collection.workspace),
            joinedload(Collection.documents)
        ).filter(
            Collection.id == collection_id,
            Collection.is_deleted == False
        ).first()

        if not collection:
            return None

        # Check workspace access
        if not self._user_can_access_workspace(collection.workspace, user_id):
            return None

        return collection

    def list_collections(
        self,
        workspace_id: UUID,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Collection], int]:
        """List collections in a workspace"""
        # Verify workspace access
        workspace = self.get_workspace(workspace_id, user_id)
        if not workspace:
            return [], 0

        query = self.db.query(Collection).filter(
            Collection.workspace_id == workspace_id,
            Collection.is_deleted == False
        )

        total = query.count()
        collections = query.order_by(
            Collection.name
        ).offset(offset).limit(limit).all()

        return collections, total

    def add_documents_to_collection(
        self,
        collection_id: UUID,
        document_ids: List[UUID],
        user_id: UUID
    ) -> Optional[Collection]:
        """Add documents to a collection"""
        collection = self.get_collection(collection_id, user_id)
        if not collection:
            return None

        # Check permission
        if not collection.workspace.can_user_edit(str(user_id)):
            return None

        # Get current max position
        max_pos = self.db.query(func.max(CollectionDocument.position)).filter(
            CollectionDocument.collection_id == collection_id
        ).scalar() or -1

        for doc_id in document_ids:
            # Check if already in collection
            existing = self.db.query(CollectionDocument).filter(
                CollectionDocument.collection_id == collection_id,
                CollectionDocument.document_id == doc_id
            ).first()

            if not existing:
                max_pos += 1
                coll_doc = CollectionDocument(
                    collection_id=collection_id,
                    document_id=doc_id,
                    position=max_pos
                )
                self.db.add(coll_doc)
                collection.document_count += 1

        collection.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(collection)

        return collection

    def remove_documents_from_collection(
        self,
        collection_id: UUID,
        document_ids: List[UUID],
        user_id: UUID
    ) -> Optional[Collection]:
        """Remove documents from a collection"""
        collection = self.get_collection(collection_id, user_id)
        if not collection:
            return None

        # Check permission
        if not collection.workspace.can_user_edit(str(user_id)):
            return None

        removed = 0
        for doc_id in document_ids:
            result = self.db.query(CollectionDocument).filter(
                CollectionDocument.collection_id == collection_id,
                CollectionDocument.document_id == doc_id
            ).delete()
            removed += result

        collection.document_count = max(0, collection.document_count - removed)
        collection.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(collection)

        return collection

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_thread_context(
        self,
        thread_id: UUID,
        user_id: UUID,
        max_messages: Optional[int] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None
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
        from ..core.config import settings
        from ..utils.token_counter import count_tokens

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

        thread = self.get_thread(thread_id, user_id, include_messages=True)
        if not thread:
            return {"messages": [], "metadata": {"truncated": False, "total_tokens": 0}}

        messages = []
        total_tokens = 0
        all_message_count = len([m for m in thread.messages if not m.is_deleted])
        truncated = False

        # Get messages in reverse order (newest first) for token limiting
        for msg in reversed(thread.messages):
            if msg.is_deleted:
                continue

            # Use accurate token counting
            msg_tokens = count_tokens(msg.content) if msg.content else 0

            if total_tokens + msg_tokens > effective_max_tokens:
                truncated = True
                break

            messages.insert(0, msg.to_llm_format())
            total_tokens += msg_tokens

            if len(messages) >= effective_max_messages:
                truncated = True
                break

        # Calculate context usage ratio for warning
        usage_ratio = total_tokens / effective_max_tokens if effective_max_tokens > 0 else 0
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
            }
        }

    def search_conversations(
        self,
        workspace_id: UUID,
        user_id: UUID,
        query: str,
        limit: int = 20
    ) -> List[Conversation]:
        """Search conversations by title/description"""
        workspace = self.get_workspace(workspace_id, user_id)
        if not workspace:
            return []

        search_pattern = f"%{query}%"

        conversations = self.db.query(Conversation).filter(
            Conversation.workspace_id == workspace_id,
            Conversation.is_deleted == False,
            or_(
                Conversation.title.ilike(search_pattern),
                Conversation.description.ilike(search_pattern)
            )
        ).order_by(
            desc(Conversation.last_activity_at)
        ).limit(limit).all()

        return conversations

    def get_workspace_stats(
        self,
        workspace_id: UUID,
        user_id: UUID
    ) -> Optional[dict]:
        """Get workspace statistics"""
        workspace = self.get_workspace(workspace_id, user_id)
        if not workspace:
            return None

        # Count conversations
        conv_count = self.db.query(func.count(Conversation.id)).filter(
            Conversation.workspace_id == workspace_id,
            Conversation.is_deleted == False
        ).scalar()

        # Count threads
        thread_count = self.db.query(func.count(Thread.id)).join(
            Conversation
        ).filter(
            Conversation.workspace_id == workspace_id,
            Thread.is_deleted == False
        ).scalar()

        # Count messages
        msg_count = self.db.query(func.count(ChatMessage.id)).join(
            Thread
        ).join(
            Conversation
        ).filter(
            Conversation.workspace_id == workspace_id,
            ChatMessage.is_deleted == False
        ).scalar()

        # Count collections
        coll_count = self.db.query(func.count(Collection.id)).filter(
            Collection.workspace_id == workspace_id,
            Collection.is_deleted == False
        ).scalar()

        return {
            'workspace_id': str(workspace_id),
            'conversation_count': conv_count,
            'thread_count': thread_count,
            'message_count': msg_count,
            'collection_count': coll_count,
            'member_count': len(workspace.members)
        }


def get_chat_service(db: Session) -> ChatService:
    """Dependency injection helper for ChatService"""
    return ChatService(db)
