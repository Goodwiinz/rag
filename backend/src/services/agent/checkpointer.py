"""LangGraph checkpointer backed by PostgreSQL.

Uses ``AsyncPostgresSaver`` wired to the shared ``AsyncConnectionPool``
owned by ``_pool_utils`` (TCP keepalives required for HITL pauses behind
Supabase/PgBouncer in session mode). Falls back to in-memory
``MemorySaver`` only when ``ENVIRONMENT`` is not ``production``/``staging``.

Pool lifecycle lives in ``_pool_utils``; this module never closes it.
"""

import asyncio
import logging

from src.core.config import get_settings
from src.services.agent._pool_utils import (
    get_shared_langgraph_pool,
    require_durable_or_fallback,
)

logger = logging.getLogger(__name__)

_checkpointer = None
_checkpointer_lock = asyncio.Lock()


def get_db_uri() -> str:
    """Build a ``postgresql://`` connection string from settings.

    The project stores the full connection URL in ``settings.DATABASE_URL``.
    ``langgraph-checkpoint-postgres`` requires a plain ``psycopg`` (v3) URI,
    so we normalise the scheme and strip any ``+asyncpg`` driver suffix.
    """
    settings = get_settings()
    uri = settings.DATABASE_URL

    if uri.startswith("postgresql+asyncpg://"):
        uri = uri.replace("postgresql+asyncpg://", "postgresql://", 1)
    elif uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql://", 1)

    return uri


async def get_checkpointer():
    """Return the async checkpointer singleton.

    Attempts ``AsyncPostgresSaver`` over the shared pool. On failure,
    prod/staging raises; dev/test falls back to ``MemorySaver``.
    """
    global _checkpointer

    if _checkpointer is not None:
        return _checkpointer

    async with _checkpointer_lock:
        if _checkpointer is not None:
            return _checkpointer

        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

            from src.services.agent.reflection import ReflectionResult

            pool = await get_shared_langgraph_pool(get_db_uri())
            # Allowlist project pydantic types for msgpack serde (strict mode).
            serde = JsonPlusSerializer(
                allowed_msgpack_modules=[
                    (ReflectionResult.__module__, ReflectionResult.__name__),
                ]
            )
            _checkpointer = AsyncPostgresSaver(pool, serde=serde)
            await _checkpointer.setup()
            logger.info("LangGraph checkpointer initialised (PostgreSQL)")
        except Exception as e:
            require_durable_or_fallback(
                "Postgres checkpointer", get_settings().ENVIRONMENT, e
            )

            logger.error(
                "Postgres checkpointer UNAVAILABLE — falling back to MemorySaver. "
                "HITL state will not survive restarts. Cause: %s",
                e,
            )
            from langgraph.checkpoint.memory import MemorySaver

            _checkpointer = MemorySaver()

    return _checkpointer


async def reset_checkpointer() -> None:
    """Clear the singleton so the next call re-initialises it.

    Does NOT close the shared pool — that's owned by ``_pool_utils`` and
    closed once at app shutdown via ``close_shared_langgraph_pool``.
    """
    global _checkpointer

    async with _checkpointer_lock:
        _checkpointer = None
    logger.info("Checkpointer singleton reset — will reconnect on next use")


async def close_checkpointer() -> None:
    """Drop the singleton at app shutdown. Pool closed separately."""
    await reset_checkpointer()
