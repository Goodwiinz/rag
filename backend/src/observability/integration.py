"""
Integration module for observability components in the Multimodal RAG System.
Provides automatic initialization and middleware for FastAPI applications.
"""

import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Callable, Dict, Optional

from fastapi import Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint

from .config import config
from .logging import configure_logging, correlation_context, get_logger
from .metrics import configure_metrics, get_meter, track_performance
from .performance_optimization import get_profiler, profile_performance
from .performance_testing import test_runner
from .slo_monitoring import get_slo_monitor, record_slo_metrics
from .tracer import configure_tracing, get_trace_id, set_correlation_id, trace_span

logger = get_logger(__name__)


class ObservabilityManager:
    """Central observability management and configuration."""

    def __init__(self):
        self.initialized = False
        self.tracer = None
        self.meter = None
        self.slo_monitor = None
        self.profiler = None

    def initialize(self):
        """Initialize all observability components."""
        if self.initialized:
            logger.warning("Observability already initialized")
            return

        try:
            logger.info("Initializing observability components")

            # Configure structured logging first
            configure_logging()
            logger.info("Structured logging configured")

            # Configure tracing
            self.tracer = configure_tracing()
            logger.info("Distributed tracing configured")

            # Configure metrics
            self.meter = configure_metrics()
            logger.info("Metrics collection configured")

            # Initialize SLO monitoring
            self.slo_monitor = get_slo_monitor()
            logger.info("SLO monitoring initialized")

            # Initialize performance profiler
            self.profiler = get_profiler()
            logger.info("Performance profiler initialized")

            # Setup alert callbacks
            self._setup_alerting()

            self.initialized = True
            logger.info("All observability components initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize observability: {e}")
            raise

    def _setup_alerting(self):
        """Setup alerting callbacks and integrations."""

        def alert_callback(alert_data: Dict[str, Any]):
            """Handle SLO alerts."""
            logger.warning(
                f"SLO Alert: {alert_data['slo_name']} - {alert_data['new_status']}",
                **alert_data,
            )

            # Here you could integrate with external alerting systems
            # like PagerDuty, Slack, email, etc.

        self.slo_monitor.add_alert_callback(alert_callback)

    def health_check(self) -> Dict[str, Any]:
        """Perform health check of all observability components."""
        health_status = {
            "status": "healthy",
            "components": {},
            "timestamp": time.time(),
        }

        try:
            # Check logging
            health_status["components"]["logging"] = {
                "status": "healthy",
                "level": config.log_level,
                "format": config.log_format,
            }

            # Check tracing
            health_status["components"]["tracing"] = {
                "status": "healthy" if self.tracer else "uninitialized",
                "service_name": config.otel_service_name,
                "environment": config.otel_environment,
            }

            # Check metrics
            health_status["components"]["metrics"] = {
                "status": "healthy" if self.meter else "uninitialized",
                "prometheus_port": config.prometheus_port,
            }

            # Check SLO monitoring
            health_status["components"]["slo_monitoring"] = {
                "status": "healthy" if self.slo_monitor else "uninitialized",
                "slos_configured": len(self.slo_monitor.slos)
                if self.slo_monitor
                else 0,
            }

        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)
            logger.error(f"Observability health check failed: {e}")

        return health_status


# Global observability manager
observability_manager = ObservabilityManager()


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for automatic observability instrumentation."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Generate correlation ID
        correlation_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())

        # Set correlation context
        with correlation_context(
            correlation_id=correlation_id,
            request_id=request_id,
            user_id=getattr(request.state, "user_id", None),
        ):
            # Start performance tracking
            start_time = time.time()

            # Create span for HTTP request
            with trace_span(
                name=f"HTTP {request.method} {request.url.path}",
                attributes={
                    "http.method": request.method,
                    "http.url": str(request.url),
                    "http.scheme": request.url.scheme,
                    "http.host": request.url.hostname,
                    "http.target": request.url.path,
                    "http.user_agent": request.headers.get("user-agent", ""),
                    "http.remote_addr": request.client.host if request.client else "",
                    "correlation_id": correlation_id,
                    "request_id": request_id,
                },
            ):
                try:
                    # Process request
                    response = await call_next(request)

                    # Calculate duration
                    duration = time.time() - start_time

                    # Record SLO metrics
                    record_slo_metrics(
                        operation=f"{request.method} {request.url.path}",
                        duration=duration,
                        success=response.status_code < 500,
                        metadata={
                            "status_code": response.status_code,
                            "correlation_id": correlation_id,
                            "request_id": request_id,
                        },
                    )

                    # Add custom headers
                    response.headers["X-Correlation-ID"] = correlation_id
                    response.headers["X-Request-ID"] = request_id
                    response.headers["X-Trace-ID"] = get_trace_id() or ""

                    # Log request completion
                    logger.info(
                        f"HTTP request completed",
                        extra={
                            "http_method": request.method,
                            "http_path": request.url.path,
                            "status_code": response.status_code,
                            "duration_seconds": duration,
                            "correlation_id": correlation_id,
                            "request_id": request_id,
                        },
                    )

                    return response

                except Exception as e:
                    # Calculate duration even for errors
                    duration = time.time() - start_time

                    # Record failed request
                    record_slo_metrics(
                        operation=f"{request.method} {request.url.path}",
                        duration=duration,
                        success=False,
                        metadata={
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                            "correlation_id": correlation_id,
                            "request_id": request_id,
                        },
                    )

                    # Log error
                    logger.error(
                        f"HTTP request failed",
                        extra={
                            "http_method": request.method,
                            "http_path": request.url.path,
                            "duration_seconds": duration,
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                            "correlation_id": correlation_id,
                            "request_id": request_id,
                        },
                        exc_info=True,
                    )

                    raise


def setup_observability(app):
    """Setup observability for FastAPI application."""
    # Initialize observability components
    observability_manager.initialize()

    # Add middleware
    app.add_middleware(ObservabilityMiddleware)

    # Add health check endpoint
    @app.get("/health/observability")
    async def observability_health():
        return observability_manager.health_check()

    # Add metrics endpoint
    @app.get("/metrics")
    async def metrics():
        import json

        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

        from .metrics import get_metrics_registry

        registry = get_metrics_registry()
        if registry:
            metrics_data = generate_latest(registry).decode("utf-8")
            return Response(content=metrics_data, media_type=CONTENT_TYPE_LATEST)
        else:
            return {"error": "Metrics not available"}

    # Add performance testing endpoints
    @app.post("/admin/performance-test")
    async def run_performance_test(request: Request):
        """Run performance tests (admin only)."""
        try:
            test_config = await request.json()
            result = await test_runner.run_load_test(test_config)
            return {"status": "completed", "result": result}
        except Exception as e:
            logger.error(f"Performance test failed: {e}")
            return {"status": "error", "message": str(e)}

    logger.info("Observability middleware and endpoints configured")


# Decorators for easy instrumentation


def observe_function(operation: Optional[str] = None):
    """Decorator for automatic function observation."""

    def decorator(func: Callable) -> Callable:
        op_name = operation or f"{func.__module__}.{func.__name__}"
        return profile_performance(op_name)(func)

    return decorator


def observe_async_function(operation: Optional[str] = None):
    """Decorator for automatic async function observation."""

    def decorator(func: Callable) -> Callable:
        op_name = operation or f"{func.__module__}.{func.__name__}"
        return profile_performance(op_name)(func)

    return decorator


@asynccontextmanager
async def observe_operation(operation: str, **metadata):
    """Context manager for observing operations."""
    with trace_span(operation, attributes=metadata):
        with track_performance(operation):
            yield


# Utility functions


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID."""
    from .tracer import get_correlation_id

    return get_correlation_id()


def get_trace_headers() -> Dict[str, str]:
    """Get trace headers for propagation."""
    headers = {}
    trace_id = get_trace_id()
    if trace_id:
        headers["X-Trace-ID"] = trace_id

    correlation_id = get_correlation_id()
    if correlation_id:
        headers["X-Correlation-ID"] = correlation_id

    return headers


def log_business_event(event_type: str, message: str, **kwargs):
    """Log business events with context."""
    from .logging import log_business_event

    log_business_event(event_type, message, **kwargs)


def record_business_metric(metric_name: str, value: float, **labels):
    """Record business metrics."""
    from .metrics import record_histogram

    record_histogram(f"business_{metric_name}", value, labels)


# Performance optimization utilities


def optimize_database_connections():
    """Get database connection pool manager."""
    from .performance_optimization import connection_manager

    return connection_manager


def get_cache_manager():
    """Get cache manager."""
    from .performance_optimization import cache_manager

    return cache_manager


def get_performance_profiler():
    """Get performance profiler."""
    return get_profiler()


# Testing utilities


def get_performance_test_runner():
    """Get performance test runner."""
    return test_runner


def create_rag_test_suite(base_url: str):
    """Create RAG-specific test suite."""
    from .performance_testing import RAGPerformanceTestSuite

    return RAGPerformanceTestSuite(base_url)


# SLA monitoring utilities


def check_slo_compliance(slo_name: str) -> Dict[str, Any]:
    """Check SLO compliance status."""
    slo_monitor = get_slo_monitor()
    status = slo_monitor.get_slo_status(slo_name)

    if not status:
        return {"error": f"SLO '{slo_name}' not found"}

    return {
        "slo_name": slo_name,
        "status": status.status.value,
        "current_values": status.current_values,
        "last_evaluation": status.last_evaluation.isoformat()
        if status.last_evaluation
        else None,
        "compliant": status.status.value in ["compliant", "warning"],
    }


def get_all_slo_status() -> Dict[str, Any]:
    """Get status of all SLOs."""
    slo_monitor = get_slo_monitor()
    all_slos = slo_monitor.get_all_slo_status()

    return {
        slo_name: {
            "status": slo.status.value,
            "current_values": slo.current_values,
            "last_evaluation": slo.last_evaluation.isoformat()
            if slo.last_evaluation
            else None,
            "compliant": slo.status.value in ["compliant", "warning"],
        }
        for slo_name, slo in all_slos.items()
    }


# Initialization function
def initialize_observability():
    """Initialize observability (call this during application startup)."""
    return observability_manager.initialize()
