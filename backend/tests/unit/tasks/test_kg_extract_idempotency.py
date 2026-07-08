"""acks_late idempotency guard on kg_extract_entities_job.

celery_app sets task_acks_late=True, so a worker recycled after the job
finishes but before the broker ack gets the SAME message redelivered.
Pre-guard behavior: kg_extract_entities_job re-ran the full paid LLM
extraction and regressed the job COMPLETED -> RUNNING via start_job().
Pins the same short-circuit its siblings got in #912/#930.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit

from src.models.processing import JobStatus
from src.tasks import processing_tasks as pt


def test_kg_extract_short_circuits_completed_job(monkeypatch):
    job = MagicMock()
    job.status = JobStatus.COMPLETED
    db = MagicMock()
    db.query.return_value.filter.return_value.first.side_effect = [job]
    monkeypatch.setattr(pt, "SessionLocal", lambda: db)

    result = pt.kg_extract_entities_job.apply(args=("job-1",)).result

    assert result == {
        "status": "completed",
        "job_id": "job-1",
        "skipped": "duplicate_delivery",
    }
    job.start_job.assert_not_called()
