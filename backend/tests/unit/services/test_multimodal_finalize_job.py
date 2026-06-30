"""ProcessingJob status must match the document outcome.

`process_document` called `job.complete_job()` unconditionally, even when a step
failed and the document was set FAILED — leaving job=COMPLETED / document=FAILED,
so a client polling the job saw a false success. `_finalize_job` now fails the
job when processing did not succeed.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.services.processing.multimodal_processing_service import (
    MultimodalProcessingService,
)

pytestmark = pytest.mark.unit


def _svc():
    # Skip __init__ (it wants a db session + service wiring); we only exercise
    # the pure finalize branch.
    svc = object.__new__(MultimodalProcessingService)
    svc.get_processed_files = lambda document: []
    return svc


def _doc():
    doc = MagicMock()
    doc.id = "doc-1"
    return doc


def test_finalize_fails_job_on_partial_failure():
    svc, job = _svc(), MagicMock()
    svc._finalize_job(
        job,
        _doc(),
        {"success": False, "errors": ["ocr step failed"], "processing_time": 1.2},
    )
    job.fail_job.assert_called_once()
    job.complete_job.assert_not_called()
    # The failure carries the collected step errors.
    assert "ocr step failed" in job.fail_job.call_args.kwargs["error_message"]


def test_finalize_completes_job_on_success():
    svc, job = _svc(), MagicMock()
    svc._finalize_job(
        job,
        _doc(),
        {"success": True, "errors": [], "processing_time": 1.2},
    )
    job.complete_job.assert_called_once()
    job.fail_job.assert_not_called()


def test_finalize_fail_message_falls_back_when_no_errors():
    svc, job = _svc(), MagicMock()
    svc._finalize_job(
        job,
        _doc(),
        {"success": False, "errors": [], "processing_time": 0.1},
    )
    job.fail_job.assert_called_once()
    assert job.fail_job.call_args.kwargs["error_message"]  # non-empty fallback
