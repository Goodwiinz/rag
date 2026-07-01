"""acks_late idempotency guards on evaluation tasks.

celery_app sets task_acks_late=True, so a worker recycled after a task
finishes but before the broker ack gets the SAME message redelivered.
Pre-guard behavior: run_rag_triad_evaluation / run_batch_evaluation re-ran the
full paid LLM evaluation and appended a duplicate set of EvaluationMetric rows
to the job; run_real_time_evaluation created a brand-new EvaluationJob per
delivery. These tests pin the short-circuit semantics.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit

from src.tasks import evaluation_tasks as et


def _terminal_job(status="completed"):
    job = MagicMock()
    job.status = status
    return job


def _session_with(first_results):
    """MagicMock sync session whose query().filter().first() yields in order."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.side_effect = first_results
    return db


@pytest.mark.parametrize("status", ["completed", "failed", "cancelled"])
def test_rag_triad_short_circuits_terminal_job(monkeypatch, status):
    job = _terminal_job(status)
    dataset = MagicMock()
    db = _session_with([job, dataset])
    monkeypatch.setattr(et, "SessionLocal", lambda: db)

    result = et.run_rag_triad_evaluation.apply(args=("job-1",)).result

    assert result == {
        "status": status,
        "job_id": "job-1",
        "skipped": "duplicate_delivery",
    }
    job.start_job.assert_not_called()


def test_batch_short_circuits_terminal_job(monkeypatch):
    job = _terminal_job("completed")
    db = _session_with([job])
    monkeypatch.setattr(et, "SessionLocal", lambda: db)

    result = et.run_batch_evaluation.apply(args=("job-2", ["q1", "q2"])).result

    assert result["skipped"] == "duplicate_delivery"
    job.start_job.assert_not_called()


def test_rag_triad_runs_when_job_running(monkeypatch):
    # Non-terminal (running/pending) must NOT short-circuit — a crash mid-run
    # should still be retried. The task proceeds past the guard and calls
    # start_job (we let it blow up right after by making the dataset empty).
    job = _terminal_job("pending")
    dataset = MagicMock()
    dataset.questions = []
    dataset.reference_answers = []
    dataset.contexts = []
    db = _session_with([job, dataset])
    monkeypatch.setattr(et, "SessionLocal", lambda: db)

    et.run_rag_triad_evaluation.apply(args=("job-3",))

    job.start_job.assert_called_once()


def test_real_time_short_circuits_existing_task_id(monkeypatch):
    existing = MagicMock()
    existing.status = "completed"
    existing.id = "job-4"
    db = _session_with([existing])
    monkeypatch.setattr(et, "SessionLocal", lambda: db)

    result = et.run_real_time_evaluation.apply(
        args=("q", "a", ["ctx"]),
        task_id="stable-delivery-id",
    ).result

    assert result == {
        "status": "completed",
        "job_id": "job-4",
        "skipped": "duplicate_delivery",
    }
    db.add.assert_not_called()
