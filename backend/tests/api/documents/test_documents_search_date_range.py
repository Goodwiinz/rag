"""R4-L3 regression: ``search_documents``' ``date_range`` query param was a
free-text ``Optional[str]``, so an unrecognized value (typo, or anything not
in {last_week,last_month,last_year}) silently fell through every ``elif``
and applied no filter at all -- indistinguishable from a working filter to
the caller. It's now ``DocumentDateRange`` (validated enum, matching the
repo's "never raw strings in filters" convention), so FastAPI rejects an
unknown value with 422 before the handler runs.
"""

from __future__ import annotations

import uuid
from typing import Iterator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.documents import documents as documents_mod
from src.core.database import get_db
from src.core.dependencies import get_current_organization, get_current_user

pytestmark = pytest.mark.unit


@pytest.fixture()
def client() -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(documents_mod.router)

    user = MagicMock()
    org = MagicMock()
    org.id = uuid.uuid4()

    count_result = MagicMock()
    count_result.scalar.return_value = 0
    result_result = MagicMock()
    result_result.scalars.return_value.all.return_value = []

    db = MagicMock()
    db.execute = AsyncMock(side_effect=[count_result, result_result])

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_organization] = lambda: org
    app.dependency_overrides[get_db] = lambda: db

    with TestClient(app) as c:
        yield c


def test_unknown_date_range_rejected(client: TestClient) -> None:
    resp = client.post(
        "/documents/search", params={"query": "x", "date_range": "yesterday"}
    )
    assert resp.status_code == 422


@pytest.mark.parametrize("value", ["last_week", "last_month", "last_year"])
def test_known_date_range_accepted(client: TestClient, value: str) -> None:
    resp = client.post("/documents/search", params={"query": "x", "date_range": value})
    assert resp.status_code == 200
    assert resp.json()["search_filters"]["date_range"] == value


def test_no_date_range_accepted(client: TestClient) -> None:
    resp = client.post("/documents/search", params={"query": "x"})
    assert resp.status_code == 200
    assert resp.json()["search_filters"]["date_range"] is None
