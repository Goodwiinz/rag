"""Health checks for readiness-critical dependencies."""

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict

import redis.asyncio as aioredis
from prometheus_client import Counter, Gauge

HEALTH_CHECK_TOTAL = Counter(
    "health_checks_total", "Total health checks", ["component", "status"]
)
COMPONENT_STATUS = Gauge(
    "component_status", "Component status (1=healthy, 0=unhealthy)", ["component"]
)


class HealthStatus(Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    component: str
    status: HealthStatus
    message: str
    response_time: float


class HealthChecker:
    """Check PostgreSQL and Redis, the dependencies that gate readiness."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    async def check_database(self) -> HealthCheckResult:
        """Check PostgreSQL using the application's pooled async engine."""
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

            try:
                from sqlalchemy import text

                from src.core.database import async_engine
            except Exception as import_err:
                return HealthCheckResult(
                    component=component,
                    status=HealthStatus.UNKNOWN,
                    message=f"Database engine not initialized: {import_err}",
                    response_time=time.time() - start_time,
                )

            async with async_engine.connect() as conn:
                result = await conn.scalar(text("SELECT 1"))

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

            HEALTH_CHECK_TOTAL.labels(component=component, status="unhealthy").inc()
            COMPONENT_STATUS.labels(component=component).set(0)
            return HealthCheckResult(
                component=component,
                status=HealthStatus.UNHEALTHY,
                message="Database query returned unexpected result",
                response_time=response_time,
            )
        except Exception as exc:
            response_time = time.time() - start_time
            HEALTH_CHECK_TOTAL.labels(component=component, status="unhealthy").inc()
            COMPONENT_STATUS.labels(component=component).set(0)
            return HealthCheckResult(
                component=component,
                status=HealthStatus.UNHEALTHY,
                message=f"Database connection failed: {exc}",
                response_time=response_time,
            )

    async def check_redis(self) -> HealthCheckResult:
        """Check Redis using the configured URL without rewriting its scheme."""
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

            redis = aioredis.from_url(
                redis_url, encoding="utf-8", decode_responses=True
            )
            try:
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

                HEALTH_CHECK_TOTAL.labels(component=component, status="unhealthy").inc()
                COMPONENT_STATUS.labels(component=component).set(0)
                return HealthCheckResult(
                    component=component,
                    status=HealthStatus.UNHEALTHY,
                    message="Redis ping failed",
                    response_time=response_time,
                )
            finally:
                await redis.close()
        except Exception as exc:
            response_time = time.time() - start_time
            HEALTH_CHECK_TOTAL.labels(component=component, status="unhealthy").inc()
            COMPONENT_STATUS.labels(component=component).set(0)
            return HealthCheckResult(
                component=component,
                status=HealthStatus.UNHEALTHY,
                message=f"Redis connection failed: {exc}",
                response_time=response_time,
            )
