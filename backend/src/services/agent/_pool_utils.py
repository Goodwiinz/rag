"""Shared helpers for langgraph-postgres pool construction.

Used by both the checkpointer (`AsyncPostgresSaver`) and the long-term
memory store (`AsyncPostgresStore`). Centralises pool kwargs, keepalives,
and the prod/staging hard-fail policy so the two callers stay in sync.

Pool ownership lives here — checkpointer and memory store fetch the
shared singleton via ``get_shared_langgraph_pool`` and never close it
themselves. Shutdown calls ``close_shared_langgraph_pool`` once.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)

# TCP keepalive settings — prevents Supabase/PgBouncer session-mode idle
# disconnects from silently dropping the connection during HITL pauses
# (user confirmation wait time can exceed the pooler's idle threshold).
KEEPALIVE_KWARGS = {
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 3,
}

# Pool sizing: ONE shared pool serves both checkpointer + memory store.
# Sized to stay well under Supabase session-mode limit (~25) per pod.
_SHARED_MIN_SIZE = 1
_SHARED_MAX_SIZE = 8

# Non-singleton fallback (kept for tests that want isolated pools).
_DEFAULT_MIN_SIZE = 1
_DEFAULT_MAX_SIZE = 5

_shared_pool: Optional["AsyncConnectionPool"] = None
_shared_pool_lock = asyncio.Lock()


def _pool_kwargs() -> dict:
    from psycopg.rows import dict_row

    return {
        "autocommit": True,
        "prepare_threshold": 0,
        "row_factory": dict_row,
        **KEEPALIVE_KWARGS,
    }


async def build_langgraph_pool(uri: str) -> "AsyncConnectionPool":
    """Open an isolated ``AsyncConnectionPool`` configured for langgraph.

    Kept for tests / niche callers wanting their own pool. Production
    code paths should call ``get_shared_langgraph_pool`` instead.
    """
    from psycopg_pool import AsyncConnectionPool

    pool = AsyncConnectionPool(
        conninfo=uri,
        min_size=_DEFAULT_MIN_SIZE,
        max_size=_DEFAULT_MAX_SIZE,
        kwargs=_pool_kwargs(),
        open=False,
    )
    await pool.open(wait=False)
    return pool


async def get_shared_langgraph_pool(uri: str) -> "AsyncConnectionPool":
    """Return the shared langgraph-postgres pool singleton.

    Both ``AsyncPostgresSaver`` and ``AsyncPostgresStore`` accept any
    ``Conn`` (connection or pool); sharing one pool halves per-pod
    connection count vs running a separate pool per consumer.
    """
    global _shared_pool

    if _shared_pool is not None:
        return _shared_pool

    async with _shared_pool_lock:
        if _shared_pool is not None:
            return _shared_pool

        from psycopg_pool import AsyncConnectionPool

        pool = AsyncConnectionPool(
            conninfo=uri,
            min_size=_SHARED_MIN_SIZE,
            max_size=_SHARED_MAX_SIZE,
            kwargs=_pool_kwargs(),
            open=False,
        )
        await pool.open(wait=False)
        _shared_pool = pool
        return _shared_pool


async def close_shared_langgraph_pool() -> None:
    """Close the shared pool at app shutdown. Idempotent."""
    global _shared_pool

    async with _shared_pool_lock:
        if _shared_pool is None:
            return
        try:
            await _shared_pool.close()
        except Exception as e:
            logger.warning("Error closing shared langgraph pool: %s", e)
        _shared_pool = None


def require_durable_or_fallback(component: str, env: str, exc: Exception) -> None:
    """Raise in production/staging; log-and-continue elsewhere.

    Callers use this when a Postgres-backed singleton (checkpointer, store)
    fails to initialise: in prod/staging we must not silently degrade to a
    non-durable in-memory backend, but in dev/test that fallback is fine.
    """
    if env in ("production", "staging"):
        logger.error(
            "%s UNAVAILABLE in %s — failing fast. "
            "Set ENVIRONMENT=development to allow in-memory fallback. "
            "Cause: %s",
            component,
            env,
            exc,
        )
        raise RuntimeError(
            f"{component} required in {env}; refusing to fall back to a "
            "non-durable in-memory backend."
        ) from exc
