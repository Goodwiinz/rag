"""LangGraph checkpointer backed by PostgreSQL.

Uses ``AsyncPostgresSaver`` from ``langgraph-checkpoint-postgres`` with a
fallback to an in-memory ``MemorySaver`` when the Postgres connection is
unavailable (e.g. during tests or local dev without a running database).
"""

import logging
from typing import Optional

from src.core.config import get_settings

logger = logging.getLogger(__name__)

# Module-level singleton
_checkpointer = None


def get_db_uri() -> str:
    """Build a ``postgresql://`` connection string from settings.

    The project stores the full connection URL in ``settings.DATABASE_URL``.
    ``langgraph-checkpoint-postgres`` requires a plain ``psycopg`` (v3) URI,
    so we normalise the scheme and strip any ``+asyncpg`` driver suffix.
    """
    settings = get_settings()
    uri = settings.DATABASE_URL

    # Normalise driver — checkpoint-postgres uses psycopg (v3)
    if uri.startswith("postgresql+asyncpg://"):
        uri = uri.replace("postgresql+asyncpg://", "postgresql://", 1)
    elif uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql://", 1)

    return uri


async def get_checkpointer():
    """Return an async checkpointer singleton.

    First attempts to connect via ``AsyncPostgresSaver``.  If the dependency
    is missing or the connection fails, falls back to ``MemorySaver``.
    """
    global _checkpointer

    if _checkpointer is not None:
        return _checkpointer

    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        uri = get_db_uri()
        _checkpointer = AsyncPostgresSaver.from_conn_string(uri)
        # Create the checkpoint tables if they don't exist yet
        await _checkpointer.setup()
        logger.info("LangGraph checkpointer initialised (PostgreSQL)")
    except Exception as e:
        logger.warning(
            "Failed to initialise Postgres checkpointer, falling back to MemorySaver: %s",
            e,
        )
        from langgraph.checkpoint.memory import MemorySaver

        _checkpointer = MemorySaver()

    return _checkpointer
