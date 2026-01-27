"""
Unit tests for ProjectThread model.

Tests the database model that links research projects to chat threads.
"""

import pytest
from datetime import datetime
from uuid import uuid4

# Import all models to ensure SQLAlchemy registry is complete
from src.models import ProjectThread, ProjectThreadLinkType


class TestProjectThreadModel:
    """Unit tests for ProjectThread model"""

    def test_project_thread_creation(self):
        """Test creating a ProjectThread instance"""
        project_id = uuid4()
        thread_id = uuid4()
        user_id = uuid4()

        project_thread = ProjectThread(
            project_id=project_id,
            thread_id=thread_id,
            link_type=ProjectThreadLinkType.MANUAL.value,
            linked_by_id=user_id,
            context_note="Test link",
        )

        assert project_thread.project_id == project_id
        assert project_thread.thread_id == thread_id
        assert project_thread.link_type == ProjectThreadLinkType.MANUAL.value
        assert project_thread.linked_by_id == user_id
        assert project_thread.context_note == "Test link"

    def test_project_thread_default_values(self):
        """Test ProjectThread default values"""
        project_thread = ProjectThread(
            project_id=uuid4(),
            thread_id=uuid4(),
        )

        assert project_thread.link_type == ProjectThreadLinkType.MANUAL.value
        assert project_thread.linked_at is not None
        assert isinstance(project_thread.linked_at, datetime)
        assert project_thread.context_note is None

    def test_project_thread_link_types(self):
        """Test all ProjectThreadLinkType enum values"""
        assert ProjectThreadLinkType.AUTO.value == "auto"
        assert ProjectThreadLinkType.MANUAL.value == "manual"
        assert ProjectThreadLinkType.FROM_CHAT.value == "from_chat"

    def test_project_thread_to_dict(self):
        """Test ProjectThread to_dict method"""
        project_id = uuid4()
        thread_id = uuid4()
        user_id = uuid4()
        linked_at = datetime.utcnow()

        project_thread = ProjectThread(
            id=uuid4(),
            project_id=project_id,
            thread_id=thread_id,
            link_type=ProjectThreadLinkType.AUTO.value,
            linked_at=linked_at,
            linked_by_id=user_id,
            context_note="Auto-linked",
        )

        result = project_thread.to_dict()

        assert result["project_id"] == project_id
        assert result["thread_id"] == thread_id
        assert result["link_type"] == ProjectThreadLinkType.AUTO.value
        assert result["linked_at"] == linked_at.isoformat()
        assert result["linked_by_id"] == user_id
        assert result["context_note"] == "Auto-linked"

    def test_project_thread_repr(self):
        """Test ProjectThread string representation"""
        project_id = uuid4()
        thread_id = uuid4()

        project_thread = ProjectThread(
            project_id=project_id,
            thread_id=thread_id,
            link_type=ProjectThreadLinkType.MANUAL.value,
        )

        repr_str = repr(project_thread)
        assert "ProjectThread" in repr_str
        assert str(project_id) in repr_str
        assert str(thread_id) in repr_str
        assert "manual" in repr_str

    @pytest.mark.parametrize(
        "link_type",
        [
            ProjectThreadLinkType.AUTO,
            ProjectThreadLinkType.MANUAL,
            ProjectThreadLinkType.FROM_CHAT,
        ],
    )
    def test_project_thread_all_link_types(self, link_type):
        """Test creating ProjectThread with all link type values"""
        project_thread = ProjectThread(
            project_id=uuid4(),
            thread_id=uuid4(),
            link_type=link_type.value,
        )

        assert project_thread.link_type == link_type.value

    def test_project_thread_nullable_fields(self):
        """Test ProjectThread with nullable fields"""
        project_thread = ProjectThread(
            project_id=uuid4(),
            thread_id=uuid4(),
            linked_by_id=None,
            context_note=None,
        )

        assert project_thread.linked_by_id is None
        assert project_thread.context_note is None

    def test_project_thread_context_note_max_length(self):
        """Test ProjectThread with long context note"""
        long_note = "A" * 1000  # 1000 character note
        project_thread = ProjectThread(
            project_id=uuid4(),
            thread_id=uuid4(),
            context_note=long_note,
        )

        assert project_thread.context_note == long_note
        assert len(project_thread.context_note) == 1000
