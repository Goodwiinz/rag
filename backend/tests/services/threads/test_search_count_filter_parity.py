"""Regression: search COUNT queries must apply the same filters as the result
query.

The thread/message count builders previously applied only a subset of filters
(thread: omitted created_by_id/date_from/date_to/min_message_count; message:
omitted user_id/roles/date_from/date_to/has_citations). With any omitted filter
set, COUNT(*) over-counted vs the actual page → inflated total + phantom
has_more (pages that return nothing). Both builders now share
_apply_thread_filters / _apply_message_filters with the result builders, so the
two can't drift. These tests pin that parity.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from src.models.chat_message import MessageRole
from src.models.thread import ThreadStatus
from src.services.threads.thread_message_search_service import (
    MessageSearchFilter,
    MessageSearchRequest,
    ThreadMessageSearchService,
    ThreadSearchFilter,
    ThreadSearchRequest,
)

# Param keys that exist only on the paginated result query, never the count.
_RESULT_ONLY = {"limit", "offset"}


@pytest.mark.unit
def test_thread_count_applies_every_result_filter():
    svc = ThreadMessageSearchService()
    req = ThreadSearchRequest(
        query="machine learning",
        filters=ThreadSearchFilter(
            conversation_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            status=[ThreadStatus.ACTIVE],
            created_by_id=uuid.uuid4(),
            date_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
            date_to=datetime(2026, 6, 1, tzinfo=timezone.utc),
            min_message_count=3,
        ),
    )
    uid = uuid.uuid4()

    _, search_params = svc._build_thread_search_query("ml", req, uid)
    count_sql, count_params = svc._build_thread_count_query("ml", req, uid)

    # Every filter predicate that scopes the result set must also scope the count.
    for needle in (
        "t.conversation_id = :conversation_id",
        "c.workspace_id = :workspace_id",
        "t.status IN (",
        "t.created_by_id = :created_by_id",
        "t.created_at >= :date_from",
        "t.created_at <= :date_to",
        "t.message_count >= :min_message_count",
    ):
        assert needle in count_sql, f"count query missing predicate: {needle}"

    # Filter params must match exactly (count never carries limit/offset).
    expected = {k: v for k, v in search_params.items() if k not in _RESULT_ONLY}
    assert count_params == expected


@pytest.mark.unit
def test_message_count_applies_every_result_filter():
    svc = ThreadMessageSearchService()
    req = MessageSearchRequest(
        query="vector search",
        filters=MessageSearchFilter(
            thread_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            roles=[MessageRole.USER, MessageRole.ASSISTANT],
            date_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
            date_to=datetime(2026, 6, 1, tzinfo=timezone.utc),
            has_citations=True,
        ),
    )
    uid = uuid.uuid4()

    _, search_params = svc._build_message_search_query("vs", req, uid)
    count_sql, count_params = svc._build_message_count_query("vs", req, uid)

    for needle in (
        "m.thread_id = :thread_id",
        "t.conversation_id = :conversation_id",
        "c.workspace_id = :workspace_id",
        "m.user_id = :user_id",
        "m.role IN (",
        "m.created_at >= :date_from",
        "m.created_at <= :date_to",
        "EXISTS (SELECT 1 FROM citations cit",
    ):
        assert needle in count_sql, f"count query missing predicate: {needle}"

    expected = {k: v for k, v in search_params.items() if k not in _RESULT_ONLY}
    assert count_params == expected


@pytest.mark.unit
def test_has_citations_false_uses_not_exists_in_count():
    svc = ThreadMessageSearchService()
    req = MessageSearchRequest(
        query="x",
        filters=MessageSearchFilter(has_citations=False),
    )
    count_sql, _ = svc._build_message_count_query("x", req, uuid.uuid4())
    assert "NOT EXISTS (SELECT 1 FROM citations cit" in count_sql
