"""
Comprehensive error handling and retry logic for WebSocket connections
Includes circuit breaker patterns, exponential backoff, and graceful degradation
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Callable, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import uuid
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class ErrorSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ErrorCategory(Enum):
    NETWORK = "network"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    VALIDATION = "validation"
    SYSTEM = "system"
    BUSINESS_LOGIC = "business_logic"
    TEMPORARY = "temporary"
    PERMANENT = "permanent"

class CircuitBreakerState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject all requests
    HALF_OPEN = "half_open"  # Testing if service has recovered

@dataclass
class ErrorMetrics:
    """Error tracking metrics"""
    total_errors: int = 0
    errors_by_category: Dict[str, int] = field(default_factory=dict)
    errors_by_severity: Dict[str, int] = field(default_factory=dict)
    recent_errors: List[Dict[str, Any]] = field(default_factory=list)
    last_error_time: Optional[datetime] = None
    consecutive_errors: int = 0

@dataclass
class RetryConfig:
    """Retry configuration"""
    max_attempts: int = 3
    base_delay_ms: float = 1000
    max_delay_ms: float = 30000
    exponential_base: float = 2.0
    jitter_factor: float = 0.1
    retryable_categories: List[ErrorCategory] = field(default_factory=lambda: [
        ErrorCategory.NETWORK,
        ErrorCategory.TIMEOUT,
        ErrorCategory.TEMPORARY,
        ErrorCategory.SYSTEM
    ])

@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""
    failure_threshold: int = 5  # Open after N failures
    timeout_seconds: int = 60   # Stay open for N seconds
    success_threshold: int = 2  # Close after N successes in half-open state
    monitoring_window_seconds: int = 300  # Consider errors in this window

class WebSocketErrorHandler:
    """
    Comprehensive error handling system for WebSocket connections
    """

    def __init__(self, retry_config: Optional[RetryConfig] = None):
        self.retry_config = retry_config or RetryConfig()
        self.error_metrics = ErrorMetrics()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}

        # Error handlers registry
        self.error_handlers: Dict[ErrorCategory, List[Callable]] = {
            category: [] for category in ErrorCategory
        }

        # Global error handler
        self.global_error_handlers: List[Callable] = []

        # Fallback handlers
        self.fallback_handlers: Dict[str, Callable] = {}

    async def handle_websocket_error(
        self,
        connection_id: str,
        error: Exception,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Handle WebSocket error with comprehensive logic

        Returns:
            Tuple of (should_retry, response_message)
        """
        try:
            # Categorize and assess error
            error_info = self._analyze_error(error, context)

            # Update metrics
            self._update_metrics(error_info)

            # Check circuit breaker
            service_name = error_info.get('service', 'default')
            if not await self._check_circuit_breaker(service_name):
                logger.warning(f"Circuit breaker open for service: {service_name}")
                return False, self._create_circuit_breaker_response(error_info)

            # Determine retry eligibility
            should_retry = self._should_retry_error(error_info)

            # Execute error handlers
            await self._execute_error_handlers(error_info)

            # Log error appropriately
            self._log_error(error_info)

            # Create error response
            error_response = self._create_error_response(error_info)

            # Update circuit breaker
            await self._update_circuit_breaker(service_name, not should_retry)

            return should_retry, error_response

        except Exception as e:
            logger.error(f"Error in error handler: {e}")
            return False, {
                'type': 'error',
                'error_code': 'INTERNAL_ERROR',
                'error_message': 'Internal error handling failed',
                'error_category': ErrorCategory.SYSTEM.value,
                'severity': ErrorSeverity.HIGH.value,
                'retry_after': 5.0
            }

    def register_error_handler(
        self,
        category: ErrorCategory,
        handler: Callable[[Dict[str, Any]], Any]
    ):
        """Register a handler for specific error category"""
        self.error_handlers[category].append(handler)

    def register_global_error_handler(self, handler: Callable[[Dict[str, Any]], Any]):
        """Register a global error handler"""
        self.global_error_handlers.append(handler)

    def register_fallback_handler(
        self,
        operation: str,
        handler: Callable[[Dict[str, Any]], Any]
    ):
        """Register a fallback handler for specific operations"""
        self.fallback_handlers[operation] = handler

    async def execute_with_retry(
        self,
        operation: str,
        func: Callable,
        *args,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Any:
        """
        Execute operation with automatic retry logic
        """
        last_error = None
        attempt = 0

        while attempt < self.retry_config.max_attempts:
            attempt += 1

            try:
                # Check circuit breaker before attempting
                if not await self._check_circuit_breaker(operation):
                    raise Exception(f"Circuit breaker open for operation: {operation}")

                # Execute the function
                result = await func(*args, **kwargs)

                # Success - reset circuit breaker
                await self._update_circuit_breaker(operation, True)

                return result

            except Exception as e:
                last_error = e
                error_info = self._analyze_error(e, context)

                # Check if error is retryable
                if not self._should_retry_error(error_info):
                    break

                # Check if we should continue retrying
                if attempt >= self.retry_config.max_attempts:
                    break

                # Calculate delay
                delay_ms = self._calculate_retry_delay(attempt)

                logger.warning(
                    f"Operation {operation} failed (attempt {attempt}/{self.retry_config.max_attempts}), "
                    f"retrying in {delay_ms:.1f}ms. Error: {str(e)}"
                )

                await asyncio.sleep(delay_ms / 1000)

        # All retries failed, try fallback
        if operation in self.fallback_handlers:
            try:
                logger.info(f"Executing fallback for operation: {operation}")
                return await self.fallback_handlers[operation]({
                    'error': last_error,
                    'context': context,
                    'attempts': attempt
                })
            except Exception as fallback_error:
                logger.error(f"Fallback handler failed for {operation}: {fallback_error}")

        # Re-raise the last error
        raise last_error

    def get_error_metrics(self) -> Dict[str, Any]:
        """Get current error metrics"""
        return {
            'total_errors': self.error_metrics.total_errors,
            'errors_by_category': dict(self.error_metrics.errors_by_category),
            'errors_by_severity': dict(self.error_metrics.errors_by_severity),
            'recent_errors_count': len(self.error_metrics.recent_errors),
            'last_error_time': self.error_metrics.last_error_time.isoformat() if self.error_metrics.last_error_time else None,
            'consecutive_errors': self.error_metrics.consecutive_errors,
            'active_circuit_breakers': len([cb for cb in self.circuit_breakers.values() if cb.state == CircuitBreakerState.OPEN])
        }

    # Private methods

    def _analyze_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Analyze and categorize error"""
        error_str = str(error).lower()
        error_type = type(error).__name__

        # Determine error category
        category = self._categorize_error(error_str, error_type)

        # Determine severity
        severity = self._determine_severity(error_str, category)

        # Check if retryable
        is_retryable = category in self.retry_config.retryable_categories

        return {
            'error': error,
            'error_type': error_type,
            'error_message': str(error),
            'error_category': category.value,
            'severity': severity.value,
            'is_retryable': is_retryable,
            'timestamp': datetime.utcnow(),
            'context': context or {},
            'service': context.get('service', 'default') if context else 'default',
            'operation': context.get('operation', 'unknown') if context else 'unknown'
        }

    def _categorize_error(self, error_str: str, error_type: str) -> ErrorCategory:
        """Categorize error based on message content and type"""
        if any(keyword in error_str for keyword in ['connection', 'network', 'timeout', 'unreachable']):
            if 'timeout' in error_str or error_type == 'TimeoutError':
                return ErrorCategory.TIMEOUT
            return ErrorCategory.NETWORK

        elif any(keyword in error_str for keyword in ['auth', 'unauthorized', 'forbidden', 'jwt', 'token']):
            if 'forbidden' in error_str:
                return ErrorCategory.AUTHORIZATION
            return ErrorCategory.AUTHENTICATION

        elif 'rate limit' in error_str or error_type == 'RateLimitExceeded':
            return ErrorCategory.RATE_LIMIT

        elif 'validation' in error_str or 'invalid' in error_str or error_type == 'ValidationError':
            return ErrorCategory.VALIDATION

        elif any(keyword in error_str for keyword in ['temporary', 'retry later', 'service unavailable']):
            return ErrorCategory.TEMPORARY

        elif any(keyword in error_str for keyword in ['permanent', 'not found', 'access denied']):
            return ErrorCategory.PERMANENT

        elif any(keyword in error_str for keyword in ['database', 'storage', 'file']):
            return ErrorCategory.BUSINESS_LOGIC

        else:
            return ErrorCategory.SYSTEM

    def _determine_severity(self, error_str: str, category: ErrorCategory) -> ErrorSeverity:
        """Determine error severity based on category and content"""
        if category in [ErrorCategory.AUTHENTICATION, ErrorCategory.AUTHORIZATION]:
            return ErrorSeverity.MEDIUM

        elif category == ErrorCategory.RATE_LIMIT:
            return ErrorSeverity.LOW

        elif category in [ErrorCategory.NETWORK, ErrorCategory.TIMEOUT, ErrorCategory.TEMPORARY]:
            return ErrorSeverity.MEDIUM

        elif category in [ErrorCategory.SYSTEM, ErrorCategory.PERMANENT]:
            return ErrorSeverity.HIGH

        elif any(keyword in error_str for keyword in ['critical', 'fatal', 'emergency']):
            return ErrorSeverity.CRITICAL

        else:
            return ErrorSeverity.LOW

    def _should_retry_error(self, error_info: Dict[str, Any]) -> bool:
        """Determine if error should be retried"""
        return (
            error_info.get('is_retryable', False) and
            error_info.get('consecutive_errors', 0) < self.retry_config.max_attempts
        )

    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay with jitter"""
        # Exponential backoff
        base_delay = self.retry_config.base_delay_ms
        exponential_delay = base_delay * (self.retry_config.exponential_base ** (attempt - 1))

        # Cap at maximum delay
        capped_delay = min(exponential_delay, self.retry_config.max_delay_ms)

        # Add jitter
        jitter = capped_delay * self.retry_config.jitter_factor * (2 * time.time() % 1 - 0.5)

        return max(0, capped_delay + jitter)

    def _update_metrics(self, error_info: Dict[str, Any]):
        """Update error metrics"""
        self.error_metrics.total_errors += 1
        self.error_metrics.last_error_time = datetime.utcnow()
        self.error_metrics.consecutive_errors += 1

        category = error_info['error_category']
        severity = error_info['severity']

        self.error_metrics.errors_by_category[category] = self.error_metrics.errors_by_category.get(category, 0) + 1
        self.error_metrics.errors_by_severity[severity] = self.error_metrics.errors_by_severity.get(severity, 0) + 1

        # Add to recent errors (keep last 100)
        self.error_metrics.recent_errors.append({
            'timestamp': error_info['timestamp'].isoformat(),
            'category': category,
            'severity': severity,
            'message': error_info['error_message']
        })

        if len(self.error_metrics.recent_errors) > 100:
            self.error_metrics.recent_errors = self.error_metrics.recent_errors[-100:]

    def _log_error(self, error_info: Dict[str, Any]):
        """Log error with appropriate level"""
        severity = error_info['severity']
        category = error_info['error_category']
        message = error_info['error_message']

        log_message = (
            f"{category.upper()} error: {message} "
            f"(severity: {severity}, operation: {error_info.get('operation', 'unknown')})"
        )

        if severity == ErrorSeverity.CRITICAL.value:
            logger.critical(log_message)
        elif severity == ErrorSeverity.HIGH.value:
            logger.error(log_message)
        elif severity == ErrorSeverity.MEDIUM.value:
            logger.warning(log_message)
        else:
            logger.info(log_message)

    async def _execute_error_handlers(self, error_info: Dict[str, Any]):
        """Execute registered error handlers"""
        category = ErrorCategory(error_info['error_category'])

        # Execute category-specific handlers
        for handler in self.error_handlers[category]:
            try:
                await handler(error_info)
            except Exception as e:
                logger.error(f"Error in category-specific handler: {e}")

        # Execute global handlers
        for handler in self.global_error_handlers:
            try:
                await handler(error_info)
            except Exception as e:
                logger.error(f"Error in global error handler: {e}")

    def _create_error_response(self, error_info: Dict[str, Any]) -> Dict[str, Any]:
        """Create standardized error response"""
        response = {
            'type': 'error',
            'error_code': f"{error_info['error_category'].upper()}_{error_info['error_type'].upper()}",
            'error_message': error_info['error_message'],
            'error_category': error_info['error_category'],
            'severity': error_info['severity'],
            'timestamp': error_info['timestamp'].isoformat()
        }

        # Add retry information
        if error_info.get('is_retryable', False):
            response['retry_after'] = self.retry_config.base_delay_ms / 1000
            response['max_retries'] = self.retry_config.max_attempts

        # Add context information
        if error_info.get('context'):
            response['context'] = error_info['context']

        return response

    def _create_circuit_breaker_response(self, error_info: Dict[str, Any]) -> Dict[str, Any]:
        """Create circuit breaker open response"""
        return {
            'type': 'error',
            'error_code': 'CIRCUIT_BREAKER_OPEN',
            'error_message': 'Service temporarily unavailable due to high error rate',
            'error_category': ErrorCategory.SYSTEM.value,
            'severity': ErrorSeverity.HIGH.value,
            'retry_after': 60.0,
            'timestamp': datetime.utcnow().isoformat()
        }

    async def _check_circuit_breaker(self, service_name: str) -> bool:
        """Check if circuit breaker allows requests"""
        if service_name not in self.circuit_breakers:
            self.circuit_breakers[service_name] = CircuitBreaker(service_name)

        return self.circuit_breakers[service_name].can_request()

    async def _update_circuit_breaker(self, service_name: str, success: bool):
        """Update circuit breaker state"""
        if service_name not in self.circuit_breakers:
            self.circuit_breakers[service_name] = CircuitBreaker(service_name)

        if success:
            self.circuit_breakers[service_name].record_success()
            self.error_metrics.consecutive_errors = 0
        else:
            self.circuit_breakers[service_name].record_failure()

class CircuitBreaker:
    """
    Circuit breaker implementation for fault tolerance
    """

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()

        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_state_change: Optional[datetime] = None

    def can_request(self) -> bool:
        """Check if request should be allowed"""
        if self.state == CircuitBreakerState.CLOSED:
            return True

        elif self.state == CircuitBreakerState.OPEN:
            # Check if timeout has passed
            if (datetime.utcnow() - self.last_failure_time).seconds >= self.config.timeout_seconds:
                self.state = CircuitBreakerState.HALF_OPEN
                self.success_count = 0
                return True
            return False

        elif self.state == CircuitBreakerState.HALF_OPEN:
            return True

        return False

    def record_success(self):
        """Record a successful request"""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                self.last_state_change = datetime.utcnow()
        elif self.state == CircuitBreakerState.CLOSED:
            # Reset failure count on success
            self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self):
        """Record a failed request"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        if self.state == CircuitBreakerState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitBreakerState.OPEN
                self.last_state_change = datetime.utcnow()

        elif self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN
            self.last_state_change = datetime.utcnow()

# Global error handler instance
_websocket_error_handler: Optional[WebSocketErrorHandler] = None

def get_websocket_error_handler() -> WebSocketErrorHandler:
    """Get or create the global WebSocket error handler"""
    global _websocket_error_handler
    if _websocket_error_handler is None:
        _websocket_error_handler = WebSocketErrorHandler()
    return _websocket_error_handler

# Error handling decorators and context managers

@asynccontextmanager
async def websocket_error_context(operation: str, context: Optional[Dict[str, Any]] = None):
    """
    Context manager for automatic WebSocket error handling
    """
    error_handler = get_websocket_error_handler()

    try:
        yield
    except Exception as e:
        should_retry, error_response = await error_handler.handle_websocket_error(
            connection_id=context.get('connection_id', 'unknown') if context else 'unknown',
            error=e,
            context=context
        )

        if not should_retry:
            # Re-raise if not retryable
            raise

def handle_websocket_errors(
    category: ErrorCategory = None,
    fallback_operation: Optional[str] = None
):
    """
    Decorator for automatic WebSocket error handling
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            error_handler = get_websocket_error_handler()
            operation = fallback_operation or func.__name__

            try:
                return await error_handler.execute_with_retry(
                    operation=operation,
                    func=func,
                    *args,
                    **kwargs
                )
            except Exception as e:
                # Final error handling
                logger.error(f"Operation {operation} failed after all retries: {e}")
                raise

        return wrapper
    return decorator