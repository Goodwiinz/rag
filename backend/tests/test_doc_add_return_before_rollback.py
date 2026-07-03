"""Guard: add_document_to_project must not read ORM attrs after the KG rollback.

`add_document_to_project` adds a document (committed), then best-effort queues a
KG entity-extraction job. If that queueing fails, its `except` calls
`db.rollback()`, which **expires** `collection_doc`/`document`. The success
response is returned *after* that block. Previously the return read
`collection_doc.created_at` / `document.*` inline — on the KG-failure path those
attributes were expired, so accessing them triggered an async lazy-load
(`MissingGreenlet`), which the outer `except` turned into HTTP 500
"Failed to add document" — even though the document had already been added.

Fix: build the response payload from the ORM objects *before* the KG block
(while they are fresh) and only attach `kg_job_id` afterwards, so the return
never touches an expired ORM attribute.

This guard asserts the response is built before the KG block and the handler
returns that captured payload rather than re-reading the ORM objects.
"""

from pathlib import Path

# tests/ -> backend/
ROUTER = (
    Path(__file__).resolve().parents[1] / "src" / "api" / "research" / "projects.py"
)


def _add_document_fn() -> str:
    source = ROUTER.read_text()
    start = source.index("async def add_document_to_project")
    end = source.index("async def", start + 10)
    return source[start:end]


def test_response_built_before_kg_block():
    fn = _add_document_fn()
    resp_build = fn.index("response = {")
    kg_block = fn.index("kg_job_id: Optional[str] = None")
    assert resp_build < kg_block, (
        "the response payload must be built before the KG-queue block, whose "
        "rollback expires the ORM objects the response reads"
    )


def test_no_orm_read_after_kg_enqueue():
    fn = _add_document_fn()
    enqueue = fn.index("apply_async")
    # collection_doc.created_at is the tell-tale expired-lazy-load read; it must
    # only appear before the enqueue (in the pre-built response), never after.
    assert fn.rindex("collection_doc.created_at") < enqueue, (
        "collection_doc.created_at is read after the KG enqueue/rollback — on the "
        "failure path this triggers a MissingGreenlet lazy-load and a false 500"
    )
    assert "return response" in fn, "handler must return the pre-built response dict"
