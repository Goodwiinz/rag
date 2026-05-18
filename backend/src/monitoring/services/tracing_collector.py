"""
Tracing Collector Service

Distributed tracing service using OpenTelemetry for collecting,
processing, and exporting trace data across the RAG system.
"""

import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.b3 import B3MultiFormat
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.semconv.resource import ResourceAttributes

from src.monitoring.models.tracing import (
    Span,
    SpanEvent,
    SpanKind,
    SpanLink,
    SpanStatus,
    Trace,
    TraceError,
)

from ..config.monitoring_config import TracingConfig
from ..utils.exceptions import TracingError

logger = logging.getLogger(__name__)


@dataclass
class SpanContext:
    """Context for active spans"""

    span_id: str
    trace_id: str
    parent_span_id: Optional[str]
    operation_name: str
    service_name: str
    component: Optional[str]
    start_time: datetime
    labels: Dict[str, str] = field(default_factory=dict)
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    links: List[Dict[str, Any]] = field(default_factory=list)


class TracingCollector:
    """
    Distributed tracing collector using OpenTelemetry

    Collects, processes, and exports trace data with support for
    multiple backends (Jaeger, OTLP) and automatic instrumentation.
    """

    def __init__(self, config: TracingConfig):
        """Initialize tracing collector"""
        self.config = config
        self._initialized = False
        self._running = False

        # OpenTelemetry components
        self._tracer_provider: Optional[TracerProvider] = None
        self._tracer: Optional[trace.Tracer] = None
        self._exporters: List[Any] = []

        # Active spans tracking
        self._active_spans: Dict[str, SpanContext] = {}
        self._spans_lock = asyncio.Lock()

        # Trace storage
        self._trace_buffer: List[Dict[str, Any]] = []
        self._buffer_lock = asyncio.Lock()

        # Background task
        self._processing_task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        """Initialize the tracing collector"""
        if self._initialized:
            return

        try:
            logger.info("Initializing tracing collector...")

            # Initialize OpenTelemetry
            await self._initialize_opentelemetry()

            # Setup automatic instrumentation
            if self.config.auto_instrumentation:
                await self._setup_auto_instrumentation()

            # Initialize span processors
            await self._initialize_exporters()

            self._initialized = True
            logger.info("✅ Tracing collector initialized")

        except Exception as e:
            logger.error(f"❌ Failed to initialize tracing collector: {e}")
            raise TracingError(f"Initialization failed: {e}")

    async def start(self) -> None:
        """Start tracing collection"""
        if not self._initialized:
            await self.initialize()

        if self._running:
            return

        try:
            logger.info("Starting tracing collector...")

            # Start background processing task
            self._processing_task = asyncio.create_task(self._processing_loop())

            self._running = True
            logger.info("✅ Tracing collector started")

        except Exception as e:
            logger.error(f"❌ Failed to start tracing collector: {e}")
            raise TracingError(f"Start failed: {e}")

    async def stop(self) -> None:
        """Stop tracing collection"""
        if not self._running:
            return

        try:
            logger.info("Stopping tracing collector...")

            # Cancel background task
            if self._processing_task:
                self._processing_task.cancel()
                try:
                    await self._processing_task
                except asyncio.CancelledError:
                    pass

            # Flush remaining traces
            await self._flush_traces()

            # Shutdown OpenTelemetry
            if self._tracer_provider:
                self._tracer_provider.shutdown()

            self._running = False
            logger.info("✅ Tracing collector stopped")

        except Exception as e:
            logger.error(f"❌ Error stopping tracing collector: {e}")

    async def cleanup(self) -> None:
        """Cleanup tracing collector resources"""
        await self.stop()
        self._active_spans.clear()
        self._trace_buffer.clear()
        self._exporters.clear()
        logger.info("✅ Tracing collector cleanup complete")

    async def start_span(
        self,
        operation_name: str,
        service: str,
        component: Optional[str] = None,
        parent_span: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> SpanContext:
        """
        Start a new span

        Args:
            operation_name: Name of the operation
            service: Service name
            component: Optional component name
            parent_span: Optional parent span ID
            labels: Optional span labels
            attributes: Optional span attributes

        Returns:
            Span context for the started span
        """
        if not self._running:
            raise TracingError("Tracing collector not running")

        try:
            # Generate span and trace IDs
            span_id = str(uuid.uuid4())
            trace_id = str(uuid.uuid4())

            # If parent span is provided, use its trace ID
            if parent_span:
                parent_context = self._active_spans.get(parent_span)
                if parent_context:
                    trace_id = parent_context.trace_id

            # Create span context
            span_context = SpanContext(
                span_id=span_id,
                trace_id=trace_id,
                parent_span_id=parent_span,
                operation_name=operation_name,
                service_name=service,
                component=component,
                start_time=datetime.utcnow(),
                labels=labels or {},
                attributes=attributes or {},
            )

            # Track active span
            async with self._spans_lock:
                self._active_spans[span_id] = span_context

            # Create OpenTelemetry span
            if self._tracer:
                otel_span = self._tracer.start_span(operation_name)
                span_context.otel_span = otel_span

            logger.debug(f"Started span: {operation_name} (ID: {span_id})")
            return span_context

        except Exception as e:
            logger.error(f"Error starting span {operation_name}: {e}")
            raise TracingError(f"Failed to start span: {e}")

    async def finish_span(
        self,
        span_context: SpanContext,
        status: str = SpanStatus.OK,
        error: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Finish a span

        Args:
            span_context: Span context to finish
            status: Span status
            error: Optional error message
            attributes: Optional additional attributes
        """
        if not self._running:
            return

        try:
            # Calculate duration
            end_time = datetime.utcnow()
            duration_ms = (end_time - span_context.start_time).total_seconds() * 1000

            # Update span context
            span_context.attributes.update(attributes or {})
            span_context.end_time = end_time
            span_context.duration_ms = duration_ms
            span_context.status = status
            span_context.error_message = error

            # Add error event if applicable
            if error:
                await self.add_span_event(
                    span_context,
                    "error",
                    {"exception.message": error, "exception.type": "Exception"},
                )

            # Convert to trace data
            trace_data = {
                "trace_id": span_context.trace_id,
                "span_id": span_context.span_id,
                "parent_span_id": span_context.parent_span_id,
                "operation_name": span_context.operation_name,
                "service_name": span_context.service_name,
                "component": span_context.component,
                "start_time": span_context.start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_ms": duration_ms,
                "status": status,
                "labels": span_context.labels,
                "attributes": span_context.attributes,
                "events": span_context.events,
                "links": span_context.links,
                "error_message": error,
            }

            # Add to buffer
            async with self._buffer_lock:
                self._trace_buffer.append(trace_data)

            # Remove from active spans
            async with self._spans_lock:
                self._active_spans.pop(span_context.span_id, None)

            # Finish OpenTelemetry span
            if hasattr(span_context, "otel_span") and span_context.otel_span:
                span_context.otel_span.end()

            logger.debug(
                f"Finished span: {span_context.operation_name} (ID: {span_context.span_id})"
            )

        except Exception as e:
            logger.error(f"Error finishing span {span_context.span_id}: {e}")

    async def add_span_event(
        self,
        span_context: SpanContext,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add an event to a span

        Args:
            span_context: Span context
            name: Event name
            attributes: Optional event attributes
        """
        try:
            event = {
                "name": name,
                "timestamp": datetime.utcnow().isoformat(),
                "attributes": attributes or {},
            }

            span_context.events.append(event)

            # Add to OpenTelemetry span
            if hasattr(span_context, "otel_span") and span_context.otel_span:
                span_context.otel_span.add_event(name, attributes or {})

        except Exception as e:
            logger.error(f"Error adding event to span {span_context.span_id}: {e}")

    async def add_span_link(
        self,
        span_context: SpanContext,
        linked_trace_id: str,
        linked_span_id: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add a link to another span

        Args:
            span_context: Span context
            linked_trace_id: ID of linked trace
            linked_span_id: ID of linked span
            attributes: Optional link attributes
        """
        try:
            link = {
                "linked_trace_id": linked_trace_id,
                "linked_span_id": linked_span_id,
                "attributes": attributes or {},
            }

            span_context.links.append(link)

        except Exception as e:
            logger.error(f"Error adding link to span {span_context.span_id}: {e}")

    @asynccontextmanager
    async def trace_operation(
        self,
        operation_name: str,
        service: str,
        component: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        """
        Context manager for tracing operations

        Args:
            operation_name: Name of the operation
            service: Service name
            component: Optional component name
            labels: Optional span labels
            attributes: Optional span attributes
        """
        span_context = None
        try:
            span_context = await self.start_span(
                operation_name=operation_name,
                service=service,
                component=component,
                labels=labels,
                attributes=attributes,
            )
            yield span_context
            await self.finish_span(span_context, status=SpanStatus.OK)
        except Exception as e:
            if span_context:
                await self.finish_span(
                    span_context, status=SpanStatus.ERROR, error=str(e)
                )
            raise

    async def get_traces(
        self,
        trace_id: Optional[str] = None,
        service: Optional[str] = None,
        operation: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Get traces data

        Args:
            trace_id: Optional trace ID filter
            service: Optional service filter
            operation: Optional operation filter
            start_time: Optional start time filter
            end_time: Optional end time filter
            limit: Maximum number of traces to return

        Returns:
            Dictionary containing trace data
        """
        try:
            # Default time range to last hour if not specified
            if not end_time:
                end_time = datetime.utcnow()
            if not start_time:
                start_time = end_time - timedelta(hours=1)

            # Filter traces from buffer
            async with self._buffer_lock:
                filtered_traces = [
                    trace
                    for trace in self._trace_buffer
                    if start_time
                    <= datetime.fromisoformat(trace["start_time"])
                    <= end_time
                ]

            # Apply filters
            if trace_id:
                filtered_traces = [
                    t for t in filtered_traces if t["trace_id"] == trace_id
                ]

            if service:
                filtered_traces = [
                    t for t in filtered_traces if t["service_name"] == service
                ]

            if operation:
                filtered_traces = [
                    t for t in filtered_traces if t["operation_name"] == operation
                ]

            # Group by trace ID
            traces_by_id = {}
            for span_data in filtered_traces:
                if span_data["trace_id"] not in traces_by_id:
                    traces_by_id[span_data["trace_id"]] = {
                        "trace_id": span_data["trace_id"],
                        "spans": [],
                        "start_time": span_data["start_time"],
                        "end_time": span_data["end_time"],
                        "duration_ms": span_data["duration_ms"],
                        "service_name": span_data["service_name"],
                        "status": span_data["status"],
                    }
                traces_by_id[span_data["trace_id"]]["spans"].append(span_data)

            # Limit results
            trace_ids = list(traces_by_id.keys())[:limit]
            result = {tid: traces_by_id[tid] for tid in trace_ids}

            return {
                "traces": result,
                "count": len(result),
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "filters": {
                    "trace_id": trace_id,
                    "service": service,
                    "operation": operation,
                },
            }

        except Exception as e:
            logger.error(f"Error getting traces: {e}")
            raise TracingError(f"Failed to get traces: {e}")

    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the tracing collector"""
        return {
            "initialized": self._initialized,
            "running": self._running,
            "auto_instrumentation": self.config.auto_instrumentation,
            "sampling_ratio": self.config.sampling_ratio,
            "active_spans_count": len(self._active_spans),
            "buffer_size": len(self._trace_buffer),
            "exporters_count": len(self._exporters),
            "jaeger_enabled": self.config.jaeger_enabled,
            "otlp_enabled": self.config.otlp_enabled,
            "status": "healthy" if self._running else "stopped",
        }

    async def _initialize_opentelemetry(self) -> None:
        """Initialize OpenTelemetry components"""
        try:
            # Create resource with service information
            resource = Resource.create(
                {
                    ResourceAttributes.SERVICE_NAME: self.config.service_name,
                    ResourceAttributes.SERVICE_VERSION: self.config.service_version,
                    "environment": self.config.service_name,
                }
            )

            # Create tracer provider
            self._tracer_provider = TracerProvider(resource=resource)
            trace.set_tracer_provider(self._tracer_provider)

            # Create tracer
            self._tracer = self._tracer_provider.get_tracer(__name__)

            # Set global propagator
            if self.config.trace_parent_span:
                set_global_textmap(B3MultiFormat())

            logger.info("✅ OpenTelemetry initialized")

        except Exception as e:
            logger.error(f"❌ Failed to initialize OpenTelemetry: {e}")
            raise

    async def _setup_auto_instrumentation(self) -> None:
        """Setup automatic instrumentation"""
        try:
            if self.config.instrument_fastapi:
                FastAPIInstrumentor.instrument()
                logger.debug("✅ FastAPI instrumentation enabled")

            if self.config.instrument_sqlalchemy:
                SQLAlchemyInstrumentor.instrument()
                logger.debug("✅ SQLAlchemy instrumentation enabled")

            if self.config.instrument_redis:
                RedisInstrumentor.instrument()
                logger.debug("✅ Redis instrumentation enabled")

            if self.config.instrument_httpx:
                HTTPXClientInstrumentor.instrument()
                logger.debug("✅ HTTPX instrumentation enabled")

        except Exception as e:
            logger.error(f"❌ Failed to setup auto-instrumentation: {e}")
            # Don't raise error as auto-instrumentation is optional

    async def _initialize_exporters(self) -> None:
        """Initialize trace exporters"""
        try:
            # Jaeger native exporter was dropped from opentelemetry-python in
            # 1.35; Jaeger 1.35+ ingests OTLP directly. Point OTLP at the
            # Jaeger collector's :4317 port to keep Jaeger working.
            if self.config.jaeger_enabled and not self.config.otlp_enabled:
                logger.warning(
                    "jaeger_enabled=true without otlp_enabled — Jaeger native "
                    "exporter is removed. Enable OTLP and point "
                    "otlp_endpoint at the Jaeger collector :4317."
                )

            # OTLP exporter
            if self.config.otlp_enabled:
                otlp_exporter = OTLPSpanExporter(
                    endpoint=self.config.otlp_endpoint, headers=self.config.otlp_headers
                )
                span_processor = BatchSpanProcessor(otlp_exporter)
                self._tracer_provider.add_span_processor(span_processor)
                self._exporters.append(otlp_exporter)
                logger.info("✅ OTLP exporter initialized")

        except Exception as e:
            logger.error(f"❌ Failed to initialize exporters: {e}")
            raise

    async def _processing_loop(self) -> None:
        """Background loop for processing traces"""
        while self._running:
            try:
                # Process buffered traces
                await self._flush_traces()

                # Clean up old active spans (those older than 1 hour)
                await self._cleanup_old_spans()

                await asyncio.sleep(30)  # Process every 30 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in trace processing loop: {e}")
                await asyncio.sleep(60)

    async def _flush_traces(self) -> None:
        """Flush buffered traces to storage"""
        async with self._buffer_lock:
            if not self._trace_buffer:
                return

            traces_to_process = self._trace_buffer.copy()
            self._trace_buffer.clear()

        # Process traces (in a real implementation, this would store to database)
        for trace_data in traces_to_process:
            try:
                # Store trace to database or other storage
                # This is where you'd implement the actual storage logic
                pass
            except Exception as e:
                logger.error(f"Error processing trace {trace_data['trace_id']}: {e}")

        if traces_to_process:
            logger.debug(f"Processed {len(traces_to_process)} traces")

    async def _cleanup_old_spans(self) -> None:
        """Clean up old active spans"""
        cutoff_time = datetime.utcnow() - timedelta(hours=1)

        async with self._spans_lock:
            old_spans = [
                span_id
                for span_id, span_context in self._active_spans.items()
                if span_context.start_time < cutoff_time
            ]

            for span_id in old_spans:
                span_context = self._active_spans.pop(span_id, None)
                if span_context:
                    logger.warning(
                        f"Cleaning up abandoned span: {span_context.operation_name} (ID: {span_id})"
                    )
                    # Finish the span as timed out
                    await self.finish_span(
                        span_context, status=SpanStatus.TIMEOUT, error="Span timed out"
                    )

        if old_spans:
            logger.debug(f"Cleaned up {len(old_spans)} old spans")
