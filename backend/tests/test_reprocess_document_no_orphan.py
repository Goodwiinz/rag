"""Guard: reprocess_document must not commit before the Celery enqueue.

`reprocess_document` (api/documents/documents.py) reset the document's status to
PENDING and committed it, then created a `ProcessingJob(status=PENDING)` and
committed that too — all BEFORE calling `process_document_ingestion.delay(...)`.

If `.delay()` raised (broker/Redis down), the `except`'s `db.rollback()` could
not undo the two prior commits, leaving:
  - an orphaned `ProcessingJob(status=PENDING, celery_task_id=NULL)` no worker
    ever picks up (no reaper resets PENDING jobs), and
  - the document stranded in PENDING with its prior (e.g. COMPLETED) status lost,
while the client received a misleading HTTP 500.

Fix (mirrors the KG-job fix): `flush` (not `commit`) the status reset and the job
insert, enqueue, then a single `commit` — so a broker failure rolls both back
cleanly. This guard asserts no `commit` sits between the try and the enqueue, and
that a commit follows it.
"""

from pathlib import Path
import re

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


def test_no_commit_before_enqueue():
    fn = _reprocess_fn()
    enqueue = fn.index("process_document_ingestion.delay(")
    before = fn[fn.index("try:") : enqueue]
    assert "await db.commit()" not in before, (
        "reprocess_document commits before the Celery enqueue; a broker failure "
        "then orphans a PENDING job and strands the document in PENDING. Flush "
        "before enqueue and commit once afterwards."
    )


def test_commit_after_enqueue():
    fn = _reprocess_fn()
    enqueue = fn.index("process_document_ingestion.delay(")
    after = fn[enqueue:]
    assert "await db.commit()" in after, (
        "reprocess_document must commit after the enqueue succeeds so a broker "
        "failure rolls back the status reset and job insert"
    )
