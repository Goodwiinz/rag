"""
Search Cache Service

Provides caching for search results to improve
performance and reduce load on search backends.
"""

import asyncio
import hashlib
import json
import random
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .base import SearchQuery, SearchResult, SearchSource

logger = logging.getLogger(__name__)


@dataclass
class CacheConfig:
    """Configuration for the search cache."""

    # Default TTL in seconds
    default_ttl: int = 300  # 5 minutes

    # Maximum cache entries
    max_entries: int = 10000

    # Whether to use Redis if available
    use_redis: bool = True

    # Redis key prefix
    redis_prefix: str = "search_cache:"

    # Cache warming settings
    enable_warming: bool = False
    warming_interval: int = 3600  # 1 hour


@dataclass
class CacheEntry:
    """A cached search result entry."""

    key: str
    results: List[Dict[str, Any]]
    created_at: datetime
    ttl: int
    hit_count: int = 0

    @property
    def is_expired(self) -> bool:
        """Check if the entry has expired."""
        expiry = self.created_at + timedelta(seconds=self.ttl)
        return datetime.now(timezone.utc) > expiry


class InMemoryCache:
    """Simple in-memory cache implementation."""

    def __init__(self, max_entries: int = 10000):
        self.max_entries = max_entries
        self._cache: Dict[str, CacheEntry] = {}
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
        }

    async def get(self, key: str) -> Optional[List[Dict[str, Any]]]:
        """Get a value from cache."""
        entry = self._cache.get(key)

        if entry is None:
            self._stats["misses"] += 1
            return None

        if entry.is_expired:
            del self._cache[key]
            self._stats["misses"] += 1
            return None

        entry.hit_count += 1
        self._stats["hits"] += 1
        return entry.results

    async def set(self, key: str, results: List[Dict[str, Any]], ttl: int = 300):
        """Set a value in cache."""
        # Evict entries if at capacity
        if len(self._cache) >= self.max_entries:
            self._evict_entries()

        self._cache[key] = CacheEntry(
            key=key,
            results=results,
            created_at=datetime.now(timezone.utc),
            ttl=ttl,
        )

    async def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    async def clear(self):
        """Clear all cache entries."""
        self._cache.clear()

    def _evict_entries(self):
        """Evict expired and least-used entries."""
        # First, remove expired entries
        expired_keys = [k for k, v in self._cache.items() if v.is_expired]
        for key in expired_keys:
            del self._cache[key]
            self._stats["evictions"] += 1

        # If still over capacity, remove least recently used
        if len(self._cache) >= self.max_entries:
            # Sort by hit count (ascending) and created_at (ascending)
            sorted_entries = sorted(
                self._cache.items(), key=lambda x: (x[1].hit_count, x[1].created_at)
            )

            # Remove bottom 10%
            to_remove = max(1, len(sorted_entries) // 10)
            for key, _ in sorted_entries[:to_remove]:
                del self._cache[key]
                self._stats["evictions"] += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total * 100 if total > 0 else 0

        return {
            "type": "in_memory",
            "entries": len(self._cache),
            "max_entries": self.max_entries,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "evictions": self._stats["evictions"],
            "hit_rate_pct": round(hit_rate, 2),
        }


class RedisCache:
    """Redis-backed cache implementation."""

    def __init__(self, redis_url: Optional[str] = None, prefix: str = "search_cache:"):
        self.prefix = prefix
        self._client = None
        self._is_available = False

        self._init_client(redis_url)

        self._stats = {
            "hits": 0,
            "misses": 0,
        }

    def _init_client(self, redis_url: Optional[str]):
        """Initialize Redis client."""
        try:
            import os

            import redis.asyncio as redis

            url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
            self._client = redis.from_url(url)
            self._is_available = True
            logger.info(f"Redis cache connected to {url}")

        except ImportError:
            logger.warning("redis package not installed, Redis cache unavailable")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")

    def _make_key(self, key: str) -> str:
        """Create a prefixed cache key."""
        return f"{self.prefix}{key}"

    async def get(self, key: str) -> Optional[List[Dict[str, Any]]]:
        """Get a value from Redis cache."""
        if not self._is_available:
            return None

        try:
            data = await self._client.get(self._make_key(key))
            if data:
                self._stats["hits"] += 1
                return json.loads(data)
            self._stats["misses"] += 1
            return None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            self._stats["misses"] += 1
            return None

    async def set(self, key: str, results: List[Dict[str, Any]], ttl: int = 300):
        """Set a value in Redis cache."""
        if not self._is_available:
            return

        try:
            jitter = int(ttl * 0.15)
            effective_ttl = ttl + random.randint(-jitter, jitter)
            await self._client.setex(self._make_key(key), effective_ttl, json.dumps(results))
        except Exception as e:
            logger.error(f"Redis set error: {e}")

    async def delete(self, key: str) -> bool:
        """Delete a key from Redis cache."""
        if not self._is_available:
            return False

        try:
            result = await self._client.delete(self._make_key(key))
            return result > 0
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False

    async def clear(self):
        """Clear all cache entries with our prefix."""
        if not self._is_available:
            return

        try:
            cursor = 0
            while True:
                cursor, keys = await self._client.scan(
                    cursor, match=f"{self.prefix}*", count=100
                )
                if keys:
                    await self._client.delete(*keys)
                if cursor == 0:
                    break
        except Exception as e:
            logger.error(f"Redis clear error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total * 100 if total > 0 else 0

        return {
            "type": "redis",
            "available": self._is_available,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "hit_rate_pct": round(hit_rate, 2),
        }


class SearchCache:
    """
    Main search cache service with multiple backend support.

    Uses Redis if available, falls back to in-memory cache.
    Provides automatic cache key generation and TTL management.
    """

    def __init__(
        self, config: Optional[CacheConfig] = None, redis_url: Optional[str] = None
    ):
        """
        Initialize the search cache.

        Args:
            config: Cache configuration
            redis_url: Optional Redis URL override
        """
        self.config = config or CacheConfig()

        # Initialize backends
        self._memory_cache = InMemoryCache(self.config.max_entries)
        self._redis_cache = None

        if self.config.use_redis:
            self._redis_cache = RedisCache(redis_url, self.config.redis_prefix)

    def _generate_cache_key(self, query: SearchQuery) -> str:
        """Generate a unique cache key for a query."""
        key_data = {
            "text": query.text.lower().strip(),
            "filters": sorted(query.filters.items()) if query.filters else [],
            "limit": query.limit,
            "offset": query.offset,
            "include_sources": (
                [s.value for s in query.include_sources]
                if query.include_sources
                else None
            ),
            "exclude_sources": (
                [s.value for s in query.exclude_sources]
                if query.exclude_sources
                else None
            ),
            "min_score": query.min_score,
            "org_id": query.organization_id,
        }

        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_string.encode()).hexdigest()[:32]

    def _serialize_results(self, results: List[SearchResult]) -> List[Dict[str, Any]]:
        """Serialize results for caching."""
        return [
            {
                "document_id": r.document_id,
                "score": r.score,
                "snippet": r.snippet,
                "title": r.title,
                "source": r.source.value,
                "metadata": r.metadata,
                "highlight": r.highlight,
                "chunk_id": r.chunk_id,
            }
            for r in results
        ]

    def _deserialize_results(self, data: List[Dict[str, Any]]) -> List[SearchResult]:
        """Deserialize results from cache."""
        return [
            SearchResult(
                document_id=d["document_id"],
                score=d["score"],
                snippet=d["snippet"],
                title=d.get("title", ""),
                source=SearchSource(d.get("source", "vector")),
                metadata=d.get("metadata", {}),
                highlight=d.get("highlight"),
                chunk_id=d.get("chunk_id"),
            )
            for d in data
        ]

    async def get(self, query: SearchQuery) -> Optional[List[SearchResult]]:
        """
        Get cached results for a query.

        Args:
            query: The search query

        Returns:
            Cached results or None if not found
        """
        key = self._generate_cache_key(query)

        # Try Redis first
        if self._redis_cache and self._redis_cache._is_available:
            data = await self._redis_cache.get(key)
            if data:
                logger.debug(f"Redis cache hit for key {key}")
                return self._deserialize_results(data)

        # Fall back to memory cache
        data = await self._memory_cache.get(key)
        if data:
            logger.debug(f"Memory cache hit for key {key}")
            return self._deserialize_results(data)

        return None

    async def set(
        self, query: SearchQuery, results: List[SearchResult], ttl: Optional[int] = None
    ):
        """
        Cache results for a query.

        Args:
            query: The search query
            results: Results to cache
            ttl: Optional TTL override
        """
        key = self._generate_cache_key(query)
        ttl = ttl or self.config.default_ttl
        data = self._serialize_results(results)

        # Store in both caches
        await self._memory_cache.set(key, data, ttl)

        if self._redis_cache and self._redis_cache._is_available:
            await self._redis_cache.set(key, data, ttl)

        logger.debug(f"Cached {len(results)} results for key {key}")

    async def invalidate(self, query: SearchQuery):
        """Invalidate cache for a specific query."""
        key = self._generate_cache_key(query)

        await self._memory_cache.delete(key)

        if self._redis_cache and self._redis_cache._is_available:
            await self._redis_cache.delete(key)

    async def clear(self):
        """Clear all cached results."""
        await self._memory_cache.clear()

        if self._redis_cache and self._redis_cache._is_available:
            await self._redis_cache.clear()

        logger.info("Search cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get combined cache statistics."""
        stats = {
            "memory": self._memory_cache.get_stats(),
        }

        if self._redis_cache:
            stats["redis"] = self._redis_cache.get_stats()

        return stats
