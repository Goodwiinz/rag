"""
Observability module for the Multimodal Enterprise RAG System

This module provides comprehensive observability capabilities including:
- Distributed tracing with OpenTelemetry
- Metrics collection and custom business metrics
- Structured logging with correlation
- Performance monitoring and alerting
- APM integration and health checks
"""

from .tracer import configure_tracing, get_tracer
from .metrics import configure_metrics, get_meter, create_metrics
from .logging import configure_logging, get_logger, correlation_context
from .monitoring import health_check, performance_monitor
from .instrumentation import instrument_app, instrument_services

__all__ = [
    "configure_tracing",
    "get_tracer",
    "configure_metrics",
    "get_meter",
    "create_metrics",
    "configure_logging",
    "get_logger",
    "correlation_context",
    "health_check",
    "performance_monitor",
    "instrument_app",
    "instrument_services",
]