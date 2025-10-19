"""
Automatic instrumentation for the RAG system

Provides comprehensive automatic instrumentation including:
- FastAPI application instrumentation
- Database operation tracing
- HTTP client instrumentation
- Redis operation tracing
- Custom business logic instrumentation
- Service-to-service call tracing
"""

import asyncio
import time
from typing import Dict, Any, Optional, Callable
from functools import wraps
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware

from sqlalchemy import event
from sqlalchemy.engine import Engine
import redis
import httpx

from .tracer import (
    trace_span, async_trace_span, get_trace_id, get_span_id,
    set_correlation_id, get_correlation_id, set_span_attribute
)
from .metrics import (
    track_performance, record_histogram, increment_counter,
    record_search_metrics, record_file_processing_metrics
)
from .logging import correlation_context, get_logger
from ..core.config import settings

logger = get_logger(__name__)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Middleware for automatic HTTP request tracing and metrics"""

    async def dispatch(self, request: Request, call_next):
        """Process HTTP request with observability"""
        # Generate correlation ID
        correlation_id = request.headers.get("x-correlation-id") or get_correlation_id()

        # Extract user and tenant information
        user_id = request.headers.get("x-user-id")
        tenant_id = request.headers.get("x-tenant-id")
        request_id = request.headers.get("x-request-id")

        # Start correlation context
        with correlation_context(correlation_id, user_id, tenant_id, request_id):
            # Start span for HTTP request
            span_name = f"HTTP {request.method} {request.url.path}"
            with async_trace_span(
                span_name,
                attributes={
                    "http.method": request.method,
                    "http.url": str(request.url),
                    "http.scheme": request.url.scheme,
                    "http.host": request.url.hostname,
                    "http.target": request.url.path,
                    "http.user_agent": request.headers.get("user-agent", ""),
                    "http.client_ip": request.client.host if request.client else "unknown",
                    "http.referer": request.headers.get("referer", ""),
                }
            ) as span:
                start_time = time.time()

                # Add correlation ID to response headers
                response = Response()
                response.headers["x-correlation-id"] = correlation_id

                try:
                    # Process request
                    response = await call_next(request)

                    # Record success metrics
                    duration = time.time() - start_time
                    status_code = response.status_code

                    # Update span with response info
                    span.set_attribute("http.status_code", status_code)
                    span.set_status("OK" if 200 <= status_code < 400 else "ERROR")

                    # Record metrics
                    attributes = {
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": str(status_code),
                        "status_class": f"{status_code // 100}xx"
                    }

                    if user_id:
                        attributes["user_id"] = user_id
                    if tenant_id:
                        attributes["tenant_id"] = tenant_id

                    record_histogram("http_request_duration_seconds", duration, attributes)
                    increment_counter("http_requests_total", attributes=attributes)

                    # Log request completion
                    logger.info(
                        f"HTTP Request: {request.method} {request.url.path} -> {status_code}",
                        duration=duration,
                        method=request.method,
                        path=request.url.path,
                        status_code=status_code,
                        user_id=user_id,
                        tenant_id=tenant_id
                    )

                    # Add timing header
                    response.headers["x-process-time"] = str(duration)
                    response.headers["x-correlation-id"] = correlation_id

                    return response

                except Exception as e:
                    # Record error metrics
                    duration = time.time() - start_time
                    error_attrs = {
                        "method": request.method,
                        "path": request.url.path,
                        "error_type": type(e).__name__,
                    }

                    increment_counter("http_requests_errors_total", attributes=error_attrs)
                    logger.error(
                        f"HTTP Request Error: {request.method} {request.url.path}",
                        error=str(e),
                        error_type=type(e).__name__,
                        duration=duration,
                        method=request.method,
                        path=request.url.path
                    )

                    # Update span with error info
                    span.record_exception(e)
                    span.set_status("ERROR", str(e))

                    raise


class DatabaseInstrumentation:
    """Instrumentation for database operations"""

    @staticmethod
    def instrument_sqlalchemy(engine: Engine):
        """Instrument SQLAlchemy engine for query tracing"""

        @event.listens_for(engine, "before_cursor_execute")
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            """Start tracing database query"""
            context._query_start_time = time.time()
            context._query_span_name = "database.query"

            # Start span for database operation
            span = trace_span(
                context._query_span_name,
                attributes={
                    "db.system": "postgresql",
                    "db.operation": context.execution_options.get("operation", "query"),
                    "db.statement": statement[:500],  # Truncate long statements
                    "db.query.parameters_count": len(parameters) if parameters else 0,
                }
            )

            context._query_span = span

        @event.listens_for(engine, "after_cursor_execute")
        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            """Complete database query tracing"""
            if hasattr(context, '_query_start_time'):
                duration = time.time() - context._query_start_time

                # Record metrics
                record_histogram("database_query_duration_seconds", duration, {
                    "operation": context.execution_options.get("operation", "query"),
                    "success": "true"
                })

                increment_counter("database_queries_total", {
                    "operation": context.execution_options.get("operation", "query"),
                    "success": "true"
                })

                logger.debug(
                    f"Database query completed",
                    duration=duration,
                    operation=context.execution_options.get("operation", "query"),
                    statement_preview=statement[:100]
                )

        @event.listens_for(engine, "handle_error")
        def handle_error(context, exception):
            """Handle database errors"""
            if hasattr(context, '_query_start_time'):
                duration = time.time() - context._query_start_time

                # Record error metrics
                increment_counter("database_queries_total", {
                    "operation": context.execution_options.get("operation", "query"),
                    "success": "false",
                    "error_type": type(exception).__name__
                })

                logger.error(
                    f"Database query error",
                    error=str(exception),
                    error_type=type(exception).__name__,
                    duration=duration
                )


class RedisInstrumentation:
    """Instrumentation for Redis operations"""

    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self._instrument_client()

    def _instrument_client(self):
        """Instrument Redis client methods"""
        original_execute_command = self.redis_client.execute_command

        def instrumented_execute_command(*args, **kwargs):
            """Instrument Redis command execution"""
            command = args[0] if args else "unknown"
            start_time = time.time()

            with trace_span(
                "redis.command",
                attributes={
                    "redis.command": command,
                    "redis.args_count": len(args) - 1,  # Exclude command name
                }
            ) as span:
                try:
                    result = original_execute_command(*args, **kwargs)
                    duration = time.time() - start_time

                    # Record metrics
                    record_histogram("redis_command_duration_seconds", duration, {
                        "command": command,
                        "success": "true"
                    })

                    increment_counter("redis_commands_total", {
                        "command": command,
                        "success": "true"
                    })

                    return result

                except Exception as e:
                    duration = time.time() - start_time

                    # Record error metrics
                    increment_counter("redis_commands_total", {
                        "command": command,
                        "success": "false",
                        "error_type": type(e).__name__
                    })

                    span.record_exception(e)
                    span.set_status("ERROR", str(e))

                    raise

        # Replace original method
        self.redis_client.execute_command = instrumented_execute_command


class HTTPClientInstrumentation:
    """Instrumentation for HTTP client calls"""

    @staticmethod
    def instrument_httpx_client(client: httpx.Client):
        """Instrument httpx client for outbound calls"""
        original_request = client.request

        def instrumented_request(method: str, url: str, **kwargs):
            """Instrument HTTP request"""
            start_time = time.time()
            parsed_url = httpx.URL(url)

            with trace_span(
                "http.client.request",
                attributes={
                    "http.method": method.upper(),
                    "http.url": str(url),
                    "http.scheme": parsed_url.scheme,
                    "http.host": parsed_url.host,
                    "http.target": str(parsed_url.path),
                }
            ) as span:
                try:
                    response = original_request(method, url, **kwargs)
                    duration = time.time() - start_time

                    # Update span with response info
                    span.set_attribute("http.status_code", response.status_code)

                    # Record metrics
                    record_histogram("http_client_request_duration_seconds", duration, {
                        "method": method.upper(),
                        "status_code": str(response.status_code),
                        "target_host": parsed_url.host
                    })

                    increment_counter("http_client_requests_total", {
                        "method": method.upper(),
                        "status_code": str(response.status_code),
                        "target_host": parsed_url.host
                    })

                    return response

                except Exception as e:
                    duration = time.time() - start_time

                    # Record error metrics
                    increment_counter("http_client_requests_total", {
                        "method": method.upper(),
                        "success": "false",
                        "error_type": type(e).__name__,
                        "target_host": parsed_url.host
                    })

                    span.record_exception(e)
                    span.set_status("ERROR", str(e))

                    raise

        client.request = instrumented_request


def instrument_app(app: FastAPI) -> FastAPI:
    """Instrument FastAPI application with comprehensive observability"""
    # Add observability middleware
    app.add_middleware(ObservabilityMiddleware)

    # Configure logging
    from .logging import configure_logging
    configure_logging()

    # Configure metrics
    from .metrics import configure_metrics
    configure_metrics()

    # Configure tracing
    from .tracer import configure_tracing
    configure_tracing()

    logger.info("Application instrumented with observability", service="rag-system-backend")

    return app


def instrument_services(
    sql_engine: Optional[Engine] = None,
    redis_client: Optional[redis.Redis] = None,
    http_client: Optional[httpx.Client] = None
) -> Dict[str, Any]:
    """Instrument various services and clients"""
    instrumentation_results = {}

    # Instrument database
    if sql_engine:
        DatabaseInstrumentation.instrument_sqlalchemy(sql_engine)
        instrumentation_results["database"] = "instrumented"
        logger.info("Database instrumented for observability")

    # Instrument Redis
    if redis_client:
        redis_instrumentation = RedisInstrumentation(redis_client)
        instrumentation_results["redis"] = "instrumented"
        logger.info("Redis client instrumented for observability")

    # Instrument HTTP client
    if http_client:
        HTTPClientInstrumentation.instrument_httpx_client(http_client)
        instrumentation_results["http_client"] = "instrumented"
        logger.info("HTTP client instrumented for observability")

    return instrumentation_results


def trace_async_business_operation(
    operation_name: str,
    business_entity: Optional[str] = None,
    business_id: Optional[str] = None
):
    """Decorator for tracing async business operations"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Build attributes
            attributes = {
                "operation.name": operation_name,
                "operation.type": "business",
            }

            if business_entity:
                attributes["business.entity"] = business_entity
            if business_id:
                attributes["business.id"] = business_id

            with async_trace_span(f"business.{operation_name}", attributes=attributes):
                with track_performance(f"business_{operation_name}"):
                    try:
                        start_time = time.time()
                        result = await func(*args, **kwargs)
                        duration = time.time() - start_time

                        # Log business event
                        from .logging import log_business_event
                        log_business_event(
                            event_type=operation_name,
                            entity_type=business_entity or "unknown",
                            entity_id=business_id or "unknown",
                            action="completed",
                            details={"duration": duration}
                        )

                        return result

                    except Exception as e:
                        # Log business error
                        from .logging import log_error_with_context
                        log_error_with_context(
                            error=e,
                            context={
                                "operation": operation_name,
                                "business_entity": business_entity,
                                "business_id": business_id
                            }
                        )
                        raise

        return wrapper
    return decorator


def trace_sync_business_operation(
    operation_name: str,
    business_entity: Optional[str] = None,
    business_id: Optional[str] = None
):
    """Decorator for tracing sync business operations"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Build attributes
            attributes = {
                "operation.name": operation_name,
                "operation.type": "business",
            }

            if business_entity:
                attributes["business.entity"] = business_entity
            if business_id:
                attributes["business.id"] = business_id

            with trace_span(f"business.{operation_name}", attributes=attributes):
                with track_performance(f"business_{operation_name}"):
                    try:
                        start_time = time.time()
                        result = func(*args, **kwargs)
                        duration = time.time() - start_time

                        # Log business event
                        from .logging import log_business_event
                        log_business_event(
                            event_type=operation_name,
                            entity_type=business_entity or "unknown",
                            entity_id=business_id or "unknown",
                            action="completed",
                            details={"duration": duration}
                        )

                        return result

                    except Exception as e:
                        # Log business error
                        from .logging import log_error_with_context
                        log_error_with_context(
                            error=e,
                            context={
                                "operation": operation_name,
                                "business_entity": business_entity,
                                "business_id": business_id
                            }
                        )
                        raise

        return wrapper
    return decorator