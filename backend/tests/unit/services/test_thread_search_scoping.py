"""Thread/message search must scope results to the caller's workspaces.

The raw-SQL builders accepted ``user_id`` but never applied it, so any
authenticated user could full-text search every workspace's threads and
message content across all tenants. These tests pin the access predicate
(owner / public / active member) and its bound param into every builder.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.services.threads.thread_message_search_service import (
    MessageSearchRequest,
    ThreadSearchRequest,
    ThreadMessageSearchService,
)

pytestmark = pytest.mark.unit

_ACCESS_MARKERS = (
    "w.owner_id = :access_user_id",
    "w.is_public = true",
    "workspace_members wm",
)


def _svc():
    return ThreadMessageSearchService()


def _assert_scoped(sql: str, params: dict, user_id):
    for marker in _ACCESS_MARKERS:
        assert marker in sql, f"missing access marker {marker!r}"
    assert params["access_user_id"] == str(user_id)


def test_thread_search_query_is_scoped():
    uid = uuid4()
    sql, params = _svc()._build_thread_search_query(
        "neural", ThreadSearchRequest(query="neural"), uid
    )
    _assert_scoped(sql, params, uid)


def test_thread_count_query_is_scoped():
    uid = uuid4()
    sql, params = _svc()._build_thread_count_query(
        "neural", ThreadSearchRequest(query="neural"), uid
    )
    _assert_scoped(sql, params, uid)


def test_message_search_query_is_scoped():
    uid = uuid4()
    sql, params = _svc()._build_message_search_query(
        "neural", MessageSearchRequest(query="neural"), uid
    )
    _assert_scoped(sql, params, uid)


def test_message_count_query_is_scoped():
    uid = uuid4()
    sql, params = _svc()._build_message_count_query(
        "neural", MessageSearchRequest(query="neural"), uid
    )
    _assert_scoped(sql, params, uid)


def test_message_author_filter_does_not_collide_with_access_param():
    """The message-author search filter binds ``:user_id``; the access
    predicate binds ``:access_user_id`` — both must be present and distinct."""
    author_id = uuid4()
    caller_id = uuid4()
    sql, params = _svc()._build_message_search_query(
        "neural",
        MessageSearchRequest(query="neural", filters={"user_id": author_id}),
        caller_id,
    )
    assert params["access_user_id"] == str(caller_id)
    assert params["user_id"] == str(author_id)
    assert "m.user_id = :user_id" in sql
