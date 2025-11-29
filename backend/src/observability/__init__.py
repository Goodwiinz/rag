"""
Observability module for the Multimodal Enterprise RAG System

This module provides comprehensive observability capabilities including:
- Distributed tracing with OpenTelemetry
- Metrics collection and custom business metrics
- Structured logging with correlation
- Performance monitoring and alerting
- APM integration and health checks
"""

from .config import config, ObservabilityConfig
from .tracer import configure_tracing, get_tracer, trace_span, trace_function
from .metrics import (
    configure_metrics, get_meter, track_performance,
    record_rag_metrics, record_search_metrics, record_file_processing_metrics
)
from .logging import configure_logging, get_logger, correlation_context
from .slo_monitoring import (
    get_slo_monitor, record_slo_metrics, evaluate_slos,
    SLOStatus, AlertSeverity
)

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

    # SLO Monitoring
    "get_slo_monitor",
    "record_slo_metrics",
    "evaluate_slos",
    "SLOStatus",
    "AlertSeverity",
]