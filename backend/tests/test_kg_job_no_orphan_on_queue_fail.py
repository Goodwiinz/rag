"""Guard: add_document_to_project must not commit the KG job before enqueuing.

`add_document_to_project` (api/research/projects.py) auto-queues an
entity-extraction `ProcessingJob`. It previously did:

    db.add(kg_job)
    await db.commit()          # <-- persists status=PENDING, celery_task_id=NULL
    ...
    task = kg_extract_entities_job.apply_async(...)   # can raise if broker down
    ...
    except Exception:
        await db.rollback()    # cannot undo the already-committed row above

If `apply_async` raised (broker/Redis blip), the rollback could not undo the
committed row, and the handler still returned HTTP 201 — leaving an orphaned
`ProcessingJob(status=PENDING, celery_task_id=NULL)` that is never enqueued and
never reaped.

Fix: `flush` (not `commit`) before `apply_async`, then a single `commit` after
the task id is set — so a queue failure rolls the job back cleanly. This source
guard asserts no `commit` sits between adding the KG job and enqueuing it.
"""

from pathlib import Path

# tests/ -> backend/
ROUTER = (
    Path(__file__).resolve().parents[1] / "src" / "api" / "research" / "projects.py"
)


def _kg_queue_block() -> str:
    """The stretch from adding the KG job to enqueuing it."""
    source = ROUTER.read_text()
    start = source.index("db.add(kg_job)")
    # the actual enqueue call, not the word "apply_async" in a comment
    end = source.index("kg_extract_entities_job.apply_async(", start)
    return source[start:end]


def test_no_commit_between_kg_job_add_and_enqueue():
    block = _kg_queue_block()
    assert "await db.commit()" not in block, (
        "add_document_to_project commits the KG ProcessingJob before apply_async; "
        "a broker failure then orphans a PENDING/celery_task_id=NULL row that the "
        "rollback cannot undo. Flush before enqueue and commit once afterwards."
    )


def test_kg_job_flushed_before_enqueue():
    block = _kg_queue_block()
    assert "await db.flush()" in block, (
        "add_document_to_project must flush (not commit) to populate kg_job.id "
        "before apply_async, so a queue failure rolls back without an orphan"
    )
