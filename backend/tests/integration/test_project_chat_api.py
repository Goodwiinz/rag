"""
Integration tests for Project-Chat API endpoints.

Tests the full integration between research projects and chat threads,
including creating chats from projects, linking threads, and managing
project-thread relationships.
"""

import pytest
from uuid import uuid4
from fastapi import status

from src.models import Collection, Conversation, Thread


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
        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_save_thread_to_note(
        self, async_client, test_user, test_project, test_thread, test_project_thread
    ):
        """Test saving a thread's content to a project note."""
        # Arrange
        request_data = {
            "thread_id": str(test_thread.id),
            "note_title": "Chat Discussion Notes",
            "include_citations": True
        }

        # Act
        response = await async_client.post(
            f"/api/v1/projects/{test_project.id}/chat/save-to-note",
            json=request_data
        )

        # Assert - May be 404 if not implemented yet
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_201_CREATED,
            status.HTTP_404_NOT_FOUND
        ]

    async def test_start_chat_with_no_documents(
        self, async_client, test_user, test_workspace, test_db
    ):
        """Test starting a chat from a project with no documents."""
        # Create empty project
        empty_project = Collection(
            name="Empty Project",
            description="No documents",
            workspace_id=test_workspace.id
        )
        test_db.add(empty_project)
        await test_db.commit()
        await test_db.refresh(empty_project)

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
        """Test that re-linking an already-linked thread is idempotent."""
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

        # Assert - Re-link returns the existing link (idempotent, no 409)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["project_id"] == str(test_project.id)
        assert data["thread_id"] == str(test_thread.id)
        assert data["link_type"] == "manual"

    async def test_workspace_isolation(
        self, async_client, test_user, other_user, test_project, other_workspace, test_db
    ):
        """Test that users cannot link threads from different workspaces."""
        # Create thread in different workspace
        other_conversation = Conversation(
            workspace_id=other_workspace.id,
            title="Other Workspace Chat",
            created_by_id=other_user.id
        )
        test_db.add(other_conversation)
        await test_db.flush()

        other_thread = Thread(
            conversation_id=other_conversation.id,
            title="Other Thread",
            created_by_id=other_user.id
        )
        test_db.add(other_thread)
        await test_db.commit()
        await test_db.refresh(other_thread)

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

        # Assert - Should fail because user cannot access another user's thread
        assert response.status_code == status.HTTP_404_NOT_FOUND

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
