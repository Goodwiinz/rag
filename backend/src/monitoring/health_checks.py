"""
Health Check System for Knowledge Graph Analytics Dashboard
Comprehensive health monitoring for applications and dependencies
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

import aiohttp
import asyncpg
import psutil
import redis.asyncio as redis
from elasticsearch import AsyncElasticsearch

from .logging import get_logger
from .metrics import business_metrics
from .opentelemetry import otel_manager

logger = get_logger(__name__)


class HealthStatus(Enum):
    """Health check status levels"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class CheckType(Enum):
    """Types of health checks"""

    LIVENESS = "liveness"
    READINESS = "readiness"
    DEPENDENCY = "dependency"
    RESOURCE = "resource"
    SECURITY = "security"


@dataclass
class HealthCheckResult:
    """Result of a health check"""

    name: str
    status: HealthStatus
    message: str
    duration_ms: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = field(default_factory=dict)
    check_type: CheckType = CheckType.DEPENDENCY
    component: str = ""
    threshold: Optional[float] = None
    actual_value: Optional[float] = None


@dataclass
class HealthSummary:
    """Summary of overall system health"""

    status: HealthStatus
    total_checks: int
    healthy_checks: int
    degraded_checks: int
    unhealthy_checks: int
    unknown_checks: int
    checks: List[HealthCheckResult] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    overall_score: float = 0.0


class HealthCheck:
    """Base class for health checks"""

    def __init__(
        self,
        name: str,
        check_type: CheckType = CheckType.DEPENDENCY,
        timeout: float = 10.0,
        component: str = "",
    ):
        self.name = name
        self.check_type = check_type
        self.timeout = timeout
        self.component = component
        self.last_check: Optional[HealthCheckResult] = None
        self.check_count = 0
        self.failure_count = 0
        self.consecutive_failures = 0
        self.last_success: Optional[datetime] = None
        self.last_failure: Optional[datetime] = None

    async def check(self) -> HealthCheckResult:
        """Perform the health check"""
        start_time = time.time()
        self.check_count += 1

        try:
            result = await asyncio.wait_for(self._check_health(), timeout=self.timeout)
            self.consecutive_failures = 0
            self.last_success = datetime.utcnow()
        except asyncio.TimeoutError:
            result = HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check timed out after {self.timeout}s",
                duration_ms=(time.time() - start_time) * 1000,
                check_type=self.check_type,
                component=self.component,
            )
            self._handle_failure()
        except Exception as e:
            result = HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000,
                check_type=self.check_type,
                component=self.component,
                details={"error": str(e), "error_type": type(e).__name__},
            )
            self._handle_failure()

        self.last_check = result
        return result

    async def _check_health(self) -> HealthCheckResult:
        """Override this method to implement specific health check logic"""
        raise NotImplementedError

    def _handle_failure(self):
        """Handle check failure"""
        self.failure_count += 1
        self.consecutive_failures += 1
        self.last_failure = datetime.utcnow()

    def get_availability_percentage(self) -> float:
        """Get availability percentage based on check history"""
        if self.check_count == 0:
            return 0.0
        return ((self.check_count - self.failure_count) / self.check_count) * 100


class DatabaseHealthCheck(HealthCheck):
    """Database health check"""

    def __init__(self, connection_string: str, **kwargs):
        super().__init__("database", CheckType.DEPENDENCY, **kwargs)
        self.connection_string = connection_string

    async def _check_health(self) -> HealthCheckResult:
        """Check database connectivity and performance"""
        start_time = time.time()

        try:
            # Test database connection
            conn = await asyncpg.connect(self.connection_string)

            # Test simple query
            result = await conn.fetchval("SELECT 1")

            # Get database stats
            stats = await conn.fetchrow(
                """
                SELECT
                    count(*) as total_connections,
                    count(*) FILTER (WHERE state = 'active') as active_connections
                FROM pg_stat_activity
            """
            )

            await conn.close()

            duration_ms = (time.time() - start_time) * 1000

            if result != 1:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.UNHEALTHY,
                    message="Database query returned unexpected result",
                    duration_ms=duration_ms,
                    check_type=self.check_type,
                    component=self.component,
                    details={"query_result": result},
                )

            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY,
                message="Database connection successful",
                duration_ms=duration_ms,
                check_type=self.check_type,
                component=self.component,
                details={
                    "total_connections": stats["total_connections"],
                    "active_connections": stats["active_connections"],
                },
                actual_value=duration_ms,
                threshold=1000.0,  # 1 second threshold
            )

        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Database health check failed: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000,
                check_type=self.check_type,
                component=self.component,
                details={"error": str(e)},
            )


class RedisHealthCheck(HealthCheck):
    """Redis health check"""

    def __init__(self, redis_url: str, **kwargs):
        super().__init__("redis", CheckType.DEPENDENCY, **kwargs)
        self.redis_url = redis_url

    async def _check_health(self) -> HealthCheckResult:
        """Check Redis connectivity and performance"""
        start_time = time.time()

        try:
            # Test Redis connection
            redis_client = redis.from_url(self.redis_url)

            # Test ping
            await redis_client.ping()

            # Test set/get operations
            test_key = f"health_check_{int(time.time())}"
            await redis_client.set(test_key, "test", ex=10)
            value = await redis_client.get(test_key)

            # Get Redis info
            info = await redis_client.info()

            await redis_client.close()

            duration_ms = (time.time() - start_time) * 1000

            if value != b"test":
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.UNHEALTHY,
                    message="Redis set/get operation failed",
                    duration_ms=duration_ms,
                    check_type=self.check_type,
                    component=self.component,
                )

            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY,
                message="Redis connection successful",
                duration_ms=duration_ms,
                check_type=self.check_type,
                component=self.component,
                details={
                    "used_memory": info.get("used_memory", 0),
                    "connected_clients": info.get("connected_clients", 0),
                    "total_commands_processed": info.get("total_commands_processed", 0),
                },
                actual_value=duration_ms,
                threshold=500.0,  # 500ms threshold
            )

        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Redis health check failed: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000,
                check_type=self.check_type,
                component=self.component,
                details={"error": str(e)},
            )


class ElasticsearchHealthCheck(HealthCheck):
    """Elasticsearch health check"""

    def __init__(self, elasticsearch_url: str, **kwargs):
        super().__init__("elasticsearch", CheckType.DEPENDENCY, **kwargs)
        self.elasticsearch_url = elasticsearch_url

    async def _check_health(self) -> HealthCheckResult:
        """Check Elasticsearch connectivity and cluster health"""
        start_time = time.time()

        try:
            # Test Elasticsearch connection
            es = AsyncElasticsearch([self.elasticsearch_url])

            # Get cluster health
            health = await es.cluster.health()

            # Test search operation
            await es.search(index="_all", size=1)

            await es.close()

            duration_ms = (time.time() - start_time) * 1000

            # Determine status based on cluster health
            cluster_status = health.get("status", "unknown")

            if cluster_status == "red":
                status = HealthStatus.UNHEALTHY
            elif cluster_status == "yellow":
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.HEALTHY

            return HealthCheckResult(
                name=self.name,
                status=status,
                message=f"Elasticsearch cluster status: {cluster_status}",
                duration_ms=duration_ms,
                check_type=self.check_type,
                component=self.component,
                details={
                    "cluster_status": cluster_status,
                    "number_of_nodes": health.get("number_of_nodes", 0),
                    "active_primary_shards": health.get("active_primary_shards", 0),
                    "active_shards": health.get("active_shards", 0),
                },
                actual_value=duration_ms,
                threshold=2000.0,  # 2 second threshold
            )

        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Elasticsearch health check failed: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000,
                check_type=self.check_type,
                component=self.component,
                details={"error": str(e)},
            )


class HTTPHealthCheck(HealthCheck):
    """HTTP endpoint health check"""

    def __init__(
        self,
        url: str,
        method: str = "GET",
        expected_status: int = 200,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ):
        super().__init__(
            f"http_{url.replace('://', '_').replace('/', '_')}",
            CheckType.DEPENDENCY,
            **kwargs,
        )
        self.url = url
        self.method = method
        self.expected_status = expected_status
        self.headers = headers or {}

    async def _check_health(self) -> HealthCheckResult:
        """Check HTTP endpoint"""
        start_time = time.time()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    self.method,
                    self.url,
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as response:
                    content_length = len(await response.read())

                    duration_ms = (time.time() - start_time) * 1000

                    if response.status == self.expected_status:
                        status = HealthStatus.HEALTHY
                        message = f"HTTP {self.method} {self.url} - {response.status}"
                    elif 400 <= response.status < 500:
                        status = HealthStatus.DEGRADED
                        message = f"HTTP {self.method} {self.url} - Client error: {response.status}"
                    else:
                        status = HealthStatus.UNHEALTHY
                        message = f"HTTP {self.method} {self.url} - Server error: {response.status}"

                    return HealthCheckResult(
                        name=self.name,
                        status=status,
                        message=message,
                        duration_ms=duration_ms,
                        check_type=self.check_type,
                        component=self.component,
                        details={
                            "status_code": response.status,
                            "content_length": content_length,
                            "headers": dict(response.headers),
                        },
                        actual_value=duration_ms,
                        threshold=5000.0,  # 5 second threshold
                    )

        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"HTTP health check failed: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000,
                check_type=self.check_type,
                component=self.component,
                details={"error": str(e)},
            )


class ResourceHealthCheck(HealthCheck):
    """System resource health check"""

    def __init__(
        self,
        resource_type: str,
        warning_threshold: float,
        critical_threshold: float,
        **kwargs,
    ):
        super().__init__(f"resource_{resource_type}", CheckType.RESOURCE, **kwargs)
        self.resource_type = resource_type
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

    async def _check_health(self) -> HealthCheckResult:
        """Check system resource usage"""
        start_time = time.time()

        try:
            if self.resource_type == "cpu":
                usage_percent = psutil.cpu_percent(interval=1)
                message = f"CPU usage: {usage_percent:.1f}%"
            elif self.resource_type == "memory":
                memory = psutil.virtual_memory()
                usage_percent = memory.percent
                message = f"Memory usage: {usage_percent:.1f}% ({memory.used / 1024**3:.1f}GB / {memory.total / 1024**3:.1f}GB)"
            elif self.resource_type == "disk":
                disk = psutil.disk_usage("/")
                usage_percent = (disk.used / disk.total) * 100
                message = f"Disk usage: {usage_percent:.1f}% ({disk.used / 1024**3:.1f}GB / {disk.total / 1024**3:.1f}GB)"
            else:
                raise ValueError(f"Unknown resource type: {self.resource_type}")

            duration_ms = (time.time() - start_time) * 1000

            # Determine status based on thresholds
            if usage_percent >= self.critical_threshold:
                status = HealthStatus.UNHEALTHY
            elif usage_percent >= self.warning_threshold:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.HEALTHY

            return HealthCheckResult(
                name=self.name,
                status=status,
                message=message,
                duration_ms=duration_ms,
                check_type=self.check_type,
                component=self.component,
                details={
                    "usage_percent": usage_percent,
                    "warning_threshold": self.warning_threshold,
                    "critical_threshold": self.critical_threshold,
                },
                actual_value=usage_percent,
                threshold=self.warning_threshold,
            )

        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Resource health check failed: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000,
                check_type=self.check_type,
                component=self.component,
                details={"error": str(e)},
            )


class CustomHealthCheck(HealthCheck):
    """Custom health check with user-defined function"""

    def __init__(self, name: str, check_function: Callable[[], Any], **kwargs):
        super().__init__(name, **kwargs)
        self.check_function = check_function

    async def _check_health(self) -> HealthCheckResult:
        """Execute custom health check function"""
        start_time = time.time()

        try:
            # Call the custom function
            if asyncio.iscoroutinefunction(self.check_function):
                result = await self.check_function()
            else:
                result = self.check_function()

            duration_ms = (time.time() - start_time) * 1000

            # Handle different result types
            if isinstance(result, HealthCheckResult):
                return result
            elif isinstance(result, bool):
                status = HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
                message = "Custom check passed" if result else "Custom check failed"
            elif isinstance(result, dict):
                status = HealthStatus(result.get("status", "unknown"))
                message = result.get("message", "Custom check completed")
                details = {
                    k: v for k, v in result.items() if k not in ["status", "message"]
                }
            else:
                status = HealthStatus.HEALTHY
                message = f"Custom check result: {result}"
                details = {"result": result}

            return HealthCheckResult(
                name=self.name,
                status=status,
                message=message,
                duration_ms=duration_ms,
                check_type=self.check_type,
                component=self.component,
                details=details,
                actual_value=duration_ms,
            )

        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Custom health check failed: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000,
                check_type=self.check_type,
                component=self.component,
                details={"error": str(e)},
            )


class HealthCheckManager:
    """Manager for health checks"""

    def __init__(self):
        self.checks: Dict[str, HealthCheck] = {}
        self.last_summary: Optional[HealthSummary] = None
        self._check_results: List[HealthCheckResult] = []

    def add_check(self, health_check: HealthCheck):
        """Add a health check"""
        self.checks[health_check.name] = health_check

    def remove_check(self, name: str):
        """Remove a health check"""
        if name in self.checks:
            del self.checks[name]

    async def run_check(self, name: str) -> HealthCheckResult:
        """Run a specific health check"""
        if name not in self.checks:
            raise ValueError(f"Health check '{name}' not found")

        result = await self.checks[name].check()
        self._check_results.append(result)

        # Keep only last 1000 results
        if len(self._check_results) > 1000:
            self._check_results = self._check_results[-1000:]

        return result

    async def run_all_checks(self) -> HealthSummary:
        """Run all health checks and return summary"""
        if not self.checks:
            return HealthSummary(
                status=HealthStatus.UNKNOWN,
                total_checks=0,
                healthy_checks=0,
                degraded_checks=0,
                unhealthy_checks=0,
                unknown_checks=0,
            )

        # Run all checks concurrently
        tasks = [check.check() for check in self.checks.values()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        check_results = []
        healthy_count = 0
        degraded_count = 0
        unhealthy_count = 0
        unknown_count = 0

        from src.core.async_utils import reraise_if_cancelled

        for result in results:
            reraise_if_cancelled(result)
            if isinstance(result, Exception):
                # Handle exceptions
                error_result = HealthCheckResult(
                    name="unknown",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Check failed with exception: {str(result)}",
                    duration_ms=0,
                )
                check_results.append(error_result)
                unhealthy_count += 1
            else:
                check_results.append(result)

                if result.status == HealthStatus.HEALTHY:
                    healthy_count += 1
                elif result.status == HealthStatus.DEGRADED:
                    degraded_count += 1
                elif result.status == HealthStatus.UNHEALTHY:
                    unhealthy_count += 1
                else:
                    unknown_count += 1

        # Determine overall status
        if unhealthy_count > 0:
            overall_status = HealthStatus.UNHEALTHY
        elif degraded_count > 0:
            overall_status = HealthStatus.DEGRADED
        elif healthy_count > 0:
            overall_status = HealthStatus.HEALTHY
        else:
            overall_status = HealthStatus.UNKNOWN

        # Calculate overall score
        total_weighted_score = 0
        total_weight = 0

        for result in check_results:
            weight = 1.0
            score = 0.0

            if result.status == HealthStatus.HEALTHY:
                score = 1.0
            elif result.status == HealthStatus.DEGRADED:
                score = 0.5
            elif result.status == HealthStatus.UNHEALTHY:
                score = 0.0

            # Apply weight based on check type
            if result.check_type == CheckType.DEPENDENCY:
                weight = 2.0
            elif result.check_type == CheckType.RESOURCE:
                weight = 1.5

            total_weighted_score += score * weight
            total_weight += weight

        overall_score = total_weighted_score / total_weight if total_weight > 0 else 0.0

        # Create summary
        summary = HealthSummary(
            status=overall_status,
            total_checks=len(check_results),
            healthy_checks=healthy_count,
            degraded_checks=degraded_count,
            unhealthy_checks=unhealthy_count,
            unknown_checks=unknown_count,
            checks=check_results,
            overall_score=overall_score,
        )

        self.last_summary = summary
        self._record_health_metrics(summary)

        return summary

    def _record_health_metrics(self, summary: HealthSummary):
        """Record health metrics"""
        # Record overall health score
        business_metrics.record_metric("health_score", summary.overall_score, "score")

        # Record individual check statuses
        for result in summary.checks:
            status_value = 1 if result.status == HealthStatus.HEALTHY else 0
            business_metrics.record_metric(
                "health_check_status",
                status_value,
                "status",
                {
                    "check_name": result.name,
                    "component": result.component,
                    "check_type": result.check_type.value,
                },
            )

    def get_check_statistics(self, name: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a specific check"""
        if name not in self.checks:
            return None

        check = self.checks[name]
        return {
            "name": check.name,
            "check_type": check.check_type.value,
            "component": check.component,
            "check_count": check.check_count,
            "failure_count": check.failure_count,
            "consecutive_failures": check.consecutive_failures,
            "availability_percentage": check.get_availability_percentage(),
            "last_success": check.last_success.isoformat()
            if check.last_success
            else None,
            "last_failure": check.last_failure.isoformat()
            if check.last_failure
            else None,
            "last_check": check.last_check.timestamp.isoformat()
            if check.last_check
            else None,
            "last_status": check.last_check.status.value if check.last_check else None,
        }

    def get_all_statistics(self) -> Dict[str, Any]:
        """Get statistics for all checks"""
        return {
            "total_checks": len(self.checks),
            "check_statistics": {
                name: self.get_check_statistics(name) for name in self.checks.keys()
            },
            "last_summary": {
                "status": self.last_summary.status.value,
                "overall_score": self.last_summary.overall_score,
                "timestamp": self.last_summary.timestamp.isoformat(),
            }
            if self.last_summary
            else None,
        }


# Global health check manager instance
health_manager = HealthCheckManager()


# Convenience functions
def setup_default_health_checks():
    """Setup default health checks for the application"""

    # Database health check
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        health_manager.add_check(DatabaseHealthCheck(db_url, component="database"))

    # Redis health check
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        health_manager.add_check(RedisHealthCheck(redis_url, component="cache"))

    # Elasticsearch health check
    es_url = os.environ.get("ELASTICSEARCH_URL")
    if es_url:
        health_manager.add_check(ElasticsearchHealthCheck(es_url, component="search"))

    # Resource health checks
    health_manager.add_check(ResourceHealthCheck("cpu", 70.0, 90.0, component="system"))
    health_manager.add_check(
        ResourceHealthCheck("memory", 80.0, 95.0, component="system")
    )
    health_manager.add_check(
        ResourceHealthCheck("disk", 85.0, 95.0, component="system")
    )


async def check_health() -> HealthSummary:
    """Check overall system health"""
    return await health_manager.run_all_checks()


async def check_component_health(component: str) -> HealthSummary:
    """Check health of specific component"""
    # Filter checks by component
    component_checks = [
        check
        for check in health_manager.checks.values()
        if check.component == component
    ]

    if not component_checks:
        return HealthSummary(
            status=HealthStatus.UNKNOWN,
            total_checks=0,
            healthy_checks=0,
            degraded_checks=0,
            unhealthy_checks=0,
            unknown_checks=0,
        )

    # Run component-specific checks
    tasks = [check.check() for check in component_checks]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results (similar to run_all_checks)
    check_results = []
    healthy_count = degraded_count = unhealthy_count = unknown_count = 0

    from src.core.async_utils import reraise_if_cancelled

    for result in results:
        reraise_if_cancelled(result)
        if isinstance(result, Exception):
            unhealthy_count += 1
        else:
            check_results.append(result)
            if result.status == HealthStatus.HEALTHY:
                healthy_count += 1
            elif result.status == HealthStatus.DEGRADED:
                degraded_count += 1
            elif result.status == HealthStatus.UNHEALTHY:
                unhealthy_count += 1
            else:
                unknown_count += 1

    # Determine overall status
    if unhealthy_count > 0:
        overall_status = HealthStatus.UNHEALTHY
    elif degraded_count > 0:
        overall_status = HealthStatus.DEGRADED
    else:
        overall_status = HealthStatus.HEALTHY

    return HealthSummary(
        status=overall_status,
        total_checks=len(check_results),
        healthy_checks=healthy_count,
        degraded_checks=degraded_count,
        unhealthy_checks=unhealthy_count,
        unknown_checks=unknown_count,
        checks=check_results,
    )
