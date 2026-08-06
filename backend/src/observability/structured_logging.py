"""
Structured Logging with Correlation IDs for Observability
Centralized logging with trace correlation and structured output for analysis
"""

import asyncio
import json
import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from datetime import timezone as dt_timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import structlog
from prometheus_client import Counter, Histogram

from .opentelemetry import get_span_id, get_trace_id, otel_manager


class LogLevel(Enum):
    """Log levels for structured logging"""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class LogCategory(Enum):
    """Log categories for better organization"""

    SYSTEM = "system"
    API = "api"
    DATABASE = "database"
    CACHE = "cache"
    DOCUMENT_PROCESSING = "document_processing"
    WEBSOCKET = "websocket"
    SEARCH = "search"
    ML_INFERENCE = "ml_inference"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    SECURITY = "security"
    PERFORMANCE = "performance"
    BUSINESS = "business"


@dataclass
class LogContext:
    """Structured log context with correlation information"""

    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    user_id: Optional[str] = None
    organization_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    tenant_id: Optional[str] = None
    environment: str = "development"
    service_name: str = "multimodal-rag-system"
    service_version: str = "1.0.0"
    hostname: Optional[str] = None
    pod_name: Optional[str] = None
    additional_context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        data = asdict(self)
        # Remove empty/None values for cleaner logs
        return {k: v for k, v in data.items() if v is not None and v != ""}


@dataclass
class StructuredLogEntry:
    """Structured log entry with rich metadata"""

    timestamp: float
    level: LogLevel
    category: LogCategory
    message: str
    context: LogContext
    event_name: Optional[str] = None
    event_data: Dict[str, Any] = field(default_factory=dict)
    error_details: Optional[Dict[str, Any]] = None
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    business_metrics: Dict[str, Any] = field(default_factory=dict)
    stack_trace: Optional[str] = None
    tags: List[str] = field(default_factory=list)


class StructuredLogger:
    """Structured logging system with correlation and OpenTelemetry integration"""

    def __init__(
        self,
        log_level: LogLevel = LogLevel.INFO,
        enable_console: bool = True,
        enable_file: bool = True,
        log_file_path: str = "/app/logs/structured.log",
        enable_json_output: bool = True,
        max_file_size_mb: int = 100,
        backup_count: int = 5,
    ):
        self.log_level = log_level
        self.enable_console = enable_console
        self.enable_file = enable_file
        self.log_file_path = log_file_path
        self.enable_json_output = enable_json_output
        self.max_file_size_mb = max_file_size_mb
        self.backup_count = backup_count

        # Thread-local context storage
        self._context_storage = threading.local()

        # Async context storage (for async operations)
        self._async_context = {}

        # Metrics for logging
        self.log_counter = Counter(
            "structured_logs_total",
            "Total structured logs",
            ["level", "category", "service"],
        )
        self.log_duration = Histogram(
            "log_processing_duration_seconds", "Log processing duration"
        )

        # Initialize structlog
        self._setup_structlog()

        # Setup file logging if enabled
        if self.enable_file:
            self._setup_file_logging()

    def _setup_structlog(self):
        """Setup structlog with custom processors"""
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            self._add_correlation_context,
            self._add_opentelemetry_context,
            structlog.processors.TimeStamper(fmt="ISO"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
        ]

        if self.enable_json_output:
            processors.append(structlog.processors.JSONRenderer())
        else:
            processors.append(structlog.dev.ConsoleRenderer())

        structlog.configure(
            processors=processors,
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )

    def _setup_file_logging(self):
        """Setup file logging with rotation"""
        import logging.handlers

        # Create log directory if it doesn't exist
        log_dir = Path(self.log_file_path).parent
        log_dir.mkdir(parents=True, exist_ok=True)

        # Setup file handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            self.log_file_path,
            maxBytes=self.max_file_size_mb * 1024 * 1024,
            backupCount=self.backup_count,
        )

        # Configure file formatter
        if self.enable_json_output:
            formatter = logging.Formatter("%(message)s")
        else:
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )

        file_handler.setFormatter(formatter)

        # Add to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)
        root_logger.setLevel(logging.DEBUG)

    def _add_correlation_context(
        self, logger, method_name: str, event_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add correlation context to log event"""
        context = self.get_current_context()
        event_dict.update(context.to_dict())
        return event_dict

    def _add_opentelemetry_context(
        self, logger, method_name: str, event_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add OpenTelemetry trace context to log event"""
        try:
            trace_id = get_trace_id()
            span_id = get_span_id()

            if trace_id:
                event_dict["otel_trace_id"] = trace_id
            if span_id:
                event_dict["otel_span_id"] = span_id

        except Exception:
            # OpenTelemetry might not be initialized
            pass

        return event_dict

    def set_context(self, **kwargs):
        """Set correlation context for the current thread/async context"""
        # Get current context
        context = self.get_current_context()

        # Update context with provided values
        for key, value in kwargs.items():
            if hasattr(context, key):
                setattr(context, key, value)
            else:
                context.additional_context[key] = value

        # Store in thread-local storage
        self._context_storage.context = context

    def get_current_context(self) -> LogContext:
        """Get current correlation context"""
        try:
            # Try thread-local storage first
            return getattr(self._context_storage, "context", LogContext())
        except AttributeError:
            # Try async context
            try:
                task = asyncio.current_task()
                if task and task.get_name() in self._async_context:
                    return self._async_context[task.get_name()]
            except RuntimeError:
                pass

            return LogContext()

    def set_async_context(self, context: LogContext):
        """Set context for async operations"""
        try:
            task = asyncio.current_task()
            if task:
                self._async_context[task.get_name()] = context
        except RuntimeError:
            pass

    @contextmanager
    def correlation_context(self, **kwargs):
        """Context manager for correlation context"""
        # Save current context
        old_context = self.get_current_context()

        # Set new context
        self.set_context(**kwargs)

        try:
            yield
        finally:
            # Restore old context
            self._context_storage.context = old_context

    def log(
        self,
        level: LogLevel,
        category: LogCategory,
        message: str,
        event_name: Optional[str] = None,
        event_data: Optional[Dict[str, Any]] = None,
        error: Optional[Exception] = None,
        performance_metrics: Optional[Dict[str, Any]] = None,
        business_metrics: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        **kwargs,
    ):
        """Log a structured event"""
        start_time = time.time()

        try:
            # Get current context
            context = self.get_current_context()

            # Create log entry
            entry = StructuredLogEntry(
                timestamp=time.time(),
                level=level,
                category=category,
                message=message,
                context=context,
                event_name=event_name,
                event_data=event_data or {},
                performance_metrics=performance_metrics or {},
                business_metrics=business_metrics or {},
                tags=tags or [],
            )

            # Add error details if provided
            if error:
                entry.error_details = {
                    "type": type(error).__name__,
                    "message": str(error),
                    "module": getattr(error, "__module__", None),
                }

                if hasattr(error, "__traceback__"):
                    import traceback

                    entry.stack_trace = traceback.format_exception(
                        type(error), error, error.__traceback__
                    )

            # Add additional context from kwargs
            entry.context.additional_context.update(kwargs)

            # Convert to log format
            log_data = {
                "timestamp": datetime.fromtimestamp(
                    entry.timestamp, dt_timezone.utc
                ).isoformat(),
                "level": entry.level.value,
                "category": entry.category.value,
                "message": entry.message,
                "event_name": entry.event_name,
                "event_data": entry.event_data,
                "context": entry.context.to_dict(),
                "performance_metrics": entry.performance_metrics,
                "business_metrics": entry.business_metrics,
                "tags": entry.tags,
            }

            if entry.error_details:
                log_data["error"] = entry.error_details

            if entry.stack_trace:
                log_data["stack_trace"] = entry.stack_trace

            # Get structured logger
            logger = structlog.get_logger(category.value)

            # Log at appropriate level
            log_method = getattr(logger, level.value)
            log_method(message, **log_data)

            # Record metrics
            self.log_counter.labels(
                level=level.value, category=category.value, service=context.service_name
            ).inc()

        except Exception as e:
            # Fallback to basic logging if structured logging fails
            logging.error(
                f"Structured logging failed: {e}. Original message: {message}"
            )

        finally:
            # Record processing duration
            duration = time.time() - start_time
            self.log_duration.observe(duration)

    def debug(self, category: LogCategory, message: str, **kwargs):
        """Log debug message"""
        self.log(LogLevel.DEBUG, category, message, **kwargs)

    def info(self, category: LogCategory, message: str, **kwargs):
        """Log info message"""
        self.log(LogLevel.INFO, category, message, **kwargs)

    def warning(self, category: LogCategory, message: str, **kwargs):
        """Log warning message"""
        self.log(LogLevel.WARNING, category, message, **kwargs)

    def error(
        self,
        category: LogCategory,
        message: str,
        error: Optional[Exception] = None,
        **kwargs,
    ):
        """Log error message"""
        self.log(LogLevel.ERROR, category, message, error=error, **kwargs)

    def critical(
        self,
        category: LogCategory,
        message: str,
        error: Optional[Exception] = None,
        **kwargs,
    ):
        """Log critical message"""
        self.log(LogLevel.CRITICAL, category, message, error=error, **kwargs)

    # Convenience methods for specific categories
    def log_api_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        request_id: str,
        user_id: Optional[str] = None,
        request_size: Optional[int] = None,
        response_size: Optional[int] = None,
    ):
        """Log API request"""
        self.info(
            LogCategory.API,
            "API request processed",
            event_name="api_request",
            event_data={
                "method": method,
                "path": path,
                "status_code": status_code,
                "request_size_bytes": request_size,
                "response_size_bytes": response_size,
            },
            performance_metrics={
                "duration_ms": duration_ms,
                "throughput_requests_per_second": 1 / (duration_ms / 1000)
                if duration_ms > 0
                else 0,
            },
            tags=[f"status_{status_code}", f"method_{method}"],
            request_id=request_id,
            user_id=user_id,
        )

    def log_document_processing(
        self,
        document_id: str,
        stage: str,
        status: str,
        duration_ms: Optional[float] = None,
        file_size: Optional[int] = None,
        error: Optional[Exception] = None,
    ):
        """Log document processing event"""
        level = LogLevel.INFO if error is None else LogLevel.ERROR

        self.log(
            level,
            LogCategory.DOCUMENT_PROCESSING,
            f"Document processing {status}: {stage}",
            event_name="document_processing",
            event_data={
                "document_id": document_id,
                "stage": stage,
                "status": status,
                "file_size_bytes": file_size,
            },
            performance_metrics={"duration_ms": duration_ms} if duration_ms else {},
            error=error,
            tags=[f"stage_{stage}", f"status_{status}"],
        )

    def log_websocket_event(
        self,
        connection_id: str,
        event_type: str,
        user_id: Optional[str] = None,
        latency_ms: Optional[float] = None,
        message_size: Optional[int] = None,
        error: Optional[Exception] = None,
    ):
        """Log WebSocket event"""
        level = LogLevel.INFO if error is None else LogLevel.ERROR

        self.log(
            level,
            LogCategory.WEBSOCKET,
            f"WebSocket event: {event_type}",
            event_name="websocket_event",
            event_data={
                "connection_id": connection_id,
                "event_type": event_type,
                "message_size_bytes": message_size,
            },
            performance_metrics={"latency_ms": latency_ms} if latency_ms else {},
            error=error,
            connection_id=connection_id,
            user_id=user_id,
            tags=[f"event_{event_type}"],
        )

    def log_database_operation(
        self,
        operation: str,
        table: str,
        duration_ms: float,
        rows_affected: Optional[int] = None,
        error: Optional[Exception] = None,
    ):
        """Log database operation"""
        level = LogLevel.INFO if error is None else LogLevel.ERROR

        self.log(
            level,
            LogCategory.DATABASE,
            f"Database operation: {operation} on {table}",
            event_name="database_operation",
            event_data={
                "operation": operation,
                "table": table,
                "rows_affected": rows_affected,
            },
            performance_metrics={"duration_ms": duration_ms},
            error=error,
            tags=[f"operation_{operation}", f"table_{table}"],
        )

    def log_cache_operation(
        self,
        operation: str,
        key: str,
        hit: bool,
        duration_ms: float,
        value_size: Optional[int] = None,
    ):
        """Log cache operation"""
        self.info(
            LogCategory.CACHE,
            f"Cache {operation}: {key}",
            event_name="cache_operation",
            event_data={
                "operation": operation,
                "key": key,
                "hit": hit,
                "value_size_bytes": value_size,
            },
            performance_metrics={"duration_ms": duration_ms},
            tags=[f"operation_{operation}", "hit" if hit else "miss"],
        )

    def log_search_query(
        self,
        query: str,
        results_count: int,
        duration_ms: float,
        search_type: str,
        user_id: Optional[str] = None,
    ):
        """Log search query"""
        self.info(
            LogCategory.SEARCH,
            f"Search query executed: {search_type}",
            event_name="search_query",
            event_data={
                "query_length": len(query),
                "results_count": results_count,
                "search_type": search_type,
            },
            performance_metrics={
                "duration_ms": duration_ms,
                "results_per_second": results_count / (duration_ms / 1000)
                if duration_ms > 0
                else 0,
            },
            user_id=user_id,
            tags=[f"type_{search_type}"],
        )

    def log_ml_inference(
        self,
        model_name: str,
        input_size: int,
        duration_ms: float,
        confidence: Optional[float] = None,
        error: Optional[Exception] = None,
    ):
        """Log ML inference"""
        level = LogLevel.INFO if error is None else LogLevel.ERROR

        self.log(
            level,
            LogCategory.ML_INFERENCE,
            f"ML inference: {model_name}",
            event_name="ml_inference",
            event_data={
                "model_name": model_name,
                "input_size": input_size,
                "confidence": confidence,
            },
            performance_metrics={
                "duration_ms": duration_ms,
                "inferences_per_second": 1000 / duration_ms if duration_ms > 0 else 0,
            },
            error=error,
            tags=[f"model_{model_name}"],
        )

    def log_security_event(
        self,
        event_type: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        severity: str = "medium",
        blocked: bool = False,
    ):
        """Log security event"""
        level = (
            LogLevel.WARNING
            if severity == "low"
            else LogLevel.ERROR
            if severity == "medium"
            else LogLevel.CRITICAL
        )

        self.log(
            level,
            LogCategory.SECURITY,
            f"Security event: {event_type}",
            event_name="security_event",
            event_data={
                "event_type": event_type,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "severity": severity,
                "blocked": blocked,
            },
            user_id=user_id,
            tags=[f"severity_{severity}", f"event_{event_type}"],
        )


# Global structured logger instance
structured_logger = StructuredLogger()


# Convenience functions
def set_log_context(**kwargs):
    """Set correlation context for logging"""
    structured_logger.set_context(**kwargs)


@contextmanager
def log_correlation(**kwargs):
    """Context manager for log correlation"""
    with structured_logger.correlation_context(**kwargs):
        yield


def log_api_request(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    request_id: str,
    user_id: Optional[str] = None,
    request_size: Optional[int] = None,
    response_size: Optional[int] = None,
):
    """Log API request"""
    structured_logger.log_api_request(
        method,
        path,
        status_code,
        duration_ms,
        request_id,
        user_id,
        request_size,
        response_size,
    )


def log_document_processing(
    document_id: str,
    stage: str,
    status: str,
    duration_ms: Optional[float] = None,
    file_size: Optional[int] = None,
    error: Optional[Exception] = None,
):
    """Log document processing"""
    structured_logger.log_document_processing(
        document_id, stage, status, duration_ms, file_size, error
    )


def log_websocket_event(
    connection_id: str,
    event_type: str,
    user_id: Optional[str] = None,
    latency_ms: Optional[float] = None,
    message_size: Optional[int] = None,
    error: Optional[Exception] = None,
):
    """Log WebSocket event"""
    structured_logger.log_websocket_event(
        connection_id, event_type, user_id, latency_ms, message_size, error
    )


def log_database_operation(
    operation: str,
    table: str,
    duration_ms: float,
    rows_affected: Optional[int] = None,
    error: Optional[Exception] = None,
):
    """Log database operation"""
    structured_logger.log_database_operation(
        operation, table, duration_ms, rows_affected, error
    )


def log_cache_operation(
    operation: str,
    key: str,
    hit: bool,
    duration_ms: float,
    value_size: Optional[int] = None,
):
    """Log cache operation"""
    structured_logger.log_cache_operation(operation, key, hit, duration_ms, value_size)


def log_search_query(
    query: str,
    results_count: int,
    duration_ms: float,
    search_type: str,
    user_id: Optional[str] = None,
):
    """Log search query"""
    structured_logger.log_search_query(
        query, results_count, duration_ms, search_type, user_id
    )


def log_ml_inference(
    model_name: str,
    input_size: int,
    duration_ms: float,
    confidence: Optional[float] = None,
    error: Optional[Exception] = None,
):
    """Log ML inference"""
    structured_logger.log_ml_inference(
        model_name, input_size, duration_ms, confidence, error
    )


def log_security_event(
    event_type: str,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    severity: str = "medium",
    blocked: bool = False,
):
    """Log security event"""
    structured_logger.log_security_event(
        event_type, user_id, ip_address, user_agent, severity, blocked
    )
