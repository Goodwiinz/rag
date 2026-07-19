"""
Backend API performance optimization utilities for the RAG system
"""

import asyncio
import functools
import gzip
import json
import logging
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, List, Optional, Union

import aioredis
import orjson  # Faster JSON parsing
import redis.asyncio as redis
from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)

# Performance metrics
API_REQUEST_COUNT = Counter(
    "api_requests_total", "Total API requests", ["endpoint", "method", "status"]
)
API_REQUEST_DURATION = Histogram(
    "api_request_duration_seconds", "API request duration", ["endpoint", "method"]
)
API_ACTIVE_REQUESTS = Gauge("api_active_requests", "Number of active API requests")
API_RESPONSE_SIZE = Histogram(
    "api_response_size_bytes", "API response size", ["endpoint"]
)


@dataclass
class APIPerformanceConfig:
    """API performance configuration"""

    # Response caching
    enable_response_cache: bool = True
    cache_ttl_default: int = 300  # 5 minutes
    cache_ttl_by_endpoint: Dict[str, int] = None

    # Request size limits
    max_request_size_mb: int = 50
    max_response_size_mb: int = 100

    # Compression
    enable_compression: bool = True
    compression_threshold_bytes: int = 1024

    # Rate limiting
    enable_rate_limiting: bool = True
    default_rate_limit: int = 100  # requests per minute
    rate_limit_by_endpoint: Dict[str, int] = None

    # Connection pooling
    max_connections: int = 100
    connection_timeout: int = 30
    read_timeout: int = 60

    # Pagination
    default_page_size: int = 20
    max_page_size: int = 100

    # Async processing
    max_concurrent_requests: int = 50
    request_timeout: int = 120


class ResponseCache:
    """Intelligent response caching system"""

    def __init__(self, redis_client: redis.Redis, config: APIPerformanceConfig):
        self.redis_client = redis_client
        self.config = config
        self.cache_stats = defaultdict(lambda: {"hits": 0, "misses": 0, "sets": 0})

    def _generate_cache_key(self, request: Request) -> str:
        """Generate cache key from request"""
        # Include relevant request parameters
        key_parts = [
            request.method,
            request.url.path,
            str(dict(request.query_params)),
            # Include user context if available
            getattr(request.state, "user_id", "anonymous"),
            getattr(request.state, "tenant_id", "default"),
        ]

        key_string = "|".join(str(part) for part in key_parts)
        return f"api_cache:{hash(key_string)}"

    def _should_cache_response(self, request: Request, response: Response) -> bool:
        """Determine if response should be cached"""
        # Only cache GET requests
        if request.method != "GET":
            return False

        # Don't cache error responses
        if response.status_code >= 400:
            return False

        # Don't cache large responses
        content_length = len(response.body) if hasattr(response, "body") else 0
        if content_length > self.config.max_response_size_mb * 1024 * 1024:
            return False

        # Check endpoint-specific cache rules
        path = request.url.path
        cache_ttl = self.config.cache_ttl_by_endpoint.get(
            path, self.config.cache_ttl_default
        )

        # Don't cache if TTL is 0 or negative
        if cache_ttl <= 0:
            return False

        return True

    def _get_cache_ttl(self, request: Request) -> int:
        """Get cache TTL for request"""
        path = request.url.path
        return self.config.cache_ttl_by_endpoint.get(
            path, self.config.cache_ttl_default
        )

    async def get_cached_response(self, request: Request) -> Optional[Response]:
        """Get cached response if available"""
        if not self.config.enable_response_cache:
            return None

        cache_key = self._generate_cache_key(request)

        try:
            cached_data = await self.redis_client.get(cache_key)
            if cached_data:
                response_data = json.loads(cached_data)
                self.cache_stats[cache_key]["hits"] += 1
                return Response(
                    content=response_data["content"],
                    status_code=response_data["status_code"],
                    headers=response_data["headers"],
                    media_type=response_data["media_type"],
                )
        except Exception as e:
            logger.error(f"Cache get error: {e}")

        self.cache_stats[cache_key]["misses"] += 1
        return None

    async def cache_response(self, request: Request, response: Response) -> None:
        """Cache response if appropriate"""
        if not self._should_cache_response(request, response):
            return

        cache_key = self._generate_cache_key(request)
        ttl = self._get_cache_ttl(request)

        try:
            response_data = {
                "content": response.body.decode() if hasattr(response, "body") else "",
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "media_type": response.media_type,
            }

            await self.redis_client.setex(cache_key, ttl, json.dumps(response_data))
            self.cache_stats[cache_key]["sets"] += 1

        except Exception as e:
            logger.error(f"Cache set error: {e}")

    async def invalidate_cache_pattern(self, pattern: str) -> int:
        """Invalidate cache entries matching pattern"""
        try:
            keys = await self.redis_client.keys(f"api_cache:*{pattern}*")
            if keys:
                return await self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache invalidation error: {e}")
            return 0

    def get_cache_stats(self) -> Dict[str, Dict]:
        """Get cache statistics"""
        return dict(self.cache_stats)


class RateLimiter:
    """Advanced rate limiting system"""

    def __init__(self, redis_client: redis.Redis, config: APIPerformanceConfig):
        self.redis_client = redis_client
        self.config = config
        self.limit_stats = defaultdict(int)

    async def is_allowed(
        self, key: str, limit: Optional[int] = None, window: int = 60
    ) -> tuple[bool, Dict]:
        """Check if request is allowed and return rate limit info"""
        if not self.config.enable_rate_limiting:
            return True, {
                "limit": float("inf"),
                "remaining": float("inf"),
                "reset_time": 0,
            }

        limit = limit or self.config.default_rate_limit
        current_time = int(time.time())
        window_start = current_time - window
        redis_key = f"rate_limit:{key}"

        try:
            # Use Redis sliding window algorithm
            pipeline = self.redis_client.pipeline()
            pipeline.zremrangebyscore(redis_key, 0, window_start)
            pipeline.zcard(redis_key)
            pipeline.expire(redis_key, window)
            _, current_count, _ = await pipeline.execute()

            if current_count >= limit:
                # Get oldest request time for reset time
                oldest = await self.redis_client.zrange(
                    redis_key, 0, 0, withscores=True
                )
                reset_time = (
                    int(oldest[0][1]) + window if oldest else current_time + window
                )

                return False, {"limit": limit, "remaining": 0, "reset_time": reset_time}

            # Add current request
            await self.redis_client.zadd(redis_key, {str(current_time): current_time})
            self.limit_stats[key] += 1

            return True, {
                "limit": limit,
                "remaining": limit - current_count - 1,
                "reset_time": current_time + window,
            }

        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            # Allow request if rate limiting fails
            return True, {
                "limit": float("inf"),
                "remaining": float("inf"),
                "reset_time": 0,
            }

    def get_rate_limit_stats(self) -> Dict[str, int]:
        """Get rate limiting statistics"""
        return dict(self.limit_stats)


class APIPerformanceMiddleware:
    """Comprehensive API performance middleware"""

    def __init__(
        self, app, redis_client: redis.Redis, config: APIPerformanceConfig = None
    ):
        self.app = app
        self.config = config or APIPerformanceConfig()
        self.response_cache = ResponseCache(redis_client, self.config)
        self.rate_limiter = RateLimiter(redis_client, self.config)

    async def __call__(self, scope, receive, send):
        """ASGI application with performance optimizations"""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Create request object
        request = Request(scope, receive)

        # Increment active requests
        API_ACTIVE_REQUESTS.inc()

        start_time = time.time()

        try:
            # Rate limiting
            client_key = f"{request.client.host}:{request.url.path}"
            is_allowed, rate_limit_info = await self.rate_limiter.is_allowed(client_key)

            if not is_allowed:
                response = JSONResponse(
                    status_code=429,
                    content={"error": "Rate limit exceeded", **rate_limit_info},
                )
                await self._send_response(response, send, scope, start_time, request)
                return

            # Check cache for GET requests
            if request.method == "GET":
                cached_response = await self.response_cache.get_cached_response(request)
                if cached_response:
                    await self._send_response(
                        cached_response, send, scope, start_time, request
                    )
                    return

            # Process request
            response = await self._call_asgi(request, receive, send)

            # Cache successful GET responses
            if request.method == "GET" and response.status_code == 200:
                await self.response_cache.cache_response(request, response)

            await self._send_response(response, send, scope, start_time, request)

        except Exception as e:
            logger.error(f"API middleware error: {e}")
            response = JSONResponse(
                status_code=500, content={"error": "Internal server error"}
            )
            await self._send_response(response, send, scope, start_time, request)

        finally:
            API_ACTIVE_REQUESTS.dec()

    async def _call_asgi(self, request: Request, receive, send):
        """Call the ASGI application"""
        # Create a wrapper to capture the response
        response_wrapper = ResponseWrapper()

        async def wrapped_send(message):
            if message["type"] == "http.response.start":
                response_wrapper.status_code = message["status"]
                response_wrapper.headers = message.get("headers", [])
            await send(message)

        await self.app(dict(request), receive, wrapped_send)
        return response_wrapper

    async def _send_response(self, response, send, scope, start_time, request):
        """Send response with performance optimizations"""
        duration = time.time() - start_time

        # Record metrics
        API_REQUEST_COUNT.labels(
            endpoint=request.url.path,
            method=request.method,
            status=response.status_code,
        ).inc()

        API_REQUEST_DURATION.labels(
            endpoint=request.url.path, method=request.method
        ).observe(duration)

        # Add performance headers
        headers = dict(response.headers) if hasattr(response, "headers") else {}
        headers["X-Response-Time"] = f"{duration:.3f}s"

        # Compress response if enabled and applicable
        if self.config.enable_compression and "gzip" in request.headers.get(
            "accept-encoding", ""
        ):
            # This is simplified - in practice, you'd need to implement
            # proper response compression
            pass

        # Send response
        await send(
            {
                "type": "http.response.start",
                "status": response.status_code,
                "headers": [(k.encode(), v.encode()) for k, v in headers.items()],
            }
        )

        body = response.body if hasattr(response, "body") else b""
        await send(
            {
                "type": "http.response.body",
                "body": body,
            }
        )


class ResponseWrapper:
    """Wrapper to capture ASGI response"""

    def __init__(self):
        self.status_code = 200
        self.headers = []
        self.body = b""


# Decorators for API optimization
def cache_api_response(ttl: int = 300):
    """Decorator for caching API responses"""

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # This is a simplified implementation
            # In practice, you'd integrate with the response cache
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def rate_api_endpoint(limit: int, window: int = 60):
    """Decorator for rate limiting API endpoints"""

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # This is a simplified implementation
            # In practice, you'd integrate with the rate limiter
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def measure_api_performance(func: Callable):
    """Decorator for measuring API performance"""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            logger.info(f"{func.__name__} completed in {duration:.3f}s")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"{func.__name__} failed after {duration:.3f}s: {e}")
            raise

    return wrapper


class AsyncBatchProcessor:
    """Batch processing for API operations"""

    def __init__(self, max_batch_size: int = 100, max_wait_time: float = 0.1):
        self.max_batch_size = max_batch_size
        self.max_wait_time = max_wait_time
        self.pending_requests = []
        self.processing = False

    async def add_request(self, request_data: Dict) -> Any:
        """Add request to batch processing queue"""
        future = asyncio.Future()
        self.pending_requests.append((request_data, future))

        if not self.processing:
            asyncio.create_task(self._process_batch())

        return await future

    async def _process_batch(self):
        """Process batch of requests"""
        if self.processing:
            return

        self.processing = True

        while self.pending_requests:
            # Wait for more requests or timeout
            start_time = time.time()
            while (
                len(self.pending_requests) < self.max_batch_size
                and time.time() - start_time < self.max_wait_time
            ):
                await asyncio.sleep(0.01)

            if not self.pending_requests:
                break

            # Process current batch
            batch = self.pending_requests[: self.max_batch_size]
            self.pending_requests = self.pending_requests[self.max_batch_size :]

            try:
                results = await self._execute_batch([req for req, _ in batch])

                for (_, future), result in zip(batch, results):
                    future.set_result(result)
            except Exception as e:
                for _, future in batch:
                    future.set_exception(e)

        self.processing = False

    async def _execute_batch(self, requests: List[Dict]) -> List[Any]:
        """Execute batch of requests - to be implemented by specific use case"""
        # This would be implemented based on the specific batch operation
        return [None] * len(requests)


# Utility functions for API optimization
async def validate_request_size(request: Request, max_size_mb: int = 50) -> bool:
    """Validate request size"""
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > max_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"Request too large. Maximum size is {max_size_mb}MB",
        )
    return True


def paginate_response(
    data: List[Any], page: int, page_size: int, max_page_size: int = 100
) -> Dict:
    """Paginate response data"""
    page_size = min(page_size, max_page_size)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size

    return {
        "data": data[start_idx:end_idx],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": len(data),
            "total_pages": (len(data) + page_size - 1) // page_size,
            "has_next": end_idx < len(data),
            "has_prev": page > 1,
        },
    }


async def compress_response(
    data: Union[str, bytes], threshold_bytes: int = 1024
) -> bytes:
    """Compress response data if beneficial"""
    if isinstance(data, str):
        data = data.encode("utf-8")

    if len(data) < threshold_bytes:
        return data

    try:
        compressed = gzip.compress(data, compresslevel=6)
        # Only use compression if it actually reduces size
        if len(compressed) < len(data):
            return compressed
    except Exception as e:
        logger.error(f"Compression error: {e}")

    return data
