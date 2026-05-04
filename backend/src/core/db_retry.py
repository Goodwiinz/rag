"""Retry decorator for transient database pool exhaustion."""

import asyncio
import functools
import logging
from typing import Callable

from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)

_POOL_EXHAUSTION_KEYWORDS = ("max clients", "pool", "too many connections")


def retry_on_pool_exhaustion(max_retries: int = 3, base_delay: float = 0.5):
    """Retry on transient DB pool exhaustion with exponential backoff."""

    def decorator(func: Callable) -> Callable:
        is_async = asyncio.iscoroutinefunction(func)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            for attempt in range(1, max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except OperationalError as e:
                    msg = str(e).lower()
                    if not any(kw in msg for kw in _POOL_EXHAUSTION_KEYWORDS):
                        raise
                    if attempt == max_retries:
                        logger.error(
                            "DB pool exhausted after %d retries: %s", max_retries, e
                        )
                        raise
                    delay = base_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "DB pool exhausted (attempt %d/%d), retrying in %.2fs...",
                        attempt,
                        max_retries,
                        delay,
                    )
                    await asyncio.sleep(delay)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except OperationalError as e:
                    msg = str(e).lower()
                    if not any(kw in msg for kw in _POOL_EXHAUSTION_KEYWORDS):
                        raise
                    if attempt == max_retries:
                        logger.error(
                            "DB pool exhausted after %d retries: %s", max_retries, e
                        )
                        raise
                    delay = base_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "DB pool exhausted (attempt %d/%d), retrying in %.2fs...",
                        attempt,
                        max_retries,
                        delay,
                    )
                    import time

                    time.sleep(delay)

        return async_wrapper if is_async else sync_wrapper

    return decorator
