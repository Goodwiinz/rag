"""
API Gateway Service - Port 8080
Handles request routing, authentication, rate limiting, and load balancing
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

try:
    import jwt
except ImportError:
    jwt = None  # Optional dependency
import redis.asyncio as redis
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from src.core.config import settings
from src.shared.exceptions import (
    AuthenticationError,
    AuthorizationError,
    BaseCustomException,
    RateLimitError,
    ServiceUnavailableError,
)
from src.shared.schemas import (
    APIVersion,
    BaseResponse,
    ErrorResponse,
    HealthCheckResponse,
    OrganizationContext,
    RateLimitInfo,
)
from src.shared.utils import (
    CorrelationIdMiddleware,
    EventLogger,
    HealthChecker,
    MetricsCollector,
    RateLimiter,
    get_correlation_id,
    make_http_request,
)

# Configuration
API_GATEWAY_CONFIG = {
    "service_name": "api-gateway",
    "version": "1.0.0",
    "port": 8080,
    "host": "0.0.0.0",  # nosec B104 - containerized deployment
}

# Service registry
SERVICE_REGISTRY = {
    "document-management": {"url": "http://localhost:8001", "health_check": "/health"},
    "search": {"url": "http://localhost:8002", "health_check": "/health"},
    "knowledge-graph": {"url": "http://localhost:8003", "health_check": "/health"},
    "evaluation": {"url": "http://localhost:8004", "health_check": "/health"},
    "processing-pipeline": {"url": "http://localhost:8005", "health_check": "/health"},
    "analytics": {"url": "http://localhost:8006", "health_check": "/health"},
    "user-management": {"url": "http://localhost:8007", "health_check": "/health"},
    "realtime-communications": {
        "url": "http://localhost:8008",
        "health_check": "/health",
    },
}

# Route mappings
ROUTE_MAPPINGS = {
    # Document Management
    "/api/v1/documents": "document-management",
    "/api/v1/files": "document-management",
    "/api/v1/uploads": "document-management",
    # Search
    "/api/v1/search": "search",
    "/api/v1/hybrid-search": "search",
    "/api/v1/suggestions": "search",
    # Knowledge Graph
    "/api/v1/knowledge-graph": "knowledge-graph",
    "/api/v1/entities": "knowledge-graph",
    "/api/v1/graph": "knowledge-graph",
    # Evaluation
    "/api/v1/evaluation": "evaluation",
    "/api/v1/metrics": "evaluation",
    "/api/v1/benchmarks": "evaluation",
    # Processing Pipeline
    "/api/v1/processing": "processing-pipeline",
    "/api/v1/jobs": "processing-pipeline",
    # Analytics
    "/api/v1/analytics": "analytics",
    "/api/v1/dashboard": "analytics",
    "/api/v1/reports": "analytics",
    # User Management
    "/api/v1/auth": "user-management",
    "/api/v1/users": "user-management",
    "/api/v1/organizations": "user-management",
    # Real-time Communications
    "/api/v1/websocket": "realtime-communications",
    "/api/v1/notifications": "realtime-communications",
    "/api/v1/realtime": "realtime-communications",
}

# Initialize FastAPI app
app = FastAPI(
    title="API Gateway Service",
    version=API_GATEWAY_CONFIG["version"],
    description="Gateway service for Multimodal Enterprise RAG System",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"] if settings.DEBUG else ["localhost", "127.0.0.1"],
)

app.add_middleware(CorrelationIdMiddleware)

# Initialize components
rate_limiter = RateLimiter(settings.REDIS_URL)
event_logger = EventLogger(API_GATEWAY_CONFIG["service_name"])
health_checker = HealthChecker(API_GATEWAY_CONFIG["service_name"])
metrics = MetricsCollector(API_GATEWAY_CONFIG["service_name"])
security = HTTPBearer(auto_error=False)

# Prometheus metrics
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code", "service"],
)

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint", "service"],
)

ACTIVE_CONNECTIONS = Gauge("active_connections", "Active connections", ["service"])

RATE_LIMIT_HITS = Counter(
    "rate_limit_hits_total", "Total rate limit hits", ["endpoint", "identifier"]
)


class ServiceHealth(BaseModel):
    """Service health status"""

    service_name: str
    url: str
    status: str
    response_time_ms: float
    last_check: datetime
    error_message: Optional[str] = None


class GatewayStatus(BaseModel):
    """Gateway status response"""

    status: str
    version: str
    uptime_seconds: float
    services: Dict[str, ServiceHealth]
    metrics: Dict[str, Any]


class RouteRequest(BaseModel):
    """Route request model"""

    path: str
    method: str
    headers: Optional[Dict[str, str]] = {}
    query_params: Optional[Dict[str, Any]] = {}
    body: Optional[Dict[str, Any]] = None


# Global variables
service_health: Dict[str, ServiceHealth] = {}
gateway_start_time = time.time()


async def get_service_from_path(path: str) -> Optional[str]:
    """Get service name from request path"""
    for route_pattern, service_name in ROUTE_MAPPINGS.items():
        if path.startswith(route_pattern):
            return service_name
    return None


async def verify_jwt_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[Dict[str, Any]]:
    """Verify JWT token and return payload"""
    if not credentials:
        return None

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except jwt.JWTError:
        raise AuthenticationError("Invalid token")


async def get_user_context(
    request: Request, token_payload: Optional[Dict[str, Any]] = None
) -> Optional[OrganizationContext]:
    """Get user context from token"""
    if not token_payload:
        return None

    try:
        # Extract user information from token
        user_id = token_payload.get("sub")
        organization_id = token_payload.get("organization_id")
        role = token_payload.get("role")
        permissions = token_payload.get("permissions", [])

        if not all([user_id, organization_id, role]):
            return None

        return OrganizationContext(
            organization_id=organization_id,
            user_role=role,
            permissions=permissions,
            storage_quota_mb=0,  # Would get from user service
            storage_used_mb=0.0,  # Would get from user service
        )
    except Exception as e:
        await event_logger.log_error(e, {"operation": "get_user_context"})
        return None


async def check_rate_limit(
    request: Request, user_context: Optional[OrganizationContext] = None
) -> RateLimitInfo:
    """Check rate limit for request"""
    # Get identifier for rate limiting
    if user_context:
        identifier = str(user_context.organization_id)
    else:
        identifier = request.client.host if request.client else "anonymous"

    # Get rate limit rules based on user role and endpoint
    endpoint = request.url.path
    if user_context:
        if user_context.user_role == "admin":
            limit = 1000  # Higher limit for admins
        elif user_context.user_role == "user":
            limit = 100  # Standard user limit
        else:
            limit = 50  # Lower limit for other roles
    else:
        limit = 20  # Very low limit for unauthenticated requests

    # Check rate limit
    is_allowed, info = await rate_limiter.is_allowed(
        key="api_requests",
        limit=limit,
        window=60,  # 1 minute window
        identifier=identifier,
    )

    if not is_allowed:
        RATE_LIMIT_HITS.labels(endpoint=endpoint, identifier=identifier).inc()
        raise RateLimitError(
            retry_after=info["retry_after"], limit=info["limit"], window=60
        )

    return RateLimitInfo(
        limit=info["limit"],
        remaining=info["remaining"],
        reset_time=datetime.fromtimestamp(info["reset_time"], tz=timezone.utc),
        retry_after=info.get("retry_after"),
    )


async def proxy_request(
    service_name: str,
    request: Request,
    user_context: Optional[OrganizationContext] = None,
) -> Response:
    """Proxy request to target service"""
    service_config = SERVICE_REGISTRY.get(service_name)
    if not service_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service '{service_name}' not found",
        )

    # Check service health
    health_status = service_health.get(service_name)
    if health_status and health_status.status != "healthy":
        raise ServiceUnavailableError(
            message=f"Service '{service_name}' is unavailable",
            service_name=service_name,
        )

    # Build target URL
    target_url = f"{service_config['url']}{request.url.path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    # Prepare headers
    headers = dict(request.headers)
    headers.pop("host", None)  # Remove host header

    # Add user context headers
    if user_context:
        headers["X-User-ID"] = str(user_context.organization_id)
        headers["X-Organization-ID"] = str(user_context.organization_id)
        headers["X-User-Role"] = user_context.user_role
        headers["X-User-Permissions"] = ",".join(user_context.permissions)

    # Add correlation ID
    correlation_id = get_correlation_id(request)
    headers["X-Correlation-ID"] = correlation_id

    try:
        # Make request to target service
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=await request.body(),
                follow_redirects=True,
            )

        # Create response
        proxy_response = Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
        )

        # Add rate limit headers
        rate_limit_info = await check_rate_limit(request, user_context)
        proxy_response.headers["X-RateLimit-Limit"] = str(rate_limit_info.limit)
        proxy_response.headers["X-RateLimit-Remaining"] = str(rate_limit_info.remaining)
        proxy_response.headers["X-RateLimit-Reset"] = str(
            int(rate_limit_info.reset_time.timestamp())
        )

        return proxy_response

    except httpx.RequestError as e:
        await event_logger.log_error(
            e,
            {
                "service": service_name,
                "target_url": target_url,
                "method": request.method,
            },
        )
        raise ServiceUnavailableError(
            message=f"Failed to connect to service '{service_name}'",
            service_name=service_name,
        )


@app.on_event("startup")
async def startup_event():
    """Initialize gateway on startup"""
    await event_logger.log_event(
        event_type="gateway_startup",
        event_data={"version": API_GATEWAY_CONFIG["version"]},
    )

    # Add health checks
    for service_name, config in SERVICE_REGISTRY.items():

        async def check_service_health(service_config=config):
            try:
                start_time = time.time()
                health_url = f"{service_config['url']}{service_config['health_check']}"
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(health_url)
                    response.raise_for_status()

                response_time = (time.time() - start_time) * 1000

                # Update service health status
                service_health[service_name] = ServiceHealth(
                    service_name=service_name,
                    url=service_config["url"],
                    status="healthy",
                    response_time_ms=response_time,
                    last_check=datetime.now(timezone.utc),
                )

                return True

            except Exception as e:
                service_health[service_name] = ServiceHealth(
                    service_name=service_name,
                    url=service_config["url"],
                    status="unhealthy",
                    response_time_ms=0,
                    last_check=datetime.now(timezone.utc),
                    error_message=str(e),
                )
                return False

        health_checker.add_check(f"service_{service_name}", check_service_health)

    # Start background tasks
    asyncio.create_task(health_check_loop())
    asyncio.create_task(metrics_collection_loop())


async def health_check_loop():
    """Background task to check service health"""
    while True:
        try:
            await health_checker.check_health()
            await asyncio.sleep(30)  # Check every 30 seconds
        except Exception as e:
            await event_logger.log_error(e, {"task": "health_check_loop"})
            await asyncio.sleep(60)  # Wait longer on error


async def metrics_collection_loop():
    """Background task to collect metrics"""
    while True:
        try:
            # Collect service metrics
            for service_name, health in service_health.items():
                metrics.set_gauge(
                    "service_response_time_ms",
                    health.response_time_ms,
                    {"service": service_name},
                )
                metrics.set_gauge(
                    "service_healthy",
                    1 if health.status == "healthy" else 0,
                    {"service": service_name},
                )

            # Collect gateway metrics
            metrics.set_gauge(
                "gateway_uptime_seconds", time.time() - gateway_start_time
            )

            await asyncio.sleep(60)  # Collect every minute
        except Exception as e:
            await event_logger.log_error(e, {"task": "metrics_collection_loop"})
            await asyncio.sleep(120)


@app.api_route(
    "/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
)
async def gateway_proxy(
    request: Request,
    token_payload: Optional[Dict[str, Any]] = Depends(verify_jwt_token),
):
    """Main gateway proxy handler"""
    start_time = time.time()
    correlation_id = get_correlation_id(request)

    try:
        # Get target service
        service_name = await get_service_from_path(request.url.path)
        if not service_name:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No service found for the requested path",
            )

        # Get user context
        user_context = await get_user_context(request, token_payload)

        # Check rate limits
        await check_rate_limit(request, user_context)

        # Update active connections
        ACTIVE_CONNECTIONS.labels(service=service_name).inc()

        try:
            # Proxy request to service
            response = await proxy_request(service_name, request, user_context)

            # Record metrics
            duration = time.time() - start_time
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.url.path,
                status_code=response.status_code,
                service=service_name,
            ).inc()
            REQUEST_DURATION.labels(
                method=request.method, endpoint=request.url.path, service=service_name
            ).observe(duration)

            # Log successful request
            await event_logger.log_event(
                event_type="request_completed",
                event_data={
                    "method": request.method,
                    "path": request.url.path,
                    "service": service_name,
                    "status_code": response.status_code,
                    "duration_ms": duration * 1000,
                },
                user_id=user_context.organization_id if user_context else None,
                correlation_id=correlation_id,
            )

            return response

        finally:
            # Update active connections
            ACTIVE_CONNECTIONS.labels(service=service_name).dec()

    except BaseCustomException as e:
        # Record error metrics
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status_code=e.status_code,
            service=service_name or "unknown",
        ).inc()

        await event_logger.log_error(
            e,
            {
                "method": request.method,
                "path": request.url.path,
                "service": service_name,
            },
            user_context.organization_id if user_context else None,
            correlation_id=correlation_id,
        )

        raise HTTPException(
            status_code=e.status_code,
            detail={
                "error": {
                    "message": e.message,
                    "error_code": e.error_code,
                    "error_type": e.error_type,
                    "details": e.details,
                    "suggestions": e.suggestions,
                }
            },
        )

    except Exception as e:
        # Record unexpected error
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status_code=500,
            service=service_name or "unknown",
        ).inc()

        await event_logger.log_error(
            e,
            {
                "method": request.method,
                "path": request.url.path,
                "service": service_name,
            },
            correlation_id=correlation_id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "message": "Internal server error",
                    "error_code": "INTERNAL_ERROR",
                    "error_type": "internal_error",
                }
            },
        )


@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Gateway health check"""
    health_data = await health_checker.check_health()

    return HealthCheckResponse(
        status=health_data["status"],
        version=API_GATEWAY_CONFIG["version"],
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc),
        services=health_data["checks"],
        uptime_seconds=time.time() - gateway_start_time,
    )


@app.get("/status", response_model=GatewayStatus)
async def gateway_status():
    """Detailed gateway status"""
    return GatewayStatus(
        status="healthy",
        version=API_GATEWAY_CONFIG["version"],
        uptime_seconds=time.time() - gateway_start_time,
        services=service_health,
        metrics=metrics.get_metrics(),
    )


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus metrics endpoint"""
    if not settings.ENABLE_METRICS:
        raise HTTPException(status_code=404, detail="Metrics not enabled")

    metrics_data = generate_latest()
    return Response(content=metrics_data, media_type=CONTENT_TYPE_LATEST)


@app.get("/routes", response_model=Dict[str, str])
async def list_routes():
    """List all available routes and their target services"""
    return ROUTE_MAPPINGS.copy()


@app.get("/services", response_model=Dict[str, ServiceHealth])
async def list_services():
    """List all services and their health status"""
    return service_health.copy()


@app.get("/version", response_model=APIVersion)
async def get_version():
    """Get API version information"""
    return APIVersion(version=API_GATEWAY_CONFIG["version"], deprecated=False)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await rate_limiter.close()
    await event_logger.log_event(
        event_type="gateway_shutdown",
        event_data={"uptime_seconds": time.time() - gateway_start_time},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.services.api_gateway:app",
        host=API_GATEWAY_CONFIG["host"],
        port=API_GATEWAY_CONFIG["port"],
        log_level=settings.LOG_LEVEL.lower(),
    )
