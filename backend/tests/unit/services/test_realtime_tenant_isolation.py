"""realtime analytics pub/sub must be namespaced per organization.

R5-M22: any authenticated user could subscribe to or publish onto any
channel string (``self.subscriptions`` / ``broadcast_to_channel`` matched on
the raw, client-supplied channel name with no tenant scope), so one org's
live metrics/events broadcast to every other org's WebSocket subscribers of
the same channel name. ``/test/subscribe`` additionally let any caller spray
up to 100 junk metrics onto any channel with no rate limit.

Fix: ``RealtimeAnalyticsService.namespaced_channel`` prefixes every channel
with the server-resolved (never client-supplied) caller org before it is
used for subscribe, unsubscribe, or broadcast — org A and org B subscribing
to the literal channel "performance" land on two different internal keys and
can never cross-broadcast. ``/test/subscribe`` is removed outright (dead
code: the analytics realtime router is not mounted in main.py, and nothing
in frontend/src called it).

These tests exercise the real ``RealtimeAnalyticsService`` methods with the
DB session and WebSocket send calls faked out (this service has no existing
test coverage and talks to Postgres/Redis directly; a real websocket/DB is
unnecessary to prove the tenant-isolation property).
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit


class _FakeWebSocket:
    def __init__(self):
        self.sent: list[str] = []

    async def send_text(self, text: str) -> None:
        self.sent.append(text)


@asynccontextmanager
async def _fake_session():
    db = AsyncMock()
    yield db


def _service():
    from src.services.analytics.realtime_service import RealtimeAnalyticsService

    svc = RealtimeAnalyticsService()
    svc.redis_client = None  # skip the Redis fan-out branch in broadcast
    return svc


# --- namespacing primitive ---------------------------------------------------


def test_namespaced_channel_differs_by_org():
    from src.services.analytics.realtime_service import RealtimeAnalyticsService

    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    chan_a = RealtimeAnalyticsService.namespaced_channel(org_a, "performance")
    chan_b = RealtimeAnalyticsService.namespaced_channel(org_b, "performance")
    assert chan_a != chan_b
    assert str(org_a) in chan_a
    assert str(org_b) in chan_b


# --- subscribe fails closed with no resolved org ------------------------------


@pytest.mark.asyncio
async def test_handle_subscribe_rejects_connection_with_no_org():
    svc = _service()
    ws = _FakeWebSocket()
    svc.active_connections["conn"] = ws
    # No entry in svc.connection_orgs — the connection has no resolved org.

    with patch(
        "src.services.analytics.realtime_service.get_async_session",
        _fake_session,
    ):
        await svc.handle_subscribe(
            "conn", {"subscription_type": "metrics", "channel": "performance"}
        )

    assert "conn" not in svc.subscriptions or not svc.subscriptions.get("conn")
    assert any('"type": "error"' in m for m in ws.sent)


# --- subscribe/broadcast tenant isolation -------------------------------------


@pytest.mark.asyncio
async def test_broadcast_never_crosses_org_for_the_same_bare_channel_name():
    """broadcast_to_channel's target-connection selection is what enforces
    isolation; assert on which connection_ids it messages (via a mocked
    send_message) rather than on JSON-serialized payload bytes — the raw
    metric/event dumps contain datetime fields ``json.dumps`` can't encode,
    an unrelated pre-existing wrinkle in send_message orthogonal to R5-M22.
    """
    svc = _service()
    org_a, org_b = uuid.uuid4(), uuid.uuid4()

    svc.active_connections["conn_a"] = _FakeWebSocket()
    svc.active_connections["conn_b"] = _FakeWebSocket()
    svc.connection_orgs["conn_a"] = org_a
    svc.connection_orgs["conn_b"] = org_b

    with patch(
        "src.services.analytics.realtime_service.get_async_session",
        _fake_session,
    ):
        # Both orgs subscribe to the SAME bare channel name.
        await svc.handle_subscribe(
            "conn_a",
            {
                "subscription_type": "metrics",
                "channel": "performance",
                "user_id": str(uuid.uuid4()),
            },
        )
        await svc.handle_subscribe(
            "conn_b",
            {
                "subscription_type": "metrics",
                "channel": "performance",
                "user_id": str(uuid.uuid4()),
            },
        )

        # Sanity: stored under different (namespaced) internal channels.
        chan_a = next(iter(svc.subscriptions["conn_a"].values()))["channel"]
        chan_b = next(iter(svc.subscriptions["conn_b"].values()))["channel"]
        assert chan_a != chan_b

        from src.models.analytics.realtime_models import LiveMetricData

        metric = LiveMetricData(
            metric_id="m1",
            metric_name="Metric 1",
            channel="performance",
            current_value=1.0,
            previous_value=0.0,
            change_percentage=0.0,
            timestamp=datetime.utcnow(),
            time_window="1m",
            aggregation_type="sum",
            sample_count=1,
            data_quality_score=1.0,
            dimensions=None,
            tags=None,
            is_anomaly=False,
            alert_threshold_min=None,
            alert_threshold_max=None,
            source="test",
            confidence=1.0,
        )
        with patch.object(svc, "send_message", AsyncMock()) as sent:
            # Org A publishes on "performance" — only org A's connection hears it.
            await svc.publish_metric(metric, organization_id=org_a)

    messaged_connections = {call.args[0] for call in sent.await_args_list}
    assert messaged_connections == {"conn_a"}  # never crosses into org B


@pytest.mark.asyncio
async def test_publish_event_namespaces_every_channel_to_the_caller_org():
    svc = _service()
    org_a, org_b = uuid.uuid4(), uuid.uuid4()

    svc.active_connections["conn_a"] = _FakeWebSocket()
    svc.active_connections["conn_b"] = _FakeWebSocket()
    svc.connection_orgs["conn_a"] = org_a
    svc.connection_orgs["conn_b"] = org_b

    with patch(
        "src.services.analytics.realtime_service.get_async_session",
        _fake_session,
    ):
        await svc.handle_subscribe(
            "conn_a",
            {
                "subscription_type": "events",
                "channel": "user_activity",
                "user_id": str(uuid.uuid4()),
            },
        )
        await svc.handle_subscribe(
            "conn_b",
            {
                "subscription_type": "events",
                "channel": "user_activity",
                "user_id": str(uuid.uuid4()),
            },
        )

        from src.models.analytics.realtime_models import EventStreamData

        event = EventStreamData(
            event_type="click",
            event_name="click",
            source="test",
            payload={},
            metadata=None,
            user_id=None,
            session_id=None,
            request_id=None,
            correlation_id=None,
            processed_at=datetime.utcnow(),
            processing_latency_ms=None,
            status="ok",
            error_message=None,
            routing_key=None,
            channels=["user_activity"],
        )
        with patch.object(svc, "send_message", AsyncMock()) as sent:
            await svc.publish_event(event, organization_id=org_b)

    messaged_connections = {call.args[0] for call in sent.await_args_list}
    assert messaged_connections == {"conn_b"}  # org A never sees org B's event
