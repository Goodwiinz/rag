"""Guard: KG job endpoints must not commit before enqueuing.

`create_merge_job` (POST /api/v1/merge-jobs) and `create_extraction_job`
(POST /api/v1/extraction-jobs) each committed a `ProcessingJob(status=PENDING)`
*before* calling `apply_async` — with no try/except around the enqueue:

    db.add(job)
    db.commit()          # persists PENDING, celery_task_id=NULL
    db.refresh(job)
    task = kg_..._job.apply_async(...)   # raises if broker down
    ...
    db.commit()

If `apply_async` raised (broker/Redis down), the exception propagated with the
PENDING row already committed → an orphaned `ProcessingJob(status=PENDING,
celery_task_id=NULL)` that no worker picks up and no janitor resets.

Fix: `flush` (not `commit`) before `apply_async`; the single `commit` lands only
after the enqueue succeeds. On failure the request's session closes uncommitted,
rolling back the flush — no orphan. This guard asserts neither endpoint commits
between adding the job and enqueuing it.
"""

from pathlib import Path
import re

# tests/ -> backend/
ROUTER = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "api"
    / "search"
    / "knowledge_graph.py"
)

# (function name, the qualified enqueue call that ends the pre-enqueue window)
CASES = [
    ("create_merge_job", "kg_merge_entities_job.apply_async("),
    ("create_extraction_job", "kg_extract_entities_job.apply_async("),
]


def _fn_source(name: str) -> str:
    source = ROUTER.read_text()
    start = source.index(f"def {name}(")
    m = re.search(r"\n(async def |def )", source[start + 10 :])
    end = start + 10 + m.start() if m else len(source)
    return source[start:end]


def test_no_commit_before_enqueue():
    for name, enqueue_call in CASES:
        fn = _fn_source(name)
        before = fn[fn.index("db.add(job)") : fn.index(enqueue_call)]
        assert "db.commit()" not in before, (
            f"{name} commits before {enqueue_call} — a broker failure then orphans "
            f"a PENDING ProcessingJob. Flush before enqueue, commit once after."
        )
        assert "db.flush()" in before, (
            f"{name} must flush (not commit) before {enqueue_call} so a queue "
            f"failure rolls back cleanly"
        )


def test_commit_after_enqueue():
    for name, enqueue_call in CASES:
        fn = _fn_source(name)
        after = fn[fn.index(enqueue_call) :]
        assert (
            "db.commit()" in after
        ), f"{name} must commit after {enqueue_call} succeeds"
