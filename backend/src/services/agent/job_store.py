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
from typing import Any, Optional

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

# Per-process monotonic counter — a tiebreaker for set_job calls landing in the
# same ``time.time()`` tick, so two updates in one tick cannot overwrite out of
# order (created_at alone can't disambiguate them).
_seq: int = 0


def _is_newer_or_equal(data: dict, existing: dict) -> bool:
    """True if *data* should overwrite *existing* in the L1 cache.

    Orders by ``(created_at, _seq)``: ``created_at`` is the cross-process clock,
    ``_seq`` the per-process tiebreaker. Missing keys default to 0 for backward
    compatibility with pre-``_seq`` values already stored in Redis.
    """
    return (data.get("created_at", 0), data.get("_seq", 0)) >= (
        existing.get("created_at", 0),
        existing.get("_seq", 0),
    )


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


async def _get_redis() -> Optional[Any]:  # noqa: ANN401
    """Return the shared Redis client, creating it on first call.

    Imports ``redis.asyncio`` lazily so its module-level setup
    (event-loop hooks, connection-factory registration) cannot
    interfere with other async libraries during application startup.
    """
    import redis.asyncio as aioredis

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


async def _redis_write_if_newer(redis_client: Any, job_id: str, data: dict) -> None:
    """``setex`` *data* only if Redis does not already hold a newer job state.

    Monotonic guard for the L2 (Redis) layer: a delayed fire-and-forget write
    must not stomp a newer authoritative state that landed after it. Reads the
    stored ``created_at`` and skips the write when it is strictly newer.

    Not fully atomic (GET then SET) — closes the dominant delayed-write race;
    a same-tick concurrent SET is still theoretically possible.
    """
    key = f"{_JOB_KEY_PREFIX}{job_id}"
    try:
        existing_raw = await redis_client.get(key)
        if existing_raw is not None:
            existing = _json.loads(existing_raw)
            if existing.get("created_at", 0) > data.get("created_at", 0):
                return
        await redis_client.setex(key, _JOB_TTL_SECONDS, _json.dumps(data, default=str))
    except Exception:
        logger.exception("Failed to write job %s to Redis", job_id)


async def _write_to_redis_only(job_id: str, data: dict) -> None:
    """Write *data* to Redis without touching the L1 cache.

    Used by the sync ``_set_job`` wrapper whose caller has already
    populated L1 directly.  Avoids a race where the fire-and-forget
    background task overwrites a later L1 update from the main flow.
    """
    redis_client = await _get_redis()
    if redis_client is not None:
        await _redis_write_if_newer(redis_client, job_id, data)


async def set_job(job_id: str, data: dict) -> None:
    """Persist a job to Redis (L2) + in-memory L1 cache (write-through).

    L1 overwrite is guarded by ``created_at`` so a delayed fire-and-forget
    write cannot stomp a newer authoritative state written after it.
    """
    global _seq
    data["created_at"] = time.time()

    # L1: in-memory cache (monotonic guard — never overwrite newer data)
    with _l1_lock:
        _seq += 1
        data["_seq"] = _seq
        existing = _l1.get(job_id)
        # set_job REPLACES the record. Carry the owner forward when a status
        # update omits it — the GET ownership check fails closed on a missing
        # user_id, so dropping it would lock the owner out of their own job.
        # Scope: L1 only. If the entry was evicted from L1 but still lives in
        # Redis, an ownerless write is NOT enriched — acceptable because every
        # writer stamps user_id explicitly; this is a same-process backstop.
        if "user_id" not in data and existing is not None and existing.get("user_id"):
            data["user_id"] = existing["user_id"]
        if existing is None or _is_newer_or_equal(data, existing):
            _l1[job_id] = data
        _l1_maybe_cleanup()

    # L2: Redis
    await set_job_redis_only(job_id, data)


async def set_job_redis_only(job_id: str, data: dict) -> None:
    """Persist a job to Redis only — does not touch L1.

    This is the *inline authoritative* write (called from ``set_job`` on the
    async run path). It writes directly with ``setex`` and intentionally skips
    the GET-before-SET monotonic guard: a job's status transitions are written
    in order on a single task, so there is no newer state to stomp here, and
    the per-turn hot path shouldn't pay an extra Redis round-trip per write.
    The guard lives on ``_write_to_redis_only`` — the *delayed* fire-and-forget
    path, where an out-of-order stomp can actually happen.
    """
    redis_client = await _get_redis()
    if redis_client is not None:
        try:
            await redis_client.setex(
                f"{_JOB_KEY_PREFIX}{job_id}",
                _JOB_TTL_SECONDS,
                _json.dumps(data, default=str),
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
                # Seed L1 for next read — monotonic guard so a slightly stale
                # Redis read cannot clobber a fresher L1 entry written meanwhile.
                with _l1_lock:
                    existing = _l1.get(job_id)
                    if existing is None or _is_newer_or_equal(data, existing):
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
