import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import redis.asyncio as redis
from src.core.config import settings

logger = logging.getLogger(__name__)

class RateLimiterInterface(ABC):
    @abstractmethod
    async def is_allowed(self, identifier: str, prefix: str = "") -> bool:
        """Check if identifier is allowed to make an attempt"""
        pass

    @abstractmethod
    async def get_remaining_attempts(self, identifier: str, prefix: str = "") -> int:
        """Get remaining attempts for identifier"""
        pass

    @abstractmethod
    async def close(self):
        """Cleanup resources"""
        pass

class InMemoryRateLimiter(RateLimiterInterface):
    """Simple rate limiter for authentication endpoints (In-Memory)"""

    def __init__(self, max_attempts: int = 5, window_minutes: int = 15):
        self.max_attempts = max_attempts
        self.window_minutes = window_minutes
        self.attempts: Dict[str, List[datetime]] = {}

    async def is_allowed(self, identifier: str, prefix: str = "") -> bool:
        """Check if identifier is allowed to make an attempt"""
        key = f"{prefix}:{identifier}" if prefix else identifier
        now = datetime.now(timezone.utc)
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

        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=self.window_minutes)

        # Count recent attempts
        recent_attempts = [
            attempt_time
            for attempt_time in self.attempts[key]
            if attempt_time > window_start
        ]

        return max(0, self.max_attempts - len(recent_attempts))

    async def close(self):
        self.attempts.clear()

class RedisRateLimiter(RateLimiterInterface):
    """Redis-based rate limiter for distributed environments"""

    def __init__(self, max_attempts: int, window_minutes: int, redis_url: str = None):
        self.max_attempts = max_attempts
        self.window_minutes = window_minutes
        self.redis_url = redis_url or settings.REDIS_URL
        self._redis: Optional[redis.Redis] = None
        # Lua script to atomically increment and set expire only on first use
        self._incr_expire_script = """
        local current = redis.call("INCR", KEYS[1])
        if current == 1 then
            redis.call("EXPIRE", KEYS[1], ARGV[1])
        end
        return current
        """

    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis connection"""
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    async def is_allowed(self, identifier: str, prefix: str = "") -> bool:
        """Check if identifier is allowed to make an attempt"""
        try:
            client = await self._get_redis()
            key = f"auth_rate_limit:{prefix}:{identifier}" if prefix else f"auth_rate_limit:{identifier}"

            # Execute Lua script for atomicity and correct expiration behavior
            # ARGV[1] is expiration in seconds
            current = await client.eval(
                self._incr_expire_script,
                1,
                key,
                self.window_minutes * 60
            )

            return int(current) <= self.max_attempts

        except Exception as e:
            logger.error(f"Redis rate limit error: {e}")
            # Fail open - allow request if Redis is down
            return True

    async def get_remaining_attempts(self, identifier: str, prefix: str = "") -> int:
        """Get remaining attempts for identifier"""
        try:
            client = await self._get_redis()
            key = f"auth_rate_limit:{prefix}:{identifier}" if prefix else f"auth_rate_limit:{identifier}"

            current = await client.get(key)
            if current is None:
                return self.max_attempts

            return max(0, self.max_attempts - int(current))

        except Exception as e:
            logger.error(f"Redis rate limit error: {e}")
            return self.max_attempts

    async def close(self):
        """Close Redis connection"""
        if self._redis:
            await self._redis.close()
            self._redis = None

def create_rate_limiter(max_attempts: int, window_minutes: int) -> RateLimiterInterface:
    """Factory to create appropriate rate limiter"""
    # If REDIS_URL is configured (and not explicitly disabled), use Redis
    if settings.REDIS_URL:
        # We assume Redis is available if URL is set.
        # RedisRateLimiter handles connection failures gracefully (fails open).
        logger.info(f"Initializing RedisRateLimiter with URL: {settings.REDIS_URL}")
        return RedisRateLimiter(max_attempts, window_minutes)

    logger.warning("REDIS_URL not set. Using InMemoryRateLimiter (not suitable for production multi-worker setups).")
    return InMemoryRateLimiter(max_attempts, window_minutes)
