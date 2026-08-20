"""R5-L18: get_evaluation_metrics ignored organization_id and swallowed every
exception into `[]`.

EvaluationMetric has no organization_id of its own — scope has to come from
a join through EvaluationJob. The old query only filtered on `job_id`, so
(defense-in-depth aside — the route already checks job ownership before
calling this) the service itself would happily return another org's metrics
if ever called with an org-mismatched job_id. Worse: `except Exception:
return []` made a real DB failure indistinguishable from "this job has no
metrics yet".
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit


def test_get_evaluation_metrics_joins_and_filters_by_organization() -> None:
    from src.services.evaluation.rag_evaluation_service import rag_evaluation_service

    db = MagicMock()
    query = db.query.return_value
    joined = query.join.return_value
    filtered = joined.filter.return_value
    filtered.order_by.return_value.limit.return_value.all.return_value = []

    rag_evaluation_service.get_evaluation_metrics(
        job_id="job-1", organization_id="org-1", db=db
    )

    db.query.assert_called_once()
    query.join.assert_called_once()
    # The filter call must have been given more than one predicate —
    # job_id AND organization_id (through the join) — not job_id alone.
    filter_call_args = joined.filter.call_args
    assert len(filter_call_args.args) >= 2, (
        "get_evaluation_metrics must filter on both job_id and the joined "
        "EvaluationJob.organization_id, not job_id alone"
    )


def test_get_evaluation_metrics_does_not_swallow_exceptions_to_empty_list() -> None:
    """Before the fix, any exception here (a real DB failure, a bad query)
    was caught and silently converted into `[]` — indistinguishable from
    "no metrics exist yet". The fix lets it propagate."""
    from src.services.evaluation.rag_evaluation_service import rag_evaluation_service

    db = MagicMock()
    db.query.side_effect = RuntimeError("connection reset")

    with pytest.raises(RuntimeError):
        rag_evaluation_service.get_evaluation_metrics(
            job_id="job-1", organization_id="org-1", db=db
        )


def test_get_evaluation_metrics_still_applies_metric_type_filter() -> None:
    from src.services.evaluation.rag_evaluation_service import rag_evaluation_service

    db = MagicMock()
    query = db.query.return_value
    joined = query.join.return_value
    filtered = joined.filter.return_value
    type_filtered = filtered.filter.return_value
    type_filtered.order_by.return_value.limit.return_value.all.return_value = []

    rag_evaluation_service.get_evaluation_metrics(
        job_id="job-1",
        organization_id="org-1",
        metric_types=["rag_triad_faithfulness"],
        db=db,
    )

    filtered.filter.assert_called_once()
