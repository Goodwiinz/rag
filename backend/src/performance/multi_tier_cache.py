"""
Enterprise-grade multi-tier caching system with Redis, CDN, and application-level caching
Implements intelligent cache warming, invalidation, and performance monitoring
Security-focused implementation using only JSON serialization
"""

import asyncio
import gzip
import hashlib
import json
import logging
import os
import tempfile
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import aioredis
import numpy as np

logger = logging.getLogger(__name__)


class CacheLevel(Enum):
    """Cache hierarchy levels"""

    L1_MEMORY = "l1_memory"  # In-memory cache (fastest)
    L2_REDIS = "l2_redis"  # Redis cache (fast)
    L3_APPLICATION = "l3_app"  # Application-level cache (medium)
    L4_CDN = "l4_cdn"  # CDN cache (slow but distributed)


class CacheStrategy(Enum):
    """Cache invalidation strategies"""

    TTL_BASED = "ttl_based"
    LRU = "lru"
    WRITE_THROUGH = "write_through"
    WRITE_BEHIND = "write_behind"
    REFRESH_AHEAD = "refresh_ahead"


@dataclass
class CacheEntry:
    """Cache entry with metadata"""

    key: str
    value: Any
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    ttl: Optional[int] = None
    size_bytes: int = 0
    cache_level: CacheLevel = CacheLevel.L1_MEMORY
    compression_ratio: float = 1.0
    tags: Set[str] = field(default_factory=set)

    def is_expired(self) -> bool:
        """Check if cache entry is expired"""
        if self.ttl is None:
            return False
        return (datetime.utcnow() - self.created_at).total_seconds() > self.ttl

    def update_access(self):
        """Update access metadata"""
        self.last_accessed = datetime.utcnow()
        self.access_count += 1

    def get_priority_score(self) -> float:
        """Calculate priority score for eviction"""
        # Higher score = higher priority to keep
        age_hours = (datetime.utcnow() - self.created_at).total_seconds() / 3600
        access_frequency = self.access_count / max(1, age_hours)
        return access_frequency * (
            1 / max(1, self.size_bytes / 1024)
        )  # Favor small, frequently accessed items


@dataclass
class CacheConfig:
    """Configuration for multi-tier cache"""

    l1_max_size: int = 1000  # Max entries in memory cache
    l1_max_memory_mb: int = 100  # Max memory in MB
    l2_redis_url: str = "redis://localhost:6379"
    l2_default_ttl: int = 300  # 5 minutes
    l3_enable_file_cache: bool = True
    # Use system tempdir for secure cache location (avoids hardcoded /tmp)
    l3_cache_dir: str = field(default_factory=lambda: os.path.join(tempfile.gettempdir(), "rag_cache"))
    l4_cdn_url: Optional[str] = None
    compression_threshold: int = 1024  # Compress entries larger than 1KB
    enable_metrics: bool = True
    metrics_retention_hours: int = 24
    background_cleanup_interval: int = 300  # 5 minutes
    cache_warming_enabled: bool = True
    refresh_ahead_threshold: float = 0.8  # Refresh when 80% of TTL elapsed
    max_serialization_depth: int = 10  # Prevent deep recursion in serialization


class SafeJSONSerializer:
    """Safe JSON serializer with security constraints"""

    @staticmethod
    def is_safe_type(obj: Any) -> bool:
        """Check if object is safe for JSON serialization"""
        safe_types = (str, int, float, bool, type(None))
        if isinstance(obj, safe_types):
            return True
        if isinstance(obj, (list, tuple)):
            return all(SafeJSONSerializer.is_safe_type(item) for item in obj)
        if isinstance(obj, dict):
            return all(
                isinstance(k, str) and SafeJSONSerializer.is_safe_type(v)
                for k, v in obj.items()
            )
        return False

    @staticmethod
    def serialize(obj: Any, max_depth: int = 10, current_depth: int = 0) -> str:
        """Safely serialize object to JSON"""
        if current_depth > max_depth:
            raise ValueError("Serialization depth exceeded maximum limit")

        if SafeJSONSerializer.is_safe_type(obj):
            return json.dumps(obj, default=str, ensure_ascii=False)
        else:
            # Convert complex objects to safe dictionaries
            if hasattr(obj, "__dict__"):
                safe_dict = {}
                for key, value in obj.__dict__.items():
                    if not key.startswith("_"):  # Skip private attributes
                        try:
                            if SafeJSONSerializer.is_safe_type(value):
                                safe_dict[key] = value
                            else:
                                # Convert to string for complex types
                                safe_dict[key] = str(value)
                        except Exception:
                            safe_dict[key] = "Unable to serialize"
                return json.dumps(safe_dict, default=str, ensure_ascii=False)
            else:
                return json.dumps(str(obj), ensure_ascii=False)

    @staticmethod
    def deserialize(data: str) -> Any:
        """Safely deserialize JSON data"""
        return json.loads(data)


class L1MemoryCache:
    """L1 in-memory cache with LRU eviction and safe serialization"""

    def __init__(self, config: CacheConfig):
        self.config = config
        self.cache: Dict[str, CacheEntry] = {}
        self.access_order: List[str] = []
        self.current_memory_mb = 0
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "sets": 0,
            "compression_saves": 0,
            "serialization_errors": 0,
        }

    def _estimate_size(self, value: Any) -> int:
        """Estimate memory size of a value"""
        try:
            if isinstance(value, str):
                return len(value.encode("utf-8"))
            elif isinstance(value, (dict, list)):
                return len(json.dumps(value, default=str).encode("utf-8"))
            else:
                return len(str(value).encode("utf-8"))
        except Exception:
            return 1024  # Default estimate

    def _should_compress(self, value: Any, size: int) -> bool:
        """Check if value should be compressed"""
        return size > self.config.compression_threshold

    def _compress_value(self, value: Any) -> Tuple[Any, float]:
        """Compress JSON value and return compressed value with ratio"""
        try:
            serialized = SafeJSONSerializer.serialize(value).encode("utf-8")
            compressed = gzip.compress(serialized)
            ratio = len(compressed) / len(serialized)

            if ratio < 0.8:  # Only use compression if it saves >20%
                return compressed, ratio
            else:
                return value, 1.0
        except Exception as e:
            logger.error(f"Compression error: {e}")
            return value, 1.0

    def _decompress_value(self, value: Any) -> Any:
        """Decompress value if needed"""
        try:
            if isinstance(value, bytes):
                try:
                    decompressed = gzip.decompress(value)
                    return SafeJSONSerializer.deserialize(decompressed.decode("utf-8"))
                except:
                    # Not compressed, try direct deserialization
                    try:
                        return SafeJSONSerializer.deserialize(value.decode("utf-8"))
                    except:
                        return str(value)
            else:
                return value
        except Exception as e:
            logger.error(f"Decompression error: {e}")
            return None

    async def get(self, key: str) -> Optional[Any]:
        """Get value from L1 cache"""
        if key not in self.cache:
            self.stats["misses"] += 1
            return None

        entry = self.cache[key]

        # Check expiration
        if entry.is_expired():
            await self.delete(key)
            self.stats["misses"] += 1
            return None

        # Update access information
        entry.update_access()
        self._update_access_order(key)

        self.stats["hits"] += 1
        return self._decompress_value(entry.value)

    async def set(
        self, key: str, value: Any, ttl: Optional[int] = None, tags: Set[str] = None
    ) -> bool:
        """Set value in L1 cache with safe serialization"""
        try:
            # Validate object is serializable
            if not SafeJSONSerializer.is_safe_type(value):
                # Try to convert complex objects
                if hasattr(value, "__dict__"):
                    # Convert object to dictionary
                    safe_value = {}
                    for attr in dir(value):
                        if not attr.startswith("_"):
                            try:
                                attr_value = getattr(value, attr)
                                if SafeJSONSerializer.is_safe_type(attr_value):
                                    safe_value[attr] = attr_value
                                else:
                                    safe_value[attr] = str(attr_value)
                            except Exception:
                                continue
                    value = safe_value
                else:
                    # Convert to string as last resort
                    value = str(value)

            # Estimate size
            size = self._estimate_size(value)

            # Check if we need compression
            original_value = value
            compression_ratio = 1.0
            if self._should_compress(value, size):
                value, compression_ratio = self._compress_value(value)
                if compression_ratio < 1.0:
                    self.stats["compression_saves"] += 1

            # Create cache entry
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=datetime.utcnow(),
                last_accessed=datetime.utcnow(),
                ttl=ttl,
                size_bytes=size,
                compression_ratio=compression_ratio,
                tags=tags or set(),
            )

            # Check memory constraints
            await self._ensure_memory_limit(size)

            # Store entry
            self.cache[key] = entry
            self._update_access_order(key)
            self.current_memory_mb += size / (1024 * 1024)
            self.stats["sets"] += 1

            return True

        except Exception as e:
            logger.error(f"Error setting L1 cache entry {key}: {e}")
            self.stats["serialization_errors"] += 1
            return False

    async def delete(self, key: str) -> bool:
        """Delete entry from L1 cache"""
        if key in self.cache:
            entry = self.cache[key]
            self.current_memory_mb -= entry.size_bytes / (1024 * 1024)
            del self.cache[key]
            if key in self.access_order:
                self.access_order.remove(key)
            return True
        return False

    async def _ensure_memory_limit(self, new_entry_size: int):
        """Ensure cache stays within memory limits"""
        while (
            len(self.cache) >= self.config.l1_max_size
            or self.current_memory_mb + new_entry_size / (1024 * 1024)
            > self.config.l1_max_memory_mb
        ):
            if not self.cache:
                break

            # Find entry with lowest priority score
            lowest_key = min(
                self.cache.keys(), key=lambda k: self.cache[k].get_priority_score()
            )
            await self.delete(lowest_key)
            self.stats["evictions"] += 1

    def _update_access_order(self, key: str):
        """Update LRU access order"""
        if key in self.access_order:
            self.access_order.remove(key)
        self.access_order.append(key)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = (
            (self.stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        )

        return {
            **self.stats,
            "hit_rate_percent": hit_rate,
            "total_entries": len(self.cache),
            "memory_usage_mb": self.current_memory_mb,
            "avg_access_count": np.mean([e.access_count for e in self.cache.values()])
            if self.cache
            else 0,
            "compression_savings": sum(
                1 - e.compression_ratio
                for e in self.cache.values()
                if e.compression_ratio < 1
            ),
        }


class L2RedisCache:
    """L2 Redis cache with clustering support and safe serialization"""

    def __init__(self, config: CacheConfig):
        self.config = config
        self.redis_client: Optional[aioredis.Redis] = None
        self.stats = {
            "hits": 0,
            "misses": 0,
            "errors": 0,
            "sets": 0,
            "connection_failures": 0,
        }

    async def initialize(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = aioredis.from_url(
                self.config.l2_redis_url,
                encoding="utf-8",
                decode_responses=False,  # Keep binary for compression
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
                max_connections=20,
            )

            # Test connection
            await self.redis_client.ping()
            logger.info("L2 Redis cache initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Redis cache: {e}")
            self.redis_client = None

    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis cache"""
        if not self.redis_client:
            return None

        try:
            data = await self.redis_client.get(key)
            if data is None:
                self.stats["misses"] += 1
                return None

            # Deserialize with compression support
            value = self._deserialize(data)
            if value is not None:
                self.stats["hits"] += 1
                return value
            else:
                self.stats["misses"] += 1
                return None

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Redis get error for key {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in Redis cache with safe serialization"""
        if not self.redis_client:
            return False

        try:
            # Validate object is serializable
            if not SafeJSONSerializer.is_safe_type(value):
                # Convert to safe format
                if hasattr(value, "__dict__"):
                    safe_value = {}
                    for attr in dir(value):
                        if not attr.startswith("_"):
                            try:
                                attr_value = getattr(value, attr)
                                if SafeJSONSerializer.is_safe_type(attr_value):
                                    safe_value[attr] = attr_value
                                else:
                                    safe_value[attr] = str(attr_value)
                            except Exception:
                                continue
                    value = safe_value
                else:
                    value = str(value)

            # Serialize with compression
            data = self._serialize(value)
            cache_ttl = ttl or self.config.l2_default_ttl

            await self.redis_client.setex(key, cache_ttl, data)
            self.stats["sets"] += 1
            return True

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Redis set error for key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete value from Redis cache"""
        if not self.redis_client:
            return False

        try:
            await self.redis_client.delete(key)
            return True
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Redis delete error for key {key}: {e}")
            return False

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate keys matching pattern"""
        if not self.redis_client:
            return 0

        try:
            keys = await self.redis_client.keys(pattern)
            if keys:
                deleted = await self.redis_client.delete(*keys)
                return deleted
            return 0
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Redis pattern delete error: {e}")
            return 0

    def _serialize(self, value: Any) -> bytes:
        """Serialize value with compression using safe JSON"""
        try:
            serialized = SafeJSONSerializer.serialize(value).encode("utf-8")
        except Exception as e:
            logger.error(f"Serialization error: {e}")
            serialized = json.dumps(
                {"error": "Serialization failed", "original": str(value)}
            ).encode("utf-8")

        # Compress if large
        if len(serialized) > self.config.compression_threshold:
            compressed = gzip.compress(serialized)
            # Return with compression marker
            return (
                b"COMP:" + compressed
                if len(compressed) < len(serialized)
                else serialized
            )

        return serialized

    def _deserialize(self, data: bytes) -> Any:
        """Deserialize value with decompression using safe JSON"""
        try:
            # Check for compression marker
            if data.startswith(b"COMP:"):
                data = gzip.decompress(data[5:])  # Remove 'COMP:' marker

            # Try safe JSON deserialization
            try:
                return SafeJSONSerializer.deserialize(data.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                logger.error(f"JSON deserialization error: {e}")
                return None

        except Exception as e:
            logger.error(f"Deserialization error: {e}")
            return None

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = (
            (self.stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        )

        return {
            **self.stats,
            "hit_rate_percent": hit_rate,
            "connected": self.redis_client is not None,
        }


class L3ApplicationCache:
    """L3 Application-level cache with persistence and safe serialization"""

    def __init__(self, config: CacheConfig):
        self.config = config
        self.cache: Dict[str, CacheEntry] = {}
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "disk_reads": 0,
            "disk_writes": 0,
            "serialization_errors": 0,
        }

    async def initialize(self):
        """Initialize application cache"""
        if self.config.l3_enable_file_cache:
            # Load existing cache from disk
            await self._load_from_disk()

    async def get(self, key: str) -> Optional[Any]:
        """Get value from application cache"""
        if key not in self.cache:
            self.stats["misses"] += 1
            return None

        entry = self.cache[key]
        if entry.is_expired():
            await self.delete(key)
            self.stats["misses"] += 1
            return None

        entry.update_access()
        self.stats["hits"] += 1
        return entry.value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in application cache with safe serialization"""
        try:
            # Validate object is serializable
            if not SafeJSONSerializer.is_safe_type(value):
                # Convert to safe format
                if hasattr(value, "__dict__"):
                    safe_value = {}
                    for attr in dir(value):
                        if not attr.startswith("_"):
                            try:
                                attr_value = getattr(value, attr)
                                if SafeJSONSerializer.is_safe_type(attr_value):
                                    safe_value[attr] = attr_value
                                else:
                                    safe_value[attr] = str(attr_value)
                            except Exception:
                                continue
                    value = safe_value
                else:
                    value = str(value)

            entry = CacheEntry(
                key=key,
                value=value,
                created_at=datetime.utcnow(),
                last_accessed=datetime.utcnow(),
                ttl=ttl,
                cache_level=CacheLevel.L3_APPLICATION,
            )

            self.cache[key] = entry
            self.stats["sets"] += 1

            # Persist to disk if enabled
            if self.config.l3_enable_file_cache:
                await self._persist_to_disk()

            return True

        except Exception as e:
            logger.error(f"Error setting L3 cache entry {key}: {e}")
            self.stats["serialization_errors"] += 1
            return False

    async def delete(self, key: str) -> bool:
        """Delete entry from application cache"""
        if key in self.cache:
            del self.cache[key]
            return True
        return False

    async def _persist_to_disk(self):
        """Persist cache to disk using safe JSON"""
        # Implementation would save to file system using SafeJSONSerializer
        pass

    async def _load_from_disk(self):
        """Load cache from disk using safe JSON"""
        # Implementation would load from file system using SafeJSONSerializer
        pass

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = (
            (self.stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        )

        return {
            **self.stats,
            "hit_rate_percent": hit_rate,
            "total_entries": len(self.cache),
        }


class MultiTierCacheManager:
    """Enterprise-grade multi-tier cache manager with security-first approach"""

    def __init__(self, config: CacheConfig):
        self.config = config

        # Initialize cache tiers
        self.l1_cache = L1MemoryCache(config)
        self.l2_cache = L2RedisCache(config)
        self.l3_cache = L3ApplicationCache(config)

        # Cache warming and refresh tasks
        self.warming_tasks: Dict[str, asyncio.Task] = {}
        self.background_cleanup_task: Optional[asyncio.Task] = None

        # Performance metrics
        self.global_stats = {
            "total_requests": 0,
            "cache_warms": 0,
            "refreshes": 0,
            "multi_tier_hits": 0,  # Hits that required tier fallback
            "security_violations": 0,  # Count of unsafe object attempts
            "start_time": datetime.utcnow(),
        }

        # Tag-based invalidation
        self.tag_index: Dict[str, Set[str]] = defaultdict(set)

    async def initialize(self):
        """Initialize all cache tiers"""
        await self.l2_cache.initialize()
        await self.l3_cache.initialize()

        # Start background tasks
        self.background_cleanup_task = asyncio.create_task(self._background_cleanup())

        logger.info("Multi-tier cache manager initialized with security constraints")

    async def get(self, key: str, check_all_tiers: bool = True) -> Optional[Any]:
        """Get value from cache with tier fallback and security validation"""
        start_time = time.time()
        self.global_stats["total_requests"] += 1

        try:
            # Try L1 (memory) cache first
            value = await self.l1_cache.get(key)
            if value is not None:
                return value

            if not check_all_tiers:
                return None

            # Try L2 (Redis) cache
            value = await self.l2_cache.get(key)
            if value is not None:
                # Validate before promoting to L1
                if SafeJSONSerializer.is_safe_type(value):
                    await self.l1_cache.set(key, value)
                    self.global_stats["multi_tier_hits"] += 1
                else:
                    self.global_stats["security_violations"] += 1
                return value

            # Try L3 (application) cache
            value = await self.l3_cache.get(key)
            if value is not None:
                # Validate before promoting to higher tiers
                if SafeJSONSerializer.is_safe_type(value):
                    await self.l2_cache.set(key, value)
                    await self.l1_cache.set(key, value)
                    self.global_stats["multi_tier_hits"] += 1
                else:
                    self.global_stats["security_violations"] += 1
                return value

            return None

        except Exception as e:
            logger.error(f"Error getting cache key {key}: {e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Set[str] = None,
        strategy: CacheStrategy = CacheStrategy.WRITE_THROUGH,
    ) -> bool:
        """Set value in cache with security validation and configurable strategy"""
        try:
            # Security validation - ensure object is safe for caching
            if not SafeJSONSerializer.is_safe_type(value):
                self.global_stats["security_violations"] += 1
                logger.warning(
                    f"Unsafe object type detected for key {key}: {type(value)}"
                )

                # Try to convert to safe format
                if hasattr(value, "__dict__"):
                    safe_value = {}
                    for attr in dir(value):
                        if not attr.startswith("_"):
                            try:
                                attr_value = getattr(value, attr)
                                if SafeJSONSerializer.is_safe_type(attr_value):
                                    safe_value[attr] = attr_value
                                else:
                                    safe_value[attr] = str(attr_value)
                            except Exception:
                                continue
                    value = safe_value
                else:
                    value = str(value)

            success = True

            # Update tag index
            if tags:
                for tag in tags:
                    self.tag_index[tag].add(key)

            if strategy == CacheStrategy.WRITE_THROUGH:
                # Write to all tiers
                success &= await self.l1_cache.set(key, value, ttl, tags)
                success &= await self.l2_cache.set(key, value, ttl)
                success &= await self.l3_cache.set(key, value, ttl)

            elif strategy == CacheStrategy.WRITE_BEHIND:
                # Write to L1 immediately, others asynchronously
                success &= await self.l1_cache.set(key, value, ttl, tags)
                asyncio.create_task(self._background_write(key, value, ttl, tags))

            return success

        except Exception as e:
            logger.error(f"Error setting cache key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete from all cache tiers"""
        try:
            success = True
            success &= await self.l1_cache.delete(key)
            success &= await self.l2_cache.delete(key)
            success &= await self.l3_cache.delete(key)

            # Remove from tag index
            for tag, keys in self.tag_index.items():
                keys.discard(key)

            return success

        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {e}")
            return False

    async def invalidate_by_tag(self, tag: str) -> int:
        """Invalidate all cache entries with given tag"""
        keys_to_invalidate = self.tag_index.get(tag, set())
        invalidated_count = 0

        for key in keys_to_invalidate:
            if await self.delete(key):
                invalidated_count += 1

        # Clear tag index
        self.tag_index[tag].clear()

        logger.info(f"Invalidated {invalidated_count} entries for tag: {tag}")
        return invalidated_count

    async def warm_cache(self, keys: List[str], loader: Callable[[str], Any]) -> int:
        """Warm cache with pre-loaded data and security validation"""
        warmed_count = 0

        for key in keys:
            if key not in self.l1_cache.cache:
                try:
                    # Load data asynchronously
                    task = asyncio.create_task(self._load_and_cache(key, loader))
                    self.warming_tasks[key] = task
                    warmed_count += 1
                except Exception as e:
                    logger.error(f"Error warming cache key {key}: {e}")

        self.global_stats["cache_warms"] += warmed_count
        return warmed_count

    async def _load_and_cache(self, key: str, loader: Callable[[str], Any]):
        """Load data and cache it with security validation"""
        try:
            data = await loader(key)
            if data is not None:
                # Validate data before caching
                if SafeJSONSerializer.is_safe_type(data):
                    await self.set(key, data, strategy=CacheStrategy.WRITE_BEHIND)
                else:
                    logger.warning(
                        f"Unsafe data type for cache warming key {key}: {type(data)}"
                    )
                    self.global_stats["security_violations"] += 1
        except Exception as e:
            logger.error(f"Error loading data for key {key}: {e}")
        finally:
            self.warming_tasks.pop(key, None)

    async def _background_write(
        self, key: str, value: Any, ttl: Optional[int], tags: Set[str]
    ):
        """Background write for write-behind strategy"""
        try:
            await self.l2_cache.set(key, value, ttl)
            await self.l3_cache.set(key, value, ttl)
        except Exception as e:
            logger.error(f"Background write failed for key {key}: {e}")

    async def _background_cleanup(self):
        """Background cleanup task"""
        while True:
            try:
                await asyncio.sleep(self.config.background_cleanup_interval)

                # Cleanup expired entries
                await self._cleanup_expired_entries()

                # Cleanup completed warming tasks
                completed_tasks = [k for k, v in self.warming_tasks.items() if v.done()]
                for key in completed_tasks:
                    self.warming_tasks.pop(key, None)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Background cleanup error: {e}")
                await asyncio.sleep(60)

    async def _cleanup_expired_entries(self):
        """Clean up expired cache entries"""
        # L1 cleanup
        expired_keys = [k for k, v in self.l1_cache.cache.items() if v.is_expired()]
        for key in expired_keys:
            await self.l1_cache.delete(key)

        # L3 cleanup
        expired_keys = [k for k, v in self.l3_cache.cache.items() if v.is_expired()]
        for key in expired_keys:
            await self.l3_cache.delete(key)

    async def refresh_ahead(self, key_pattern: str, loader: Callable[[str], Any]):
        """Refresh cache entries before they expire"""
        try:
            # Implementation would scan for entries approaching expiration
            # and refresh them asynchronously
            pass
        except Exception as e:
            logger.error(f"Refresh ahead error: {e}")

    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics"""
        uptime = (datetime.utcnow() - self.global_stats["start_time"]).total_seconds()
        requests_per_second = self.global_stats["total_requests"] / max(1, uptime)

        # Calculate overall hit rate
        total_hits = sum(
            [
                self.l1_cache.stats["hits"],
                self.l2_cache.stats["hits"],
                self.l3_cache.stats["hits"],
            ]
        )
        total_requests = sum(
            [
                self.l1_cache.stats["hits"] + self.l1_cache.stats["misses"],
                self.l2_cache.stats["hits"] + self.l2_cache.stats["misses"],
                self.l3_cache.stats["hits"] + self.l3_cache.stats["misses"],
            ]
        )
        overall_hit_rate = (
            (total_hits / total_requests * 100) if total_requests > 0 else 0
        )

        return {
            "global_stats": {
                **self.global_stats,
                "uptime_seconds": uptime,
                "requests_per_second": requests_per_second,
                "overall_hit_rate_percent": overall_hit_rate,
                "security_violation_rate": (
                    self.global_stats["security_violations"]
                    / max(1, self.global_stats["total_requests"])
                    * 100
                ),
            },
            "l1_stats": self.l1_cache.get_stats(),
            "l2_stats": self.l2_cache.get_stats(),
            "l3_stats": self.l3_cache.get_stats(),
            "tag_count": len(self.tag_index),
            "warming_tasks": len(self.warming_tasks),
        }

    async def shutdown(self):
        """Graceful shutdown"""
        if self.background_cleanup_task:
            self.background_cleanup_task.cancel()

        # Cancel warming tasks
        for task in self.warming_tasks.values():
            task.cancel()

        # Close Redis connection
        if self.l2_cache.redis_client:
            await self.l2_cache.redis_client.close()


# Decorator for easy cache usage with security validation
def cached_multi_tier(
    cache_manager: MultiTierCacheManager,
    key_prefix: str = "",
    ttl: int = 300,
    tags: Set[str] = None,
    strategy: CacheStrategy = CacheStrategy.WRITE_THROUGH,
):
    """Decorator for automatic multi-tier caching with security validation"""

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            key_parts = (
                [key_prefix, str(func.__name__)]
                + [str(arg) for arg in args]
                + [f"{k}:{v}" for k, v in sorted(kwargs.items())]
            )
            # Use MD5 for non-security cache key generation (usedforsecurity=False)
            cache_key = hashlib.md5(":".join(key_parts).encode(), usedforsecurity=False).hexdigest()

            # Try to get from cache
            cached_result = await cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Execute function
            try:
                result = await func(*args, **kwargs)

                # Validate result before caching
                if SafeJSONSerializer.is_safe_type(result):
                    await cache_manager.set(cache_key, result, ttl, tags, strategy)
                else:
                    logger.warning(
                        f"Function result not cacheable due to security: {func.__name__}"
                    )
                    cache_manager.global_stats["security_violations"] += 1

                return result

            except Exception as e:
                logger.error(f"Function execution error in cached wrapper: {e}")
                raise

        return wrapper

    return decorator


# Global cache manager instance
_multi_tier_cache_manager = None


def get_multi_tier_cache_manager(config: CacheConfig = None) -> MultiTierCacheManager:
    """Get or create the global multi-tier cache manager"""
    global _multi_tier_cache_manager
    if _multi_tier_cache_manager is None:
        _multi_tier_cache_manager = MultiTierCacheManager(config or CacheConfig())
    return _multi_tier_cache_manager
