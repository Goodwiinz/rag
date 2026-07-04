"""Legacy shadow agent threads must be excluded from FTS (PR 4a).

Before the server-canonical cutover every /chat turn was double-written:
once into the workspace thread and once into a shadow agent thread
(``rag_document_scope`` containing ``{"source": "agent"}``). Search hit
both copies. The exclusion predicate must appear in ALL FOUR builders —
the repo rule is that count queries apply the same filters as result
queries, or ``total``/``has_more`` over-report.
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

_EXCLUSION = (
    "NOT (COALESCE(t.rag_document_scope, '{}'::jsonb) "
    '@> \'{"source": "agent"}\'::jsonb)'
)


def _svc():
    return ThreadMessageSearchService()


def test_thread_search_excludes_legacy_agent_threads():
    sql, _ = _svc()._build_thread_search_query(
        "neural", ThreadSearchRequest(query="neural"), uuid4()
    )
    assert _EXCLUSION in sql


def test_thread_count_excludes_legacy_agent_threads():
    sql, _ = _svc()._build_thread_count_query(
        "neural", ThreadSearchRequest(query="neural"), uuid4()
    )
    assert _EXCLUSION in sql


def test_message_search_excludes_legacy_agent_threads():
    sql, _ = _svc()._build_message_search_query(
        "neural", MessageSearchRequest(query="neural"), uuid4()
    )
    assert _EXCLUSION in sql


def test_message_count_excludes_legacy_agent_threads():
    sql, _ = _svc()._build_message_count_query(
        "neural", MessageSearchRequest(query="neural"), uuid4()
    )
    assert _EXCLUSION in sql
