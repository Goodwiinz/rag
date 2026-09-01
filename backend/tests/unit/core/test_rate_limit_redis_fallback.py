"""R7-M7: a Redis outage must not disable rate limiting.

``RedisRateLimiter`` used to return ``(True, 0)`` from every ``except``, so a
Redis failure turned every limited endpoint into an unlimited one — exactly
when the system is least able to absorb the load. It now degrades to the
in-memory limiter it already carries.
"""

from __future__ import annotations

import pytest

from src.core.rate_limit import RedisRateLimiter

pytestmark = pytest.mark.unit


def _broken_limiter(max_attempts: int = 2) -> RedisRateLimiter:
    limiter = RedisRateLimiter(max_attempts, 1, redis_url="redis://unused")

    async def _boom() -> None:
        raise ConnectionError("redis is down")

    limiter._get_redis = _boom  # type: ignore[assignment]
    return limiter


async def test_check_rate_limit_still_enforces_when_redis_errors() -> None:
    limiter = _broken_limiter(max_attempts=2)

    for _ in range(2):
        allowed, _retry = await limiter.check_rate_limit("user-1", prefix="agent_turn")
        assert allowed is True
        await limiter.record_attempt("user-1", prefix="agent_turn")

    allowed, retry_after = await limiter.check_rate_limit("user-1", prefix="agent_turn")
    assert allowed is False, "Redis being down must not fail open"
    assert retry_after >= 1


async def test_is_allowed_degrades_instead_of_allowing_everything() -> None:
    limiter = _broken_limiter(max_attempts=1)

    assert await limiter.is_allowed("user-2") is True
    assert await limiter.is_allowed("user-2") is False


async def test_buckets_stay_separate_in_the_fallback() -> None:
    limiter = _broken_limiter(max_attempts=1)

    await limiter.record_attempt("user-3", prefix="agent_turn")

    allowed, _ = await limiter.check_rate_limit("user-3", prefix="agent_read")
    assert allowed is True, "a different prefix is a different budget"


async def test_degraded_warning_is_throttled(caplog: pytest.LogCaptureFixture) -> None:
    limiter = _broken_limiter()

    with caplog.at_level("WARNING", logger="src.core.rate_limit"):
        for _ in range(5):
            await limiter.check_rate_limit("user-4")

    degraded = [
        r for r in caplog.records if "Redis rate limit unavailable" in r.message
    ]
    assert len(degraded) == 1, "an outage must not flood the log every request"
