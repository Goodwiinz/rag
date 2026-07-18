"""acks_late idempotency guard on the OPENAI extract_entities task.

celery_app sets task_acks_late=True, so a worker recycled after the job
finishes but before the broker ack gets the SAME message redelivered.
Pre-guard behavior: extract_entities re-ran the full paid LLM extraction,
regressed the job COMPLETED -> RUNNING via start_job(), AND appended a second
copy of every entity (OPENAI rows are never delete-before-inserted). Pins the
same short-circuit its siblings got (#912 follow-up).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit

from src.models.processing import JobStatus
from src.tasks import processing_tasks as pt


def test_extract_entities_short_circuits_completed_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = MagicMock()
    job.status = JobStatus.COMPLETED
    db = MagicMock()
    db.query.return_value.filter.return_value.first.side_effect = [job]
    monkeypatch.setattr(pt, "SessionLocal", lambda: db)

    result = pt.extract_entities.apply(args=("job-1",)).result

    assert result == {
        "status": "completed",
        "job_id": "job-1",
        "skipped": "duplicate_delivery",
    }
    job.start_job.assert_not_called()
    # No new entity rows added on a redelivered completed job.
    db.add.assert_not_called()
