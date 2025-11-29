"""
Sentry Integration

Error tracking and performance monitoring integration with Sentry.
"""

import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.tracing import Transaction

from ..config.monitoring_config import get_monitoring_config

logger = logging.getLogger(__name__)


class SentryManager:
    """
    Manages Sentry integration for error tracking and performance monitoring
    """

    def __init__(self):
        self._initialized = False
        self._config = get_monitoring_config()

    def initialize(self, dsn: Optional[str] = None, **kwargs) -> None:
        """
        Initialize Sentry SDK

        Args:
            dsn: Sentry DSN (defaults to SENTRY_DSN environment variable)
            **kwargs: Additional Sentry configuration options
        """
        if self._initialized:
            logger.warning("Sentry already initialized")
            return

        try:
            sentry_dsn = dsn or os.getenv("SENTRY_DSN")
            if not sentry_dsn:
                logger.info("⚠️ Sentry DSN not provided, skipping Sentry initialization")
                return

            # Configure integrations
            integrations = [
                FastApiIntegration(auto_enabling_integrations=False),
                SqlalchemyIntegration(),
                RedisIntegration(),
                CeleryIntegration(),
                AsyncioIntegration(),
                LoggingIntegration(
                    level=logging.INFO,
                    event_level=logging.ERROR
                )
            ]

            # Configure Sentry
            sentry_config = {
                "dsn": sentry_dsn,
                "integrations": integrations,
                "environment": self._config.environment,
                "release": os.getenv("APP_VERSION", "1.0.0"),
                "traces_sample_rate": self._config.tracing.sampling_ratio,
                "auto_enabling_integrations": False,
                "send_default_pii": False,
                "attach_stacktrace": True,
                "request_bodies": "medium",
                "before_send": self._before_send,
                "before_breadcrumb": self._before_breadcrumb,
                "transport": self._create_transport(),
                **kwargs
            }

            # Add custom tags
            sentry_config["tags"] = {
                "service": self._config.service_name,
                "environment": self._config.environment,
                "version": os.getenv("APP_VERSION", "1.0.0")
            }

            sentry_sdk.init(**sentry_config)
            self._initialized = True

            logger.info(f"✅ Sentry initialized for {self._config.service_name} in {self._config.environment}")

        except Exception as e:
            logger.error(f"❌ Failed to initialize Sentry: {e}")
            raise

    def configure_scope(self, callback) -> None:
        """
        Configure Sentry scope with custom data

        Args:
            callback: Function that receives scope as parameter
        """
        if not self._initialized:
            return

        try:
            with sentry_sdk.configure_scope() as scope:
                callback(scope)
        except Exception as e:
            logger.error(f"Error configuring Sentry scope: {e}")

    def set_user(self, user_id: str, email: Optional[str] = None, **kwargs) -> None:
        """
        Set user context in Sentry

        Args:
            user_id: User ID
            email: User email
            **kwargs: Additional user attributes
        """
        if not self._initialized:
            return

        def configure_user(scope):
            scope.set_user({
                "id": user_id,
                "email": email,
                **kwargs
            })

        self.configure_scope(configure_user)

    def set_tag(self, key: str, value: str) -> None:
        """
        Set a tag in Sentry

        Args:
            key: Tag key
            value: Tag value
        """
        if not self._initialized:
            return

        sentry_sdk.set_tag(key, value)

    def set_extra(self, key: str, value: Any) -> None:
        """
        Set extra data in Sentry

        Args:
            key: Data key
            value: Data value
        """
        if not self._initialized:
            return

        sentry_sdk.set_extra(key, value)

    def add_breadcrumb(self,
                      message: str,
                      category: Optional[str] = None,
                      level: Optional[str] = None,
                      **kwargs) -> None:
        """
        Add a breadcrumb to Sentry

        Args:
            message: Breadcrumb message
            category: Breadcrumb category
            level: Breadcrumb level
            **kwargs: Additional breadcrumb data
        """
        if not self._initialized:
            return

        breadcrumb = {
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            **kwargs
        }

        if category:
            breadcrumb["category"] = category
        if level:
            breadcrumb["level"] = level

        sentry_sdk.add_breadcrumb(breadcrumb)

    def capture_exception(self, exception: Exception, **kwargs) -> Optional[str]:
        """
        Capture an exception in Sentry

        Args:
            exception: Exception to capture
            **kwargs: Additional context

        Returns:
            Event ID if captured, None otherwise
        """
        if not self._initialized:
            return None

        try:
            return sentry_sdk.capture_exception(exception, **kwargs)
        except Exception as e:
            logger.error(f"Error capturing exception in Sentry: {e}")
            return None

    def capture_message(self, message: str, level: str = "info", **kwargs) -> Optional[str]:
        """
        Capture a message in Sentry

        Args:
            message: Message to capture
            level: Message level
            **kwargs: Additional context

        Returns:
            Event ID if captured, None otherwise
        """
        if not self._initialized:
            return None

        try:
            return sentry_sdk.capture_message(message, level, **kwargs)
        except Exception as e:
            logger.error(f"Error capturing message in Sentry: {e}")
            return None

    def start_transaction(self, name: str, op: Optional[str] = None, **kwargs) -> Optional[Transaction]:
        """
        Start a Sentry transaction

        Args:
            name: Transaction name
            op: Operation type
            **kwargs: Additional transaction options

        Returns:
            Transaction object or None
        """
        if not self._initialized:
            return None

        try:
            return sentry_sdk.start_transaction(
                name=name,
                op=op,
                **kwargs
            )
        except Exception as e:
            logger.error(f"Error starting Sentry transaction: {e}")
            return None

    def flush(self, timeout: float = 2.0) -> None:
        """
        Flush pending events to Sentry

        Args:
            timeout: Flush timeout in seconds
        """
        if not self._initialized:
            return

        try:
            sentry_sdk.flush(timeout)
        except Exception as e:
            logger.error(f"Error flushing Sentry: {e}")

    def _before_send(self, event: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process event before sending to Sentry

        Args:
            event: Sentry event
            hint: Event hint

        Returns:
            Modified event or None to drop
        """
        try:
            # Filter out sensitive data
            if "request" in event:
                self._sanitize_request_data(event["request"])

            # Add custom context
            event["tags"]["service"] = self._config.service_name
            event["tags"]["environment"] = self._config.environment

            # Filter out certain exceptions
            exception = event.get("exception", {}).get("values", [{}])[0]
            if exception and self._should_ignore_exception(exception):
                return None

            return event

        except Exception as e:
            logger.error(f"Error in before_send: {e}")
            return event

    def _before_breadcrumb(self, breadcrumb: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process breadcrumb before adding to Sentry

        Args:
            breadcrumb: Breadcrumb data
            hint: Breadcrumb hint

        Returns:
            Modified breadcrumb or None to drop
        """
        try:
            # Filter out noisy breadcrumbs
            if breadcrumb.get("category") in ["http", "navigation"]:
                # Only keep HTTP breadcrumbs for errors
                if breadcrumb.get("level") != "error":
                    return None

            # Sanitize breadcrumb data
            if "data" in breadcrumb:
                self._sanitize_breadcrumb_data(breadcrumb["data"])

            return breadcrumb

        except Exception as e:
            logger.error(f"Error in before_breadcrumb: {e}")
            return breadcrumb

    def _sanitize_request_data(self, request_data: Dict[str, Any]) -> None:
        """Sanitize sensitive request data"""
        if "headers" in request_data:
            sensitive_headers = ["authorization", "cookie", "x-api-key"]
            for header in sensitive_headers:
                if header.lower() in request_data["headers"]:
                    request_data["headers"][header] = "[FILTERED]"

        if "data" in request_data:
            # Filter sensitive fields from request data
            sensitive_fields = ["password", "token", "secret", "key", "credential"]
            self._filter_sensitive_fields(request_data["data"], sensitive_fields)

    def _sanitize_breadcrumb_data(self, data: Dict[str, Any]) -> None:
        """Sanitize sensitive breadcrumb data"""
        sensitive_fields = ["password", "token", "secret", "key", "authorization"]
        self._filter_sensitive_fields(data, sensitive_fields)

    def _filter_sensitive_fields(self, data: Any, sensitive_fields: list) -> None:
        """Recursively filter sensitive fields from data"""
        if isinstance(data, dict):
            for key, value in data.items():
                if any(field in key.lower() for field in sensitive_fields):
                    data[key] = "[FILTERED]"
                elif isinstance(value, (dict, list)):
                    self._filter_sensitive_fields(value, sensitive_fields)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, (dict, list)):
                    self._filter_sensitive_fields(item, sensitive_fields)

    def _should_ignore_exception(self, exception: Dict[str, Any]) -> bool:
        """Determine if an exception should be ignored"""
        ignored_exceptions = [
            "KeyboardInterrupt",
            "SystemExit",
            "ConnectionError",
            "TimeoutError"
        ]

        exception_type = exception.get("type", "")
        return any(ignored in exception_type for ignored in ignored_exceptions)

    def _create_transport(self):
        """Create custom transport for Sentry"""
        class CustomTransport(sentry_sdk.transport.HttpTransport):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)

            def _send_event(self, event):
                # Add custom headers or modify event before sending
                return super()._send_event(event)

        return CustomTransport


# Global Sentry manager instance
_sentry_manager: Optional[SentryManager] = None


def get_sentry_manager() -> SentryManager:
    """Get the global Sentry manager instance"""
    global _sentry_manager
    if _sentry_manager is None:
        _sentry_manager = SentryManager()
    return _sentry_manager


def init_sentry(dsn: Optional[str] = None, **kwargs) -> None:
    """
    Initialize Sentry for the application

    Args:
        dsn: Sentry DSN
        **kwargs: Additional Sentry configuration
    """
    manager = get_sentry_manager()
    manager.initialize(dsn, **kwargs)


# Decorators for Sentry integration
def sentry_trace(operation_name: Optional[str] = None):
    """
    Decorator to trace function execution with Sentry

    Args:
        operation_name: Name for the operation
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            manager = get_sentry_manager()
            if not manager._initialized:
                return func(*args, **kwargs)

            name = operation_name or f"{func.__module__}.{func.__name__}"
            transaction = manager.start_transaction(name, "function")

            try:
                result = func(*args, **kwargs)
                if transaction:
                    transaction.set_status("ok")
                return result
            except Exception as e:
                if transaction:
                    transaction.set_status("internal_error")
                    manager.capture_exception(e)
                raise
            finally:
                if transaction:
                    transaction.finish()

        return wrapper
    return decorator


def capture_sentry_exception(message: Optional[str] = None):
    """
    Decorator to automatically capture exceptions in Sentry

    Args:
        message: Optional custom message
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                manager = get_sentry_manager()
                if manager._initialized:
                    if message:
                        manager.capture_exception(e, extra={"custom_message": message})
                    else:
                        manager.capture_exception(e)
                raise

        return wrapper
    return decorator