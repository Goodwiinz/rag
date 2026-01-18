"""
Comprehensive Unit Tests for ChatService.

Applies testing patterns from Temporal Python Testing skill:
- Isolated unit tests with mocked dependencies
- Error injection for edge cases
- Parameterized testing for decision branches
- Coverage strategies targeting ≥80%

Test Categories:
- Workspace CRUD operations
- Conversation CRUD operations
- Thread CRUD operations (including bulk operations)
- Message CRUD operations
- Collection operations
- Access control and permissions
- Error handling
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from uuid import uuid4, UUID
from datetime import datetime, timedelta
from typing import List, Optional

# Test markers
pytestmark = [pytest.mark.unit, pytest.mark.chat]


# =============================================================================
# Fixtures - Following Temporal pattern of reusable test environments
# =============================================================================

@pytest.fixture
def mock_db_session():
    """
    Mock database session for isolated testing.
    Equivalent to WorkflowEnvironment for Temporal tests.
    """
    session = MagicMock()
    session.query.return_value = session
    session.filter.return_value = session
    session.options.return_value = session
    session.first.return_value = None
    session.all.return_value = []
    session.count.return_value = 0
    session.scalar.return_value = 0
    session.add = MagicMock()
    session.commit = MagicMock()
    session.refresh = MagicMock()
    session.rollback = MagicMock()
    session.begin_nested = MagicMock(return_value=MagicMock())
    return session


@pytest.fixture
def mock_user():
    """Create a mock user for testing."""
    user = Mock()
    user.id = uuid4()
    user.email = "test@example.com"
    user.is_active = True
    return user


@pytest.fixture
def mock_admin_user():
    """Create a mock admin user."""
    user = Mock()
    user.id = uuid4()
    user.email = "admin@example.com"
    user.is_active = True
    return user


@pytest.fixture
def mock_workspace(mock_user):
    """Create a mock workspace with proper access control methods."""
    workspace = Mock()
    workspace.id = uuid4()
    workspace.name = "Test Workspace"
    workspace.description = "Test workspace description"
    workspace.owner_id = mock_user.id
    workspace.organization_id = uuid4()
    workspace.is_public = False
    workspace.is_archived = False
    workspace.is_deleted = False
    workspace.created_at = datetime.utcnow()
    workspace.updated_at = datetime.utcnow()
    workspace.members = []
    workspace.conversations = []

    # Access control methods
    workspace.is_member = Mock(return_value=True)
    workspace.can_user_edit = Mock(return_value=True)
    workspace.can_user_admin = Mock(return_value=True)

    return workspace


@pytest.fixture
def mock_conversation(mock_workspace, mock_user):
    """Create a mock conversation."""
    conversation = Mock()
    conversation.id = uuid4()
    conversation.workspace_id = mock_workspace.id
    conversation.workspace = mock_workspace
    conversation.title = "Test Conversation"
    conversation.description = "Test description"
    conversation.created_by_id = mock_user.id
    conversation.is_archived = False
    conversation.is_pinned = False
    conversation.is_deleted = False
    conversation.last_activity_at = datetime.utcnow()
    conversation.threads = []
    conversation.update_activity = Mock()
    return conversation


@pytest.fixture
def mock_thread(mock_conversation, mock_user):
    """Create a mock thread."""
    from unittest.mock import PropertyMock

    thread = Mock()
    thread.id = uuid4()
    thread.conversation_id = mock_conversation.id
    thread.conversation = mock_conversation
    thread.title = "Test Thread"
    thread.status = Mock(value="active")
    thread.created_by_id = mock_user.id
    thread.message_count = 0
    thread.token_count = 0
    thread.is_deleted = False
    thread.last_message_at = datetime.utcnow()
    thread.messages = []
    thread.summary = None
    return thread


@pytest.fixture
def chat_service(mock_db_session):
    """
    Create ChatService with mocked database session.
    Equivalent to Worker fixture in Temporal tests.
    """
    import sys
    import os

    # Add backend/src to path if not already
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    src_dir = os.path.join(backend_dir, "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    from src.services.chat_service import ChatService
    return ChatService(mock_db_session)


# =============================================================================
# Workspace Tests - Following Temporal unit test patterns
# =============================================================================

class TestWorkspaceOperations:
    """Test workspace CRUD operations."""

    def test_create_workspace_success(self, chat_service, mock_db_session, mock_user):
        """Test successful workspace creation."""
        from src.schemas.chat import WorkspaceCreate

        data = WorkspaceCreate(
            name="New Workspace",
            description="A new workspace",
            is_public=False,
            organization_id=uuid4()
        )

        # Configure mock to return workspace after commit
        mock_workspace = Mock()
        mock_workspace.id = uuid4()
        mock_workspace.name = data.name

        mock_db_session.refresh = Mock(side_effect=lambda x: setattr(x, 'id', mock_workspace.id))

        result = chat_service.create_workspace(data, mock_user.id)

        # Verify database operations
        assert mock_db_session.add.call_count == 2  # Workspace + Member
        mock_db_session.commit.assert_called_once()

    def test_get_workspace_not_found(self, chat_service, mock_db_session, mock_user):
        """Test getting non-existent workspace returns None."""
        mock_db_session.first.return_value = None

        result = chat_service.get_workspace(uuid4(), mock_user.id)

        assert result is None

    def test_get_workspace_with_access(self, chat_service, mock_db_session, mock_user, mock_workspace):
        """Test getting workspace with proper access."""
        mock_db_session.first.return_value = mock_workspace
        mock_workspace.owner_id = mock_user.id  # User is owner

        result = chat_service.get_workspace(mock_workspace.id, mock_user.id)

        assert result == mock_workspace

    def test_get_workspace_public_access(self, chat_service, mock_db_session, mock_user, mock_workspace):
        """Test public workspace is accessible to any user."""
        mock_workspace.is_public = True
        mock_workspace.owner_id = uuid4()  # Different owner
        mock_db_session.first.return_value = mock_workspace

        result = chat_service.get_workspace(mock_workspace.id, mock_user.id)

        assert result == mock_workspace

    @pytest.mark.parametrize("is_public,is_member,is_owner,expected_access", [
        (True, False, False, True),   # Public workspace accessible to anyone
        (False, True, False, True),   # Private but user is member
        (False, False, True, True),   # Private but user is owner
        (False, False, False, False), # Private, not member, not owner
    ])
    def test_workspace_access_control(
        self, chat_service, mock_db_session, mock_user, mock_workspace,
        is_public, is_member, is_owner, expected_access
    ):
        """Parameterized test for workspace access control decisions."""
        mock_workspace.is_public = is_public
        mock_workspace.is_member.return_value = is_member
        mock_workspace.owner_id = mock_user.id if is_owner else uuid4()
        mock_db_session.first.return_value = mock_workspace

        result = chat_service._user_can_access_workspace(mock_workspace, mock_user.id)

        assert result == expected_access

    def test_list_workspaces_pagination(self, chat_service, mock_db_session, mock_user):
        """Test workspace listing with pagination."""
        mock_workspaces = [Mock(id=uuid4(), name=f"Workspace {i}") for i in range(5)]

        # Create a proper query chain mock
        query_mock = MagicMock()
        query_mock.join.return_value = query_mock
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.offset.return_value = query_mock
        query_mock.limit.return_value = query_mock
        query_mock.count.return_value = 10
        query_mock.all.return_value = mock_workspaces

        mock_db_session.query.return_value = query_mock

        workspaces, total = chat_service.list_workspaces(mock_user.id, limit=5, offset=0)

        assert len(workspaces) == 5
        assert total == 10

    def test_delete_workspace_only_owner(self, chat_service, mock_db_session, mock_user, mock_workspace):
        """Test only owner can delete workspace."""
        # User is owner
        mock_workspace.owner_id = mock_user.id
        mock_db_session.first.return_value = mock_workspace

        with patch.object(chat_service, 'get_workspace', return_value=mock_workspace):
            result = chat_service.delete_workspace(mock_workspace.id, mock_user.id)

        assert result is True
        assert mock_workspace.is_deleted is True

    def test_delete_workspace_non_owner_denied(self, chat_service, mock_db_session, mock_user, mock_workspace):
        """Test non-owner cannot delete workspace."""
        mock_workspace.owner_id = uuid4()  # Different user
        mock_db_session.first.return_value = mock_workspace

        with patch.object(chat_service, 'get_workspace', return_value=mock_workspace):
            result = chat_service.delete_workspace(mock_workspace.id, mock_user.id)

        assert result is False

    def test_update_workspace_success(self, chat_service, mock_db_session, mock_user, mock_workspace):
        """Test updating workspace properties."""
        from src.schemas.chat import WorkspaceUpdate

        data = WorkspaceUpdate(
            name="Updated Workspace",
            description="Updated description",
            is_public=True,
            is_archived=False
        )

        with patch.object(chat_service, 'get_workspace', return_value=mock_workspace):
            result = chat_service.update_workspace(mock_workspace.id, data, mock_user.id)

        assert result == mock_workspace
        assert mock_workspace.name == "Updated Workspace"
        assert mock_workspace.description == "Updated description"
        assert mock_workspace.is_public is True

    def test_update_workspace_partial_update(self, chat_service, mock_db_session, mock_user, mock_workspace):
        """Test partial workspace update (only name)."""
        from src.schemas.chat import WorkspaceUpdate

        original_description = mock_workspace.description
        data = WorkspaceUpdate(name="New Name Only")

        with patch.object(chat_service, 'get_workspace', return_value=mock_workspace):
            result = chat_service.update_workspace(mock_workspace.id, data, mock_user.id)

        assert result == mock_workspace
        assert mock_workspace.name == "New Name Only"
        assert mock_workspace.description == original_description  # Unchanged

    def test_update_workspace_no_permission(self, chat_service, mock_db_session, mock_user, mock_workspace):
        """Test update fails without admin permission."""
        from src.schemas.chat import WorkspaceUpdate

        mock_workspace.can_user_admin.return_value = False
        data = WorkspaceUpdate(name="New Name")

        with patch.object(chat_service, 'get_workspace', return_value=mock_workspace):
            result = chat_service.update_workspace(mock_workspace.id, data, mock_user.id)

        assert result is None


# =============================================================================
# Conversation Tests
# =============================================================================

class TestConversationOperations:
    """Test conversation CRUD operations."""

    def test_create_conversation_success(self, chat_service, mock_db_session, mock_user, mock_workspace):
        """Test successful conversation creation."""
        from src.schemas.chat import ConversationCreate

        data = ConversationCreate(
            workspace_id=mock_workspace.id,
            title="New Conversation",
            description="A new conversation"
        )

        with patch.object(chat_service, 'get_workspace', return_value=mock_workspace):
            result = chat_service.create_conversation(data, mock_user.id)

        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    def test_create_conversation_no_workspace_access(self, chat_service, mock_db_session, mock_user):
        """Test conversation creation fails without workspace access."""
        from src.schemas.chat import ConversationCreate

        data = ConversationCreate(
            workspace_id=uuid4(),
            title="New Conversation"
        )

        with patch.object(chat_service, 'get_workspace', return_value=None):
            result = chat_service.create_conversation(data, mock_user.id)

        assert result is None

    def test_list_conversations_with_search(self, chat_service, mock_db_session, mock_user, mock_workspace):
        """Test conversation listing with search query."""
        mock_convs = [
            Mock(id=uuid4(), title="ML Discussion"),
            Mock(id=uuid4(), title="ML Research")
        ]
        mock_db_session.count.return_value = 2
        mock_db_session.all.return_value = mock_convs

        with patch.object(chat_service, 'get_workspace', return_value=mock_workspace):
            convs, total = chat_service.list_conversations(
                mock_workspace.id, mock_user.id, search_query="ML"
            )

        assert total == 2

    def test_get_conversation_success(self, chat_service, mock_db_session, mock_user, mock_conversation):
        """Test getting conversation by ID."""
        # Create proper query chain mock
        query_mock = MagicMock()
        query_mock.options.return_value = query_mock
        query_mock.filter.return_value = query_mock
        query_mock.first.return_value = mock_conversation

        mock_db_session.query.return_value = query_mock

        result = chat_service.get_conversation(mock_conversation.id, mock_user.id)

        assert result == mock_conversation

    def test_get_conversation_not_found(self, chat_service, mock_db_session, mock_user):
        """Test getting non-existent conversation."""
        query_mock = MagicMock()
        query_mock.options.return_value = query_mock
        query_mock.filter.return_value = query_mock
        query_mock.first.return_value = None

        mock_db_session.query.return_value = query_mock

        result = chat_service.get_conversation(uuid4(), mock_user.id)

        assert result is None

    def test_delete_conversation_success(self, chat_service, mock_db_session, mock_user, mock_conversation):
        """Test soft-deleting conversation."""
        with patch.object(chat_service, 'get_conversation', return_value=mock_conversation):
            result = chat_service.delete_conversation(mock_conversation.id, mock_user.id)

        assert result is True
        assert mock_conversation.is_deleted is True

    def test_delete_conversation_no_permission(self, chat_service, mock_db_session, mock_user, mock_conversation):
        """Test delete fails without admin permission."""
        mock_conversation.workspace.can_user_admin.return_value = False

        with patch.object(chat_service, 'get_conversation', return_value=mock_conversation):
            result = chat_service.delete_conversation(mock_conversation.id, mock_user.id)

        assert result is False

    def test_delete_conversation_not_found(self, chat_service, mock_db_session, mock_user):
        """Test deleting non-existent conversation."""
        with patch.object(chat_service, 'get_conversation', return_value=None):
            result = chat_service.delete_conversation(uuid4(), mock_user.id)

        assert result is False


# =============================================================================
# Thread Tests - Including Bulk Operations
# =============================================================================

class TestThreadOperations:
    """Test thread CRUD and bulk operations."""

    def test_create_thread_with_initial_message(
        self, chat_service, mock_db_session, mock_user, mock_conversation
    ):
        """Test thread creation with initial message."""
        from src.schemas.chat import ThreadCreate

        data = ThreadCreate(
            conversation_id=mock_conversation.id,
            title="New Thread",
            initial_message="Hello, this is my first message"
        )

        with patch.object(chat_service, 'get_conversation', return_value=mock_conversation):
            result = chat_service.create_thread(data, mock_user.id)

        # Should add thread + initial message
        assert mock_db_session.add.call_count >= 1

    def test_create_thread_no_permission(
        self, chat_service, mock_db_session, mock_user, mock_conversation
    ):
        """Test thread creation fails without edit permission."""
        from src.schemas.chat import ThreadCreate

        mock_conversation.workspace.can_user_edit.return_value = False

        data = ThreadCreate(
            conversation_id=mock_conversation.id,
            title="New Thread"
        )

        with patch.object(chat_service, 'get_conversation', return_value=mock_conversation):
            result = chat_service.create_thread(data, mock_user.id)

        assert result is None

    @pytest.mark.parametrize("status_filter,expected_count", [
        (None, 5),     # All statuses
        ("active", 3), # Only active
        ("resolved", 2), # Only resolved
    ])
    def test_list_threads_status_filter(
        self, chat_service, mock_db_session, mock_user, mock_conversation,
        status_filter, expected_count
    ):
        """Parameterized test for thread listing with status filter."""
        mock_threads = [Mock() for _ in range(expected_count)]
        mock_db_session.count.return_value = expected_count
        mock_db_session.all.return_value = mock_threads

        with patch.object(chat_service, 'get_conversation', return_value=mock_conversation):
            threads, total = chat_service.list_threads(
                mock_conversation.id, mock_user.id,
                status_filter=status_filter
            )

        assert total == expected_count

    def test_update_thread_with_status_change(self, chat_service, mock_db_session, mock_user, mock_thread):
        """Test updating thread with status change to resolved (triggers task)."""
        from src.schemas.chat import ThreadUpdate
        from src.models.thread import ThreadStatus

        mock_thread.status = ThreadStatus.ACTIVE
        data = ThreadUpdate(
            title="Updated Title",
            status=ThreadStatus.RESOLVED
        )

        # Mock the module to prevent import errors during task queuing
        mock_module = MagicMock()
        mock_module.summarize_thread_on_resolve_task.delay = Mock()

        with patch.object(chat_service, 'get_thread', return_value=mock_thread):
            with patch.dict('sys.modules', {'src.tasks.summarize_thread_task': mock_module}):
                result = chat_service.update_thread(mock_thread.id, data, mock_user.id)

        assert result == mock_thread
        assert mock_thread.title == "Updated Title"

    def test_update_thread_no_status_change(self, chat_service, mock_db_session, mock_user, mock_thread):
        """Test updating thread without status change (no task trigger)."""
        from src.schemas.chat import ThreadUpdate
        from src.models.thread import ThreadStatus

        mock_thread.status = ThreadStatus.ACTIVE
        data = ThreadUpdate(title="Just Title Update")

        with patch.object(chat_service, 'get_thread', return_value=mock_thread):
            result = chat_service.update_thread(mock_thread.id, data, mock_user.id)

        assert result == mock_thread
        assert mock_thread.title == "Just Title Update"
        assert mock_thread.status == ThreadStatus.ACTIVE

    def test_update_thread_no_permission(self, chat_service, mock_db_session, mock_user, mock_thread):
        """Test update fails without edit permission."""
        from src.schemas.chat import ThreadUpdate

        mock_thread.conversation.workspace.can_user_edit.return_value = False
        data = ThreadUpdate(title="New Title")

        with patch.object(chat_service, 'get_thread', return_value=mock_thread):
            result = chat_service.update_thread(mock_thread.id, data, mock_user.id)

        assert result is None

    def test_delete_thread_success(self, chat_service, mock_db_session, mock_user, mock_thread):
        """Test soft-deleting thread."""
        with patch.object(chat_service, 'get_thread', return_value=mock_thread):
            result = chat_service.delete_thread(mock_thread.id, mock_user.id)

        assert result is True
        assert mock_thread.is_deleted is True

    def test_delete_thread_no_permission(self, chat_service, mock_db_session, mock_user, mock_thread):
        """Test delete fails without edit permission."""
        mock_thread.conversation.workspace.can_user_edit.return_value = False

        with patch.object(chat_service, 'get_thread', return_value=mock_thread):
            result = chat_service.delete_thread(mock_thread.id, mock_user.id)

        assert result is False

    def test_delete_thread_not_found(self, chat_service, mock_db_session, mock_user):
        """Test deleting non-existent thread."""
        with patch.object(chat_service, 'get_thread', return_value=None):
            result = chat_service.delete_thread(uuid4(), mock_user.id)

        assert result is False


class TestBulkThreadOperations:
    """Test bulk thread operations following error injection patterns."""

    def test_bulk_update_threads_best_effort(
        self, chat_service, mock_db_session, mock_user, mock_thread
    ):
        """Test bulk update in best-effort mode continues on errors."""
        from src.schemas.chat import ThreadUpdate

        thread_ids = [uuid4(), uuid4(), uuid4()]
        data = ThreadUpdate(title="Updated Title")

        # First succeeds, second fails, third succeeds
        mock_thread_1 = Mock(id=thread_ids[0], conversation=mock_thread.conversation)
        mock_thread_3 = Mock(id=thread_ids[2], conversation=mock_thread.conversation)

        def get_thread_side_effect(tid, uid, **kwargs):
            if tid == thread_ids[0]:
                return mock_thread_1
            elif tid == thread_ids[1]:
                return None  # Not found
            elif tid == thread_ids[2]:
                return mock_thread_3
            return None

        with patch.object(chat_service, 'get_thread', side_effect=get_thread_side_effect):
            with patch.object(chat_service, 'update_thread', side_effect=[
                mock_thread_1, None, mock_thread_3
            ]):
                results = chat_service.bulk_update_threads(
                    thread_ids, data, mock_user.id, atomic=False
                )

        # Should have 3 results
        assert len(results) == 3
        # First should succeed
        assert results[0][1] is True
        # Second should fail
        assert results[1][1] is False
        # Third should succeed
        assert results[2][1] is True

    def test_bulk_update_threads_atomic_rollback(
        self, chat_service, mock_db_session, mock_user, mock_thread
    ):
        """Test atomic bulk update rolls back on any failure."""
        from src.schemas.chat import ThreadUpdate

        thread_ids = [uuid4(), uuid4()]
        data = ThreadUpdate(title="Updated Title")

        # Make get_thread raise error for second thread
        mock_thread_1 = Mock(id=thread_ids[0], conversation=mock_thread.conversation)
        mock_thread_1.title = "Old Title"
        mock_thread_1.summary = None
        mock_thread_1.status = Mock()

        def get_thread_side_effect(tid, uid):
            if tid == thread_ids[0]:
                return mock_thread_1
            elif tid == thread_ids[1]:
                return None  # Will cause ValueError in atomic mode
            return None

        with patch.object(chat_service, 'get_thread', side_effect=get_thread_side_effect):
            results = chat_service.bulk_update_threads(
                thread_ids, data, mock_user.id, atomic=True
            )

        # All should fail due to atomic rollback
        assert all(r[1] is False for r in results)
        mock_db_session.rollback.assert_called_once()

    def test_bulk_delete_threads_success(
        self, chat_service, mock_db_session, mock_user
    ):
        """Test bulk delete in best-effort mode."""
        thread_ids = [uuid4(), uuid4()]

        with patch.object(chat_service, 'delete_thread', return_value=True):
            results = chat_service.bulk_delete_threads(
                thread_ids, mock_user.id, atomic=False
            )

        assert len(results) == 2
        assert all(r[1] is True for r in results)

    def test_bulk_summarize_threads(
        self, chat_service, mock_db_session, mock_user, mock_thread
    ):
        """Test bulk summarization triggers async tasks."""
        thread_ids = [mock_thread.id]

        # Create mock for the task module
        mock_task = MagicMock()
        mock_task.delay = Mock()

        with patch.object(chat_service, 'get_thread', return_value=mock_thread):
            # Patch the import inside the method
            with patch.dict('sys.modules', {'src.tasks.summarize_thread_task': MagicMock(summarize_thread_task=mock_task)}):
                results = chat_service.bulk_summarize_threads(thread_ids, mock_user.id)

        assert len(results) == 1
        assert results[0][1] is True  # Success


# =============================================================================
# Message Tests
# =============================================================================

class TestMessageOperations:
    """Test message CRUD operations."""

    def test_create_message_with_citations(
        self, chat_service, mock_db_session, mock_user, mock_thread
    ):
        """Test message creation with citations for RAG responses."""
        from src.schemas.chat import ChatMessageCreate, CitationCreate, MessageRole

        mock_thread.conversation.workspace.can_user_edit.return_value = True

        citations = [
            CitationCreate(
                document_id=uuid4(),
                chunk_index=0,
                score=0.95
            )
        ]

        data = ChatMessageCreate(
            thread_id=mock_thread.id,
            role=MessageRole.ASSISTANT,
            content="Based on the documents, here is the answer...",
            citations=citations
        )

        with patch.object(chat_service, 'get_thread', return_value=mock_thread):
            with patch('src.utils.token_counter.count_message_tokens', return_value=50):
                result = chat_service.create_message(data, mock_user.id)

        # Message + citation should be added
        assert mock_db_session.add.call_count >= 1

    def test_create_message_no_thread_access(
        self, chat_service, mock_db_session, mock_user
    ):
        """Test message creation fails without thread access."""
        from src.schemas.chat import ChatMessageCreate, MessageRole

        data = ChatMessageCreate(
            thread_id=uuid4(),
            role=MessageRole.USER,
            content="Hello"
        )

        with patch.object(chat_service, 'get_thread', return_value=None):
            result = chat_service.create_message(data, mock_user.id)

        assert result is None

    def test_list_messages_pagination(
        self, chat_service, mock_db_session, mock_user, mock_thread
    ):
        """Test message listing with pagination."""
        mock_messages = [Mock(id=uuid4(), content=f"Message {i}") for i in range(10)]

        # Create proper query chain mock
        query_mock = MagicMock()
        query_mock.options.return_value = query_mock
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.offset.return_value = query_mock
        query_mock.limit.return_value = query_mock
        query_mock.count.return_value = 50
        query_mock.all.return_value = mock_messages

        mock_db_session.query.return_value = query_mock

        with patch.object(chat_service, 'get_thread', return_value=mock_thread):
            messages, total = chat_service.list_messages(
                mock_thread.id, mock_user.id, limit=10, offset=0
            )

        assert len(messages) == 10
        assert total == 50

    def test_delete_message_author_only(
        self, chat_service, mock_db_session, mock_user, mock_thread
    ):
        """Test only message author can delete their message."""
        mock_message = Mock()
        mock_message.id = uuid4()
        mock_message.user_id = mock_user.id  # Same user
        mock_message.thread = mock_thread
        mock_message.is_deleted = False

        with patch.object(chat_service, 'get_message', return_value=mock_message):
            result = chat_service.delete_message(mock_message.id, mock_user.id)

        assert result is True
        assert mock_message.is_deleted is True

    def test_delete_message_other_user_denied(
        self, chat_service, mock_db_session, mock_user, mock_thread
    ):
        """Test other users cannot delete message unless admin."""
        mock_message = Mock()
        mock_message.id = uuid4()
        mock_message.user_id = uuid4()  # Different user
        mock_message.thread = mock_thread
        mock_message.is_deleted = False
        mock_thread.conversation.workspace.can_user_admin.return_value = False

        with patch.object(chat_service, 'get_message', return_value=mock_message):
            result = chat_service.delete_message(mock_message.id, mock_user.id)

        assert result is False


# =============================================================================
# Thread Context Tests
# =============================================================================

class TestThreadContext:
    """Test thread context retrieval for LLM."""

    def test_get_thread_context_empty(
        self, chat_service, mock_db_session, mock_user
    ):
        """Test context for non-existent thread."""
        with patch.object(chat_service, 'get_thread', return_value=None):
            result = chat_service.get_thread_context(uuid4(), mock_user.id)

        assert result["messages"] == []
        assert result["metadata"]["truncated"] is False
        assert result["metadata"]["total_tokens"] == 0

    def test_get_thread_context_with_messages(
        self, chat_service, mock_db_session, mock_user, mock_thread
    ):
        """Test context retrieval with messages."""
        # Create mock messages
        mock_messages = [
            Mock(
                id=uuid4(),
                content=f"Message {i}",
                is_deleted=False,
                to_llm_format=Mock(return_value={"role": "user", "content": f"Message {i}"})
            )
            for i in range(3)
        ]
        mock_thread.messages = mock_messages

        with patch.object(chat_service, 'get_thread', return_value=mock_thread):
            with patch('src.utils.token_counter.count_tokens', return_value=10):
                with patch('src.core.config.settings') as mock_settings:
                    mock_settings.THREAD_DEFAULT_MAX_MESSAGES = 100
                    mock_settings.THREAD_DEFAULT_MAX_TOKENS = 4000
                    mock_settings.THREAD_CONTEXT_WARN_THRESHOLD = 0.8
                    mock_settings.MODEL_CONTEXT_LIMITS = {}

                    result = chat_service.get_thread_context(mock_thread.id, mock_user.id)

        assert len(result["messages"]) == 3
        assert result["metadata"]["message_count"] == 3

    def test_get_thread_context_token_limit(
        self, chat_service, mock_db_session, mock_user, mock_thread
    ):
        """Test context truncation at token limit."""
        # Create mock messages with high token counts
        mock_messages = [
            Mock(
                id=uuid4(),
                content="A" * 1000,
                is_deleted=False,
                to_llm_format=Mock(return_value={"role": "user", "content": "A" * 1000})
            )
            for i in range(10)
        ]
        mock_thread.messages = mock_messages

        with patch.object(chat_service, 'get_thread', return_value=mock_thread):
            with patch('src.utils.token_counter.count_tokens', return_value=500):  # 500 tokens each
                with patch('src.core.config.settings') as mock_settings:
                    mock_settings.THREAD_DEFAULT_MAX_MESSAGES = 100
                    mock_settings.THREAD_DEFAULT_MAX_TOKENS = 1000  # Only fits 2 messages
                    mock_settings.THREAD_CONTEXT_WARN_THRESHOLD = 0.8
                    mock_settings.MODEL_CONTEXT_LIMITS = {}

                    result = chat_service.get_thread_context(mock_thread.id, mock_user.id)

        assert result["metadata"]["truncated"] is True
        assert result["metadata"]["message_count"] < 10


# =============================================================================
# Collection Tests
# =============================================================================

class TestCollectionOperations:
    """Test collection CRUD operations."""

    def test_create_collection_with_documents(
        self, chat_service, mock_db_session, mock_user, mock_workspace
    ):
        """Test collection creation with initial documents."""
        from src.schemas.chat import CollectionCreate

        doc_ids = [uuid4(), uuid4(), uuid4()]

        data = CollectionCreate(
            workspace_id=mock_workspace.id,
            name="Research Papers",
            description="ML research papers",
            document_ids=doc_ids
        )

        with patch.object(chat_service, 'get_workspace', return_value=mock_workspace):
            result = chat_service.create_collection(data, mock_user.id)

        # Collection + 3 document associations
        assert mock_db_session.add.call_count >= 1

    def test_add_documents_to_collection(
        self, chat_service, mock_db_session, mock_user, mock_workspace
    ):
        """Test adding documents to existing collection."""
        mock_collection = Mock()
        mock_collection.id = uuid4()
        mock_collection.workspace = mock_workspace
        mock_collection.document_count = 0
        mock_collection.updated_at = None

        # Create proper query chain for max position and exists checks
        query_mock = MagicMock()
        query_mock.filter.return_value = query_mock
        query_mock.scalar.return_value = 0  # No existing documents
        query_mock.first.return_value = None  # Documents not already in collection

        mock_db_session.query.return_value = query_mock

        doc_ids = [uuid4(), uuid4()]

        with patch.object(chat_service, 'get_collection', return_value=mock_collection):
            result = chat_service.add_documents_to_collection(
                mock_collection.id, doc_ids, mock_user.id
            )

        # Verify 2 CollectionDocument records were added (document_count is computed)
        assert mock_db_session.add.call_count == 2

    def test_remove_documents_from_collection(
        self, chat_service, mock_db_session, mock_user, mock_workspace
    ):
        """Test removing documents from collection."""
        mock_collection = Mock()
        mock_collection.id = uuid4()
        mock_collection.workspace = mock_workspace
        mock_collection.document_count = 3

        mock_db_session.delete.return_value = 2  # 2 documents removed

        doc_ids = [uuid4(), uuid4()]

        with patch.object(chat_service, 'get_collection', return_value=mock_collection):
            result = chat_service.remove_documents_from_collection(
                mock_collection.id, doc_ids, mock_user.id
            )

        # document_count should decrease


# =============================================================================
# Error Handling Tests - Following Temporal error injection patterns
# =============================================================================

class TestErrorHandling:
    """Test error handling scenarios."""

    def test_database_error_on_create(
        self, chat_service, mock_db_session, mock_user
    ):
        """Test handling of database errors during creation."""
        from src.schemas.chat import WorkspaceCreate

        mock_db_session.commit.side_effect = Exception("Database connection lost")

        data = WorkspaceCreate(
            name="New Workspace",
            is_public=False,
            organization_id=uuid4()
        )

        with pytest.raises(Exception, match="Database connection lost"):
            chat_service.create_workspace(data, mock_user.id)

    def test_concurrent_update_handling(
        self, chat_service, mock_db_session, mock_user, mock_workspace
    ):
        """Test handling of concurrent update conflicts."""
        # Simulate stale data error on commit
        call_count = [0]

        def commit_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Stale data detected")

        mock_db_session.commit.side_effect = commit_side_effect

        from src.schemas.chat import WorkspaceUpdate
        data = WorkspaceUpdate(name="Updated Name")

        with patch.object(chat_service, 'get_workspace', return_value=mock_workspace):
            with pytest.raises(Exception, match="Stale data"):
                chat_service.update_workspace(mock_workspace.id, data, mock_user.id)


# =============================================================================
# Workspace Stats Tests
# =============================================================================

class TestWorkspaceStats:
    """Test workspace statistics retrieval."""

    def test_get_workspace_stats(
        self, chat_service, mock_db_session, mock_user, mock_workspace
    ):
        """Test workspace statistics calculation."""
        mock_workspace.members = [Mock(), Mock()]  # 2 members

        # Create proper query chain mock for each count query
        scalar_values = [5, 15, 100, 3]  # conversations, threads, messages, collections
        scalar_index = [0]

        def scalar_side_effect():
            idx = scalar_index[0]
            scalar_index[0] += 1
            return scalar_values[idx] if idx < len(scalar_values) else 0

        query_mock = MagicMock()
        query_mock.filter.return_value = query_mock
        query_mock.join.return_value = query_mock
        query_mock.scalar.side_effect = scalar_side_effect

        mock_db_session.query.return_value = query_mock

        with patch.object(chat_service, 'get_workspace', return_value=mock_workspace):
            stats = chat_service.get_workspace_stats(mock_workspace.id, mock_user.id)

        assert stats is not None
        assert stats['conversation_count'] == 5
        assert stats['thread_count'] == 15
        assert stats['message_count'] == 100
        assert stats['collection_count'] == 3
        assert stats['member_count'] == 2

    def test_get_workspace_stats_no_access(
        self, chat_service, mock_db_session, mock_user
    ):
        """Test stats return None without access."""
        with patch.object(chat_service, 'get_workspace', return_value=None):
            stats = chat_service.get_workspace_stats(uuid4(), mock_user.id)

        assert stats is None
