"""Redis-backed job store for agent execution jobs.

Replaces the process-local ``OrderedDict`` with a Redis-backed store so
jobs survive server restarts and can be shared across multiple workers.

The in-memory ``OrderedDict`` is kept as an L1 read cache (write-through)
so the hot path (polling) avoids a Redis round-trip.
"""

from __future__ import annotations

import json as _json
import logging
import time
from collections import OrderedDict
from threading import Lock
from typing import Optional

import redis.asyncio as aioredis

from src.core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Key naming
# ---------------------------------------------------------------------------
_JOB_KEY_PREFIX = "agent:job:"
_JOB_TTL_SECONDS = 3600  # 1 hour — matches the old in-memory expiry

# ---------------------------------------------------------------------------
# In-memory L1 cache (write-through)
# ---------------------------------------------------------------------------
_l1: OrderedDict[str, dict] = OrderedDict()
_l1_lock = Lock()
_L1_MAX_ENTRIES = 500

_LAST_L1_CLEANUP: float = 0.0
_L1_CLEANUP_INTERVAL = 60.0


def _l1_cleanup() -> None:
    """Remove expired entries (>1h) and evict oldest when over max.

    Must be called while holding ``_l1_lock``.
    """
    global _LAST_L1_CLEANUP
    now = time.time()
    expired = [k for k, v in _l1.items() if now - v.get("created_at", now) > _JOB_TTL_SECONDS]
    for k in expired:
        del _l1[k]
    while len(_l1) > _L1_MAX_ENTRIES:
        _l1.popitem(last=False)
    _LAST_L1_CLEANUP = now


def _l1_maybe_cleanup() -> None:
    """Throttled L1 cleanup called from read paths.

    Must be called while holding ``_l1_lock``.
    """
    if time.time() - _LAST_L1_CLEANUP >= _L1_CLEANUP_INTERVAL:
        _l1_cleanup()


# ---------------------------------------------------------------------------
# Redis client (lazy singleton)
# ---------------------------------------------------------------------------
_redis: Optional[aioredis.Redis] = None


async def _get_redis() -> Optional[aioredis.Redis]:
    """Return the shared Redis client, creating it on first call."""
    global _redis
    if _redis is not None:
        return _redis
    settings = get_settings()
    if not settings.REDIS_URL:
        logger.warning("REDIS_URL not configured — job store using in-memory only")
        return None
    try:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await _redis.ping()
    except Exception:
        logger.exception("Failed to connect to Redis for job store")
        _redis = None
    return _redis


async def close_redis() -> None:
    """Close the Redis connection (called during shutdown)."""
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None


# ---------------------------------------------------------------------------
# Public API (replaces the old _set_job / _get_job)
# ---------------------------------------------------------------------------


async def _write_to_redis_only(job_id: str, data: dict) -> None:
    """Write *data* to Redis without touching the L1 cache.

    Used by the sync ``_set_job`` wrapper whose caller has already
    populated L1 directly.  Avoids a race where the fire-and-forget
    background task overwrites a later L1 update from the main flow.
    """
    redis_client = await _get_redis()
    if redis_client is not None:
        try:
            payload = _json.dumps(data, default=str)
            await redis_client.setex(
                f"{_JOB_KEY_PREFIX}{job_id}", _JOB_TTL_SECONDS, payload
            )
        except Exception:
            logger.exception("Failed to write job %s to Redis", job_id)


async def set_job(job_id: str, data: dict) -> None:
    """Persist a job to Redis (L2) + in-memory L1 cache (write-through)."""
    data["created_at"] = time.time()

    # L1: in-memory cache
    with _l1_lock:
        _l1[job_id] = data
        _l1_cleanup()

    # L2: Redis
    redis_client = await _get_redis()
    if redis_client is not None:
        try:
            payload = _json.dumps(data, default=str)
            await redis_client.setex(
                f"{_JOB_KEY_PREFIX}{job_id}", _JOB_TTL_SECONDS, payload
            )
        except Exception:
            logger.exception("Failed to write job %s to Redis", job_id)


async def get_job(job_id: str) -> Optional[dict]:
    """Retrieve a job, checking L1 cache first, then Redis."""
    # L1: in-memory cache (fast path)
    with _l1_lock:
        _l1_maybe_cleanup()
        cached = _l1.get(job_id)
        if cached is not None:
            # Check expiry
            if time.time() - cached.get("created_at", 0) > _JOB_TTL_SECONDS:
                del _l1[job_id]
            else:
                return cached

    # L2: Redis
    redis_client = await _get_redis()
    if redis_client is not None:
        try:
            raw = await redis_client.get(f"{_JOB_KEY_PREFIX}{job_id}")
            if raw is not None:
                data = _json.loads(raw)
                # Seed L1 for next read
                with _l1_lock:
                    _l1[job_id] = data
                return data
        except Exception:
            logger.exception("Failed to read job %s from Redis", job_id)

    return None


async def delete_job(job_id: str) -> None:
    """Remove a job from both L1 and Redis."""
    with _l1_lock:
        _l1.pop(job_id, None)

    redis_client = await _get_redis()
    if redis_client is not None:
        try:
            await redis_client.delete(f"{_JOB_KEY_PREFIX}{job_id}")
        except Exception:
            logger.exception("Failed to delete job %s from Redis", job_id)
