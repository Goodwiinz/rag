"""Guard: add_document_to_project enqueues the KG job after commit.

`add_document_to_project` (api/research/projects.py) auto-queues an
entity-extraction `ProcessingJob`. It previously flushed, then called
`kg_extract_entities_job.apply_async(...)` *before* the commit and read the
returned `task.id` into `celery_task_id` in the same transaction:

    db.add(kg_job)
    await db.flush()
    task = kg_extract_entities_job.apply_async(...)   # can raise if broker down
    kg_job.celery_task_id = task.id                   # pre-commit readback
    await db.commit()

That flush-before-enqueue shape avoided the orphan-on-broker-failure case but
left the worker-reads-before-commit race: a fast worker could pick up the job
before the row was durable.

Fix: route the enqueue through `enqueue_after_commit_apply_async(...)`, which
fires `apply_async` only *after* the commit succeeds and drops it entirely if
the transaction rolls back. The row stays PENDING with `celery_task_id=NULL`
until the worker stamps it via `start_job`; a broker outage in the post-commit
window is recovered by the lost-job reconciler (src.tasks.reconcile_jobs), which
treats PENDING/celery_task_id=NULL as maybe-lost and re-enqueues.

This guard asserts the post-commit helper is used, and that no raw pre-commit
`apply_async` or `kg_job.celery_task_id` readback remains.
"""

from pathlib import Path

# tests/ -> backend/
ROUTER = (
    Path(__file__).resolve().parents[1] / "src" / "api" / "research" / "projects.py"
)


def _kg_block() -> str:
    """The stretch from adding the KG job to the commit that persists it."""
    source = ROUTER.read_text()
    start = source.index("db.add(kg_job)")
    end = source.index("kg_job_id = str(kg_job.id)")
    return source[start:end]


def test_enqueues_through_post_commit_apply_async_helper():
    block = _kg_block()
    assert "enqueue_after_commit_apply_async(" in block, (
        "add_document_to_project must enqueue the KG job via "
        "enqueue_after_commit_apply_async(...) so apply_async fires only after "
        "the commit (no worker-reads-before-commit race)"
    )


def test_no_raw_precommit_apply_async():
    block = _kg_block()
    assert "kg_extract_entities_job.apply_async(" not in block, (
        "add_document_to_project must not raw-apply_async the KG task before "
        "commit; route it through enqueue_after_commit_apply_async(...)"
    )


def test_no_precommit_celery_task_id_readback():
    block = _kg_block()
    assert "kg_job.celery_task_id" not in block, (
        "celery_task_id must not be persisted at create time — apply_async now "
        "fires post-commit (its task id is unavailable pre-commit) and the "
        "worker stamps celery_task_id via start_job. The create-time NULL is "
        "correct: the lost-job reconciler treats PENDING/celery_task_id=NULL as "
        "maybe-lost and re-enqueues."
    )
