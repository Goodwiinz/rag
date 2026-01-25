"""
Cache Service Integration Tests

Tests for Redis caching with real Redis instance to validate:
- TTL expiration behavior
- Rate limiting with counters
- Distributed locking
- Pub/Sub messaging
- Cache invalidation patterns
"""

import pytest
import asyncio
import time
import uuid
import json
from concurrent.futures import ThreadPoolExecutor

# Mark all tests in this module
pytestmark = [
    pytest.mark.requires_redis,
    pytest.mark.integration,
]


@pytest.fixture
def sync_redis_client(redis_container):
    """Create a synchronous Redis client for testing."""
    import redis

    client = redis.Redis.from_url(redis_container["url"])
    yield client
    client.flushdb()
    client.close()


@pytest.fixture
async def async_redis_client(redis_container):
    """Create an async Redis client for testing."""
    import redis.asyncio as aioredis

    client = aioredis.from_url(
        redis_container["url"],
        encoding="utf-8",
        decode_responses=True,
    )
    yield client
    await client.flushdb()
    await client.close()


class TestTTLExpiration:
    """Tests for TTL (Time To Live) expiration."""

    def test_caches_with_ttl_expiration(self, sync_redis_client):
        """Verify values expire after TTL."""
        key = f"ttl_test:{uuid.uuid4().hex}"
        value = {"data": "test_value", "timestamp": time.time()}

        # Set with 1 second TTL
        sync_redis_client.setex(key, 1, json.dumps(value))

        # Immediately retrieve - should exist
        retrieved = sync_redis_client.get(key)
        assert retrieved is not None
        assert json.loads(retrieved)["data"] == "test_value"

        # Wait for expiration
        time.sleep(1.5)

        # Should be expired
        expired = sync_redis_client.get(key)
        assert expired is None

    def test_ttl_countdown(self, sync_redis_client):
        """Verify TTL countdown is accurate."""
        key = f"ttl_countdown:{uuid.uuid4().hex}"

        sync_redis_client.setex(key, 10, "test_value")

        # Check initial TTL
        initial_ttl = sync_redis_client.ttl(key)
        assert 8 <= initial_ttl <= 10

        # Wait and check again
        time.sleep(2)
        remaining_ttl = sync_redis_client.ttl(key)
        assert 6 <= remaining_ttl <= 8

    def test_persist_removes_ttl(self, sync_redis_client):
        """Verify PERSIST removes TTL and makes key permanent."""
        key = f"persist_test:{uuid.uuid4().hex}"

        sync_redis_client.setex(key, 5, "test_value")
        assert sync_redis_client.ttl(key) > 0

        # Remove TTL
        sync_redis_client.persist(key)

        # TTL should return -1 (no expiration)
        assert sync_redis_client.ttl(key) == -1

        # Value should still exist (Redis returns bytes)
        assert sync_redis_client.get(key) == b"test_value"

    def test_expire_updates_ttl(self, sync_redis_client):
        """Verify EXPIRE updates existing TTL."""
        key = f"expire_update:{uuid.uuid4().hex}"

        sync_redis_client.setex(key, 10, "test_value")
        assert sync_redis_client.ttl(key) <= 10

        # Update TTL to longer duration
        sync_redis_client.expire(key, 60)
        assert sync_redis_client.ttl(key) > 50


class TestRateLimiting:
    """Tests for rate limiting using Redis counters."""

    def test_rate_limiter_blocks_after_limit(self, sync_redis_client):
        """Verify rate limiter blocks requests after limit is reached."""
        user_id = f"user:{uuid.uuid4().hex}"
        limit = 5
        window_seconds = 10

        def check_rate_limit(user: str, max_requests: int, window: int) -> bool:
            """Simple rate limiter implementation."""
            key = f"rate_limit:{user}:{int(time.time()) // window}"
            current = sync_redis_client.incr(key)

            if current == 1:
                sync_redis_client.expire(key, window)

            return current <= max_requests

        # First 5 requests should succeed
        for i in range(limit):
            result = check_rate_limit(user_id, limit, window_seconds)
            assert result is True, f"Request {i+1} should be allowed"

        # 6th request should be blocked
        result = check_rate_limit(user_id, limit, window_seconds)
        assert result is False, "Request 6 should be blocked"

    def test_sliding_window_rate_limit(self, sync_redis_client):
        """Verify sliding window rate limiting."""
        user_id = f"sliding:{uuid.uuid4().hex}"

        def sliding_window_rate_limit(user: str, max_requests: int, window_ms: int) -> bool:
            """Sliding window rate limiter using sorted set."""
            key = f"sliding_rate:{user}"
            now = time.time() * 1000  # Current time in milliseconds
            window_start = now - window_ms

            # Remove old entries
            sync_redis_client.zremrangebyscore(key, 0, window_start)

            # Count current window
            current_count = sync_redis_client.zcard(key)

            if current_count < max_requests:
                # Add new request
                sync_redis_client.zadd(key, {f"{now}:{uuid.uuid4().hex}": now})
                sync_redis_client.expire(key, window_ms // 1000 + 1)
                return True

            return False

        # 3 requests in 1 second window
        limit = 3
        window_ms = 1000

        for i in range(limit):
            assert sliding_window_rate_limit(user_id, limit, window_ms) is True

        # 4th should fail
        assert sliding_window_rate_limit(user_id, limit, window_ms) is False


class TestDistributedLocking:
    """Tests for distributed locking."""

    def test_distributed_lock_prevents_race(self, sync_redis_client):
        """Verify distributed lock prevents concurrent access."""
        lock_key = f"lock:{uuid.uuid4().hex}"
        counter_key = f"counter:{uuid.uuid4().hex}"
        sync_redis_client.set(counter_key, 0)

        def acquire_lock(key: str, timeout: int = 10) -> bool:
            """Acquire a distributed lock."""
            lock_value = str(uuid.uuid4())
            acquired = sync_redis_client.set(
                key,
                lock_value,
                ex=timeout,
                nx=True  # Only set if not exists
            )
            return acquired is not None

        def release_lock(key: str):
            """Release a distributed lock."""
            sync_redis_client.delete(key)

        def increment_with_lock():
            """Increment counter with lock protection."""
            if acquire_lock(lock_key, timeout=5):
                try:
                    # Critical section
                    current = int(sync_redis_client.get(counter_key) or 0)
                    time.sleep(0.01)  # Simulate work
                    sync_redis_client.set(counter_key, current + 1)
                finally:
                    release_lock(lock_key)
                return True
            return False

        # Run concurrent increments
        results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(increment_with_lock) for _ in range(10)]
            results = [f.result() for f in futures]

        # Some should succeed, some should fail due to lock
        successful = sum(results)
        final_value = int(sync_redis_client.get(counter_key))

        # Counter should match successful operations
        assert final_value == successful
        assert successful > 0  # At least some should succeed

    def test_lock_expiration(self, sync_redis_client):
        """Verify lock auto-expires to prevent deadlocks."""
        lock_key = f"expire_lock:{uuid.uuid4().hex}"

        # Acquire lock with 1 second TTL
        acquired = sync_redis_client.set(lock_key, "owner1", ex=1, nx=True)
        assert acquired is True

        # Second attempt should fail immediately
        not_acquired = sync_redis_client.set(lock_key, "owner2", ex=1, nx=True)
        assert not_acquired is None

        # Wait for expiration
        time.sleep(1.5)

        # Now should be able to acquire
        acquired_after = sync_redis_client.set(lock_key, "owner2", ex=1, nx=True)
        assert acquired_after is True


class TestPubSub:
    """Tests for Pub/Sub messaging."""

    def test_pubsub_broadcasts_to_subscribers(self, sync_redis_client):
        """Verify Pub/Sub message delivery."""
        channel = f"test_channel:{uuid.uuid4().hex}"
        received_messages = []

        def subscriber_thread():
            """Subscriber that collects messages."""
            pubsub = sync_redis_client.pubsub()
            pubsub.subscribe(channel)

            # Wait for messages (with timeout)
            start_time = time.time()
            while time.time() - start_time < 3:
                message = pubsub.get_message(timeout=0.1)
                if message and message["type"] == "message":
                    received_messages.append(message["data"])
                    if len(received_messages) >= 3:
                        break

            pubsub.unsubscribe()
            pubsub.close()

        # Start subscriber in thread
        with ThreadPoolExecutor(max_workers=1) as executor:
            subscriber_future = executor.submit(subscriber_thread)

            # Give subscriber time to connect
            time.sleep(0.2)

            # Publish messages
            sync_redis_client.publish(channel, "message_1")
            sync_redis_client.publish(channel, "message_2")
            sync_redis_client.publish(channel, "message_3")

            # Wait for subscriber to finish
            subscriber_future.result(timeout=5)

        # Verify messages received
        assert len(received_messages) == 3
        assert "message_1" in [m.decode() if isinstance(m, bytes) else m for m in received_messages]


class TestCachePatterns:
    """Tests for common cache patterns."""

    def test_cache_aside_pattern(self, sync_redis_client):
        """Verify cache-aside (lazy loading) pattern."""
        cache_key = f"cache_aside:{uuid.uuid4().hex}"
        db_calls = {"count": 0}

        def get_from_db():
            """Simulate database fetch."""
            db_calls["count"] += 1
            return {"id": 123, "name": "Test Entity"}

        def get_with_cache(key: str):
            """Get data with cache-aside pattern."""
            # Try cache first
            cached = sync_redis_client.get(key)
            if cached:
                return json.loads(cached), "cache"

            # Cache miss - get from DB
            data = get_from_db()

            # Store in cache
            sync_redis_client.setex(key, 300, json.dumps(data))

            return data, "db"

        # First call - cache miss
        result1, source1 = get_with_cache(cache_key)
        assert source1 == "db"
        assert db_calls["count"] == 1

        # Second call - cache hit
        result2, source2 = get_with_cache(cache_key)
        assert source2 == "cache"
        assert db_calls["count"] == 1  # No additional DB call

        # Results should match
        assert result1 == result2

    def test_write_through_pattern(self, sync_redis_client):
        """Verify write-through cache pattern."""
        cache_key = f"write_through:{uuid.uuid4().hex}"
        mock_db = {}

        def save_to_db(data):
            """Simulate database save."""
            mock_db[data["id"]] = data

        def write_through(key: str, data: dict):
            """Write-through pattern - write to cache and DB."""
            # Write to cache
            sync_redis_client.setex(key, 300, json.dumps(data))

            # Write to DB
            save_to_db(data)

        data = {"id": "entity_1", "value": "test_data"}
        write_through(cache_key, data)

        # Both cache and DB should have the data
        cached = json.loads(sync_redis_client.get(cache_key))
        assert cached == data
        assert mock_db["entity_1"] == data

    def test_cache_invalidation(self, sync_redis_client):
        """Verify cache invalidation patterns."""
        prefix = f"invalidation_test:{uuid.uuid4().hex}"

        # Set up multiple cached values
        keys = []
        for i in range(5):
            key = f"{prefix}:item:{i}"
            sync_redis_client.setex(key, 300, f"value_{i}")
            keys.append(key)

        # Verify all exist
        for key in keys:
            assert sync_redis_client.exists(key)

        # Invalidate using pattern
        pattern_keys = sync_redis_client.keys(f"{prefix}:item:*")
        if pattern_keys:
            sync_redis_client.delete(*pattern_keys)

        # Verify all deleted
        for key in keys:
            assert not sync_redis_client.exists(key)


@pytest.mark.skip(reason="Async fixture scope issue with pytest-asyncio - needs further investigation")
class TestAsyncCache:
    """Tests for async Redis operations."""

    @pytest.mark.asyncio
    async def test_async_cache_operations(self, async_redis_client):
        """Verify async cache operations."""
        key = f"async_test:{uuid.uuid4().hex}"
        value = {"async": True, "data": "test"}

        # Set
        await async_redis_client.setex(key, 60, json.dumps(value))

        # Get
        retrieved = await async_redis_client.get(key)
        assert json.loads(retrieved) == value

        # Delete
        deleted = await async_redis_client.delete(key)
        assert deleted == 1

        # Verify deleted
        final = await async_redis_client.get(key)
        assert final is None

    @pytest.mark.asyncio
    async def test_async_pipeline(self, async_redis_client):
        """Verify async pipeline operations."""
        prefix = f"pipeline:{uuid.uuid4().hex}"

        # Use pipeline for batch operations
        async with async_redis_client.pipeline() as pipe:
            for i in range(10):
                pipe.setex(f"{prefix}:key:{i}", 60, f"value_{i}")
            results = await pipe.execute()

        # All should succeed
        assert all(r is True for r in results)

        # Verify all values set
        async with async_redis_client.pipeline() as pipe:
            for i in range(10):
                pipe.get(f"{prefix}:key:{i}")
            values = await pipe.execute()

        assert len(values) == 10
        for i, v in enumerate(values):
            assert v == f"value_{i}"

    @pytest.mark.asyncio
    async def test_async_increment_with_ttl(self, async_redis_client):
        """Verify async increment with TTL."""
        key = f"async_incr:{uuid.uuid4().hex}"

        # Increment and set TTL atomically
        result = await async_redis_client.incr(key)
        await async_redis_client.expire(key, 60)

        assert result == 1

        # Subsequent increments
        for i in range(4):
            result = await async_redis_client.incr(key)

        assert result == 5

        # TTL should be set
        ttl = await async_redis_client.ttl(key)
        assert 50 <= ttl <= 60
