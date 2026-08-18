"""Redis-backed job store for agent execution jobs.

Replaces the process-local ``OrderedDict`` with a Redis-backed store so
jobs survive server restarts and can be shared across multiple workers.

The in-memory ``OrderedDict`` is kept as an L1 read cache (write-through)
so the hot path (polling) avoids a Redis round-trip.

Every status write is additionally projected into the durable ``agent_runs``
Postgres table. Non-terminal writes remain fire-and-forget; thread-scoped
terminal writes land before L1/Redis publication on the happy path, so
completion does not hold the database's single-writer slot longer than
necessary. A failed strict write does not cost the terminal status itself: it
falls back to the same best-effort re-projection non-terminal writes use, so
a Postgres blip at completion narrows durability instead of losing the
result (see ``set_job``).
"""

from __future__ import annotations

import asyncio
import contextlib
import json as _json
import logging
import time
from collections import OrderedDict
from threading import Lock
from typing import TYPE_CHECKING, Any, Optional
from uuid import uuid4

from src.core.config import get_settings
from src.shared.enums import JobStatus

if TYPE_CHECKING:
    # Only for the `_redis` annotation below — the runtime import is deferred
    # inside `_get_redis()` (see its docstring) so `redis.asyncio`'s module-level
    # setup can't interfere with other async libraries during app startup.
    import redis.asyncio as aioredis

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


class ConfirmationCoordinationUnavailable(RuntimeError):
    """Raised when a shared deployment cannot claim a confirmation safely."""


def process_local_confirmation_coordination_allowed() -> bool:
    """Whether this process may use an in-memory confirmation claim."""
    return get_settings().is_throwaway_environment


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
    expired = [
        k for k, v in _l1.items() if now - v.get("created_at", now) > _JOB_TTL_SECONDS
    ]
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
    client: Optional[Any] = None
    try:
        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await client.ping()
    except Exception:
        logger.exception("Failed to connect to Redis for job store")
        # `from_url` allocates a connection pool synchronously; a failed ping
        # leaves it open with nothing left to close it if we just drop the
        # reference — one leaked pool per retry cycle for the life of a Redis
        # outage. Best-effort close: this path already logged and is about to
        # degrade to in-memory-only, so a second failure here is not fatal.
        if client is not None:
            with contextlib.suppress(Exception):
                await client.aclose()
        _redis = None
        return _redis
    _redis = client
    return _redis


async def get_redis() -> Optional[Any]:  # noqa: ANN401
    """Public alias for the shared lazy Redis client (used by stream_buffer)."""
    return await _get_redis()


async def close_redis() -> None:
    """Close the Redis connection (called during shutdown)."""
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None


# ---------------------------------------------------------------------------
# Durable projection (agent_runs) — fire-and-forget write-through
# ---------------------------------------------------------------------------

# Strong references to in-flight projection tasks so the event loop cannot
# garbage-collect them mid-write (same pattern as jobs._background_tasks).
_projection_tasks: set = set()


def _projection_payload(data: dict, fallback: Optional[dict] = None) -> dict:
    """Snapshot the fields projected into ``agent_runs``."""
    request = data.get("request")
    result = data.get("result")
    fallback = fallback or {}
    fallback_request = fallback.get("request")
    fallback_result = fallback.get("result")
    return {
        "status": data.get("status"),
        "user_id": data.get("user_id"),
        "organization_id": data.get("organization_id"),
        "error": data.get("error"),
        "thread_id": (
            data.get("thread_id")
            or (request.get("thread_id") if isinstance(request, dict) else None)
            or (result.get("thread_id") if isinstance(result, dict) else None)
            or fallback.get("thread_id")
            or (
                fallback_request.get("thread_id")
                if isinstance(fallback_request, dict)
                else None
            )
            or (
                fallback_result.get("thread_id")
                if isinstance(fallback_result, dict)
                else None
            )
        ),
    }


def _projection_enabled() -> bool:
    """Whether to schedule the background agent_runs projection at all.

    Disabled under ``ENVIRONMENT=testing``: pytest closes each test's event
    loop as soon as the test returns, so a fire-and-forget task scheduled
    here outlives its loop. With the CI sqlite database that leaves an
    aiosqlite ``_connection_worker_thread`` (non-daemon) blocked on a future
    whose loop is already closed — the worker process never exits and the
    unit-test job hangs. Projection *scheduling* is pinned by tests that
    monkeypatch this to True (with ``record_job_status`` mocked); the
    projection body is covered against an explicit session in
    test_agent_run_service.py.
    """
    try:
        return get_settings().ENVIRONMENT != "testing"
    except Exception:  # pragma: no cover — settings must never break writes
        return True


def _on_projection_done(task) -> None:
    """Drop a finished projection task and surface unexpected errors."""
    _projection_tasks.discard(task)
    try:
        task.result()
    except asyncio.CancelledError:
        pass
    except Exception:
        # record_job_status already swallows its own failures; this catches
        # anything raised before it ran (e.g. import errors).
        logger.exception("agent_runs projection task failed")


def schedule_run_projection(job_id: str, data: dict) -> None:
    """Fire-and-forget the ``agent_runs`` Postgres projection for a write.

    Snapshots the few projected fields synchronously so a later mutation of
    *data* (the same dict the L1 cache holds) cannot race the background
    write. Never blocks and never raises: Redis stays authoritative — a
    skipped/failed projection only narrows the failover fallback.

    No-op under ``ENVIRONMENT=testing`` (see ``_projection_enabled``) so no
    background task can outlive a test's event loop.
    """
    if not _projection_enabled():
        return
    status = data.get("status")
    if not status:
        return
    payload = _projection_payload(data)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return  # no loop — sync caller outside async context; best-effort skip

    try:
        from src.services.agent.agent_run_service import record_job_status

        task = loop.create_task(record_job_status(job_id, payload))
        _projection_tasks.add(task)
        task.add_done_callback(_on_projection_done)
    except Exception:
        # The projection is strictly best-effort — scheduling problems must
        # never break the authoritative Redis/L1 write path.
        logger.warning(
            "Failed to schedule agent_runs projection for job %s",
            job_id,
            exc_info=True,
        )


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

    # Carry ownership forward and capture the prior request/result before the
    # replacement write. Terminal updates often contain only status + actor.
    with _l1_lock:
        existing = _l1.get(job_id)
        # set_job REPLACES the record. Carry the owner forward when a status
        # update omits it — the GET ownership check fails closed on a missing
        # user_id, so dropping it would lock the owner out of their own job.
        # Scope: L1 only. If the entry was evicted from L1 but still lives in
        # Redis, an ownerless write is NOT enriched — acceptable because every
        # writer stamps user_id explicitly; this is a same-process backstop.
        if "user_id" not in data and existing is not None and existing.get("user_id"):
            data["user_id"] = existing["user_id"]
        # Same carry-forward for tenancy: replacement writes typically omit
        # organization_id; keep it so the agent_runs projection stays scoped.
        if (
            "organization_id" not in data
            and existing is not None
            and existing.get("organization_id")
        ):
            data["organization_id"] = existing["organization_id"]

    projection_payload = _projection_payload(data, existing)
    try:
        status = JobStatus(data.get("status"))
    except (TypeError, ValueError):
        status = None
    strict_terminal_projection = bool(
        status is not None
        and status.is_terminal
        and projection_payload.get("thread_id")
    )
    projection_failed = False
    if strict_terminal_projection:
        # Release the durable single-writer slot before L1/Redis can expose a
        # terminal result to the client — but that ordering must not cost the
        # terminal status itself. Every caller of set_job for a terminal write
        # sits directly in an except-handler body with no try/except of its
        # own (agent_execution_service._run_agent_graph's COMPLETED/FAILED
        # branches); letting record_job_status's exception escape here kills
        # the background task with L1/Redis stuck on "running" until the
        # sweeper's stale window, which then overwrites the real error with a
        # generic "swept as stale" message. Fall through instead: the
        # single-writer slot is released late rather than the result being
        # lost, and the best-effort seam below (shared with non-terminal
        # writes) retries the durable row — the sweeper also repairs the
        # projection from the live store on its next pass regardless.
        from src.services.agent.agent_run_service import record_job_status

        try:
            await record_job_status(job_id, projection_payload, raise_on_error=True)
        except Exception:
            logger.exception(
                "Terminal agent_runs projection failed for job %s; exposing "
                "L1/Redis anyway and rescheduling a best-effort re-projection",
                job_id,
            )
            projection_failed = True

    # L1: in-memory cache (monotonic guard — never overwrite newer data).
    # Re-read `existing` here rather than reusing the pre-projection snapshot
    # above: the strict projection just awaited a Postgres round-trip, and a
    # newer write (e.g. get_job_fresh folding in a fresher Redis read, or a
    # concurrent set_job) may have landed in L1 during that window. Comparing
    # against the stale snapshot would let this write stomp it; the lock is
    # the only place the comparison is valid. (The pre-await snapshot above
    # is still correct for the owner/org carry-forward — that races nothing.)
    with _l1_lock:
        _seq += 1
        data["_seq"] = _seq
        existing = _l1.get(job_id)
        if existing is None or _is_newer_or_equal(data, existing):
            _l1[job_id] = data
        _l1_maybe_cleanup()

    # Non-terminal and threadless writes retain the rollout's best-effort
    # projection behavior. Thread-scoped terminal writes landed above, unless
    # the strict projection failed — that case falls back here too.
    if not strict_terminal_projection or projection_failed:
        schedule_run_projection(job_id, data)

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


async def _cas_in_memory(
    job_id: str, expected: JobStatus | str, new_status: JobStatus | str
) -> str:
    """Compare-and-set the status using the store API (L1 + write-through).

    Used when Redis is unavailable (single process ⇒ the L1 lock is sufficient)
    AND as the graceful fallback when a Redis operational error interrupts the
    WATCH/MULTI path — so a transient Redis hiccup degrades to single-process
    behavior (still flips + lets the caller proceed) rather than silently
    dropping the transition.
    """
    job = await get_job(job_id)
    if job is None:
        return "missing"
    with _l1_lock:
        current = _l1.get(job_id) or job
        if current.get("status") != expected:
            return "conflict"
        current["status"] = new_status
        _l1[job_id] = current
        claimed = current
    await set_job(job_id, claimed)
    return "claimed"


async def compare_and_set_status(
    job_id: str, expected: JobStatus | str, new_status: JobStatus | str
) -> str:
    """Atomically flip a job's status from *expected* to *new_status*.

    Returns one of: ``"claimed"`` (transition applied — caller is the winner),
    ``"conflict"`` (job exists but status != expected — a concurrent caller
    already transitioned it, or it is denied/completed), ``"missing"`` (no such
    job).

    This closes the multi-worker double-resume race on /confirm: two workers
    racing to confirm the same HITL job both read ``awaiting_confirmation``, but
    only one wins this compare-and-set, so only one schedules a resume — without
    it a destructive HITL tool (ingest/create_note/create_draft) could execute
    twice. Uses a Redis WATCH/MULTI optimistic transaction (JSON parsed in
    Python to avoid cjson's empty-dict ambiguity). Disposable local/CI processes
    may fall back to memory; shared deployments fail closed without Redis.
    """
    redis_client = await _get_redis()
    if redis_client is None:
        if not process_local_confirmation_coordination_allowed():
            raise ConfirmationCoordinationUnavailable(
                "Distributed confirmation coordination is unavailable"
            )
        return await _cas_in_memory(job_id, expected, new_status)

    key = f"{_JOB_KEY_PREFIX}{job_id}"
    from redis.exceptions import RedisError, WatchError

    claim_id = uuid4().hex
    try:
        async with redis_client.pipeline(transaction=True) as pipe:
            while True:
                try:
                    await pipe.watch(key)
                    raw = await pipe.get(key)  # immediate mode after WATCH
                    if raw is None:
                        await pipe.reset()
                        return "missing"
                    job = _json.loads(raw)
                    if job.get("status") != expected:
                        await pipe.reset()
                        return "conflict"
                    job["status"] = new_status
                    job["_confirmation_claim_id"] = claim_id
                    ttl = await pipe.ttl(key)
                    pipe.multi()
                    pipe.setex(
                        key,
                        ttl if (ttl and ttl > 0) else _JOB_TTL_SECONDS,
                        _json.dumps(job, default=str),
                    )
                    await pipe.execute()  # raises WatchError if key changed
                    break
                except WatchError:
                    # Reset clears the WATCH/command state before re-watching —
                    # required so the retry's watch() starts from a clean slate
                    # and the connection isn't left bound.
                    await pipe.reset()
                    continue
    except (RedisError, OSError, asyncio.TimeoutError):
        # Operational Redis/connection error (not a logical conflict). Only a
        # disposable single-process environment can safely fall back to memory;
        # shared deployments fail closed so two pods cannot both resume.
        logger.warning(
            "compare_and_set_status Redis path failed for job %s; "
            "checking whether an in-memory fallback is safe",
            job_id,
            exc_info=True,
        )
        if not process_local_confirmation_coordination_allowed():
            try:
                committed_raw = await redis_client.get(key)
                committed = _json.loads(committed_raw) if committed_raw else None
            except (RedisError, OSError, asyncio.TimeoutError, ValueError):
                committed = None
            if not (
                committed
                and committed.get("status") == new_status
                and committed.get("_confirmation_claim_id") == claim_id
            ):
                raise ConfirmationCoordinationUnavailable(
                    "Distributed confirmation coordination is unavailable"
                )
            job = committed
        else:
            return await _cas_in_memory(job_id, expected, new_status)

    # Mirror the winning transition into L1 so this worker's polls are consistent.
    with _l1_lock:
        cached = _l1.get(job_id)
        if cached is not None:
            cached["status"] = new_status
    # Project the claimed transition (the in-memory fallback path projects via
    # set_job inside _cas_in_memory; this covers the Redis WATCH/MULTI path).
    schedule_run_projection(job_id, job)
    return "claimed"


async def get_job(job_id: str) -> Optional[dict]:
    """Retrieve a job: Redis-first (cross-worker truth), L1 as fallback.

    Redis is authoritative across workers — an L1-first read let worker A
    serve a stale local entry after worker B advanced the job in Redis
    (codex audit on #1405: the resume and worker-failure paths acted on such
    reads). The monotonic ``_seq`` guard still protects the one case where
    the LOCAL copy is fresher (this worker's write-through beat its own
    fire-and-forget Redis write): the newer of the two wins. L1 serves the
    answer only when Redis is unavailable or has no key.
    """
    # L1 lookup (expiry-checked); used for the freshness compare and as the
    # Redis-down fallback — never returned early over a live Redis read.
    cached: Optional[dict] = None
    with _l1_lock:
        _l1_maybe_cleanup()
        entry = _l1.get(job_id)
        if entry is not None:
            if time.time() - entry.get("created_at", 0) > _JOB_TTL_SECONDS:
                del _l1[job_id]
            else:
                cached = entry

    redis_client = await _get_redis()
    if redis_client is not None:
        try:
            raw = await redis_client.get(f"{_JOB_KEY_PREFIX}{job_id}")
            if raw is not None:
                data = _json.loads(raw)
                with _l1_lock:
                    existing = _l1.get(job_id)
                    if existing is None or _is_newer_or_equal(data, existing):
                        _l1[job_id] = data
                        return data
                    # Local write-through is newer than the Redis read
                    # (its async projection hasn't landed yet).
                    return existing
        except Exception:
            logger.exception("Failed to read job %s from Redis", job_id)

    return cached


async def get_job_fresh(job_id: str) -> Optional[dict]:
    """Redis-first job read for cross-process freshness; L1 fallback.

    ``get_job`` prefers the process-local L1 cache, which is only coherent
    with writes made by THIS process. When the run's writer is a different
    process — Celery dispatch mode, or a confirm/poll landing on a different
    API replica — a previously-seeded L1 entry goes permanently stale (a
    ``running`` record would 409 every confirm and spin the poller for the
    full 1h TTL). Poll/confirm reads therefore consult Redis first and fold
    the fresh copy back into L1 under the monotonic guard (so an in-flight
    newer local write is never clobbered). Degrades to the plain L1 read when
    Redis is unavailable — identical to today's single-process behavior.
    """
    redis_client = await _get_redis()
    if redis_client is not None:
        try:
            raw = await redis_client.get(f"{_JOB_KEY_PREFIX}{job_id}")
            if raw is not None:
                data = _json.loads(raw)
                with _l1_lock:
                    existing = _l1.get(job_id)
                    if existing is None or _is_newer_or_equal(data, existing):
                        _l1[job_id] = data
                        return data
                    # L1 holds a strictly newer local write (fire-and-forget
                    # Redis write still in flight) — prefer it.
                    return existing
            # Redis miss (TTL/failover): fall through to L1 so a record that
            # only ever lived locally (Redis down at write time) still reads.
        except Exception:
            logger.exception("Failed to read job %s from Redis", job_id)
    with _l1_lock:
        _l1_maybe_cleanup()
        cached = _l1.get(job_id)
        if cached is None:
            return None
        if time.time() - cached.get("created_at", 0) > _JOB_TTL_SECONDS:
            del _l1[job_id]
            return None
        return cached


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
