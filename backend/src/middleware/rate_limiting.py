"""
Rate limiting middleware for analytics endpoints
Protects against abuse and ensures fair usage
"""

import time
import hashlib
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, deque
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import redis
import logging

from src.core.config import settings
from src.models.user import UserRole

logger = logging.getLogger(__name__)


class InMemoryRateLimiter:
    """
    In-memory rate limiter using sliding window algorithm
    Fallback when Redis is not available
    """

    def __init__(self):
        # Structure: {key: deque of timestamps}
        self.requests: Dict[str, deque] = defaultdict(deque)
        self.locks: Dict[str, bool] = {}

    def is_allowed(self, key: str, limit: int, window: int) -> Tuple[bool, Dict]:
        """
        Check if request is allowed using sliding window

        Args:
            key: Rate limit key (e.g., user_id, ip_address)
            limit: Max requests allowed
            window: Time window in seconds

        Returns:
            Tuple of (allowed, info_dict)
        """
        now = time.time()
        window_start = now - window

        # Clean old requests
        while self.requests[key] and self.requests[key][0] < window_start:
            self.requests[key].popleft()

        current_requests = len(self.requests[key])

        info = {
            "current_requests": current_requests,
            "limit": limit,
            "window": window,
            "reset_time": now + window,
            "retry_after": None
        }

        if current_requests >= limit:
            # Calculate when the oldest request will expire
            if self.requests[key]:
                oldest_request = self.requests[key][0]
                info["retry_after"] = int(oldest_request + window - now)
            return False, info

        # Add current request
        self.requests[key].append(now)
        return True, info


class RedisRateLimiter:
    """
    Redis-based rate limiter with sliding window algorithm
    """

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def is_allowed(self, key: str, limit: int, window: int) -> Tuple[bool, Dict]:
        """
        Check if request is allowed using Redis sliding window

        Uses Redis sorted set for O(log N) operations
        """
        now = time.time()
        window_start = now - window
        pipeline = self.redis.pipeline()

        try:
            # Remove old requests outside the window
            self.redis.zremrangebyscore(key, 0, window_start)

            # Count current requests in window
            current_requests = self.redis.zcard(key)

            info = {
                "current_requests": current_requests,
                "limit": limit,
                "window": window,
                "reset_time": now + window,
                "retry_after": None
            }

            if current_requests >= limit:
                # Get oldest request timestamp to calculate retry_after
                oldest = self.redis.zrange(key, 0, 0, withscores=True)
                if oldest:
                    oldest_timestamp = oldest[0][1]
                    info["retry_after"] = int(oldest_timestamp + window - now)
                return False, info

            # Add current request
            self.redis.zadd(key, {str(now): now})
            self.redis.expire(key, window)

            return True, info

        except redis.RedisError as e:
            logger.error(f"Redis rate limiter error: {e}")
            # Fallback to allowing the request
            return True, info


class AnalyticsRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware specifically for analytics endpoints
    """

    def __init__(self, app, redis_client: Optional[redis.Redis] = None):
        super().__init__(app)

        if redis_client:
            self.rate_limiter = RedisRateLimiter(redis_client)
        else:
            self.rate_limiter = InMemoryRateLimiter()
            logger.warning("Using in-memory rate limiter. Consider using Redis for production.")

        # Rate limit configurations
        self.rate_limits = {
            # General analytics limits
            UserRole.USER: {"requests": 100, "window": 3600},  # 100 requests/hour
            UserRole.ANALYST: {"requests": 500, "window": 3600},  # 500 requests/hour
            UserRole.CONTENT_MANAGER: {"requests": 1000, "window": 3600},  # 1000 requests/hour
            UserRole.ADMIN: {"requests": 2000, "window": 3600},  # 2000 requests/hour

            # Heavy operation limits (e.g., large reports)
            "heavy_operations": {"requests": 10, "window": 3600},  # 10 heavy operations/hour

            # Export limits
            "exports": {"requests": 20, "window": 3600},  # 20 exports/hour

            # API call limits (smaller window)
            "api_calls": {"requests": 50, "window": 300},  # 50 requests/5 minutes
        }

    def _get_rate_limit_key(self, request: Request, limit_type: str = "api_calls") -> str:
        """
        Generate rate limit key based on request context
        """
        # Try to get user context from request state (set by auth middleware)
        user_context = getattr(request.state, "user_context", None)

        if user_context and user_context.get("user_id"):
            base_key = f"analytics:{user_context['user_id']}"
        else:
            # Fallback to IP-based limiting
            client_ip = request.client.host if request.client else "unknown"
            base_key = f"analytics:ip:{client_ip}"

        return f"{base_key}:{limit_type}"

    def _is_heavy_operation(self, request: Request) -> bool:
        """
        Determine if this is a heavy analytics operation
        """
        path = request.url.path.lower()

        heavy_patterns = [
            "/reports/generate",
            "/analytics/export",
            "/quality/trends",
            "/behavior/analysis",
            "/performance/summary"
        ]

        return any(pattern in path for pattern in heavy_patterns)

    def _is_export_operation(self, request: Request) -> bool:
        """
        Determine if this is an export operation
        """
        path = request.url.path.lower()
        query = request.url.query.lower()

        export_patterns = [
            "/export",
            "/download",
            "format=csv",
            "format=excel",
            "format=pdf"
        ]

        return any(pattern in path or pattern in query for pattern in export_patterns)

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Apply rate limiting to analytics requests
        """
        # Only apply to analytics endpoints
        if not request.url.path.startswith("/api/") or "analytics" not in request.url.path:
            return await call_next(request)

        # Get user role from request state (should be set by auth middleware)
        user_context = getattr(request.state, "user_context", {})
        user_role_str = user_context.get("user_role", "USER")

        try:
            user_role = UserRole(user_role_str)
        except ValueError:
            user_role = UserRole.USER

        # Determine rate limit type and get appropriate limits
        if self._is_heavy_operation(request):
            limit_config = self.rate_limits["heavy_operations"]
            limit_type = "heavy_operations"
        elif self._is_export_operation(request):
            limit_config = self.rate_limits["exports"]
            limit_type = "exports"
        else:
            limit_config = self.rate_limits.get(user_role, self.rate_limits[UserRole.USER])
            limit_type = "api_calls"

        # Generate rate limit key
        rate_limit_key = self._get_rate_limit_key(request, limit_type)

        # Check rate limit
        allowed, info = self.rate_limiter.is_allowed(
            key=rate_limit_key,
            limit=limit_config["requests"],
            window=limit_config["window"]
        )

        # Log rate limiting attempt
        log_data = {
            "path": request.url.path,
            "method": request.method,
            "limit_type": limit_type,
            "current_requests": info["current_requests"],
            "limit": info["limit"],
            "allowed": allowed
        }

        if user_context.get("user_id"):
            log_data["user_id"] = user_context["user_id"]
        else:
            log_data["client_ip"] = request.client.host if request.client else "unknown"

        if not allowed:
            logger.warning(
                f"Rate limit exceeded for analytics request",
                extra=log_data
            )

            # Add rate limit headers
            headers = {
                "X-RateLimit-Limit": str(info["limit"]),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(info["reset_time"])),
            }

            if info["retry_after"]:
                headers["Retry-After"] = str(info["retry_after"])

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {info['limit']} requests per {info['window']} seconds.",
                headers=headers
            )
        else:
            logger.info(
                f"Rate limit check passed for analytics request",
                extra=log_data
            )

            # Add rate limit headers to response
            response = await call_next(request)

            remaining_requests = max(0, info["limit"] - info["current_requests"])
            response.headers["X-RateLimit-Limit"] = str(info["limit"])
            response.headers["X-RateLimit-Remaining"] = str(remaining_requests)
            response.headers["X-RateLimit-Reset"] = str(int(info["reset_time"]))

            return response


def get_rate_limiter(redis_client: Optional[redis.Redis] = None):
    """
    Factory function to get appropriate rate limiter
    """
    if redis_client:
        try:
            # Test Redis connection
            redis_client.ping()
            return RedisRateLimiter(redis_client)
        except redis.RedisError as e:
            logger.error(f"Redis connection failed, using in-memory rate limiter: {e}")

    return InMemoryRateLimiter()