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

from .config import config


# Global tracer instance
_tracer = None


def configure_tracing() -> trace.Tracer:
    """Configure OpenTelemetry tracing with Jaeger and OTLP exporters"""
    global _tracer

    # Set up trace provider with resource attributes
    resource = Resource.create({
        SERVICE_NAME: config.otel_service_name,
        SERVICE_VERSION: config.otel_service_version,
        DEPLOYMENT_ENVIRONMENT: config.otel_environment,
        "service.instance.id": os.environ.get("HOSTNAME", "unknown"),
        "service.namespace": "multimodal-rag",
    })

    # Create tracer provider
    trace_provider = TracerProvider(resource=resource)

    # Configure Jaeger exporter
    jaeger_exporter = JaegerExporter(
        **config.get_jaeger_config()
    )

    # Configure OTLP exporter
    otlp_exporter = OTLPSpanExporter(
        endpoint=config.otel_exporter_otlp_endpoint,
        insecure=True,
    )

    # Add exporters with batch processing
    trace_provider.add_span_processor(
        BatchSpanProcessor(jaeger_exporter,
                          max_export_batch_size=config.otel_max_export_batch_size,
                          export_timeout_millis=config.otel_batch_timeout)
    )
    trace_provider.add_span_processor(
        BatchSpanProcessor(otlp_exporter,
                          max_export_batch_size=config.otel_max_export_batch_size,
                          export_timeout_millis=config.otel_batch_timeout)
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