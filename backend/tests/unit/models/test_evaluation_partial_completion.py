"""Regression guard for honest partial-completion state on EvaluationJob.

`run_rag_triad_evaluation` (tasks/evaluation_tasks.py) drops items that raise
mid-loop (`except: continue`) and, when at least one item survives, still marks
the job COMPLETED with metrics averaged over only the survivors. Before the
fix that partial run was invisible: no count of how many items were dropped.

The fix records the drop honestly by, after computing metrics, setting
`dataset_size` = total, `processed_count` = processed (via update_progress),
calling `complete_job(...)`, and THEN stamping `error_message` with a
degradation note when items failed. That ordering only works if `complete_job`
does not clear `error_message` and leaves the counts intact — this test pins
that in-memory contract (no DB session needed; the mutators are pure).
"""

import pytest

from src.models.evaluation import EvaluationJob, EvaluationStatus

pytestmark = pytest.mark.unit


def _run_completion_sequence(processed: int, total: int) -> EvaluationJob:
    """Replicate the task's completion branch on an in-memory job."""
    job = EvaluationJob()
    job.start_job()
    job.update_progress(0)

    failed = total - processed
    job.dataset_size = total
    job.update_progress(processed)
    job.complete_job(overall_score=0.8, success_rate=100.0)
    if failed > 0:
        job.error_message = (
            f"Completed with partial results: {processed}/{total} items "
            f"processed, {failed} failed"
        )
    return job


def test_partial_run_is_completed_but_records_the_drop():
    job = _run_completion_sequence(processed=2, total=10)

    # Stays COMPLETED — the partial metrics are still useful.
    assert job.status == EvaluationStatus.COMPLETED.value
    # The drop is now visible on the persisted job.
    assert job.processed_count == 2
    assert job.dataset_size == 10
    assert job.processed_count < job.dataset_size
    # complete_job must NOT wipe the degradation note set after it.
    assert job.error_message is not None
    assert "2/10" in job.error_message
    assert "8 failed" in job.error_message
    # Metrics are still recorded.
    assert job.overall_score == 0.8


def test_full_run_leaves_no_degradation_note():
    job = _run_completion_sequence(processed=10, total=10)

    assert job.status == EvaluationStatus.COMPLETED.value
    assert job.processed_count == 10
    assert job.dataset_size == 10
    # No failures → no note (a clean COMPLETED job).
    assert job.error_message is None
