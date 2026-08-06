"""
A/B Testing Resilience Patterns

This module implements comprehensive resilience patterns for the A/B testing system,
including circuit breakers, retry mechanisms, fallback strategies, and bulkheads
to ensure high availability and graceful degradation under failure conditions.
"""

import asyncio
import concurrent.futures
import logging
import random
import statistics
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar, Union

from ..core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ============================================================================
# CIRCUIT BREAKER IMPLEMENTATION
# ============================================================================


class CircuitState(Enum):
    """Circuit breaker states"""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit is open, calls fail fast
    HALF_OPEN = "half_open"  # Testing if service has recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""

    failure_threshold: int = 5  # Number of failures before opening
    recovery_timeout: float = 60.0  # Seconds to wait before trying again
    expected_exception: tuple = (Exception,)  # Exception types to track
    success_threshold: int = 3  # Successes needed to close circuit
    monitoring_period: float = 300.0  # Period to monitor for failure rate
    failure_rate_threshold: float = 0.5  # Failure rate threshold (50%)
    minimum_requests: int = 10  # Minimum requests before rate calculation


@dataclass
class CircuitBreakerMetrics:
    """Metrics for circuit breaker"""

    total_requests: int = 0
    failed_requests: int = 0
    successful_requests: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    circuit_open_count: int = 0
    circuit_close_count: int = 0


class CircuitBreaker:
    """Implementation of circuit breaker pattern"""

    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = CircuitState.CLOSED
        self.metrics = CircuitBreakerMetrics()
        self.last_state_change = datetime.now(timezone.utc)
        self.half_open_successes = 0

        # Request history for rate calculation
        self.request_history: List[datetime] = []

    def __call__(self, func: Callable) -> Callable:
        """Decorator to apply circuit breaker to a function"""

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await self.call_async(func, *args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return self.call_sync(func, *args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    async def call_async(self, func: Callable, *args, **kwargs) -> T:
        """Execute async function with circuit breaker protection"""
        if not self.can_execute():
            raise CircuitBreakerOpenException(f"Circuit breaker '{self.name}' is OPEN")

        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise e
        finally:
            execution_time = time.time() - start_time
            logger.debug(
                f"Circuit breaker '{self.name}' execution time: {execution_time:.3f}s"
            )

    def call_sync(self, func: Callable, *args, **kwargs) -> T:
        """Execute sync function with circuit breaker protection"""
        if not self.can_execute():
            raise CircuitBreakerOpenException(f"Circuit breaker '{self.name}' is OPEN")

        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise e
        finally:
            execution_time = time.time() - start_time
            logger.debug(
                f"Circuit breaker '{self.name}' execution time: {execution_time:.3f}s"
            )

    def can_execute(self) -> bool:
        """Check if circuit breaker allows execution"""
        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if (
                datetime.now(timezone.utc) - self.last_state_change
            ).total_seconds() >= self.config.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.half_open_successes = 0
                logger.info(f"Circuit breaker '{self.name}' transitioned to HALF_OPEN")
                return True
            return False
        else:  # HALF_OPEN
            return True

    def on_success(self):
        """Handle successful execution"""
        self.metrics.successful_requests += 1
        self.metrics.total_requests += 1
        self.metrics.last_success_time = datetime.now(timezone.utc)
        self.request_history.append(datetime.now(timezone.utc))

        # Clean old request history
        cutoff_time = datetime.now(timezone.utc) - timedelta(
            seconds=self.config.monitoring_period
        )
        self.request_history = [
            req_time for req_time in self.request_history if req_time > cutoff_time
        ]

        if self.state == CircuitState.HALF_OPEN:
            self.half_open_successes += 1
            if self.half_open_successes >= self.config.success_threshold:
                self.close_circuit()

    def on_failure(self):
        """Handle failed execution"""
        self.metrics.failed_requests += 1
        self.metrics.total_requests += 1
        self.metrics.last_failure_time = datetime.now(timezone.utc)
        self.request_history.append(datetime.now(timezone.utc))

        # Clean old request history
        cutoff_time = datetime.now(timezone.utc) - timedelta(
            seconds=self.config.monitoring_period
        )
        self.request_history = [
            req_time for req_time in self.request_history if req_time > cutoff_time
        ]

        if self.state == CircuitState.HALF_OPEN:
            self.open_circuit()
        elif self.state == CircuitState.CLOSED:
            # Check if we should open circuit based on failure rate
            if self.should_open_circuit():
                self.open_circuit()

    def should_open_circuit(self) -> bool:
        """Determine if circuit should be opened based on metrics"""
        if self.metrics.total_requests < self.config.minimum_requests:
            return False

        failure_rate = self.metrics.failed_requests / self.metrics.total_requests
        return failure_rate >= self.config.failure_rate_threshold

    def open_circuit(self):
        """Open the circuit"""
        if self.state != CircuitState.OPEN:
            self.state = CircuitState.OPEN
            self.last_state_change = datetime.now(timezone.utc)
            self.metrics.circuit_open_count += 1
            logger.warning(
                f"Circuit breaker '{self.name}' opened due to high failure rate"
            )

    def close_circuit(self):
        """Close the circuit"""
        if self.state != CircuitState.CLOSED:
            self.state = CircuitState.CLOSED
            self.last_state_change = datetime.now(timezone.utc)
            self.metrics.circuit_close_count += 1
            # Reset failure counts when closing
            self.metrics.failed_requests = 0
            self.metrics.successful_requests = 0
            self.metrics.total_requests = 0
            logger.info(f"Circuit breaker '{self.name}' closed")

    def get_metrics(self) -> Dict[str, Any]:
        """Get current circuit breaker metrics"""
        failure_rate = 0
        if self.metrics.total_requests > 0:
            failure_rate = self.metrics.failed_requests / self.metrics.total_requests

        return {
            "name": self.name,
            "state": self.state.value,
            "total_requests": self.metrics.total_requests,
            "failed_requests": self.metrics.failed_requests,
            "successful_requests": self.metrics.successful_requests,
            "failure_rate": failure_rate,
            "last_failure_time": self.metrics.last_failure_time.isoformat()
            if self.metrics.last_failure_time
            else None,
            "last_success_time": self.metrics.last_success_time.isoformat()
            if self.metrics.last_success_time
            else None,
            "circuit_open_count": self.metrics.circuit_open_count,
            "circuit_close_count": self.metrics.circuit_close_count,
            "time_since_state_change": (
                datetime.now(timezone.utc) - self.last_state_change
            ).total_seconds(),
            "request_history_count": len(self.request_history),
        }


class ResilienceException(Exception):
    """Base exception for all resilience pattern failures"""

    pass


class CircuitBreakerOpenException(ResilienceException):
    """Exception raised when circuit breaker is open"""

    pass


class RetryExhaustedException(ResilienceException):
    """Exception raised when retry mechanism exhausts all attempts"""

    pass


class BulkheadFullException(ResilienceException):
    """Exception raised when bulkhead is full"""

    pass


class FallbackExecutionException(ResilienceException):
    """Exception raised when fallback strategy execution fails"""

    pass


# ============================================================================
# RETRY MECHANISM
# ============================================================================


@dataclass
class RetryConfig:
    """Configuration for retry mechanism"""

    max_attempts: int = 3
    base_delay: float = 1.0  # Base delay in seconds
    max_delay: float = 60.0  # Maximum delay in seconds
    exponential_base: float = 2.0  # Exponential backoff base
    jitter: bool = True  # Add randomness to delay
    retry_on: List[type] = field(
        default_factory=lambda: [Exception]
    )  # Exceptions to retry on


class RetryStrategy(ABC):
    """Abstract base class for retry strategies"""

    @abstractmethod
    def get_delay(self, attempt: int) -> float:
        """Get delay for given attempt"""
        pass


class ExponentialBackoffStrategy(RetryStrategy):
    """Exponential backoff retry strategy"""

    def __init__(self, config: RetryConfig):
        self.config = config

    def get_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay"""
        delay = self.config.base_delay * (self.config.exponential_base ** (attempt - 1))
        delay = min(delay, self.config.max_delay)

        if self.config.jitter:
            # Add randomness to prevent thundering herd
            jitter_range = delay * 0.1
            delay += random.uniform(-jitter_range, jitter_range)

        return max(0, delay)


class LinearBackoffStrategy(RetryStrategy):
    """Linear backoff retry strategy"""

    def __init__(self, config: RetryConfig):
        self.config = config

    def get_delay(self, attempt: int) -> float:
        """Calculate linear backoff delay"""
        delay = self.config.base_delay * attempt
        delay = min(delay, self.config.max_delay)

        if self.config.jitter:
            jitter_range = delay * 0.1
            delay += random.uniform(-jitter_range, jitter_range)

        return max(0, delay)


class FixedDelayStrategy(RetryStrategy):
    """Fixed delay retry strategy"""

    def __init__(self, config: RetryConfig):
        self.config = config

    def get_delay(self, attempt: int) -> float:
        """Return fixed delay"""
        delay = self.config.base_delay

        if self.config.jitter:
            jitter_range = delay * 0.1
            delay += random.uniform(-jitter_range, jitter_range)

        return max(0, delay)


class RetryMechanism:
    """Retry mechanism with configurable strategies"""

    def __init__(self, name: str, config: RetryConfig, strategy: RetryStrategy = None):
        self.name = name
        self.config = config
        self.strategy = strategy or ExponentialBackoffStrategy(config)

    def __call__(self, func: Callable) -> Callable:
        """Decorator to apply retry mechanism to a function"""

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await self.execute_async(func, *args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return self.execute_sync(func, *args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    async def execute_async(self, func: Callable, *args, **kwargs) -> T:
        """Execute async function with retry mechanism"""
        last_exception = None

        for attempt in range(1, self.config.max_attempts + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e

                # Check if we should retry on this exception
                if not any(
                    isinstance(e, retry_type) for retry_type in self.config.retry_on
                ):
                    raise e

                if attempt == self.config.max_attempts:
                    logger.error(
                        f"Retry mechanism '{self.name}' exhausted after {attempt} attempts: {str(e)}"
                    )
                    raise RetryExhaustedException(
                        f"Retry mechanism '{self.name}' exhausted after {attempt} attempts"
                    ) from e

                delay = self.strategy.get_delay(attempt)
                logger.warning(
                    f"Retry mechanism '{self.name}' attempt {attempt} failed, retrying in {delay:.2f}s: {str(e)}"
                )
                await asyncio.sleep(delay)

        raise last_exception

    def execute_sync(self, func: Callable, *args, **kwargs) -> T:
        """Execute sync function with retry mechanism"""
        last_exception = None

        for attempt in range(1, self.config.max_attempts + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e

                # Check if we should retry on this exception
                if not any(
                    isinstance(e, retry_type) for retry_type in self.config.retry_on
                ):
                    raise e

                if attempt == self.config.max_attempts:
                    logger.error(
                        f"Retry mechanism '{self.name}' exhausted after {attempt} attempts"
                    )
                    raise e

                delay = self.strategy.get_delay(attempt)
                logger.warning(
                    f"Retry mechanism '{self.name}' attempt {attempt} failed, retrying in {delay:.2f}s: {str(e)}"
                )
                time.sleep(delay)

        raise last_exception


# ============================================================================
# FALLBACK MECHANISM
# ============================================================================


class FallbackStrategy(ABC):
    """Abstract base class for fallback strategies"""

    @abstractmethod
    async def execute(self, original_func: Callable, *args, **kwargs) -> Any:
        """Execute fallback logic"""
        pass


class DefaultFallbackStrategy(FallbackStrategy):
    """Default fallback that raises an exception"""

    async def execute(self, original_func: Callable, *args, **kwargs) -> Any:
        raise FallbackExecutionException(
            f"Primary function {original_func.__name__} failed and no fallback available"
        )


class CacheFallbackStrategy(FallbackStrategy):
    """Fallback that returns cached value if available"""

    def __init__(self, cache_client, cache_key_generator):
        self.cache_client = cache_client
        self.cache_key_generator = cache_key_generator

    async def execute(self, original_func: Callable, *args, **kwargs) -> Any:
        # Generate cache key based on function and arguments
        cache_key = self.cache_key_generator(original_func.__name__, args, kwargs)

        # Try to get cached value
        cached_value = await self.cache_client.get(cache_key)
        if cached_value is not None:
            logger.info(f"Using cached fallback value for {original_func.__name__}")
            return cached_value

        # No cached value available
        raise Exception(f"No cached fallback available for {original_func.__name__}")


class DefaultValueFallbackStrategy(FallbackStrategy):
    """Fallback that returns a default value"""

    def __init__(self, default_value: Any):
        self.default_value = default_value

    async def execute(self, original_func: Callable, *args, **kwargs) -> Any:
        logger.info(f"Using default fallback value for {original_func.__name__}")
        return self.default_value


class FallbackFunctionStrategy(FallbackStrategy):
    """Fallback that calls a specific function"""

    def __init__(self, fallback_func: Callable):
        self.fallback_func = fallback_func

    async def execute(self, original_func: Callable, *args, **kwargs) -> Any:
        logger.info(f"Using fallback function for {original_func.__name__}")
        if asyncio.iscoroutinefunction(self.fallback_func):
            return await self.fallback_func(*args, **kwargs)
        else:
            return self.fallback_func(*args, **kwargs)


@dataclass
class FallbackConfig:
    """Configuration for fallback mechanism"""

    enabled: bool = True
    timeout: float = 5.0  # Timeout for primary function before using fallback


class FallbackMechanism:
    """Fallback mechanism with configurable strategies"""

    def __init__(self, name: str, config: FallbackConfig, strategy: FallbackStrategy):
        self.name = name
        self.config = config
        self.strategy = strategy

    def __call__(self, func: Callable) -> Callable:
        """Decorator to apply fallback mechanism to a function"""

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await self.execute_async(func, *args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return self.execute_sync(func, *args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    async def execute_async(self, func: Callable, *args, **kwargs) -> Any:
        """Execute async function with fallback mechanism"""
        if not self.config.enabled:
            return await func(*args, **kwargs)

        try:
            # Try primary function with timeout
            return await asyncio.wait_for(
                func(*args, **kwargs), timeout=self.config.timeout
            )
        except Exception as e:
            logger.warning(
                f"Primary function {func.__name__} failed: {str(e)}, using fallback"
            )
            return await self.strategy.execute(func, *args, **kwargs)

    def execute_sync(self, func: Callable, *args, **kwargs) -> Any:
        """Execute sync function with fallback mechanism"""
        if not self.config.enabled:
            return func(*args, **kwargs)

        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.warning(
                f"Primary function {func.__name__} failed: {str(e)}, using fallback"
            )
            # Run fallback safely in new event loop to maintain async interface
            try:
                # Try to get current loop and create new one if needed
                try:
                    loop = asyncio.get_running_loop()
                    # If we're in a running loop, we can't use run_until_complete
                    # Create a new future and run the fallback in the background
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            lambda: asyncio.run(
                                self.strategy.execute(func, *args, **kwargs)
                            )
                        )
                        return future.result(timeout=self.config.timeout)
                except RuntimeError:
                    # No running loop, safe to use asyncio.run
                    return asyncio.run(self.strategy.execute(func, *args, **kwargs))
            except Exception as fallback_error:
                logger.error(f"Fallback execution failed: {str(fallback_error)}")
                raise FallbackExecutionException(
                    f"Both primary and fallback failed for {func.__name__}"
                ) from e


# ============================================================================
# BULKHEAD PATTERN
# ============================================================================


@dataclass
class BulkheadConfig:
    """Configuration for bulkhead pattern"""

    max_concurrent: int = 10  # Maximum concurrent executions
    max_queue_size: int = 100  # Maximum queue size
    timeout: float = 30.0  # Timeout for queue wait


class Bulkhead:
    """Implementation of bulkhead pattern for resource isolation"""

    def __init__(self, name: str, config: BulkheadConfig):
        self.name = name
        self.config = config
        self.semaphore = asyncio.Semaphore(config.max_concurrent)
        self.queue = asyncio.Queue(maxsize=config.max_queue_size)
        self.active_tasks = set()
        self.metrics = {
            "total_requests": 0,
            "rejected_requests": 0,
            "active_tasks": 0,
            "queue_size": 0,
        }

    def __call__(self, func: Callable) -> Callable:
        """Decorator to apply bulkhead to a function"""

        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await self.execute(func, *args, **kwargs)

        return wrapper

    async def execute(self, func: Callable, *args, **kwargs) -> T:
        """Execute function with bulkhead protection"""
        self.metrics["total_requests"] += 1

        try:
            # Try to acquire semaphore safely without race conditions
            await asyncio.wait_for(self.semaphore.acquire(), timeout=0.1)
        except asyncio.TimeoutError:
            # Add to queue if immediate acquisition failed
            await asyncio.wait_for(self.queue.put(None), timeout=self.config.timeout)
            await self.semaphore.acquire()

        except asyncio.TimeoutError:
            self.metrics["rejected_requests"] += 1
            raise BulkheadFullException(f"Bulkhead '{self.name}' is full")

        # Track active task safely
        try:
            current_task = asyncio.current_task()
            if current_task is not None:
                task_id = id(current_task)
                self.active_tasks.add(task_id)
            else:
                # Fallback if current_task is None (shouldn't happen but be defensive)
                task_id = id(f"fallback_{len(self.active_tasks)}")
                self.active_tasks.add(task_id)
                logger.warning(
                    f"Current task was None in bulkhead '{self.name}', using fallback task ID"
                )
        except Exception as e:
            # Fallback if there's an error getting current task
            task_id = id(f"fallback_{len(self.active_tasks)}")
            self.active_tasks.add(task_id)
            logger.error(f"Error getting current task in bulkhead '{self.name}': {e}")

        self.metrics["active_tasks"] = len(self.active_tasks)

        try:
            result = await func(*args, **kwargs)
            return result
        finally:
            # Release semaphore and process queue
            self.semaphore.release()
            self.active_tasks.discard(task_id)
            self.metrics["active_tasks"] = len(self.active_tasks)

            # Process next item in queue if any
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass

    def get_metrics(self) -> Dict[str, Any]:
        """Get bulkhead metrics"""
        self.metrics["queue_size"] = self.queue.qsize()
        return self.metrics.copy()


# ============================================================================
# COMPREHENSIVE RESILIENCE MANAGER
# ============================================================================


@dataclass
class ResilienceConfig:
    """Complete resilience configuration"""

    circuit_breaker: Optional[CircuitBreakerConfig] = None
    retry: Optional[RetryConfig] = None
    fallback: Optional[FallbackConfig] = None
    bulkhead: Optional[BulkheadConfig] = None


class ResilienceManager:
    """Manages all resilience patterns for A/B testing services"""

    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.retry_mechanisms: Dict[str, RetryMechanism] = {}
        self.fallback_mechanisms: Dict[str, FallbackMechanism] = {}
        self.bulkheads: Dict[str, Bulkhead] = {}

    def create_circuit_breaker(
        self, name: str, config: CircuitBreakerConfig
    ) -> CircuitBreaker:
        """Create a circuit breaker"""
        circuit_breaker = CircuitBreaker(name, config)
        self.circuit_breakers[name] = circuit_breaker
        return circuit_breaker

    def create_retry_mechanism(
        self, name: str, config: RetryConfig, strategy: RetryStrategy = None
    ) -> RetryMechanism:
        """Create a retry mechanism"""
        retry_mechanism = RetryMechanism(name, config, strategy)
        self.retry_mechanisms[name] = retry_mechanism
        return retry_mechanism

    def create_fallback_mechanism(
        self, name: str, config: FallbackConfig, strategy: FallbackStrategy
    ) -> FallbackMechanism:
        """Create a fallback mechanism"""
        fallback_mechanism = FallbackMechanism(name, config, strategy)
        self.fallback_mechanisms[name] = fallback_mechanism
        return fallback_mechanism

    def create_bulkhead(self, name: str, config: BulkheadConfig) -> Bulkhead:
        """Create a bulkhead"""
        bulkhead = Bulkhead(name, config)
        self.bulkheads[name] = bulkhead
        return bulkhead

    def apply_resilience(self, name: str, config: ResilienceConfig) -> Callable:
        """Apply comprehensive resilience patterns to a function"""

        def decorator(func: Callable) -> Callable:
            decorated_func = func

            # Apply bulkhead first (outermost layer)
            if config.bulkhead:
                bulkhead = self.create_bulkhead(f"{name}_bulkhead", config.bulkhead)
                decorated_func = bulkhead(decorated_func)

            # Apply circuit breaker
            if config.circuit_breaker:
                circuit_breaker = self.create_circuit_breaker(
                    f"{name}_circuit_breaker", config.circuit_breaker
                )
                decorated_func = circuit_breaker(decorated_func)

            # Apply retry mechanism
            if config.retry:
                retry_mechanism = self.create_retry_mechanism(
                    f"{name}_retry", config.retry
                )
                decorated_func = retry_mechanism(decorated_func)

            # Apply fallback (innermost layer)
            if config.fallback:
                fallback_strategy = DefaultValueFallbackStrategy(None)
                fallback_mechanism = self.create_fallback_mechanism(
                    f"{name}_fallback", config.fallback, fallback_strategy
                )
                decorated_func = fallback_mechanism(decorated_func)

            return decorated_func

        return decorator

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get metrics from all resilience components"""
        metrics = {
            "circuit_breakers": {},
            "bulkheads": {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        for name, circuit_breaker in self.circuit_breakers.items():
            metrics["circuit_breakers"][name] = circuit_breaker.get_metrics()

        for name, bulkhead in self.bulkheads.items():
            metrics["bulkheads"][name] = bulkhead.get_metrics()

        return metrics

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on all resilience components"""
        health_status = {"status": "healthy", "components": {}, "issues": []}

        # Check circuit breakers
        for name, circuit_breaker in self.circuit_breakers.items():
            cb_metrics = circuit_breaker.get_metrics()
            if cb_metrics["state"] == "open":
                health_status["status"] = "degraded"
                health_status["issues"].append(f"Circuit breaker '{name}' is open")
                health_status["components"][name] = {
                    "status": "unhealthy",
                    "metrics": cb_metrics,
                }
            else:
                health_status["components"][name] = {
                    "status": "healthy",
                    "metrics": cb_metrics,
                }

        # Check bulkheads
        for name, bulkhead in self.bulkheads.items():
            metrics = bulkhead.get_metrics()
            if metrics["rejected_requests"] > 0:
                health_status["status"] = "degraded"
                health_status["issues"].append(
                    f"Bulkhead '{name}' has rejected requests"
                )
                health_status["components"][f"bulkhead_{name}"] = {
                    "status": "degraded",
                    "metrics": metrics,
                }
            else:
                health_status["components"][f"bulkhead_{name}"] = {
                    "status": "healthy",
                    "metrics": metrics,
                }

        return health_status


# ============================================================================
# PRECONFIGURED RESILIENCE FOR A/B TESTING COMPONENTS
# ============================================================================


def create_ab_testing_resilience_manager() -> ResilienceManager:
    """Create resilience manager with preconfigured components for A/B testing"""
    manager = ResilienceManager()

    # Query Router resilience
    manager.create_circuit_breaker(
        "query_router_db",
        CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=30.0,
            expected_exception=Exception,
            failure_rate_threshold=0.3,
        ),
    )

    manager.create_retry_mechanism(
        "query_router_assignment",
        RetryConfig(
            max_attempts=3, base_delay=0.1, max_delay=2.0, retry_on=[Exception]
        ),
        ExponentialBackoffStrategy(
            RetryConfig(
                max_attempts=3, base_delay=0.1, max_delay=2.0, retry_on=[Exception]
            )
        ),
    )

    manager.create_bulkhead(
        "query_router",
        BulkheadConfig(max_concurrent=50, max_queue_size=200, timeout=1.0),
    )

    # Metrics Collector resilience
    manager.create_circuit_breaker(
        "metrics_collector_storage",
        CircuitBreakerConfig(
            failure_threshold=10,
            recovery_timeout=60.0,
            expected_exception=Exception,
            failure_rate_threshold=0.2,
        ),
    )

    manager.create_bulkhead(
        "metrics_collector",
        BulkheadConfig(max_concurrent=20, max_queue_size=500, timeout=5.0),
    )

    # Statistical Analyzer resilience
    manager.create_circuit_breaker(
        "statistical_analyzer",
        CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=120.0,
            expected_exception=Exception,
            failure_rate_threshold=0.4,
        ),
    )

    manager.create_retry_mechanism(
        "statistical_analysis",
        RetryConfig(
            max_attempts=2, base_delay=1.0, max_delay=10.0, retry_on=[Exception]
        ),
        LinearBackoffStrategy(
            RetryConfig(
                max_attempts=2, base_delay=1.0, max_delay=10.0, retry_on=[Exception]
            )
        ),
    )

    return manager


# ============================================================================
# DECORATORS FOR COMMON USE CASES
# ============================================================================


def resilient_database_operation(name: str):
    """Decorator for database operations with standard resilience"""
    config = ResilienceConfig(
        circuit_breaker=CircuitBreakerConfig(
            failure_threshold=5, recovery_timeout=30.0, failure_rate_threshold=0.3
        ),
        retry=RetryConfig(max_attempts=3, base_delay=0.5, max_delay=5.0),
        fallback=FallbackConfig(enabled=False),  # No fallback for DB operations
    )

    manager = create_ab_testing_resilience_manager()
    return manager.apply_resilience(name, config)


def resilient_external_service_call(name: str, fallback_value: Any = None):
    """Decorator for external service calls with fallback"""
    config = ResilienceConfig(
        circuit_breaker=CircuitBreakerConfig(
            failure_threshold=3, recovery_timeout=60.0, failure_rate_threshold=0.4
        ),
        retry=RetryConfig(max_attempts=2, base_delay=1.0, max_delay=10.0),
        fallback=FallbackConfig(enabled=True, timeout=5.0),
    )

    manager = create_ab_testing_resilience_manager()

    # Create fallback strategy if fallback value provided
    if fallback_value is not None:
        fallback_strategy = DefaultValueFallbackStrategy(fallback_value)
        manager.create_fallback_mechanism(
            f"{name}_fallback", config.fallback, fallback_strategy
        )

    return manager.apply_resilience(name, config)


def resilient_high_throughput_operation(name: str, max_concurrent: int = 100):
    """Decorator for high-throughput operations with bulkhead"""
    config = ResilienceConfig(
        bulkhead=BulkheadConfig(
            max_concurrent=max_concurrent, max_queue_size=500, timeout=0.1
        )
    )

    manager = create_ab_testing_resilience_manager()
    return manager.apply_resilience(name, config)
