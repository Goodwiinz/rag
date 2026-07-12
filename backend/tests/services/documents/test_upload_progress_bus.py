"""Tests for the upload-progress Redis pub/sub bridge (audit B7).

The Celery worker publishes upload progress to a Redis channel; the API process
subscribes and forwards each event to its live ``UploadManager`` WebSocket
connections. These tests cover both sides plus crash-safety when Redis is down or
sends garbage — all with mocked Redis (no real broker).
"""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from src.services.documents import upload_progress_bus as bus

# ---------------------------------------------------------------------------
# Worker side: publishing
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_publish_progress_publishes_to_channel():
    client = AsyncMock()

    ok = await bus.publish_progress("u1", 20.0, "Starting", client=client)

    assert ok is True
    client.publish.assert_awaited_once()
    channel, payload = client.publish.await_args.args
    assert channel == bus.UPLOAD_PROGRESS_CHANNEL
    assert json.loads(payload) == {
        "upload_id": "u1",
        "progress": 20.0,
        "current_step": "Starting",
        "error_message": None,
    }
    # An injected client is owned by the caller and must not be closed here.
    client.aclose.assert_not_called()


@pytest.mark.unit
async def test_publish_progress_carries_error_message():
    client = AsyncMock()

    await bus.publish_progress("u1", 0.0, error_message="boom", client=client)

    _, payload = client.publish.await_args.args
    data = json.loads(payload)
    assert data["error_message"] == "boom"
    assert data["progress"] == 0.0


@pytest.mark.unit
async def test_publish_progress_swallows_redis_errors():
    # no-crash: a broken/absent Redis must never raise into the worker task.
    client = AsyncMock()
    client.publish.side_effect = RuntimeError("redis down")

    ok = await bus.publish_progress("u3", 50.0, client=client)

    assert ok is False  # reported failure, but did not raise


# ---------------------------------------------------------------------------
# API side: dispatch to the in-process UploadManager
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_dispatch_event_forwards_progress_to_manager():
    manager = AsyncMock()

    await bus.dispatch_event(
        manager,
        {
            "upload_id": "u1",
            "progress": 42.0,
            "current_step": "Indexing",
            "error_message": None,
        },
    )

    manager.update_progress.assert_awaited_once_with(
        "u1", 42.0, current_step="Indexing", error_message=None
    )


@pytest.mark.unit
async def test_dispatch_event_ignores_missing_upload_id():
    manager = AsyncMock()

    await bus.dispatch_event(manager, {"progress": 1.0})

    manager.update_progress.assert_not_called()


# ---------------------------------------------------------------------------
# API side: the subscriber loop (mocked Redis pub/sub)
# ---------------------------------------------------------------------------


class _FakePubSub:
    """Minimal async pub/sub stub: yields queued messages then blocks."""

    def __init__(self, messages, idle: asyncio.Event):
        self._messages = messages
        self._idle = idle
        self.subscribed_channel = None

    async def subscribe(self, channel):
        self.subscribed_channel = channel

    async def listen(self):
        for message in self._messages:
            yield message
        # Emulate a live channel with nothing left to deliver: block until the
        # subscriber task is cancelled by the test.
        await self._idle.wait()

    async def aclose(self):
        pass


class _FakeRedis:
    def __init__(self, pubsub):
        self._pubsub = pubsub

    def pubsub(self):
        return self._pubsub

    async def aclose(self):
        pass


async def _drain_until(predicate, task):
    """Poll until ``predicate`` is true, then cancel and await ``task``."""
    try:
        for _ in range(200):
            if predicate():
                break
            await asyncio.sleep(0.005)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.unit
async def test_run_progress_subscriber_forwards_events_to_manager(monkeypatch):
    manager = AsyncMock()
    idle = asyncio.Event()
    messages = [
        {"type": "subscribe", "data": 1},  # subscribe confirmation must be skipped
        {
            "type": "message",
            "data": json.dumps(
                {
                    "upload_id": "u1",
                    "progress": 55.0,
                    "current_step": "Embedding",
                    "error_message": None,
                }
            ),
        },
    ]
    fake = _FakeRedis(_FakePubSub(messages, idle))
    monkeypatch.setattr(bus, "_get_redis", lambda: fake)

    task = asyncio.create_task(bus.run_progress_subscriber(manager))
    await _drain_until(lambda: manager.update_progress.await_count > 0, task)

    manager.update_progress.assert_awaited_once_with(
        "u1", 55.0, current_step="Embedding", error_message=None
    )


@pytest.mark.unit
async def test_run_progress_subscriber_survives_malformed_payload(monkeypatch):
    # no-crash: garbage on the channel is discarded and valid events still flow.
    manager = AsyncMock()
    idle = asyncio.Event()
    messages = [
        {"type": "message", "data": "not-json{"},
        {
            "type": "message",
            "data": json.dumps({"upload_id": "u2", "progress": 100.0}),
        },
    ]
    fake = _FakeRedis(_FakePubSub(messages, idle))
    monkeypatch.setattr(bus, "_get_redis", lambda: fake)

    task = asyncio.create_task(bus.run_progress_subscriber(manager))
    await _drain_until(lambda: manager.update_progress.await_count > 0, task)

    manager.update_progress.assert_awaited_once_with(
        "u2", 100.0, current_step=None, error_message=None
    )
