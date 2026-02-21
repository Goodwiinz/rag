"""
OpenTelemetry Integration for Knowledge Graph Analytics Dashboard
Distributed tracing and comprehensive observability across all services
"""

import asyncio
import logging
import os
import time
import uuid
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

from opentelemetry import baggage, context, metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.metrics import Counter, Histogram, ObservableGauge, UpDownCounter
from opentelemetry.propagate import set_global_textmap
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import SpanKind, Status, StatusCode

from src.config.settings import settings

logger = logging.getLogger(__name__)


class OpenTelemetryManager:
    """Centralized OpenTelemetry management for the application"""

    def __init__(self):
        self._initialized = False
        self._tracer_provider: Optional[TracerProvider] = None
        self._meter_provider: Optional[MeterProvider] = None
        self._meters: Dict[str, Any] = {}
        self._tracers: Dict[str, Any] = {}
        self._metrics: Dict[str, Any] = {}

    def initialize(self) -> None:
        """Initialize OpenTelemetry with comprehensive configuration"""
        if self._initialized:
            return

        try:
            # Configure resource with comprehensive metadata
            resource = Resource.create(
                {
                    "service.name": settings.SERVICE_NAME
                    or "knowledge-graph-analytics",
                    "service.version": settings.VERSION or "1.0.0",
                    "service.instance.id": str(uuid.uuid4()),
                    "environment": settings.ENVIRONMENT or "development",
                    "deployment.zone": os.environ.get("POD_ZONE", "unknown"),
                    "k8s.pod.name": os.environ.get("POD_NAME", "unknown"),
                    "k8s.namespace.name": os.environ.get("POD_NAMESPACE", "unknown"),
                    "k8s.node.name": os.environ.get("NODE_NAME", "unknown"),
                    "host.name": os.environ.get("HOSTNAME", "unknown"),
                }
            )

            # Initialize tracing
            self._setup_tracing(resource)

            # Initialize metrics
            self._setup_metrics(resource)

            # Set up context propagation
            set_global_textmap({})

            # Initialize instrumentation libraries
            self._setup_instrumentation()

            self._initialized = True
            logger.info("OpenTelemetry initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize OpenTelemetry: {e}")
            raise

    def _setup_tracing(self, resource: Resource) -> None:
        """Set up distributed tracing"""
        # Configure OTLP span exporter
        otlp_endpoint = os.environ.get(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"
        )
        span_exporter = OTLPSpanExporter(
            endpoint=otlp_endpoint, insecure=True, timeout=30
        )

        # Configure tracer provider
        self._tracer_provider = TracerProvider(resource=resource)

        # Add batch span processor for efficient export
        batch_processor = BatchSpanProcessor(
            span_exporter,
            max_queue_size=2048,
            max_export_batch_size=512,
            export_timeout_millis=30000,
            max_export_batch_size_millis=5000,
        )
        self._tracer_provider.add_span_processor(batch_processor)

        # Set global tracer provider
        trace.set_tracer_provider(self._tracer_provider)

        # Create application tracer
        self._tracers["app"] = trace.get_tracer(__name__)
        self._tracers["api"] = trace.get_tracer("api")
        self._tracers["database"] = trace.get_tracer("database")
        self._tracers["cache"] = trace.get_tracer("cache")
        self._tracers["search"] = trace.get_tracer("search")
        self._tracers["ml"] = trace.get_tracer("ml")

    def _setup_metrics(self, resource: Resource) -> None:
        """Set up metrics collection"""
        # Configure OTLP metric exporter
        otlp_endpoint = os.environ.get(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"
        )
        metric_exporter = OTLPMetricExporter(
            endpoint=otlp_endpoint, insecure=True, timeout=30
        )

        # Configure periodic metric reader
        metric_reader = PeriodicExportingMetricReader(
            exporter=metric_exporter,
            export_interval_millis=15000,  # Export every 15 seconds
            export_timeout_millis=30000,
        )

        # Configure meter provider
        self._meter_provider = MeterProvider(
            resource=resource, metric_readers=[metric_reader]
        )

        # Set global meter provider
        metrics.set_meter_provider(self._meter_provider)

        # Create meters for different components
        self._meters["app"] = metrics.get_meter("app")
        self._meters["api"] = metrics.get_meter("api")
        self._meters["database"] = metrics.get_meter("database")
        self._meters["cache"] = metrics.get_meter("cache")
        self._meters["search"] = metrics.get_meter("search")
        self._meters["ml"] = metrics.get_meter("ml")

        # Initialize custom metrics
        self._setup_custom_metrics()

    def _setup_custom_metrics(self) -> None:
        """Set up application-specific metrics"""
        # Application metrics
        app_meter = self._meters["app"]
        self._metrics["app.request_duration"] = app_meter.create_histogram(
            "app_request_duration_seconds",
            description="Application request duration in seconds",
            unit="s",
        )
        self._metrics["app.request_count"] = app_meter.create_counter(
            "app_requests_total",
            description="Total number of application requests",
            unit="1",
        )
        self._metrics["app.active_requests"] = app_meter.create_up_down_counter(
            "app_active_requests", description="Number of active requests", unit="1"
        )

        # API metrics
        api_meter = self._meters["api"]
        self._metrics["api.http.request_duration"] = api_meter.create_histogram(
            "http_server_request_duration_seconds",
            description="HTTP request duration",
            unit="s",
        )
        self._metrics["api.http.request_count"] = api_meter.create_counter(
            "http_server_requests_total", description="Total HTTP requests", unit="1"
        )

        # Database metrics
        db_meter = self._meters["database"]
        self._metrics["db.query.duration"] = db_meter.create_histogram(
            "db_query_duration_seconds", description="Database query duration", unit="s"
        )
        self._metrics["db.query.count"] = db_meter.create_counter(
            "db_queries_total", description="Total database queries", unit="1"
        )
        self._metrics["db.connections.active"] = db_meter.create_up_down_counter(
            "db_connections_active", description="Active database connections", unit="1"
        )

        # Cache metrics
        cache_meter = self._meters["cache"]
        self._metrics["cache.hit_rate"] = cache_meter.create_histogram(
            "cache_hit_rate", description="Cache hit rate", unit="1"
        )
        self._metrics["cache.operations"] = cache_meter.create_counter(
            "cache_operations_total", description="Total cache operations", unit="1"
        )

        # Search metrics
        search_meter = self._meters["search"]
        self._metrics["search.query.duration"] = search_meter.create_histogram(
            "search_query_duration_seconds",
            description="Search query duration",
            unit="s",
        )
        self._metrics["search.results.count"] = search_meter.create_histogram(
            "search_results_count", description="Number of search results", unit="1"
        )

        # ML/AI metrics
        ml_meter = self._meters["ml"]
        self._metrics["ml.inference.duration"] = ml_meter.create_histogram(
            "ml_inference_duration_seconds",
            description="ML inference duration",
            unit="s",
        )
        self._metrics["ml.model.requests"] = ml_meter.create_counter(
            "ml_model_requests_total", description="Total ML model requests", unit="1"
        )
        self._metrics["ml.model.errors"] = ml_meter.create_counter(
            "ml_model_errors_total", description="Total ML model errors", unit="1"
        )

    def _setup_instrumentation(self) -> None:
        """Set up automatic instrumentation for common libraries"""
        try:
            # FastAPI instrumentation
            FastAPIInstrumentor.instrument(
                tracer_provider=self._tracer_provider,
                meter_provider=self._meter_provider,
                excluded_urls="/health,/metrics,/ready",
            )
        except Exception as e:
            logger.warning(f"FastAPI instrumentation failed: {e}")

        try:
            # SQLAlchemy instrumentation
            SQLAlchemyInstrumentor.instrument(
                tracer_provider=self._tracer_provider,
                meter_provider=self._meter_provider,
            )
        except Exception as e:
            logger.warning(f"SQLAlchemy instrumentation failed: {e}")

        try:
            # Redis instrumentation
            RedisInstrumentor.instrument(
                tracer_provider=self._tracer_provider,
                meter_provider=self._meter_provider,
            )
        except Exception as e:
            logger.warning(f"Redis instrumentation failed: {e}")

        try:
            # HTTPX instrumentation
            HTTPXClientInstrumentor.instrument(
                tracer_provider=self._tracer_provider,
                meter_provider=self._meter_provider,
            )
        except Exception as e:
            logger.warning(f"HTTPX instrumentation failed: {e}")

        try:
            # aiohttp client instrumentation
            AioHttpClientInstrumentor.instrument(
                tracer_provider=self._tracer_provider,
                meter_provider=self._meter_provider,
            )
        except Exception as e:
            logger.warning(f"aiohttp instrumentation failed: {e}")

        try:
            # asyncpg instrumentation
            AsyncPGInstrumentor.instrument(
                tracer_provider=self._tracer_provider,
                meter_provider=self._meter_provider,
            )
        except Exception as e:
            logger.warning(f"asyncpg instrumentation failed: {e}")

    def get_tracer(self, name: str = "app") -> trace.Tracer:
        """Get a tracer for the specified component"""
        if not self._initialized:
            self.initialize()
        return self._tracers.get(name, self._tracers["app"])

    def get_meter(self, name: str = "app") -> metrics.Meter:
        """Get a meter for the specified component"""
        if not self._initialized:
            self.initialize()
        return self._meters.get(name, self._meters["app"])

    def get_metric(self, name: str):
        """Get a specific metric by name"""
        if not self._initialized:
            self.initialize()
        return self._metrics.get(name)

    def record_metric(
        self, name: str, value: float, attributes: Optional[Dict[str, Any]] = None
    ):
        """Record a metric value"""
        metric = self.get_metric(name)
        if metric:
            metric.record(value, attributes or {})

    def increment_counter(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Increment a counter metric"""
        metric = self.get_metric(name)
        if metric:
            metric.add(1, attributes or {})

    def decrement_counter(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Decrement a counter metric"""
        metric = self.get_metric(name)
        if metric:
            metric.add(-1, attributes or {})

    def create_span(
        self, name: str, kind: "SpanKind" = SpanKind.INTERNAL
    ) -> context.Context:
        """Create a new span"""
        tracer = self.get_tracer()
        return tracer.start_span(name, kind=kind)

    def add_span_event(self, name: str, attributes: Dict[str, Any]):
        """Add an event to the current span"""
        span = trace.get_current_span()
        if span:
            span.add_event(name, attributes)

    def set_span_attribute(self, key: str, value: Any):
        """Set an attribute on the current span"""
        span = trace.get_current_span()
        if span:
            span.set_attribute(key, value)

    def set_span_status(self, status: StatusCode, description: Optional[str] = None):
        """Set the status of the current span"""
        span = trace.get_current_span()
        if span:
            span.set_status(Status(status, description))

    def shutdown(self) -> None:
        """Gracefully shutdown OpenTelemetry"""
        if self._tracer_provider:
            self._tracer_provider.shutdown()
        if self._meter_provider:
            self._meter_provider.shutdown()
        logger.info("OpenTelemetry shutdown completed")


# Global instance
otel_manager = OpenTelemetryManager()


# Decorators for easy tracing and metrics
def trace_span(
    span_name: str = None, kind: "SpanKind" = SpanKind.INTERNAL, component: str = "app"
):
    """Decorator to automatically trace function execution"""

    def decorator(func: Callable):
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            tracer = otel_manager.get_tracer(component)
            name = span_name or f"{func.__module__}.{func.__name__}"

            with tracer.start_as_current_span(name, kind=kind) as span:
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)
                span.set_attribute("function.args_count", len(args))

                try:
                    start_time = time.time()
                    result = func(*args, **kwargs)
                    duration = time.time() - start_time

                    span.set_attribute("execution.duration", duration)
                    span.set_status(StatusCode.OK)

                    # Record duration metric
                    otel_manager.record_metric(
                        f"{component}.function.duration",
                        duration,
                        {"function": func.__name__, "status": "success"},
                    )

                    return result
                except Exception as e:
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    span.set_status(StatusCode.ERROR, str(e))

                    # Record error metric
                    otel_manager.increment_counter(
                        f"{component}.function.errors",
                        {"function": func.__name__, "error_type": type(e).__name__},
                    )

                    raise

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracer = otel_manager.get_tracer(component)
            name = span_name or f"{func.__module__}.{func.__name__}"

            with tracer.start_as_current_span(name, kind=kind) as span:
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)
                span.set_attribute("function.args_count", len(args))
                span.set_attribute("function.is_async", True)

                try:
                    start_time = time.time()
                    result = await func(*args, **kwargs)
                    duration = time.time() - start_time

                    span.set_attribute("execution.duration", duration)
                    span.set_status(StatusCode.OK)

                    # Record duration metric
                    otel_manager.record_metric(
                        f"{component}.function.duration",
                        duration,
                        {"function": func.__name__, "status": "success"},
                    )

                    return result
                except Exception as e:
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    span.set_status(StatusCode.ERROR, str(e))

                    # Record error metric
                    otel_manager.increment_counter(
                        f"{component}.function.errors",
                        {"function": func.__name__, "error_type": type(e).__name__},
                    )

                    raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


def trace_api_endpoint(endpoint_name: str = None):
    """Decorator specifically for API endpoints"""
    return trace_span(span_name=endpoint_name, kind=SpanKind.SERVER, component="api")


def trace_database_operation(operation_name: str = None):
    """Decorator specifically for database operations"""
    return trace_span(
        span_name=operation_name, kind=SpanKind.CLIENT, component="database"
    )


def trace_cache_operation(operation_name: str = None):
    """Decorator specifically for cache operations"""
    return trace_span(span_name=operation_name, kind=SpanKind.CLIENT, component="cache")


def trace_search_query(query_name: str = None):
    """Decorator specifically for search queries"""
    return trace_span(span_name=query_name, kind=SpanKind.SERVER, component="search")


def trace_ml_inference(model_name: str = None):
    """Decorator specifically for ML inference"""
    return trace_span(span_name=model_name, kind=SpanKind.SERVER, component="ml")


@contextmanager
def trace_context(
    span_name: str,
    kind: "SpanKind" = SpanKind.INTERNAL,
    component: str = "app",
    attributes: Optional[Dict[str, Any]] = None,
):
    """Context manager for manual tracing"""
    tracer = otel_manager.get_tracer(component)

    with tracer.start_as_current_span(span_name, kind=kind) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)

        try:
            yield span
            span.set_status(StatusCode.OK)
        except Exception as e:
            span.set_attribute("error.type", type(e).__name__)
            span.set_attribute("error.message", str(e))
            span.set_status(StatusCode.ERROR, str(e))
            raise


def get_trace_id() -> Optional[str]:
    """Get the current trace ID"""
    span = trace.get_current_span()
    if span and span.get_span_context():
        return format(span.get_span_context().trace_id, "032x")
    return None


def get_span_id() -> Optional[str]:
    """Get the current span ID"""
    span = trace.get_current_span()
    if span and span.get_span_context():
        return format(span.get_span_context().span_id, "016x")
    return None


def inject_headers(headers: Dict[str, str]) -> None:
    """Inject tracing context into HTTP headers"""
    carrier = {}
    trace.get_current_span().inject(carrier)
    headers.update(carrier)


def extract_headers(headers: Dict[str, str]) -> context.Context:
    """Extract tracing context from HTTP headers"""
    carrier = headers
    return trace.get_current_span().extract(carrier)
