"""
Performance optimization utilities and monitoring for the Multimodal RAG System.
"""

import asyncio
import gc
import logging
import multiprocessing
import threading
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache, wraps
from typing import Any, Callable, Dict, List, Optional, Union

import psutil

from .config import config
from .logging import get_logger, log_performance
from .metrics import increment_counter, record_histogram, track_performance

logger = get_logger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics container."""

    operation: str
    start_time: float
    end_time: float
    duration: float
    memory_before: float
    memory_after: float
    memory_peak: float
    cpu_percent: float
    success: bool
    metadata: Optional[Dict[str, Any]] = None


class PerformanceProfiler:
    """Advanced performance profiler with memory and CPU monitoring."""

    def __init__(self):
        self.process = psutil.Process()
        self.metrics_history: List[PerformanceMetrics] = []
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._process_executor = ProcessPoolExecutor(max_workers=2)

    def start_profiling(self, operation: str) -> Dict[str, Any]:
        """Start profiling an operation."""
        start_time = time.time()
        memory_before = self.process.memory_info().rss / 1024 / 1024  # MB
        cpu_before = self.process.cpu_percent()

        return {
            "operation": operation,
            "start_time": start_time,
            "memory_before": memory_before,
            "cpu_before": cpu_before,
            "memory_peak": memory_before,
        }

    def end_profiling(
        self,
        profile_data: Dict[str, Any],
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PerformanceMetrics:
        """End profiling and record metrics."""
        end_time = time.time()
        memory_after = self.process.memory_info().rss / 1024 / 1024  # MB
        cpu_after = self.process.cpu_percent()
        duration = end_time - profile_data["start_time"]

        metrics = PerformanceMetrics(
            operation=profile_data["operation"],
            start_time=profile_data["start_time"],
            end_time=end_time,
            duration=duration,
            memory_before=profile_data["memory_before"],
            memory_after=memory_after,
            memory_peak=profile_data["memory_peak"],
            cpu_percent=(profile_data["cpu_before"] + cpu_after) / 2,
            success=success,
            metadata=metadata,
        )

        with self._lock:
            self.metrics_history.append(metrics)
            # Keep only last 1000 metrics
            if len(self.metrics_history) > 1000:
                self.metrics_history = self.metrics_history[-1000:]

        # Record to metrics system
        self._record_metrics(metrics)

        return metrics

    def _record_metrics(self, metrics: PerformanceMetrics):
        """Record metrics to the monitoring system."""
        # Record duration
        track_performance(metrics.operation).record()

        # Record memory usage
        record_histogram(
            f"performance_memory_usage_{metrics.operation}",
            metrics.memory_after,
            {"operation": metrics.operation},
        )

        # Record CPU usage
        record_histogram(
            f"performance_cpu_usage_{metrics.operation}",
            metrics.cpu_percent,
            {"operation": metrics.operation},
        )

        # Log performance
        log_performance(
            metrics.operation,
            metrics.duration,
            {
                "memory_before_mb": metrics.memory_before,
                "memory_after_mb": metrics.memory_after,
                "memory_peak_mb": metrics.memory_peak,
                "cpu_percent": metrics.cpu_percent,
                "success": metrics.success,
            },
        )

    def get_performance_summary(
        self, operation: Optional[str] = None, time_window_minutes: int = 60
    ) -> Dict[str, Any]:
        """Get performance summary for operations."""
        cutoff_time = time.time() - (time_window_minutes * 60)

        filtered_metrics = [
            m
            for m in self.metrics_history
            if m.end_time >= cutoff_time
            and (operation is None or m.operation == operation)
        ]

        if not filtered_metrics:
            return {}

        durations = [m.duration for m in filtered_metrics]
        memory_usage = [m.memory_after for m in filtered_metrics]
        cpu_usage = [m.cpu_percent for m in filtered_metrics]
        success_rate = sum(1 for m in filtered_metrics if m.success) / len(
            filtered_metrics
        )

        return {
            "operation": operation or "all",
            "total_operations": len(filtered_metrics),
            "success_rate": success_rate,
            "duration": {
                "min": min(durations),
                "max": max(durations),
                "avg": sum(durations) / len(durations),
                "p95": self._percentile(durations, 95),
                "p99": self._percentile(durations, 99),
            },
            "memory_usage_mb": {
                "min": min(memory_usage),
                "max": max(memory_usage),
                "avg": sum(memory_usage) / len(memory_usage),
                "p95": self._percentile(memory_usage, 95),
            },
            "cpu_usage_percent": {
                "min": min(cpu_usage),
                "max": max(cpu_usage),
                "avg": sum(cpu_usage) / len(cpu_usage),
                "p95": self._percentile(cpu_usage, 95),
            },
        }

    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of data."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]


# Global profiler instance
_profiler = None


def get_profiler() -> PerformanceProfiler:
    """Get the global performance profiler instance."""
    global _profiler
    if _profiler is None:
        _profiler = PerformanceProfiler()
    return _profiler


def profile_performance(operation: Optional[str] = None):
    """Decorator for profiling function performance."""

    def decorator(func: Callable) -> Callable:
        op_name = operation or f"{func.__module__}.{func.__name__}"

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            profiler = get_profiler()
            profile_data = profiler.start_profiling(op_name)

            try:
                result = func(*args, **kwargs)
                profiler.end_profiling(profile_data, success=True)
                return result
            except Exception as e:
                profiler.end_profiling(
                    profile_data, success=False, metadata={"error": str(e)}
                )
                raise

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            profiler = get_profiler()
            profile_data = profiler.start_profiling(op_name)

            try:
                result = await func(*args, **kwargs)
                profiler.end_profiling(profile_data, success=True)
                return result
            except Exception as e:
                profiler.end_profiling(
                    profile_data, success=False, metadata={"error": str(e)}
                )
                raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


@contextmanager
def profile_context(operation: str):
    """Context manager for profiling code blocks."""
    profiler = get_profiler()
    profile_data = profiler.start_profiling(operation)

    try:
        yield profile_data
        profiler.end_profiling(profile_data, success=True)
    except Exception as e:
        profiler.end_profiling(profile_data, success=False, metadata={"error": str(e)})
        raise


class ConnectionPoolManager:
    """Advanced connection pool manager for database and external services."""

    def __init__(self):
        self.pools: Dict[str, Any] = {}
        self.pool_configs: Dict[str, Dict[str, Any]] = {}
        self._setup_default_pools()

    def _setup_default_pools(self):
        """Setup default connection pool configurations."""
        # PostgreSQL pool
        self.pool_configs["postgresql"] = {
            "min_size": 5,
            "max_size": 20,
            "max_queries": 50000,
            "max_inactive_connection_lifetime": 300,
            "timeout": 30,
            "command_timeout": 30,
        }

        # Redis pool
        self.pool_configs["redis"] = {
            "max_connections": 20,
            "retry_on_timeout": True,
            "socket_keepalive": True,
            "socket_keepalive_options": {},
            "health_check_interval": 30,
        }

        # HTTP connection pools
        self.pool_configs["http"] = {
            "pool_size": 10,
            "maxsize": 20,
            "retries": 3,
            "backoff_factor": 0.3,
            "timeout": 30,
        }

    async def get_connection(self, pool_name: str, **kwargs):
        """Get a connection from the specified pool."""
        if pool_name not in self.pools:
            await self._create_pool(pool_name, **kwargs)

        return await self.pools[pool_name].acquire()

    async def release_connection(self, pool_name: str, connection):
        """Release a connection back to the pool."""
        if pool_name in self.pools:
            await self.pools[pool_name].release(connection)

    async def _create_pool(self, pool_name: str, **kwargs):
        """Create a new connection pool."""
        # This would be implemented based on the specific database/client library
        # Example implementation for asyncpg (PostgreSQL)
        if pool_name == "postgresql":
            import asyncpg

            config = self.pool_configs[pool_name].copy()
            config.update(kwargs)
            # self.pools[pool_name] = await asyncpg.create_pool(**config)

        # Example for Redis
        elif pool_name == "redis":
            import aioredis

            config = self.pool_configs[pool_name].copy()
            config.update(kwargs)
            # self.pools[pool_name] = aioredis.ConnectionPool.from_url(**config)

    def get_pool_stats(self, pool_name: str) -> Dict[str, Any]:
        """Get statistics for a connection pool."""
        if pool_name not in self.pools:
            return {}

        pool = self.pools[pool_name]
        return {
            "size": getattr(pool, "size", 0),
            "idle": getattr(pool, "idle", 0),
            "active": getattr(pool, "active", 0),
            "total_requests": getattr(pool, "total_requests", 0),
            "total_errors": getattr(pool, "total_errors", 0),
        }


class CacheManager:
    """Advanced multi-level caching system."""

    def __init__(self):
        self.memory_cache: Dict[str, Any] = {}
        self.cache_stats: Dict[str, Dict[str, int]] = {}
        self._lock = threading.RLock()
        self._setup_cache_config()

    def _setup_cache_config(self):
        """Setup cache configuration."""
        self.cache_config = {
            "memory": {"max_size": 1000, "ttl_seconds": 3600, "cleanup_interval": 300},
            "redis": {"ttl_seconds": 7200, "max_memory": "256mb"},
            "cdn": {"ttl_seconds": 86400, "cache_control": "public, max-age=86400"},
        }

    def get(self, key: str, cache_level: str = "memory") -> Optional[Any]:
        """Get value from cache."""
        if cache_level == "memory":
            with self._lock:
                if key in self.memory_cache:
                    item = self.memory_cache[key]
                    if self._is_valid(item):
                        self._increment_stats(key, "hits")
                        return item["value"]
                    else:
                        del self.memory_cache[key]
                        self._increment_stats(key, "misses")
                        return None
                else:
                    self._increment_stats(key, "misses")
                    return None

        # Implement other cache levels as needed
        return None

    def set(
        self,
        key: str,
        value: Any,
        cache_level: str = "memory",
        ttl: Optional[int] = None,
    ):
        """Set value in cache."""
        if cache_level == "memory":
            with self._lock:
                # Check cache size limit
                if len(self.memory_cache) >= self.cache_config["memory"]["max_size"]:
                    self._evict_lru()

                ttl_seconds = ttl or self.cache_config["memory"]["ttl_seconds"]
                expire_time = time.time() + ttl_seconds

                self.memory_cache[key] = {
                    "value": value,
                    "expire_time": expire_time,
                    "access_time": time.time(),
                    "access_count": 1,
                }
                self._increment_stats(key, "sets")

    def _is_valid(self, item: Dict[str, Any]) -> bool:
        """Check if cache item is still valid."""
        return item["expire_time"] > time.time()

    def _evict_lru(self):
        """Evict least recently used items from cache."""
        if not self.memory_cache:
            return

        # Sort by access time and remove oldest 10%
        sorted_items = sorted(
            self.memory_cache.items(), key=lambda x: x[1]["access_time"]
        )

        evict_count = max(1, len(sorted_items) // 10)
        for key, _ in sorted_items[:evict_count]:
            del self.memory_cache[key]

    def _increment_stats(self, key: str, operation: str):
        """Increment cache statistics."""
        if key not in self.cache_stats:
            self.cache_stats[key] = {"hits": 0, "misses": 0, "sets": 0, "evictions": 0}

        self.cache_stats[key][operation] += 1

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        total_hits = sum(stats["hits"] for stats in self.cache_stats.values())
        total_misses = sum(stats["misses"] for stats in self.cache_stats.values())
        total_requests = total_hits + total_misses

        return {
            "memory_cache": {
                "size": len(self.memory_cache),
                "max_size": self.cache_config["memory"]["max_size"],
                "usage_percent": (
                    len(self.memory_cache) / self.cache_config["memory"]["max_size"]
                )
                * 100,
            },
            "operations": {
                "total_hits": total_hits,
                "total_misses": total_misses,
                "total_requests": total_requests,
                "hit_rate": (total_hits / total_requests * 100)
                if total_requests > 0
                else 0,
            },
            "top_keys": dict(
                sorted(
                    self.cache_stats.items(),
                    key=lambda x: sum(x[1].values()),
                    reverse=True,
                )[:10]
            ),
        }

    def clear_cache(self, pattern: Optional[str] = None):
        """Clear cache entries matching pattern."""
        with self._lock:
            if pattern:
                import fnmatch

                keys_to_remove = [
                    key
                    for key in self.memory_cache.keys()
                    if fnmatch.fnmatch(key, pattern)
                ]
                for key in keys_to_remove:
                    del self.memory_cache[key]
            else:
                self.memory_cache.clear()


# Performance optimization decorators and utilities


def smart_cache(
    cache_key_func: Optional[Callable] = None,
    ttl_seconds: int = 3600,
    cache_level: str = "memory",
):
    """Smart caching decorator with automatic cache key generation."""

    def decorator(func: Callable) -> Callable:
        cache_manager = CacheManager()

        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if cache_key_func:
                cache_key = cache_key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__module__}.{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"

            # Try to get from cache
            cached_result = cache_manager.get(cache_key, cache_level)
            if cached_result is not None:
                return cached_result

            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_manager.set(cache_key, result, cache_level, ttl_seconds)

            return result

        return wrapper

    return decorator


def batch_processor(batch_size: int = 100, timeout_seconds: int = 30):
    """Decorator for batch processing of operations."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(items: List[Any]) -> List[Any]:
            if not items:
                return []

            if len(items) <= batch_size:
                return func(items)

            # Process in batches
            results = []
            for i in range(0, len(items), batch_size):
                batch = items[i : i + batch_size]
                batch_results = func(batch)
                results.extend(batch_results)

            return results

        return wrapper

    return decorator


async def parallel_executor(
    tasks: List[Callable],
    max_workers: Optional[int] = None,
    executor_type: str = "thread",
) -> List[Any]:
    """Execute tasks in parallel."""
    if max_workers is None:
        max_workers = min(32, (os.cpu_count() or 1) + 4)

    if executor_type == "thread":
        executor = ThreadPoolExecutor(max_workers=max_workers)
    else:
        executor = ProcessPoolExecutor(max_workers=max_workers)

    try:
        if asyncio.iscoroutinefunction(tasks[0]):
            # For async functions, use asyncio.gather
            results = await asyncio.gather(*[task() for task in tasks])
        else:
            # For sync functions, use executor
            loop = asyncio.get_event_loop()
            results = await asyncio.gather(
                *[loop.run_in_executor(executor, task) for task in tasks]
            )
    finally:
        executor.shutdown(wait=True)

    return results


class MemoryOptimizer:
    """Memory optimization utilities."""

    @staticmethod
    def force_garbage_collection():
        """Force garbage collection and return memory stats."""
        import gc

        gc.collect()

        process = psutil.Process()
        memory_info = process.memory_info()

        return {
            "rss_mb": memory_info.rss / 1024 / 1024,
            "vms_mb": memory_info.vms / 1024 / 1024,
            "percent": process.memory_percent(),
            "gc_stats": gc.get_stats() if hasattr(gc, "get_stats") else None,
        }

    @staticmethod
    @lru_cache(maxsize=1000)
    def cached_computation(*args, **kwargs):
        """Example of LRU cache for expensive computations."""
        # This would contain the actual computation logic
        return hash(str(args) + str(sorted(kwargs.items())))

    @staticmethod
    def optimize_data_structures(data: Any) -> Any:
        """Optimize data structures for memory usage."""
        # This would implement specific optimizations based on data type
        return data


# Global instances
connection_manager = ConnectionPoolManager()
cache_manager = CacheManager()
memory_optimizer = MemoryOptimizer()
