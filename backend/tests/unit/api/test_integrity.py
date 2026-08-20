"""Tests for the integrity-check upsert (R4-L5).

Covers the on_conflict_do_update statement builder directly: calling it twice
for the same document_id+method must target one row and carry the updated
values, without racing a select-then-update/insert (which could raise
MultipleResultsFound or IntegrityError under concurrency).
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from src.api.documents.integrity import build_integrity_upsert_stmt

pytestmark = pytest.mark.unit


def _result(ai_probability: float) -> dict:
    return {
        "ai_probability": ai_probability,
        "human_probability": 1.0 - ai_probability,
        "method": "roberta-base-openai-detector",
        "segment_scores": [{"text_preview": "hi", "ai_probability": ai_probability}],
    }


def _compiled_sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect())).upper()


def test_upsert_is_single_statement_conflicting_on_document_and_method():
    document_id = uuid4()
    stmt = build_integrity_upsert_stmt(document_id, _result(0.3), datetime.now(timezone.utc))
    sql = _compiled_sql(stmt)

    assert "INSERT INTO INTEGRITY_SCORES" in sql
    assert "ON CONFLICT (DOCUMENT_ID, METHOD) DO UPDATE" in sql


def test_upsert_set_clause_updates_mutable_fields_not_the_conflict_key():
    document_id = uuid4()
    stmt = build_integrity_upsert_stmt(document_id, _result(0.7), datetime.now(timezone.utc))
    sql = _compiled_sql(stmt)

    for field in ("AI_PROBABILITY", "HUMAN_PROBABILITY", "ANALYZED_AT", "SEGMENT_SCORES"):
        assert f"{field} = EXCLUDED.{field}" in sql
    # document_id/method are the conflict target: never rewritten by the SET clause.
    assert "SET DOCUMENT_ID" not in sql
    assert "SET METHOD" not in sql


def test_repeated_upsert_for_same_document_targets_one_row():
    """Two builds for the same document_id (e.g. a re-run integrity check) must
    both resolve to an upsert keyed on that document+method, so the second
    execution updates the first row in place instead of racing an insert."""
    document_id = uuid4()
    analyzed_at = datetime.now(timezone.utc)

    stmt1 = build_integrity_upsert_stmt(document_id, _result(0.2), analyzed_at)
    stmt2 = build_integrity_upsert_stmt(document_id, _result(0.9), analyzed_at)

    for stmt in (stmt1, stmt2):
        sql = _compiled_sql(stmt)
        assert "ON CONFLICT (DOCUMENT_ID, METHOD) DO UPDATE" in sql

    # Different result payloads still bind to the same document_id parameter.
    assert stmt1.compile().params["document_id"] == stmt2.compile().params["document_id"] == document_id
