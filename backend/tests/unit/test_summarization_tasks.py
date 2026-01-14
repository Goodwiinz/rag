"""
Unit tests for Celery Summarization Tasks (GOO-48)

Tests the Celery tasks:
- summarize_thread_task: Async thread summarization
- summarize_thread_on_resolve_task: Force summarize on resolve
- batch_summarize_threads_task: Batch summarization
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from uuid import uuid4, UUID
from datetime import datetime, timezone
from celery.exceptions import Retry

import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))


class TestSummarizeThreadTask:
    """Test summarize_thread_task Celery task"""

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session"""
        session = Mock()
        session.query = Mock()
        session.close = Mock()
        return session

    @pytest.fixture
    def mock_thread(self):
        """Create mock Thread object"""
        thread = Mock()
        thread.id = uuid4()
        thread.message_count = 5
        thread.summary = None
        return thread

    @pytest.fixture
    def mock_summarization_service(self):
        """Create mock ThreadSummarizationService"""
        service = Mock()
        return service

    def test_summarize_thread_success(self, mock_db_session, mock_thread):
        """Test successful thread summarization"""
        thread_id = str(uuid4())

        with patch(
            "src.tasks.summarize_thread_task.SessionLocal", return_value=mock_db_session
        ):
            mock_db_session.query.return_value.filter.return_value.first.return_value = mock_thread

            with patch(
                "src.tasks.summarize_thread_task.get_thread_summarization_service"
            ) as mock_get_service:
                mock_service = Mock()
                mock_service.generate_summary = AsyncMock(
                    return_value="Generated summary"
                )
                mock_get_service.return_value = mock_service

                with patch("asyncio.new_event_loop") as mock_loop:
                    mock_event_loop = Mock()
                    mock_event_loop.run_until_complete = Mock(
                        return_value="Generated summary"
                    )
                    mock_event_loop.close = Mock()
                    mock_loop.return_value = mock_event_loop

                    from src.tasks.summarize_thread_task import summarize_thread_task

                    # Create mock task instance
                    task = Mock()
                    task.request = Mock()
                    task.request.id = "test-task-id"

                    result = summarize_thread_task(task, thread_id)

                    assert result == "Generated summary"
                    mock_db_session.close.assert_called_once()

    def test_summarize_thread_not_found(self, mock_db_session):
        """Test summarization when thread not found"""
        thread_id = str(uuid4())

        with patch(
            "src.tasks.summarize_thread_task.SessionLocal", return_value=mock_db_session
        ):
            mock_db_session.query.return_value.filter.return_value.first.return_value = None

            from src.tasks.summarize_thread_task import summarize_thread_task

            task = Mock()
            result = summarize_thread_task(task, thread_id)

            assert result is None
            mock_db_session.close.assert_called_once()

    def test_summarize_thread_force_bypasses_rate_limit(
        self, mock_db_session, mock_thread
    ):
        """Test that force=True bypasses rate limiting"""
        thread_id = str(uuid4())

        with patch(
            "src.tasks.summarize_thread_task.SessionLocal", return_value=mock_db_session
        ):
            mock_db_session.query.return_value.filter.return_value.first.return_value = mock_thread

            with patch(
                "src.tasks.summarize_thread_task.get_thread_summarization_service"
            ) as mock_get_service:
                mock_service = Mock()
                mock_service.generate_summary = AsyncMock(return_value="Forced summary")
                mock_get_service.return_value = mock_service

                with patch("asyncio.new_event_loop") as mock_loop:
                    mock_event_loop = Mock()
                    mock_event_loop.run_until_complete = Mock(
                        return_value="Forced summary"
                    )
                    mock_event_loop.close = Mock()
                    mock_loop.return_value = mock_event_loop

                    from src.tasks.summarize_thread_task import summarize_thread_task

                    task = Mock()
                    result = summarize_thread_task(task, thread_id, force=True)

                    # Verify generate_summary was called with force=True
                    call_args = mock_event_loop.run_until_complete.call_args
                    assert result == "Forced summary"


class TestSummarizeOnResolveTask:
    """Test summarize_thread_on_resolve_task Celery task"""

    def test_on_resolve_calls_with_force(self):
        """Test that on_resolve task calls with force=True"""
        thread_id = str(uuid4())

        with patch(
            "src.tasks.summarize_thread_task.summarize_thread_task"
        ) as mock_summarize:
            # Mock delay method
            mock_summarize.delay = Mock()

            from src.tasks.summarize_thread_task import summarize_thread_on_resolve_task

            task = Mock()
            summarize_thread_on_resolve_task(task, thread_id)

            # Should call summarize_thread_task.delay with force=True
            mock_summarize.delay.assert_called_once_with(thread_id, force=True)


class TestBatchSummarizeTask:
    """Test batch_summarize_threads_task Celery task"""

    def test_batch_summarize_all_success(self):
        """Test batch summarization with all successes"""
        thread_ids = [str(uuid4()) for _ in range(3)]

        with patch(
            "src.tasks.summarize_thread_task.summarize_thread_task"
        ) as mock_summarize:
            mock_summarize.return_value = "Generated summary"

            from src.tasks.summarize_thread_task import batch_summarize_threads_task

            result = batch_summarize_threads_task(thread_ids)

            assert result["total"] == 3
            assert result["success"] == 3
            assert result["failed"] == 0
            assert result["skipped"] == 0

    def test_batch_summarize_with_skips(self):
        """Test batch summarization with some threads skipped (no summary needed)"""
        thread_ids = [str(uuid4()) for _ in range(3)]

        with patch(
            "src.tasks.summarize_thread_task.summarize_thread_task"
        ) as mock_summarize:
            # First returns summary, second and third return None (skipped)
            mock_summarize.side_effect = ["Summary 1", None, None]

            from src.tasks.summarize_thread_task import batch_summarize_threads_task

            result = batch_summarize_threads_task(thread_ids)

            assert result["total"] == 3
            assert result["success"] == 1
            assert result["skipped"] == 2
            assert result["failed"] == 0

    def test_batch_summarize_with_failures(self):
        """Test batch summarization with some failures"""
        thread_ids = [str(uuid4()) for _ in range(3)]

        with patch(
            "src.tasks.summarize_thread_task.summarize_thread_task"
        ) as mock_summarize:
            # First succeeds, second throws, third succeeds
            mock_summarize.side_effect = [
                "Summary 1",
                Exception("Database error"),
                "Summary 3",
            ]

            from src.tasks.summarize_thread_task import batch_summarize_threads_task

            result = batch_summarize_threads_task(thread_ids)

            assert result["total"] == 3
            assert result["success"] == 2
            assert result["failed"] == 1

    def test_batch_summarize_empty_list(self):
        """Test batch summarization with empty list"""
        from src.tasks.summarize_thread_task import batch_summarize_threads_task

        result = batch_summarize_threads_task([])

        assert result["total"] == 0
        assert result["success"] == 0
        assert result["failed"] == 0
        assert result["skipped"] == 0


class TestSummarizationTaskClass:
    """Test SummarizationTask base class behavior"""

    def test_task_has_autoretry(self):
        """Test that task has autoretry configuration"""
        from src.tasks.summarize_thread_task import SummarizationTask

        assert hasattr(SummarizationTask, "autoretry_for")
        assert SummarizationTask.autoretry_for == (Exception,)

    def test_task_has_retry_kwargs(self):
        """Test that task has retry configuration"""
        from src.tasks.summarize_thread_task import SummarizationTask

        assert hasattr(SummarizationTask, "retry_kwargs")
        assert SummarizationTask.retry_kwargs["max_retries"] == 3

    def test_task_has_retry_backoff(self):
        """Test that task uses exponential backoff"""
        from src.tasks.summarize_thread_task import SummarizationTask

        assert hasattr(SummarizationTask, "retry_backoff")
        assert SummarizationTask.retry_backoff is True

    def test_on_success_callback(self):
        """Test on_success callback is defined"""
        from src.tasks.summarize_thread_task import SummarizationTask

        task = SummarizationTask()
        # Should not raise
        task.on_success("result", "task-id", [], {})

    def test_on_failure_callback(self):
        """Test on_failure callback is defined"""
        from src.tasks.summarize_thread_task import SummarizationTask

        task = SummarizationTask()
        # Should not raise
        task.on_failure(Exception("test"), "task-id", [], {}, None)

    def test_on_retry_callback(self):
        """Test on_retry callback is defined"""
        from src.tasks.summarize_thread_task import SummarizationTask

        task = SummarizationTask()
        # Should not raise
        task.on_retry(Exception("test"), "task-id", [], {}, None)


class TestTaskErrorHandling:
    """Test error handling in summarization tasks"""

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session"""
        session = Mock()
        session.query = Mock()
        session.close = Mock()
        return session

    def test_task_closes_db_on_exception(self, mock_db_session):
        """Test that database session is closed even on exception"""
        thread_id = str(uuid4())

        with patch(
            "src.tasks.summarize_thread_task.SessionLocal", return_value=mock_db_session
        ):
            mock_db_session.query.side_effect = Exception("DB Error")

            from src.tasks.summarize_thread_task import summarize_thread_task

            task = Mock()

            with pytest.raises(Exception) as exc_info:
                summarize_thread_task(task, thread_id)

            assert "DB Error" in str(exc_info.value)
            mock_db_session.close.assert_called_once()

    def test_task_handles_invalid_uuid(self, mock_db_session):
        """Test task handles invalid UUID gracefully"""
        invalid_thread_id = "not-a-uuid"

        with patch(
            "src.tasks.summarize_thread_task.SessionLocal", return_value=mock_db_session
        ):
            from src.tasks.summarize_thread_task import summarize_thread_task

            task = Mock()

            with pytest.raises(ValueError):
                summarize_thread_task(task, invalid_thread_id)

            mock_db_session.close.assert_called_once()
