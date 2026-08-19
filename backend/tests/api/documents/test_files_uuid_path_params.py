"""R4-M2 regression: file_id path params were typed ``str`` and compared
directly against a UUID column. A non-UUID value (e.g. ``"not-a-uuid"``)
reached asyncpg untouched and raised a DataError, which the endpoint's own
``except Exception`` (or no handler at all) turned into a 500. Typing the
path param ``uuid.UUID`` lets FastAPI reject it at the routing layer with a
422 before any query runs.

These tests mount only ``files.py``'s router (not the full app) behind a
minimal FastAPI instance with its dependencies overridden, so a garbage path
segment never reaches a real database.
"""

from __future__ import annotations

import uuid
from typing import Iterator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.documents import files as files_mod
from src.core.database import get_db
from src.core.dependencies import get_current_organization, get_current_user
from src.services.documents.file_service import get_file_service

pytestmark = pytest.mark.unit

GARBAGE_IDS = ["not-a-uuid", "12345", "'; DROP TABLE documents;--"]

FILE_ID_ENDPOINTS = [
    ("GET", "/files/{file_id}"),
    ("GET", "/files/{file_id}/download"),
    ("PUT", "/files/{file_id}"),
    ("DELETE", "/files/{file_id}"),
    ("GET", "/files/{file_id}/content"),
    ("GET", "/files/{file_id}/metadata"),
    ("POST", "/files/{file_id}/reprocess"),
]


@pytest.fixture()
def client() -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(files_mod.router)

    user = MagicMock()
    user.id = "user-1"

    org = MagicMock()
    org.id = uuid.uuid4()

    db = MagicMock()
    db.execute = AsyncMock(
        return_value=MagicMock(**{"scalars.return_value.first.return_value": None})
    )

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_organization] = lambda: org
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_file_service] = lambda: MagicMock()

    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize("method,path_template", FILE_ID_ENDPOINTS)
@pytest.mark.parametrize("garbage", GARBAGE_IDS)
def test_garbage_file_id_returns_422_not_500(
    client: TestClient, method: str, path_template: str, garbage: str
) -> None:
    path = path_template.format(file_id=garbage)
    resp = client.request(method, path)
    assert resp.status_code == 422, (
        f"{method} {path} returned {resp.status_code}, expected 422 for a "
        f"non-UUID file_id (body={resp.text!r})"
    )


@pytest.mark.parametrize("method,path_template", FILE_ID_ENDPOINTS)
def test_valid_uuid_file_id_reaches_404_not_422(
    client: TestClient, method: str, path_template: str
) -> None:
    """A well-formed but non-existent UUID must route past validation and hit
    the normal "not found" path, proving the type change didn't also reject
    legitimate ids."""
    path = path_template.format(file_id=str(uuid.uuid4()))
    resp = client.request(method, path)
    assert resp.status_code != 422
