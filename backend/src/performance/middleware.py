"""
Performance monitoring and profiling middleware for the RAG system
"""

import time
import psutil
import asyncio
from typing import Dict, List, Optional, Callable
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
import json
import logging
from contextlib import asynccontextmanager
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import threading
from prometheus_client import Counter, Histogram, Gauge, generate_latest
import redis.asyncio as redis

logger = logging.getLogger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'HTTP request duration', ['method', 'endpoint'])
MEMORY_USAGE = Gauge('memory_usage_bytes', 'Memory usage in bytes')
CPU_USAGE = Gauge('cpu_usage_percent', 'CPU usage percentage')
CONCURRENT_REQUESTS = Gauge('concurrent_requests', 'Number of concurrent requests')

@dataclass
class PerformanceMetrics:
    """Performance metrics data structure"""
    endpoint: str
    method: str
    status_code: int
    duration: float
    memory_usage_mb: float
    cpu_usage_percent: float
    timestamp: float
    user_id: Optional[str] = None
    query_params: Optional[Dict] = None

@dataclass
class DatabaseMetrics:
    """Database performance metrics"""
    query_type: str
    table: str
    duration: float
    affected_rows: int
    timestamp: float
    query_hash: str

@dataclass
class CacheMetrics:
    """Cache performance metrics"""
    cache_type: str
    operation: str  # 'hit', 'miss', 'set', 'delete'
    key_pattern: str
    duration: float
    size_bytes: int
    timestamp: float

class PerformanceProfiler:
    """Advanced performance profiler for the application"""

    def __init__(self, max_samples: int = 10000):
        self.max_samples = max_samples
        self.metrics_buffer: deque = deque(maxlen=max_samples)
        self.database_metrics: deque = deque(maxlen=5000)
        self.cache_metrics: deque = deque(maxlen=5000)
        self.endpoint_stats: Dict[str, Dict] = defaultdict(lambda: {
            'count': 0,
            'total_duration': 0,
            'min_duration': float('inf'),
            'max_duration': 0,
            'avg_duration': 0,
            'p95_duration': 0,
            'error_count': 0,
            'last_reset': time.time()
        })
        self._lock = threading.Lock()
        self._running = False
        self._monitoring_task: Optional[asyncio.Task] = None

    async def start_monitoring(self):
        """Start continuous performance monitoring"""
        if self._running:
            return

        self._running = True
        self._monitoring_task = asyncio.create_task(self._monitor_system_resources())
        logger.info("Performance profiler started")

    async def stop_monitoring(self):
        """Stop performance monitoring"""
        self._running = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
        logger.info("Performance profiler stopped")

    async def _monitor_system_resources(self):
        """Monitor system resources in background"""
        while self._running:
            try:
                # Update system metrics
                MEMORY_USAGE.set(psutil.virtual_memory().used)
                CPU_USAGE.set(psutil.cpu_percent())
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Error monitoring system resources: {e}")
                await asyncio.sleep(5)

    def record_request(self, metrics: PerformanceMetrics):
        """Record request performance metrics"""
        with self._lock:
            self.metrics_buffer.append(metrics)

            # Update endpoint statistics
            key = f"{metrics.method} {metrics.endpoint}"
            stats = self.endpoint_stats[key]
            stats['count'] += 1
            stats['total_duration'] += metrics.duration
            stats['min_duration'] = min(stats['min_duration'], metrics.duration)
            stats['max_duration'] = max(stats['max_duration'], metrics.duration)
            stats['avg_duration'] = stats['total_duration'] / stats['count']

            if metrics.status_code >= 400:
                stats['error_count'] += 1

    def record_database_query(self, metrics: DatabaseMetrics):
        """Record database query metrics"""
        with self._lock:
            self.database_metrics.append(metrics)

    def record_cache_operation(self, metrics: CacheMetrics):
        """Record cache operation metrics"""
        with self._lock:
            self.cache_metrics.append(metrics)

    def get_endpoint_stats(self, endpoint: Optional[str] = None) -> Dict:
        """Get endpoint performance statistics"""
        with self._lock:
            if endpoint:
                key = endpoint
                return {key: dict(self.endpoint_stats.get(key, {}))}
            return dict(self.endpoint_stats)

    def get_recent_metrics(self, count: int = 100) -> List[PerformanceMetrics]:
        """Get recent performance metrics"""
        with self._lock:
            return list(self.metrics_buffer)[-count:]

    def calculate_percentiles(self, durations: List[float]) -> Dict[str, float]:
        """Calculate percentiles for duration values"""
        if not durations:
            return {}

        sorted_durations = sorted(durations)
        n = len(sorted_durations)

        return {
            'p50': sorted_durations[n // 2],
            'p75': sorted_durations[int(n * 0.75)],
            'p90': sorted_durations[int(n * 0.90)],
            'p95': sorted_durations[int(n * 0.95)],
            'p99': sorted_durations[int(n * 0.99)],
        }

    def get_performance_summary(self, time_window: int = 300) -> Dict:
        """Get performance summary for the last time_window seconds"""
        current_time = time.time()
        cutoff_time = current_time - time_window

        with self._lock:
            # Filter recent metrics
            recent_metrics = [
                m for m in self.metrics_buffer
                if m.timestamp >= cutoff_time
            ]

            if not recent_metrics:
                return {"error": "No metrics available"}

            # Calculate summary statistics
            durations = [m.duration for m in recent_metrics]
            endpoint_counts = defaultdict(int)
            status_counts = defaultdict(int)

            for metric in recent_metrics:
                endpoint_key = f"{metric.method} {metric.endpoint}"
                endpoint_counts[endpoint_key] += 1
                status_counts[metric.status_code] += 1

            percentiles = self.calculate_percentiles(durations)

            return {
                "time_window_seconds": time_window,
                "total_requests": len(recent_metrics),
                "duration_stats": {
                    "min": min(durations),
                    "max": max(durations),
                    "avg": sum(durations) / len(durations),
                    **percentiles
                },
                "requests_per_second": len(recent_metrics) / time_window,
                "status_distribution": dict(status_counts),
                "top_endpoints": dict(sorted(
                    endpoint_counts.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10]),
                "error_rate": sum(1 for m in recent_metrics if m.status_code >= 400) / len(recent_metrics),
                "generated_at": current_time
            }

class PerformanceMiddleware(BaseHTTPMiddleware):
    """Middleware for performance monitoring"""

    def __init__(self, app: ASGIApp, profiler: PerformanceProfiler):
        super().__init__(app)
        self.profiler = profiler
        self.concurrent_requests = 0

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with performance monitoring"""
        # Increment concurrent requests
        CONCURRENT_REQUESTS.inc()
        self.concurrent_requests += 1

        # Record request start
        start_time = time.time()
        method = request.method
        endpoint = request.url.path

        # Get memory usage before request
        process = psutil.Process()
        memory_before = process.memory_info().rss / 1024 / 1024  # MB
        cpu_before = psutil.cpu_percent()

        try:
            # Process request
            response = await call_next(request)

            # Record metrics
            duration = time.time() - start_time
            memory_after = process.memory_info().rss / 1024 / 1024  # MB
            cpu_after = psutil.cpu_percent()

            # Create performance metrics
            metrics = PerformanceMetrics(
                endpoint=endpoint,
                method=method,
                status_code=response.status_code,
                duration=duration,
                memory_usage_mb=memory_after - memory_before,
                cpu_usage_percent=cpu_after - cpu_before,
                timestamp=time.time(),
                query_params=dict(request.query_params) if request.query_params else None
            )

            # Record metrics
            self.profiler.record_request(metrics)

            # Update Prometheus metrics
            REQUEST_COUNT.labels(
                method=method,
                endpoint=endpoint,
                status=response.status_code
            ).inc()

            REQUEST_DURATION.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)

            # Add performance headers
            response.headers["X-Process-Time"] = f"{duration:.4f}"
            response.headers["X-Memory-Usage-MB"] = f"{memory_after:.2f}"

            return response

        except Exception as e:
            # Record error metrics
            duration = time.time() - start_time

            metrics = PerformanceMetrics(
                endpoint=endpoint,
                method=method,
                status_code=500,
                duration=duration,
                memory_usage_mb=0,
                cpu_usage_percent=0,
                timestamp=time.time(),
                query_params=dict(request.query_params) if request.query_params else None
            )

            self.profiler.record_request(metrics)

            # Update error counters
            REQUEST_COUNT.labels(
                method=method,
                endpoint=endpoint,
                status=500
            ).inc()

            raise

        finally:
            # Decrement concurrent requests
            CONCURRENT_REQUESTS.dec()
            self.concurrent_requests -= 1

class DatabaseProfiler:
    """Database query profiler"""

    def __init__(self, profiler: PerformanceProfiler):
        self.profiler = profiler

    @asynccontextmanager
    async def profile_query(self, query_type: str, table: str, query: str):
        """Profile database query execution"""
        start_time = time.time()

        try:
            yield
        finally:
            duration = time.time() - start_time

            # Create query hash for aggregation
            query_hash = hash(query.strip().lower())

            metrics = DatabaseMetrics(
                query_type=query_type,
                table=table,
                duration=duration,
                affected_rows=0,  # Would be set by the actual query execution
                timestamp=time.time(),
                query_hash=str(query_hash)
            )

            self.profiler.record_database_query(metrics)

class CacheProfiler:
    """Cache operation profiler"""

    def __init__(self, profiler: PerformanceProfiler):
        self.profiler = profiler

    @asynccontextmanager
    async def profile_cache_operation(self, cache_type: str, operation: str, key: str):
        """Profile cache operation"""
        start_time = time.time()

        try:
            yield
        finally:
            duration = time.time() - start_time

            # Get cache key pattern (strip user-specific parts)
            key_pattern = key.split(':')[0] if ':' in key else key

            metrics = CacheMetrics(
                cache_type=cache_type,
                operation=operation,
                key_pattern=key_pattern,
                duration=duration,
                size_bytes=0,  # Would be set by actual cache operation
                timestamp=time.time()
            )

            self.profiler.record_cache_operation(metrics)

# Global profiler instance
profiler = PerformanceProfiler()
database_profiler = DatabaseProfiler(profiler)
cache_profiler = CacheProfiler(profiler)