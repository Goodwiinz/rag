"""Audit B7 regression: the Celery worker must publish upload progress to Redis.

Previously ``process_document_upload`` imported the in-process ``UploadManager``
from the API route module and pushed progress through it. Running in a *worker*
process, that manager's connection map is always empty, so progress reached no
one. The task now publishes to Redis (`publish_progress`) via the shared
``run_async`` boundary; the API process forwards those events to live sockets.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import src.tasks.document_processing_tasks as tasks


def _install_common_mocks(monkeypatch, *, job_id, doc_id, success=True):
    """Patch the task's DB/claim/service/redis collaborators, return publish mock."""
    job = SimpleNamespace(id=job_id, document_id=doc_id, fail_job=MagicMock())
    document = SimpleNamespace(
        id=doc_id, processing_status=None, processing_started_at=None
    )

    db = MagicMock()
    query = MagicMock()
    db.query.return_value = query
    query.filter.return_value = query
    query.first.side_effect = [job, document]
    monkeypatch.setattr(tasks, "SessionLocal", lambda: db)

    monkeypatch.setattr(
        tasks,
        "claim_job_for_processing",
        lambda *a, **k: SimpleNamespace(proceed=True, reason=None),
    )

    proc = MagicMock()
    proc.process_document = AsyncMock(
        return_value={
            "success": success,
            "errors": [] if success else ["bad"],
            "processing_time": 1.0,
        }
    )
    monkeypatch.setattr(tasks, "MultimodalProcessingService", lambda _db: proc)

    publish_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(tasks, "publish_progress", publish_mock)
    # Drive the coroutines the shared loop would normally run.
    monkeypatch.setattr(tasks, "run_async", lambda coro, **kw: asyncio.run(coro))

    return publish_mock, proc


@pytest.mark.unit
@pytest.mark.regression
def test_process_document_upload_publishes_progress_to_redis(monkeypatch):
    publish_mock, proc = _install_common_mocks(
        monkeypatch, job_id="job1", doc_id="doc1", success=True
    )

    result = tasks.process_document_upload.apply(
        args=("job1",), kwargs={"upload_id": "up1"}
    ).get()

    assert result["status"] == "completed"
    proc.process_document.assert_awaited_once()

    # Progress is published to Redis at start (20%) and completion (100%) — never
    # through the in-process UploadManager (which the worker can no longer import).
    published = [call.args[:2] for call in publish_mock.await_args_list]
    assert ("up1", 20.0) in published
    assert ("up1", 100.0) in published


@pytest.mark.unit
@pytest.mark.regression
def test_process_document_upload_publishes_failure_progress(monkeypatch):
    publish_mock, _ = _install_common_mocks(
        monkeypatch, job_id="jobF", doc_id="docF", success=False
    )

    result = tasks.process_document_upload.apply(
        args=("jobF",), kwargs={"upload_id": "upF"}
    ).get()

    assert result["status"] == "failed"
    # Start (20%) then a failure event at 0.0 with an error message.
    progresses = [call.args[1] for call in publish_mock.await_args_list]
    assert 20.0 in progresses
    assert 0.0 in progresses
    failure_call = publish_mock.await_args_list[-1]
    assert failure_call.kwargs.get("error_message", "").startswith("Processing failed")


@pytest.mark.unit
def test_process_document_upload_without_upload_id_skips_publish(monkeypatch):
    # No upload_id => nothing to report; the task still completes and never
    # touches the progress channel.
    publish_mock, _ = _install_common_mocks(
        monkeypatch, job_id="job2", doc_id="doc2", success=True
    )

    result = tasks.process_document_upload.apply(args=("job2",)).get()

    assert result["status"] == "completed"
    publish_mock.assert_not_awaited()
