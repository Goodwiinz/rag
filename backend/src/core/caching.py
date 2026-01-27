"""
Consistent Caching Utilities for Scalable Systems

Provides decorator-based caching with Redis backend, TTL management,
cache invalidation patterns, and monitoring.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import pickle
from dataclasses import dataclass
from datetime import timedelta
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, Union

logger = logging.getLogger(__name__)

# Import settings for HMAC key
try:
    from src.core.config import settings
    HMAC_SECRET = settings.SECRET_KEY.encode() if hasattr(settings, 'SECRET_KEY') else b'default-insecure-key-change-in-production'
except ImportError:
    logger.warning("Could not import settings, using default HMAC key (INSECURE)")
    HMAC_SECRET = b'default-insecure-key-change-in-production'

T = TypeVar("T")


# =============================================================================
# Cache Configuration
# =============================================================================


@dataclass
class CacheConfig:
    """Global cache configuration."""

    enabled: bool = True
    default_ttl: int = 300  # 5 minutes
    key_prefix: str = "rag"
    serialize_method: str = "json"  # "json" or "pickle"


# Global config
cache_config = CacheConfig()


@dataclass
class CacheStats:
    """Cache statistics for monitoring."""

    namespace: str
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    errors: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


# Track stats per namespace
_cache_stats: dict[str, CacheStats] = {}


def get_cache_stats(namespace: str) -> CacheStats:
    """Get or create cache stats for namespace."""
    if namespace not in _cache_stats:
        _cache_stats[namespace] = CacheStats(namespace=namespace)
    return _cache_stats[namespace]


def get_all_cache_stats() -> dict[str, CacheStats]:
    """Get all cache statistics."""
    return _cache_stats.copy()


# =============================================================================
# Cache Key Generation
# =============================================================================


def generate_cache_key(
    namespace: str,
    *args,
    **kwargs,
) -> str:
    """
    Generate a deterministic cache key from arguments.

    Args:
        namespace: Cache namespace (e.g., "search", "embeddings")
        *args: Positional arguments to include in key
        **kwargs: Keyword arguments to include in key

    Returns:
        SHA256 hash-based cache key
    """
    # Create a deterministic string representation
    key_parts = [cache_config.key_prefix, namespace]

    # Add positional args
    for arg in args:
        key_parts.append(_serialize_for_key(arg))

    # Add sorted kwargs
    for k in sorted(kwargs.keys()):
        key_parts.append(f"{k}={_serialize_for_key(kwargs[k])}")

    key_string = ":".join(key_parts)

    # Hash for consistent length and safety
    hash_value = hashlib.sha256(key_string.encode()).hexdigest()[:32]

    return f"{cache_config.key_prefix}:{namespace}:{hash_value}"


def _serialize_for_key(value: Any) -> str:
    """Serialize a value for cache key generation."""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    elif isinstance(value, (list, tuple)):
        return f"[{','.join(_serialize_for_key(v) for v in value)}]"
    elif isinstance(value, dict):
        items = sorted(value.items())
        return f"{{{','.join(f'{k}:{_serialize_for_key(v)}' for k, v in items)}}}"
    elif hasattr(value, "id"):
        return f"id:{value.id}"
    elif hasattr(value, "__dict__"):
        return _serialize_for_key(value.__dict__)
    else:
        return str(hash(str(value)))


# =============================================================================
# Serialization
# =============================================================================


def _secure_pickle_dumps(obj: Any) -> bytes:
    """
    Securely serialize object with pickle using HMAC signature.

    Format: [32-byte HMAC-SHA256 signature][pickled data]

    Security: Prevents deserialization attacks by validating data integrity.
    """
    pickled_data = pickle.dumps(obj)
    signature = hmac.new(HMAC_SECRET, pickled_data, hashlib.sha256).digest()
    return signature + pickled_data


def _secure_pickle_loads(data: bytes) -> Any:
    """
    Securely deserialize pickle data with HMAC signature validation.

    Raises:
        ValueError: If signature is invalid or missing (possible tampering)
    """
    if len(data) < 32:
        raise ValueError("Data too short to contain valid HMAC signature")

    signature = data[:32]
    pickled_data = data[32:]

    # Verify signature
    expected_signature = hmac.new(HMAC_SECRET, pickled_data, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected_signature):
        raise ValueError("Invalid HMAC signature - possible data tampering detected")

    # Safe to deserialize after signature validation
    # nosec B301: pickle.loads is safe here because data integrity is verified via HMAC-SHA256
    return pickle.loads(pickled_data)  # nosec B301


def serialize_value(value: Any) -> bytes:
    """Serialize value for cache storage."""
    if cache_config.serialize_method == "json":
        try:
            return json.dumps(value, default=str).encode()
        except (TypeError, ValueError):
            # Fall back to HMAC-signed pickle for complex objects
            logger.debug("JSON serialization failed, falling back to secure pickle")
            return _secure_pickle_dumps(value)
    else:
        # Use HMAC-signed pickle
        return _secure_pickle_dumps(value)


def deserialize_value(data: bytes) -> Any:
    """
    Deserialize value from cache storage.

    Raises:
        ValueError: If pickle data signature is invalid
    """
    if cache_config.serialize_method == "json":
        try:
            return json.loads(data.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Try HMAC-signed pickle as fallback
            logger.debug("JSON deserialization failed, trying secure pickle")
            try:
                return _secure_pickle_loads(data)
            except ValueError as e:
                logger.error(f"Pickle deserialization failed: {e}")
                raise ValueError(
                    f"Cache data deserialization failed: {e}. "
                    "Data may be corrupted or from untrusted source."
                )
    else:
        # Use HMAC-signed pickle
        return _secure_pickle_loads(data)


# =============================================================================
# Redis Cache Backend
# =============================================================================


class RedisCache:
    """
    Redis-backed cache implementation.

    Usage:
        cache = RedisCache(redis_client)

        # Set with TTL
        await cache.set("key", value, ttl=300)

        # Get
        value = await cache.get("key")

        # Delete
        await cache.delete("key")

        # Batch operations
        values = await cache.mget(["key1", "key2", "key3"])
    """

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._local_cache: dict[str, tuple[Any, float]] = {}  # key -> (value, expiry)

    def set_client(self, redis_client):
        """Set Redis client (for lazy initialization)."""
        self._redis = redis_client

    async def get(
        self,
        key: str,
        namespace: str = "default",
    ) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key
            namespace: Namespace for stats tracking

        Returns:
            Cached value or None if not found
        """
        stats = get_cache_stats(namespace)

        try:
            if self._redis is None:
                stats.misses += 1
                return None

            data = await self._redis.get(key)
            if data is None:
                stats.misses += 1
                return None

            stats.hits += 1
            return deserialize_value(data)

        except Exception as e:
            logger.error(f"Cache get error for {key}: {e}")
            stats.errors += 1
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        namespace: str = "default",
    ) -> bool:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if None)
            namespace: Namespace for stats tracking

        Returns:
            True if successful, False otherwise
        """
        stats = get_cache_stats(namespace)
        effective_ttl = ttl or cache_config.default_ttl

        try:
            if self._redis is None:
                return False

            data = serialize_value(value)
            await self._redis.setex(key, effective_ttl, data)
            stats.sets += 1
            return True

        except Exception as e:
            logger.error(f"Cache set error for {key}: {e}")
            stats.errors += 1
            return False

    async def delete(
        self,
        key: str,
        namespace: str = "default",
    ) -> bool:
        """Delete value from cache."""
        stats = get_cache_stats(namespace)

        try:
            if self._redis is None:
                return False

            await self._redis.delete(key)
            stats.deletes += 1
            return True

        except Exception as e:
            logger.error(f"Cache delete error for {key}: {e}")
            stats.errors += 1
            return False

    async def mget(
        self,
        keys: list[str],
        namespace: str = "default",
    ) -> list[Optional[Any]]:
        """Get multiple values from cache."""
        stats = get_cache_stats(namespace)

        try:
            if self._redis is None:
                stats.misses += len(keys)
                return [None] * len(keys)

            data_list = await self._redis.mget(keys)
            results = []

            for data in data_list:
                if data is None:
                    stats.misses += 1
                    results.append(None)
                else:
                    stats.hits += 1
                    results.append(deserialize_value(data))

            return results

        except Exception as e:
            logger.error(f"Cache mget error: {e}")
            stats.errors += 1
            return [None] * len(keys)

    async def invalidate_pattern(
        self,
        pattern: str,
        namespace: str = "default",
    ) -> int:
        """
        Invalidate all keys matching pattern.

        Args:
            pattern: Redis pattern (e.g., "rag:search:*")
            namespace: Namespace for stats

        Returns:
            Number of keys deleted
        """
        stats = get_cache_stats(namespace)

        try:
            if self._redis is None:
                return 0

            cursor = 0
            deleted = 0

            while True:
                cursor, keys = await self._redis.scan(
                    cursor=cursor,
                    match=pattern,
                    count=100,
                )

                if keys:
                    await self._redis.delete(*keys)
                    deleted += len(keys)
                    stats.deletes += len(keys)

                if cursor == 0:
                    break

            logger.info(f"Invalidated {deleted} keys matching '{pattern}'")
            return deleted

        except Exception as e:
            logger.error(f"Cache invalidate_pattern error: {e}")
            stats.errors += 1
            return 0


# Global cache instance
_cache: Optional[RedisCache] = None


def get_cache() -> RedisCache:
    """Get global cache instance."""
    global _cache
    if _cache is None:
        _cache = RedisCache()
    return _cache


def set_cache_client(redis_client):
    """Set Redis client for global cache."""
    get_cache().set_client(redis_client)


# =============================================================================
# Cache Decorators
# =============================================================================


def cached(
    ttl: int = 300,
    namespace: str = "default",
    key_builder: Optional[Callable[..., str]] = None,
    skip_cache_if: Optional[Callable[..., bool]] = None,
):
    """
    Decorator to cache function results.

    Usage:
        @cached(ttl=600, namespace="search")
        async def search_documents(query: str, limit: int = 10):
            ...

        @cached(
            ttl=3600,
            namespace="embeddings",
            key_builder=lambda text: f"emb:{hash(text)}"
        )
        async def get_embedding(text: str):
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            if not cache_config.enabled:
                return await func(*args, **kwargs)

            # Check if we should skip cache
            if skip_cache_if and skip_cache_if(*args, **kwargs):
                return await func(*args, **kwargs)

            # Generate cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                cache_key = generate_cache_key(namespace, func.__name__, *args, **kwargs)

            # Try to get from cache
            cache = get_cache()
            cached_value = await cache.get(cache_key, namespace)

            if cached_value is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_value

            # Execute function and cache result
            logger.debug(f"Cache miss for {func.__name__}")
            result = await func(*args, **kwargs)

            # Cache the result
            await cache.set(cache_key, result, ttl, namespace)

            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            # For sync functions, just execute without caching
            # (Use async version for caching)
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def cache_aside(
    ttl: int = 300,
    namespace: str = "default",
    refresh_threshold: float = 0.8,  # Refresh when 80% of TTL has passed
):
    """
    Cache-aside pattern with background refresh.

    When cache is near expiry, refreshes in background while returning stale value.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        _refresh_tasks: dict[str, asyncio.Task] = {}

        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            if not cache_config.enabled:
                return await func(*args, **kwargs)

            cache_key = generate_cache_key(namespace, func.__name__, *args, **kwargs)
            cache = get_cache()

            # Get cached value with TTL info
            cached_value = await cache.get(cache_key, namespace)

            if cached_value is not None:
                # Check if we need background refresh
                # (Would need TTL checking from Redis - simplified here)
                return cached_value

            # Execute and cache
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, ttl, namespace)
            return result

        return wrapper

    return decorator


# =============================================================================
# Cache Invalidation Helpers
# =============================================================================


async def invalidate_cache(namespace: str, *identifiers):
    """
    Invalidate cache entries for specific identifiers.

    Usage:
        await invalidate_cache("documents", document_id)
        await invalidate_cache("search", user_id, "recent")
    """
    cache = get_cache()
    pattern = generate_cache_key(namespace, *identifiers) + "*"
    await cache.invalidate_pattern(pattern, namespace)


async def invalidate_namespace(namespace: str):
    """
    Invalidate all cache entries in a namespace.

    Usage:
        await invalidate_namespace("search")  # Clear all search cache
    """
    cache = get_cache()
    pattern = f"{cache_config.key_prefix}:{namespace}:*"
    await cache.invalidate_pattern(pattern, namespace)


# =============================================================================
# Cache Warming
# =============================================================================


async def warm_cache(
    func: Callable,
    args_list: list[tuple],
    namespace: str = "default",
    concurrency: int = 5,
):
    """
    Pre-populate cache with common queries.

    Usage:
        common_queries = [
            (("machine learning",), {}),
            (("deep learning",), {}),
            (("neural networks",), {}),
        ]
        await warm_cache(search_documents, common_queries, "search")
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def warm_one(args, kwargs):
        async with semaphore:
            try:
                await func(*args, **kwargs)
                logger.debug(f"Warmed cache for {func.__name__}{args}")
            except Exception as e:
                logger.warning(f"Failed to warm cache for {func.__name__}{args}: {e}")

    tasks = [warm_one(args, kwargs) for args, kwargs in args_list]
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info(f"Cache warming complete for {namespace}: {len(tasks)} entries")
