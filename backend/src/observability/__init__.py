"""
Observability module for the Multimodal Enterprise RAG System

This module provides comprehensive observability capabilities including:
- Distributed tracing with OpenTelemetry
- Metrics collection and custom business metrics
- Structured logging with correlation
- Performance monitoring and alerting
- APM integration and health checks
"""

from .config import ObservabilityConfig, config
from .logging import configure_logging, correlation_context, get_logger
from .sentry import init_sentry
from .metrics import (
    configure_metrics,
    get_meter,
    record_file_processing_metrics,
    record_rag_metrics,
    record_search_metrics,
    track_performance,
)
from .slo_monitoring import (
    AlertSeverity,
    SLOStatus,
    evaluate_slos,
    get_slo_monitor,
    record_slo_metrics,
)
from .tracer import configure_tracing, get_tracer, trace_function, trace_span

__all__ = [
    # Configuration
    "config",
    "ObservabilityConfig",
    # Tracing
    "configure_tracing",
    "get_tracer",
    "trace_span",
    "trace_function",
    # Metrics
    "configure_metrics",
    "get_meter",
    "track_performance",
    "record_rag_metrics",
    "record_search_metrics",
    "record_file_processing_metrics",
    # Logging
    "configure_logging",
    "get_logger",
    "correlation_context",
    # Sentry
    "init_sentry",
    # SLO Monitoring
    "get_slo_monitor",
    "record_slo_metrics",
    "evaluate_slos",
    "SLOStatus",
    "AlertSeverity",
]
