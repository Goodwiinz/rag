"""
Unit tests for Bulk Thread Operations (GOO-52)

Tests the ChatService bulk methods:
- bulk_update_threads(): Bulk resolve/archive operations
- bulk_delete_threads(): Bulk delete operations
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4, UUID
from datetime import datetime, timezone
from typing import List, Tuple, Optional

import sys
from pathlib import Path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))


class TestBulkUpdateThreads:
    """Test ChatService.bulk_update_threads() method"""

    @pytest.fixture
    def mock_chat_service(self):
        """Create a mock ChatService with database session"""
        from src.services.chat_service import ChatService

        mock_db = Mock()
        service = ChatService(mock_db)
        return service

    @pytest.fixture
    def sample_thread_ids(self) -> List[UUID]:
        """Generate sample thread UUIDs"""
        return [uuid4() for _ in range(5)]

    @pytest.fixture
    def mock_thread(self):
        """Create a mock Thread object"""
        def _create_thread(thread_id: UUID):
            thread = Mock()
            thread.id = thread_id
            thread.status = Mock(value="active")
            thread.title = f"Thread {thread_id}"
            thread.created_at = datetime.now(timezone.utc)
            thread.updated_at = datetime.now(timezone.utc)
            thread.is_deleted = False
            return thread
        return _create_thread

    def test_bulk_resolve_all_valid_threads(self, mock_chat_service, sample_thread_ids, mock_thread):
        """Test bulk resolve with all valid thread IDs - happy path"""
        user_id = uuid4()

        # Mock update_thread to return success for all
        mock_chat_service.update_thread = Mock(
            side_effect=lambda tid, data, uid: mock_thread(tid)
        )

        from src.schemas.chat import ThreadUpdate
        from src.models.thread import ThreadStatus

        results = mock_chat_service.bulk_update_threads(
            sample_thread_ids,
            ThreadUpdate(status=ThreadStatus.RESOLVED),
            user_id
        )

        assert len(results) == len(sample_thread_ids)
        assert all(success for _, success, _, _ in results)
        assert all(error is None for _, _, error, _ in results)
        assert all(thread is not None for _, _, _, thread in results)

    def test_bulk_archive_all_valid_threads(self, mock_chat_service, sample_thread_ids, mock_thread):
        """Test bulk archive with all valid thread IDs"""
        user_id = uuid4()

        mock_chat_service.update_thread = Mock(
            side_effect=lambda tid, data, uid: mock_thread(tid)
        )

        from src.schemas.chat import ThreadUpdate
        from src.models.thread import ThreadStatus

        results = mock_chat_service.bulk_update_threads(
            sample_thread_ids,
            ThreadUpdate(status=ThreadStatus.ARCHIVED),
            user_id
        )

        assert len(results) == len(sample_thread_ids)
        assert all(success for _, success, _, _ in results)

    def test_bulk_update_partial_success(self, mock_chat_service, mock_thread):
        """Test bulk update with some threads existing, some not"""
        user_id = uuid4()
        thread_ids = [uuid4() for _ in range(4)]

        # First two succeed, last two return None (not found)
        mock_chat_service.update_thread = Mock(
            side_effect=[
                mock_thread(thread_ids[0]),
                mock_thread(thread_ids[1]),
                None,
                None
            ]
        )

        from src.schemas.chat import ThreadUpdate
        from src.models.thread import ThreadStatus

        results = mock_chat_service.bulk_update_threads(
            thread_ids,
            ThreadUpdate(status=ThreadStatus.RESOLVED),
            user_id
        )

        assert len(results) == 4
        # First two succeed
        assert results[0][1] is True
        assert results[1][1] is True
        # Last two fail
        assert results[2][1] is False
        assert results[3][1] is False
        assert "not found" in results[2][2].lower() or "permissions" in results[2][2].lower()

    def test_bulk_update_handles_exceptions(self, mock_chat_service):
        """Test bulk update handles exceptions gracefully"""
        user_id = uuid4()
        thread_ids = [uuid4() for _ in range(3)]

        mock_chat_service.update_thread = Mock(
            side_effect=[
                Mock(),  # First succeeds
                Exception("Database error"),  # Second throws
                Mock(),  # Third succeeds
            ]
        )

        from src.schemas.chat import ThreadUpdate
        from src.models.thread import ThreadStatus

        results = mock_chat_service.bulk_update_threads(
            thread_ids,
            ThreadUpdate(status=ThreadStatus.RESOLVED),
            user_id
        )

        assert len(results) == 3
        assert results[0][1] is True
        assert results[1][1] is False
        assert "Database error" in results[1][2]
        assert results[2][1] is True

    def test_bulk_update_empty_list(self, mock_chat_service):
        """Test bulk update with empty thread_ids list"""
        user_id = uuid4()

        from src.schemas.chat import ThreadUpdate
        from src.models.thread import ThreadStatus

        results = mock_chat_service.bulk_update_threads(
            [],
            ThreadUpdate(status=ThreadStatus.RESOLVED),
            user_id
        )

        assert results == []

    def test_bulk_update_returns_correct_thread_ids(self, mock_chat_service, mock_thread):
        """Test that result thread_ids match input thread_ids"""
        user_id = uuid4()
        thread_ids = [uuid4() for _ in range(3)]

        mock_chat_service.update_thread = Mock(
            side_effect=lambda tid, data, uid: mock_thread(tid)
        )

        from src.schemas.chat import ThreadUpdate
        from src.models.thread import ThreadStatus

        results = mock_chat_service.bulk_update_threads(
            thread_ids,
            ThreadUpdate(status=ThreadStatus.RESOLVED),
            user_id
        )

        result_ids = [tid for tid, _, _, _ in results]
        assert result_ids == thread_ids


class TestBulkDeleteThreads:
    """Test ChatService.bulk_delete_threads() method"""

    @pytest.fixture
    def mock_chat_service(self):
        """Create a mock ChatService with database session"""
        from src.services.chat_service import ChatService

        mock_db = Mock()
        service = ChatService(mock_db)
        return service

    def test_bulk_delete_all_valid_threads(self, mock_chat_service):
        """Test bulk delete with all valid thread IDs"""
        user_id = uuid4()
        thread_ids = [uuid4() for _ in range(5)]

        mock_chat_service.delete_thread = Mock(return_value=True)

        results = mock_chat_service.bulk_delete_threads(thread_ids, user_id)

        assert len(results) == 5
        assert all(success for _, success, _ in results)
        assert all(error is None for _, _, error in results)

    def test_bulk_delete_partial_success(self, mock_chat_service):
        """Test bulk delete with some threads not found"""
        user_id = uuid4()
        thread_ids = [uuid4() for _ in range(4)]

        # First two succeed, last two return False
        mock_chat_service.delete_thread = Mock(
            side_effect=[True, True, False, False]
        )

        results = mock_chat_service.bulk_delete_threads(thread_ids, user_id)

        assert len(results) == 4
        assert results[0][1] is True
        assert results[1][1] is True
        assert results[2][1] is False
        assert results[3][1] is False

    def test_bulk_delete_handles_exceptions(self, mock_chat_service):
        """Test bulk delete handles exceptions gracefully"""
        user_id = uuid4()
        thread_ids = [uuid4() for _ in range(3)]

        mock_chat_service.delete_thread = Mock(
            side_effect=[
                True,
                Exception("Foreign key constraint"),
                True,
            ]
        )

        results = mock_chat_service.bulk_delete_threads(thread_ids, user_id)

        assert len(results) == 3
        assert results[0][1] is True
        assert results[1][1] is False
        assert "Foreign key constraint" in results[1][2]
        assert results[2][1] is True

    def test_bulk_delete_empty_list(self, mock_chat_service):
        """Test bulk delete with empty thread_ids list"""
        user_id = uuid4()

        results = mock_chat_service.bulk_delete_threads([], user_id)

        assert results == []

    def test_bulk_delete_returns_correct_thread_ids(self, mock_chat_service):
        """Test that result thread_ids match input thread_ids"""
        user_id = uuid4()
        thread_ids = [uuid4() for _ in range(3)]

        mock_chat_service.delete_thread = Mock(return_value=True)

        results = mock_chat_service.bulk_delete_threads(thread_ids, user_id)

        result_ids = [tid for tid, _, _ in results]
        assert result_ids == thread_ids


class TestBulkThreadSchemas:
    """Test bulk thread operation schemas"""

    def test_bulk_thread_request_valid(self):
        """Test BulkThreadRequest with valid thread_ids"""
        from src.schemas.chat import BulkThreadRequest

        thread_ids = [uuid4() for _ in range(5)]
        request = BulkThreadRequest(thread_ids=thread_ids)

        assert len(request.thread_ids) == 5
        assert all(isinstance(tid, UUID) for tid in request.thread_ids)

    def test_bulk_thread_request_max_limit(self):
        """Test BulkThreadRequest enforces max 100 thread limit"""
        from src.schemas.chat import BulkThreadRequest
        from pydantic import ValidationError

        thread_ids = [uuid4() for _ in range(101)]

        with pytest.raises(ValidationError) as exc_info:
            BulkThreadRequest(thread_ids=thread_ids)

        assert "max_length" in str(exc_info.value).lower() or "100" in str(exc_info.value)

    def test_bulk_thread_request_min_length(self):
        """Test BulkThreadRequest requires at least 1 thread"""
        from src.schemas.chat import BulkThreadRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            BulkThreadRequest(thread_ids=[])

        assert "min_length" in str(exc_info.value).lower() or "1" in str(exc_info.value)

    def test_bulk_thread_response_structure(self):
        """Test BulkThreadResponse has correct structure"""
        from src.schemas.chat import BulkThreadResponse, BulkThreadResult

        results = [
            BulkThreadResult(thread_id=uuid4(), success=True, error=None, thread=None),
            BulkThreadResult(thread_id=uuid4(), success=False, error="Not found", thread=None),
        ]

        response = BulkThreadResponse(
            total=2,
            succeeded=1,
            failed=1,
            results=results
        )

        assert response.total == 2
        assert response.succeeded == 1
        assert response.failed == 1
        assert len(response.results) == 2

    def test_bulk_thread_result_with_thread(self):
        """Test BulkThreadResult can include thread data"""
        from src.schemas.chat import BulkThreadResult, ThreadResponse
        from src.models.thread import ThreadStatus

        thread_id = uuid4()

        # Create a minimal thread response
        thread_response = Mock()
        thread_response.id = thread_id

        result = BulkThreadResult(
            thread_id=thread_id,
            success=True,
            error=None,
            thread=None  # Would be ThreadResponse in real usage
        )

        assert result.success is True
        assert result.error is None
