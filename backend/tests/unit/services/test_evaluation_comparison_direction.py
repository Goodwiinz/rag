"""R5-M16: comparison averages mixed higher-is-better with higher-is-worse
metrics.

`compare_evaluations` averaged EvaluationMetric.value across every metric on
a job, including hallucination_rate (lower is better) alongside
answer_relevancy/faithfulness/contextual_relevancy (higher is better). A run
that got worse at hallucinating (higher hallucination_rate) inflated
baseline_score/comparison_score and could flip the reported improvement
direction. The fix scores only the higher-is-better metrics and reports the
higher-is-worse ones separately under `metric_comparisons`.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit


def _metric(metric_type: str, value: float) -> MagicMock:
    m = MagicMock()
    m.metric_type = metric_type
    m.value = value
    return m


@pytest.mark.asyncio
async def test_hallucination_rate_excluded_from_the_scored_average(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.services.evaluation.rag_evaluation_service import rag_evaluation_service

    baseline_job = MagicMock()
    baseline_job.name = "baseline"
    comparison_job = MagicMock()
    comparison_job.name = "comparison"

    # Baseline: relevancy 0.9, hallucination 0.1 (good on both axes).
    baseline_metrics = [
        _metric("rag_triad_answer_relevancy", 0.9),
        _metric("hallucination_rate", 0.1),
    ]
    # Comparison: relevancy STILL 0.9 (unchanged) but hallucination rate got
    # much WORSE (0.9). A naive mixed mean would show comparison_avg=0.9
    # (unchanged from (0.9+0.1)/2=0.5 baseline to (0.9+0.9)/2=0.9 comparison)
    # — reporting a big *improvement* for a run that got worse at
    # hallucinating and identical on relevancy.
    comparison_metrics = [
        _metric("rag_triad_answer_relevancy", 0.9),
        _metric("hallucination_rate", 0.9),
    ]

    db = MagicMock()
    db.query.return_value.filter.return_value.first.side_effect = [
        baseline_job,
        comparison_job,
    ]
    db.query.return_value.filter.return_value.all.side_effect = [
        baseline_metrics,
        comparison_metrics,
    ]

    comparison = await rag_evaluation_service.compare_evaluations(
        baseline_job_id="baseline-1",
        comparison_job_id="comparison-1",
        name="test",
        user_id="user-1",
        organization_id="org-1",
        db=db,
    )

    # Scored purely on the higher-is-better metric (answer_relevancy):
    # unchanged at 0.9 on both sides, 0% improvement — not inflated by the
    # hallucination_rate regression.
    assert comparison.baseline_score == pytest.approx(0.9)
    assert comparison.comparison_score == pytest.approx(0.9)
    assert comparison.improvement_percentage == pytest.approx(0.0)

    # The hallucination_rate regression is still visible, just reported
    # separately rather than blended into the score.
    worse = comparison.metric_comparisons["higher_is_worse_metrics"]
    assert worse["hallucination_rate"]["baseline_avg"] == pytest.approx(0.1)
    assert worse["hallucination_rate"]["comparison_avg"] == pytest.approx(0.9)
