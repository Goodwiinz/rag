"""
Chat Repository Integration Tests

Tests for the chat hierarchy (Workspace -> Conversation -> Thread -> Message)
with real PostgreSQL database to validate:
- Cascade deletes through hierarchy
- Message ordering by created_at
- Thread status transitions
- Bulk operations with transactions
"""

import pytest
import uuid
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

# Mark all tests in this module
pytestmark = [
    pytest.mark.requires_postgres,
    pytest.mark.integration,
]


@pytest.fixture(scope="function")
def db_session(postgres_container):
    """Create a database session with all chat-related tables."""
    from src.models.base import Base
    from src.models.user import User, UserRole
    from src.models.organization import Organization, StorageTier
    from src.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
    from src.models.conversation import Conversation
    from src.models.thread import Thread, ThreadStatus
    from src.models.chat_message import ChatMessage, MessageRole
    # Import ab_testing to resolve User -> Experiment relationship
    from src.models import ab_testing  # noqa: F401

    engine = create_engine(postgres_container["url"])
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        yield session
    finally:
        session.rollback()
        session.close()
        # Drop tables with CASCADE to handle circular dependencies in ab_testing
        with engine.connect() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
            conn.commit()
        engine.dispose()


@pytest.fixture
def test_organization(db_session):
    """Create a test organization."""
    from src.models.organization import Organization, StorageTier

    org = Organization(
        id=uuid.uuid4(),
        name=f"Chat Test Org {uuid.uuid4().hex[:8]}",
        storage_tier=StorageTier.PROFESSIONAL,
        storage_limit_bytes=100 * 1024 ** 3,
        is_active=True,
    )
    db_session.add(org)
    db_session.commit()
    return org


@pytest.fixture
def test_user(db_session, test_organization):
    """Create a test user."""
    from src.models.user import User, UserRole
    from src.core.security import get_password_hash

    user = User(
        id=uuid.uuid4(),
        email=f"chatuser-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=get_password_hash("password123"),
        first_name="Chat",
        last_name="User",
        role=UserRole.USER,
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def test_workspace(db_session, test_user, test_organization):
    """Create a test workspace."""
    from src.models.workspace import Workspace

    workspace = Workspace(
        id=uuid.uuid4(),
        name="Test Workspace",
        description="A workspace for chat integration tests",
        owner_id=test_user.id,
        organization_id=test_organization.id,
        is_archived=False,
        is_public=False,
    )
    db_session.add(workspace)
    db_session.commit()
    return workspace


@pytest.fixture
def test_conversation(db_session, test_workspace, test_user):
    """Create a test conversation."""
    from src.models.conversation import Conversation

    conversation = Conversation(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        title="Test Conversation",
        description="A conversation for testing",
        created_by_id=test_user.id,
        is_archived=False,
        is_pinned=False,
    )
    db_session.add(conversation)
    db_session.commit()
    return conversation


class TestChatHierarchy:
    """Tests for workspace -> conversation -> thread -> message hierarchy."""

    def test_workspace_conversation_thread_hierarchy(
        self, db_session, test_workspace, test_conversation, test_user
    ):
        """Verify the complete chat hierarchy can be created."""
        from src.models.thread import Thread, ThreadStatus
        from src.models.chat_message import ChatMessage, MessageRole

        # Create thread
        thread = Thread(
            id=uuid.uuid4(),
            conversation_id=test_conversation.id,
            title="Test Thread",
            status=ThreadStatus.ACTIVE,
            created_by_id=test_user.id,
        )
        db_session.add(thread)
        db_session.commit()

        # Create messages
        user_msg = ChatMessage(
            id=uuid.uuid4(),
            thread_id=thread.id,
            user_id=test_user.id,
            role=MessageRole.USER,
            content="Hello, this is a test message.",
            token_count=10,
        )

        assistant_msg = ChatMessage(
            id=uuid.uuid4(),
            thread_id=thread.id,
            role=MessageRole.ASSISTANT,
            content="Hello! How can I help you today?",
            model_name="gpt-4",
            token_count=12,
            latency_ms=250,
        )

        db_session.add_all([user_msg, assistant_msg])
        db_session.commit()

        # Verify hierarchy
        saved_workspace = db_session.query(type(test_workspace)).filter_by(id=test_workspace.id).first()
        assert len(saved_workspace.conversations) == 1

        saved_conversation = saved_workspace.conversations[0]
        assert len(saved_conversation.threads) == 1

        saved_thread = saved_conversation.threads[0]
        assert len(saved_thread.messages) == 2


class TestCascadeDeletes:
    """Tests for cascade delete behavior through hierarchy."""

    def test_deleting_workspace_cascades_to_conversations(
        self, db_session, test_workspace, test_user
    ):
        """Verify deleting workspace cascades to conversations."""
        from src.models.conversation import Conversation

        # Create multiple conversations
        conv_ids = []
        for i in range(3):
            conv = Conversation(
                id=uuid.uuid4(),
                workspace_id=test_workspace.id,
                title=f"Conversation {i}",
                created_by_id=test_user.id,
            )
            db_session.add(conv)
            conv_ids.append(conv.id)

        db_session.commit()

        # Delete workspace
        db_session.delete(test_workspace)
        db_session.commit()

        # Verify conversations were cascade deleted
        remaining = db_session.query(Conversation).filter(
            Conversation.id.in_(conv_ids)
        ).all()
        assert len(remaining) == 0

    def test_deleting_conversation_cascades_to_threads(
        self, db_session, test_conversation, test_user
    ):
        """Verify deleting conversation cascades to threads."""
        from src.models.thread import Thread, ThreadStatus
        from src.models.conversation import Conversation

        # Create threads
        thread_ids = []
        for i in range(3):
            thread = Thread(
                id=uuid.uuid4(),
                conversation_id=test_conversation.id,
                title=f"Thread {i}",
                status=ThreadStatus.ACTIVE,
                created_by_id=test_user.id,
            )
            db_session.add(thread)
            thread_ids.append(thread.id)

        db_session.commit()

        # Delete conversation
        db_session.delete(test_conversation)
        db_session.commit()

        # Verify threads were cascade deleted
        remaining = db_session.query(Thread).filter(Thread.id.in_(thread_ids)).all()
        assert len(remaining) == 0

    def test_deleting_thread_cascades_to_messages(
        self, db_session, test_conversation, test_user
    ):
        """Verify deleting thread cascades to messages."""
        from src.models.thread import Thread, ThreadStatus
        from src.models.chat_message import ChatMessage, MessageRole

        thread = Thread(
            id=uuid.uuid4(),
            conversation_id=test_conversation.id,
            title="Thread to Delete",
            status=ThreadStatus.ACTIVE,
            created_by_id=test_user.id,
        )
        db_session.add(thread)
        db_session.commit()

        # Create messages
        msg_ids = []
        for i in range(5):
            msg = ChatMessage(
                id=uuid.uuid4(),
                thread_id=thread.id,
                role=MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT,
                content=f"Message {i}",
                user_id=test_user.id if i % 2 == 0 else None,
            )
            db_session.add(msg)
            msg_ids.append(msg.id)

        db_session.commit()

        # Delete thread
        db_session.delete(thread)
        db_session.commit()

        # Verify messages were cascade deleted
        remaining = db_session.query(ChatMessage).filter(
            ChatMessage.id.in_(msg_ids)
        ).all()
        assert len(remaining) == 0


class TestMessageOrdering:
    """Tests for message ordering within threads."""

    def test_message_ordering_by_created_at(self, db_session, test_conversation, test_user):
        """Verify messages are ordered by created_at timestamp."""
        from src.models.thread import Thread, ThreadStatus
        from src.models.chat_message import ChatMessage, MessageRole

        thread = Thread(
            id=uuid.uuid4(),
            conversation_id=test_conversation.id,
            title="Ordering Test Thread",
            status=ThreadStatus.ACTIVE,
            created_by_id=test_user.id,
        )
        db_session.add(thread)
        db_session.commit()

        # Create messages with explicit timestamps
        base_time = datetime.utcnow()
        messages = []
        for i in range(5):
            msg = ChatMessage(
                id=uuid.uuid4(),
                thread_id=thread.id,
                role=MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT,
                content=f"Message {i}",
                created_at=base_time + timedelta(seconds=i * 10),
            )
            messages.append(msg)

        # Add messages in random order
        import random
        shuffled = messages.copy()
        random.shuffle(shuffled)
        db_session.add_all(shuffled)
        db_session.commit()

        # Query thread and check message order
        saved_thread = db_session.query(Thread).filter_by(id=thread.id).first()

        # Messages should be ordered by created_at (relationship has order_by)
        for i, msg in enumerate(saved_thread.messages):
            assert msg.content == f"Message {i}"


class TestThreadStatus:
    """Tests for thread status transitions."""

    def test_thread_status_transitions(self, db_session, test_conversation, test_user):
        """Verify thread status can transition between states."""
        from src.models.thread import Thread, ThreadStatus

        thread = Thread(
            id=uuid.uuid4(),
            conversation_id=test_conversation.id,
            title="Status Test Thread",
            status=ThreadStatus.ACTIVE,
            created_by_id=test_user.id,
        )
        db_session.add(thread)
        db_session.commit()

        # Initial state
        assert thread.status == ThreadStatus.ACTIVE
        assert thread.is_active is True
        assert thread.is_resolved is False

        # Resolve thread
        thread.resolve()
        db_session.commit()

        saved_thread = db_session.query(Thread).filter_by(id=thread.id).first()
        assert saved_thread.status == ThreadStatus.RESOLVED
        assert saved_thread.is_active is False
        assert saved_thread.is_resolved is True

        # Reopen thread
        saved_thread.reopen()
        db_session.commit()

        reopened_thread = db_session.query(Thread).filter_by(id=thread.id).first()
        assert reopened_thread.status == ThreadStatus.ACTIVE

        # Archive thread
        reopened_thread.archive()
        db_session.commit()

        archived_thread = db_session.query(Thread).filter_by(id=thread.id).first()
        assert archived_thread.status == ThreadStatus.ARCHIVED


class TestBulkOperations:
    """Tests for bulk operations with transactions."""

    def test_bulk_thread_archive_transaction(self, db_session, test_conversation, test_user):
        """Verify bulk thread archiving works atomically."""
        from src.models.thread import Thread, ThreadStatus

        # Create multiple threads
        threads = []
        for i in range(5):
            thread = Thread(
                id=uuid.uuid4(),
                conversation_id=test_conversation.id,
                title=f"Bulk Thread {i}",
                status=ThreadStatus.ACTIVE,
                created_by_id=test_user.id,
            )
            threads.append(thread)

        db_session.add_all(threads)
        db_session.commit()

        thread_ids = [t.id for t in threads]

        # Bulk archive
        db_session.query(Thread).filter(
            Thread.id.in_(thread_ids)
        ).update(
            {Thread.status: ThreadStatus.ARCHIVED},
            synchronize_session="fetch"
        )
        db_session.commit()

        # Verify all threads archived
        archived_threads = db_session.query(Thread).filter(
            Thread.id.in_(thread_ids),
            Thread.status == ThreadStatus.ARCHIVED
        ).all()
        assert len(archived_threads) == 5

    def test_bulk_message_creation_transaction(
        self, db_session, test_conversation, test_user
    ):
        """Verify bulk message creation is atomic."""
        from src.models.thread import Thread, ThreadStatus
        from src.models.chat_message import ChatMessage, MessageRole

        thread = Thread(
            id=uuid.uuid4(),
            conversation_id=test_conversation.id,
            title="Bulk Message Thread",
            status=ThreadStatus.ACTIVE,
            created_by_id=test_user.id,
        )
        db_session.add(thread)
        db_session.commit()

        # Create 100 messages in bulk
        messages = []
        for i in range(100):
            msg = ChatMessage(
                id=uuid.uuid4(),
                thread_id=thread.id,
                role=MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT,
                content=f"Bulk message {i}",
            )
            messages.append(msg)

        db_session.add_all(messages)
        db_session.commit()

        # Verify all messages created
        message_count = db_session.query(ChatMessage).filter_by(
            thread_id=thread.id
        ).count()
        assert message_count == 100

    def test_transaction_rollback_on_error(self, db_session, test_conversation, test_user):
        """Verify transaction rollback on error."""
        from src.models.thread import Thread, ThreadStatus
        from src.models.chat_message import ChatMessage, MessageRole

        thread = Thread(
            id=uuid.uuid4(),
            conversation_id=test_conversation.id,
            title="Rollback Test Thread",
            status=ThreadStatus.ACTIVE,
            created_by_id=test_user.id,
        )
        db_session.add(thread)
        db_session.commit()

        thread_id = thread.id

        try:
            # Create some messages
            for i in range(3):
                msg = ChatMessage(
                    id=uuid.uuid4(),
                    thread_id=thread_id,
                    role=MessageRole.USER,
                    content=f"Message {i}",
                )
                db_session.add(msg)

            # Try to create message with invalid thread_id (should fail)
            invalid_msg = ChatMessage(
                id=uuid.uuid4(),
                thread_id=uuid.uuid4(),  # Non-existent thread
                role=MessageRole.USER,
                content="Invalid message",
            )
            db_session.add(invalid_msg)
            db_session.commit()  # This should fail
        except IntegrityError:
            db_session.rollback()

        # Verify no messages were created (rollback worked)
        message_count = db_session.query(ChatMessage).filter_by(
            thread_id=thread_id
        ).count()
        assert message_count == 0


class TestWorkspaceMembers:
    """Tests for workspace membership."""

    def test_workspace_member_roles(self, db_session, test_workspace, test_user, test_organization):
        """Verify workspace member role assignments."""
        from src.models.workspace import WorkspaceMember, WorkspaceRole
        from src.models.user import User, UserRole
        from src.core.security import get_password_hash

        # Create additional users
        editor = User(
            id=uuid.uuid4(),
            email=f"editor-{uuid.uuid4().hex[:8]}@example.com",
            password_hash=get_password_hash("password"),
            first_name="Editor",
            last_name="User",
            role=UserRole.USER,
            organization_id=test_organization.id,
        )
        viewer = User(
            id=uuid.uuid4(),
            email=f"viewer-{uuid.uuid4().hex[:8]}@example.com",
            password_hash=get_password_hash("password"),
            first_name="Viewer",
            last_name="User",
            role=UserRole.USER,
            organization_id=test_organization.id,
        )
        db_session.add_all([editor, viewer])
        db_session.commit()

        # Add members with different roles
        editor_member = WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=test_workspace.id,
            user_id=editor.id,
            role=WorkspaceRole.EDITOR,
            invited_by_id=test_user.id,
        )
        viewer_member = WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=test_workspace.id,
            user_id=viewer.id,
            role=WorkspaceRole.VIEWER,
            invited_by_id=test_user.id,
        )
        db_session.add_all([editor_member, viewer_member])
        db_session.commit()

        # Verify roles
        saved_workspace = db_session.query(type(test_workspace)).filter_by(
            id=test_workspace.id
        ).first()

        assert saved_workspace.is_member(str(editor.id))
        assert saved_workspace.is_member(str(viewer.id))

        editor_role = saved_workspace.get_member_role(str(editor.id))
        assert editor_role == WorkspaceRole.EDITOR

        viewer_role = saved_workspace.get_member_role(str(viewer.id))
        assert viewer_role == WorkspaceRole.VIEWER

        # Editor can edit, viewer cannot
        assert saved_workspace.can_user_edit(str(editor.id))
        assert not saved_workspace.can_user_edit(str(viewer.id))
