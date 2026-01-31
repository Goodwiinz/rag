"""
Comprehensive health checking system for all components.
"""
import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import asyncpg
import httpx
import redis.asyncio as aioredis
from neo4j import GraphDatabase
from prometheus_client import Counter, Gauge, Histogram
from qdrant_client import QdrantClient

# Metrics for health checks
HEALTH_CHECK_TOTAL = Counter(
    "health_checks_total", "Total health checks", ["component", "status"]
)
HEALTH_CHECK_DURATION = Histogram(
    "health_check_duration_seconds", "Health check duration", ["component"]
)
COMPONENT_STATUS = Gauge(
    "component_status", "Component status (1=healthy, 0=unhealthy)", ["component"]
)


class HealthStatus(Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    component: str
    status: HealthStatus
    message: str
    response_time: float
    details: Optional[Dict[str, Any]] = None
    timestamp: float = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


class HealthChecker:
    """Comprehensive health checking system."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.results: Dict[str, HealthCheckResult] = {}

    async def check_all_components(self) -> Dict[str, HealthCheckResult]:
        """Run health checks on all components."""
        checks = [
            self.check_database,
            self.check_redis,
            self.check_neo4j,
            self.check_qdrant,
            self.check_external_apis,
            self.check_disk_space,
            self.check_memory_usage,
            self.check_celery_workers,
            self.check_virus_scanner,
            self.check_ai_services,
        ]

        # Run all checks concurrently
        tasks = [check() for check in checks]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                component = checks[i].__name__.replace("check_", "")
                self.results[component] = HealthCheckResult(
                    component=component,
                    status=HealthStatus.UNKNOWN,
                    message=f"Health check failed: {str(result)}",
                    response_time=0.0,
                )
            else:
                self.results[result.component] = result

        return self.results

    async def check_database(self) -> HealthCheckResult:
        """Check PostgreSQL database connectivity."""
        start_time = time.time()
        component = "database"

        try:
            database_url = self.config.get("database_url")
            if not database_url:
                return HealthCheckResult(
                    component=component,
                    status=HealthStatus.UNKNOWN,
                    message="Database URL not configured",
                    response_time=0.0,
                )

            conn = await asyncpg.connect(database_url)

            # Test basic query
            result = await conn.fetchval("SELECT 1")
            await conn.close()

            response_time = time.time() - start_time

            if result == 1:
                HEALTH_CHECK_TOTAL.labels(component=component, status="healthy").inc()
                COMPONENT_STATUS.labels(component=component).set(1)
                return HealthCheckResult(
                    component=component,
                    status=HealthStatus.HEALTHY,
                    message="Database connection successful",
                    response_time=response_time,
                )
            else:
                HEALTH_CHECK_TOTAL.labels(component=component, status="unhealthy").inc()
                COMPONENT_STATUS.labels(component=component).set(0)
                return HealthCheckResult(
                    component=component,
                    status=HealthStatus.UNHEALTHY,
                    message="Database query returned unexpected result",
                    response_time=response_time,
                )

        except Exception as e:
            response_time = time.time() - start_time
            HEALTH_CHECK_TOTAL.labels(component=component, status="unhealthy").inc()
            COMPONENT_STATUS.labels(component=component).set(0)
            return HealthCheckResult(
                component=component,
                status=HealthStatus.UNHEALTHY,
                message=f"Database connection failed: {str(e)}",
                response_time=response_time,
            )

    async def check_redis(self) -> HealthCheckResult:
        """Check Redis connectivity."""
        start_time = time.time()
        component = "redis"

        try:
            redis_url = self.config.get("redis_url")
            if not redis_url:
                return HealthCheckResult(
                    component=component,
                    status=HealthStatus.UNKNOWN,
                    message="Redis URL not configured",
                    response_time=0.0,
                )

            # Parse Redis URL properly using urlparse
            if not redis_url.startswith("redis://"):
                redis_url = f"redis://{redis_url}"

            # Use aioredis.from_url with the full URL to handle all URL components
            redis = await aioredis.from_url(
                redis_url, encoding="utf-8", decode_responses=True
            )

            try:
                # Test ping
                result = await redis.ping()
                response_time = time.time() - start_time

                if result:
                    HEALTH_CHECK_TOTAL.labels(
                        component=component, status="healthy"
                    ).inc()
                    COMPONENT_STATUS.labels(component=component).set(1)
                    return HealthCheckResult(
                        component=component,
                        status=HealthStatus.HEALTHY,
                        message="Redis connection successful",
                        response_time=response_time,
                    )
                else:
                    HEALTH_CHECK_TOTAL.labels(
                        component=component, status="unhealthy"
                    ).inc()
                    COMPONENT_STATUS.labels(component=component).set(0)
                    return HealthCheckResult(
                        component=component,
                        status=HealthStatus.UNHEALTHY,
                        message="Redis ping failed",
                        response_time=response_time,
                    )
            finally:
                await redis.close()

        except Exception as e:
            response_time = time.time() - start_time
            HEALTH_CHECK_TOTAL.labels(component=component, status="unhealthy").inc()
            COMPONENT_STATUS.labels(component=component).set(0)
            return HealthCheckResult(
                component=component,
                status=HealthStatus.UNHEALTHY,
                message=f"Redis connection failed: {str(e)}",
                response_time=response_time,
            )

    async def check_neo4j(self) -> HealthCheckResult:
        """Check Neo4j connectivity."""
        start_time = time.time()
        component = "neo4j"

        try:
            uri = self.config.get("neo4j_uri")
            user = self.config.get("neo4j_user")
            password = self.config.get("neo4j_password")

            if not all([uri, user, password]):
                return HealthCheckResult(
                    component=component,
                    status=HealthStatus.UNKNOWN,
                    message="Neo4j configuration incomplete",
                    response_time=0.0,
                )

            def sync_neo4j_check():
                """Synchronous Neo4j operations to run in thread."""
                driver = GraphDatabase.driver(uri, auth=(user, password))
                try:
                    with driver.session() as session:
                        result = session.run("RETURN 1")
                        value = result.single()[0]
                    return value
                finally:
                    driver.close()

            # Run blocking Neo4j operations in thread pool
            value = await asyncio.to_thread(sync_neo4j_check)

            response_time = time.time() - start_time

            if value == 1:
                HEALTH_CHECK_TOTAL.labels(component=component, status="healthy").inc()
                COMPONENT_STATUS.labels(component=component).set(1)
                return HealthCheckResult(
                    component=component,
                    status=HealthStatus.HEALTHY,
                    message="Neo4j connection successful",
                    response_time=response_time,
                )
            else:
                HEALTH_CHECK_TOTAL.labels(component=component, status="unhealthy").inc()
                COMPONENT_STATUS.labels(component=component).set(0)
                return HealthCheckResult(
                    component=component,
                    status=HealthStatus.UNHEALTHY,
                    message="Neo4j query returned unexpected result",
                    response_time=response_time,
                )

        except Exception as e:
            response_time = time.time() - start_time
            HEALTH_CHECK_TOTAL.labels(component=component, status="unhealthy").inc()
            COMPONENT_STATUS.labels(component=component).set(0)
            return HealthCheckResult(
                component=component,
                status=HealthStatus.UNHEALTHY,
                message=f"Neo4j connection failed: {str(e)}",
                response_time=response_time,
            )

    async def check_qdrant(self) -> HealthCheckResult:
        """Check Qdrant vector database connectivity."""
        start_time = time.time()
        component = "qdrant"

        try:
            url = self.config.get("qdrant_url")
            if not url:
                return HealthCheckResult(
                    component=component,
                    status=HealthStatus.UNKNOWN,
                    message="Qdrant URL not configured",
                    response_time=0.0,
                )

            # Extract host and port
            if url.startswith("http://"):
                url = url.replace("http://", "")
            host, port = url.split(":") if ":" in url else (url, "6333")

            client = QdrantClient(host=host, port=int(port))

            # Test collection list
            collections = client.get_collections()

            response_time = time.time() - start_time

            HEALTH_CHECK_TOTAL.labels(component=component, status="healthy").inc()
            COMPONENT_STATUS.labels(component=component).set(1)
            return HealthCheckResult(
                component=component,
                status=HealthStatus.HEALTHY,
                message=f"Qdrant connection successful ({len(collections.collections)} collections)",
                response_time=response_time,
                details={"collections_count": len(collections.collections)},
            )

        except Exception as e:
            response_time = time.time() - start_time
            HEALTH_CHECK_TOTAL.labels(component=component, status="unhealthy").inc()
            COMPONENT_STATUS.labels(component=component).set(0)
            return HealthCheckResult(
                component=component,
                status=HealthStatus.UNHEALTHY,
                message=f"Qdrant connection failed: {str(e)}",
                response_time=response_time,
            )

    async def check_external_apis(self) -> HealthCheckResult:
        """Check external API connectivity."""
        start_time = time.time()
        component = "external_apis"

        results = {}

        # Check OpenAI API
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.openai.com/v1/models", timeout=10.0
                )
            results["openai"] = {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "response_time": response.elapsed.total_seconds(),
            }
        except Exception as e:
            results["openai"] = {"status": "unhealthy", "error": str(e)}

        # Check Anthropic API
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.anthropic.com/v1/messages", timeout=10.0
                )
            results["anthropic"] = {
                "status": "healthy"
                if response.status_code in [200, 401]
                else "unhealthy",  # 401 means API is up but auth failed
                "response_time": response.elapsed.total_seconds(),
            }
        except Exception as e:
            results["anthropic"] = {"status": "unhealthy", "error": str(e)}

        response_time = time.time() - start_time

        # Determine overall status
        healthy_count = sum(1 for r in results.values() if r["status"] == "healthy")
        total_count = len(results)

        if healthy_count == total_count:
            status = HealthStatus.HEALTHY
            message = "All external APIs are healthy"
        elif healthy_count > 0:
            status = HealthStatus.DEGRADED
            message = f"Some external APIs are unhealthy ({healthy_count}/{total_count} healthy)"
        else:
            status = HealthStatus.UNHEALTHY
            message = "All external APIs are unhealthy"

        HEALTH_CHECK_TOTAL.labels(component=component, status=status.value).inc()
        COMPONENT_STATUS.labels(component=component).set(
            1 if status == HealthStatus.HEALTHY else 0
        )

        return HealthCheckResult(
            component=component,
            status=status,
            message=message,
            response_time=response_time,
            details=results,
        )

    async def check_disk_space(self) -> HealthCheckResult:
        """Check disk space usage."""
        start_time = time.time()
        component = "disk_space"

        try:
            import shutil

            total, used, free = shutil.disk_usage("/")
            used_percent = (used / total) * 100

            response_time = time.time() - start_time

            if used_percent < 80:
                status = HealthStatus.HEALTHY
                message = f"Disk usage is at {used_percent:.1f}%"
            elif used_percent < 90:
                status = HealthStatus.DEGRADED
                message = f"Disk usage is high at {used_percent:.1f}%"
            else:
                status = HealthStatus.UNHEALTHY
                message = f"Disk usage is critical at {used_percent:.1f}%"

            HEALTH_CHECK_TOTAL.labels(component=component, status=status.value).inc()
            COMPONENT_STATUS.labels(component=component).set(
                1 if status == HealthStatus.HEALTHY else 0
            )

            return HealthCheckResult(
                component=component,
                status=status,
                message=message,
                response_time=response_time,
                details={
                    "total_gb": total // (1024**3),
                    "used_gb": used // (1024**3),
                    "free_gb": free // (1024**3),
                    "used_percent": round(used_percent, 1),
                },
            )

        except Exception as e:
            response_time = time.time() - start_time
            HEALTH_CHECK_TOTAL.labels(component=component, status="unhealthy").inc()
            COMPONENT_STATUS.labels(component=component).set(0)
            return HealthCheckResult(
                component=component,
                status=HealthStatus.UNHEALTHY,
                message=f"Disk space check failed: {str(e)}",
                response_time=response_time,
            )

    async def check_memory_usage(self) -> HealthCheckResult:
        """Check memory usage."""
        start_time = time.time()
        component = "memory"

        try:
            import psutil

            memory = psutil.virtual_memory()
            used_percent = memory.percent

            response_time = time.time() - start_time

            if used_percent < 80:
                status = HealthStatus.HEALTHY
                message = f"Memory usage is at {used_percent:.1f}%"
            elif used_percent < 90:
                status = HealthStatus.DEGRADED
                message = f"Memory usage is high at {used_percent:.1f}%"
            else:
                status = HealthStatus.UNHEALTHY
                message = f"Memory usage is critical at {used_percent:.1f}%"

            HEALTH_CHECK_TOTAL.labels(component=component, status=status.value).inc()
            COMPONENT_STATUS.labels(component=component).set(
                1 if status == HealthStatus.HEALTHY else 0
            )

            return HealthCheckResult(
                component=component,
                status=status,
                message=message,
                response_time=response_time,
                details={
                    "total_gb": memory.total // (1024**3),
                    "used_gb": memory.used // (1024**3),
                    "available_gb": memory.available // (1024**3),
                    "used_percent": round(used_percent, 1),
                },
            )

        except Exception as e:
            response_time = time.time() - start_time
            HEALTH_CHECK_TOTAL.labels(component=component, status="unhealthy").inc()
            COMPONENT_STATUS.labels(component=component).set(0)
            return HealthCheckResult(
                component=component,
                status=HealthStatus.UNHEALTHY,
                message=f"Memory check failed: {str(e)}",
                response_time=response_time,
            )

    async def check_celery_workers(self) -> HealthCheckResult:
        """Check Celery worker status."""
        start_time = time.time()
        component = "celery_workers"

        try:
            from ..tasks.celery_app import celery_app

            # Get active workers
            inspect = celery_app.control.inspect()
            active_workers = inspect.active()

            response_time = time.time() - start_time

            if active_workers and len(active_workers) > 0:
                HEALTH_CHECK_TOTAL.labels(component=component, status="healthy").inc()
                COMPONENT_STATUS.labels(component=component).set(1)
                return HealthCheckResult(
                    component=component,
                    status=HealthStatus.HEALTHY,
                    message=f"{len(active_workers)} active Celery workers",
                    response_time=response_time,
                    details={"worker_count": len(active_workers)},
                )
            else:
                HEALTH_CHECK_TOTAL.labels(component=component, status="unhealthy").inc()
                COMPONENT_STATUS.labels(component=component).set(0)
                return HealthCheckResult(
                    component=component,
                    status=HealthStatus.UNHEALTHY,
                    message="No active Celery workers found",
                    response_time=response_time,
                )

        except Exception as e:
            response_time = time.time() - start_time
            HEALTH_CHECK_TOTAL.labels(component=component, status="unhealthy").inc()
            COMPONENT_STATUS.labels(component=component).set(0)
            return HealthCheckResult(
                component=component,
                status=HealthStatus.UNKNOWN,
                message=f"Celery worker check failed: {str(e)}",
                response_time=response_time,
            )

    async def check_virus_scanner(self) -> HealthCheckResult:
        """Check ClamAV virus scanner."""
        start_time = time.time()
        component = "virus_scanner"

        try:
            # Use asyncio.create_subprocess_exec for non-blocking subprocess execution
            try:
                proc = await asyncio.create_subprocess_exec(
                    "clamscan",
                    "--version",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                # Wait for completion with timeout
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=10.0
                )
                returncode = proc.returncode

                response_time = time.time() - start_time

                if returncode == 0:
                    version = stdout.decode().strip()
                    HEALTH_CHECK_TOTAL.labels(
                        component=component, status="healthy"
                    ).inc()
                    COMPONENT_STATUS.labels(component=component).set(1)
                    return HealthCheckResult(
                        component=component,
                        status=HealthStatus.HEALTHY,
                        message=f"ClamAV is running: {version}",
                        response_time=response_time,
                    )
                else:
                    HEALTH_CHECK_TOTAL.labels(
                        component=component, status="unhealthy"
                    ).inc()
                    COMPONENT_STATUS.labels(component=component).set(0)
                    return HealthCheckResult(
                        component=component,
                        status=HealthStatus.UNHEALTHY,
                        message="ClamAV is not responding",
                        response_time=response_time,
                    )
            except asyncio.TimeoutError:
                response_time = time.time() - start_time
                HEALTH_CHECK_TOTAL.labels(component=component, status="unhealthy").inc()
                COMPONENT_STATUS.labels(component=component).set(0)
                return HealthCheckResult(
                    component=component,
                    status=HealthStatus.UNHEALTHY,
                    message="ClamAV health check timed out",
                    response_time=response_time,
                )

        except FileNotFoundError:
            response_time = time.time() - start_time
            HEALTH_CHECK_TOTAL.labels(component=component, status="unhealthy").inc()
            COMPONENT_STATUS.labels(component=component).set(0)
            return HealthCheckResult(
                component=component,
                status=HealthStatus.UNHEALTHY,
                message="ClamAV is not installed",
                response_time=response_time,
            )
        except Exception as e:
            response_time = time.time() - start_time
            HEALTH_CHECK_TOTAL.labels(component=component, status="unhealthy").inc()
            COMPONENT_STATUS.labels(component=component).set(0)
            return HealthCheckResult(
                component=component,
                status=HealthStatus.UNHEALTHY,
                message=f"Virus scanner check failed: {str(e)}",
                response_time=response_time,
            )

    async def check_ai_services(self) -> HealthCheckResult:
        """Check AI service configurations and availability."""
        start_time = time.time()
        component = "ai_services"

        results = {}

        # Check OpenAI configuration
        openai_key = self.config.get("openai_api_key")
        if openai_key:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        "https://api.openai.com/v1/models",
                        headers={"Authorization": f"Bearer {openai_key}"},
                        timeout=10.0,
                    )
                results["openai"] = {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "response_time": response.elapsed.total_seconds(),
                }
            except Exception as e:
                results["openai"] = {"status": "unhealthy", "error": str(e)}
        else:
            results["openai"] = {"status": "not_configured"}

        # Check Anthropic configuration
        anthropic_key = self.config.get("anthropic_api_key")
        if anthropic_key:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        "https://api.anthropic.com/v1/messages",
                        headers={"x-api-key": anthropic_key},
                        timeout=10.0,
                    )
                results["anthropic"] = {
                    "status": "healthy"
                    if response.status_code in [200, 401]
                    else "unhealthy",
                    "response_time": response.elapsed.total_seconds(),
                }
            except Exception as e:
                results["anthropic"] = {"status": "unhealthy", "error": str(e)}
        else:
            results["anthropic"] = {"status": "not_configured"}

        response_time = time.time() - start_time

        # Determine overall status
        healthy_count = sum(1 for r in results.values() if r["status"] == "healthy")
        configured_count = sum(
            1 for r in results.values() if r["status"] != "not_configured"
        )

        if configured_count == 0:
            status = HealthStatus.UNKNOWN
            message = "No AI services configured"
        elif healthy_count == configured_count:
            status = HealthStatus.HEALTHY
            message = "All configured AI services are healthy"
        elif healthy_count > 0:
            status = HealthStatus.DEGRADED
            message = f"Some AI services are unhealthy ({healthy_count}/{configured_count} healthy)"
        else:
            status = HealthStatus.UNHEALTHY
            message = "All configured AI services are unhealthy"

        HEALTH_CHECK_TOTAL.labels(component=component, status=status.value).inc()
        COMPONENT_STATUS.labels(component=component).set(
            1 if status == HealthStatus.HEALTHY else 0
        )

        return HealthCheckResult(
            component=component,
            status=status,
            message=message,
            response_time=response_time,
            details=results,
        )

    def get_overall_status(self) -> HealthStatus:
        """Get overall system health status."""
        if not self.results:
            return HealthStatus.UNKNOWN

        statuses = [result.status for result in self.results.values()]

        if all(status == HealthStatus.HEALTHY for status in statuses):
            return HealthStatus.HEALTHY
        elif any(status == HealthStatus.UNHEALTHY for status in statuses):
            return HealthStatus.UNHEALTHY
        elif any(status == HealthStatus.DEGRADED for status in statuses):
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.UNKNOWN

    def get_health_summary(self) -> Dict[str, Any]:
        """Get a summary of all health checks."""
        overall_status = self.get_overall_status()

        return {
            "status": overall_status.value,
            "timestamp": time.time(),
            "checks": {
                component: {
                    "status": result.status.value,
                    "message": result.message,
                    "response_time": result.response_time,
                    "details": result.details,
                }
                for component, result in self.results.items()
            },
        }
