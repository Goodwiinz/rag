"""
Circuit Breaker Pattern for External Service Calls

Provides protection against cascading failures when external services
(Neo4j, Qdrant, Cohere) are unavailable or slow.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class ServiceUnavailableError(Exception):
    """Raised when circuit breaker is open."""

    def __init__(self, service_name: str, message: str = None):
        self.service_name = service_name
        self.message = message or f"{service_name} service is currently unavailable"
        super().__init__(self.message)


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker monitoring."""

    service_name: str
    state: CircuitState
    failure_count: int
    success_count: int
    last_failure_time: Optional[float]
    last_success_time: Optional[float]
    total_calls: int
    rejected_calls: int


class ServiceCircuitBreaker:
    """
    Circuit breaker for external service calls.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service is failing, requests are rejected immediately
    - HALF_OPEN: Testing if service has recovered

    Transitions:
    - CLOSED -> OPEN: When failure_count >= failure_threshold
    - OPEN -> HALF_OPEN: After recovery_timeout seconds
    - HALF_OPEN -> CLOSED: After half_open_max_calls successful calls
    - HALF_OPEN -> OPEN: On any failure
    """

    def __init__(
        self,
        service_name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
        excluded_exceptions: tuple = (),
    ):
        """
        Initialize circuit breaker.

        Args:
            service_name: Name of the service (for logging)
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before testing recovery
            half_open_max_calls: Successful calls needed to close circuit
            excluded_exceptions: Exceptions that don't count as failures
        """
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.excluded_exceptions = excluded_exceptions

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._last_success_time: Optional[float] = None
        self._half_open_calls = 0
        self._total_calls = 0
        self._rejected_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self._state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (rejecting requests)."""
        return self._state == CircuitState.OPEN

    def can_execute(self) -> bool:
        """
        Check if a request can be executed.

        Returns:
            True if request should proceed, False if it should be rejected.
        """
        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            if (
                self._last_failure_time
                and time.time() - self._last_failure_time >= self.recovery_timeout
            ):
                self._transition_to_half_open()
                return True
            return False

        # HALF_OPEN: Allow limited requests to test recovery
        return self._half_open_calls < self.half_open_max_calls

    def record_success(self) -> None:
        """Record a successful call."""
        self._last_success_time = time.time()
        self._success_count += 1

        if self._state == CircuitState.HALF_OPEN:
            self._half_open_calls += 1
            if self._half_open_calls >= self.half_open_max_calls:
                self._transition_to_closed()

    def record_failure(self, exception: Exception = None) -> None:
        """
        Record a failed call.

        Args:
            exception: The exception that caused the failure
        """
        # Check if exception should be excluded
        if exception and isinstance(exception, self.excluded_exceptions):
            logger.debug(
                f"Exception {type(exception).__name__} excluded from circuit breaker"
            )
            return

        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            # Any failure in HALF_OPEN immediately opens circuit
            self._transition_to_open()
        elif self._failure_count >= self.failure_threshold:
            self._transition_to_open()

    def _transition_to_open(self) -> None:
        """Transition to OPEN state."""
        previous_state = self._state
        self._state = CircuitState.OPEN
        logger.warning(
            f"Circuit breaker OPEN for {self.service_name} "
            f"(previous: {previous_state.value}, failures: {self._failure_count})"
        )

    def _transition_to_half_open(self) -> None:
        """Transition to HALF_OPEN state."""
        self._state = CircuitState.HALF_OPEN
        self._half_open_calls = 0
        logger.info(
            f"Circuit breaker HALF_OPEN for {self.service_name} - testing recovery"
        )

    def _transition_to_closed(self) -> None:
        """Transition to CLOSED state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_calls = 0
        logger.info(
            f"Circuit breaker CLOSED for {self.service_name} - service recovered"
        )

    def get_stats(self) -> CircuitBreakerStats:
        """Get current statistics."""
        return CircuitBreakerStats(
            service_name=self.service_name,
            state=self._state,
            failure_count=self._failure_count,
            success_count=self._success_count,
            last_failure_time=self._last_failure_time,
            last_success_time=self._last_success_time,
            total_calls=self._total_calls,
            rejected_calls=self._rejected_calls,
        )

    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time = None
        self._last_success_time = None
        logger.info(f"Circuit breaker RESET for {self.service_name}")


# Global circuit breakers for external services
circuit_breakers: dict[str, ServiceCircuitBreaker] = {
    "neo4j": ServiceCircuitBreaker(
        "neo4j", failure_threshold=5, recovery_timeout=30.0, half_open_max_calls=3
    ),
    "do_kb": ServiceCircuitBreaker(
        "do_kb", failure_threshold=5, recovery_timeout=30.0, half_open_max_calls=3
    ),
    "cohere": ServiceCircuitBreaker(
        "cohere",
        failure_threshold=3,  # Lower threshold for external API
        recovery_timeout=60.0,  # Longer recovery for external API
        half_open_max_calls=2,
    ),
    "cohere_embed": ServiceCircuitBreaker(
        "cohere_embed",
        failure_threshold=3,
        recovery_timeout=60.0,
        half_open_max_calls=2,
    ),
}


def get_circuit_breaker(service_name: str) -> Optional[ServiceCircuitBreaker]:
    """Get circuit breaker for a service."""
    return circuit_breakers.get(service_name)


def with_circuit_breaker(service_name: str):
    """
    Decorator to wrap async function with circuit breaker protection.

    Usage:
        @with_circuit_breaker("neo4j")
        async def query_neo4j():
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            breaker = circuit_breakers.get(service_name)
            if not breaker:
                # No circuit breaker configured, execute normally
                return await func(*args, **kwargs)

            breaker._total_calls += 1

            if not breaker.can_execute():
                breaker._rejected_calls += 1
                raise ServiceUnavailableError(
                    service_name,
                    f"{service_name} circuit breaker is open - "
                    f"service unavailable (failures: {breaker._failure_count})",
                )

            try:
                result = await func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure(e)
                raise

        return wrapper

    return decorator


def with_circuit_breaker_sync(service_name: str):
    """
    Decorator to wrap sync function with circuit breaker protection.

    Usage:
        @with_circuit_breaker_sync("neo4j")
        def query_neo4j():
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            breaker = circuit_breakers.get(service_name)
            if not breaker:
                return func(*args, **kwargs)

            breaker._total_calls += 1

            if not breaker.can_execute():
                breaker._rejected_calls += 1
                raise ServiceUnavailableError(
                    service_name,
                    f"{service_name} circuit breaker is open - service unavailable",
                )

            try:
                result = func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure(e)
                raise

        return wrapper

    return decorator


async def execute_with_circuit_breaker(
    service_name: str,
    func: Callable[..., T],
    *args,
    fallback: Callable[..., T] = None,
    **kwargs,
) -> T:
    """
    Execute a function with circuit breaker protection and optional fallback.

    Args:
        service_name: Name of the service
        func: Async function to execute
        fallback: Optional fallback function to call if circuit is open
        *args, **kwargs: Arguments to pass to the function

    Returns:
        Result of func or fallback

    Raises:
        ServiceUnavailableError: If circuit is open and no fallback provided
    """
    breaker = circuit_breakers.get(service_name)

    if not breaker:
        return await func(*args, **kwargs)

    breaker._total_calls += 1

    if not breaker.can_execute():
        breaker._rejected_calls += 1
        if fallback:
            logger.warning(f"{service_name} circuit open, using fallback")
            return (
                await fallback(*args, **kwargs)
                if asyncio.iscoroutinefunction(fallback)
                else fallback(*args, **kwargs)
            )
        raise ServiceUnavailableError(service_name)

    try:
        result = await func(*args, **kwargs)
        breaker.record_success()
        return result
    except Exception as e:
        breaker.record_failure(e)
        if fallback:
            logger.warning(
                f"{service_name} call failed ({type(e).__name__}), using fallback"
            )
            return (
                await fallback(*args, **kwargs)
                if asyncio.iscoroutinefunction(fallback)
                else fallback(*args, **kwargs)
            )
        raise


def get_all_circuit_breaker_stats() -> dict[str, CircuitBreakerStats]:
    """Get statistics for all circuit breakers."""
    return {name: breaker.get_stats() for name, breaker in circuit_breakers.items()}
