"""Route-level guards for R5-M14, R5-M15, R5-L13, R5-L14, R5-L15.

- M14: /evaluation/real-time was the only endpoint in the file missing
  `except HTTPException: raise`, so its own 503 fell into the generic
  `except Exception` below and was reported as a 500.
- M15: soft-deleted EvaluationJob rows were still listed/aggregated —
  nothing in the router filtered on `is_deleted`.
- L13: `EvaluationType(...)` and the report_type free string both raised
  ValueError deep inside request handling (500 / post-200 task failure)
  instead of a 400.
- L14: BatchEvaluationRequest.queries / search_limit were unbounded.
- L15: /metrics/summary aggregated in SQL instead of loading every
  EvaluationMetric row (including its Text/JSON columns) into Python.
"""

from __future__ import annotations

import statistics
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from kombu.exceptions import OperationalError

pytestmark = pytest.mark.unit


@pytest.fixture
def client() -> Any:
    from src.api.infrastructure import evaluation
    from src.core.database import get_db_sync
    from src.core.dependencies import get_current_user

    user = MagicMock()
    user.id = uuid4()
    user.organization_id = uuid4()

    db = MagicMock()

    app = FastAPI()
    app.include_router(evaluation.router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db_sync] = lambda: db

    return TestClient(app, raise_server_exceptions=False), db


# ---------------------------------------------------------------------------
# R5-M14
# ---------------------------------------------------------------------------


def test_real_time_broker_outage_is_a_503_not_a_500(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.api.infrastructure import evaluation

    test_client, _db = client
    task = MagicMock()
    task.delay.side_effect = OperationalError("broker down")
    monkeypatch.setattr(evaluation, "run_real_time_evaluation", task)

    response = test_client.post(
        "/evaluation/real-time",
        json={"query": "q", "generated_answer": "a", "retrieved_context": ["c"]},
    )

    assert response.status_code == 503


# ---------------------------------------------------------------------------
# R5-M15
# ---------------------------------------------------------------------------


def _filter_predicate_strings(mock_filter: MagicMock) -> list[str]:
    """String-repr every positional arg across every call to a mocked
    `.filter(...)`, so tests can check a predicate was included without
    needing to reconstruct/compare SQLAlchemy expression objects."""
    out: list[str] = []
    for call in mock_filter.call_args_list:
        out.extend(str(a) for a in call.args)
    return out


def test_list_jobs_filters_out_soft_deleted(client: Any) -> None:
    test_client, db = client
    db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = (
        []
    )

    response = test_client.get("/evaluation/jobs")

    assert response.status_code == 200
    preds = _filter_predicate_strings(db.query.return_value.filter)
    assert any("is_deleted" in p for p in preds)


def test_get_job_filters_out_soft_deleted(client: Any) -> None:
    from src.services.evaluation.rag_evaluation_service import rag_evaluation_service

    test_client, db = client
    db.query.return_value.filter.return_value.first.return_value = None

    response = test_client.get(f"/evaluation/jobs/{uuid4()}")

    assert response.status_code == 404
    preds = _filter_predicate_strings(db.query.return_value.filter)
    assert any("is_deleted" in p for p in preds)


def test_delete_job_filters_out_soft_deleted(client: Any) -> None:
    test_client, db = client
    db.query.return_value.filter.return_value.first.return_value = None

    response = test_client.delete(f"/evaluation/jobs/{uuid4()}")

    assert response.status_code == 404
    preds = _filter_predicate_strings(db.query.return_value.filter)
    assert any("is_deleted" in p for p in preds)


def test_comparison_creation_filters_out_soft_deleted_jobs(client: Any) -> None:
    test_client, db = client
    db.query.return_value.filter.return_value.first.return_value = None

    response = test_client.post(
        "/evaluation/comparisons",
        json={
            "name": "c",
            "baseline_job_id": str(uuid4()),
            "comparison_job_id": str(uuid4()),
        },
    )

    assert response.status_code == 404
    preds = _filter_predicate_strings(db.query.return_value.filter)
    assert any("is_deleted" in p for p in preds)


# ---------------------------------------------------------------------------
# R5-L13
# ---------------------------------------------------------------------------


def test_unknown_evaluation_type_is_a_400_not_a_500(client: Any) -> None:
    test_client, _db = client

    response = test_client.post(
        "/evaluation/jobs",
        json={
            "name": "n",
            "evaluation_type": "not_a_real_type",
            "questions": ["q1"],
        },
    )

    assert response.status_code == 400


def test_unknown_report_type_is_a_400_not_a_task_failure(client: Any) -> None:
    from src.api.infrastructure import evaluation
    from src.models.evaluation import EvaluationStatus

    test_client, db = client
    job = MagicMock()
    job.status = EvaluationStatus.COMPLETED.value
    db.query.return_value.filter.return_value.first.return_value = job

    response = test_client.post(
        f"/evaluation/jobs/{uuid4()}/reports/not_a_real_report_type",
    )

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# R5-L14
# ---------------------------------------------------------------------------


def test_batch_request_rejects_too_many_queries(client: Any) -> None:
    test_client, _db = client

    response = test_client.post(
        "/evaluation/jobs/batch",
        json={"name": "n", "queries": [f"q{i}" for i in range(101)]},
    )

    assert response.status_code == 422


def test_batch_request_rejects_out_of_range_search_limit(client: Any) -> None:
    test_client, _db = client

    response = test_client.post(
        "/evaluation/jobs/batch",
        json={"name": "n", "queries": ["q1"], "search_limit": 500},
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# R5-L15
# ---------------------------------------------------------------------------


def test_metrics_summary_aggregates_via_sql_group_by(client: Any) -> None:
    test_client, db = client

    filtered = db.query.return_value.join.return_value.filter.return_value
    # First query: (metric_type, count, avg, min, max, violations) grouped.
    filtered.group_by.return_value.all.return_value = [
        ("rag_triad_faithfulness", 3, 0.7, 0.5, 0.9, 1),
    ]
    # Second query: just the raw (metric_type, value) pairs, for std_dev.
    filtered.all.return_value = [
        ("rag_triad_faithfulness", 0.5),
        ("rag_triad_faithfulness", 0.7),
        ("rag_triad_faithfulness", 0.9),
    ]

    response = test_client.get("/evaluation/metrics/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["total_metrics"] == 3
    assert body["threshold_violations"] == 1
    summary = body["metric_summary"]["rag_triad_faithfulness"]
    assert summary["count"] == 3
    assert summary["mean"] == pytest.approx(0.7)
    assert summary["min"] == pytest.approx(0.5)
    assert summary["max"] == pytest.approx(0.9)
    assert summary["std_dev"] == pytest.approx(statistics.stdev([0.5, 0.7, 0.9]))
    assert body["average_scores"]["rag_triad_faithfulness"] == pytest.approx(0.7)

    # The endpoint must query with GROUP BY (aggregation), not load every
    # row and reduce in Python.
    db.query.return_value.join.return_value.filter.return_value.group_by.assert_called_once()
