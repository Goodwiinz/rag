"""Guard: reprocess_document enqueues post-commit (no pre-commit race, no orphan).

`reprocess_document` (api/documents/documents.py) resets the document to PENDING
and creates a `ProcessingJob`, then enqueues `process_document_ingestion`. It now
routes that enqueue through `enqueue_after_commit(...)`, which fires `.delay(...)`
only *after* the surrounding commit succeeds and drops it entirely if the
transaction rolls back — closing the worker-reads-before-commit race without the
old orphan risk. A broker outage in the narrow post-commit window leaves the job
PENDING/celery_task_id=NULL, which the lost-job reconciler (src.tasks.reconcile_jobs)
re-enqueues.

This guard asserts the endpoint uses the post-commit helper and no longer issues
a raw pre-commit `process_document_ingestion.delay(...)`, and that a commit is
present.
"""

import re
from pathlib import Path

# tests/ -> backend/
ROUTER = (
    Path(__file__).resolve().parents[1] / "src" / "api" / "documents" / "documents.py"
)


def _reprocess_fn() -> str:
    source = ROUTER.read_text()
    start = source.index("async def reprocess_document")
    m = re.search(r"\n(async def |def )", source[start + 10 :])
    end = start + 10 + m.start() if m else len(source)
    return source[start:end]


def test_enqueues_through_post_commit_helper():
    fn = _reprocess_fn()
    assert "enqueue_after_commit(" in fn, (
        "reprocess_document must enqueue via enqueue_after_commit(...) so the "
        "Celery dispatch fires only after the commit (no worker-reads-before-"
        "commit race, no orphaned PENDING job on rollback)"
    )


def test_no_raw_precommit_delay():
    fn = _reprocess_fn()
    assert "process_document_ingestion.delay(" not in fn, (
        "reprocess_document must not raw-.delay() the ingestion task before "
        "commit; route it through enqueue_after_commit(...)"
    )


def test_commit_present():
    fn = _reprocess_fn()
    assert "await db.commit()" in fn, "reprocess_document must commit the job insert"
