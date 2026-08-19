"""R4-M10 regression: RedisRateLimiter.is_allowed raised UnboundLocalError
when Redis failed on its very first call.

``info`` was only built inside the try block, after ``zremrangebyscore``. If
that first Redis call raised (e.g. a Redis outage), the `except
redis.RedisError` fallback tried to `return True, info` with `info` never
assigned -> UnboundLocalError instead of the intended fail-open behavior.
"""

from unittest.mock import MagicMock

import pytest
import redis

from src.middleware.rate_limiting import RedisRateLimiter

pytestmark = pytest.mark.unit


def test_is_allowed_fails_open_when_redis_errors_on_first_call():
    mock_redis = MagicMock()
    mock_redis.zremrangebyscore.side_effect = redis.RedisError("connection refused")

    limiter = RedisRateLimiter(mock_redis)

    allowed, info = limiter.is_allowed("some-key", limit=10, window=60)

    assert allowed is True
    assert info["limit"] == 10
    assert info["window"] == 60
    assert info["current_requests"] == 0
    assert info["retry_after"] is None


def test_is_allowed_normal_path_still_works():
    mock_redis = MagicMock()
    mock_redis.zremrangebyscore.return_value = 0
    mock_redis.zcard.return_value = 3

    limiter = RedisRateLimiter(mock_redis)
    allowed, info = limiter.is_allowed("some-key", limit=10, window=60)

    assert allowed is True
    assert info["current_requests"] == 3
    mock_redis.zadd.assert_called_once()
