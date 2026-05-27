"""Tests for db_retry decorator."""

import pytest
from sqlalchemy.exc import OperationalError

from src.core.db_retry import retry_on_pool_exhaustion


@pytest.mark.asyncio
async def test_retry_on_pool_exhaustion_retries_then_succeeds():
    call_count = 0

    @retry_on_pool_exhaustion(max_retries=3, base_delay=0.01)
    async def flaky_connect():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise OperationalError(
                "MaxClientsInSessionMode: max clients reached", None, None
            )
        return "ok"

    result = await flaky_connect()
    assert result == "ok"
    assert call_count == 3


@pytest.mark.asyncio
async def test_retry_does_not_retry_on_non_pool_errors():
    call_count = 0

    @retry_on_pool_exhaustion(max_retries=3, base_delay=0.01)
    async def failing_connect():
        nonlocal call_count
        call_count += 1
        raise OperationalError("relation does not exist", None, None)

    with pytest.raises(OperationalError, match="relation does not exist"):
        await failing_connect()
    assert call_count == 1


@pytest.mark.asyncio
async def test_retry_exhausts_all_attempts():
    call_count = 0

    @retry_on_pool_exhaustion(max_retries=2, base_delay=0.01)
    async def always_full():
        nonlocal call_count
        call_count += 1
        raise OperationalError("pool is full", None, None)

    with pytest.raises(OperationalError, match="pool is full"):
        await always_full()
    assert call_count == 2


def test_sync_retry_retries_then_succeeds():
    call_count = 0

    @retry_on_pool_exhaustion(max_retries=3, base_delay=0.01)
    def sync_connect():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise OperationalError("too many connections", None, None)
        return "connected"

    result = sync_connect()
    assert result == "connected"
    assert call_count == 2
