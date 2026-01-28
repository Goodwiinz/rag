"""
Unit tests for Project-Chat Integration Pydantic Schemas.

Tests validation rules, serialization, and edge cases.
"""

import pytest
from datetime import datetime
from uuid import uuid4, UUID
from pydantic import ValidationError

from src.shared.research_schemas import (
    StartChatFromProjectRequest,
    StartChatFromProjectResponse,
    LinkThreadRequest,
    ProjectThreadResponse,
    ProjectThreadListResponse,
    SaveThreadToNoteRequest,
)


# ============================================================================
# StartChatFromProjectRequest Tests
# ============================================================================

class TestStartChatFromProjectRequest:
    """Tests for StartChatFromProjectRequest schema"""

    def test_valid_request_with_all_fields(self):
        """Test creating request with all fields"""
        conversation_id = uuid4()
        request = StartChatFromProjectRequest(
            initial_message="Hello, let's discuss the research",
            conversation_id=conversation_id,
            thread_title="Research Discussion",
        )

        assert request.initial_message == "Hello, let's discuss the research"
        assert request.conversation_id == conversation_id
        assert request.thread_title == "Research Discussion"

    def test_valid_request_minimal_fields(self):
        """Test creating request with only required fields"""
        request = StartChatFromProjectRequest(
            initial_message="Start the conversation",
        )

        assert request.initial_message == "Start the conversation"
        assert request.conversation_id is None
        assert request.thread_title is None

    def test_initial_message_required(self):
        """Test that initial_message is required"""
        with pytest.raises(ValidationError) as exc_info:
            StartChatFromProjectRequest()

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("initial_message",) for e in errors)

    def test_initial_message_min_length(self):
        """Test initial_message minimum length validation"""
        with pytest.raises(ValidationError) as exc_info:
            StartChatFromProjectRequest(initial_message="")

        errors = exc_info.value.errors()
        assert any("min_length" in str(e) or "too_short" in str(e) for e in errors)

    def test_thread_title_max_length(self):
        """Test thread_title maximum length validation (500 chars)"""
        with pytest.raises(ValidationError):
            StartChatFromProjectRequest(
                initial_message="Test message",
                thread_title="A" * 501,  # Exceeds 500 max
            )

    def test_thread_title_at_max_length(self):
        """Test thread_title at exactly max length"""
        request = StartChatFromProjectRequest(
            initial_message="Test message",
            thread_title="A" * 500,  # Exactly 500
        )
        assert len(request.thread_title) == 500

    def test_conversation_id_valid_uuid(self):
        """Test conversation_id accepts valid UUID"""
        valid_uuid = uuid4()
        request = StartChatFromProjectRequest(
            initial_message="Test",
            conversation_id=valid_uuid,
        )
        assert request.conversation_id == valid_uuid

    def test_conversation_id_invalid_format(self):
        """Test conversation_id rejects invalid format"""
        with pytest.raises(ValidationError):
            StartChatFromProjectRequest(
                initial_message="Test",
                conversation_id="not-a-valid-uuid",
            )


# ============================================================================
# StartChatFromProjectResponse Tests
# ============================================================================

class TestStartChatFromProjectResponse:
    """Tests for StartChatFromProjectResponse schema"""

    def test_valid_response(self):
        """Test creating valid response"""
        thread_id = uuid4()
        conversation_id = uuid4()
        project_thread_id = uuid4()
        doc_ids = [uuid4(), uuid4()]

        response = StartChatFromProjectResponse(
            thread_id=thread_id,
            conversation_id=conversation_id,
            project_thread_id=project_thread_id,
            document_scope=doc_ids,
        )

        assert response.thread_id == thread_id
        assert response.conversation_id == conversation_id
        assert response.project_thread_id == project_thread_id
        assert len(response.document_scope) == 2

    def test_response_with_empty_document_scope(self):
        """Test response with empty document scope"""
        response = StartChatFromProjectResponse(
            thread_id=uuid4(),
            conversation_id=uuid4(),
            project_thread_id=uuid4(),
            document_scope=[],
        )

        assert response.document_scope == []

    def test_response_requires_all_fields(self):
        """Test that all fields are required"""
        with pytest.raises(ValidationError) as exc_info:
            StartChatFromProjectResponse(
                thread_id=uuid4(),
                # Missing conversation_id, project_thread_id, document_scope
            )

        errors = exc_info.value.errors()
        assert len(errors) >= 1


# ============================================================================
# LinkThreadRequest Tests
# ============================================================================

class TestLinkThreadRequest:
    """Tests for LinkThreadRequest schema"""

    def test_valid_request_with_context(self):
        """Test creating request with context note"""
        thread_id = uuid4()
        request = LinkThreadRequest(
            thread_id=thread_id,
            context_note="This thread contains relevant discussion",
        )

        assert request.thread_id == thread_id
        assert request.context_note == "This thread contains relevant discussion"

    def test_valid_request_without_context(self):
        """Test creating request without optional context"""
        thread_id = uuid4()
        request = LinkThreadRequest(thread_id=thread_id)

        assert request.thread_id == thread_id
        assert request.context_note is None

    def test_thread_id_required(self):
        """Test that thread_id is required"""
        with pytest.raises(ValidationError) as exc_info:
            LinkThreadRequest()

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("thread_id",) for e in errors)

    def test_thread_id_must_be_uuid(self):
        """Test thread_id must be valid UUID"""
        with pytest.raises(ValidationError):
            LinkThreadRequest(thread_id="invalid-uuid")

    def test_context_note_can_be_long(self):
        """Test context note can be arbitrarily long"""
        long_note = "A" * 10000
        request = LinkThreadRequest(
            thread_id=uuid4(),
            context_note=long_note,
        )
        assert len(request.context_note) == 10000


# ============================================================================
# ProjectThreadResponse Tests
# ============================================================================

class TestProjectThreadResponse:
    """Tests for ProjectThreadResponse schema"""

    def test_valid_response_all_fields(self):
        """Test creating response with all fields"""
        now = datetime.utcnow()
        response = ProjectThreadResponse(
            id=uuid4(),
            project_id=uuid4(),
            thread_id=uuid4(),
            thread_title="Research Discussion",
            conversation_id=uuid4(),
            link_type="manual",
            linked_at=now,
            linked_by_id=uuid4(),
            context_note="Important discussion",
            message_count=10,
            last_message_at=now,
        )

        assert response.thread_title == "Research Discussion"
        assert response.link_type == "manual"
        assert response.message_count == 10

    def test_valid_response_optional_fields_none(self):
        """Test response with optional fields as None"""
        response = ProjectThreadResponse(
            id=uuid4(),
            project_id=uuid4(),
            thread_id=uuid4(),
            thread_title="Test Thread",
            conversation_id=uuid4(),
            link_type="auto",
            linked_at=datetime.utcnow(),
        )

        assert response.linked_by_id is None
        assert response.context_note is None
        assert response.message_count == 0  # Default
        assert response.last_message_at is None

    def test_link_type_values(self):
        """Test different link type values"""
        for link_type in ["auto", "manual", "from_chat"]:
            response = ProjectThreadResponse(
                id=uuid4(),
                project_id=uuid4(),
                thread_id=uuid4(),
                thread_title="Test",
                conversation_id=uuid4(),
                link_type=link_type,
                linked_at=datetime.utcnow(),
            )
            assert response.link_type == link_type

    def test_message_count_default(self):
        """Test message_count defaults to 0"""
        response = ProjectThreadResponse(
            id=uuid4(),
            project_id=uuid4(),
            thread_id=uuid4(),
            thread_title="Test",
            conversation_id=uuid4(),
            link_type="manual",
            linked_at=datetime.utcnow(),
        )
        assert response.message_count == 0


# ============================================================================
# ProjectThreadListResponse Tests
# ============================================================================

class TestProjectThreadListResponse:
    """Tests for ProjectThreadListResponse schema"""

    def test_valid_list_response(self):
        """Test creating valid list response"""
        threads = [
            ProjectThreadResponse(
                id=uuid4(),
                project_id=uuid4(),
                thread_id=uuid4(),
                thread_title=f"Thread {i}",
                conversation_id=uuid4(),
                link_type="manual",
                linked_at=datetime.utcnow(),
            )
            for i in range(3)
        ]

        response = ProjectThreadListResponse(
            threads=threads,
            total=3,
        )

        assert len(response.threads) == 3
        assert response.total == 3

    def test_empty_list_response(self):
        """Test empty list response"""
        response = ProjectThreadListResponse(
            threads=[],
            total=0,
        )

        assert response.threads == []
        assert response.total == 0

    def test_total_mismatch_allowed(self):
        """Test that total doesn't have to match threads length (pagination)"""
        threads = [
            ProjectThreadResponse(
                id=uuid4(),
                project_id=uuid4(),
                thread_id=uuid4(),
                thread_title="Thread",
                conversation_id=uuid4(),
                link_type="manual",
                linked_at=datetime.utcnow(),
            )
        ]

        response = ProjectThreadListResponse(
            threads=threads,
            total=100,  # Total can be larger (for pagination)
        )

        assert len(response.threads) == 1
        assert response.total == 100


# ============================================================================
# SaveThreadToNoteRequest Tests
# ============================================================================

class TestSaveThreadToNoteRequest:
    """Tests for SaveThreadToNoteRequest schema"""

    def test_valid_request_all_fields(self):
        """Test creating request with all fields"""
        thread_id = uuid4()
        request = SaveThreadToNoteRequest(
            thread_id=thread_id,
            note_title="Discussion Summary",
            include_citations=True,
        )

        assert request.thread_id == thread_id
        assert request.note_title == "Discussion Summary"
        assert request.include_citations is True

    def test_include_citations_default_true(self):
        """Test include_citations defaults to True"""
        request = SaveThreadToNoteRequest(
            thread_id=uuid4(),
            note_title="Note Title",
        )
        assert request.include_citations is True

    def test_include_citations_false(self):
        """Test include_citations can be False"""
        request = SaveThreadToNoteRequest(
            thread_id=uuid4(),
            note_title="Note Title",
            include_citations=False,
        )
        assert request.include_citations is False

    def test_note_title_min_length(self):
        """Test note_title minimum length (1 char)"""
        with pytest.raises(ValidationError):
            SaveThreadToNoteRequest(
                thread_id=uuid4(),
                note_title="",
            )

    def test_note_title_max_length(self):
        """Test note_title maximum length (255 chars)"""
        with pytest.raises(ValidationError):
            SaveThreadToNoteRequest(
                thread_id=uuid4(),
                note_title="A" * 256,
            )

    def test_note_title_at_max_length(self):
        """Test note_title at exactly max length"""
        request = SaveThreadToNoteRequest(
            thread_id=uuid4(),
            note_title="A" * 255,
        )
        assert len(request.note_title) == 255

    def test_note_title_required(self):
        """Test note_title is required"""
        with pytest.raises(ValidationError) as exc_info:
            SaveThreadToNoteRequest(thread_id=uuid4())

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("note_title",) for e in errors)

    def test_thread_id_required(self):
        """Test thread_id is required"""
        with pytest.raises(ValidationError) as exc_info:
            SaveThreadToNoteRequest(note_title="Title")

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("thread_id",) for e in errors)


# ============================================================================
# Serialization Tests
# ============================================================================

class TestSchemaSerialization:
    """Tests for schema serialization/deserialization"""

    def test_response_json_serialization(self):
        """Test response can be serialized to JSON"""
        response = StartChatFromProjectResponse(
            thread_id=uuid4(),
            conversation_id=uuid4(),
            project_thread_id=uuid4(),
            document_scope=[uuid4()],
        )

        json_str = response.model_dump_json()
        assert "thread_id" in json_str
        assert "document_scope" in json_str

    def test_response_dict_serialization(self):
        """Test response can be serialized to dict"""
        response = ProjectThreadResponse(
            id=uuid4(),
            project_id=uuid4(),
            thread_id=uuid4(),
            thread_title="Test",
            conversation_id=uuid4(),
            link_type="manual",
            linked_at=datetime.utcnow(),
        )

        data = response.model_dump()
        assert isinstance(data, dict)
        assert "thread_title" in data
        assert data["link_type"] == "manual"

    def test_request_from_dict(self):
        """Test request can be created from dict"""
        data = {
            "initial_message": "Test message",
            "thread_title": "Test Thread",
        }

        request = StartChatFromProjectRequest(**data)
        assert request.initial_message == "Test message"

    def test_uuid_serialization(self):
        """Test UUID fields are properly serialized"""
        response = StartChatFromProjectResponse(
            thread_id=uuid4(),
            conversation_id=uuid4(),
            project_thread_id=uuid4(),
            document_scope=[uuid4()],
        )

        data = response.model_dump()
        # UUIDs should be serialized (either as string or UUID)
        assert data["thread_id"] is not None
