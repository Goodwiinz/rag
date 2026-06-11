"""MetricsService.ingest_event maps an API event payload onto the canonical
AnalyticsEvent ORM model (src/models/analytics_event.py).

Columns get dedicated fields (event_type/event_name/event_category/user_id/
session_id/organization_id/value/tags); the remaining payload keys
(request_id/properties/country/city/timezone) are tucked into the flexible
``event_data`` JSON. After persisting, ingest_event fans out to
``_extract_metrics_from_event``.

These tests mock only the session boundary (get_async_session) and the
downstream extraction hook; the mapping itself runs for real, so a regression in
the column/JSON split is caught behaviorally.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit


def _patch_session_and_extract(monkeypatch):
    """Patch get_async_session with an async-CM yielding a mock session, and
    stub _extract_metrics_from_event. Returns (service, mock_session,
    extract_mock)."""
    from src.services.analytics import metrics_service as metrics_module

    service = metrics_module.metrics_service

    mock_session = MagicMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    @asynccontextmanager
    async def fake_get_async_session():
        yield mock_session

    monkeypatch.setattr(metrics_module, "get_async_session", fake_get_async_session)

    extract_mock = AsyncMock()
    monkeypatch.setattr(service, "_extract_metrics_from_event", extract_mock)

    return service, mock_session, extract_mock


@pytest.mark.asyncio
async def test_ingest_event_maps_payload_onto_canonical_event(monkeypatch):
    from src.models.analytics_event import AnalyticsEvent, EventType

    service, mock_session, extract_mock = _patch_session_and_extract(monkeypatch)

    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    payload = {
        "event_type": EventType.SEARCH_QUERY,  # valid canonical enum member
        "event_name": "search_query",
        "event_category": "search",
        "user_id": user_id,
        "session_id": "sess-123",
        "organization_id": org_id,  # required, non-null
        "value": 7.0,
        "tags": ["alpha", "beta"],
        # tucked-away fields → event_data JSON, not their own columns
        "request_id": "req-xyz",
        "properties": {"q": "neural nets"},
        "country": "US",
        "city": "Boston",
        "timezone": "America/New_York",
    }

    ok = await service.ingest_event(payload)
    assert ok is True

    # Session boundary: exactly one add + one commit.
    mock_session.add.assert_called_once()
    mock_session.commit.assert_awaited_once()

    event = mock_session.add.call_args.args[0]
    assert isinstance(event, AnalyticsEvent)

    # Dedicated columns.
    assert event.event_type is EventType.SEARCH_QUERY
    assert event.event_name == "search_query"
    assert event.event_category == "search"
    assert event.user_id == user_id
    assert event.session_id == "sess-123"
    assert event.organization_id == org_id
    assert event.value == 7.0
    assert event.tags == ["alpha", "beta"]

    # The five fields without a dedicated column land in event_data JSON.
    assert event.event_data == {
        "request_id": "req-xyz",
        "properties": {"q": "neural nets"},
        "country": "US",
        "city": "Boston",
        "timezone": "America/New_York",
    }

    # Downstream metric extraction is invoked with the original payload.
    extract_mock.assert_awaited_once_with(payload)


@pytest.mark.asyncio
async def test_ingest_event_defaults_optional_fields_to_none(monkeypatch):
    """Optional keys absent from the payload map to None (via .get), and the
    event_data JSON still carries all five tucked-away slots as None."""
    from src.models.analytics_event import AnalyticsEvent, EventType

    service, mock_session, extract_mock = _patch_session_and_extract(monkeypatch)

    org_id = uuid.uuid4()
    payload = {
        "event_type": EventType.PAGE_VIEW,
        "event_name": "page_view",
        "organization_id": org_id,
    }

    ok = await service.ingest_event(payload)
    assert ok is True

    event = mock_session.add.call_args.args[0]
    assert isinstance(event, AnalyticsEvent)

    assert event.event_type is EventType.PAGE_VIEW
    assert event.event_name == "page_view"
    assert event.organization_id == org_id
    assert event.event_category is None
    assert event.user_id is None
    assert event.session_id is None
    assert event.value is None
    assert event.tags is None

    assert event.event_data == {
        "request_id": None,
        "properties": None,
        "country": None,
        "city": None,
        "timezone": None,
    }

    extract_mock.assert_awaited_once_with(payload)
