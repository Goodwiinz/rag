"""Round-4 WO-2 regressions for ``documents/processing.py``.

- R4-M2: ``document_id``/``job_id`` path params were typed ``str`` and
  compared directly against UUID columns; a garbage value reached asyncpg
  untouched and 500'd. Typed ``uuid.UUID`` now, so FastAPI 422s it first.
- R4-M3: ``list_processing_jobs``' ``limit``/``offset`` accepted any int,
  including 0/negative/huge, with no upstream guard.
- R4-M4: ``BatchProcessingRequest.document_ids`` had no length cap.
- R4-L1: ``retry_failed_jobs``' ``HTTPException(400)`` (missing
  ``job_ids``/``organization_wide``) was raised *inside* the ``try`` and
  swallowed by the trailing ``except Exception`` -> 500 instead of 400.
- R4-L10: ``start_document_processing`` derived organization from
  ``current_user.organization_id`` directly instead of the
  ``get_current_organization`` dependency, so an orgless user passed the
  literal string ``"None"`` through instead of getting a clean 404.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Iterator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.api.documents import processing as processing_mod
from src.core.database import get_db
from src.core.dependencies import (
    get_current_organization,
    get_current_user,
    require_admin,
)
from src.services.processing.processing_service import get_processing_service

pytestmark = pytest.mark.unit


def _user() -> MagicMock:
    u = MagicMock()
    u.id = "user-1"
    return u


def _org() -> MagicMock:
    o = MagicMock()
    o.id = uuid.uuid4()
    return o


@pytest.fixture()
def client() -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(processing_mod.router)

    user = _user()
    org = _org()

    # Async db.execute(...) result stub covering every shape the routes call:
    # scalar_one_or_none() (single-row lookups), scalar_one() (count queries),
    # and scalars().all() (list queries) all resolve to "nothing found".
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    execute_result.scalar_one.return_value = 0
    execute_result.scalars.return_value.all.return_value = []

    async_db = MagicMock()
    async_db.execute = AsyncMock(return_value=execute_result)
    async_db.commit = AsyncMock()
    async_db.rollback = AsyncMock()
    async_db.delete = AsyncMock()

    processing_service = MagicMock()
    processing_service.process_document = AsyncMock(
        side_effect=ValueError("document not found")
    )

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_organization] = lambda: org
    app.dependency_overrides[get_db] = lambda: async_db
    app.dependency_overrides[get_processing_service] = lambda: processing_service
    app.dependency_overrides[require_admin] = lambda: user

    with TestClient(app) as c:
        yield c


# --- R4-M2: garbage UUID path params -> 422 -------------------------------


@pytest.mark.parametrize("garbage", ["not-a-uuid", "12345", "'; DROP TABLE x;--"])
def test_start_processing_garbage_document_id_422(
    client: TestClient, garbage: str
) -> None:
    resp = client.post(f"/processing/documents/{garbage}/process")
    assert resp.status_code == 422


@pytest.mark.parametrize("garbage", ["not-a-uuid", "12345"])
def test_processing_status_garbage_document_id_422(
    client: TestClient, garbage: str
) -> None:
    resp = client.get(f"/processing/documents/{garbage}/status")
    assert resp.status_code == 422


@pytest.mark.parametrize("garbage", ["not-a-uuid", "12345"])
def test_job_status_garbage_job_id_422(client: TestClient, garbage: str) -> None:
    resp = client.get(f"/processing/jobs/{garbage}")
    assert resp.status_code == 422


@pytest.mark.parametrize("garbage", ["not-a-uuid", "12345"])
def test_cancel_job_garbage_job_id_422(client: TestClient, garbage: str) -> None:
    resp = client.post(f"/processing/jobs/{garbage}/cancel")
    assert resp.status_code == 422


def test_valid_uuid_document_id_passes_routing(client: TestClient) -> None:
    # process_document raises ValueError -> 400, proving routing accepted the
    # id (never reached type validation) and the handler's own error path ran.
    resp = client.post(f"/processing/documents/{uuid.uuid4()}/process")
    assert resp.status_code == 400


# --- R4-M3: limit/offset bounds --------------------------------------------


@pytest.mark.parametrize("limit", [0, -1, 1_000_000])
def test_list_jobs_invalid_limit_422(client: TestClient, limit: int) -> None:
    resp = client.get("/processing/jobs", params={"limit": limit})
    assert resp.status_code == 422


def test_list_jobs_invalid_offset_422(client: TestClient) -> None:
    resp = client.get("/processing/jobs", params={"offset": -1})
    assert resp.status_code == 422


def test_list_jobs_valid_bounds_ok(client: TestClient) -> None:
    resp = client.get("/processing/jobs", params={"limit": 200, "offset": 0})
    assert resp.status_code == 200


# --- R4-M4: batch document_ids capped at 100 -------------------------------


def test_batch_processing_over_100_ids_422(client: TestClient) -> None:
    ids = [str(uuid.uuid4()) for _ in range(101)]
    resp = client.post("/processing/batch", json={"document_ids": ids})
    assert resp.status_code == 422


def test_batch_processing_100_ids_not_rejected_for_length(client: TestClient) -> None:
    ids = [str(uuid.uuid4()) for _ in range(100)]
    resp = client.post("/processing/batch", json={"document_ids": ids})
    # Not a 422 from the length constraint (may be 200 with all-missing
    # errors, since the mocked db query returns no documents).
    assert resp.status_code == 200


# --- R4-L1: HTTPException(400) inside try must not become 500 -------------


def test_retry_missing_target_returns_400_not_500(client: TestClient) -> None:
    resp = client.post("/processing/retry", json={})
    assert resp.status_code == 400
    assert "job_ids or organization_wide" in resp.json()["detail"]


def test_retry_http_exception_direct_call_preserves_status() -> None:
    """Unit-level confirmation the fix is the ``except HTTPException: raise``
    guard, not an incidental status change elsewhere."""
    request = MagicMock(organization_wide=False, job_ids=None)
    processing_service = MagicMock()
    org = _org()

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            processing_mod.retry_failed_jobs(
                request,
                current_user=_user(),
                organization=org,
                processing_service=processing_service,
            )
        )
    assert exc_info.value.status_code == 400


# --- R4-L10: orgless user gets 404, not "None" passed downstream ----------


def test_start_processing_orgless_user_returns_404() -> None:
    """``get_current_organization`` 404s when the user has no organization;
    wiring it as a route dependency means process_document is never called
    with the string ``"None"``."""
    from src.core.dependencies import get_current_organization as real_dep

    user_without_org = MagicMock()
    user_without_org.organization = None

    with pytest.raises(HTTPException) as exc_info:
        real_dep(current_user=user_without_org)
    assert exc_info.value.status_code == 404


def test_start_processing_uses_dependency_organization_not_raw_user_field() -> None:
    """Regression for the literal bug: process_document must be called with
    the organization resolved via the dependency, not
    ``current_user.organization_id`` directly (which is ``"None"`` string for
    an orgless user rather than raising)."""
    org = _org()
    processing_service = MagicMock()
    job = MagicMock()
    job.id = uuid.uuid4()
    job.status.value = "queued"
    processing_service.process_document = AsyncMock(return_value=job)

    user = _user()
    # Deliberately mismatched from `org` to prove the org argument comes from
    # the dependency, not from the user object.
    user.organization_id = "None"

    asyncio.run(
        processing_mod.start_document_processing(
            document_id=uuid.uuid4(),
            current_user=user,
            organization=org,
            processing_service=processing_service,
        )
    )

    _, kwargs = processing_service.process_document.call_args
    assert kwargs["organization_id"] == str(org.id)
    assert kwargs["organization_id"] != "None"
