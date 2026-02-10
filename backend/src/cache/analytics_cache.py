"""
Redis-based caching system for RAG Analytics
Provides high-performance caching for analytics queries, metrics, and reports
"""

import json
import hashlib
from typing import Any, Optional, Dict, List, Union, Callable
from datetime import datetime, timedelta
from functools import wraps
import asyncio
import logging
from dataclasses import dataclass

try:
    import redis.asyncio as redis
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

from src.config.analytics_config import get_analytics_config
from src.exceptions.analytics_exceptions import CacheError, CacheMissError

logger = logging.getLogger(__name__)


@dataclass
class CacheKey:
    """Cache key structure for analytics data"""

    prefix: str
    organization_id: str
    data_type: str
    filters: Dict[str, Any]
    time_range: Optional[tuple] = None

    def generate_key(self) -> str:
        """Generate a unique cache key"""
        # Create a hash of filters and time_range for consistent key length
        filter_str = json.dumps(sorted(self.filters.items()), sort_keys=True)
        time_str = json.dumps(self.time_range) if self.time_range else ""

        hash_input = f"{self.prefix}:{self.organization_id}:{self.data_type}:{filter_str}:{time_str}"
        # Use MD5 for non-security cache key generation (usedforsecurity=False)
        hash_key = hashlib.md5(hash_input.encode(), usedforsecurity=False).hexdigest()

        return f"analytics:{self.prefix}:{self.data_type}:{self.organization_id}:{hash_key}"


class CacheTTL:
    """Cache TTL constants for different data types"""

    # Fast changing data - short TTL
    REALTIME_METRICS = 60  # 1 minute
    DASHBOARD_DATA = 180   # 3 minutes

    # Medium changing data - medium TTL
    AGGREGATED_METRICS = 300  # 5 minutes
    USER_BEHAVIOR = 600       # 10 minutes

    # Slow changing data - long TTL
    QUALITY_SCORES = 1800     # 30 minutes
    PERFORMANCE_SUMMARY = 900 # 15 minutes

    # Reports - very long TTL
    REPORTS = 3600            # 1 hour
    EXPORTS = 7200            # 2 hours


class AnalyticsCache:
    """Redis-based analytics cache with fallback to in-memory cache"""

    def __init__(self):
        self.config = get_analytics_config()
        self.redis_client = None
        self.fallback_cache = {}  # Simple in-memory fallback
        self.fallback_cache_expiry = {}
        self._connected = False

        if REDIS_AVAILABLE and self.config.redis_analytics_url:
            self._init_redis()
        else:
            logger.warning("Redis not available, using in-memory fallback cache")

    async def _init_redis(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = redis.from_url(
                self.config.redis_analytics_url,
                encoding="utf-8",
                decode_responses=True,  # Use string responses for JSON serialization
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )

            # Test connection
            await self.redis_client.ping()
            self._connected = True
            logger.info("Analytics cache connected to Redis")

        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None
            self._connected = False

    def _get_fallback_key(self, key: str) -> str:
        """Get fallback cache key"""
        return f"fallback:{key}"

    def _is_fallback_expired(self, key: str) -> bool:
        """Check if fallback cache entry is expired"""
        expiry = self.fallback_cache_expiry.get(key)
        if expiry is None:
            return True

        return datetime.utcnow() > expiry

    def _cleanup_fallback_cache(self):
        """Clean up expired fallback cache entries"""
        now = datetime.utcnow()
        expired_keys = [
            key for key, expiry in self.fallback_cache_expiry.items()
            if now > expiry
        ]

        for key in expired_keys:
            self.fallback_cache.pop(key, None)
            self.fallback_cache_expiry.pop(key, None)

    async def get(self, key: str, use_fallback: bool = True) -> Any:
        """Get value from cache"""
        try:
            # Try Redis first
            if self.redis_client and self._connected:
                try:
                    value = await self.redis_client.get(key)
                    if value is not None:
                        # Deserialize using JSON (secure, no arbitrary code execution)
                        try:
                            return json.loads(value)
                        except (json.JSONDecodeError, TypeError) as e:
                            logger.warning(f"Failed to deserialize cached value for key {key}: {e}")
                            return None
                except Exception as e:
                    logger.warning(f"Redis get failed for key {key}: {e}")

            # Fallback to in-memory cache
            if use_fallback:
                fallback_key = self._get_fallback_key(key)
                if not self._is_fallback_expired(fallback_key):
                    return self.fallback_cache.get(fallback_key)

            return None

        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int = 300, use_fallback: bool = True) -> bool:
        """Set value in cache"""
        try:
            # Try Redis first
            if self.redis_client and self._connected:
                try:
                    # Serialize value using JSON (secure, prevents arbitrary code execution)
                    try:
                        serialized = json.dumps(value, default=str)
                    except (TypeError, ValueError) as e:
                        logger.warning(f"Failed to serialize value for key {key}: {e}")
                        return False

                    await self.redis_client.setex(key, ttl, serialized)

                    if use_fallback:
                        # Also set in fallback cache
                        fallback_key = self._get_fallback_key(key)
                        self.fallback_cache[fallback_key] = value
                        self.fallback_cache_expiry[fallback_key] = datetime.utcnow() + timedelta(seconds=ttl)

                    return True

                except Exception as e:
                    logger.warning(f"Redis set failed for key {key}: {e}")

            # Fallback to in-memory cache
            if use_fallback:
                fallback_key = self._get_fallback_key(key)
                self.fallback_cache[fallback_key] = value
                self.fallback_cache_expiry[fallback_key] = datetime.utcnow() + timedelta(seconds=ttl)

                # Clean up old entries
                self._cleanup_fallback_cache()

                return True

            return False

        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        try:
            success = True

            # Delete from Redis
            if self.redis_client and self._connected:
                try:
                    await self.redis_client.delete(key)
                except Exception as e:
                    logger.warning(f"Redis delete failed for key {key}: {e}")
                    success = False

            # Delete from fallback cache
            fallback_key = self._get_fallback_key(key)
            self.fallback_cache.pop(fallback_key, None)
            self.fallback_cache_expiry.pop(fallback_key, None)

            return success

        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all cache keys matching pattern"""
        try:
            deleted_count = 0

            # Delete from Redis
            if self.redis_client and self._connected:
                try:
                    keys = await self.redis_client.keys(pattern)
                    if keys:
                        deleted_count = await self.redis_client.delete(*keys)
                except Exception as e:
                    logger.warning(f"Redis pattern delete failed: {e}")

            # Delete from fallback cache
            pattern = pattern.replace('*', '.*')
            fallback_pattern = f"fallback:{pattern}"

            keys_to_delete = [
                key for key in self.fallback_cache.keys()
                if fallback_pattern.replace('.*', '') in key
            ]

            for key in keys_to_delete:
                self.fallback_cache.pop(key, None)
                self.fallback_cache_expiry.pop(key, None)
                deleted_count += 1

            logger.info(f"Invalidated {deleted_count} cache entries matching pattern: {pattern}")
            return deleted_count

        except Exception as e:
            logger.error(f"Cache pattern invalidation error: {e}")
            return 0

    async def get_analytics_data(
        self,
        organization_id: str,
        data_type: str,
        filters: Dict[str, Any],
        time_range: Optional[tuple] = None,
        ttl: Optional[int] = None
    ) -> Optional[Any]:
        """Get analytics data from cache"""
        cache_key = CacheKey(
            prefix="analytics",
            organization_id=organization_id,
            data_type=data_type,
            filters=filters,
            time_range=time_range
        )

        key = cache_key.generate_key()

        if ttl is None:
            ttl = self._get_default_ttl(data_type)

        return await self.get(key)

    async def set_analytics_data(
        self,
        organization_id: str,
        data_type: str,
        data: Any,
        filters: Dict[str, Any],
        time_range: Optional[tuple] = None,
        ttl: Optional[int] = None
    ) -> bool:
        """Set analytics data in cache"""
        cache_key = CacheKey(
            prefix="analytics",
            organization_id=organization_id,
            data_type=data_type,
            filters=filters,
            time_range=time_range
        )

        key = cache_key.generate_key()

        if ttl is None:
            ttl = self._get_default_ttl(data_type)

        return await self.set(key, data, ttl)

    async def invalidate_organization_data(self, organization_id: str) -> int:
        """Invalidate all cache data for an organization"""
        pattern = f"analytics:*:*{organization_id}:*"
        return await self.invalidate_pattern(pattern)

    async def invalidate_data_type(self, data_type: str) -> int:
        """Invalidate all cache data for a specific data type"""
        pattern = f"analytics:*:{data_type}:*"
        return await self.invalidate_pattern(pattern)

    def _get_default_ttl(self, data_type: str) -> int:
        """Get default TTL for data type"""
        ttl_mapping = {
            "realtime_metrics": CacheTTL.REALTIME_METRICS,
            "dashboard_data": CacheTTL.DASHBOARD_DATA,
            "aggregated_metrics": CacheTTL.AGGREGATED_METRICS,
            "user_behavior": CacheTTL.USER_BEHAVIOR,
            "quality_scores": CacheTTL.QUALITY_SCORES,
            "performance_summary": CacheTTL.PERFORMANCE_SUMMARY,
            "reports": CacheTTL.REPORTS,
            "exports": CacheTTL.EXPORTS
        }

        return ttl_mapping.get(data_type, CacheTTL.AGGREGATED_METRICS)

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        stats = {
            "redis_connected": self._connected,
            "fallback_cache_size": len(self.fallback_cache),
            "fallback_cache_keys": list(self.fallback_cache.keys())
        }

        if self.redis_client and self._connected:
            try:
                info = await self.redis_client.info()
                stats.update({
                    "redis_used_memory": info.get("used_memory_human"),
                    "redis_connected_clients": info.get("connected_clients"),
                    "redis_total_commands": info.get("total_commands_processed"),
                    "redis_keyspace_hits": info.get("keyspace_hits", 0),
                    "redis_keyspace_misses": info.get("keyspace_misses", 0)
                })

                # Calculate hit rate
                hits = stats.get("redis_keyspace_hits", 0)
                misses = stats.get("redis_keyspace_misses", 0)
                total = hits + misses
                stats["redis_hit_rate"] = (hits / total * 100) if total > 0 else 0

            except Exception as e:
                logger.warning(f"Failed to get Redis stats: {e}")

        return stats

    async def health_check(self) -> Dict[str, Any]:
        """Perform cache health check"""
        health = {
            "status": "healthy",
            "redis_connected": self._connected,
            "fallback_available": True
        }

        # Check Redis health
        if self.redis_client and self._connected:
            try:
                start_time = datetime.utcnow()
                await self.redis_client.ping()
                ping_time = (datetime.utcnow() - start_time).total_seconds() * 1000

                health["redis_ping_ms"] = ping_time
                health["redis_status"] = "healthy"

                if ping_time > 100:
                    health["redis_status"] = "degraded"

            except Exception as e:
                health["redis_status"] = "unhealthy"
                health["redis_error"] = str(e)
                health["status"] = "degraded"

        # Check fallback cache health
        try:
            test_key = "health_check_test"
            test_value = {"timestamp": datetime.utcnow().isoformat()}

            await self.set(test_key, test_value, ttl=10)
            retrieved = await self.get(test_key)

            if retrieved == test_value:
                health["fallback_status"] = "healthy"
            else:
                health["fallback_status"] = "unhealthy"
                health["status"] = "degraded"

            await self.delete(test_key)

        except Exception as e:
            health["fallback_status"] = "unhealthy"
            health["fallback_error"] = str(e)
            health["status"] = "unhealthy"

        return health


# Global cache instance
_analytics_cache = AnalyticsCache()


def get_analytics_cache() -> AnalyticsCache:
    """Get the global analytics cache instance"""
    return _analytics_cache


def cached_analytics(data_type: str, ttl: Optional[int] = None):
    """Decorator for caching analytics function results"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract organization_id from kwargs or args
            organization_id = kwargs.get("organization_id")
            if not organization_id and args:
                organization_id = args[0]  # Assume first arg is organization_id

            if not organization_id:
                # Skip caching if no organization_id
                return await func(*args, **kwargs)

            # Create cache key from function args
            cache_kwargs = {k: v for k, v in kwargs.items() if k != "organization_id"}

            # Try to get from cache
            cache = get_analytics_cache()
            cached_result = await cache.get_analytics_data(
                organization_id=organization_id,
                data_type=data_type,
                filters=cache_kwargs,
                time_range=kwargs.get("time_range"),
                ttl=ttl
            )

            if cached_result is not None:
                return cached_result

            # Execute function and cache result
            result = await func(*args, **kwargs)

            await cache.set_analytics_data(
                organization_id=organization_id,
                data_type=data_type,
                data=result,
                filters=cache_kwargs,
                time_range=kwargs.get("time_range"),
                ttl=ttl
            )

            return result

        return wrapper
    return decorator


async def invalidate_analytics_cache(organization_id: Optional[str] = None, data_type: Optional[str] = None):
    """Invalidate analytics cache entries"""
    cache = get_analytics_cache()

    if organization_id and data_type:
        # Invalidate specific organization and data type
        await cache.invalidate_organization_data(organization_id)
    elif organization_id:
        # Invalidate all data for organization
        await cache.invalidate_organization_data(organization_id)
    elif data_type:
        # Invalidate all data of specific type
        await cache.invalidate_data_type(data_type)
    else:
        # Invalidate all analytics cache
        await cache.invalidate_pattern("analytics:*")


# Cache warming functions
async def warm_organization_cache(organization_id: str, days: int = 7):
    """Warm cache for an organization with common queries"""
    from datetime import datetime, timedelta

    cache = get_analytics_cache()

    # Common time ranges
    end_date = datetime.utcnow()
    start_dates = [
        end_date - timedelta(days=1),    # Last 24 hours
        end_date - timedelta(days=7),    # Last 7 days
        end_date - timedelta(days=30),   # Last 30 days
    ]

    # Common filters for different data types
    common_data_types = [
        "quality_metrics",
        "user_behavior",
        "performance_metrics",
        "dashboard_data"
    ]

    warmed_count = 0

    for data_type in common_data_types:
        for start_date in start_dates:
            filters = {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            }

            # Pre-populate cache (this would typically trigger the actual data loading)
            key = CacheKey(
                prefix="analytics",
                organization_id=organization_id,
                data_type=data_type,
                filters=filters,
                time_range=(start_date.isoformat(), end_date.isoformat())
            ).generate_key()

            # Set empty placeholder to ensure cache key exists
            await cache.set(key, {"cached": True, "warmed_at": datetime.utcnow().isoformat()}, ttl=300)
            warmed_count += 1

    logger.info(f"Warmed {warmed_count} cache entries for organization {organization_id}")
    return warmed_count