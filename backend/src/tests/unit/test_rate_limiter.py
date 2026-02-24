"""
Unit tests for rate limiters
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.core.rate_limit import InMemoryRateLimiter, RedisRateLimiter, get_rate_limiter


@pytest.mark.asyncio
async def test_in_memory_rate_limiter():
    """Test InMemoryRateLimiter functionality"""
    limiter = InMemoryRateLimiter(max_attempts=2, window_minutes=1)
    identifier = "test_user"

    # First attempt
    assert await limiter.is_allowed(identifier) is True
    assert await limiter.get_remaining_attempts(identifier) == 1

    # Second attempt
    assert await limiter.is_allowed(identifier) is True
    assert await limiter.get_remaining_attempts(identifier) == 0

    # Third attempt (should fail)
    assert await limiter.is_allowed(identifier) is False
    assert await limiter.get_remaining_attempts(identifier) == 0

    # Test with different identifier (should be allowed)
    assert await limiter.is_allowed("other_user") is True


@pytest.mark.asyncio
async def test_redis_rate_limiter():
    """Test RedisRateLimiter functionality with mocked Redis"""
    with patch("redis.asyncio.from_url") as mock_from_url:
        mock_redis = AsyncMock()
        mock_from_url.return_value = mock_redis

        limiter = RedisRateLimiter(max_attempts=2, window_minutes=1)
        identifier = "test_user"

        # Mock Redis eval to return incrementing values (INCR behavior inside script)
        mock_redis.eval.side_effect = [1, 2, 3]
        mock_redis.get.side_effect = ["1", "2", "3"]

        # First attempt
        assert await limiter.is_allowed(identifier) is True
        # Check if eval was called correctly
        args, _ = mock_redis.eval.call_args
        assert args[1] == 1 # numkeys
        assert args[2] == "rate_limit:test_user" # KEYS[1]
        assert args[3] == 60 # ARGV[1] (window_seconds)

        # Second attempt
        assert await limiter.is_allowed(identifier) is True

        # Third attempt (should fail)
        assert await limiter.is_allowed(identifier) is False

        # Test fail-open behavior
        mock_redis.eval.side_effect = Exception("Redis connection error")
        assert await limiter.is_allowed(identifier) is True


def test_get_rate_limiter_factory():
    """Test get_rate_limiter factory function"""
    with patch("src.core.config.settings.REDIS_URL", "redis://localhost"):
        limiter = get_rate_limiter()
        assert isinstance(limiter, RedisRateLimiter)

    with patch("src.core.config.settings.REDIS_URL", ""):
        limiter = get_rate_limiter()
        assert isinstance(limiter, InMemoryRateLimiter)
