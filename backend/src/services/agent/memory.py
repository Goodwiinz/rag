"""Cross-conversation memory using LangGraph Store (PostgreSQL-backed).

Provides long-term user memory that persists across conversations,
enabling the agent to remember user preferences and past interactions.

Uses ``AsyncPostgresStore`` over the shared pool owned by ``_pool_utils``.
Falls back to ``InMemoryStore`` only when ``ENVIRONMENT == "testing"`` or
the Postgres connection fails outside production/staging.

Pool lifecycle lives in ``_pool_utils``; this module never closes it.
"""

import asyncio
import logging

from src.core.config import get_settings
from src.services.agent._pool_utils import (
    get_shared_langgraph_pool,
    require_durable_or_fallback,
)
from src.services.agent.checkpointer import get_db_uri

logger = logging.getLogger(__name__)

_store = None
_store_lock = asyncio.Lock()


def _build_memory_index_config() -> dict | None:
    """Return the LangGraph store index config when Cohere is available.

    AsyncPostgresStore returns ranked, scored search results only when an
    ``index=`` arg with an embedder is supplied at construction. Without
    it, ``asearch`` falls back to recency/exact-key match and every
    recalled item carries ``score=None`` (trace evidence: 019e05ad,
    019e040b on rag-agent-dev).

    Returns ``None`` when Cohere is not configured so callers can fall
    back to the un-indexed store rather than crashing on startup.
    """
    try:
        from src.services.embedding.cohere_embed_service import (
            cohere_embed_service,
        )
    except Exception as exc:  # noqa: BLE001 - import failure must not crash
        logger.warning("Cohere import failed; memory index disabled: %s", exc)
        return None

    if not cohere_embed_service.is_enabled:
        logger.info(
            "Cohere embedding disabled (no API key); memory index disabled"
        )
        return None

    async def _embed(texts):
        # AsyncPostgresStore feeds the same callable for both index time
        # and query time. Use "search_document" since most calls are
        # writes; query-time mismatch is a small quality dip Cohere
        # tolerates fine.
        return await cohere_embed_service.embed_texts(
            list(texts), input_type="search_document"
        )

    return {
        "embed": _embed,
        "dims": cohere_embed_service.dimensions,
        "fields": ["query"],
    }


async def get_memory_store():
    """Return the long-term memory store singleton."""
    global _store

    if _store is not None:
        return _store

    async with _store_lock:
        if _store is not None:
            return _store

        settings = get_settings()
        if settings.ENVIRONMENT == "testing":
            from langgraph.store.memory import InMemoryStore

            _store = InMemoryStore()
            logger.info("Memory store initialised (InMemoryStore — testing env)")
            return _store

        try:
            from langgraph.store.postgres.aio import AsyncPostgresStore

            pool = await get_shared_langgraph_pool(get_db_uri())
            index_config = _build_memory_index_config()
            if index_config is not None:
                _store = AsyncPostgresStore(pool, index=index_config)
            else:
                _store = AsyncPostgresStore(pool)
            await _store.setup()
            # Diagnostic: confirm backend class + whether semantic index is
            # wired. Trace evidence shows asearch returns score=None for
            # every recalled entry when index= is unset. Log makes the
            # runtime state obvious.
            indexed = bool(
                getattr(_store, "_index", None)
                or getattr(_store, "index_config", None)
                or index_config is not None
            )
            logger.info(
                "Memory store initialised (%s, indexed=%s, dims=%s)",
                type(_store).__name__,
                indexed,
                (index_config or {}).get("dims") if index_config else None,
            )
            return _store
        except Exception as e:
            require_durable_or_fallback(
                "Postgres memory store", settings.ENVIRONMENT, e
            )

            logger.error(
                "Postgres memory store UNAVAILABLE — falling back to "
                "InMemoryStore. Long-term memory will NOT survive restarts. "
                "Cause: %s",
                e,
            )
            from langgraph.store.memory import InMemoryStore

            _store = InMemoryStore()
            return _store


async def reset_memory_store() -> None:
    """Clear the singleton so the next call reconnects.

    Does NOT close the shared pool — owned by ``_pool_utils``.
    """
    global _store

    async with _store_lock:
        _store = None
    logger.info("Memory store singleton reset — will reconnect on next use")


async def close_memory_store() -> None:
    """Drop the singleton at app shutdown. Pool closed separately."""
    await reset_memory_store()


async def search_memories(
    store,
    user_id: str,
    query: str,
    limit: int = 5,
) -> list:
    """Search for relevant memories for a user."""
    if store is None:
        return []

    try:
        namespace = ("user", user_id)
        results = await store.asearch(namespace, query=query, limit=limit)
        return [
            {
                "key": item.key,
                "value": item.value,
                "score": getattr(item, "score", 0.0),
            }
            for item in results
        ]
    except Exception as e:
        logger.warning("Memory search failed: %s", e)
        return []


async def save_memory(
    store,
    user_id: str,
    key: str,
    value: dict,
) -> bool:
    """Save a memory for a user."""
    if store is None:
        return False

    try:
        namespace = ("user", user_id)
        await store.aput(namespace, key, value)
        logger.debug("Saved memory for user %s: %s", user_id, key)
        return True
    except Exception as e:
        logger.warning("Memory save failed: %s", e)
        return False
