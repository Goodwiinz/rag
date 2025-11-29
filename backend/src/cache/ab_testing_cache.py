"""
A/B Testing Caching Strategy and Redis Data Structures

This module provides comprehensive caching strategies for the A/B testing system,
including Redis data structures, cache invalidation policies, and performance
optimizations for high-throughput scenarios (10K+ queries/hour).
"""

import json
import gzip
import hashlib
import struct
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Union, Tuple, Set
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import asyncio
import redis.asyncio as redis
from redis.asyncio import Redis
import mmh3  # MurmurHash3 for fast hashing

from ..core.config import settings
from ..models.ab_testing import Experiment, Variant, ExperimentAssignment
from ..cache.cache_keys import get_ab_testing_cache_key


logger = logging.getLogger(__name__)


# ============================================================================
# CACHE CONFIGURATION AND POLICIES
# ============================================================================

class CachePolicy(str, Enum):
    """Cache eviction and expiration policies"""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    TTL = "ttl"  # Time To Live
    WRITE_THROUGH = "write_through"
    WRITE_BEHIND = "write_behind"
    CACHE_ASIDE = "cache_aside"


class CacheTier(str, Enum):
    """Cache tiers for different data types"""
    HOT = "hot"      # Frequently accessed, small data (assignments)
    WARM = "warm"    # Moderately accessed (experiment configs)
    COLD = "cold"    # Infrequently accessed (historical data)


@dataclass
class CacheConfig:
    """Configuration for cache settings"""
    # Redis configuration
    max_connections: int = 100
    connection_timeout: int = 5
    socket_timeout: int = 5
    max_connections_per_pool: int = 20

    # Cache sizes and TTLs
    assignment_cache_size: int = 100000  # 100K assignments
    assignment_ttl: int = 3600  # 1 hour
    experiment_cache_size: int = 10000   # 10K experiments
    experiment_ttl: int = 1800   # 30 minutes
    metrics_cache_size: int = 50000     # 50K metric aggregates
    metrics_ttl: int = 300      # 5 minutes

    # Performance settings
    batch_size: int = 100
    pipeline_size: int = 50
    compression_threshold: int = 1024  # bytes
    enable_sharding: bool = True
    shard_count: int = 16

    # Monitoring
    enable_metrics: bool = True
    metrics_interval: int = 60  # seconds


# ============================================================================
# CACHE KEY GENERATION
# ============================================================================

class CacheKeyGenerator:
    """Generates consistent cache keys for different data types"""

    def __init__(self, prefix: str = "ab_testing"):
        self.prefix = prefix

    def assignment_key(self, user_id: Optional[str], session_id: Optional[str],
                      experiment_id: Optional[str] = None) -> str:
        """Generate cache key for user assignment"""
        if user_id:
            identifier = f"user:{user_id}"
        elif session_id:
            identifier = f"session:{session_id}"
        else:
            raise ValueError("Either user_id or session_id must be provided")

        key_parts = [self.prefix, "assignment", identifier]
        if experiment_id:
            key_parts.append(experiment_id)

        return ":".join(key_parts)

    def experiment_key(self, experiment_id: str) -> str:
        """Generate cache key for experiment data"""
        return f"{self.prefix}:experiment:{experiment_id}"

    def experiment_config_key(self, experiment_id: str) -> str:
        """Generate cache key for experiment configuration"""
        return f"{self.prefix}:config:experiment:{experiment_id}"

    def variant_config_key(self, variant_id: str) -> str:
        """Generate cache key for variant configuration"""
        return f"{self.prefix}:config:variant:{variant_id}"

    def metrics_aggregate_key(self, experiment_id: str, metric_type: str,
                            time_window: str = "hour") -> str:
        """Generate cache key for aggregated metrics"""
        return f"{self.prefix}:metrics:aggregate:{experiment_id}:{metric_type}:{time_window}"

    def user_segments_key(self, user_id: str) -> str:
        """Generate cache key for user segments"""
        return f"{self.prefix}:segments:user:{user_id}"

    def experiment_variants_key(self, experiment_id: str) -> str:
        """Generate cache key for experiment variants list"""
        return f"{self.prefix}:variants:experiment:{experiment_id}"

    def routing_table_key(self, organization_id: str) -> str:
        """Generate cache key for routing table"""
        return f"{self.prefix}:routing:org:{organization_id}"

    def stats_key(self, experiment_id: str, stat_type: str) -> str:
        """Generate cache key for experiment statistics"""
        return f"{self.prefix}:stats:{experiment_id}:{stat_type}"

    def hash_key(self, data: str) -> str:
        """Generate consistent hash for data"""
        return str(mmh3.hash128(data, signed=False))

    def shard_key(self, key: str, shard_count: int = 16) -> str:
        """Generate sharded key"""
        hash_value = mmh3.hash(key)
        shard_id = hash_value % shard_count
        return f"{key}:shard:{shard_id}"


# ============================================================================
# SERIALIZATION AND COMPRESSION
# ============================================================================

class CacheSerializer:
    """Handles secure serialization and compression of cache data using JSON only"""

    def __init__(self, compression_threshold: int = 1024):
        self.compression_threshold = compression_threshold

    def serialize(self, data: Any, compress: bool = True) -> bytes:
        """Serialize data for caching using JSON only (secure)"""
        try:
            # Convert to JSON for all data types
            serialized = json.dumps(data, default=str, ensure_ascii=False).encode('utf-8')

            # Compress if above threshold
            if compress and len(serialized) > self.compression_threshold:
                serialized = gzip.compress(serialized)
                # Add compression flag
                serialized = b'COMP:' + serialized

            return serialized

        except Exception as e:
            logger.error(f"Serialization failed: {e}")
            raise

    def deserialize(self, data: bytes) -> Any:
        """Deserialize cached data using JSON only (secure)"""
        try:
            # Check for compression flag
            if data.startswith(b'COMP:'):
                data = gzip.decompress(data[5:])  # Remove 'COMP:' prefix

            # Parse JSON
            return json.loads(data.decode('utf-8'))

        except Exception as e:
            logger.error(f"Deserialization failed: {e}")
            raise


# ============================================================================
# REDIS DATA STRUCTURES
# ============================================================================

class ABTestingCacheStructures:
    """Redis data structures optimized for A/B testing operations"""

    def __init__(self, redis_client: Redis, key_generator: CacheKeyGenerator,
                 serializer: CacheSerializer):
        self.redis = redis_client
        self.keys = key_generator
        self.serializer = serializer

    # ============================================================================
    # USER ASSIGNMENT CACHE (Hash + Sorted Sets)
    # ============================================================================

    async def cache_assignment(self, assignment_data: Dict[str, Any], ttl: int = 3600):
        """Cache user assignment with fast lookup"""
        key = self.keys.assignment_key(
            assignment_data.get("user_id"),
            assignment_data.get("session_id")
        )

        # Prepare assignment data for hash storage
        hash_data = {
            "experiment_id": assignment_data.get("experiment_id"),
            "variant_id": assignment_data.get("variant_id"),
            "assignment_type": assignment_data.get("assignment_type", "automatic"),
            "assigned_at": assignment_data.get("assigned_at", datetime.now(timezone.utc).isoformat()),
            "user_segment": json.dumps(assignment_data.get("user_segment", {}))
        }

        # Use pipeline for atomic operations
        async with self.redis.pipeline() as pipe:
            # Store assignment data
            await pipe.hset(key, mapping=hash_data)
            await pipe.expire(key, ttl)

            # Add to experiment's assignment index (for cleanup)
            experiment_id = assignment_data.get("experiment_id")
            if experiment_id:
                experiment_assignments_key = f"{self.keys.prefix}:assignments:experiment:{experiment_id}"
                user_id = assignment_data.get("user_id")
                session_id = assignment_data.get("session_id")

                if user_id:
                    await pipe.zadd(experiment_assignments_key, {f"user:{user_id}": datetime.now(timezone.utc).timestamp()})
                if session_id:
                    await pipe.zadd(experiment_assignments_key, {f"session:{session_id}": datetime.now(timezone.utc).timestamp()})
                await pipe.expire(experiment_assignments_key, ttl)

            await pipe.execute()

    async def get_assignment(self, user_id: Optional[str], session_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """Get cached assignment"""
        key = self.keys.assignment_key(user_id, session_id)
        assignment_data = await self.redis.hgetall(key)

        if not assignment_data:
            return None

        # Convert bytes to strings and parse JSON
        result = {}
        for field, value in assignment_data.items():
            field_str = field.decode('utf-8')
            value_str = value.decode('utf-8')

            if field_str == "user_segment":
                try:
                    result[field_str] = json.loads(value_str)
                except json.JSONDecodeError:
                    result[field_str] = {}
            else:
                result[field_str] = value_str

        return result

    async def invalidate_assignment(self, user_id: Optional[str], session_id: Optional[str]):
        """Invalidate cached assignment"""
        key = self.keys.assignment_key(user_id, session_id)
        await self.redis.delete(key)

    # ============================================================================
    # EXPERIMENT CONFIGURATION CACHE (String + Hash)
    # ============================================================================

    async def cache_experiment(self, experiment_data: Dict[str, Any], ttl: int = 1800):
        """Cache experiment configuration"""
        experiment_id = experiment_data["id"]

        # Cache main experiment data
        experiment_key = self.keys.experiment_key(experiment_id)
        config_key = self.keys.experiment_config_key(experiment_id)

        # Store experiment summary
        await self.redis.setex(experiment_key, ttl, self.serializer.serialize(experiment_data))

        # Store detailed configuration if present
        if "config" in experiment_data:
            await self.redis.setex(config_key, ttl, self.serializer.serialize(experiment_data["config"]))

        # Add to organization's active experiments
        if experiment_data.get("status") == "running":
            org_id = experiment_data.get("organization_id")
            if org_id:
                org_experiments_key = f"{self.keys.prefix}:active:org:{org_id}"
                await self.redis.sadd(org_experiments_key, experiment_id)
                await self.redis.expire(org_experiments_key, ttl)

    async def get_experiment(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        """Get cached experiment"""
        experiment_key = self.keys.experiment_key(experiment_id)
        cached_data = await self.redis.get(experiment_key)

        if not cached_data:
            return None

        return self.serializer.deserialize(cached_data)

    async def get_active_experiments(self, organization_id: str) -> Set[str]:
        """Get active experiment IDs for organization"""
        key = f"{self.keys.prefix}:active:org:{organization_id}"
        members = await self.redis.smembers(key)
        return {member.decode('utf-8') for member in members}

    # ============================================================================
    # METRICS AGGREGATION CACHE (Hash + Sorted Sets)
    # ============================================================================

    async def cache_metric_aggregate(self, experiment_id: str, metric_type: str,
                                   time_window: str, data: Dict[str, Any], ttl: int = 300):
        """Cache aggregated metrics"""
        key = self.keys.metrics_aggregate_key(experiment_id, metric_type, time_window)

        # Store aggregate data with timestamp
        aggregate_data = {
            "data": self.serializer.serialize(data),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "experiment_id": experiment_id,
            "metric_type": metric_type,
            "time_window": time_window
        }

        await self.redis.hset(key, mapping=aggregate_data)
        await self.redis.expire(key, ttl)

        # Add to time-series index for queries
        ts_key = f"{self.keys.prefix}:metrics:ts:{metric_type}:{time_window}"
        score = datetime.now(timezone.utc).timestamp()
        await self.redis.zadd(ts_key, {experiment_id: score})
        await self.redis.expire(ts_key, ttl * 2)  # Keep longer for queries

    async def get_metric_aggregate(self, experiment_id: str, metric_type: str,
                                 time_window: str) -> Optional[Dict[str, Any]]:
        """Get cached metric aggregate"""
        key = self.keys.metrics_aggregate_key(experiment_id, metric_type, time_window)
        cached_data = await self.redis.hgetall(key)

        if not cached_data:
            return None

        # Deserialize data
        result = {}
        for field, value in cached_data.items():
            field_str = field.decode('utf-8')
            value_str = value.decode('utf-8')

            if field_str == "data":
                result["data"] = self.serializer.deserialize(value_str.encode('utf-8'))
            else:
                result[field_str] = value_str

        return result

    # ============================================================================
    # USER SEGMENTS CACHE (Set)
    # ============================================================================

    async def cache_user_segments(self, user_id: str, segments: List[str], ttl: int = 1800):
        """Cache user segments"""
        key = self.keys.user_segments_key(user_id)
        await self.redis.delete(key)  # Clear existing segments
        if segments:
            await self.redis.sadd(key, *segments)
            await self.redis.expire(key, ttl)

    async def get_user_segments(self, user_id: str) -> Set[str]:
        """Get cached user segments"""
        key = self.keys.user_segments_key(user_id)
        segments = await self.redis.smembers(key)
        return {segment.decode('utf-8') for segment in segments}

    # ============================================================================
    # ROUTING TABLE CACHE (String + Bloom Filter)
    # ============================================================================

    async def cache_routing_table(self, organization_id: str, routing_data: Dict[str, Any], ttl: int = 600):
        """Cache routing table for fast lookup"""
        key = self.keys.routing_table_key(organization_id)

        # Store routing rules and experiment mappings
        async with self.redis.pipeline() as pipe:
            # Store main routing table
            await pipe.setex(key, ttl, self.serializer.serialize(routing_data))

            # Create bloom filter for quick experiment existence checks
            experiments = routing_data.get("experiments", [])
            if experiments:
                bloom_key = f"{key}:bloom"
                await self._create_bloom_filter(bloom_key, experiments, ttl)

            await pipe.execute()

    async def get_routing_table(self, organization_id: str) -> Optional[Dict[str, Any]]:
        """Get cached routing table"""
        key = self.keys.routing_table_key(organization_id)
        cached_data = await self.redis.get(key)

        if not cached_data:
            return None

        return self.serializer.deserialize(cached_data)

    async def experiment_exists_in_routing(self, organization_id: str, experiment_id: str) -> bool:
        """Quick check if experiment exists in routing table using bloom filter"""
        bloom_key = f"{self.keys.routing_table_key(organization_id)}:bloom"
        return await self._check_bloom_filter(bloom_key, experiment_id)

    # ============================================================================
    # PERFORMANCE STATISTICS CACHE (Sorted Sets)
    # ============================================================================

    async def update_experiment_stats(self, experiment_id: str, stat_type: str, value: float):
        """Update experiment performance statistics"""
        key = self.keys.stats_key(experiment_id, stat_type)
        timestamp = datetime.now(timezone.utc).timestamp()

        # Add to time series
        await self.redis.zadd(key, {str(timestamp): value})

        # Keep only last 1000 data points
        await self.redis.zremrangebyrank(key, 0, -1001)

        # Set expiration
        await self.redis.expire(key, 3600)

    async def get_experiment_stats(self, experiment_id: str, stat_type: str,
                                 time_range_minutes: int = 60) -> List[Tuple[float, float]]:
        """Get experiment statistics for time range"""
        key = self.keys.stats_key(experiment_id, stat_type)

        # Calculate time range
        now = datetime.now(timezone.utc).timestamp()
        start_time = now - (time_range_minutes * 60)

        # Get data points in range
        data_points = await self.redis.zrangebyscore(key, start_time, now, withscores=True)

        return [(float(score), float(member.decode('utf-8'))) for member, score in data_points]

    # ============================================================================
    # BLOOM FILTER IMPLEMENTATION
    # ============================================================================

    async def _create_bloom_filter(self, key: str, items: List[str], ttl: int):
        """Create bloom filter using Redis bit operations for better performance"""
        size = 10000  # Filter size (in bits)
        hash_count = 7  # Number of hash functions

        # Use Redis bit operations to create bloom filter
        async with self.redis.pipeline() as pipe:
            # Initialize bit array by setting key with proper bit length
            # Redis SETBIT creates keys automatically, no need to pre-initialize

            # Add items to bloom filter using bit operations
            for item in items:
                for i in range(hash_count):
                    # Calculate bit position using multiple hash functions
                    hash_val = mmh3.hash(item, i) % size
                    # Set the bit at calculated position
                    await pipe.setbit(key, hash_val, 1)

            # Set TTL for the bloom filter
            await pipe.expire(key, ttl)
            await pipe.execute()

    async def _check_bloom_filter(self, key: str, item: str) -> bool:
        """Check if item exists in bloom filter using Redis bit operations"""
        size = 10000  # Filter size must match creation size
        hash_count = 7  # Number of hash functions must match creation

        # Check if bloom filter exists
        if not await self.redis.exists(key):
            return False

        # Check bloom filter using bit operations
        async with self.redis.pipeline() as pipe:
            for i in range(hash_count):
                # Calculate same bit positions as in creation
                hash_val = mmh3.hash(item, i) % size
                # Get the bit at calculated position
                await pipe.getbit(key, hash_val)

            # Execute all bit checks at once
            bit_results = await pipe.execute()

        # If any bit is 0, item definitely doesn't exist
        # If all bits are 1, item might exist (false positive possible)
        return all(bit_results)  # Might be false positive


# ============================================================================
# CACHE MANAGER
# ============================================================================

class ABTestingCacheManager:
    """High-level cache management for A/B testing system"""

    def __init__(self, redis_client: Redis, config: CacheConfig = None):
        self.redis = redis_client
        self.config = config or CacheConfig()

        # Initialize components
        self.key_generator = CacheKeyGenerator()
        self.serializer = CacheSerializer(self.config.compression_threshold)
        self.structures = ABTestingCacheStructures(
            redis_client, self.key_generator, self.serializer
        )

        # Performance tracking
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0
        }

        # Background tasks
        self.cleanup_task = None
        self.metrics_task = None

    async def start(self):
        """Start cache manager and background tasks"""
        # Prevent duplicate background tasks
        if self.cleanup_task is None or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(self.periodic_cleanup())
            logger.debug("Started cleanup task")
        else:
            logger.warning("Cleanup task already running, skipping start")

        # Start metrics collection if enabled
        if self.config.enable_metrics:
            if self.metrics_task is None or self.metrics_task.done():
                self.metrics_task = asyncio.create_task(self.collect_metrics())
                logger.debug("Started metrics collection task")
            else:
                logger.warning("Metrics collection task already running, skipping start")

        logger.info("A/B Testing Cache Manager started")

    async def stop(self):
        """Stop cache manager and background tasks"""
        tasks_to_cancel = []

        # Cancel cleanup task if running
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            tasks_to_cancel.append(self.cleanup_task)
            logger.debug("Cancelling cleanup task")

        # Cancel metrics task if running
        if self.metrics_task and not self.metrics_task.done():
            self.metrics_task.cancel()
            tasks_to_cancel.append(self.metrics_task)
            logger.debug("Cancelling metrics collection task")

        # Wait for tasks to finish cancelling
        if tasks_to_cancel:
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
            logger.debug(f"Cancelled {len(tasks_to_cancel)} background tasks")

        # Clear task references
        self.cleanup_task = None
        self.metrics_task = None

        logger.info("A/B Testing Cache Manager stopped")

    # ============================================================================
    # HIGH-LEVEL CACHE OPERATIONS
    # ============================================================================

    async def get_or_assign_variant(
        self,
        user_id: Optional[str],
        session_id: Optional[str],
        organization_id: str,
        query_context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Get cached assignment or assign new variant"""
        try:
            # Check cache first
            cached_assignment = await self.structures.get_assignment(user_id, session_id)
            if cached_assignment:
                self.cache_stats["hits"] += 1

                # Verify assignment is still valid
                if await self._is_assignment_valid(cached_assignment):
                    return cached_assignment
                else:
                    # Invalid assignment, remove from cache
                    await self.invalidate_assignment(user_id, session_id)

            self.cache_stats["misses"] += 1

            # Assignment not in cache or invalid, return None
            # The calling service will handle assignment logic
            return None

        except Exception as e:
            logger.error(f"Cache get/assign failed: {e}")
            return None

    async def cache_assignment_result(
        self,
        assignment_data: Dict[str, Any],
        ttl: Optional[int] = None
    ):
        """Cache assignment result"""
        try:
            ttl = ttl or self.config.assignment_ttl
            await self.structures.cache_assignment(assignment_data, ttl)
            self.cache_stats["sets"] += 1

        except Exception as e:
            logger.error(f"Cache assignment failed: {e}")

    async def invalidate_assignment(self, user_id: Optional[str], session_id: Optional[str]):
        """Invalidate cached assignment"""
        try:
            await self.structures.invalidate_assignment(user_id, session_id)
            self.cache_stats["deletes"] += 1

        except Exception as e:
            logger.error(f"Cache invalidate failed: {e}")

    async def warm_up_cache(self, organization_id: str, experiment_ids: List[str]):
        """Warm up cache with frequently accessed data"""
        try:
            # Cache routing table
            routing_data = await self._build_routing_table(organization_id, experiment_ids)
            await self.structures.cache_routing_table(organization_id, routing_data)

            # Cache experiment configurations
            for experiment_id in experiment_ids:
                experiment = await self._load_experiment(experiment_id)
                if experiment:
                    await self.structures.cache_experiment(experiment)

            logger.info(f"Cache warm-up completed for {len(experiment_ids)} experiments")

        except Exception as e:
            logger.error(f"Cache warm-up failed: {e}")

    # ============================================================================
    # BACKGROUND TASKS
    # ============================================================================

    async def periodic_cleanup(self):
        """Periodic cleanup of expired cache entries"""
        while True:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                await self._cleanup_expired_entries()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cache cleanup error: {e}")

    async def collect_metrics(self):
        """Collect cache performance metrics"""
        while True:
            try:
                await asyncio.sleep(self.config.metrics_interval)
                await self._report_cache_metrics()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Metrics collection error: {e}")

    # ============================================================================
    # UTILITY METHODS
    # ============================================================================

    async def _is_assignment_valid(self, assignment: Dict[str, Any]) -> bool:
        """Check if cached assignment is still valid"""
        try:
            # Check if experiment is still active
            experiment_id = assignment.get("experiment_id")
            if not experiment_id:
                return False

            experiment = await self.structures.get_experiment(experiment_id)
            return experiment and experiment.get("status") == "running"

        except Exception:
            return False

    async def _build_routing_table(self, organization_id: str, experiment_ids: List[str]) -> Dict[str, Any]:
        """Build routing table for organization"""
        # This would be implemented based on your routing logic
        return {
            "organization_id": organization_id,
            "experiments": experiment_ids,
            "routing_rules": {},
            "last_updated": datetime.now(timezone.utc).isoformat()
        }

    async def _load_experiment(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        """Load experiment from database"""
        # This would query your database
        return None

    async def _cleanup_expired_entries(self):
        """Clean up expired cache entries"""
        # Redis handles TTL expiration automatically
        # This method can be used for additional cleanup logic
        pass

    async def _report_cache_metrics(self):
        """Report cache performance metrics"""
        total_requests = self.cache_stats["hits"] + self.cache_stats["misses"]
        hit_rate = (self.cache_stats["hits"] / total_requests * 100) if total_requests > 0 else 0

        logger.info(f"Cache Performance - Hit Rate: {hit_rate:.2f}%, "
                   f"Hits: {self.cache_stats['hits']}, "
                   f"Misses: {self.cache_stats['misses']}, "
                   f"Sets: {self.cache_stats['sets']}")

        # Reset stats
        self.cache_stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0}

    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache information and statistics"""
        return {
            "config": asdict(self.config),
            "stats": self.cache_stats.copy(),
            "status": "running" if self.cleanup_task else "stopped"
        }


# ============================================================================
# CACHE FACTORY
# ============================================================================

class ABTestingCacheFactory:
    """Factory for creating cache instances"""

    @staticmethod
    async def create_cache(config: CacheConfig = None) -> ABTestingCacheManager:
        """Create and initialize cache manager"""
        config = config or CacheConfig()

        # Parse Redis URL using proper URL parsing
        redis_url = settings.REDIS_URL
        if '://' in redis_url:
            # Use proper connection parameters from URL
            redis_client = Redis.from_url(
                redis_url,
                max_connections=config.max_connections,
                socket_timeout=config.socket_timeout,
                connection_timeout=config.connection_timeout,
                retry_on_timeout=True,
                decode_responses=False  # Keep bytes for consistency
            )
        else:
            # Fallback for simple host:port format with IPv4/IPv6 support
            host = "localhost"
            port = 6379
            
            try:
                # Handle bracketed IPv6 addresses like [::1]:6379
                if redis_url.startswith('['):
                    bracket_end = redis_url.find(']')
                    if bracket_end == -1:
                        raise ValueError(f"Malformed IPv6 address: {redis_url}")
                    host = redis_url[1:bracket_end]
                    # Check for port after bracket
                    if len(redis_url) > bracket_end + 1 and redis_url[bracket_end + 1] == ':':
                        port_str = redis_url[bracket_end + 2:]
                        try:
                            port = int(port_str)
                        except ValueError:
                            logger.warning(f"Invalid port '{port_str}', using default 6379")
                            port = 6379
                # Handle regular host:port or IPv6 without brackets
                elif ':' in redis_url:
                    # Use rpartition to split on the last ':' to handle IPv6 like ::1
                    host_part, sep, port_str = redis_url.rpartition(':')
                    if host_part:
                        # Try to parse port
                        try:
                            port = int(port_str)
                            host = host_part
                        except ValueError:
                            # Port parsing failed, treat whole string as host (likely IPv6)
                            logger.warning(f"Could not parse port from '{redis_url}', treating as host-only")
                            host = redis_url
                            port = 6379
                    else:
                        # No host part, just port (edge case)
                        host = "localhost"
                        try:
                            port = int(port_str)
                        except ValueError:
                            logger.warning(f"Invalid port '{port_str}', using default 6379")
                            port = 6379
                else:
                    host = redis_url or "localhost"
                    
            except Exception as e:
                logger.error(f"Error parsing Redis URL '{redis_url}': {e}. Using defaults localhost:6379")
                host = "localhost"
                port = 6379

            redis_client = Redis(
                host=host,
                port=port,
                max_connections=config.max_connections,
                socket_timeout=config.socket_timeout,
                connection_timeout=config.connection_timeout,
                retry_on_timeout=True,
                decode_responses=False
            )

        # Create cache manager
        cache_manager = ABTestingCacheManager(redis_client, config)
        await cache_manager.start()

        return cache_manager

    @staticmethod
    async def create_distributed_cache(redis_nodes: List[str], config: CacheConfig = None):
        """Create distributed cache across multiple Redis nodes"""
        # This would implement Redis Cluster or consistent hashing
        # For now, return single node cache
        return await ABTestingCacheFactory.create_cache(config)