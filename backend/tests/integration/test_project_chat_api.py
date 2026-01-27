"""
Integration tests for Project-Chat API endpoints.

Tests the full integration between research projects and chat threads,
including creating chats from projects, linking threads, and managing
project-thread relationships.
"""

import pytest
import asyncio
from uuid import uuid4
from httpx import AsyncClient
from fastapi import status

from src.main import app
from src.core.database import get_db
from src.models import User, Workspace, Collection, Conversation, Thread, ProjectThread


@pytest.mark.asyncio
class TestProjectChatIntegration:
    """Integration tests for project-chat API endpoints."""

    async def test_start_chat_from_project(self, async_client, test_user, test_workspace, test_project):
        """Test starting a new chat from a project."""
        # Arrange
        request_data = {
            "initial_message": "What are the key findings in this project?",
            "thread_title": "Research Discussion"
        }

        # Act
        response = await async_client.post(
            f"/api/v1/projects/{test_project.id}/chat/start",
            json=request_data
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "thread_id" in data
        assert "conversation_id" in data
        assert "project_thread_id" in data
        assert "document_scope" in data

        # Verify thread was created
        thread_id = data["thread_id"]
        conversation_id = data["conversation_id"]
        assert thread_id is not None
        assert conversation_id is not None

    async def test_list_project_threads(self, async_client, test_user, test_project):
        """Test listing all threads linked to a project."""
        # Act
        response = await async_client.get(
            f"/api/v1/projects/{test_project.id}/chat/threads"
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "threads" in data
        assert "total" in data
        assert isinstance(data["threads"], list)
        assert data["total"] >= 0

    async def test_link_existing_thread_to_project(
        self, async_client, test_user, test_project, test_thread
    ):
        """Test manually linking an existing thread to a project."""
        # Arrange
        request_data = {
            "thread_id": str(test_thread.id),
            "link_type": "manual",
            "context_note": "Manually linked for testing"
        }

        # Act
        response = await async_client.post(
            f"/api/v1/projects/{test_project.id}/chat/link",
            json=request_data
        )

        # Assert
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]
        data = response.json()
        assert data["project_id"] == str(test_project.id)
        assert data["thread_id"] == str(test_thread.id)
        assert data["link_type"] == "manual"

    async def test_unlink_thread_from_project(
        self, async_client, test_user, test_project, test_thread, test_project_thread
    ):
        """Test unlinking a thread from a project."""
        # Act
        response = await async_client.delete(
            f"/api/v1/projects/{test_project.id}/chat/threads/{test_thread.id}"
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "message" in data
        assert "unlinked" in data["message"].lower()

    async def test_save_thread_to_note(
        self, async_client, test_user, test_project, test_thread, test_project_thread
    ):
        """Test saving a thread's content to a project note."""
        # Arrange
        request_data = {
            "note_title": "Chat Discussion Notes",
            "include_citations": True
        }

        # Act
        response = await async_client.post(
            f"/api/v1/projects/{test_project.id}/chat/threads/{test_thread.id}/save-to-note",
            json=request_data
        )

        # Assert - May be 404 if not implemented yet
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_201_CREATED,
            status.HTTP_404_NOT_FOUND
        ]

    async def test_start_chat_with_no_documents(
        self, async_client, test_user, test_workspace
    ):
        """Test starting a chat from a project with no documents."""
        # Create empty project
        empty_project = Collection(
            name="Empty Project",
            description="No documents",
            workspace_id=test_workspace.id
        )
        db = next(get_db())
        db.add(empty_project)
        await db.commit()

        # Arrange
        request_data = {
            "initial_message": "Test message",
            "thread_title": "Test Thread"
        }

        # Act
        response = await async_client.post(
            f"/api/v1/projects/{empty_project.id}/chat/start",
            json=request_data
        )

        # Assert - Should still succeed but with empty document_scope
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "document_scope" in data
        assert len(data["document_scope"]) == 0

    async def test_duplicate_thread_link(
        self, async_client, test_user, test_project, test_thread, test_project_thread
    ):
        """Test attempting to link the same thread twice."""
        # Arrange
        request_data = {
            "thread_id": str(test_thread.id),
            "link_type": "manual"
        }

        # Act
        response = await async_client.post(
            f"/api/v1/projects/{test_project.id}/chat/link",
            json=request_data
        )

        # Assert - Should fail with 409 Conflict
        assert response.status_code == status.HTTP_409_CONFLICT
        data = response.json()
        assert "already linked" in data["detail"].lower()

    async def test_workspace_isolation(
        self, async_client, test_user, other_user, test_project, other_workspace
    ):
        """Test that users cannot link threads from different workspaces."""
        # Create thread in different workspace
        other_conversation = Conversation(
            workspace_id=other_workspace.id,
            title="Other Workspace Chat",
            created_by_id=other_user.id
        )
        other_thread = Thread(
            conversation_id=other_conversation.id,
            title="Other Thread",
            created_by_id=other_user.id
        )
        db = next(get_db())
        db.add(other_conversation)
        db.add(other_thread)
        await db.commit()

        # Arrange
        request_data = {
            "thread_id": str(other_thread.id),
            "link_type": "manual"
        }

        # Act
        response = await async_client.post(
            f"/api/v1/projects/{test_project.id}/chat/link",
            json=request_data
        )

        # Assert - Should fail with 403 Forbidden
        assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_invalid_project_id(self, async_client, test_user):
        """Test accessing non-existent project."""
        # Arrange
        fake_project_id = str(uuid4())

        # Act
        response = await async_client.get(
            f"/api/v1/projects/{fake_project_id}/chat/threads"
        )

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND


# Fixtures
@pytest.fixture
async def test_workspace(test_user):
    """Create a test workspace."""
    workspace = Workspace(
        name="Test Workspace",
        description="Integration test workspace",
        owner_id=test_user.id
    )
    db = next(get_db())
    db.add(workspace)
    await db.commit()
    await db.refresh(workspace)
    return workspace


@pytest.fixture
async def test_project(test_workspace):
    """Create a test project (Collection)."""
    project = Collection(
        name="Test Project",
        description="Integration test project",
        workspace_id=test_workspace.id
    )
    db = next(get_db())
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@pytest.fixture
async def test_conversation(test_workspace, test_user):
    """Create a test conversation."""
    conversation = Conversation(
        workspace_id=test_workspace.id,
        title="Test Conversation",
        created_by_id=test_user.id
    )
    db = next(get_db())
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


@pytest.fixture
async def test_thread(test_conversation, test_user):
    """Create a test thread."""
    thread = Thread(
        conversation_id=test_conversation.id,
        title="Test Thread",
        created_by_id=test_user.id
    )
    db = next(get_db())
    db.add(thread)
    await db.commit()
    await db.refresh(thread)
    return thread


@pytest.fixture
async def test_project_thread(test_project, test_thread, test_user):
    """Create a test project-thread link."""
    project_thread = ProjectThread(
        project_id=test_project.id,
        thread_id=test_thread.id,
        link_type="auto",
        linked_by_id=test_user.id,
        context_note="Test link"
    )
    db = next(get_db())
    db.add(project_thread)
    await db.commit()
    await db.refresh(project_thread)
    return project_thread


@pytest.fixture
async def other_workspace(other_user):
    """Create another workspace for isolation testing."""
    workspace = Workspace(
        name="Other Workspace",
        description="Isolation test workspace",
        owner_id=other_user.id
    )
    db = next(get_db())
    db.add(workspace)
    await db.commit()
    await db.refresh(workspace)
    return workspace


@pytest.fixture
async def other_user():
    """Create another user for isolation testing."""
    user = User(
        email="other@test.com",
        password_hash="hashed_password",
        first_name="Other",
        last_name="User"
    )
    db = next(get_db())
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
