"""
Rate limiting utilities for distributed environments.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import redis.asyncio as redis
from src.core.config import settings

logger = logging.getLogger(__name__)


class RateLimiter(ABC):
    """Abstract base class for rate limiters"""

    @abstractmethod
    async def is_allowed(self, identifier: str, prefix: str = "") -> bool:
        """Check if identifier is allowed to make an attempt"""
        pass

    @abstractmethod
    async def get_remaining_attempts(self, identifier: str, prefix: str = "") -> int:
        """Get remaining attempts for identifier"""
        pass


class InMemoryRateLimiter(RateLimiter):
    """In-memory rate limiter (async version of original)"""

    def __init__(self, max_attempts: int = 5, window_minutes: int = 15):
        self.max_attempts = max_attempts
        self.window_minutes = window_minutes
        self.attempts: Dict[str, List[datetime]] = {}

    async def is_allowed(self, identifier: str, prefix: str = "") -> bool:
        """Check if identifier is allowed to make an attempt"""
        key = f"{prefix}:{identifier}" if prefix else identifier
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=self.window_minutes)

        # Clean old attempts
        if key in self.attempts:
            self.attempts[key] = [
                attempt_time
                for attempt_time in self.attempts[key]
                if attempt_time > window_start
            ]
        else:
            self.attempts[key] = []

        # Check if under limit
        if len(self.attempts[key]) >= self.max_attempts:
            return False

        # Record this attempt
        self.attempts[key].append(now)
        return True

    async def get_remaining_attempts(self, identifier: str, prefix: str = "") -> int:
        """Get remaining attempts for identifier"""
        key = f"{prefix}:{identifier}" if prefix else identifier
        if key not in self.attempts:
            return self.max_attempts

        now = datetime.utcnow()
        window_start = now - timedelta(minutes=self.window_minutes)

        # Count recent attempts
        recent_attempts = [
            attempt_time
            for attempt_time in self.attempts[key]
            if attempt_time > window_start
        ]

        return max(0, self.max_attempts - len(recent_attempts))


class RedisRateLimiter(RateLimiter):
    """Redis-based rate limiter for distributed environments"""

    def __init__(
        self,
        redis_url: str = None,
        max_attempts: int = 5,
        window_minutes: int = 15,
    ):
        self.redis_url = redis_url or settings.REDIS_URL
        self.max_attempts = max_attempts
        self.window_seconds = window_minutes * 60
        self._redis: Optional[redis.Redis] = None

    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis connection"""
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    async def is_allowed(self, identifier: str, prefix: str = "") -> bool:
        """
        Check if identifier is allowed to make an attempt.
        Uses a fixed window counter in Redis with atomic expiration via Lua script.
        """
        try:
            redis_client = await self._get_redis()
            # Normalize key
            key = f"rate_limit:{prefix}:{identifier}" if prefix else f"rate_limit:{identifier}"

            # Lua script to atomically increment and set expiry on first use
            lua_script = """
            local current = redis.call("INCR", KEYS[1])
            if current == 1 then
                redis.call("EXPIRE", KEYS[1], ARGV[1])
            end
            return current
            """

            # Execute script
            current_count = await redis_client.eval(lua_script, 1, key, self.window_seconds)

            return current_count <= self.max_attempts

        except Exception as e:
            logger.error(f"Redis rate limiting error: {e}")
            # Fail open to avoid blocking legitimate users on Redis error
            return True

    async def get_remaining_attempts(self, identifier: str, prefix: str = "") -> int:
        """Get remaining attempts"""
        try:
            redis_client = await self._get_redis()
            key = f"rate_limit:{prefix}:{identifier}" if prefix else f"rate_limit:{identifier}"

            current_count = await redis_client.get(key)
            if current_count is None:
                return self.max_attempts

            return max(0, self.max_attempts - int(current_count))

        except Exception as e:
            logger.error(f"Redis rate limiting error: {e}")
            return self.max_attempts

    async def close(self):
        """Close Redis connection"""
        if self._redis:
            await self._redis.close()


def get_rate_limiter(
    max_attempts: int = 5, window_minutes: int = 15
) -> RateLimiter:
    """Factory function to get appropriate rate limiter"""
    if settings.REDIS_URL:
        return RedisRateLimiter(
            max_attempts=max_attempts, window_minutes=window_minutes
        )
    return InMemoryRateLimiter(max_attempts=max_attempts, window_minutes=window_minutes)
