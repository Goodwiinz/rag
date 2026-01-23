"""
Async Test Helpers

Provides utilities for testing async code:
- Synchronous runners for async functions
- Quick async mock creation
- Mock session factories
- Timing utilities

Usage:
    from tests.utils.async_helpers import run_sync, async_mock_response

    result = run_sync(my_async_function())
    mock = async_mock_response({"status": "ok"})
"""

import asyncio
import functools
from typing import Any, Awaitable, Callable, Dict, List, Optional, TypeVar, Union
from unittest.mock import AsyncMock, MagicMock, Mock
from contextlib import asynccontextmanager
import time

T = TypeVar('T')


# ============================================================================
# Synchronous Async Runners
# ============================================================================

def run_sync(coro: Awaitable[T]) -> T:
    """
    Run an async coroutine synchronously.

    Useful for testing async code in non-async test functions.

    Example:
        async def my_async_fn():
            return "result"

        result = run_sync(my_async_fn())
        assert result == "result"
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def sync_test(fn: Callable[..., Awaitable[T]]) -> Callable[..., T]:
    """
    Decorator to run async test functions synchronously.

    Example:
        @sync_test
        async def test_something():
            result = await async_function()
            assert result == expected
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return run_sync(fn(*args, **kwargs))
    return wrapper


# ============================================================================
# Async Mock Factories
# ============================================================================

def async_mock_response(data: Any) -> AsyncMock:
    """
    Create an AsyncMock that returns the given data.

    Example:
        mock = async_mock_response({"id": "123"})
        result = await mock()
        assert result == {"id": "123"}
    """
    mock = AsyncMock()
    mock.return_value = data
    return mock


def async_mock_side_effect(values: List[Any]) -> AsyncMock:
    """
    Create an AsyncMock that returns values in sequence.

    Example:
        mock = async_mock_side_effect([1, 2, 3])
        assert await mock() == 1
        assert await mock() == 2
        assert await mock() == 3
    """
    mock = AsyncMock()
    mock.side_effect = values
    return mock


def async_mock_exception(exception: Exception) -> AsyncMock:
    """
    Create an AsyncMock that raises an exception.

    Example:
        mock = async_mock_exception(ValueError("error"))
        with pytest.raises(ValueError):
            await mock()
    """
    mock = AsyncMock()
    mock.side_effect = exception
    return mock


def async_mock_with_delay(data: Any, delay_seconds: float) -> AsyncMock:
    """
    Create an AsyncMock that returns data after a delay.

    Useful for testing timeout behavior.

    Example:
        mock = async_mock_with_delay({"result": "ok"}, delay_seconds=0.5)
        result = await asyncio.wait_for(mock(), timeout=1.0)
    """
    async def delayed_return(*args, **kwargs):
        await asyncio.sleep(delay_seconds)
        return data

    mock = AsyncMock()
    mock.side_effect = delayed_return
    return mock


# ============================================================================
# Mock Session Factory
# ============================================================================

class MockSessionFactory:
    """
    Factory for creating configured mock database sessions.

    Example:
        factory = MockSessionFactory()
        session = factory.create(query_results=[user])

        result = await session.execute(select(User))
        assert result.scalar_one() == user
    """

    def create(
        self,
        query_results: Optional[List[Any]] = None,
        scalar_result: Optional[Any] = None,
        raise_on_execute: Optional[Exception] = None,
        raise_on_commit: Optional[Exception] = None,
    ) -> MagicMock:
        """Create a configured mock session."""
        session = MagicMock()

        # Result mock
        result_mock = MagicMock()
        result_mock.scalar.return_value = scalar_result or (query_results[0] if query_results else None)
        result_mock.scalar_one_or_none.return_value = scalar_result or (query_results[0] if query_results else None)
        result_mock.scalars.return_value = MagicMock(
            all=MagicMock(return_value=query_results or []),
            first=MagicMock(return_value=query_results[0] if query_results else None)
        )
        result_mock.all.return_value = query_results or []
        result_mock.first.return_value = query_results[0] if query_results else None

        # Execute
        if raise_on_execute:
            session.execute = AsyncMock(side_effect=raise_on_execute)
        else:
            session.execute = AsyncMock(return_value=result_mock)

        # Commit
        if raise_on_commit:
            session.commit = AsyncMock(side_effect=raise_on_commit)
        else:
            session.commit = AsyncMock()

        # Other methods
        session.rollback = AsyncMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        session.close = AsyncMock()
        session.add = MagicMock()
        session.add_all = MagicMock()
        session.delete = AsyncMock()

        # Track added items
        session._added_items = []
        session.add.side_effect = lambda x: session._added_items.append(x)

        # Context manager
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)

        return session

    def create_with_transaction(
        self,
        query_results: Optional[List[Any]] = None,
    ) -> MagicMock:
        """Create session with transaction context manager."""
        session = self.create(query_results=query_results)

        transaction = MagicMock()
        transaction.__aenter__ = AsyncMock(return_value=transaction)
        transaction.__aexit__ = AsyncMock(return_value=None)

        session.begin = MagicMock(return_value=transaction)
        session.begin_nested = MagicMock(return_value=transaction)

        return session


def mock_async_session_factory() -> MagicMock:
    """
    Create a mock async session factory (dependency injection).

    Example:
        factory = mock_async_session_factory()
        async with factory() as session:
            result = await session.execute(query)
    """
    factory = MockSessionFactory()

    async def get_session():
        session = factory.create()
        try:
            yield session
        finally:
            await session.close()

    mock_factory = MagicMock()
    mock_factory.return_value = get_session()
    return mock_factory


# ============================================================================
# Timing Utilities
# ============================================================================

class AsyncTimer:
    """
    Context manager for timing async operations.

    Example:
        async with AsyncTimer() as timer:
            await some_async_operation()

        print(f"Took {timer.elapsed_ms}ms")
    """

    def __init__(self):
        self.start_time: float = 0
        self.end_time: float = 0

    @property
    def elapsed(self) -> float:
        """Elapsed time in seconds."""
        return self.end_time - self.start_time

    @property
    def elapsed_ms(self) -> float:
        """Elapsed time in milliseconds."""
        return self.elapsed * 1000

    async def __aenter__(self) -> "AsyncTimer":
        self.start_time = time.perf_counter()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self.end_time = time.perf_counter()


def assert_async_completes_within(timeout_seconds: float):
    """
    Decorator to assert async function completes within timeout.

    Example:
        @assert_async_completes_within(1.0)
        async def test_fast_operation():
            await fast_operation()
    """
    def decorator(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(fn(*args, **kwargs), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                raise AssertionError(
                    f"Function {fn.__name__} did not complete within {timeout_seconds}s"
                )
        return wrapper
    return decorator


# ============================================================================
# Concurrent Execution Helpers
# ============================================================================

async def gather_with_exceptions(*coros: Awaitable[T]) -> List[Union[T, Exception]]:
    """
    Gather results from coroutines, returning exceptions instead of raising.

    Example:
        results = await gather_with_exceptions(
            async_fn1(),
            async_fn2(),
            failing_fn()  # This won't stop the others
        )

        for result in results:
            if isinstance(result, Exception):
                print(f"Error: {result}")
    """
    results = []
    for coro in coros:
        try:
            result = await coro
            results.append(result)
        except Exception as e:
            results.append(e)
    return results


async def run_with_retry(
    coro_factory: Callable[[], Awaitable[T]],
    max_retries: int = 3,
    delay_seconds: float = 0.1,
    backoff_multiplier: float = 2.0,
) -> T:
    """
    Run async function with exponential backoff retry.

    Example:
        result = await run_with_retry(
            lambda: flaky_api_call(),
            max_retries=3
        )
    """
    last_exception = None
    delay = delay_seconds

    for attempt in range(max_retries):
        try:
            return await coro_factory()
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                await asyncio.sleep(delay)
                delay *= backoff_multiplier

    raise last_exception


# ============================================================================
# Test Fixture Helpers
# ============================================================================

@asynccontextmanager
async def mock_dependency(original: Any, mock: Any):
    """
    Async context manager for temporarily replacing a dependency.

    Example:
        async with mock_dependency(service.client, mock_client):
            result = await service.do_something()
    """
    # This is a simple implementation - in practice you'd need
    # proper dependency injection patterns
    yield mock


async def wait_for_condition(
    condition: Callable[[], bool],
    timeout: float = 5.0,
    poll_interval: float = 0.1,
) -> bool:
    """
    Wait for a condition to become true.

    Example:
        await wait_for_condition(
            lambda: len(results) >= 10,
            timeout=5.0
        )
    """
    start = time.perf_counter()
    while time.perf_counter() - start < timeout:
        if condition():
            return True
        await asyncio.sleep(poll_interval)
    return False
