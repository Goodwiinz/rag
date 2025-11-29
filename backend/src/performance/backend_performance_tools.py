"""
Backend Performance Tools for the Multimodal Enterprise RAG System

This module provides comprehensive backend performance monitoring, profiling,
caching, and optimization tools for FastAPI applications and microservices.
"""

import asyncio
import time
import logging
import psutil
import threading
import json
import cProfile
import pstats
import io
import tracemalloc
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from functools import wraps, lru_cache
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict, deque
import memory_profiler
import linecache
import inspect
import uvloop
from contextlib import asynccontextmanager, contextmanager
import redis
from fastapi import Request, Response, HTTPException
from fastapi.middleware.base import BaseHTTPMiddleware
import numpy as np
from cachetools import TTLCache, LRUCache
import aioredis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """Backend performance metrics"""
    timestamp: datetime
    endpoint: str
    method: str
    status_code: int
    duration: float
    memory_usage: int
    cpu_usage: float
    database_time: float
    cache_hits: int
    cache_misses: int
    request_size: int
    response_size: int
    user_id: Optional[str]
    session_id: Optional[str]
    error_message: Optional[str]

@dataclass
class FunctionProfile:
    """Function profiling information"""
    function_name: str
    module: str
    line_number: int
    call_count: int
    total_time: float
    avg_time: float
    max_time: float
    min_time: float
    memory_usage: int
    errors: int
    last_executed: datetime

@dataclass
class CacheMetrics:
    """Cache performance metrics"""
    cache_name: str
    cache_type: str
    hits: int
    misses: int
    hit_ratio: float
    evictions: int
    size: int
    max_size: int
    memory_usage: int

class PerformanceProfiler:
    """Advanced performance profiling system"""

    def __init__(self):
        self.profiles: Dict[str, FunctionProfile] = {}
        self.memory_snapshots: deque = deque(maxlen=100)
        self.call_stack: deque = deque(maxlen=1000)
        self.profiler_enabled = False
        self.memory_profiler_enabled = False
        self.function_times: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.error_counts: Dict[str, int] = defaultdict(int)

    def enable_profiling(self):
        """Enable performance profiling"""
        self.profiler_enabled = True
        tracemalloc.start()
        logger.info("Performance profiling enabled")

    def disable_profiling(self):
        """Disable performance profiling"""
        self.profiler_enabled = False
        if tracemalloc.is_tracing():
            tracemalloc.stop()
        logger.info("Performance profiling disabled")

    @contextmanager
    def profile_function(self, function_name: str):
        """Profile a specific function"""
        if not self.profiler_enabled:
            yield
            return

        start_time = time.perf_counter()
        start_memory = psutil.Process().memory_info().rss if self.memory_profiler_enabled else 0
        error_occurred = False

        try:
            self.call_stack.append(function_name)
            yield
        except Exception as e:
            error_occurred = True
            self.error_counts[function_name] += 1
            raise
        finally:
            end_time = time.perf_counter()
            end_memory = psutil.Process().memory_info().rss if self.memory_profiler_enabled else 0
            duration = end_time - start_time
            memory_delta = end_memory - start_memory

            self.call_stack.pop()

            # Update function profile
            if function_name not in self.profiles:
                # Get function metadata
                frame = inspect.currentframe().f_back
                module = inspect.getmodule(frame).__name__ if frame and inspect.getmodule(frame) else "unknown"
                line_number = frame.f_lineno if frame else 0

                self.profiles[function_name] = FunctionProfile(
                    function_name=function_name,
                    module=module,
                    line_number=line_number,
                    call_count=0,
                    total_time=0.0,
                    avg_time=0.0,
                    max_time=0.0,
                    min_time=float('inf'),
                    memory_usage=0,
                    errors=0,
                    last_executed=datetime.now()
                )

            profile = self.profiles[function_name]
            profile.call_count += 1
            profile.total_time += duration
            profile.avg_time = profile.total_time / profile.call_count
            profile.max_time = max(profile.max_time, duration)
            profile.min_time = min(profile.min_time, duration)
            profile.memory_usage += memory_delta
            profile.last_executed = datetime.now()

            if error_occurred:
                profile.errors += 1

            # Store timing data
            self.function_times[function_name].append(duration)

    def get_top_functions(self, limit: int = 10, sort_by: str = "total_time") -> List[FunctionProfile]:
        """Get top functions by performance metric"""
        if sort_by == "total_time":
            return sorted(self.profiles.values(), key=lambda p: p.total_time, reverse=True)[:limit]
        elif sort_by == "avg_time":
            return sorted(self.profiles.values(), key=lambda p: p.avg_time, reverse=True)[:limit]
        elif sort_by == "call_count":
            return sorted(self.profiles.values(), key=lambda p: p.call_count, reverse=True)[:limit]
        elif sort_by == "errors":
            return sorted(self.profiles.values(), key=lambda p: p.errors, reverse=True)[:limit]
        else:
            return list(self.profiles.values())[:limit]

    def get_function_profile(self, function_name: str) -> Optional[FunctionProfile]:
        """Get profile for a specific function"""
        return self.profiles.get(function_name)

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get overall performance summary"""
        if not self.profiles:
            return {"error": "No profiling data available"}

        total_functions = len(self.profiles)
        total_calls = sum(p.call_count for p in self.profiles.values())
        total_time = sum(p.total_time for p in self.profiles.values())
        total_errors = sum(p.errors for p in self.profiles.values())

        return {
            "summary": {
                "total_functions": total_functions,
                "total_calls": total_calls,
                "total_time": total_time,
                "total_errors": total_errors,
                "avg_function_time": total_time / max(1, total_calls),
                "error_rate": total_errors / max(1, total_calls)
            },
            "top_functions": {
                "by_total_time": self.get_top_functions(5, "total_time"),
                "by_avg_time": self.get_top_functions(5, "avg_time"),
                "by_call_count": self.get_top_functions(5, "call_count"),
                "by_errors": self.get_top_functions(5, "errors")
            },
            "memory": {
                "current_usage": psutil.Process().memory_info().rss,
                "peak_usage": max((s.memory for s in self.memory_snapshots), default=0),
                "snapshots_count": len(self.memory_snapshots)
            }
        }

    def reset_profiles(self):
        """Reset all profiling data"""
        self.profiles.clear()
        self.function_times.clear()
        self.error_counts.clear()
        self.memory_snapshots.clear()
        logger.info("Profiling data reset")

class AdvancedCacheManager:
    """Advanced caching system with multiple cache types and strategies"""

    def __init__(self):
        self.caches: Dict[str, Any] = {}
        self.cache_metrics: Dict[str, CacheMetrics] = {}
        self.redis_client: Optional[redis.Redis] = None
        self.aioredis_client: Optional[aioredis.Redis] = None

    def create_cache(
        self,
        name: str,
        cache_type: str = "lru",
        max_size: int = 1000,
        ttl: Optional[int] = None
    ) -> Any:
        """Create a cache instance"""

        if cache_type == "lru":
            cache = LRUCache(maxsize=max_size)
        elif cache_type == "ttl":
            cache = TTLCache(maxsize=max_size, ttl=ttl)
        elif cache_type == "memory":
            cache = {}
        else:
            raise ValueError(f"Unsupported cache type: {cache_type}")

        self.caches[name] = cache
        self.cache_metrics[name] = CacheMetrics(
            cache_name=name,
            cache_type=cache_type,
            hits=0,
            misses=0,
            hit_ratio=0.0,
            evictions=0,
            size=0,
            max_size=max_size,
            memory_usage=0
        )

        logger.info(f"Created {cache_type} cache '{name}' with max_size={max_size}")
        return cache

    async def setup_redis_cache(self, redis_url: str):
        """Setup Redis cache"""
        try:
            self.redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
            self.aioredis_client = await aioredis.from_url(redis_url, decode_responses=True)

            # Test connection
            await self.aioredis_client.ping()

            self.create_cache("redis", "redis", max_size=10000)
            logger.info("Redis cache connected successfully")

        except Exception as e:
            logger.error(f"Failed to setup Redis cache: {e}")
            raise

    def get_cache_decorator(self, cache_name: str, key_func: Optional[Callable] = None):
        """Get cache decorator function"""

        def decorator(func: Callable):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                if cache_name not in self.caches:
                    # Auto-create cache if it doesn't exist
                    self.create_cache(cache_name)

                cache = self.caches[cache_name]
                metrics = self.cache_metrics[cache_name]

                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"

                # Try to get from cache
                try:
                    if cache_name == "redis" and self.redis_client:
                        cached_result = self.redis_client.get(cache_key)
                        if cached_result:
                            metrics.hits += 1
                            metrics.hit_ratio = metrics.hits / (metrics.hits + metrics.misses)
                            return json.loads(cached_result)
                    elif hasattr(cache, 'get'):
                        cached_result = cache.get(cache_key)
                        if cached_result is not None:
                            metrics.hits += 1
                            metrics.hit_ratio = metrics.hits / (metrics.hits + metrics.misses)
                            return cached_result
                except Exception as e:
                    logger.warning(f"Cache get error: {e}")

                # Cache miss - execute function
                metrics.misses += 1
                metrics.hit_ratio = metrics.hits / (metrics.hits + metrics.misses)

                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                # Store in cache
                try:
                    if cache_name == "redis" and self.redis_client:
                        self.redis_client.setex(
                            cache_key,
                            3600,  # 1 hour TTL
                            json.dumps(result, default=str)
                        )
                    elif hasattr(cache, '__setitem__'):
                        cache[cache_key] = result

                    metrics.size = len(cache) if hasattr(cache, '__len__') else 0

                except Exception as e:
                    logger.warning(f"Cache set error: {e}")

                return result

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                if cache_name not in self.caches:
                    self.create_cache(cache_name)

                cache = self.caches[cache_name]
                metrics = self.cache_metrics[cache_name]

                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"

                # Try to get from cache
                try:
                    if hasattr(cache, 'get'):
                        cached_result = cache.get(cache_key)
                        if cached_result is not None:
                            metrics.hits += 1
                            metrics.hit_ratio = metrics.hits / (metrics.hits + metrics.misses)
                            return cached_result
                except Exception as e:
                    logger.warning(f"Cache get error: {e}")

                # Cache miss - execute function
                metrics.misses += 1
                metrics.hit_ratio = metrics.hits / (metrics.hits + metrics.misses)

                result = func(*args, **kwargs)

                # Store in cache
                try:
                    if hasattr(cache, '__setitem__'):
                        cache[cache_key] = result

                    metrics.size = len(cache) if hasattr(cache, '__len__') else 0

                except Exception as e:
                    logger.warning(f"Cache set error: {e}")

                return result

            return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

        return decorator

    def get_cache_stats(self) -> Dict[str, CacheMetrics]:
        """Get statistics for all caches"""
        return self.cache_metrics.copy()

    def clear_cache(self, cache_name: str):
        """Clear a specific cache"""
        if cache_name in self.caches:
            cache = self.caches[cache_name]
            if hasattr(cache, 'clear'):
                cache.clear()
            elif isinstance(cache, dict):
                cache.clear()

            # Reset metrics
            metrics = self.cache_metrics[cache_name]
            metrics.hits = 0
            metrics.misses = 0
            metrics.hit_ratio = 0.0
            metrics.size = 0
            metrics.evictions = 0

            logger.info(f"Cache '{cache_name}' cleared")

    async def preload_cache(self, cache_name: str, data_loader: Callable, keys: List[Any]):
        """Preload cache with data"""
        if cache_name not in self.caches:
            self.create_cache(cache_name)

        cache = self.caches[cache_name]

        for key in keys:
            try:
                if asyncio.iscoroutinefunction(data_loader):
                    data = await data_loader(key)
                else:
                    data = data_loader(key)

                if cache_name == "redis" and self.redis_client:
                    self.redis_client.setex(str(key), 3600, json.dumps(data, default=str))
                elif hasattr(cache, '__setitem__'):
                    cache[key] = data

            except Exception as e:
                logger.error(f"Error preloading cache key {key}: {e}")

class PerformanceMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for performance monitoring"""

    def __init__(self, app, profiler: PerformanceProfiler):
        super().__init__(app)
        self.profiler = profiler
        self.metrics_history: deque = deque(maxlen=10000)
        self.request_times: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and collect performance metrics"""

        start_time = time.perf_counter()
        start_memory = psutil.Process().memory_info().rss
        start_cpu = psutil.cpu_percent()

        # Extract request information
        method = request.method
        url_path = request.url.path
        query_string = str(request.url.query) if request.url.query else ""
        endpoint = f"{method} {url_path}"

        request_size = len(await request.body()) if hasattr(request, 'body') else 0

        response = None
        status_code = 500
        response_size = 0
        error_message = None

        try:
            response = await call_next(request)
            status_code = response.status_code

            # Get response size if available
            if hasattr(response, 'body'):
                response_body = b""
                async for chunk in response.body_iterator:
                    response_body += chunk
                response_size = len(response_body)
                # Recreate response with body
                response = Response(
                    content=response_body,
                    status_code=status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type
                )

        except HTTPException as e:
            status_code = e.status_code
            error_message = str(e.detail)
            response = JSONResponse(
                status_code=status_code,
                content={"error": error_message}
            )
        except Exception as e:
            status_code = 500
            error_message = str(e)
            response = JSONResponse(
                status_code=status_code,
                content={"error": "Internal server error"}
            )

        end_time = time.perf_counter()
        end_memory = psutil.Process().memory_info().rss
        end_cpu = psutil.cpu_percent()

        duration = (end_time - start_time) * 1000  # Convert to ms
        memory_delta = end_memory - start_memory
        cpu_delta = end_cpu - start_cpu

        # Get user and session info if available
        user_id = getattr(request.state, 'user_id', None)
        session_id = getattr(request.state, 'session_id', None)

        # Create metrics
        metrics = PerformanceMetrics(
            timestamp=datetime.now(),
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            duration=duration,
            memory_usage=memory_delta,
            cpu_usage=cpu_delta,
            database_time=0.0,  # Would need database middleware integration
            cache_hits=0,      # Would need cache middleware integration
            cache_misses=0,    # Would need cache middleware integration
            request_size=request_size,
            response_size=response_size,
            user_id=user_id,
            session_id=session_id,
            error_message=error_message
        )

        # Store metrics
        self.metrics_history.append(metrics)
        self.request_times[endpoint].append(duration)

        # Log slow requests
        if duration > 1000:  # Slow requests > 1 second
            logger.warning(
                f"Slow request detected: {endpoint} took {duration:.2f}ms "
                f"(memory: {memory_delta:,} bytes, CPU: {cpu_delta:.1f}%)"
            )

        # Log errors
        if status_code >= 400:
            logger.error(
                f"Request failed: {endpoint} returned {status_code} - {error_message}"
            )

        return response

    def get_request_metrics(
        self,
        endpoint: Optional[str] = None,
        minutes: int = 60
    ) -> Dict[str, Any]:
        """Get request performance metrics"""

        cutoff_time = datetime.now() - timedelta(minutes=minutes)

        # Filter metrics
        if endpoint:
            filtered_metrics = [
                m for m in self.metrics_history
                if m.timestamp > cutoff_time and m.endpoint == endpoint
            ]
        else:
            filtered_metrics = [
                m for m in self.metrics_history
                if m.timestamp > cutoff_time
            ]

        if not filtered_metrics:
            return {"error": "No metrics available for the specified period"}

        # Calculate statistics
        durations = [m.duration for m in filtered_metrics]
        memory_usage = [m.memory_usage for m in filtered_metrics]
        cpu_usage = [m.cpu_usage for m in filtered_metrics]

        status_codes = defaultdict(int)
        for m in filtered_metrics:
            status_codes[m.status_code] += 1

        return {
            "period": {
                "minutes": minutes,
                "start": cutoff_time,
                "end": datetime.now()
            },
            "endpoint": endpoint or "all",
            "total_requests": len(filtered_metrics),
            "duration": {
                "avg": np.mean(durations),
                "min": np.min(durations),
                "max": np.max(durations),
                "p50": np.percentile(durations, 50),
                "p95": np.percentile(durations, 95),
                "p99": np.percentile(durations, 99)
            },
            "memory_usage": {
                "avg": np.mean(memory_usage),
                "min": np.min(memory_usage),
                "max": np.max(memory_usage),
                "total": np.sum(memory_usage)
            },
            "cpu_usage": {
                "avg": np.mean(cpu_usage),
                "min": np.min(cpu_usage),
                "max": np.max(cpu_usage)
            },
            "status_codes": dict(status_codes),
            "error_rate": sum(status_codes.get(code, 0) for code in [400, 401, 403, 404, 500]) / len(filtered_metrics)
        }

class AsyncTaskQueue:
    """High-performance async task queue with priorities and batching"""

    def __init__(self, max_workers: int = 10, batch_size: int = 100):
        self.queue = asyncio.PriorityQueue()
        self.workers = []
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.running = False
        self.processed_tasks = 0
        self.failed_tasks = 0
        self.task_history: deque = deque(maxlen=1000)

    async def start(self):
        """Start the task queue workers"""
        self.running = True
        self.workers = [
            asyncio.create_task(self._worker(f"worker-{i}"))
            for i in range(self.max_workers)
        ]
        logger.info(f"Task queue started with {self.max_workers} workers")

    async def stop(self):
        """Stop the task queue workers"""
        self.running = False

        # Cancel all workers
        for worker in self.workers:
            worker.cancel()

        # Wait for workers to finish
        await asyncio.gather(*self.workers, return_exceptions=True)

        logger.info("Task queue stopped")

    async def add_task(
        self,
        task_func: Callable,
        priority: int = 0,
        *args,
        **kwargs
    ) -> asyncio.Future:
        """Add a task to the queue"""

        future = asyncio.Future()
        task = (priority, time.time(), task_func, args, kwargs, future)

        await self.queue.put(task)
        return future

    async def add_batch_tasks(
        self,
        tasks: List[Tuple[Callable, tuple, dict]],
        priority: int = 0
    ) -> List[asyncio.Future]:
        """Add multiple tasks to the queue"""

        futures = []
        for task_func, args, kwargs in tasks:
            future = await self.add_task(task_func, priority, *args, **kwargs)
            futures.append(future)

        return futures

    async def _worker(self, worker_name: str):
        """Worker process that handles tasks from the queue"""

        logger.info(f"Worker {worker_name} started")

        while self.running:
            try:
                # Get task from queue
                priority, timestamp, task_func, args, kwargs, future = await asyncio.wait_for(
                    self.queue.get(),
                    timeout=1.0
                )

                start_time = time.perf_counter()

                try:
                    # Execute the task
                    if asyncio.iscoroutinefunction(task_func):
                        result = await task_func(*args, **kwargs)
                    else:
                        result = task_func(*args, **kwargs)

                    # Set successful result
                    if not future.done():
                        future.set_result(result)

                    self.processed_tasks += 1

                    # Record task execution
                    duration = time.perf_counter() - start_time
                    self.task_history.append({
                        "worker": worker_name,
                        "priority": priority,
                        "duration": duration,
                        "success": True,
                        "timestamp": datetime.now()
                    })

                except Exception as e:
                    # Set error result
                    if not future.done():
                        future.set_exception(e)

                    self.failed_tasks += 1

                    # Record task failure
                    duration = time.perf_counter() - start_time
                    self.task_history.append({
                        "worker": worker_name,
                        "priority": priority,
                        "duration": duration,
                        "success": False,
                        "error": str(e),
                        "timestamp": datetime.now()
                    })

                self.queue.task_done()

            except asyncio.TimeoutError:
                # No task available, continue
                continue
            except Exception as e:
                logger.error(f"Worker {worker_name} error: {e}")
                continue

        logger.info(f"Worker {worker_name} stopped")

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get task queue statistics"""

        successful_tasks = [t for t in self.task_history if t["success"]]
        failed_tasks = [t for t in self.task_history if not t["success"]]

        durations = [t["duration"] for t in self.task_history]

        return {
            "queue_size": self.queue.qsize(),
            "workers": {
                "total": len(self.workers),
                "active": sum(1 for w in self.workers if not w.done()),
                "max_workers": self.max_workers
            },
            "tasks": {
                "processed": self.processed_tasks,
                "failed": self.failed_tasks,
                "success_rate": self.processed_tasks / max(1, self.processed_tasks + self.failed_tasks)
            },
            "performance": {
                "avg_duration": np.mean(durations) if durations else 0,
                "max_duration": np.max(durations) if durations else 0,
                "min_duration": np.min(durations) if durations else 0,
                "throughput": len(self.task_history) / max(1, (datetime.now() - self.task_history[0]["timestamp"]).total_seconds()) if self.task_history else 0
            }
        }

class MemoryOptimizer:
    """Memory optimization and monitoring tools"""

    def __init__(self):
        self.memory_snapshots: deque = deque(maxlen=100)
        self.memory_pools: Dict[str, int] = {}
        self.gc_stats = {}

    def start_monitoring(self, interval: int = 10):
        """Start memory monitoring"""

        def monitor_memory():
            import gc

            while True:
                try:
                    # Get current memory usage
                    process = psutil.Process()
                    memory_info = process.memory_info()

                    snapshot = {
                        "timestamp": datetime.now(),
                        "rss": memory_info.rss,
                        "vms": memory_info.vms,
                        "percent": process.memory_percent(),
                        "available": psutil.virtual_memory().available,
                        "gc_counts": gc.get_count(),
                        "gc_stats": gc.get_stats()
                    }

                    self.memory_snapshots.append(snapshot)

                    # Trigger garbage collection if memory usage is high
                    if memory_info.rss > 1024 * 1024 * 1024:  # > 1GB
                        collected = gc.collect()
                        logger.info(f"Garbage collection triggered, collected {collected} objects")

                except Exception as e:
                    logger.error(f"Memory monitoring error: {e}")

                time.sleep(interval)

        # Start monitoring in background thread
        monitor_thread = threading.Thread(target=monitor_memory, daemon=True)
        monitor_thread.start()

        logger.info(f"Memory monitoring started with {interval}s interval")

    def analyze_memory_usage(self) -> Dict[str, Any]:
        """Analyze memory usage patterns"""

        if not self.memory_snapshots:
            return {"error": "No memory data available"}

        rss_values = [s["rss"] for s in self.memory_snapshots]
        percent_values = [s["percent"] for s in self.memory_snapshots]

        return {
            "current": self.memory_snapshots[-1],
            "statistics": {
                "rss": {
                    "avg": np.mean(rss_values),
                    "min": np.min(rss_values),
                    "max": np.max(rss_values),
                    "growth": rss_values[-1] - rss_values[0] if len(rss_values) > 1 else 0
                },
                "percent": {
                    "avg": np.mean(percent_values),
                    "min": np.min(percent_values),
                    "max": np.max(percent_values)
                }
            },
            "trends": {
                "direction": "increasing" if rss_values[-1] > rss_values[0] else "decreasing",
                "growth_rate": (rss_values[-1] - rss_values[0]) / max(1, rss_values[0]) if len(rss_values) > 1 else 0
            },
            "recommendations": self._generate_memory_recommendations()
        }

    def _generate_memory_recommendations(self) -> List[str]:
        """Generate memory optimization recommendations"""

        if not self.memory_snapshots:
            return []

        current_snapshot = self.memory_snapshots[-1]
        recommendations = []

        # Check for high memory usage
        if current_snapshot["percent"] > 80:
            recommendations.append("Memory usage is high (>80%). Consider optimizing memory usage or scaling up.")

        # Check for memory leaks
        if len(self.memory_snapshots) > 10:
            recent_values = [s["rss"] for s in list(self.memory_snapshots)[-10:]]
            if recent_values[-1] > recent_values[0] * 1.1:  # 10% growth
                recommendations.append("Potential memory leak detected. Memory usage has been consistently increasing.")

        # Check for garbage collection
        gc_counts = current_snapshot["gc_counts"]
        if sum(gc_counts) > 100000:
            recommendations.append("High object creation rate detected. Consider object pooling or recycling.")

        return recommendations

    def optimize_memory(self):
        """Perform memory optimization"""
        import gc

        # Force garbage collection
        collected = gc.collect()

        # Clear memory pools if they exist
        for pool_name, pool_size in list(self.memory_pools.items()):
            if pool_size > 1000:
                logger.info(f"Clearing memory pool: {pool_name}")
                del self.memory_pools[pool_name]

        logger.info(f"Memory optimization completed, collected {collected} objects")

        return {
            "objects_collected": collected,
            "pools_cleared": len([name for name, size in self.memory_pools.items() if size > 1000])
        }

# Global instances
performance_profiler = PerformanceProfiler()
cache_manager = AdvancedCacheManager()
task_queue = AsyncTaskQueue()
memory_optimizer = MemoryOptimizer()

# Decorator for function profiling
def profile_function(func_name: Optional[str] = None):
    """Decorator to profile function performance"""
    def decorator(func: Callable):
        name = func_name or f"{func.__module__}.{func.__name__}"

        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                with performance_profiler.profile_function(name):
                    return await func(*args, **kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                with performance_profiler.profile_function(name):
                    return func(*args, **kwargs)
            return sync_wrapper

    return decorator

# Decorator for caching
def cached(cache_name: str, ttl: Optional[int] = None, key_func: Optional[Callable] = None):
    """Decorator for caching function results"""
    return cache_manager.get_cache_decorator(cache_name, key_func)

# Performance monitoring utilities
async def get_system_performance() -> Dict[str, Any]:
    """Get comprehensive system performance metrics"""

    # CPU metrics
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count()
    cpu_freq = psutil.cpu_freq()

    # Memory metrics
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()

    # Disk metrics
    disk = psutil.disk_usage('/')
    disk_io = psutil.disk_io_counters()

    # Network metrics
    network = psutil.net_io_counters()
    network_connections = len(psutil.net_connections())

    # Process metrics
    process = psutil.Process()
    process_memory = process.memory_info()
    process_cpu = process.cpu_percent()

    return {
        "timestamp": datetime.now().isoformat(),
        "cpu": {
            "percent": cpu_percent,
            "count": cpu_count,
            "frequency": {
                "current": cpu_freq.current if cpu_freq else None,
                "min": cpu_freq.min if cpu_freq else None,
                "max": cpu_freq.max if cpu_freq else None
            }
        },
        "memory": {
            "total": memory.total,
            "available": memory.available,
            "percent": memory.percent,
            "used": memory.used,
            "free": memory.free,
            "swap": {
                "total": swap.total,
                "used": swap.used,
                "free": swap.free,
                "percent": swap.percent
            }
        },
        "disk": {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": (disk.used / disk.total) * 100,
            "io": {
                "read_bytes": disk_io.read_bytes if disk_io else 0,
                "write_bytes": disk_io.write_bytes if disk_io else 0,
                "read_count": disk_io.read_count if disk_io else 0,
                "write_count": disk_io.write_count if disk_io else 0
            }
        },
        "network": {
            "bytes_sent": network.bytes_sent if network else 0,
            "bytes_recv": network.bytes_recv if network else 0,
            "packets_sent": network.packets_sent if network else 0,
            "packets_recv": network.packets_recv if network else 0,
            "connections": network_connections
        },
        "process": {
            "pid": process.pid,
            "memory": {
                "rss": process_memory.rss,
                "vms": process_memory.vms
            },
            "cpu_percent": process_cpu,
            "num_threads": process.num_threads(),
            "num_handles": process.num_handles() if hasattr(process, 'num_handles') else 0
        }
    }

# Startup and shutdown functions
async def initialize_performance_tools():
    """Initialize performance monitoring tools"""

    # Enable profiling
    performance_profiler.enable_profiling()

    # Start task queue
    await task_queue.start()

    # Start memory monitoring
    memory_optimizer.start_monitoring(interval=30)

    # Setup Redis cache if available
    # await cache_manager.setup_redis_cache("redis://localhost:6379")

    logger.info("Performance tools initialized")

async def cleanup_performance_tools():
    """Cleanup performance monitoring tools"""

    # Stop task queue
    await task_queue.stop()

    # Disable profiling
    performance_profiler.disable_profiling()

    logger.info("Performance tools cleaned up")