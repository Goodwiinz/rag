"""
Health check API endpoints.
"""
import asyncio
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from ..core.config import get_settings
from ..core.metrics import record_request_count, record_request_duration
from .checker import HealthChecker, HealthStatus

router = APIRouter(prefix="/health", tags=["health"])

# Global health checker instance
_health_checker: Optional[HealthChecker] = None
_last_check_time: float = 0
_check_cache_ttl: float = 30  # Cache health checks for 30 seconds


def get_health_checker() -> HealthChecker:
    """Get or create health checker instance."""
    global _health_checker
    if _health_checker is None:
        settings = get_settings()
        config = {
            "database_url": settings.DATABASE_URL,
            "redis_url": settings.REDIS_URL,
            "neo4j_uri": settings.NEO4J_URI,
            "neo4j_user": settings.NEO4J_USER,
            "neo4j_password": settings.NEO4J_PASSWORD,
            "qdrant_url": settings.QDRANT_URL,
            "openai_api_key": settings.OPENAI_API_KEY,
            "anthropic_api_key": settings.ANTHROPIC_API_KEY,
        }
        _health_checker = HealthChecker(config)
    return _health_checker


async def get_cached_health_results() -> Dict[str, Any]:
    """Get cached health results or run new checks if cache is expired."""
    global _last_check_time

    current_time = time.time()
    health_checker = get_health_checker()

    if current_time - _last_check_time > _check_cache_ttl or not health_checker.results:
        await health_checker.check_all_components()
        _last_check_time = current_time

    return health_checker.get_health_summary()


@router.get("/")
async def health_check(request: Request):
    """
    Basic health check endpoint.
    Returns overall system health status.
    """
    start_time = time.time()

    try:
        health_summary = await get_cached_health_results()

        # Record metrics
        duration = time.time() - start_time
        record_request_count("health_check", "200")
        record_request_duration("health_check", duration)

        # Return appropriate HTTP status based on health
        status_code = 200
        if health_summary["status"] == HealthStatus.UNHEALTHY.value:
            status_code = 503
        elif health_summary["status"] == HealthStatus.DEGRADED.value:
            status_code = 200  # Still return 200 for degraded but indicate in response

        return JSONResponse(
            status_code=status_code,
            content={
                "status": health_summary["status"],
                "timestamp": health_summary["timestamp"],
                "version": "1.0.0",  # This should come from app version
                "uptime": get_uptime(),
                "checks": {k: v["status"] for k, v in health_summary["checks"].items()},
            },
        )

    except Exception as e:
        duration = time.time() - start_time
        record_request_count("health_check", "500")
        record_request_duration("health_check", duration)

        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": time.time(),
                "error": f"Health check failed: {str(e)}",
            },
        )


@router.get("/detailed")
async def detailed_health_check(request: Request):
    """
    Detailed health check endpoint.
    Returns detailed status of all components.
    """
    start_time = time.time()

    try:
        health_summary = await get_cached_health_results()

        # Record metrics
        duration = time.time() - start_time
        record_request_count("health_check_detailed", "200")
        record_request_duration("health_check_detailed", duration)

        # Return appropriate HTTP status based on health
        status_code = 200
        if health_summary["status"] == HealthStatus.UNHEALTHY.value:
            status_code = 503

        return JSONResponse(status_code=status_code, content=health_summary)

    except Exception as e:
        duration = time.time() - start_time
        record_request_count("health_check_detailed", "500")
        record_request_duration("health_check_detailed", duration)

        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": time.time(),
                "error": f"Detailed health check failed: {str(e)}",
            },
        )


@router.get("/check/{component}")
async def check_component(component: str, request: Request):
    """
    Check health of a specific component.
    """
    start_time = time.time()

    try:
        health_checker = get_health_checker()

        # Run specific component check
        check_method = getattr(health_checker, f"check_{component}", None)
        if not check_method:
            raise HTTPException(
                status_code=404, detail=f"Component '{component}' not found"
            )

        result = await check_method()

        # Record metrics
        duration = time.time() - start_time
        record_request_count(f"health_check_{component}", "200")
        record_request_duration(f"health_check_{component}", duration)

        status_code = 200
        if result.status == HealthStatus.UNHEALTHY:
            status_code = 503

        return JSONResponse(
            status_code=status_code,
            content={
                "component": result.component,
                "status": result.status.value,
                "message": result.message,
                "response_time": result.response_time,
                "timestamp": result.timestamp,
                "details": result.details,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        duration = time.time() - start_time
        record_request_count(f"health_check_{component}", "500")
        record_request_duration(f"health_check_{component}", duration)

        return JSONResponse(
            status_code=503,
            content={
                "component": component,
                "status": "unhealthy",
                "message": f"Component check failed: {str(e)}",
                "timestamp": time.time(),
            },
        )


@router.get("/metrics")
async def health_metrics():
    """
    Health-specific metrics endpoint.
    Returns metrics about the health check system itself.
    """
    health_checker = get_health_checker()

    return {
        "health_checker": {
            "last_check_time": _last_check_time,
            "cache_ttl": _check_cache_ttl,
            "components_checked": len(health_checker.results),
            "overall_status": health_checker.get_overall_status().value,
        },
        "system": {"uptime": get_uptime(), "timestamp": time.time()},
    }


@router.post("/invalidate-cache")
async def invalidate_health_cache():
    """
    Invalidate the health check cache.
    Forces new health checks on next request.
    """
    global _last_check_time
    _last_check_time = 0

    return {"message": "Health check cache invalidated", "timestamp": time.time()}


@router.get("/readiness")
async def readiness_probe():
    """
    Kubernetes readiness probe.
    Checks if the application is ready to serve traffic.
    """
    try:
        health_checker = get_health_checker()

        # Check critical components for readiness
        critical_checks = ["database", "redis"]

        for component in critical_checks:
            check_method = getattr(health_checker, f"check_{component}", None)
            if check_method:
                result = await check_method()
                if result.status != HealthStatus.HEALTHY:
                    raise HTTPException(
                        status_code=503,
                        detail=f"Critical component {component} is not healthy",
                    )

        return {"status": "ready", "timestamp": time.time()}

    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Readiness check failed: {str(e)}")


@router.get("/liveness")
async def liveness_probe():
    """
    Kubernetes liveness probe.
    Checks if the application is still alive.
    """
    return {"status": "alive", "timestamp": time.time(), "uptime": get_uptime()}


@router.get("/startup")
async def startup_probe():
    """
    Kubernetes startup probe.
    Checks if the application has started successfully.
    """
    try:
        # Check if the application can respond to basic requests
        health_checker = get_health_checker()

        # Quick check of database connectivity
        db_result = await health_checker.check_database()

        if db_result.status == HealthStatus.HEALTHY:
            return {
                "status": "started",
                "timestamp": time.time(),
                "uptime": get_uptime(),
            }
        else:
            raise HTTPException(
                status_code=503,
                detail="Application not fully started - database not ready",
            )

    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Startup check failed: {str(e)}")


def get_uptime() -> Dict[str, Any]:
    """Get application uptime information."""
    try:
        import psutil

        process = psutil.Process()
        uptime_seconds = time.time() - process.create_time()

        return {
            "seconds": int(uptime_seconds),
            "human_readable": str(timedelta(seconds=int(uptime_seconds))),
        }
    except Exception:
        return {"seconds": 0, "human_readable": "unknown"}
