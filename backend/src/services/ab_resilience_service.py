"""
A/B Testing Resilience Service
Provides circuit breakers, retries, and fault tolerance for A/B testing operations
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import random

from ..core.config import settings
from ..cache.analytics_cache import analytics_cache

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, fail fast
    HALF_OPEN = "half_open"  # Testing if service has recovered


class RetryStrategy(Enum):
    """Retry strategies"""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_INTERVAL = "fixed_interval"
    IMMEDIATE = "immediate"


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5          # Number of failures before opening
    timeout: float = 60.0               # Seconds to wait before trying again
    success_threshold: int = 3          # Success count to close circuit
    monitor_period: float = 300.0       # Period to monitor for failures
    min_calls: int = 10                 # Minimum calls before breaking


@dataclass
class RetryConfig:
    """Configuration for retry logic"""
    max_attempts: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    retry_on: List[Exception] = field(default_factory=lambda: [Exception])


@dataclass
class ServiceMetrics:
    """Service performance metrics"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    average_response_time: float = 0.0
    last_failure_time: Optional[datetime] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0


class CircuitBreaker:
    """
    Circuit breaker implementation for fault tolerance
    """

    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = CircuitState.CLOSED
        self.metrics = ServiceMetrics()
        self.last_state_change = datetime.utcnow()
        self.failure_count = 0
        self.success_count = 0

    def is_call_allowed(self) -> bool:
        """Check if a call is allowed based on circuit state"""
        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.OPEN:
            # Check if timeout has passed
            if (datetime.utcnow() - self.last_state_change).total_seconds() > self.config.timeout:
                self.state = CircuitState.HALF_OPEN
                self.last_state_change = datetime.utcnow()
                logger.info(f"Circuit breaker {self.name} moved to HALF_OPEN state")
                return True
            return False
        elif self.state == CircuitState.HALF_OPEN:
            return True

        return False

    def record_success(self, response_time: float = 0.0):
        """Record a successful call"""
        self.metrics.total_calls += 1
        self.metrics.successful_calls += 1
        self.metrics.consecutive_failures = 0
        self.metrics.consecutive_successes += 1

        # Update average response time
        if self.metrics.total_calls == 1:
            self.metrics.average_response_time = response_time
        else:
            alpha = 0.1  # Exponential moving average factor
            self.metrics.average_response_time = (
                alpha * response_time +
                (1 - alpha) * self.metrics.average_response_time
            )

        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                self.last_state_change = datetime.utcnow()
                logger.info(f"Circuit breaker {self.name} moved to CLOSED state")

    def record_failure(self):
        """Record a failed call"""
        self.metrics.total_calls += 1
        self.metrics.failed_calls += 1
        self.metrics.consecutive_failures += 1
        self.metrics.consecutive_successes = 0
        self.metrics.last_failure_time = datetime.utcnow()

        if self.state == CircuitState.CLOSED:
            self.failure_count += 1
            if (self.failure_count >= self.config.failure_threshold and
                self.metrics.total_calls >= self.config.min_calls):
                self.state = CircuitState.OPEN
                self.last_state_change = datetime.utcnow()
                logger.warning(f"Circuit breaker {self.name} moved to OPEN state")
        elif self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.last_state_change = datetime.utcnow()
            logger.warning(f"Circuit breaker {self.name} moved back to OPEN state")

    def get_status(self) -> Dict[str, Any]:
        """Get current circuit breaker status"""
        return {
            "name": self.name,
            "state": self.state.value,
            "total_calls": self.metrics.total_calls,
            "successful_calls": self.metrics.successful_calls,
            "failed_calls": self.metrics.failed_calls,
            "success_rate": (
                self.metrics.successful_calls / self.metrics.total_calls
                if self.metrics.total_calls > 0 else 0
            ),
            "average_response_time": self.metrics.average_response_time,
            "consecutive_failures": self.metrics.consecutive_failures,
            "last_failure_time": (
                self.metrics.last_failure_time.isoformat()
                if self.metrics.last_failure_time else None
            ),
            "last_state_change": self.last_state_change.isoformat()
        }


class RetryHandler:
    """
    Retry handler with various backoff strategies
    """

    def __init__(self, config: RetryConfig):
        self.config = config

    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute function with retry logic
        """
        last_exception = None

        for attempt in range(self.config.max_attempts):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e

                # Check if this exception type should be retried
                if not any(isinstance(e, exc_type) for exc_type in self.config.retry_on):
                    raise e

                if attempt < self.config.max_attempts - 1:
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        f"Attempt {attempt + 1} failed for {func.__name__}. "
                        f"Retrying in {delay:.2f}s. Error: {str(e)}"
                    )
                    await asyncio.sleep(delay)

        # All attempts failed
        logger.error(
            f"All {self.config.max_attempts} attempts failed for {func.__name__}. "
            f"Last error: {str(last_exception)}"
        )
        raise last_exception

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay based on retry strategy"""
        if self.config.strategy == RetryStrategy.FIXED_INTERVAL:
            delay = self.config.base_delay
        elif self.config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.config.base_delay * (attempt + 1)
        elif self.config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.config.base_delay * (self.config.backoff_multiplier ** attempt)
        else:  # IMMEDIATE
            delay = 0

        # Apply maximum delay limit
        delay = min(delay, self.config.max_delay)

        # Add jitter if enabled
        if self.config.jitter and delay > 0:
            jitter_amount = delay * 0.1  # 10% jitter
            delay += random.uniform(-jitter_amount, jitter_amount)
            delay = max(0, delay)  # Ensure non-negative

        return delay


class ResilienceService:
    """
    Main resilience service providing circuit breakers and retry logic
    for A/B testing operations
    """

    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.retry_handlers: Dict[str, RetryHandler] = {}
        self._initialize_default_configs()

    def _initialize_default_configs(self):
        """Initialize default circuit breaker and retry configurations"""
        # Database operations
        self.register_circuit_breaker(
            "database",
            CircuitBreakerConfig(
                failure_threshold=5,
                timeout=30.0,
                success_threshold=3,
                min_calls=5
            )
        )
        self.register_retry_handler(
            "database",
            RetryConfig(
                max_attempts=3,
                strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
                base_delay=0.5,
                max_delay=10.0
            )
        )

        # Redis operations
        self.register_circuit_breaker(
            "redis",
            CircuitBreakerConfig(
                failure_threshold=3,
                timeout=60.0,
                success_threshold=2,
                min_calls=3
            )
        )
        self.register_retry_handler(
            "redis",
            RetryConfig(
                max_attempts=2,
                strategy=RetryStrategy.LINEAR_BACKOFF,
                base_delay=1.0,
                max_delay=5.0
            )
        )

        # Statistical analysis
        self.register_circuit_breaker(
            "statistical_analysis",
            CircuitBreakerConfig(
                failure_threshold=3,
                timeout=120.0,
                success_threshold=2,
                min_calls=2
            )
        )
        self.register_retry_handler(
            "statistical_analysis",
            RetryConfig(
                max_attempts=1,  # Don't retry expensive analysis operations
                strategy=RetryStrategy.IMMEDIATE
            )
        )

        # External API calls
        self.register_circuit_breaker(
            "external_api",
            CircuitBreakerConfig(
                failure_threshold=5,
                timeout=300.0,
                success_threshold=3,
                min_calls=10
            )
        )
        self.register_retry_handler(
            "external_api",
            RetryConfig(
                max_attempts=3,
                strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
                base_delay=2.0,
                max_delay=60.0
            )
        )

    def register_circuit_breaker(self, name: str, config: CircuitBreakerConfig):
        """Register a new circuit breaker"""
        self.circuit_breakers[name] = CircuitBreaker(name, config)
        logger.info(f"Registered circuit breaker: {name}")

    def register_retry_handler(self, name: str, config: RetryConfig):
        """Register a new retry handler"""
        self.retry_handlers[name] = RetryHandler(config)
        logger.info(f"Registered retry handler: {name}")

    async def execute_with_resilience(
        self,
        service_name: str,
        func: Callable,
        *args,
        use_circuit_breaker: bool = True,
        use_retry: bool = True,
        **kwargs
    ) -> Any:
        """
        Execute function with resilience patterns
        """
        start_time = time.time()

        # Circuit breaker check
        if use_circuit_breaker and service_name in self.circuit_breakers:
            circuit_breaker = self.circuit_breakers[service_name]
            if not circuit_breaker.is_call_allowed():
                raise Exception(f"Circuit breaker {service_name} is OPEN")

        # Execute with retry
        retry_handler = self.retry_handlers.get(service_name) if use_retry else None

        try:
            if retry_handler:
                result = await retry_handler.execute_with_retry(func, *args, **kwargs)
            else:
                result = await func(*args, **kwargs)

            # Record success
            response_time = time.time() - start_time
            if use_circuit_breaker and service_name in self.circuit_breakers:
                self.circuit_breakers[service_name].record_success(response_time)

            return result

        except Exception as e:
            # Record failure
            if use_circuit_breaker and service_name in self.circuit_breakers:
                self.circuit_breakers[service_name].record_failure()

            logger.error(f"Service {service_name} call failed: {str(e)}")
            raise

    async def execute_database_operation(self, func: Callable, *args, **kwargs) -> Any:
        """Execute database operation with resilience"""
        return await self.execute_with_resilience("database", func, *args, **kwargs)

    async def execute_redis_operation(self, func: Callable, *args, **kwargs) -> Any:
        """Execute Redis operation with resilience"""
        return await self.execute_with_resilience("redis", func, *args, **kwargs)

    async def execute_statistical_analysis(self, func: Callable, *args, **kwargs) -> Any:
        """Execute statistical analysis with resilience"""
        return await self.execute_with_resilience(
            "statistical_analysis", func, *args, **kwargs
        )

    async def execute_external_api_call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute external API call with resilience"""
        return await self.execute_with_resilience("external_api", func, *args, **kwargs)

    def get_circuit_breaker_status(self, name: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific circuit breaker"""
        if name in self.circuit_breakers:
            return self.circuit_breakers[name].get_status()
        return None

    def get_all_circuit_breaker_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all circuit breakers"""
        return {
            name: breaker.get_status()
            for name, breaker in self.circuit_breakers.items()
        }

    def reset_circuit_breaker(self, name: str) -> bool:
        """Reset a circuit breaker to closed state"""
        if name in self.circuit_breakers:
            breaker = self.circuit_breakers[name]
            breaker.state = CircuitState.CLOSED
            breaker.failure_count = 0
            breaker.success_count = 0
            breaker.last_state_change = datetime.utcnow()
            logger.info(f"Reset circuit breaker {name} to CLOSED state")
            return True
        return False

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check of all resilience components"""
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "circuit_breakers": {},
            "overall_health": "healthy"
        }

        degraded_count = 0
        unhealthy_count = 0

        for name, breaker in self.circuit_breakers.items():
            status = breaker.get_status()
            health_status["circuit_breakers"][name] = status

            if status["state"] == "open":
                unhealthy_count += 1
            elif status["consecutive_failures"] > 2:
                degraded_count += 1

        # Determine overall health
        if unhealthy_count > 0:
            health_status["overall_health"] = "unhealthy"
            health_status["status"] = "unhealthy"
        elif degraded_count > 0:
            health_status["overall_health"] = "degraded"
            health_status["status"] = "degraded"

        return health_status

    async def cleanup_old_metrics(self):
        """Clean up old metrics data"""
        # This could be implemented to clean up old metrics
        # or reset circuit breakers that have been stable for a long time
        pass


# Decorator for easy resilience application

def with_resilience(
    service_name: str,
    use_circuit_breaker: bool = True,
    use_retry: bool = True
):
    """
    Decorator to apply resilience patterns to functions
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            return await resilience_service.execute_with_resilience(
                service_name, func, *args,
                use_circuit_breaker=use_circuit_breaker,
                use_retry=use_retry,
                **kwargs
            )
        return wrapper
    return decorator


# Global service instance
resilience_service = ResilienceService()


# Context manager for circuit breaker operations

class CircuitBreakerContext:
    """Context manager for circuit breaker operations"""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.circuit_breaker = resilience_service.circuit_breakers.get(service_name)

    async def __aenter__(self):
        if self.circuit_breaker and not self.circuit_breaker.is_call_allowed():
            raise Exception(f"Circuit breaker {self.service_name} is OPEN")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.circuit_breaker:
            if exc_type is not None:
                self.circuit_breaker.record_failure()
            else:
                self.circuit_breaker.record_success()
        return False  # Don't suppress exceptions


# Usage example:
# async with CircuitBreakerContext("database") as cb:
#     # Database operation here
#     result = await some_database_function()