"""
Monitoring Service Exceptions

Custom exceptions for monitoring and observability services.
"""


class ObservabilityError(Exception):
    """Base exception for observability services"""
    pass


class MetricsError(ObservabilityError):
    """Exception for metrics collection and processing"""
    pass


class TracingError(ObservabilityError):
    """Exception for distributed tracing"""
    pass


class LoggingError(ObservabilityError):
    """Exception for log aggregation and processing"""
    pass


class AlertingError(ObservabilityError):
    """Exception for alert generation and notification"""
    pass


class HealthCheckError(ObservabilityError):
    """Exception for health check operations"""
    pass


class ConfigurationError(ObservabilityError):
    """Exception for configuration issues"""
    pass


class ServiceUnavailableError(ObservabilityError):
    """Exception when a monitoring service is unavailable"""
    pass


class ValidationError(ObservabilityError):
    """Exception for data validation errors"""
    pass


class AuthenticationError(ObservabilityError):
    """Exception for authentication failures"""
    pass


class AuthorizationError(ObservabilityError):
    """Exception for authorization failures"""
    pass