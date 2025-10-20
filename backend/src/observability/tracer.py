"""
OpenTelemetry tracing configuration for distributed tracing

Provides comprehensive distributed tracing capabilities including:
- Automatic span creation for HTTP requests
- Manual span instrumentation for business logic
- Database operation tracing
- Service-to-service call tracing
- Trace context propagation
- Custom span attributes and events
"""

import os
import time
import uuid
from typing import Optional, Dict, Any, Callable
from functools import wraps
from contextlib import contextmanager, asynccontextmanager

try:
    from opentelemetry import trace, baggage, context
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION, DEPLOYMENT_ENVIRONMENT
    from opentelemetry.propagators.b3 import B3MultiFormat
    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
    # Create dummy objects for when opentelemetry is not available
    trace = None
    baggage = None
    context = None
from opentelemetry.propagators.jaeger import JaegerPropagator
from opentelemetry.trace import Status, StatusCode, SpanKind
from opentelemetry.trace.propagation import get_current_span

from ..core.config import settings


# Global tracer instance
_tracer = None


def configure_tracing() -> trace.Tracer:
    """Configure OpenTelemetry tracing with Jaeger and OTLP exporters"""
    global _tracer

    # Set up trace provider with resource attributes
    resource = Resource.create({
        SERVICE_NAME: "rag-system-backend",
        SERVICE_VERSION: settings.VERSION,
        DEPLOYMENT_ENVIRONMENT: settings.ENVIRONMENT,
        "service.instance.id": os.environ.get("HOSTNAME", "unknown"),
        "service.namespace": "rag-system",
    })

    # Create tracer provider
    trace_provider = TracerProvider(resource=resource)

    # Configure Jaeger exporter
    jaeger_endpoint = os.environ.get("JAEGER_ENDPOINT", "http://jaeger:14268/api/traces")
    jaeger_exporter = JaegerExporter(
        endpoint=jaeger_endpoint,
        collector_endpoint=jaeger_endpoint,
        agent_host_name=os.environ.get("JAEGER_AGENT_HOST", "jaeger"),
        agent_port=int(os.environ.get("JAEGER_AGENT_PORT", "6831")),
    )

    # Configure OTLP exporter (for Grafana Tempo or other OTLP-compatible backends)
    otlp_endpoint = os.environ.get("OTLP_ENDPOINT", "http://tempo:4317")
    otlp_exporter = OTLPSpanExporter(
        endpoint=otlp_endpoint,
        insecure=True,  # Set to False with proper certificates in production
    )

    # Add exporters with batch processing
    trace_provider.add_span_processor(
        BatchSpanProcessor(jaeger_exporter, max_export_batch_size=512, export_timeout_millis=30000)
    )
    trace_provider.add_span_processor(
        BatchSpanProcessor(otlp_exporter, max_export_batch_size=512, export_timeout_millis=30000)
    )

    # Set as global tracer provider
    trace.set_tracer_provider(trace_provider)

    # Configure propagators
    from opentelemetry import propagators
    propagators.set_global_textmap(B3MultiFormat())

    # Create and store tracer
    _tracer = trace_provider.get_tracer(__name__)

    return _tracer


def get_tracer(name: Optional[str] = None) -> trace.Tracer:
    """Get a tracer instance"""
    if _tracer is None:
        configure_tracing()

    if name:
        return trace.get_tracer(name)
    return _tracer


@contextmanager
def trace_span(
    name: str,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: Optional[Dict[str, Any]] = None,
    status: Optional[Status] = None
):
    """Context manager for creating spans"""
    tracer = get_tracer()

    with tracer.start_as_current_span(name, kind=kind) as span:
        # Add attributes if provided
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)

        # Set status if provided
        if status:
            span.set_status(status)

        yield span


@asynccontextmanager
async def async_trace_span(
    name: str,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: Optional[Dict[str, Any]] = None,
    status: Optional[Status] = None
):
    """Async context manager for creating spans"""
    tracer = get_tracer()

    with tracer.start_as_current_span(name, kind=kind) as span:
        # Add attributes if provided
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)

        # Set status if provided
        if status:
            span.set_status(status)

        yield span


def trace_function(
    name: Optional[str] = None,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: Optional[Dict[str, Any]] = None,
    record_exception: bool = True
):
    """Decorator for tracing function execution"""
    def decorator(func: Callable):
        span_name = name or f"{func.__module__}.{func.__name__}"

        @wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()

            with tracer.start_as_current_span(span_name, kind=kind) as span:
                # Add function attributes
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)

                # Add custom attributes
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)

                try:
                    # Execute function
                    start_time = time.time()
                    result = func(*args, **kwargs)
                    execution_time = time.time() - start_time

                    # Add execution metrics
                    span.set_attribute("function.execution_time", execution_time)
                    span.set_status(Status(StatusCode.OK))

                    return result

                except Exception as e:
                    # Record exception if enabled
                    if record_exception:
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                    else:
                        span.set_status(Status(StatusCode.ERROR))

                    raise

        return wrapper

    return decorator


def trace_async_function(
    name: Optional[str] = None,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: Optional[Dict[str, Any]] = None,
    record_exception: bool = True
):
    """Decorator for tracing async function execution"""
    def decorator(func: Callable):
        span_name = name or f"{func.__module__}.{func.__name__}"

        @wraps(func)
        async def wrapper(*args, **kwargs):
            tracer = get_tracer()

            with tracer.start_as_current_span(span_name, kind=kind) as span:
                # Add function attributes
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)

                # Add custom attributes
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)

                try:
                    # Execute async function
                    start_time = time.time()
                    result = await func(*args, **kwargs)
                    execution_time = time.time() - start_time

                    # Add execution metrics
                    span.set_attribute("function.execution_time", execution_time)
                    span.set_status(Status(StatusCode.OK))

                    return result

                except Exception as e:
                    # Record exception if enabled
                    if record_exception:
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                    else:
                        span.set_status(Status(StatusCode.ERROR))

                    raise

        return wrapper

    return decorator


def add_span_event(name: str, attributes: Optional[Dict[str, Any]] = None):
    """Add an event to the current span"""
    span = get_current_span()
    if span:
        span.add_event(name, attributes or {})


def set_span_attribute(key: str, value: Any):
    """Set an attribute on the current span"""
    span = get_current_span()
    if span:
        span.set_attribute(key, value)


def get_trace_id() -> Optional[str]:
    """Get the current trace ID"""
    span = get_current_span()
    if span:
        return format(span.get_span_context().trace_id, "032x")
    return None


def get_span_id() -> Optional[str]:
    """Get the current span ID"""
    span = get_current_span()
    if span:
        return format(span.get_span_context().span_id, "016x")
    return None


def generate_correlation_id() -> str:
    """Generate a new correlation ID"""
    return str(uuid.uuid4())


def set_correlation_id(correlation_id: str):
    """Set correlation ID in baggage and span attributes"""
    # Set in baggage for propagation
    baggage.set_baggage("correlation_id", correlation_id)

    # Set as span attribute
    set_span_attribute("correlation_id", correlation_id)


def get_correlation_id() -> Optional[str]:
    """Get correlation ID from baggage or generate new one"""
    correlation_id = baggage.get_baggage("correlation_id")
    if not correlation_id:
        correlation_id = generate_correlation_id()
        set_correlation_id(correlation_id)
    return correlation_id