"""
Analytics-specific exceptions and error handling
Provides standardized error responses for T3 analytics system
"""

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import HTTPException, status


class AnalyticsException(Exception):
    """Base exception for analytics-related errors"""

    def __init__(
        self,
        message: str,
        error_code: str = "ANALYTICS_ERROR",
        details: Optional[Dict[str, Any]] = None,
        user_friendly_message: Optional[str] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.user_friendly_message = user_friendly_message or message
        self.timestamp = datetime.utcnow()
        super().__init__(self.message)


class PermissionDeniedException(AnalyticsException):
    """Raised when user lacks required permissions for analytics access"""

    def __init__(
        self,
        required_permission: str,
        user_role: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        message = f"Access denied. Required permission: {required_permission}, User role: {user_role}"
        super().__init__(
            message=message,
            error_code="PERMISSION_DENIED",
            details=details
            or {"required_permission": required_permission, "user_role": user_role},
            user_friendly_message="You don't have permission to access this analytics feature.",
        )


class RateLimitExceededException(AnalyticsException):
    """Raised when analytics API rate limit is exceeded"""

    def __init__(
        self,
        limit: int,
        window: int,
        retry_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        message = f"Rate limit exceeded. Maximum {limit} requests per {window} seconds."
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            details=details
            or {"limit": limit, "window": window, "retry_after": retry_after},
            user_friendly_message=f"You've exceeded the rate limit. Maximum {limit} requests per {window} seconds.",
        )


class DataValidationException(AnalyticsException):
    """Raised when analytics data validation fails"""

    def __init__(
        self,
        validation_errors: Dict[str, list],
        details: Optional[Dict[str, Any]] = None,
    ):
        message = f"Data validation failed: {validation_errors}"
        super().__init__(
            message=message,
            error_code="DATA_VALIDATION_ERROR",
            details=details or {"validation_errors": validation_errors},
            user_friendly_message="Invalid data provided. Please check your input and try again.",
        )


class InsufficientDataException(AnalyticsException):
    """Raised when there's insufficient data for analytics calculations"""

    def __init__(
        self,
        data_type: str,
        minimum_required: int,
        actual_count: int,
        details: Optional[Dict[str, Any]] = None,
    ):
        message = f"Insufficient data for {data_type}. Required: {minimum_required}, Available: {actual_count}"
        super().__init__(
            message=message,
            error_code="INSUFFICIENT_DATA",
            details=details
            or {
                "data_type": data_type,
                "minimum_required": minimum_required,
                "actual_count": actual_count,
            },
            user_friendly_message=f"Not enough data available to generate this analysis. Need at least {minimum_required} data points.",
        )


class AnalyticsTimeoutException(AnalyticsException):
    """Raised when analytics operation times out"""

    def __init__(
        self,
        operation: str,
        timeout_seconds: int,
        details: Optional[Dict[str, Any]] = None,
    ):
        message = f"Analytics operation '{operation}' timed out after {timeout_seconds} seconds"
        super().__init__(
            message=message,
            error_code="ANALYTICS_TIMEOUT",
            details=details
            or {"operation": operation, "timeout_seconds": timeout_seconds},
            user_friendly_message="The analytics operation took too long to complete. Please try with a smaller date range or fewer parameters.",
        )


class ExportFailedException(AnalyticsException):
    """Raised when analytics export fails"""

    def __init__(
        self,
        export_format: str,
        error_reason: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        message = f"Export to {export_format} failed: {error_reason}"
        super().__init__(
            message=message,
            error_code="EXPORT_FAILED",
            details=details
            or {"export_format": export_format, "error_reason": error_reason},
            user_friendly_message=f"Failed to export data in {export_format} format. Please try again or contact support.",
        )


class ConfigurationException(AnalyticsException):
    """Raised when analytics configuration is invalid"""

    def __init__(
        self,
        config_key: str,
        config_value: Any,
        reason: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        message = f"Invalid analytics configuration: {config_key} = {config_value}. Reason: {reason}"
        super().__init__(
            message=message,
            error_code="CONFIGURATION_ERROR",
            details=details
            or {
                "config_key": config_key,
                "config_value": str(config_value),
                "reason": reason,
            },
            user_friendly_message="Analytics system configuration error. Please contact your administrator.",
        )


class DataRetentionException(AnalyticsException):
    """Raised when data retention policies prevent access"""

    def __init__(
        self,
        data_type: str,
        retention_period: str,
        requested_date_range: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        message = f"Data access denied due to retention policy. {data_type} data retention: {retention_period}"
        super().__init__(
            message=message,
            error_code="DATA_RETENTION_POLICY",
            details=details
            or {
                "data_type": data_type,
                "retention_period": retention_period,
                "requested_date_range": requested_date_range,
            },
            user_friendly_message="Requested data is no longer available due to data retention policies.",
        )


class AnalyticsServiceException(AnalyticsException):
    """Raised when an external analytics service is unavailable"""

    def __init__(
        self,
        service_name: str,
        error_message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        message = f"Analytics service '{service_name}' error: {error_message}"
        super().__init__(
            message=message,
            error_code="SERVICE_ERROR",
            details=details
            or {"service_name": service_name, "service_error": error_message},
            user_friendly_message="Analytics service temporarily unavailable. Please try again later.",
        )


class CacheError(AnalyticsException):
    """Raised when cache operations fail"""

    def __init__(
        self,
        operation: str,
        cache_key: str,
        error_reason: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        message = f"Cache {operation} failed for key '{cache_key}': {error_reason}"
        super().__init__(
            message=message,
            error_code="CACHE_ERROR",
            details=details
            or {
                "operation": operation,
                "cache_key": cache_key,
                "error_reason": error_reason,
            },
            user_friendly_message="Analytics cache temporarily unavailable. Please try again later.",
        )


class CacheMissError(AnalyticsException):
    """Raised when requested data is not found in cache"""

    def __init__(
        self, cache_key: str, data_type: str, details: Optional[Dict[str, Any]] = None
    ):
        message = f"Cache miss for {data_type}: {cache_key}"
        super().__init__(
            message=message,
            error_code="CACHE_MISS",
            details=details or {"cache_key": cache_key, "data_type": data_type},
            user_friendly_message="Analytics data not found in cache. Refreshing data...",
        )


# HTTP Exception factory functions


def create_permission_denied_http_exception(
    required_permission: str, user_role: str
) -> HTTPException:
    """Create HTTP exception for permission denied errors"""
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error_code": "PERMISSION_DENIED",
            "message": f"Access denied. Required permission: {required_permission}",
            "user_friendly_message": "You don't have permission to access this analytics feature.",
            "details": {
                "required_permission": required_permission,
                "user_role": user_role,
            },
        },
    )


def create_rate_limit_http_exception(
    limit: int, window: int, retry_after: Optional[int] = None
) -> HTTPException:
    """Create HTTP exception for rate limit exceeded errors"""
    headers = {}
    if retry_after:
        headers["Retry-After"] = str(retry_after)

    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={
            "error_code": "RATE_LIMIT_EXCEEDED",
            "message": f"Rate limit exceeded. Maximum {limit} requests per {window} seconds.",
            "user_friendly_message": f"You've exceeded the rate limit. Maximum {limit} requests per {window} seconds.",
            "details": {"limit": limit, "window": window, "retry_after": retry_after},
        },
        headers=headers,
    )


def create_insufficient_data_http_exception(
    data_type: str, minimum_required: int, actual_count: int
) -> HTTPException:
    """Create HTTP exception for insufficient data errors"""
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "error_code": "INSUFFICIENT_DATA",
            "message": f"Insufficient data for {data_type}. Required: {minimum_required}, Available: {actual_count}",
            "user_friendly_message": f"Not enough data available to generate this analysis. Need at least {minimum_required} data points.",
            "details": {
                "data_type": data_type,
                "minimum_required": minimum_required,
                "actual_count": actual_count,
            },
        },
    )


def create_analytics_timeout_http_exception(
    operation: str, timeout_seconds: int
) -> HTTPException:
    """Create HTTP exception for analytics timeout errors"""
    return HTTPException(
        status_code=status.HTTP_408_REQUEST_TIMEOUT,
        detail={
            "error_code": "ANALYTICS_TIMEOUT",
            "message": f"Analytics operation '{operation}' timed out after {timeout_seconds} seconds",
            "user_friendly_message": "The analytics operation took too long to complete. Please try with a smaller date range or fewer parameters.",
            "details": {"operation": operation, "timeout_seconds": timeout_seconds},
        },
    )


def create_export_failed_http_exception(
    export_format: str, error_reason: str
) -> HTTPException:
    """Create HTTP exception for export failed errors"""
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={
            "error_code": "EXPORT_FAILED",
            "message": f"Export to {export_format} failed: {error_reason}",
            "user_friendly_message": f"Failed to export data in {export_format} format. Please try again or contact support.",
            "details": {"export_format": export_format, "error_reason": error_reason},
        },
    )
