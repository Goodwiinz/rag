"""Tests for the integrity-check upsert and score readback (R4-L5).

Covers the on_conflict_do_update statement builder directly: calling it twice
for the same document_id+method must target one row and carry the updated
values, without racing a select-then-update/insert (which could raise
MultipleResultsFound or IntegrityError under concurrency).

Also covers the GET /integrity-score reader: once the upsert conflicts on
(document_id, method) rather than document_id alone, a document can end up
with more than one IntegrityScore row (one per method). The reader must pick
the most recent one (order_by + limit(1)), not scalar_one_or_none() on
document_id alone -- the latter 500s with MultipleResultsFound the moment a
second method's row exists, the exact class of failure R4-L5 was filed for.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

from src.api.documents import integrity as integrity_mod
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
    stmt = build_integrity_upsert_stmt(
        document_id, _result(0.3), datetime.now(timezone.utc)
    )
    sql = _compiled_sql(stmt)

    assert "INSERT INTO INTEGRITY_SCORES" in sql
    assert "ON CONFLICT (DOCUMENT_ID, METHOD) DO UPDATE" in sql


def test_upsert_set_clause_updates_mutable_fields_not_the_conflict_key():
    document_id = uuid4()
    stmt = build_integrity_upsert_stmt(
        document_id, _result(0.7), datetime.now(timezone.utc)
    )
    sql = _compiled_sql(stmt)

    for field in (
        "AI_PROBABILITY",
        "HUMAN_PROBABILITY",
        "ANALYZED_AT",
        "SEGMENT_SCORES",
    ):
        assert f"{field} = EXCLUDED.{field}" in sql
    # document_id/method are the conflict target: never rewritten by the SET clause.
    assert "SET DOCUMENT_ID" not in sql
    assert "SET METHOD" not in sql


def test_upsert_set_clause_refreshes_updated_at():
    """BaseModel's onupdate=... never fires for a raw ON CONFLICT DO UPDATE
    (no ORM UPDATE runs), so updated_at must be set explicitly or it freezes
    at row-creation time forever."""
    document_id = uuid4()
    stmt = build_integrity_upsert_stmt(
        document_id, _result(0.5), datetime.now(timezone.utc)
    )
    sql = _compiled_sql(stmt)
    # Set to a bound literal (the route's own datetime.now(timezone.utc)),
    # not EXCLUDED.updated_at -- IntegrityScore has no updated_at input column.
    assert "UPDATED_AT = " in sql
    assert "UPDATED_AT = EXCLUDED.UPDATED_AT" not in sql


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
    assert (
        stmt1.compile().params["document_id"]
        == stmt2.compile().params["document_id"]
        == document_id
    )


def test_get_integrity_score_query_orders_by_recency_and_limits_to_one():
    """The GET reader must pick the newest row via ORDER BY analyzed_at DESC
    LIMIT 1 -- not scalar_one_or_none() over document_id alone, which raises
    MultipleResultsFound once a document has scores under two methods."""
    document_id = uuid.uuid4()

    document = MagicMock()
    doc_result = MagicMock()
    doc_result.scalar_one_or_none.return_value = document

    score = MagicMock()
    score.document_id = document_id
    score.ai_probability = 0.42
    score.human_probability = 0.58
    score.method = "roberta-base-openai-detector"
    score.analyzed_at = datetime.now(timezone.utc)
    score.segment_scores = []
    score_result = MagicMock()
    score_result.scalars.return_value.first.return_value = score

    db = MagicMock()
    db.execute = AsyncMock(side_effect=[doc_result, score_result])

    current_user = MagicMock()
    organization = MagicMock()

    asyncio.run(
        integrity_mod.get_integrity_score(
            document_id=document_id,
            current_user=current_user,
            organization=organization,
            db=db,
        )
    )

    score_stmt = db.execute.await_args_list[1].args[0]
    sql = str(score_stmt.compile(dialect=postgresql.dialect())).upper()
    assert "ORDER BY INTEGRITY_SCORES.ANALYZED_AT DESC" in sql
    assert "LIMIT" in sql


def test_sixth_integrity_check_within_a_minute_is_rate_limited():
    """5/min per user (R4-L5). Drives the route function directly with a
    mocked service + db, same user each call. Swaps in a fresh
    InMemoryRateLimiter for the duration of the test so the assertion is
    deterministic regardless of whether this environment's REDIS_URL points
    at a reachable Redis (create_rate_limiter prefers Redis when configured,
    and RedisRateLimiter deliberately fails open when unreachable -- R4-L11)."""
    from src.core.rate_limit import InMemoryRateLimiter

    document_id = uuid4()
    current_user = MagicMock()
    current_user.id = "rate-limit-test-user"
    organization = MagicMock()

    document = MagicMock()
    document.content_text = "some text to analyze"
    document.title = "title"
    doc_result = MagicMock()
    doc_result.scalar_one_or_none.return_value = document

    db = MagicMock()
    db.execute = AsyncMock(return_value=doc_result)
    db.commit = AsyncMock()

    async def _call():
        with patch.object(
            integrity_mod._service,
            "analyze",
            AsyncMock(return_value=_result(0.1)),
        ):
            return await integrity_mod.trigger_integrity_check(
                document_id=document_id,
                current_user=current_user,
                organization=organization,
                db=db,
            )

    async def _run():
        for _ in range(5):
            await _call()
        with pytest.raises(HTTPException) as exc_info:
            await _call()
        assert exc_info.value.status_code == 429

    with patch.object(
        integrity_mod,
        "_integrity_rate_limiter",
        InMemoryRateLimiter(
            max_attempts=integrity_mod._INTEGRITY_RATE_LIMIT_RPM, window_minutes=1
        ),
    ):
        asyncio.run(_run())
