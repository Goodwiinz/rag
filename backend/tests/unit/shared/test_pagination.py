"""Unit tests for the shared pagination primitives (audit C10 pilot).

Covers:
  * PaginationParams validation via FastAPI (size > 100 -> 422, page 0 -> 422,
    size 0 -> 422, defaults, offset math).
  * Page.create's has_more correctness at page boundaries — it is *derived*
    from the true total and the returned slice, never phantom.
"""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.shared.pagination import Page, PaginationParams

pytestmark = pytest.mark.unit


# --- PaginationParams validation (via a minimal app, no DB needed) -----------


def _client() -> TestClient:
    app = FastAPI()

    @app.get("/probe")
    def probe(pagination: PaginationParams = Depends()):
        return {
            "page": pagination.page,
            "size": pagination.size,
            "offset": pagination.offset,
        }

    return TestClient(app)


def test_defaults_applied():
    resp = _client().get("/probe")
    assert resp.status_code == 200
    assert resp.json() == {"page": 1, "size": 20, "offset": 0}


def test_offset_computed_from_page_and_size():
    resp = _client().get("/probe", params={"page": 3, "size": 25})
    assert resp.status_code == 200
    # (3 - 1) * 25
    assert resp.json() == {"page": 3, "size": 25, "offset": 50}


def test_size_over_max_rejected():
    resp = _client().get("/probe", params={"size": 101})
    assert resp.status_code == 422


def test_size_max_boundary_accepted():
    resp = _client().get("/probe", params={"size": 100})
    assert resp.status_code == 200
    assert resp.json()["size"] == 100


def test_page_zero_rejected():
    resp = _client().get("/probe", params={"page": 0})
    assert resp.status_code == 422


def test_size_zero_rejected():
    resp = _client().get("/probe", params={"size": 0})
    assert resp.status_code == 422


def test_negative_page_rejected():
    resp = _client().get("/probe", params={"page": -1})
    assert resp.status_code == 422


# --- Page.create has_more correctness ----------------------------------------


def test_has_more_true_when_rows_beyond_page():
    params = PaginationParams(page=1, size=10)
    page = Page.create(items=list(range(10)), total=11, params=params)
    assert page.has_more is True
    assert page.total == 11
    assert page.page == 1
    assert page.size == 10


def test_has_more_false_on_exact_last_page():
    # total == offset + len(items): the page is exactly filled and there is
    # nothing after it — must NOT claim a phantom next page.
    params = PaginationParams(page=1, size=10)
    page = Page.create(items=list(range(10)), total=10, params=params)
    assert page.has_more is False


def test_has_more_false_on_short_final_page():
    # page 2 of a 13-row set at size 10: 3 rows returned, offset 10, 10+3 == 13.
    params = PaginationParams(page=2, size=10)
    page = Page.create(items=list(range(3)), total=13, params=params)
    assert page.has_more is False


def test_has_more_true_on_middle_page():
    # page 1 of a 13-row set: 10 returned, 10 < 13 -> more remain.
    params = PaginationParams(page=1, size=10)
    page = Page.create(items=list(range(10)), total=13, params=params)
    assert page.has_more is True


def test_empty_result_never_has_more():
    params = PaginationParams(page=1, size=20)
    page = Page.create(items=[], total=0, params=params)
    assert page.has_more is False
    assert page.total == 0
    assert page.items == []


def test_page_past_end_has_no_more():
    # Requesting page 5 of a 3-row set returns nothing and does not claim more.
    params = PaginationParams(page=5, size=20)
    page = Page.create(items=[], total=3, params=params)
    assert page.has_more is False
