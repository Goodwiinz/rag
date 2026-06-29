"""Regression: search suggestions must be scoped to the caller's org.

`_get_search_suggestions` derives suggestions from document *titles* via a
substring LIKE. The query previously had no organization_id filter, so when a
user's search returned <5 results the suggestions leaked other tenants'
document titles. The fix scopes the query to organization_id and returns no
suggestions when the org is unknown (rather than disclosing across tenants).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.services.search.fulltext_search_service import FullTextSearchService


@pytest.mark.unit
def test_no_org_returns_no_suggestions_without_querying():
    svc = FullTextSearchService()
    db = MagicMock()

    out = svc._get_search_suggestions("report", db, organization_id=None)

    assert out == []
    # Must not run an unscoped query when it can't scope safely.
    db.execute.assert_not_called()


@pytest.mark.unit
def test_suggestions_query_is_org_scoped():
    svc = FullTextSearchService()
    db = MagicMock()
    db.execute.return_value = iter([])  # no rows

    svc._get_search_suggestions("report", db, organization_id="org-1")

    db.execute.assert_called_once()
    sql_clause, params = db.execute.call_args.args
    assert "organization_id = :organization_id" in str(sql_clause)
    assert params["organization_id"] == "org-1"
    # Still a substring search on the query, still completed-only.
    assert params["query_pattern"] == "%report%"


@pytest.mark.unit
def test_suggestions_returned_from_rows():
    svc = FullTextSearchService()
    db = MagicMock()
    row_a = MagicMock()
    row_a.suggestion = "quarterly report"
    row_b = MagicMock()
    row_b.suggestion = ""  # falsy → filtered out
    db.execute.return_value = iter([row_a, row_b])

    out = svc._get_search_suggestions("report", db, organization_id="org-1")

    assert out == ["quarterly report"]
