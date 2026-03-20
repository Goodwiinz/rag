"""Cross-conversation memory using LangGraph Store (PostgreSQL-backed).

Provides long-term user memory that persists across conversations,
enabling the agent to remember user preferences and past interactions.
"""

import asyncio
import logging
from typing import Optional

from src.core.config import get_settings

logger = logging.getLogger(__name__)

_store = None
_store_lock = asyncio.Lock()


async def get_memory_store():
    """Get or create the PostgreSQL-backed memory store singleton."""
    global _store

    if _store is not None:
        return _store

    async with _store_lock:
        if _store is not None:
            return _store

        try:
            from langgraph.store.memory import InMemoryStore

            _store = InMemoryStore()
            logger.info("Memory store initialized (InMemoryStore)")
            return _store
        except Exception as e:
            logger.warning("Failed to initialize memory store: %s", e)
            return None


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
        results = store.search(namespace, query=query, limit=limit)
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
        store.put(namespace, key, value)
        logger.debug("Saved memory for user %s: %s", user_id, key)
        return True
    except Exception as e:
        logger.warning("Memory save failed: %s", e)
        return False
