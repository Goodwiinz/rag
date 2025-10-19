"""
Structured logging configuration with correlation and observability integration

Provides comprehensive logging capabilities including:
- Structured JSON logging for machine readability
- Correlation ID tracking across services
- OpenTelemetry trace and span ID integration
- Log level management and filtering
- Log enrichment with context
- Security event logging
- Performance metric logging
"""

import os
import json
import logging
import time
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
from contextlib import contextmanager
from contextvars import ContextVar

import structlog
from opentelemetry import trace, baggage
from opentelemetry.trace import get_current_span

from ..core.config import settings


# Context variables for correlation
correlation_id_var: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)
tenant_id_var: ContextVar[Optional[str]] = ContextVar('tenant_id', default=None)
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)


class StructuredFormatter(logging.Formatter):
    """Custom structured log formatter with correlation IDs"""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON"""
        # Get correlation information
        correlation_id = correlation_id_var.get() or self._get_trace_correlation_id()
        user_id = user_id_var.get()
        tenant_id = tenant_id_var.get()
        request_id = request_id_var.get()

        # Build log entry
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "environment": settings.ENVIRONMENT,
            "service": "rag-system-backend",
            "version": settings.VERSION,
        }

        # Add correlation information
        if correlation_id:
            log_entry["correlation_id"] = correlation_id
        if user_id:
            log_entry["user_id"] = user_id
        if tenant_id:
            log_entry["tenant_id"] = tenant_id
        if request_id:
            log_entry["request_id"] = request_id

        # Add OpenTelemetry trace information
        span = get_current_span()
        if span and span.is_recording():
            span_context = span.get_span_context()
            log_entry["trace_id"] = format(span_context.trace_id, "032x")
            log_entry["span_id"] = format(span_context.span_id, "016x")

        # Add exception information if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "stack_trace": self.formatException(record.exc_info)
            }

        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in {
                'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                'filename', 'module', 'lineno', 'funcName', 'created',
                'msecs', 'relativeCreated', 'thread', 'threadName',
                'processName', 'process', 'getMessage', 'exc_info',
                'exc_text', 'stack_info'
            }:
                log_entry[key] = value

        return json.dumps(log_entry, default=str)

    def _get_trace_correlation_id(self) -> Optional[str]:
        """Get correlation ID from OpenTelemetry trace context"""
        # Try to get from baggage first
        correlation_id = baggage.get_baggage("correlation_id")
        if correlation_id:
            return correlation_id

        # Generate new correlation ID and set in baggage
        correlation_id = str(uuid.uuid4())
        baggage.set_baggage("correlation_id", correlation_id)
        return correlation_id


class CorrelationFilter(logging.Filter):
    """Filter to add correlation information to log records"""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation information to log record"""
        correlation_id = correlation_id_var.get()
        if correlation_id:
            record.correlation_id = correlation_id

        user_id = user_id_var.get()
        if user_id:
            record.user_id = user_id

        tenant_id = tenant_id_var.get()
        if tenant_id:
            record.tenant_id = tenant_id

        request_id = request_id_var.get()
        if request_id:
            record.request_id = request_id

        return True


def configure_logging() -> None:
    """Configure structured logging for the application"""
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            add_correlation_info,
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Get root logger
    root_logger = logging.getLogger()

    # Clear existing handlers
    root_logger.handlers.clear()

    # Set log level
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    root_logger.setLevel(log_level)

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)

    # Set formatter
    formatter = StructuredFormatter()
    console_handler.setFormatter(formatter)

    # Add correlation filter
    correlation_filter = CorrelationFilter()
    console_handler.addFilter(correlation_filter)

    # Add handler to root logger
    root_logger.addHandler(console_handler)

    # Configure specific loggers
    configure_specific_loggers()


def configure_specific_loggers():
    """Configure logging for specific components"""
    # Suppress verbose logging from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("opentelemetry").setLevel(logging.WARNING)

    # Application component logging
    app_loggers = [
        "src.api",
        "src.services",
        "src.database",
        "src.tasks",
        "src.middleware",
        "src.observability"
    ]

    for logger_name in app_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance"""
    return structlog.get_logger(name)


@contextmanager
def correlation_context(
    correlation_id: Optional[str] = None,
    user_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    request_id: Optional[str] = None
):
    """Context manager for correlation information"""
    # Generate correlation ID if not provided
    if not correlation_id:
        correlation_id = str(uuid.uuid4())

    # Set context variables
    token_correlation = correlation_id_var.set(correlation_id)
    token_user = user_id_var.set(user_id) if user_id else None
    token_tenant = tenant_id_var.set(tenant_id) if tenant_id else None
    token_request = request_id_var.set(request_id) if request_id else None

    # Set OpenTelemetry baggage
    baggage.set_baggage("correlation_id", correlation_id)
    if user_id:
        baggage.set_baggage("user_id", user_id)
    if tenant_id:
        baggage.set_baggage("tenant_id", tenant_id)
    if request_id:
        baggage.set_baggage("request_id", request_id)

    try:
        yield
    finally:
        # Reset context variables
        correlation_id_var.reset(token_correlation)
        if token_user:
            user_id_var.reset(token_user)
        if token_tenant:
            tenant_id_var.reset(token_tenant)
        if token_request:
            request_id_var.reset(token_request)


def add_correlation_info(logger, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Add correlation information to structured log events"""
    correlation_id = correlation_id_var.get()
    if correlation_id:
        event_dict["correlation_id"] = correlation_id

    user_id = user_id_var.get()
    if user_id:
        event_dict["user_id"] = user_id

    tenant_id = tenant_id_var.get()
    if tenant_id:
        event_dict["tenant_id"] = tenant_id

    request_id = request_id_var.get()
    if request_id:
        event_dict["request_id"] = request_id

    # Add OpenTelemetry trace information
    span = get_current_span()
    if span and span.is_recording():
        span_context = span.get_span_context()
        event_dict["trace_id"] = format(span_context.trace_id, "032x")
        event_dict["span_id"] = format(span_context.span_id, "016x")

    return event_dict


def log_security_event(
    event_type: str,
    severity: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None
):
    """Log security events with structured format"""
    logger = get_logger("security")

    security_context = {
        "event_type": event_type,
        "severity": severity,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "service": "rag-system-backend",
        "environment": settings.ENVIRONMENT,
    }

    if details:
        security_context.update(details)

    if user_id:
        security_context["user_id"] = user_id

    # Log at appropriate level based on severity
    if severity.upper() in ["HIGH", "CRITICAL"]:
        logger.error(f"SECURITY_EVENT: {message}", **security_context)
    elif severity.upper() == "MEDIUM":
        logger.warning(f"SECURITY_EVENT: {message}", **security_context)
    else:
        logger.info(f"SECURITY_EVENT: {message}", **security_context)


def log_performance_event(
    operation: str,
    duration: float,
    success: bool,
    details: Optional[Dict[str, Any]] = None
):
    """Log performance events with metrics"""
    logger = get_logger("performance")

    performance_context = {
        "operation": operation,
        "duration_seconds": duration,
        "success": success,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    if details:
        performance_context.update(details)

    if success:
        logger.info(f"PERFORMANCE: {operation} completed in {duration:.3f}s", **performance_context)
    else:
        logger.error(f"PERFORMANCE: {operation} failed after {duration:.3f}s", **performance_context)


def log_business_event(
    event_type: str,
    entity_type: str,
    entity_id: str,
    action: str,
    details: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None
):
    """Log business events for analytics"""
    logger = get_logger("business")

    business_context = {
        "event_type": event_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "action": action,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "service": "rag-system-backend",
    }

    if details:
        business_context.update(details)

    if user_id:
        business_context["user_id"] = user_id

    logger.info(f"BUSINESS_EVENT: {action} on {entity_type} {entity_id}", **business_context)


def log_error_with_context(
    error: Exception,
    context: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None
):
    """Log errors with rich context information"""
    logger = get_logger("error")

    error_context = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "service": "rag-system-backend",
    }

    if context:
        error_context.update(context)

    if user_id:
        error_context["user_id"] = user_id

    logger.error(f"ERROR: {type(error).__name__}: {error}", exc_info=True, **error_context)