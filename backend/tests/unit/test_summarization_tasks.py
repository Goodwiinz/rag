"""Unit tests for Celery summarization tasks.

Covers summarize_thread_task, summarize_thread_on_resolve_task,
batch_summarize_threads_task, and the SummarizationTask base class hooks.

Tasks are invoked via `._orig_run(...)` to bypass Celery's autoretry wrapper —
this gives unit tests deterministic exception behavior and avoids triggering
the broker. `_orig_run` is the post-`bind=True` function (no `self` arg).
"""

import importlib
import logging
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.tasks.summarize_thread_task import (
    SummarizationTask,
    batch_summarize_threads_task,
    summarize_thread_on_resolve_task,
    summarize_thread_task,
)

# Resolve the actual module object — `src.tasks.summarize_thread_task` as an
# attribute of `src.tasks` is rebound to the Celery task by src/tasks/__init__.py,
# so dotted-path lookups would target the task instead of the module.
task_module = importlib.import_module("src.tasks.summarize_thread_task")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_db() -> MagicMock:
    """A fake DB session whose query chain can be wired per-test."""
    return MagicMock()


@pytest.fixture(autouse=True)
def isolate_session_local(monkeypatch, fake_db):
    """Replace module-level SessionLocal so tasks don't hit a real engine."""
    monkeypatch.setattr(task_module, "SessionLocal", lambda: fake_db)
    return fake_db


def _wire_thread_query(db, thread):
    """Make db.query(Thread).filter(...).first() return `thread`."""
    chain = MagicMock()
    chain.filter.return_value = chain
    chain.first.return_value = thread
    db.query.return_value = chain
    return chain


# ---------------------------------------------------------------------------
# TestSummarizeThreadTask
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSummarizeThreadTask:
    def test_valid_execution_returns_summary(self, fake_db, monkeypatch):
        """Happy path: thread found, service returns 'summary', task returns it and closes db."""
        thread_id = str(uuid4())
        thread = MagicMock()
        thread.id = thread_id
        _wire_thread_query(fake_db, thread)

        service = MagicMock()
        service.generate_summary = AsyncMock(return_value="summary")
        monkeypatch.setattr(
            "src.services.threads.thread_summarization_service.get_thread_summarization_service",
            MagicMock(return_value=service),
        )

        result = summarize_thread_task._orig_run(thread_id)

        assert result == "summary"
        service.generate_summary.assert_awaited_once()
        fake_db.close.assert_called_once()

    def test_thread_not_found_returns_none(self, fake_db, monkeypatch):
        """If the thread doesn't exist, the task returns None without invoking the service."""
        _wire_thread_query(fake_db, None)
        sentinel = MagicMock(
            side_effect=AssertionError("service should not be loaded")
        )
        monkeypatch.setattr(
            "src.services.threads.thread_summarization_service.get_thread_summarization_service",
            sentinel,
        )

        result = summarize_thread_task._orig_run(str(uuid4()))

        assert result is None
        sentinel.assert_not_called()
        fake_db.close.assert_called_once()

    def test_force_true_passed_through(self, fake_db, monkeypatch):
        """force=True is forwarded to ThreadSummarizationService.generate_summary."""
        thread_id = str(uuid4())
        thread = MagicMock()
        thread.id = thread_id
        _wire_thread_query(fake_db, thread)

        service = MagicMock()
        service.generate_summary = AsyncMock(return_value="forced")
        monkeypatch.setattr(
            "src.services.threads.thread_summarization_service.get_thread_summarization_service",
            MagicMock(return_value=service),
        )

        result = summarize_thread_task._orig_run(thread_id, force=True)

        assert result == "forced"
        _, kwargs = service.generate_summary.call_args
        assert kwargs.get("force") is True

    def test_exception_reraised_for_autoretry(self, fake_db, monkeypatch):
        """A service exception propagates out (triggering Celery's autoretry) and db is still closed."""
        thread_id = str(uuid4())
        thread = MagicMock()
        thread.id = thread_id
        _wire_thread_query(fake_db, thread)

        service = MagicMock()
        service.generate_summary = AsyncMock(side_effect=RuntimeError("boom"))
        monkeypatch.setattr(
            "src.services.threads.thread_summarization_service.get_thread_summarization_service",
            MagicMock(return_value=service),
        )

        with pytest.raises(RuntimeError, match="boom"):
            summarize_thread_task._orig_run(thread_id)

        fake_db.close.assert_called_once()

    def test_autoretry_config_on_base_class(self):
        """SummarizationTask declares autoretry on all Exceptions with 3 max retries and backoff."""
        assert SummarizationTask.autoretry_for == (Exception,)
        assert SummarizationTask.retry_backoff is True
        # retry_kwargs may be mutated by Celery at runtime; assert the originally-declared values.
        assert SummarizationTask.retry_kwargs.get("max_retries") == 3
        assert SummarizationTask.retry_kwargs.get("countdown") == 5

    def test_on_success_logs_info(self, caplog):
        """on_success emits an INFO log mentioning the task id."""
        task = SummarizationTask()
        with caplog.at_level(
            logging.INFO, logger="src.tasks.summarize_thread_task"
        ):
            task.on_success(retval="x", task_id="abc-123", args=(), kwargs={})
        assert any(
            r.levelno == logging.INFO and "abc-123" in r.message
            for r in caplog.records
        )

    def test_on_failure_logs_error(self, caplog):
        """on_failure logs an ERROR with the exception detail."""
        task = SummarizationTask()
        exc = RuntimeError("kaboom")
        with caplog.at_level(
            logging.ERROR, logger="src.tasks.summarize_thread_task"
        ):
            task.on_failure(
                exc=exc, task_id="abc-456", args=(), kwargs={}, einfo=None
            )
        assert any(
            r.levelno == logging.ERROR and "kaboom" in r.message
            for r in caplog.records
        )

    def test_on_retry_logs_warning(self, caplog):
        """on_retry logs a WARNING with the exception detail."""
        task = SummarizationTask()
        exc = TimeoutError("slow")
        with caplog.at_level(
            logging.WARNING, logger="src.tasks.summarize_thread_task"
        ):
            task.on_retry(
                exc=exc, task_id="abc-789", args=(), kwargs={}, einfo=None
            )
        assert any(
            r.levelno == logging.WARNING and "slow" in r.message
            for r in caplog.records
        )


# ---------------------------------------------------------------------------
# TestSummarizeOnResolveTask
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSummarizeOnResolveTask:
    def test_delegates_with_force_true(self):
        """on_resolve delegates to summarize_thread_task.delay with force=True."""
        thread_id = str(uuid4())
        with patch.object(summarize_thread_task, "delay") as mock_delay:
            summarize_thread_on_resolve_task._orig_run(thread_id)

        mock_delay.assert_called_once_with(thread_id, force=True)


# ---------------------------------------------------------------------------
# TestBatchSummarizeThreadsTask
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBatchSummarizeThreadsTask:
    def test_aggregates_success_and_skipped(self, monkeypatch):
        """Truthy task results count as success; falsy as skipped."""
        thread_ids = [str(uuid4()), str(uuid4()), str(uuid4())]
        job = MagicMock()
        group_result = MagicMock()
        group_result.get.return_value = ["s1", None, "s3"]
        job.apply_async.return_value = group_result
        monkeypatch.setattr(task_module, "group", MagicMock(return_value=job))

        result = batch_summarize_threads_task.run(thread_ids)

        assert result == {"total": 3, "success": 2, "failed": 0, "skipped": 1}
        group_result.get.assert_called_once_with(timeout=300)

    def test_get_raises_marks_remainder_failed(self, monkeypatch, caplog):
        """If group_result.get raises, the remainder of total is marked failed and the error is logged."""
        thread_ids = [str(uuid4()) for _ in range(4)]
        job = MagicMock()
        group_result = MagicMock()
        group_result.get.side_effect = RuntimeError("broker down")
        job.apply_async.return_value = group_result
        monkeypatch.setattr(task_module, "group", MagicMock(return_value=job))

        with caplog.at_level(
            logging.ERROR, logger="src.tasks.summarize_thread_task"
        ):
            result = batch_summarize_threads_task.run(thread_ids)

        assert result == {"total": 4, "success": 0, "failed": 4, "skipped": 0}
        assert any(
            "Batch summarization failed" in r.message for r in caplog.records
        )

    def test_empty_list_returns_zeros(self, monkeypatch):
        """An empty thread_ids list produces an all-zero result without crashing."""
        job = MagicMock()
        group_result = MagicMock()
        group_result.get.return_value = []
        job.apply_async.return_value = group_result
        monkeypatch.setattr(task_module, "group", MagicMock(return_value=job))

        result = batch_summarize_threads_task.run([])

        assert result == {"total": 0, "success": 0, "failed": 0, "skipped": 0}
