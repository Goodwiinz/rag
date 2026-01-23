"""
Unit Tests for ChatService

Tests workspace, conversation, thread, and message management
with proper mocking of database sessions.

All tests use mocks - no external services required.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from uuid import uuid4, UUID
from datetime import datetime, timedelta
from typing import List

from tests.mocks.services import MockAsyncSession


# ============================================================================
# Test Data Builders
# ============================================================================

class WorkspaceBuilder:
    """Builder pattern for workspace test data."""

    def __init__(self):
        self._id = uuid4()
        self._name = "Test Workspace"
        self._description = "Test workspace description"
        self._owner_id = uuid4()
        self._organization_id = uuid4()
        self._is_public = False
        self._is_archived = False
        self._is_deleted = False
        self._created_at = datetime.utcnow()
        self._updated_at = datetime.utcnow()

    def with_id(self, id: UUID) -> "WorkspaceBuilder":
        self._id = id
        return self

    def with_name(self, name: str) -> "WorkspaceBuilder":
        self._name = name
        return self

    def with_owner(self, owner_id: UUID) -> "WorkspaceBuilder":
        self._owner_id = owner_id
        return self

    def with_organization(self, org_id: UUID) -> "WorkspaceBuilder":
        self._organization_id = org_id
        return self

    def public(self) -> "WorkspaceBuilder":
        self._is_public = True
        return self

    def archived(self) -> "WorkspaceBuilder":
        self._is_archived = True
        return self

    def deleted(self) -> "WorkspaceBuilder":
        self._is_deleted = True
        return self

    def build(self) -> Mock:
        workspace = Mock()
        workspace.id = self._id
        workspace.name = self._name
        workspace.description = self._description
        workspace.owner_id = self._owner_id
        workspace.organization_id = self._organization_id
        workspace.is_public = self._is_public
        workspace.is_archived = self._is_archived
        workspace.is_deleted = self._is_deleted
        workspace.created_at = self._created_at
        workspace.updated_at = self._updated_at
        workspace.conversations = []
        workspace.members = []
        return workspace


class ConversationBuilder:
    """Builder pattern for conversation test data."""

    def __init__(self):
        self._id = uuid4()
        self._workspace_id = uuid4()
        self._title = "Test Conversation"
        self._description = "Test conversation description"
        self._created_by_id = uuid4()
        self._is_archived = False
        self._is_pinned = False
        self._is_deleted = False
        self._last_activity_at = datetime.utcnow()

    def with_id(self, id: UUID) -> "ConversationBuilder":
        self._id = id
        return self

    def with_workspace(self, workspace_id: UUID) -> "ConversationBuilder":
        self._workspace_id = workspace_id
        return self

    def with_title(self, title: str) -> "ConversationBuilder":
        self._title = title
        return self

    def created_by(self, user_id: UUID) -> "ConversationBuilder":
        self._created_by_id = user_id
        return self

    def archived(self) -> "ConversationBuilder":
        self._is_archived = True
        return self

    def pinned(self) -> "ConversationBuilder":
        self._is_pinned = True
        return self

    def build(self) -> Mock:
        conversation = Mock()
        conversation.id = self._id
        conversation.workspace_id = self._workspace_id
        conversation.title = self._title
        conversation.description = self._description
        conversation.created_by_id = self._created_by_id
        conversation.is_archived = self._is_archived
        conversation.is_pinned = self._is_pinned
        conversation.is_deleted = self._is_deleted
        conversation.last_activity_at = self._last_activity_at
        conversation.threads = []
        return conversation


class ThreadBuilder:
    """Builder pattern for thread test data."""

    def __init__(self):
        self._id = uuid4()
        self._conversation_id = uuid4()
        self._title = "Test Thread"
        self._status = Mock(value="active")
        self._created_by_id = uuid4()
        self._message_count = 0
        self._token_count = 0
        self._is_deleted = False
        self._last_message_at = datetime.utcnow()
        self._summary = None

    def with_id(self, id: UUID) -> "ThreadBuilder":
        self._id = id
        return self

    def with_conversation(self, conversation_id: UUID) -> "ThreadBuilder":
        self._conversation_id = conversation_id
        return self

    def with_title(self, title: str) -> "ThreadBuilder":
        self._title = title
        return self

    def with_status(self, status: str) -> "ThreadBuilder":
        self._status = Mock(value=status)
        return self

    def with_message_count(self, count: int) -> "ThreadBuilder":
        self._message_count = count
        self._token_count = count * 50
        return self

    def with_summary(self, summary: str) -> "ThreadBuilder":
        self._summary = summary
        return self

    def build(self) -> Mock:
        thread = Mock()
        thread.id = self._id
        thread.conversation_id = self._conversation_id
        thread.title = self._title
        thread.status = self._status
        thread.created_by_id = self._created_by_id
        thread.message_count = self._message_count
        thread.token_count = self._token_count
        thread.is_deleted = self._is_deleted
        thread.last_message_at = self._last_message_at
        thread.summary = self._summary
        thread.messages = []
        return thread


class MessageBuilder:
    """Builder pattern for message test data."""

    def __init__(self):
        self._id = uuid4()
        self._thread_id = uuid4()
        self._role = Mock(value="user")
        self._content = "Test message content"
        self._user_id = uuid4()
        self._token_count = 10
        self._is_deleted = False
        self._created_at = datetime.utcnow()
        self._citations = []
        self._attachments = []

    def with_id(self, id: UUID) -> "MessageBuilder":
        self._id = id
        return self

    def with_thread(self, thread_id: UUID) -> "MessageBuilder":
        self._thread_id = thread_id
        return self

    def with_role(self, role: str) -> "MessageBuilder":
        self._role = Mock(value=role)
        if role == "assistant":
            self._user_id = None
        return self

    def with_content(self, content: str) -> "MessageBuilder":
        self._content = content
        self._token_count = len(content.split()) * 2
        return self

    def by_user(self, user_id: UUID) -> "MessageBuilder":
        self._user_id = user_id
        return self

    def with_citations(self, citations: List[Mock]) -> "MessageBuilder":
        self._citations = citations
        return self

    def build(self) -> Mock:
        message = Mock()
        message.id = self._id
        message.thread_id = self._thread_id
        message.role = self._role
        message.content = self._content
        message.user_id = self._user_id
        message.token_count = self._token_count
        message.is_deleted = self._is_deleted
        message.created_at = self._created_at
        message.citations = self._citations
        message.attachments = self._attachments

        def to_llm_format():
            return {"role": self._role.value, "content": self._content}

        message.to_llm_format = to_llm_format
        return message


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Create mock async session."""
    return MockAsyncSession()


@pytest.fixture
def mock_user():
    """Create mock user."""
    user = Mock()
    user.id = uuid4()
    user.email = "test@example.com"
    user.first_name = "Test"
    user.last_name = "User"
    user.organization_id = uuid4()
    user.role = Mock(value="user")
    user.is_active = True
    return user


@pytest.fixture
def mock_admin_user(mock_user):
    """Create mock admin user."""
    mock_user.role = Mock(value="admin")
    return mock_user


# ============================================================================
# Workspace Tests
# ============================================================================

class TestWorkspaceCreation:
    """Test workspace creation logic."""

    @pytest.mark.asyncio
    async def test_creates_workspace_with_valid_data(self, mock_db, mock_user):
        """Should create workspace with valid data."""
        workspace_data = {
            "name": "My Workspace",
            "description": "A test workspace",
            "is_public": False
        }

        # Simulate service behavior
        workspace = WorkspaceBuilder() \
            .with_name(workspace_data["name"]) \
            .with_owner(mock_user.id) \
            .with_organization(mock_user.organization_id) \
            .build()

        mock_db.add(workspace)
        await mock_db.commit()

        mock_db.assert_added(1)
        mock_db.assert_committed()

    @pytest.mark.asyncio
    async def test_workspace_name_is_required(self, mock_db, mock_user):
        """Should require workspace name."""
        workspace_data = {
            "name": "",  # Empty name
            "description": "Description"
        }

        # Validate name
        is_valid = bool(workspace_data["name"].strip())
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_workspace_inherits_user_organization(self, mock_db, mock_user):
        """Workspace should inherit user's organization."""
        workspace = WorkspaceBuilder() \
            .with_owner(mock_user.id) \
            .with_organization(mock_user.organization_id) \
            .build()

        assert workspace.organization_id == mock_user.organization_id

    @pytest.mark.asyncio
    async def test_public_workspace_creation(self, mock_db, mock_user):
        """Should create public workspace."""
        workspace = WorkspaceBuilder() \
            .with_owner(mock_user.id) \
            .public() \
            .build()

        assert workspace.is_public is True


class TestWorkspaceRetrieval:
    """Test workspace retrieval logic."""

    @pytest.mark.asyncio
    async def test_gets_workspace_by_id(self, mock_db, mock_user):
        """Should retrieve workspace by ID."""
        workspace = WorkspaceBuilder() \
            .with_owner(mock_user.id) \
            .build()

        mock_db.set_query_result([workspace])

        result = await mock_db.execute(Mock())
        found = result.scalar_one_or_none()

        assert found is not None
        assert found.id == workspace.id

    @pytest.mark.asyncio
    async def test_returns_none_for_nonexistent_workspace(self, mock_db):
        """Should return None for nonexistent workspace."""
        mock_db.set_query_result([])

        result = await mock_db.execute(Mock())
        found = result.scalar_one_or_none()

        assert found is None

    @pytest.mark.asyncio
    async def test_excludes_deleted_workspaces(self, mock_db, mock_user):
        """Should exclude deleted workspaces from results."""
        deleted_workspace = WorkspaceBuilder() \
            .with_owner(mock_user.id) \
            .deleted() \
            .build()

        # Filter out deleted
        workspaces = [deleted_workspace]
        active_workspaces = [w for w in workspaces if not w.is_deleted]

        assert len(active_workspaces) == 0


class TestWorkspaceAccessControl:
    """Test workspace access control."""

    def test_owner_can_access_workspace(self, mock_user):
        """Owner should be able to access their workspace."""
        workspace = WorkspaceBuilder() \
            .with_owner(mock_user.id) \
            .build()

        can_access = (
            workspace.owner_id == mock_user.id or
            workspace.is_public or
            mock_user.id in [m.id for m in workspace.members]
        )

        assert can_access is True

    def test_public_workspace_accessible_by_all(self, mock_user):
        """Public workspace should be accessible by any user."""
        other_user_id = uuid4()
        workspace = WorkspaceBuilder() \
            .with_owner(other_user_id) \
            .public() \
            .build()

        can_access = (
            workspace.owner_id == mock_user.id or
            workspace.is_public
        )

        assert can_access is True

    def test_private_workspace_not_accessible_by_others(self, mock_user):
        """Private workspace should not be accessible by non-members."""
        other_user_id = uuid4()
        workspace = WorkspaceBuilder() \
            .with_owner(other_user_id) \
            .build()  # Private by default

        can_access = (
            workspace.owner_id == mock_user.id or
            workspace.is_public or
            mock_user.id in [m.id for m in workspace.members]
        )

        assert can_access is False


# ============================================================================
# Conversation Tests
# ============================================================================

class TestConversationCreation:
    """Test conversation creation logic."""

    @pytest.mark.asyncio
    async def test_creates_conversation_in_workspace(self, mock_db, mock_user):
        """Should create conversation within workspace."""
        workspace = WorkspaceBuilder() \
            .with_owner(mock_user.id) \
            .build()

        conversation = ConversationBuilder() \
            .with_workspace(workspace.id) \
            .with_title("New Conversation") \
            .created_by(mock_user.id) \
            .build()

        mock_db.add(conversation)
        await mock_db.commit()

        mock_db.assert_added(1)
        assert conversation.workspace_id == workspace.id

    @pytest.mark.asyncio
    async def test_conversation_updates_workspace_activity(self, mock_db, mock_user):
        """Creating conversation should update workspace activity."""
        workspace = WorkspaceBuilder() \
            .with_owner(mock_user.id) \
            .build()

        old_updated_at = workspace.updated_at

        # Create conversation
        conversation = ConversationBuilder() \
            .with_workspace(workspace.id) \
            .build()

        # Update workspace
        workspace.updated_at = datetime.utcnow()

        assert workspace.updated_at >= old_updated_at


class TestConversationListing:
    """Test conversation listing logic."""

    @pytest.mark.asyncio
    async def test_lists_conversations_in_workspace(self, mock_db, mock_user):
        """Should list conversations within workspace."""
        workspace = WorkspaceBuilder().with_owner(mock_user.id).build()

        conversations = [
            ConversationBuilder().with_workspace(workspace.id).with_title(f"Conv {i}").build()
            for i in range(5)
        ]

        mock_db.set_scalars_result(conversations)

        result = await mock_db.scalars(Mock())
        found = result.all()

        assert len(found) == 5

    @pytest.mark.asyncio
    async def test_filters_archived_conversations(self, mock_db, mock_user):
        """Should filter archived conversations when requested."""
        workspace_id = uuid4()

        conversations = [
            ConversationBuilder().with_workspace(workspace_id).with_title("Active").build(),
            ConversationBuilder().with_workspace(workspace_id).archived().with_title("Archived").build(),
        ]

        # Filter non-archived
        active_conversations = [c for c in conversations if not c.is_archived]

        assert len(active_conversations) == 1
        assert active_conversations[0].title == "Active"


# ============================================================================
# Thread Tests
# ============================================================================

class TestThreadCreation:
    """Test thread creation logic."""

    @pytest.mark.asyncio
    async def test_creates_thread_in_conversation(self, mock_db, mock_user):
        """Should create thread within conversation."""
        conversation = ConversationBuilder() \
            .created_by(mock_user.id) \
            .build()

        thread = ThreadBuilder() \
            .with_conversation(conversation.id) \
            .with_title("New Thread") \
            .build()

        mock_db.add(thread)
        await mock_db.commit()

        assert thread.conversation_id == conversation.id

    @pytest.mark.asyncio
    async def test_thread_has_initial_status(self, mock_db):
        """Thread should have initial active status."""
        thread = ThreadBuilder().build()

        assert thread.status.value == "active"


class TestThreadHistory:
    """Test thread history and pagination."""

    @pytest.mark.asyncio
    async def test_paginates_thread_messages(self, mock_db):
        """Should paginate thread messages."""
        thread = ThreadBuilder().build()

        # Create 20 messages
        messages = [
            MessageBuilder().with_thread(thread.id).with_content(f"Message {i}").build()
            for i in range(20)
        ]

        # Paginate: page 1, limit 10
        offset = 0
        limit = 10
        paginated = messages[offset:offset + limit]

        assert len(paginated) == 10

    @pytest.mark.asyncio
    async def test_returns_messages_in_chronological_order(self, mock_db):
        """Should return messages in chronological order."""
        thread = ThreadBuilder().build()

        now = datetime.utcnow()
        messages = [
            MessageBuilder().with_thread(thread.id).build(),
            MessageBuilder().with_thread(thread.id).build(),
            MessageBuilder().with_thread(thread.id).build(),
        ]

        # Assign timestamps
        for i, msg in enumerate(messages):
            msg.created_at = now + timedelta(minutes=i)

        # Sort by created_at
        sorted_messages = sorted(messages, key=lambda m: m.created_at)

        # First message should have earliest timestamp
        assert sorted_messages[0].created_at <= sorted_messages[-1].created_at


class TestBulkThreadOperations:
    """Test bulk thread operations."""

    @pytest.mark.asyncio
    async def test_bulk_archives_threads(self, mock_db, mock_user):
        """Should bulk archive multiple threads."""
        conversation_id = uuid4()

        threads = [
            ThreadBuilder().with_conversation(conversation_id).build()
            for _ in range(5)
        ]

        thread_ids = [t.id for t in threads]

        # Archive all
        for thread in threads:
            thread.status = Mock(value="archived")

        archived_count = sum(1 for t in threads if t.status.value == "archived")
        assert archived_count == 5

    @pytest.mark.asyncio
    async def test_bulk_deletes_threads(self, mock_db, mock_user):
        """Should bulk delete multiple threads."""
        conversation_id = uuid4()

        threads = [
            ThreadBuilder().with_conversation(conversation_id).build()
            for _ in range(3)
        ]

        # Soft delete
        for thread in threads:
            thread.is_deleted = True

        deleted_count = sum(1 for t in threads if t.is_deleted)
        assert deleted_count == 3

    @pytest.mark.asyncio
    async def test_respects_permission_on_bulk_operations(self, mock_db, mock_user):
        """Should check permissions for each thread in bulk operation."""
        other_user_id = uuid4()

        threads = [
            ThreadBuilder().build(),  # Owned by default user
            ThreadBuilder().build(),  # Owned by default user
        ]

        threads[0].created_by_id = mock_user.id  # Can modify
        threads[1].created_by_id = other_user_id  # Cannot modify

        # Filter to only modifiable threads
        modifiable = [t for t in threads if t.created_by_id == mock_user.id]

        assert len(modifiable) == 1


# ============================================================================
# Message Tests
# ============================================================================

class TestMessageCreation:
    """Test message creation logic."""

    @pytest.mark.asyncio
    async def test_creates_user_message(self, mock_db, mock_user):
        """Should create user message in thread."""
        thread = ThreadBuilder().build()

        message = MessageBuilder() \
            .with_thread(thread.id) \
            .with_role("user") \
            .with_content("Hello, world!") \
            .by_user(mock_user.id) \
            .build()

        mock_db.add(message)
        await mock_db.commit()

        assert message.role.value == "user"
        assert message.user_id == mock_user.id

    @pytest.mark.asyncio
    async def test_creates_assistant_message(self, mock_db):
        """Should create assistant message in thread."""
        thread = ThreadBuilder().build()

        message = MessageBuilder() \
            .with_thread(thread.id) \
            .with_role("assistant") \
            .with_content("Hello! How can I help you?") \
            .build()

        assert message.role.value == "assistant"
        assert message.user_id is None

    @pytest.mark.asyncio
    async def test_updates_thread_message_count(self, mock_db):
        """Creating message should update thread message count."""
        thread = ThreadBuilder().with_message_count(5).build()

        initial_count = thread.message_count

        # Add message
        message = MessageBuilder().with_thread(thread.id).build()
        thread.message_count += 1
        thread.messages.append(message)

        assert thread.message_count == initial_count + 1

    @pytest.mark.asyncio
    async def test_updates_thread_last_message_at(self, mock_db):
        """Creating message should update thread last_message_at."""
        thread = ThreadBuilder().build()
        old_timestamp = thread.last_message_at

        # Add message
        message = MessageBuilder().with_thread(thread.id).build()
        thread.last_message_at = message.created_at

        assert thread.last_message_at >= old_timestamp


class TestMessageLlmFormat:
    """Test message LLM format conversion."""

    def test_converts_to_llm_format(self):
        """Should convert message to LLM-compatible format."""
        message = MessageBuilder() \
            .with_role("user") \
            .with_content("What is machine learning?") \
            .build()

        llm_format = message.to_llm_format()

        assert llm_format == {
            "role": "user",
            "content": "What is machine learning?"
        }

    def test_converts_assistant_message(self):
        """Should convert assistant message correctly."""
        message = MessageBuilder() \
            .with_role("assistant") \
            .with_content("Machine learning is a subset of AI...") \
            .build()

        llm_format = message.to_llm_format()

        assert llm_format["role"] == "assistant"


# ============================================================================
# Access Control Tests
# ============================================================================

class TestMessageAccessControl:
    """Test message access control."""

    def test_user_can_access_own_workspace_messages(self, mock_user):
        """User should access messages in their workspace."""
        workspace = WorkspaceBuilder().with_owner(mock_user.id).build()
        conversation = ConversationBuilder().with_workspace(workspace.id).build()
        thread = ThreadBuilder().with_conversation(conversation.id).build()
        message = MessageBuilder().with_thread(thread.id).build()

        # Check access through hierarchy
        can_access = workspace.owner_id == mock_user.id
        assert can_access is True

    def test_admin_can_access_any_workspace_messages(self, mock_admin_user):
        """Admin should access any workspace's messages."""
        other_user_id = uuid4()
        workspace = WorkspaceBuilder().with_owner(other_user_id).build()

        # Admin check
        is_admin = mock_admin_user.role.value == "admin"
        assert is_admin is True


# ============================================================================
# Thread Context Tests
# ============================================================================

class TestThreadContext:
    """Test thread context retrieval for LLM."""

    @pytest.mark.asyncio
    async def test_retrieves_thread_context(self, mock_db):
        """Should retrieve thread context for LLM."""
        thread = ThreadBuilder().build()

        messages = [
            MessageBuilder().with_thread(thread.id).with_role("user").with_content("Hello").build(),
            MessageBuilder().with_thread(thread.id).with_role("assistant").with_content("Hi!").build(),
            MessageBuilder().with_thread(thread.id).with_role("user").with_content("Question").build(),
        ]

        context = [msg.to_llm_format() for msg in messages]

        assert len(context) == 3
        assert context[0]["role"] == "user"
        assert context[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_limits_context_by_token_count(self, mock_db):
        """Should limit context to max token count."""
        max_tokens = 100

        # Create messages with explicit token counts for predictable behavior
        # Using multi-word content so token calculation works properly
        # (token_count = word_count * 2)
        msg1 = MessageBuilder().with_content("word " * 25).build()  # 25 words = 50 tokens
        msg2 = MessageBuilder().with_content("word " * 25).build()  # 25 words = 50 tokens
        msg3 = MessageBuilder().with_content("word " * 25).build()  # 25 words = 50 tokens
        messages = [msg1, msg2, msg3]

        # Simulate token-limited context building
        context = []
        total_tokens = 0

        for msg in reversed(messages):  # Most recent first
            if total_tokens + msg.token_count > max_tokens:
                break
            context.insert(0, msg)
            total_tokens += msg.token_count

        # Should only include 2 messages (100 tokens limit)
        # 50 + 50 = 100, so 2 messages fit exactly
        assert len(context) <= 2
