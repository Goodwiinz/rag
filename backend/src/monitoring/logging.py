"""
Centralized Logging System for Knowledge Graph Analytics Dashboard
Structured logging with correlation, tracing integration, and log aggregation
"""

import asyncio
import json
import logging
import os
import time
import traceback
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from functools import wraps
from typing import Any, Dict, List, Optional, Union

from .opentelemetry import get_span_id, get_trace_id, otel_manager


@dataclass
class LogContext:
    """Log context for correlation and tracing"""

    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None
    component: Optional[str] = None
    service: Optional[str] = None
    environment: Optional[str] = None
    version: Optional[str] = None
    additional_context: Dict[str, Any] = field(default_factory=dict)


class StructuredLogger:
    """Structured logger with correlation and tracing integration"""

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(name)
        self._default_context = LogContext()
        self._setup_logger()

    def _setup_logger(self):
        """Setup logger with appropriate handlers and formatters"""
        if not self.logger.handlers:
            # Create console handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)

            # Create file handler
            log_file = f"/var/log/knowledge-graph/{self.name.replace('.', '/')}.log"
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)

            # Create formatters
            console_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            file_formatter = JsonFormatter()

            console_handler.setFormatter(console_formatter)
            file_handler.setFormatter(file_formatter)

            self.logger.addHandler(console_handler)
            self.logger.addHandler(file_handler)
            self.logger.setLevel(logging.DEBUG)
            self.logger.propagate = False

    def set_default_context(self, **kwargs):
        """Set default context for all log entries"""
        for key, value in kwargs.items():
            if hasattr(self._default_context, key):
                setattr(self._default_context, key, value)
            else:
                self._default_context.additional_context[key] = value

    def _enrich_context(self, context: Optional[Dict[str, Any]] = None) -> LogContext:
        """Enrich context with tracing information"""
        log_context = LogContext()

        # Copy default context
        for field_name, field_value in asdict(self._default_context).items():
            if hasattr(log_context, field_name):
                setattr(log_context, field_name, field_value)

        # Add additional context
        log_context.additional_context.update(self._default_context.additional_context)

        # Add tracing context
        log_context.trace_id = get_trace_id()
        log_context.span_id = get_span_id()

        # Override with provided context
        if context:
            for key, value in context.items():
                if hasattr(log_context, key):
                    setattr(log_context, key, value)
                else:
                    log_context.additional_context[key] = value

        # Set defaults from environment
        if not log_context.service:
            log_context.service = os.environ.get(
                "SERVICE_NAME", "knowledge-graph-analytics"
            )
        if not log_context.environment:
            log_context.environment = os.environ.get("ENVIRONMENT", "development")
        if not log_context.version:
            log_context.version = os.environ.get("VERSION", "1.0.0")
        if not log_context.component:
            log_context.component = self.name

        # Generate correlation ID if not present
        if not log_context.correlation_id:
            log_context.correlation_id = str(uuid.uuid4())

        return log_context

    def _create_log_record(
        self,
        level: int,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        error: Optional[Exception] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> logging.LogRecord:
        """Create a structured log record"""
        log_context = self._enrich_context(context)

        # Create log data
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": logging.getLevelName(level),
            "logger": self.name,
            "message": message,
            "context": asdict(log_context),
        }

        # Add error information if present
        if error:
            log_data["error"] = {
                "type": type(error).__name__,
                "message": str(error),
                "traceback": traceback.format_exc(),
            }

        # Add extra data
        if extra_data:
            log_data["data"] = extra_data

        # Convert to JSON string for message
        json_message = json.dumps(log_data, default=str)

        # Create log record
        record = self.logger.makeRecord(
            name=self.name,
            level=level,
            pathname="",
            lineno=0,
            msg=json_message,
            args=(),
            exc_info=None,
        )

        return record

    def debug(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        error: Optional[Exception] = None,
        **kwargs,
    ):
        """Log debug message"""
        record = self._create_log_record(logging.DEBUG, message, context, error, kwargs)
        self.logger.handle(record)

    def info(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        error: Optional[Exception] = None,
        **kwargs,
    ):
        """Log info message"""
        record = self._create_log_record(logging.INFO, message, context, error, kwargs)
        self.logger.handle(record)

    def warning(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        error: Optional[Exception] = None,
        **kwargs,
    ):
        """Log warning message"""
        record = self._create_log_record(
            logging.WARNING, message, context, error, kwargs
        )
        self.logger.handle(record)

    def error(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        error: Optional[Exception] = None,
        **kwargs,
    ):
        """Log error message"""
        record = self._create_log_record(logging.ERROR, message, context, error, kwargs)
        self.logger.handle(record)

    def critical(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        error: Optional[Exception] = None,
        **kwargs,
    ):
        """Log critical message"""
        record = self._create_log_record(
            logging.CRITICAL, message, context, error, kwargs
        )
        self.logger.handle(record)

    def log_api_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration: float,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        **kwargs,
    ):
        """Log API request"""
        self.info(
            f"API {method} {path} - {status_code}",
            context={
                "user_id": user_id,
                "request_id": request_id,
                "method": method,
                "path": path,
                "status_code": status_code,
            },
            duration=duration,
            **kwargs,
        )

    def log_database_query(
        self,
        query_type: str,
        table: str,
        duration: float,
        rows_affected: Optional[int] = None,
        error: Optional[Exception] = None,
        **kwargs,
    ):
        """Log database query"""
        level = logging.ERROR if error else logging.DEBUG

        message = f"Database {query_type} on {table}"
        if error:
            message += f" - ERROR: {str(error)}"
        elif rows_affected is not None:
            message += f" - {rows_affected} rows affected"

        record = self._create_log_record(
            level,
            message,
            context={
                "query_type": query_type,
                "table": table,
                "rows_affected": rows_affected,
            },
            error=error,
            duration=duration,
            **kwargs,
        )
        self.logger.handle(record)

    def log_cache_operation(
        self,
        operation: str,
        key: str,
        hit: bool,
        duration: Optional[float] = None,
        **kwargs,
    ):
        """Log cache operation"""
        self.info(
            f"Cache {operation} - {key} - {'HIT' if hit else 'MISS'}",
            context={"operation": operation, "key": key, "hit": hit},
            duration=duration,
            **kwargs,
        )

    def log_search_query(
        self,
        query: str,
        results_count: int,
        duration: float,
        precision: Optional[float] = None,
        recall: Optional[float] = None,
        user_id: Optional[str] = None,
        **kwargs,
    ):
        """Log search query"""
        self.info(
            f"Search query executed - {results_count} results",
            context={
                "query": query,
                "results_count": results_count,
                "precision": precision,
                "recall": recall,
                "user_id": user_id,
            },
            duration=duration,
            **kwargs,
        )

    def log_graph_query(
        self,
        query_type: str,
        nodes_returned: int,
        edges_returned: int,
        complexity: int,
        duration: float,
        **kwargs,
    ):
        """Log graph query"""
        self.info(
            f"Graph {query_type} query executed",
            context={
                "query_type": query_type,
                "nodes_returned": nodes_returned,
                "edges_returned": edges_returned,
                "complexity": complexity,
            },
            duration=duration,
            **kwargs,
        )

    def log_ml_inference(
        self,
        model_name: str,
        model_version: str,
        input_shape: List[int],
        output_shape: List[int],
        duration: float,
        accuracy: Optional[float] = None,
        error: Optional[Exception] = None,
        **kwargs,
    ):
        """Log ML model inference"""
        level = logging.ERROR if error else logging.INFO

        message = f"ML inference - {model_name} v{model_version}"
        if error:
            message += f" - ERROR: {str(error)}"

        record = self._create_log_record(
            level,
            message,
            context={
                "model_name": model_name,
                "model_version": model_version,
                "input_shape": input_shape,
                "output_shape": output_shape,
                "accuracy": accuracy,
            },
            error=error,
            duration=duration,
            **kwargs,
        )
        self.logger.handle(record)

    def log_security_event(
        self,
        event_type: str,
        action: str,
        resource: str,
        source_ip: Optional[str] = None,
        user_id: Optional[str] = None,
        success: bool = True,
        **kwargs,
    ):
        """Log security event"""
        level = logging.WARNING if not success else logging.INFO

        self._create_log_record(
            level,
            f"Security event: {event_type} - {action} on {resource} - {'SUCCESS' if success else 'FAILED'}",
            context={
                "event_type": event_type,
                "action": action,
                "resource": resource,
                "source_ip": source_ip,
                "user_id": user_id,
                "success": success,
            },
            **kwargs,
        )

    def log_performance_metric(
        self,
        metric_name: str,
        value: float,
        unit: str,
        component: Optional[str] = None,
        **kwargs,
    ):
        """Log performance metric"""
        self.info(
            f"Performance metric: {metric_name} = {value} {unit}",
            context={
                "metric_name": metric_name,
                "metric_value": value,
                "metric_unit": unit,
                "component": component,
            },
            **kwargs,
        )


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging"""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        try:
            # Parse JSON message if it's already JSON
            log_data = json.loads(record.getMessage())
        except (json.JSONDecodeError, TypeError):
            # Create JSON from standard log record
            log_data = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat() + "Z",
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            }

        # Add exception information if present
        if record.exc_info:
            log_data["error"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        return json.dumps(log_data, default=str)


class LoggingManager:
    """Centralized logging manager"""

    def __init__(self):
        self.loggers: Dict[str, StructuredLogger] = {}
        self._setup_global_logging()

    def _setup_global_logging(self):
        """Setup global logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        # Suppress noisy loggers
        logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
        logging.getLogger("requests.packages.urllib3").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)

    def get_logger(self, name: str) -> StructuredLogger:
        """Get or create a structured logger"""
        if name not in self.loggers:
            self.loggers[name] = StructuredLogger(name)
        return self.loggers[name]

    def set_global_context(self, **kwargs):
        """Set global context for all loggers"""
        for logger in self.loggers.values():
            logger.set_default_context(**kwargs)


# Global logging manager instance
logging_manager = LoggingManager()


# Convenience functions
def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger"""
    return logging_manager.get_logger(name)


def set_log_context(**kwargs):
    """Set global logging context"""
    logging_manager.set_global_context(**kwargs)


# Decorators for automatic logging
def log_function_calls(
    logger_name: Optional[str] = None,
    level: int = logging.DEBUG,
    include_args: bool = False,
    include_result: bool = False,
):
    """Decorator to automatically log function calls"""

    def decorator(func):
        name = logger_name or f"{func.__module__}.{func.__name__}"
        logger = get_logger(name)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            function_name = f"{func.__module__}.{func.__name__}"

            log_data = {
                "function": function_name,
                "args_count": len(args),
                "kwargs_count": len(kwargs),
            }

            if include_args:
                log_data["args"] = str(args)
                log_data["kwargs"] = str(kwargs)

            logger.log(level, f"Calling {function_name}", context=log_data)

            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                if include_result:
                    log_data["result"] = str(result)[:500]  # Limit result length

                logger.log(
                    level,
                    f"Completed {function_name}",
                    context=log_data,
                    duration=duration,
                )
                return result

            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    f"Failed {function_name}",
                    context=log_data,
                    error=e,
                    duration=duration,
                )
                raise

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            function_name = f"{func.__module__}.{func.__name__}"

            log_data = {
                "function": function_name,
                "args_count": len(args),
                "kwargs_count": len(kwargs),
                "is_async": True,
            }

            if include_args:
                log_data["args"] = str(args)
                log_data["kwargs"] = str(kwargs)

            logger.log(level, f"Calling async {function_name}", context=log_data)

            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time

                if include_result:
                    log_data["result"] = str(result)[:500]  # Limit result length

                logger.log(
                    level,
                    f"Completed async {function_name}",
                    context=log_data,
                    duration=duration,
                )
                return result

            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    f"Failed async {function_name}",
                    context=log_data,
                    error=e,
                    duration=duration,
                )
                raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


@contextmanager
def log_context(
    logger_name: str,
    operation: str,
    context: Optional[Dict[str, Any]] = None,
    level: int = logging.INFO,
):
    """Context manager for operation logging"""
    logger = get_logger(logger_name)

    start_time = time.time()
    operation_context = {"operation": operation, **(context or {})}

    logger.log(level, f"Starting {operation}", context=operation_context)

    try:
        yield logger
        duration = time.time() - start_time
        logger.log(
            level,
            f"Completed {operation}",
            context=operation_context,
            duration=duration,
        )

    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            f"Failed {operation}", context=operation_context, error=e, duration=duration
        )
        raise


# Standard loggers for different components
api_logger = get_logger("knowledge-graph.api")
search_logger = get_logger("knowledge-graph.search")
graph_logger = get_logger("knowledge-graph.graph")
ml_logger = get_logger("knowledge-graph.ml")
database_logger = get_logger("knowledge-graph.database")
cache_logger = get_logger("knowledge-graph.cache")
security_logger = get_logger("knowledge-graph.security")
performance_logger = get_logger("knowledge-graph.performance")
