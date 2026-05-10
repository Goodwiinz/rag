"""Unit tests for ChatService bulk-thread operations.

Covers bulk_update_threads, bulk_delete_threads, and bulk_summarize_threads.
Service-layer only — the integration test in tests/integration/test_bulk_thread_api.py
covers the HTTP/WebSocket layer.
"""

import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Thread, ThreadStatus
from src.services.threads.chat_service import ChatService

# Resolve the actual module so we can monkeypatch the function-local imports.
# `src.tasks.summarize_thread_task` as an attribute of `src.tasks` is rebound
# to the Celery task by src/tasks/__init__.py, so use importlib.
task_module = importlib.import_module("src.tasks.summarize_thread_task")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _AsyncCM:
    """Minimal async context manager standing in for db.begin_nested()."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None


@pytest.fixture
def mock_db() -> AsyncMock:
    """AsyncSession mock with the methods chat_service actually calls on it."""
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    db.add = MagicMock()
    # begin_nested is a sync method that returns an async context manager
    db.begin_nested = MagicMock(return_value=_AsyncCM())
    return db


@pytest.fixture
def thread_factory():
    def _make(
        thread_id=None,
        status=ThreadStatus.ACTIVE,
        can_edit=True,
        title="t",
        summary=None,
        is_deleted=False,
    ):
        t = MagicMock(spec=Thread)
        t.id = thread_id or uuid4()
        t.status = status
        t.title = title
        t.summary = summary
        t.is_deleted = is_deleted
        t.conversation = MagicMock()
        t.conversation.workspace = MagicMock()
        t.conversation.workspace.can_user_edit = MagicMock(return_value=can_edit)
        return t

    return _make


@pytest.fixture
def chat_service(mock_db) -> ChatService:
    return ChatService(mock_db)


# ---------------------------------------------------------------------------
# TestBulkUpdateThreads
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestBulkUpdateThreads:
    async def test_atomic_happy_path(self, chat_service, mock_db, thread_factory):
        """Atomic mode: every id succeeds; commit fires once after the savepoint."""
        threads = [thread_factory() for _ in range(3)]
        chat_service.get_thread = AsyncMock(side_effect=threads)

        user_id = uuid4()
        data = SimpleNamespace(title="renamed", summary=None, status=None)

        result = await chat_service.bulk_update_threads(
            [t.id for t in threads], data, user_id, atomic=True
        )

        assert all(r[1] is True and r[2] is None for r in result)
        assert [r[3] for r in result] == threads
        for t in threads:
            assert t.title == "renamed"
        mock_db.commit.assert_awaited_once()
        mock_db.rollback.assert_not_awaited()

    async def test_best_effort_happy_path(
        self, chat_service, mock_db, thread_factory
    ):
        """Best-effort mode delegates each id to update_thread and surfaces successes."""
        threads = [thread_factory() for _ in range(2)]
        chat_service.update_thread = AsyncMock(side_effect=threads)

        user_id = uuid4()
        data = SimpleNamespace(title="x", summary=None, status=None)

        result = await chat_service.bulk_update_threads(
            [t.id for t in threads], data, user_id, atomic=False
        )

        assert [(r[1], r[2]) for r in result] == [(True, None), (True, None)]
        assert [r[3] for r in result] == threads
        assert chat_service.update_thread.await_count == 2

    async def test_best_effort_partial_success(
        self, chat_service, mock_db, thread_factory
    ):
        """A None return from update_thread is recorded as 'not found or insufficient permissions'."""
        good = thread_factory()
        chat_service.update_thread = AsyncMock(side_effect=[good, None])

        ids = [good.id, uuid4()]
        result = await chat_service.bulk_update_threads(
            ids, SimpleNamespace(title="x", summary=None, status=None), uuid4()
        )

        assert result[0] == (good.id, True, None, good)
        assert result[1][1] is False
        assert "not found" in result[1][2].lower()
        assert result[1][3] is None

    async def test_best_effort_continues_on_exception(
        self, chat_service, mock_db, thread_factory
    ):
        """An exception on one id doesn't stop processing of the others."""
        good = thread_factory()
        chat_service.update_thread = AsyncMock(
            side_effect=[good, RuntimeError("boom"), good]
        )

        ids = [good.id, uuid4(), good.id]
        result = await chat_service.bulk_update_threads(
            ids, SimpleNamespace(title="x", summary=None, status=None), uuid4()
        )

        assert result[0][1] is True
        assert result[1] == (ids[1], False, "boom", None)
        assert result[2][1] is True

    async def test_empty_list_returns_empty(self, chat_service, mock_db):
        """An empty thread_ids list returns []; the service has no max-100 check (router does)."""
        data = SimpleNamespace(title=None, summary=None, status=None)
        atomic_result = await chat_service.bulk_update_threads(
            [], data, uuid4(), atomic=True
        )
        best_effort_result = await chat_service.bulk_update_threads(
            [], data, uuid4(), atomic=False
        )

        assert atomic_result == []
        assert best_effort_result == []

    async def test_atomic_thread_not_found_rolls_back_all(
        self, chat_service, mock_db, thread_factory
    ):
        """If any thread is missing in atomic mode, every id is returned as failed and the txn rolled back."""
        good = thread_factory()
        chat_service.get_thread = AsyncMock(side_effect=[good, None])

        ids = [good.id, uuid4()]
        result = await chat_service.bulk_update_threads(
            ids,
            SimpleNamespace(title="x", summary=None, status=None),
            uuid4(),
            atomic=True,
        )

        assert all(r[1] is False for r in result)
        assert all("Atomic operation failed" in r[2] for r in result)
        mock_db.rollback.assert_awaited()
        mock_db.commit.assert_not_awaited()

    async def test_atomic_permission_denied_rolls_back_all(
        self, chat_service, mock_db, thread_factory
    ):
        """PermissionError on any thread aborts the savepoint and flags every id failed."""
        good = thread_factory(can_edit=True)
        bad = thread_factory(can_edit=False)
        chat_service.get_thread = AsyncMock(side_effect=[good, bad])

        result = await chat_service.bulk_update_threads(
            [good.id, bad.id],
            SimpleNamespace(title="x", summary=None, status=None),
            uuid4(),
            atomic=True,
        )

        assert all(r[1] is False for r in result)
        assert all("Atomic operation failed" in r[2] for r in result)
        mock_db.rollback.assert_awaited()

    async def test_atomic_rollback_on_commit_error(
        self, chat_service, mock_db, thread_factory
    ):
        """A failure during the outer commit rolls back and surfaces every id as failed."""
        threads = [thread_factory() for _ in range(2)]
        chat_service.get_thread = AsyncMock(side_effect=threads)
        mock_db.commit.side_effect = RuntimeError("commit boom")

        result = await chat_service.bulk_update_threads(
            [t.id for t in threads],
            SimpleNamespace(title="x", summary=None, status=None),
            uuid4(),
            atomic=True,
        )

        assert all(r[1] is False for r in result)
        assert all("commit boom" in r[2] for r in result)
        mock_db.rollback.assert_awaited()

    async def test_status_resolved_enqueues_summarize_task_atomic(
        self, chat_service, mock_db, thread_factory, monkeypatch
    ):
        """When atomic mode flips a thread to RESOLVED, summarize_thread_on_resolve_task.delay is invoked."""
        thread = thread_factory(status=ThreadStatus.ACTIVE)
        chat_service.get_thread = AsyncMock(return_value=thread)

        task_mock = MagicMock()
        monkeypatch.setattr(
            task_module, "summarize_thread_on_resolve_task", task_mock
        )

        result = await chat_service.bulk_update_threads(
            [thread.id],
            SimpleNamespace(
                title=None, summary=None, status=ThreadStatus.RESOLVED
            ),
            uuid4(),
            atomic=True,
        )

        assert result[0][1] is True
        task_mock.delay.assert_called_once_with(str(thread.id))

    async def test_resolve_task_failure_swallowed(
        self, chat_service, mock_db, thread_factory, monkeypatch, caplog
    ):
        """If the resolve-task .delay raises, the bulk result is still success; warning logged."""
        thread = thread_factory(status=ThreadStatus.ACTIVE)
        chat_service.get_thread = AsyncMock(return_value=thread)

        task_mock = MagicMock()
        task_mock.delay.side_effect = RuntimeError("broker dead")
        monkeypatch.setattr(
            task_module, "summarize_thread_on_resolve_task", task_mock
        )

        import logging

        with caplog.at_level(
            logging.WARNING, logger="src.services.threads.chat_service"
        ):
            result = await chat_service.bulk_update_threads(
                [thread.id],
                SimpleNamespace(
                    title=None, summary=None, status=ThreadStatus.RESOLVED
                ),
                uuid4(),
                atomic=True,
            )

        assert result[0][1] is True
        assert any(
            "Failed to queue resolution summary" in r.message
            for r in caplog.records
        )


# ---------------------------------------------------------------------------
# TestBulkDeleteThreads
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestBulkDeleteThreads:
    async def test_atomic_happy_path(self, chat_service, mock_db, thread_factory):
        """Atomic delete soft-deletes every thread, commits once, and returns all-success tuples."""
        threads = [thread_factory() for _ in range(3)]
        chat_service.get_thread = AsyncMock(side_effect=threads)

        result = await chat_service.bulk_delete_threads(
            [t.id for t in threads], uuid4(), atomic=True
        )

        assert all(r == (t.id, True, None) for r, t in zip(result, threads))
        for t in threads:
            assert t.is_deleted is True
        mock_db.commit.assert_awaited_once()

    async def test_best_effort_mixed_outcomes(
        self, chat_service, mock_db, thread_factory
    ):
        """Best-effort delete tolerates a mix of True/False/raises across ids."""
        good_id = uuid4()
        missing_id = uuid4()
        error_id = uuid4()
        chat_service.delete_thread = AsyncMock(
            side_effect=[True, False, RuntimeError("nope")]
        )

        result = await chat_service.bulk_delete_threads(
            [good_id, missing_id, error_id], uuid4(), atomic=False
        )

        assert result[0] == (good_id, True, None)
        assert result[1][1] is False and "not found" in result[1][2].lower()
        assert result[2] == (error_id, False, "nope")


# ---------------------------------------------------------------------------
# TestBulkSummarizeThreads
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestBulkSummarizeThreads:
    async def test_happy_path_enqueues_task(
        self, chat_service, mock_db, thread_factory, monkeypatch
    ):
        """Each thread that exists triggers summarize_thread_task.delay(thread_id, force=True)."""
        thread = thread_factory()
        chat_service.get_thread = AsyncMock(return_value=thread)

        task_mock = MagicMock()
        monkeypatch.setattr(task_module, "summarize_thread_task", task_mock)

        result = await chat_service.bulk_summarize_threads([thread.id], uuid4())

        assert result == [(thread.id, True, None, thread)]
        task_mock.delay.assert_called_once_with(str(thread.id), force=True)

    async def test_thread_not_found_records_failure(
        self, chat_service, mock_db, monkeypatch
    ):
        """Missing threads are recorded as failures without invoking the task."""
        chat_service.get_thread = AsyncMock(return_value=None)

        task_mock = MagicMock()
        monkeypatch.setattr(task_module, "summarize_thread_task", task_mock)

        missing_id = uuid4()
        result = await chat_service.bulk_summarize_threads([missing_id], uuid4())

        assert result[0][0] == missing_id
        assert result[0][1] is False
        assert "not found" in result[0][2].lower()
        assert result[0][3] is None
        task_mock.delay.assert_not_called()

    async def test_celery_enqueue_failure_records_failed_with_thread(
        self, chat_service, mock_db, thread_factory, monkeypatch
    ):
        """If .delay raises, the result carries the thread but is marked failed."""
        thread = thread_factory()
        chat_service.get_thread = AsyncMock(return_value=thread)

        task_mock = MagicMock()
        task_mock.delay.side_effect = RuntimeError("broker down")
        monkeypatch.setattr(task_module, "summarize_thread_task", task_mock)

        result = await chat_service.bulk_summarize_threads([thread.id], uuid4())

        assert result[0][0] == thread.id
        assert result[0][1] is False
        assert "Failed to queue task" in result[0][2]
        assert result[0][3] is thread
