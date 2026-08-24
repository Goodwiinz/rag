"""PR8-10 (audit R5-M10/M11/L7/L9/L11/L15/L17/L19/L23-refuted, R6-L7/L8/L9/L21/L23/L24) guards."""

from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]


def _read(rel: str) -> str:
    return (BACKEND_ROOT / rel).read_text()


# R5-M10
def test_thread_context_route_unwraps_service_shape() -> None:
    api = _read("src/api/threads/threads.py")
    blk = api[api.find("async def get_thread_context") :]
    assert "context is None" in blk[:900]
    assert "metadata.get(" in blk[:1400]
    svc = _read("src/services/threads/chat_service.py")
    ctx = svc[svc.find("async def get_thread_context") :]
    assert "return None\n\n        messages = []" in ctx


# R5-M11
def test_feedback_commit_after_thread_check() -> None:
    svc = _read("src/services/threads/chat_service.py")
    fb = svc[svc.find("async def update_message_feedback") :]
    assert "flush()" in fb[:1200] and "commit()" not in fb[:800]
    api = _read("src/api/threads/threads.py")
    seg = api[
        api.find("async def update_message_feedback") : api.rfind("@router.delete(")
    ]
    assert "await db.commit()" in seg
    assert "await db.rollback()" in seg


# R5-L7
def test_conversation_counts_exclude_deleted_threads() -> None:
    src = _read("src/services/threads/conversation_service.py")
    agg = src[src.find("agg_stmt = (") :]
    assert "Thread.is_deleted == False" in agg[:600]


# R5-L8
def test_conversation_search_escapes_like() -> None:
    for rel in (
        "src/services/threads/chat_service.py",
        "src/services/threads/conversation_service.py",
    ):
        src = _read(rel)
        assert "_escape_like" in src
        assert 'ilike(f"%{query}%")' not in src
        assert 'pattern = f"%{search_query}%"' not in src


# R5-L9
def test_add_member_validates_target_user() -> None:
    src = _read("src/services/threads/workspace_service.py")
    add = src[src.find("async def add_member") :]
    assert "Target user does not exist" in add[:1500]


# R5-L11
def test_workspace_quota_cap() -> None:
    src = _read("src/services/threads/workspace_service.py")
    cw = src[src.find("async def create_workspace") :]
    assert "MAX_WORKSPACES_PER_ORG" in cw[:2000]
    assert _read("src/core/config.py").count("MAX_WORKSPACES_PER_ORG") >= 1


# R5-L15 — already SQL-aggregated upstream; assert no full-row load
def test_metrics_summary_is_sql_aggregate() -> None:
    src = _read("src/api/infrastructure/evaluation.py")
    blk = src[src.find("async def get_metrics_summary") :]
    assert "func.count(EvaluationMetric.id)" in blk[:2500]
    assert ".all()\n        )" in blk  # aggregates, not ORM rows loop


# R5-L17
def test_orphan_citations_fail_closed() -> None:
    src = _read("src/api/research/citations.py")
    af = src[src.find("access_filter = or_(") :]
    # R5-L17 final: no creator column exists, so orphans match nothing —
    # fail-closed beats world-readable.
    assert "document_id.is_(None), Citation.message_id.is_(None)" not in af[:600]
    assert "R5-L17" in af[:800]


# R5-L19
def test_export_does_not_read_empty_evidence_table() -> None:
    src = _read("src/services/research_engine/export_service.py")
    assert "ResearchEvidence" not in src
    assert "evidence_list: list = []" in src


# R6-L7
def test_note_payload_bounds() -> None:
    src = _read("src/shared/research_schemas.py")
    nc = src[src.find("class ProjectNoteCreate") : src.find("class ProjectNoteUpdate")]
    assert "max_length=200_000" in nc
    assert "max_length=100" in nc
    dr = _read("src/api/research/drafts.py")
    assert "Maximum 10 items" in dr or "max_length=500" in dr


# R6-L8
def test_draft_export_filename_and_latex_escape() -> None:
    src = _read("src/services/research/draft_generation_service.py")
    assert "_safe_filename(draft.title" in src
    assert "_latex_escape(markdown_content)" in src
    assert "draft.title.replace(' ', '_')" not in src


# R6-L9
def test_relationship_type_typed_confidence_bounded() -> None:
    src = _read("src/shared/research_schemas.py")
    blk = src[src.find("class CitationRelationshipCreate") :]
    assert "relationship_type: CitationRelationshipType" in blk[:700]
    assert "allow_inf_nan=False" in blk[:900]
