"""
Observability Middleware

Comprehensive middleware that combines logging, tracing, metrics,
and correlation for complete request observability.
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from fastapi import Request, Response
from src.core.security import get_client_ip
from fastapi.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from src.auth.rbac_decorator import get_current_user

from ..config.monitoring_config import get_monitoring_config
from ..services.observability_manager import get_observability_manager

logger = logging.getLogger(__name__)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """
    Comprehensive observability middleware

    Automatically instruments HTTP requests with:
    - Request/response logging
    - Distributed tracing
    - Metrics collection
    - Correlation ID injection
    - User context tracking
    """

    def __init__(self, app, config: Optional[Dict[str, Any]] = None):
        """Initialize observability middleware"""
        super().__init__(app)
        self.config = config or {}
        self.observability_manager = get_observability_manager()
        self.monitoring_config = get_monitoring_config()

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process request with full observability instrumentation"""
        # Start timing
        start_time = time.time()
        request_id = str(uuid.uuid4())

        # Extract or create correlation ID
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())

        # Get user context if available
        user_context = await self._get_user_context(request)

        # Initialize context
        context = {
            "request_id": request_id,
            "correlation_id": correlation_id,
            "start_time": start_time,
            "user_context": user_context,
            "request_info": {
                "method": request.method,
                "url": str(request.url),
                "headers": dict(request.headers),
                "client_ip": self._get_client_ip(request),
                "user_agent": request.headers.get("User-Agent", ""),
                "path": request.url.path,
                "query_params": dict(request.query_params),
            },
        }

        # Add context to request state for other middleware
        request.state.correlation_id = correlation_id
        request.state.request_id = request_id
        request.state.user_context = user_context
        request.state.observability_context = context

        # Start tracing
        span_context = None
        try:
            span_context = (
                await self.observability_manager.tracing_collector.start_span(
                    operation_name=f"{request.method} {request.url.path}",
                    service=self.monitoring_config.service_name,
                    component="api",
                    labels={
                        "http.method": request.method,
                        "http.path": request.url.path,
                        "http.scheme": request.url.scheme,
                        "http.host": request.url.hostname,
                        "request_id": request_id,
                        "correlation_id": correlation_id,
                    },
                    attributes={
                        "http.url": str(request.url),
                        "http.user_agent": request.headers.get("User-Agent", ""),
                        "http.client_ip": context["request_info"]["client_ip"],
                        "user.id": user_context.get("user_id")
                        if user_context
                        else None,
                        "organization.id": user_context.get("organization_id")
                        if user_context
                        else None,
                    },
                )
            )

            # Add trace context to request
            request.state.trace_context = span_context

            # Log request start
            await self._log_request_start(request, context)

            # Process request
            response = await call_next(request)

            # Calculate metrics
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000

            # Update context with response info
            context["response_info"] = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "duration_ms": duration_ms,
            }

            # Add tracing attributes
            if span_context:
                await self.observability_manager.tracing_collector.add_span_event(
                    span_context,
                    "http.response_start",
                    {
                        "http.status_code": response.status_code,
                        "response.duration_ms": duration_ms,
                    },
                )

            # Record metrics
            await self._record_metrics(request, response, duration_ms, user_context)

            # Log request completion
            await self._log_request_complete(request, response, context)

            # Finish tracing
            if span_context:
                await self.observability_manager.tracing_collector.finish_span(
                    span_context,
                    status="ok" if response.status_code < 400 else "error",
                    attributes={
                        "http.status_code": response.status_code,
                        "response.duration_ms": duration_ms,
                    },
                )

            # Add correlation headers to response
            response.headers["X-Correlation-ID"] = correlation_id
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            # Calculate metrics even for errors
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000

            # Log error
            await self._log_request_error(request, e, context)

            # Record error metrics
            await self._record_error_metrics(request, e, duration_ms, user_context)

            # Finish tracing with error
            if span_context:
                await self.observability_manager.tracing_collector.finish_span(
                    span_context,
                    status="error",
                    error=str(e),
                    attributes={
                        "error.type": type(e).__name__,
                        "error.message": str(e),
                        "request.duration_ms": duration_ms,
                    },
                )

            # Re-raise the exception
            raise

    async def _get_user_context(self, request: Request) -> Optional[Dict[str, Any]]:
        """Extract user context from request"""
        try:
            # Try to get user from authentication
            if hasattr(request.state, "user") and request.state.user:
                user = request.state.user
                return {
                    "user_id": str(user.id) if hasattr(user, "id") else None,
                    "email": getattr(user, "email", None),
                    "role": getattr(user, "role", None),
                    "organization_id": str(user.organization_id)
                    if hasattr(user, "organization_id")
                    else None,
                }

            # Try to get from authorization header (simplified)
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                # In a real implementation, you'd decode the JWT token here
                pass

            return None

        except Exception as e:
            logger.debug(f"Error extracting user context: {e}")
            return None

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address"""
        return get_client_ip(
            request.headers,
            request.client.host if request.client else None,
        )

    async def _log_request_start(self, request: Request, context: Dict[str, Any]):
        """Log the start of request processing"""
        try:
            log_data = {
                "event": "request_start",
                "request_id": context["request_id"],
                "correlation_id": context["correlation_id"],
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "client_ip": context["request_info"]["client_ip"],
                "user_agent": context["request_info"]["user_agent"],
                "user_id": context["user_context"]["user_id"]
                if context["user_context"]
                else None,
                "organization_id": context["user_context"]["organization_id"]
                if context["user_context"]
                else None,
                "timestamp": datetime.utcnow().isoformat(),
            }

            logger.info(
                f"Request started: {request.method} {request.url.path}", extra=log_data
            )

        except Exception as e:
            logger.error(f"Error logging request start: {e}")

    async def _log_request_complete(
        self, request: Request, response: Response, context: Dict[str, Any]
    ):
        """Log the completion of request processing"""
        try:
            log_data = {
                "event": "request_complete",
                "request_id": context["request_id"],
                "correlation_id": context["correlation_id"],
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": context["response_info"]["duration_ms"],
                "client_ip": context["request_info"]["client_ip"],
                "user_id": context["user_context"]["user_id"]
                if context["user_context"]
                else None,
                "organization_id": context["user_context"]["organization_id"]
                if context["user_context"]
                else None,
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Log at appropriate level based on status code
            if response.status_code >= 500:
                logger.error(
                    f"Request completed with error: {response.status_code}",
                    extra=log_data,
                )
            elif response.status_code >= 400:
                logger.warning(
                    f"Request completed with warning: {response.status_code}",
                    extra=log_data,
                )
            else:
                logger.info(
                    f"Request completed: {response.status_code}", extra=log_data
                )

        except Exception as e:
            logger.error(f"Error logging request complete: {e}")

    async def _log_request_error(
        self, request: Request, error: Exception, context: Dict[str, Any]
    ):
        """Log request processing errors"""
        try:
            log_data = {
                "event": "request_error",
                "request_id": context["request_id"],
                "correlation_id": context["correlation_id"],
                "method": request.method,
                "path": request.url.path,
                "error_type": type(error).__name__,
                "error_message": str(error),
                "client_ip": context["request_info"]["client_ip"],
                "user_id": context["user_context"]["user_id"]
                if context["user_context"]
                else None,
                "organization_id": context["user_context"]["organization_id"]
                if context["user_context"]
                else None,
                "timestamp": datetime.utcnow().isoformat(),
            }

            logger.error(
                f"Request failed: {type(error).__name__}: {error}",
                extra=log_data,
                exc_info=True,
            )

        except Exception as e:
            logger.error(f"Error logging request error: {e}")

    async def _record_metrics(
        self,
        request: Request,
        response: Response,
        duration_ms: float,
        user_context: Optional[Dict[str, Any]],
    ):
        """Record request metrics"""
        try:
            labels = {
                "method": request.method,
                "path": request.url.path,
                "status_code": str(response.status_code),
                "service": self.monitoring_config.service_name,
            }

            # Add user context labels if available
            if user_context:
                if user_context.get("role"):
                    labels["user_role"] = user_context["role"]
                if user_context.get("organization_id"):
                    labels["organization_id"] = user_context["organization_id"]

            # Record HTTP request metrics
            await self.observability_manager.metrics_collector.increment_counter(
                "http_requests_total", labels=labels
            )

            await self.observability_manager.metrics_collector.observe_histogram(
                "http_request_duration_ms",
                duration_ms,
                labels={
                    "method": request.method,
                    "path": request.url.path,
                    "service": self.monitoring_config.service_name,
                },
            )

            # Record error metrics if applicable
            if response.status_code >= 400:
                await self.observability_manager.metrics_collector.increment_counter(
                    "http_errors_total",
                    labels={
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": str(response.status_code),
                        "service": self.monitoring_config.service_name,
                    },
                )

        except Exception as e:
            logger.error(f"Error recording metrics: {e}")

    async def _record_error_metrics(
        self,
        request: Request,
        error: Exception,
        duration_ms: float,
        user_context: Optional[Dict[str, Any]],
    ):
        """Record error metrics"""
        try:
            labels = {
                "method": request.method,
                "path": request.url.path,
                "error_type": type(error).__name__,
                "service": self.monitoring_config.service_name,
            }

            # Add user context labels if available
            if user_context:
                if user_context.get("role"):
                    labels["user_role"] = user_context["role"]
                if user_context.get("organization_id"):
                    labels["organization_id"] = user_context["organization_id"]

            # Record error metrics
            await self.observability_manager.metrics_collector.increment_counter(
                "http_exceptions_total", labels=labels
            )

            await self.observability_manager.metrics_collector.observe_histogram(
                "http_exception_duration_ms",
                duration_ms,
                labels={
                    "method": request.method,
                    "error_type": type(error).__name__,
                    "service": self.monitoring_config.service_name,
                },
            )

        except Exception as e:
            logger.error(f"Error recording error metrics: {e}")
