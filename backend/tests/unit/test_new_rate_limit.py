import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.core.rate_limit import InMemoryRateLimiter, RedisRateLimiter, create_rate_limiter
from src.core.config import settings

@pytest.mark.asyncio
async def test_in_memory_rate_limiter():
    limiter = InMemoryRateLimiter(max_attempts=2, window_minutes=1)

    # First attempt - allowed
    assert await limiter.is_allowed("test_user") is True
    assert await limiter.get_remaining_attempts("test_user") == 1

    # Second attempt - allowed
    assert await limiter.is_allowed("test_user") is True
    assert await limiter.get_remaining_attempts("test_user") == 0

    # Third attempt - blocked
    assert await limiter.is_allowed("test_user") is False
    assert await limiter.get_remaining_attempts("test_user") == 0

    # Different user - allowed
    assert await limiter.is_allowed("other_user") is True
    assert await limiter.get_remaining_attempts("other_user") == 1

    await limiter.close()

@pytest.mark.asyncio
async def test_redis_rate_limiter():
    # Mock redis client
    mock_redis = MagicMock()
    # eval is async
    mock_redis.eval = AsyncMock()

    # Patch from_url to return mock
    with patch("redis.asyncio.from_url", return_value=mock_redis):
        limiter = RedisRateLimiter(max_attempts=2, window_minutes=1, redis_url="redis://test")

        # First attempt
        mock_redis.eval.return_value = 1
        assert await limiter.is_allowed("test_user") is True

        # Verify eval usage
        mock_redis.eval.assert_called_with(
            limiter._incr_expire_script,
            1,
            "auth_rate_limit:test_user",
            60
        )

        # Second attempt
        mock_redis.eval.return_value = 2
        assert await limiter.is_allowed("test_user") is True

        # Third attempt - blocked
        mock_redis.eval.return_value = 3
        assert await limiter.is_allowed("test_user") is False

        # Close
        mock_redis.close = AsyncMock()
        await limiter.close()
        mock_redis.close.assert_called_once()

@pytest.mark.asyncio
async def test_redis_rate_limiter_get_remaining():
    mock_redis = MagicMock()
    mock_redis.get = AsyncMock() # get is async

    with patch("redis.asyncio.from_url", return_value=mock_redis):
        limiter = RedisRateLimiter(max_attempts=5, window_minutes=1)

        # Case 1: Key exists, count=2
        mock_redis.get.return_value = "2"
        remaining = await limiter.get_remaining_attempts("test_user")
        assert remaining == 3
        mock_redis.get.assert_called_with("auth_rate_limit:test_user")

        # Case 2: Key missing (expired/new)
        mock_redis.get.return_value = None
        remaining = await limiter.get_remaining_attempts("test_user")
        assert remaining == 5

@pytest.mark.asyncio
async def test_redis_rate_limiter_fail_open():
    # Mock redis client that raises exception
    mock_redis = MagicMock()
    mock_redis.eval = AsyncMock(side_effect=Exception("Redis down"))

    with patch("redis.asyncio.from_url", return_value=mock_redis):
        limiter = RedisRateLimiter(max_attempts=2, window_minutes=1)

        # Should return True (fail open)
        assert await limiter.is_allowed("test_user") is True

@pytest.mark.asyncio
async def test_create_rate_limiter_factory():
    # Test with REDIS_URL set
    with patch.object(settings, "REDIS_URL", "redis://test"):
        limiter = create_rate_limiter(5, 15)
        assert isinstance(limiter, RedisRateLimiter)

    # Test with REDIS_URL empty
    with patch("src.core.rate_limit.settings") as mock_settings:
        mock_settings.REDIS_URL = ""
        limiter = create_rate_limiter(5, 15)
        assert isinstance(limiter, InMemoryRateLimiter)
