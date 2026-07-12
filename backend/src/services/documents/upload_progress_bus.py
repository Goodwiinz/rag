"""Redis pub/sub bridge for document-upload progress events.

Audit B7: ``process_document_upload`` runs in a Celery *worker* process but used
to push progress through the in-process ``UploadManager`` imported from the API
route module (``src.api.documents.document_upload``). A worker's connection map
can never contain API-process WebSockets, so upload progress silently reached no
one.

Fix: the worker *publishes* progress events to a Redis channel; the API process
runs a *subscriber* that forwards each event to its live ``UploadManager``
WebSocket connections. This mirrors the pub/sub pattern already used by
``src/services/infrastructure/realtime_service.py`` and keeps the worker free of
any import of the route module.

The module deliberately depends only on redis + settings (no import of the route
module or the task module) so both sides can import it without a cycle.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

import redis.asyncio as redis

from src.core.config import settings

logger = logging.getLogger(__name__)

# Single channel; the payload carries the ``upload_id`` so one API-process
# subscriber can fan every event out to the matching WebSocket connection.
UPLOAD_PROGRESS_CHANNEL = "upload:progress"

# How long the subscriber waits before reconnecting after a Redis error.
_RECONNECT_DELAY_SECONDS = 5


def _get_redis() -> "redis.Redis":
    """Create a short-lived async Redis client (repo convention: from_url)."""
    return redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )


async def _aclose(obj: Any) -> None:
    """Close a redis client / pubsub across redis-py versions, never raising."""
    if obj is None:
        return
    closer = getattr(obj, "aclose", None) or getattr(obj, "close", None)
    if closer is None:
        return
    try:
        result = closer()
        if asyncio.iscoroutine(result):
            await result
    except Exception:  # noqa: BLE001 - cleanup is best-effort
        pass


async def publish_progress(
    upload_id: str,
    progress: float,
    current_step: Optional[str] = None,
    error_message: Optional[str] = None,
    *,
    client: Optional["redis.Redis"] = None,
) -> bool:
    """Publish an upload progress update (called from the Celery worker).

    Best-effort: never raises, so a broken/absent Redis cannot fail the task.
    Returns True when the event was published.
    """
    message = {
        "upload_id": upload_id,
        "progress": progress,
        "current_step": current_step,
        "error_message": error_message,
    }
    own_client = client is None
    redis_client = client or _get_redis()
    try:
        await redis_client.publish(
            UPLOAD_PROGRESS_CHANNEL, json.dumps(message, default=str)
        )
        return True
    except Exception:  # noqa: BLE001
        logger.warning(
            "Failed to publish upload progress event (upload_id=%s)",
            upload_id,
            exc_info=True,
        )
        return False
    finally:
        if own_client:
            await _aclose(redis_client)


async def dispatch_event(manager: Any, data: Dict[str, Any]) -> None:
    """Forward one decoded pub/sub event to the in-process ``UploadManager``.

    ``manager.update_progress`` is a no-op for an ``upload_id`` not connected in
    this process, so an event with no local WebSocket is harmless.
    """
    upload_id = data.get("upload_id")
    if not upload_id:
        return
    await manager.update_progress(
        upload_id,
        data.get("progress", 0.0),
        current_step=data.get("current_step"),
        error_message=data.get("error_message"),
    )


async def run_progress_subscriber(
    manager: Any, *, stop_event: Optional[asyncio.Event] = None
) -> None:
    """Subscribe to the upload-progress channel and forward events to ``manager``.

    Runs until cancelled (or ``stop_event`` is set), reconnecting on Redis
    errors. Start exactly one of these per API process — e.g. lazily when the
    first upload-progress WebSocket connects.
    """
    while stop_event is None or not stop_event.is_set():
        client = None
        pubsub = None
        try:
            client = _get_redis()
            pubsub = client.pubsub()
            await pubsub.subscribe(UPLOAD_PROGRESS_CHANNEL)
            logger.info(
                "Upload-progress subscriber listening on '%s'", UPLOAD_PROGRESS_CHANNEL
            )
            async for message in pubsub.listen():
                if stop_event is not None and stop_event.is_set():
                    break
                if message.get("type") != "message":
                    continue  # skip subscribe/unsubscribe confirmations
                try:
                    data = json.loads(message["data"])
                except (json.JSONDecodeError, TypeError, KeyError):
                    logger.warning(
                        "Discarding malformed upload-progress payload: %r",
                        message.get("data"),
                    )
                    continue
                try:
                    await dispatch_event(manager, data)
                except Exception:  # noqa: BLE001 - one bad event must not kill the loop
                    logger.warning(
                        "Failed to forward upload-progress event", exc_info=True
                    )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.warning(
                "Upload-progress subscriber error; reconnecting in %ss",
                _RECONNECT_DELAY_SECONDS,
                exc_info=True,
            )
            await asyncio.sleep(_RECONNECT_DELAY_SECONDS)
        finally:
            await _aclose(pubsub)
            await _aclose(client)
