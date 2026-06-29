"""Regression: the /threads/{id}/summarize HTTP path must drive the
summarization service with a SYNC session.

The service uses the sync SQLAlchemy API (db.query / db.commit) and is shared
with the Celery task. The endpoint previously handed it the request's
AsyncSession, which has no .query → AttributeError → 500 on every call. The fix
runs `_run_thread_summary_sync` in a worker thread with its own sync
SessionLocal + asyncio.run (mirroring Celery). These tests pin that contract.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from src.api.threads.threads import _run_thread_summary_sync


@pytest.mark.unit
def test_runs_service_with_sync_session_and_closes_it():
    tid = uuid.uuid4()
    sync_session = MagicMock(name="SyncSession")
    service = MagicMock()

    async def _fake_generate(thread_id, force):
        # Must be invoked with the thread id + force=True, and the session
        # handed to the service must be the sync SessionLocal one.
        assert thread_id == tid
        assert force is True
        return "a summary"

    service.generate_summary.side_effect = _fake_generate

    with (
        patch("src.core.database.SessionLocal", return_value=sync_session) as mk_sess,
        patch(
            "src.services.threads.thread_summarization_service."
            "get_thread_summarization_service",
            return_value=service,
        ) as mk_factory,
    ):
        result = _run_thread_summary_sync(tid)

    assert result == "a summary"
    mk_sess.assert_called_once()
    # The service is built from the sync session, not the request AsyncSession.
    mk_factory.assert_called_once_with(sync_session)
    # Session is always closed (finally), even on the happy path.
    sync_session.close.assert_called_once()


@pytest.mark.unit
def test_session_closed_when_service_raises():
    tid = uuid.uuid4()
    sync_session = MagicMock(name="SyncSession")
    service = MagicMock()

    async def _boom(thread_id, force):
        raise RuntimeError("llm down")

    service.generate_summary.side_effect = _boom

    with (
        patch("src.core.database.SessionLocal", return_value=sync_session),
        patch(
            "src.services.threads.thread_summarization_service."
            "get_thread_summarization_service",
            return_value=service,
        ),
    ):
        with pytest.raises(RuntimeError, match="llm down"):
            _run_thread_summary_sync(tid)

    # The session must still be closed on the error path.
    sync_session.close.assert_called_once()
