"""
Redis caching utilities for microservices
"""

import json
import logging
import hashlib
from typing import Any, Optional, Dict, List
import redis.asyncio as redis

from ..config.knowledge_graph_config import config

logger = logging.getLogger(__name__)


async def get_redis_client() -> redis.Redis:
    """Get Redis client"""
    return redis.from_url(
        config.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
    )


def safe_serialize(obj: Any) -> str:
    """Safely serialize object to JSON"""
    try:
        return json.dumps(obj, default=str, ensure_ascii=False)
    except (TypeError, ValueError) as e:
        logger.error(f"JSON serialization error: {e}")
        # Fallback to string representation
        return json.dumps({"error": "serialization_failed", "data": str(obj)})


def safe_deserialize(value: str) -> Any:
    """Safely deserialize JSON value"""
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"JSON deserialization error: {e}")
        return value


async def cache_get(
    client: redis.Redis,
    key: str,
    deserialize: bool = True
) -> Optional[Any]:
    """Get value from cache"""
    try:
        value = await client.get(key)
        if value is None:
            return None

        if deserialize:
            return safe_deserialize(value)
        return value

    except Exception as e:
        logger.error(f"Cache get error for key {key}: {e}")
        return None


async def cache_set(
    client: redis.Redis,
    key: str,
    value: Any,
    ttl: Optional[int] = None,
    serialize: bool = True
) -> bool:
    """Set value in cache"""
    try:
        if ttl is None:
            ttl = config.REDIS_CACHE_TTL

        if serialize:
            serialized_value = safe_serialize(value)
        else:
            serialized_value = str(value)

        result = await client.setex(key, ttl, serialized_value)
        return result is True

    except Exception as e:
        logger.error(f"Cache set error for key {key}: {e}")
        return False


async def cache_delete(client: redis.Redis, key: str) -> bool:
    """Delete key from cache"""
    try:
        result = await client.delete(key)
        return result > 0
    except Exception as e:
        logger.error(f"Cache delete error for key {key}: {e}")
        return False


async def cache_exists(client: redis.Redis, key: str) -> bool:
    """Check if key exists in cache"""
    try:
        result = await client.exists(key)
        return result > 0
    except Exception as e:
        logger.error(f"Cache exists error for key {key}: {e}")
        return False


async def cache_increment(
    client: redis.Redis,
    key: str,
    amount: int = 1,
    ttl: Optional[int] = None
) -> Optional[int]:
    """Increment counter in cache"""
    try:
        result = await client.incrby(key, amount)
        if ttl and result == amount:  # First time setting
            await client.expire(key, ttl)
        return result
    except Exception as e:
        logger.error(f"Cache increment error for key {key}: {e}")
        return None


async def cache_get_multiple(client: redis.Redis, keys: List[str]) -> Dict[str, Any]:
    """Get multiple values from cache"""
    try:
        values = await client.mget(keys)
        return {
            key: safe_deserialize(value) if value else None
            for key, value in zip(keys, values)
        }
    except Exception as e:
        logger.error(f"Cache get multiple error: {e}")
        return {}


async def cache_set_multiple(
    client: redis.Redis,
    mapping: Dict[str, Any],
    ttl: Optional[int] = None
) -> bool:
    """Set multiple values in cache"""
    try:
        serialized_mapping = {
            key: safe_serialize(value)
            for key, value in mapping.items()
        }

        # Use pipeline for atomic operation
        async with client.pipeline() as pipe:
            await pipe.mset(serialized_mapping)
            if ttl:
                for key in serialized_mapping.keys():
                    await pipe.expire(key, ttl)
            await pipe.execute()

        return True

    except Exception as e:
        logger.error(f"Cache set multiple error: {e}")
        return False


class CacheManager:
    """Advanced cache manager with pattern matching and bulk operations"""

    def __init__(self, prefix: str = "kg"):
        self.prefix = prefix

    def _make_key(self, key: str) -> str:
        """Create namespaced key"""
        return f"{self.prefix}:{key}"

    async def get(self, client: redis.Redis, key: str) -> Optional[Any]:
        """Get value from cache"""
        return await cache_get(client, self._make_key(key))

    async def set(
        self,
        client: redis.Redis,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """Set value in cache"""
        return await cache_set(client, self._make_key(key), value, ttl)

    async def delete(self, client: redis.Redis, key: str) -> bool:
        """Delete key from cache"""
        return await cache_delete(client, self._make_key(key))

    async def exists(self, client: redis.Redis, key: str) -> bool:
        """Check if key exists"""
        return await cache_exists(client, self._make_key(key))

    async def get_multiple(self, client: redis.Redis, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from cache"""
        namespaced_keys = [self._make_key(key) for key in keys]
        results = await cache_get_multiple(client, namespaced_keys)

        # Remove namespace from keys in result
        return {
            key.replace(f"{self.prefix}:", ""): value
            for key, value in results.items()
        }

    async def set_multiple(
        self,
        client: redis.Redis,
        mapping: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """Set multiple values in cache"""
        namespaced_mapping = {
            self._make_key(key): value
            for key, value in mapping.items()
        }
        return await cache_set_multiple(client, namespaced_mapping, ttl)

    async def delete_pattern(self, client: redis.Redis, pattern: str) -> int:
        """Delete keys matching pattern"""
        try:
            full_pattern = self._make_key(pattern)
            keys = await client.keys(full_pattern)
            if keys:
                return await client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache delete pattern error for pattern {pattern}: {e}")
            return 0

    async def get_ttl(self, client: redis.Redis, key: str) -> Optional[int]:
        """Get time to live for key"""
        try:
            return await client.ttl(self._make_key(key))
        except Exception as e:
            logger.error(f"Cache TTL error for key {key}: {e}")
            return None

    async def set_ttl(self, client: redis.Redis, key: str, ttl: int) -> bool:
        """Set time to live for key"""
        try:
            result = await client.expire(self._make_key(key), ttl)
            return result is True
        except Exception as e:
            logger.error(f"Cache set TTL error for key {key}: {e}")
            return False


# Cache key generators
def entity_cache_key(entity_id: str, tenant_id: str) -> str:
    """Generate cache key for entity"""
    return f"entity:{entity_id}:tenant:{tenant_id}"


def relationship_cache_key(relationship_id: str, tenant_id: str) -> str:
    """Generate cache key for relationship"""
    return f"relationship:{relationship_id}:tenant:{tenant_id}"


def search_cache_key(query: str, filters: dict, tenant_id: str) -> str:
    """Generate cache key for search results"""
    # Create deterministic hash for complex parameters
    filter_str = json.dumps(sorted(filters.items()), sort_keys=True)
    combined = f"{query}:{filter_str}"
    hash_obj = hashlib.md5(combined.encode())
    return f"search:{hash_obj.hexdigest()}:tenant:{tenant_id}"


def analytics_cache_key(analytics_type: str, params: dict, tenant_id: str) -> str:
    """Generate cache key for analytics results"""
    param_str = json.dumps(sorted(params.items()), sort_keys=True)
    combined = f"{analytics_type}:{param_str}"
    hash_obj = hashlib.md5(combined.encode())
    return f"analytics:{hash_obj.hexdigest()}:tenant:{tenant_id}"


def user_rate_limit_key(user_id: str, window: str) -> str:
    """Generate rate limit key for user"""
    return f"rate_limit:user:{user_id}:{window}"


def tenant_metrics_key(tenant_id: str, metric: str, timestamp: str) -> str:
    """Generate metrics key for tenant"""
    return f"metrics:{metric}:tenant:{tenant_id}:{timestamp}"


def websocket_connection_key(tenant_id: str) -> str:
    """Generate WebSocket connection tracking key"""
    return f"websocket:connections:tenant:{tenant_id}"


# Global cache manager instances
entity_cache = CacheManager("entity")
relationship_cache = CacheManager("relationship")
search_cache = CacheManager("search")
analytics_cache = CacheManager("analytics")
metrics_cache = CacheManager("metrics")
websocket_cache = CacheManager("websocket")


async def clear_tenant_cache(client: redis.Redis, tenant_id: str) -> int:
    """Clear all cache entries for a tenant"""
    patterns = [
        f"entity:*:tenant:{tenant_id}",
        f"relationship:*:tenant:{tenant_id}",
        f"search:*:tenant:{tenant_id}",
        f"analytics:*:tenant:{tenant_id}",
        f"metrics:*:tenant:{tenant_id}",
        f"websocket:*:tenant:{tenant_id}"
    ]

    total_deleted = 0
    for pattern in patterns:
        try:
            keys = await client.keys(pattern)
            if keys:
                deleted = await client.delete(*keys)
                total_deleted += deleted
                logger.info(f"Cleared {deleted} keys for pattern {pattern}")
        except Exception as e:
            logger.error(f"Error clearing cache pattern {pattern}: {e}")

    return total_deleted


async def cache_health_check(client: redis.Redis) -> dict:
    """Check Redis cache health"""
    try:
        # Test basic operations
        test_key = "health_check_test"
        await client.set(test_key, "test", ex=10)
        value = await client.get(test_key)
        await client.delete(test_key)

        # Get Redis info
        info = await client.info()

        return {
            "status": "healthy" if value == "test" else "unhealthy",
            "connected_clients": info.get("connected_clients", 0),
            "used_memory": info.get("used_memory_human", "unknown"),
            "uptime_in_seconds": info.get("uptime_in_seconds", 0),
            "total_commands_processed": info.get("total_commands_processed", 0)
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


# Cache statistics and monitoring
async def get_cache_stats(client: redis.Redis) -> dict:
    """Get cache performance statistics"""
    try:
        info = await client.info()

        return {
            "total_commands_processed": info.get("total_commands_processed", 0),
            "total_connections_received": info.get("total_connections_received", 0),
            "keyspace_hits": info.get("keyspace_hits", 0),
            "keyspace_misses": info.get("keyspace_misses", 0),
            "hit_rate": (
                info.get("keyspace_hits", 0) /
                max(info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0), 1)
            ),
            "used_memory": info.get("used_memory", 0),
            "used_memory_human": info.get("used_memory_human", "0B"),
            "connected_clients": info.get("connected_clients", 0),
            "uptime_in_seconds": info.get("uptime_in_seconds", 0),
            "instantaneous_ops_per_sec": info.get("instantaneous_ops_per_sec", 0)
        }

    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return {}


# Cache warming utilities
async def warm_entity_cache(
    client: redis.Redis,
    entities: List[Dict[str, Any]],
    tenant_id: str,
    ttl: int = 3600
) -> int:
    """Warm cache with frequently accessed entities"""
    try:
        mapping = {}
        for entity in entities:
            key = entity_cache_key(entity["id"], tenant_id)
            mapping[key] = entity

        if mapping:
            success = await cache_set_multiple(client, mapping, ttl)
            return len(mapping) if success else 0

        return 0

    except Exception as e:
        logger.error(f"Error warming entity cache: {e}")
        return 0