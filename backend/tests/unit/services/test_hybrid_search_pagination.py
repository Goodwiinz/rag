"""Regression: hybrid search returns the true post-filter total for pagination.

_apply_final_filtering used to return only the sliced page, and callers computed
has_more = len(page) >= limit — wrong (false "next page" on a full last page;
early stop dropping results when filtering thinned a page). It now returns
(page, total_after_filter) so callers compute has_more from the real total.
"""

from types import SimpleNamespace

import pytest

from src.services.search.hybrid_search_service import HybridSearchService


def _raw(i: int):
    sr = SimpleNamespace(
        title=f"title {i}",
        content_preview=f"content {i}",
        relevance_score=0.0,
        metadata={},
        tags=[],
    )
    return SimpleNamespace(
        search_result=sr,
        relevance_score=1.0 - i * 0.01,
        metadata={},
        document_id=f"doc-{i}",
    )


@pytest.mark.unit
def test_apply_final_filtering_returns_page_and_total():
    svc = HybridSearchService(db=None)
    fused = [_raw(i) for i in range(5)]

    req = SimpleNamespace(filters=None, offset=0, limit=2)
    page, total = svc._apply_final_filtering(
        fused, req, organization_id="org-1", db=None
    )
    assert len(page) == 2
    assert total == 5  # full post-filter count, not the page size
    # Caller computes has_more = total > offset + limit → 5 > 2 → True.

    # Last page: exactly one item remains; has_more would be 5 > 6 → False.
    req_last = SimpleNamespace(filters=None, offset=4, limit=2)
    page_last, total_last = svc._apply_final_filtering(
        fused, req_last, organization_id="org-1", db=None
    )
    assert len(page_last) == 1
    assert total_last == 5
