"""
A/B Testing Multi-Level Caching Service
Provides comprehensive caching strategy with multiple cache layers and intelligent invalidation
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import zlib

from ..core.config import settings
from ..cache.analytics_cache import analytics_cache

logger = logging.getLogger(__name__)


class CacheLevel(Enum):
    """Cache levels in hierarchy"""
    MEMORY = "memory"           # L1: In-memory cache (fastest)
    REDIS = "redis"             # L2: Redis cache (fast)
    DATABASE = "database"       # L3: Pre-computed database views (slow)


class CachePolicy(Enum):
    """Cache eviction policies"""
    LRU = "lru"                 # Least Recently Used
    LFU = "lfu"                 # Least Frequently Used
    TTL = "ttl"                 # Time To Live
    SIZE_BASED = "size_based"   # Based on cache size


class CacheStrategy(Enum):
    """Caching strategies"""
    WRITE_THROUGH = "write_through"     # Write to cache and backend
    WRITE_BEHIND = "write_behind"       # Write to cache, async to backend
    WRITE_AROUND = "write_around"       # Write directly to backend
    READ_THROUGH = "read_through"       # Read from cache, load from backend if miss
    CACHE_ASIDE = "cache_aside"         # Application manages cache


@dataclass
class CacheConfig:
    """Configuration for cache level"""
    max_size: int = 1000              # Maximum number of items
    ttl_seconds: int = 300            # Default TTL in seconds
    policy: CachePolicy = CachePolicy.LRU
    compression_enabled: bool = True
    cleanup_interval: int = 60         # Cleanup interval in seconds


@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    key: str
    value: Any
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    size_bytes: int = 0
    ttl_seconds: Optional[int] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if entry is expired"""
        if self.ttl_seconds is None:
            return False
        return (datetime.utcnow() - self.created_at).total_seconds() > self.ttl_seconds

    def touch(self):
        """Update access time and count"""
        self.last_accessed = datetime.utcnow()
        self.access_count += 1


class MemoryCache:
    """In-memory L1 cache implementation"""

    def __init__(self, config: CacheConfig):
        self.config = config
        self.cache: Dict[str, CacheEntry] = {}
        self.access_order: List[str] = []  # For LRU
        self.cleanup_task: Optional[asyncio.Task] = None

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        entry = self.cache.get(key)
        if entry is None:
            return None

        if entry.is_expired():
            await self.delete(key)
            return None

        entry.touch()
        self._update_access_order(key)
        return entry.value

    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
        tags: Optional[List[str]] = None
    ):
        """Set value in cache"""
        now = datetime.utcnow()
        size_bytes = self._calculate_size(value)

        entry = CacheEntry(
            key=key,
            value=value,
            created_at=now,
            last_accessed=now,
            size_bytes=size_bytes,
            ttl_seconds=ttl_seconds or self.config.ttl_seconds,
            tags=tags or []
        )

        # Check if we need to evict entries
        await self._ensure_capacity()

        # Add or update entry
        if key in self.cache:
            del self.cache[key]
            if key in self.access_order:
                self.access_order.remove(key)

        self.cache[key] = entry
        self.access_order.append(key)

    async def delete(self, key: str) -> bool:
        """Delete entry from cache"""
        if key in self.cache:
            del self.cache[key]
            if key in self.access_order:
                self.access_order.remove(key)
            return True
        return False

    async def clear(self, pattern: Optional[str] = None):
        """Clear cache entries"""
        if pattern:
            keys_to_delete = [
                key for key in self.cache.keys()
                if pattern in key
            ]
            for key in keys_to_delete:
                await self.delete(key)
        else:
            self.cache.clear()
            self.access_order.clear()

    async def invalidate_by_tags(self, tags: List[str]):
        """Invalidate entries by tags"""
        keys_to_delete = []
        for key, entry in self.cache.items():
            if any(tag in entry.tags for tag in tags):
                keys_to_delete.append(key)

        for key in keys_to_delete:
            await self.delete(key)

    def _update_access_order(self, key: str):
        """Update LRU access order"""
        if key in self.access_order:
            self.access_order.remove(key)
        self.access_order.append(key)

    async def _ensure_capacity(self):
        """Ensure cache doesn't exceed capacity"""
        while len(self.cache) >= self.config.max_size:
            await self._evict_entry()

    async def _evict_entry(self):
        """Evict entry based on policy"""
        if not self.cache:
            return

        if self.config.policy == CachePolicy.LRU:
            # Evict least recently used
            key = self.access_order[0]
        elif self.config.policy == CachePolicy.LFU:
            # Evict least frequently used
            key = min(self.cache.keys(), key=lambda k: self.cache[k].access_count)
        else:
            # Default to LRU
            key = self.access_order[0]

        await self.delete(key)

    def _calculate_size(self, value: Any) -> int:
        """Calculate size of value in bytes"""
        # Always use JSON for security
        data = json.dumps(value, default=str).encode()

        if self.config.compression_enabled:
            data = zlib.compress(data)

        return len(data)

    async def cleanup_expired(self):
        """Clean up expired entries"""
        expired_keys = [
            key for key, entry in self.cache.items()
            if entry.is_expired()
        ]

        for key in expired_keys:
            await self.delete(key)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_size = sum(entry.size_bytes for entry in self.cache.values())
        return {
            "entries": len(self.cache),
            "max_entries": self.config.max_size,
            "total_size_bytes": total_size,
            "hit_rate": 0.0,  # Would need to track hits/misses
            "policy": self.config.policy.value
        }


class RedisCache:
    """Redis L2 cache implementation"""

    def __init__(self, config: CacheConfig):
        self.config = config
        self.redis_client = None
        self.key_prefix = "ab_cache:"

    async def initialize(self):
        """Initialize Redis connection"""
        try:
            import redis.asyncio as redis
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=False,  # Handle binary data
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            await self.redis_client.ping()
            logger.info("Redis cache initialized")
        except Exception as e:
            logger.warning(f"Redis not available for caching: {e}")
            self.redis_client = None

    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis cache"""
        if not self.redis_client:
            return None

        try:
            redis_key = self._get_redis_key(key)
            data = await self.redis_client.get(redis_key)
            if data is None:
                return None

            return self._deserialize(data)
        except Exception as e:
            logger.error(f"Error getting from Redis cache: {e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
        tags: Optional[List[str]] = None
    ):
        """Set value in Redis cache"""
        if not self.redis_client:
            return

        try:
            redis_key = self._get_redis_key(key)
            data = self._serialize(value)
            ttl = ttl_seconds or self.config.ttl_seconds

            # Set main cache entry
            await self.redis_client.setex(redis_key, ttl, data)

            # Store tags for invalidation
            if tags:
                for tag in tags:
                    tag_key = f"{self.key_prefix}tag:{tag}"
                    await self.redis_client.sadd(tag_key, redis_key)
                    await self.redis_client.expire(tag_key, ttl)

        except Exception as e:
            logger.error(f"Error setting in Redis cache: {e}")

    async def delete(self, key: str) -> bool:
        """Delete entry from Redis cache"""
        if not self.redis_client:
            return False

        try:
            redis_key = self._get_redis_key(key)
            result = await self.redis_client.delete(redis_key)
            return result > 0
        except Exception as e:
            logger.error(f"Error deleting from Redis cache: {e}")
            return False

    async def invalidate_by_tags(self, tags: List[str]):
        """Invalidate entries by tags"""
        if not self.redis_client:
            return

        try:
            for tag in tags:
                tag_key = f"{self.key_prefix}tag:{tag}"
                keys = await self.redis_client.smembers(tag_key)
                if keys:
                    await self.redis_client.delete(*keys)
                await self.redis_client.delete(tag_key)
        except Exception as e:
            logger.error(f"Error invalidating by tags in Redis: {e}")

    def _get_redis_key(self, key: str) -> str:
        """Get Redis key with prefix"""
        return f"{self.key_prefix}{key}"

    def _serialize(self, value: Any) -> bytes:
        """Serialize value for storage"""
        # Always use JSON for security (avoid pickle security issues)
        data = json.dumps(value, default=str).encode()

        if self.config.compression_enabled:
            data = zlib.compress(data)

        return data

    def _deserialize(self, data: bytes) -> Any:
        """Deserialize value from storage"""
        if self.config.compression_enabled:
            data = zlib.decompress(data)

        # Always use JSON for security
        return json.loads(data.decode())


class MultiLevelCache:
    """Multi-level cache manager"""

    def __init__(self):
        # Initialize cache levels with different configurations
        self.memory_cache = MemoryCache(CacheConfig(
            max_size=500,
            ttl_seconds=300,  # 5 minutes
            policy=CachePolicy.LRU,
            compression_enabled=False  # No compression for memory
        ))

        self.redis_cache = RedisCache(CacheConfig(
            max_size=10000,
            ttl_seconds=3600,  # 1 hour
            policy=CachePolicy.TTL,
            compression_enabled=True
        ))

        self.cache_stats = {
            "l1_hits": 0,
            "l2_hits": 0,
            "misses": 0,
            "total_requests": 0
        }

        self._initialized = False
        self._cleanup_task = None  # Track background cleanup task

    async def initialize(self):
        """Initialize cache components"""
        if not self._initialized:
            await self.redis_cache.initialize()
            self._initialized = True

            # Start background cleanup task with proper tracking
            if self._cleanup_task is None or self._cleanup_task.done():
                self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
                logger.debug("Started background cleanup task")
            else:
                logger.warning("Background cleanup task already running, skipping start")

            logger.info("Multi-level cache initialized")

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache hierarchy"""
        if not self._initialized:
            await self.initialize()

        self.cache_stats["total_requests"] += 1

        # Try L1 cache (memory)
        value = await self.memory_cache.get(key)
        if value is not None:
            self.cache_stats["l1_hits"] += 1
            return value

        # Try L2 cache (Redis)
        value = await self.redis_cache.get(key)
        if value is not None:
            self.cache_stats["l2_hits"] += 1
            # Promote to L1 cache with original TTL and tags
            await self._promote_to_l1(key, value)
            return value

        # Cache miss
        self.cache_stats["misses"] += 1
        return None

    async def set(
        self,
        key: str,
        value: Any,
        l1_ttl: Optional[int] = None,
        l2_ttl: Optional[int] = None,
        tags: Optional[List[str]] = None
    ):
        """Set value in cache hierarchy"""
        if not self._initialized:
            await self.initialize()

        # Set in both cache levels
        await asyncio.gather(
            self.memory_cache.set(key, value, ttl_seconds=l1_ttl, tags=tags),
            self.redis_cache.set(key, value, ttl_seconds=l2_ttl, tags=tags)
        )

    async def delete(self, key: str):
        """Delete from all cache levels"""
        if not self._initialized:
            await self.initialize()

        await asyncio.gather(
            self.memory_cache.delete(key),
            self.redis_cache.delete(key)
        )

    async def invalidate_by_tags(self, tags: List[str]):
        """Invalidate entries by tags across all levels"""
        if not self._initialized:
            await self.initialize()

        await asyncio.gather(
            self.memory_cache.invalidate_by_tags(tags),
            self.redis_cache.invalidate_by_tags(tags)
        )

    async def clear_pattern(self, pattern: str):
        """Clear entries matching pattern"""
        if not self._initialized:
            await self.initialize()

        await self.memory_cache.clear(pattern)
        # Redis pattern clearing would need SCAN operation
        # For now, just clear memory cache

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        total_requests = self.cache_stats["total_requests"]
        hit_rate = (
            (self.cache_stats["l1_hits"] + self.cache_stats["l2_hits"]) /
            total_requests if total_requests > 0 else 0
        )

        return {
            "total_requests": total_requests,
            "l1_hits": self.cache_stats["l1_hits"],
            "l2_hits": self.cache_stats["l2_hits"],
            "misses": self.cache_stats["misses"],
            "hit_rate": hit_rate,
            "l1_hit_rate": (
                self.cache_stats["l1_hits"] / total_requests
                if total_requests > 0 else 0
            ),
            "l2_hit_rate": (
                self.cache_stats["l2_hits"] / total_requests
                if total_requests > 0 else 0
            ),
            "memory_cache": self.memory_cache.get_stats()
        }

    async def _promote_to_l1(self, key: str, value: Any):
        """Promote value from L2 to L1 cache with proper TTL and tags preservation"""
        try:
            # Check if Redis client is available
            if not self.redis_cache.redis_client:
                # No Redis available, use default memory cache settings
                await self.memory_cache.set(key, value)
                logger.debug(f"Promoted key '{key}' to L1 cache with default TTL (no Redis)")
                return

            # Get metadata from L2 cache to preserve TTL and tags
            redis_key = self.redis_cache._get_redis_key(key)
            ttl = await self.redis_cache.redis_client.ttl(redis_key)

            # Handle special TTL values:
            # -2 = key does not exist
            # -1 = key exists but has no expiry
            # >0 = remaining seconds until expiry
            if ttl == -2:
                # Key missing in Redis, use memory cache default
                l1_ttl = self.memory_cache.config.ttl_seconds
            elif ttl == -1:
                # Key exists but no expiry, use memory cache default
                l1_ttl = self.memory_cache.config.ttl_seconds
            elif ttl > 0:
                # Use minimum of remaining TTL and memory cache default
                l1_ttl = min(ttl, self.memory_cache.config.ttl_seconds)
            else:
                # Unexpected TTL value, use default
                l1_ttl = self.memory_cache.config.ttl_seconds

            # Get tags from L2 cache if they exist
            tags = []
            try:
                # Look for tag keys that contain this cache key
                tag_pattern = f"{self.redis_cache.key_prefix}tag:*"
                async for tag_key in self.redis_cache.redis_client.scan_iter(match=tag_pattern):
                    if await self.redis_cache.redis_client.sismember(tag_key, redis_key):
                        # Extract tag name from key, handle both bytes and str
                        if isinstance(tag_key, bytes):
                            tag_key_str = tag_key.decode('utf-8')
                        else:
                            tag_key_str = tag_key
                        tag_name = tag_key_str.replace(f"{self.redis_cache.key_prefix}tag:", "")
                        tags.append(tag_name)
            except Exception as tag_error:
                logger.warning(f"Error retrieving tags for key '{key}': {tag_error}")
                # Continue without tags

            # Promote to L1 with appropriate TTL
            await self.memory_cache.set(key, value, ttl_seconds=l1_ttl, tags=tags)
            logger.debug(f"Promoted key '{key}' to L1 cache with TTL: {l1_ttl}s, tags: {tags}")

        except Exception as e:
            logger.error(f"Error promoting key '{key}' to L1 cache: {e}")
            # Fallback: promote without TTL and tags
            await self.memory_cache.set(key, value)

    async def _periodic_cleanup(self):
        """Periodic cleanup of expired entries"""
        logger.debug("Background cleanup task started")
        try:
            while True:
                try:
                    await asyncio.sleep(60)  # Run every minute
                    await self.memory_cache.cleanup_expired()
                except asyncio.CancelledError:
                    logger.debug("Background cleanup task cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error in periodic cache cleanup: {e}")
                    # Continue running even if there's an error
        except asyncio.CancelledError:
            logger.debug("Background cleanup task cancelled during sleep")
        finally:
            logger.debug("Background cleanup task stopped")

    async def shutdown(self):
        """Gracefully shutdown the cache and cleanup tasks"""
        logger.info("Shutting down multi-level cache")

        # Cancel background cleanup task
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                logger.debug("Background cleanup task cancelled successfully")
            except Exception as e:
                logger.error(f"Error cancelling cleanup task: {e}")

        self._cleanup_task = None
        self._initialized = False
        logger.info("Multi-level cache shutdown complete")


class CacheManager:
    """High-level cache manager for A/B testing operations"""

    def __init__(self):
        self.cache = MultiLevelCache()
        self.key_generators = {
            "experiment": self._generate_experiment_key,
            "variant": self._generate_variant_key,
            "assignment": self._generate_assignment_key,
            "metrics": self._generate_metrics_key,
            "analysis": self._generate_analysis_key,
            "user_segments": self._generate_user_segments_key
        }

    async def initialize(self):
        """Initialize cache manager"""
        await self.cache.initialize()

    async def get_experiment(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        """Get cached experiment data"""
        key = self.key_generators["experiment"](experiment_id)
        return await self.cache.get(key)

    async def set_experiment(
        self,
        experiment_id: str,
        data: Dict[str, Any],
        ttl_seconds: int = 300
    ):
        """Cache experiment data"""
        key = self.key_generators["experiment"](experiment_id)
        tags = ["experiment", f"experiment:{experiment_id}"]
        # L2 should have longer TTL for persistence (typically 4x L1 TTL)
        l2_ttl = ttl_seconds * 4
        await self.cache.set(key, data, l1_ttl=ttl_seconds, l2_ttl=l2_ttl, tags=tags)

    async def get_variant_assignment(
        self,
        user_id: str,
        experiment_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get cached variant assignment"""
        key = self.key_generators["assignment"](user_id, experiment_id)
        return await self.cache.get(key)

    async def set_variant_assignment(
        self,
        user_id: str,
        experiment_id: str,
        assignment: Dict[str, Any],
        ttl_seconds: int = 3600
    ):
        """Cache variant assignment"""
        key = self.key_generators["assignment"](user_id, experiment_id)
        tags = ["assignment", f"user:{user_id}", f"experiment:{experiment_id}"]
        # L2 should have longer TTL for persistence (typically 2x L1 TTL for assignments)
        l2_ttl = ttl_seconds * 2
        await self.cache.set(key, assignment, l1_ttl=ttl_seconds, l2_ttl=l2_ttl, tags=tags)

    async def get_experiment_metrics(
        self,
        experiment_id: str,
        time_range: str = "24h"
    ) -> Optional[Dict[str, Any]]:
        """Get cached experiment metrics"""
        key = self.key_generators["metrics"](experiment_id, time_range)
        return await self.cache.get(key)

    async def set_experiment_metrics(
        self,
        experiment_id: str,
        metrics: Dict[str, Any],
        time_range: str = "24h",
        ttl_seconds: int = 600
    ):
        """Cache experiment metrics"""
        key = self.key_generators["metrics"](experiment_id, time_range)
        tags = ["metrics", f"experiment:{experiment_id}", f"time_range:{time_range}"]
        # L2 should have longer TTL for persistence (typically 3x L1 TTL for metrics)
        l2_ttl = ttl_seconds * 3
        await self.cache.set(key, metrics, l1_ttl=ttl_seconds, l2_ttl=l2_ttl, tags=tags)

    async def get_analysis_result(
        self,
        experiment_id: str,
        confidence_level: float
    ) -> Optional[Dict[str, Any]]:
        """Get cached statistical analysis result"""
        key = self.key_generators["analysis"](experiment_id, confidence_level)
        return await self.cache.get(key)

    async def set_analysis_result(
        self,
        experiment_id: str,
        confidence_level: float,
        result: Dict[str, Any],
        ttl_seconds: int = 1800
    ):
        """Cache statistical analysis result"""
        key = self.key_generators["analysis"](experiment_id, confidence_level)
        tags = ["analysis", f"experiment:{experiment_id}"]
        # L2 should have longer TTL for persistence (typically 6x L1 TTL for analysis results)
        l2_ttl = ttl_seconds * 6
        await self.cache.set(key, result, l1_ttl=ttl_seconds, l2_ttl=l2_ttl, tags=tags)

    async def invalidate_experiment_cache(self, experiment_id: str):
        """Invalidate all cache entries for an experiment"""
        tags = [f"experiment:{experiment_id}"]
        await self.cache.invalidate_by_tags(tags)

    async def invalidate_user_cache(self, user_id: str):
        """Invalidate all cache entries for a user"""
        tags = [f"user:{user_id}"]
        await self.cache.invalidate_by_tags(tags)

    def _generate_experiment_key(self, experiment_id: str) -> str:
        """Generate cache key for experiment"""
        return f"experiment:{experiment_id}"

    def _generate_variant_key(self, variant_id: str) -> str:
        """Generate cache key for variant"""
        return f"variant:{variant_id}"

    def _generate_assignment_key(self, user_id: str, experiment_id: str) -> str:
        """Generate cache key for assignment"""
        return f"assignment:{user_id}:{experiment_id}"

    def _generate_metrics_key(self, experiment_id: str, time_range: str) -> str:
        """Generate cache key for metrics"""
        return f"metrics:{experiment_id}:{time_range}"

    def _generate_analysis_key(self, experiment_id: str, confidence_level: float) -> str:
        """Generate cache key for analysis"""
        return f"analysis:{experiment_id}:{confidence_level}"

    def _generate_user_segments_key(self, organization_id: str) -> str:
        """Generate cache key for user segments"""
        return f"user_segments:{organization_id}"

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        return self.cache.get_cache_stats()


# Global cache manager instance
cache_manager = CacheManager()


# Decorator for caching function results

def cache_result(
    key_generator: Callable,
    ttl_seconds: int = 300,
    cache_levels: List[str] = None
):
    """
    Decorator to cache function results
    """
    if cache_levels is None:
        cache_levels = ["memory", "redis"]

    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = key_generator(*args, **kwargs)

            # Try to get from cache
            cached_result = await cache_manager.cache.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache_manager.cache.set(cache_key, result, ttl_seconds=ttl_seconds)

            return result
        return wrapper
    return decorator