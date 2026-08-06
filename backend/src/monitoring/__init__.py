"""
Monitoring and Observability Services

This package provides comprehensive monitoring, observability, and alerting
capabilities for the Multimodal Enterprise RAG System.

Components:
- Models: Database models for monitoring data
- Services: Core monitoring services (metrics, tracing, logging, alerts, health)
- API: FastAPI endpoints and WebSocket handlers
- Middleware: Observability middleware for automatic instrumentation
- Tasks: Background tasks for metrics collection and processing
- Utils: Utility functions for monitoring
- Config: Configuration management for monitoring services
"""

__version__ = "1.0.0"
__author__ = "RAG System Team"

from .services.alert_handler import AlertHandler
from .services.health_check_hub import HealthCheckHub
from .services.log_aggregator import LogAggregator
from .services.metrics_collector import MetricsCollector
from .services.observability_manager import ObservabilityManager
from .services.tracing_collector import TracingCollector

__all__ = [
    "ObservabilityManager",
    "MetricsCollector",
    "TracingCollector",
    "LogAggregator",
    "AlertHandler",
    "HealthCheckHub",
]
