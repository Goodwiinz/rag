"""kg_merge_entities_job: redelivery idempotency + delete-failure honesty.

Two guards from the Postgres<->Neo4j dual-write audit:

1. acks_late redelivery (celery_app sets task_acks_late=True) of a COMPLETED
   merge job must short-circuit — re-running would regress COMPLETED -> RUNNING
   and re-process every group (re-deleting already-merged nodes, duplicating
   re-pointed edges). Same guard its sibling kg_extract_entities_job has.

2. delete_entity swallows Neo4j errors and returns False. The relationships are
   re-pointed onto the primary BEFORE the delete, so a failed delete leaves the
   duplicate node alive alongside duplicated edges — that group is NOT merged
   and must be counted failed, not a false success.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit

from src.models.processing import JobStatus
from src.tasks import processing_tasks as pt


def test_merge_short_circuits_completed_job(monkeypatch: pytest.MonkeyPatch) -> None:
    job = MagicMock()
    job.status = JobStatus.COMPLETED
    db = MagicMock()
    db.query.return_value.filter.return_value.first.side_effect = [job]
    monkeypatch.setattr(pt, "SessionLocal", lambda: db)

    result = pt.kg_merge_entities_job.apply(args=("job-1",)).result

    assert result == {
        "status": "completed",
        "job_id": "job-1",
        "skipped": "duplicate_delivery",
    }
    job.start_job.assert_not_called()


def test_failed_delete_counts_group_as_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A delete_entity returning False must yield failed_groups=1, merged=0 —
    not a false success."""
    job = MagicMock()
    job.status = JobStatus.PENDING
    job.organization_id = "org-1"
    job.parameters = {
        "groups": [
            {
                "suggested_primary": "primary-1",
                "entities": [{"id": "primary-1"}, {"id": "dup-1"}],
            }
        ]
    }
    captured = {}
    job.complete_job.side_effect = lambda result: captured.update(result)

    db = MagicMock()
    db.query.return_value.filter.return_value.first.side_effect = [job]
    monkeypatch.setattr(pt, "SessionLocal", lambda: db)

    kg = MagicMock()
    kg.get_relationships.return_value = []
    kg.delete_entity.return_value = False  # Neo4j outage / node already gone
    monkeypatch.setattr(pt, "knowledge_graph_service", kg)

    result = pt.kg_merge_entities_job.apply(args=("job-2",)).result

    assert result["status"] == "completed"
    assert captured["merged_groups"] == 0
    assert captured["failed_groups"] == 1
    kg.delete_entity.assert_called_once_with("dup-1", organization_id="org-1")


def test_successful_delete_counts_group_as_merged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = MagicMock()
    job.status = JobStatus.PENDING
    job.organization_id = "org-1"
    job.parameters = {
        "groups": [
            {
                "suggested_primary": "primary-1",
                "entities": [{"id": "primary-1"}, {"id": "dup-1"}],
            }
        ]
    }
    captured = {}
    job.complete_job.side_effect = lambda result: captured.update(result)

    db = MagicMock()
    db.query.return_value.filter.return_value.first.side_effect = [job]
    monkeypatch.setattr(pt, "SessionLocal", lambda: db)

    kg = MagicMock()
    kg.get_relationships.return_value = []
    kg.delete_entity.return_value = True
    monkeypatch.setattr(pt, "knowledge_graph_service", kg)

    pt.kg_merge_entities_job.apply(args=("job-3",))

    assert captured["merged_groups"] == 1
    assert captured["failed_groups"] == 0
