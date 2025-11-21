"""
WebSocket Caching and Resilience Layer
Handles high-throughput message delivery, caching, and failure recovery
"""

import asyncio
import logging
import json
import time
import hashlib
from typing import Dict, List, Optional, Set, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import aioredis
from async_lru import alru_cache
import zlib
import gzip

logger = logging.getLogger(__name__)

class MessagePriority(str, Enum):
    """Message priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"
    URGENT = "urgent"

class DeliveryStatus(str, Enum):
    """Message delivery status"""
    QUEUED = "queued"
    PROCESSING = "processing"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

class CircuitState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, blocking requests
    HALF_OPEN = "half_open"  # Testing if service is recovered

@dataclass
class CachedMessage:
    """Cached message with metadata"""
    message_id: str
    message_data: dict
    message_type: str
    priority: MessagePriority
    created_at: float
    expires_at: Optional[float]
    delivery_count: int = 0
    max_delivery_attempts: int = 3
    target_connections: Set[str] = field(default_factory=set)
    target_users: Set[str] = field(default_factory=set)
    target_channels: Set[str] = field(default_factory=set)
    last_sent_at: Optional[float] = None
    retry_count: int = 0
    next_retry_at: Optional[float] = None
    compression_enabled: bool = False
    cache_hit_count: int = 0

    def is_expired(self) -> bool:
        """Check if message has expired"""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def should_retry(self) -> bool:
        """Check if message should be retried"""
        if self.retry_count >= self.max_delivery_attempts:
            return False
        if self.next_retry_at and time.time() < self.next_retry_at:
            return False
        return True

    def calculate_retry_delay(self) -> float:
        """Calculate exponential backoff retry delay"""
        base_delay = 1.0  # 1 second
        max_delay = 300.0  # 5 minutes
        delay = min(base_delay * (2 ** self.retry_count), max_delay)
        return delay

@dataclass
class CircuitBreaker:
    """Circuit breaker for external service resilience"""
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    half_open_max_calls: int = 3

    failure_count: int = 0
    last_failure_time: float = 0
    half_open_calls: int = 0
    state: CircuitState = CircuitState.CLOSED

    def can_execute(self) -> bool:
        """Check if operation can be executed"""
        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
                return True
            return False
        else:  # HALF_OPEN
            return self.half_open_calls < self.half_open_max_calls

    def record_success(self):
        """Record successful operation"""
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_calls += 1
            if self.half_open_calls >= self.half_open_max_calls:
                self.reset()
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0

    def record_failure(self):
        """Record failed operation"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
        elif (self.state == CircuitState.CLOSED and
              self.failure_count >= self.failure_threshold):
            self.state = CircuitState.OPEN

    def reset(self):
        """Reset circuit breaker to closed state"""
        self.failure_count = 0
        self.last_failure_time = 0
        self.half_open_calls = 0
        self.state = CircuitState.CLOSED

class WebSocketCache:
    """High-performance caching layer for WebSocket messages"""

    def __init__(self, redis_client: aioredis.Redis):
        self.redis_client = redis_client

        # In-memory cache for hot data
        self.memory_cache: Dict[str, CachedMessage] = {}
        self.memory_cache_size = 10000
        self.cache_hits = 0
        self.cache_misses = 0

        # Message queues for different priorities
        self.priority_queues: Dict[MessagePriority, deque] = {
            priority: deque() for priority in MessagePriority
        }

        # Circuit breakers for external services
        self.circuit_breakers: Dict[str, CircuitBreaker] = {
            'database': CircuitBreaker(failure_threshold=5, recovery_timeout=30.0),
            'search_service': CircuitBreaker(failure_threshold=3, recovery_timeout=60.0),
            'notification_service': CircuitBreaker(failure_threshold=5, recovery_timeout=45.0)
        }

        # Performance metrics
        self.metrics = {
            'messages_cached': 0,
            'messages_sent': 0,
            'messages_failed': 0,
            'cache_hit_rate': 0.0,
            'average_delivery_time': 0.0,
            'compression_ratio': 0.0
        }

        # Background tasks
        self._background_tasks: Set[asyncio.Task] = set()
        self._running = False

    async def start(self):
        """Start cache background tasks"""
        if self._running:
            return

        self._running = True

        # Start message processing task
        task = asyncio.create_task(self._process_message_queues())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        # Start cache cleanup task
        task = asyncio.create_task(self._cleanup_expired_messages())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        # Start metrics collection task
        task = asyncio.create_task(self._collect_metrics())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        logger.info("WebSocket cache started")

    async def stop(self):
        """Stop cache background tasks"""
        self._running = False
        for task in self._background_tasks:
            task.cancel()
        await asyncio.gather(*self._background_tasks, return_exceptions=True)
        logger.info("WebSocket cache stopped")

    async def cache_message(
        self,
        message_id: str,
        message_data: dict,
        message_type: str,
        priority: MessagePriority = MessagePriority.NORMAL,
        expires_in_seconds: Optional[int] = None,
        target_connections: Optional[Set[str]] = None,
        target_users: Optional[Set[str]] = None,
        target_channels: Optional[Set[str]] = None,
        compress: bool = True
    ) -> bool:
        """Cache message for delivery"""
        try:
            # Generate cache key
            cache_key = f"ws:message:{message_id}"

            # Prepare message metadata
            now = time.time()
            expires_at = now + expires_in_seconds if expires_in_seconds else None

            # Compress message if enabled
            compressed_json = None
            original_size = len(json.dumps(message_data).encode('utf-8'))

            if compress and original_size > 1024:  # Only compress messages > 1KB
                json_str = json.dumps(message_data, separators=(',', ':'))
                compressed_bytes = gzip.compress(json_str.encode('utf-8'), level=6)
                compressed_json = compressed_bytes.hex()
                compression_ratio = len(compressed_bytes) / original_size
            else:
                compressed_json = None

            # Create cached message
            cached_msg = CachedMessage(
                message_id=message_id,
                message_data=message_data,
                message_type=message_type,
                priority=priority,
                created_at=now,
                expires_at=expires_at,
                target_connections=target_connections or set(),
                target_users=target_users or set(),
                target_channels=target_channels or set(),
                compression_enabled=compressed_json is not None
            )

            # Store in Redis (compressed or uncompressed)
            redis_data = {
                'message_data': compressed_json if compressed_json else json.dumps(message_data, separators=(',', ':')),
                'message_type': message_type,
                'priority': priority.value,
                'created_at': str(cached_msg.created_at),
                'expires_at': str(cached_msg.expires_at) if expires_at else None,
                'target_connections': json.dumps(list(target_connections or [])),
                'target_users': json.dumps(list(target_users or [])),
                'target_channels': json.dumps(list(target_channels or [])),
                'compressed': str(compressed_json is not None),
                'delivery_count': '0',
                'retry_count': '0'
            }

            # Store with TTL
            ttl = expires_in_seconds if expires_in_seconds else 3600
            await self.redis_client.hset(cache_key, mapping=redis_data)
            await self.redis_client.expire(cache_key, ttl)

            # Add to priority queue
            self.priority_queues[priority].append(cached_msg)

            # Add to memory cache if space available
            if len(self.memory_cache) < self.memory_cache_size:
                self.memory_cache[cache_key] = cached_msg

            # Update metrics
            self.metrics['messages_cached'] += 1
            if compressed_json:
                self.metrics['compression_ratio'] = (
                    self.metrics['compression_ratio'] + compression_ratio
                ) / 2

            logger.debug(f"Message cached: {message_id} (priority: {priority.value})")
            return True

        except Exception as e:
            logger.error(f"Failed to cache message {message_id}: {e}")
            return False

    async def get_cached_message(self, message_id: str) -> Optional[CachedMessage]:
        """Retrieve cached message"""
        try:
            cache_key = f"ws:message:{message_id}"

            # Check memory cache first
            if cache_key in self.memory_cache:
                cached_msg = self.memory_cache[cache_key]
                if not cached_msg.is_expired():
                    cached_msg.cache_hit_count += 1
                    self.cache_hits += 1
                    return cached_msg
                else:
                    del self.memory_cache[cache_key]

            # Check Redis cache
            redis_data = await self.redis_client.hgetall(cache_key)
            if not redis_data:
                self.cache_misses += 1
                return None

            # Parse cached data
            message_data = None
            if redis_data.get(b'compressed', b'false').decode() == 'true':
                # Decompress message
                compressed_hex = redis_data.get(b'message_data').decode()
                compressed_bytes = bytes.fromhex(compressed_hex)
                decompressed_bytes = gzip.decompress(compressed_bytes)
                message_data = json.loads(decompressed_bytes.decode('utf-8'))
            else:
                # Parse JSON message
                message_data = json.loads(redis_data.get(b'message_data').decode())

            # Reconstruct cached message
            cached_msg = CachedMessage(
                message_id=message_id,
                message_data=message_data,
                message_type=redis_data.get(b'message_type').decode(),
                priority=MessagePriority(redis_data.get(b'priority').decode()),
                created_at=float(redis_data.get(b'created_at').decode()),
                expires_at=(
                    float(redis_data.get(b'expires_at').decode())
                    if redis_data.get(b'expires_at')
                    else None
                ),
                target_connections=set(
                    json.loads(redis_data.get(b'target_connections', b'[]').decode())
                ),
                target_users=set(
                    json.loads(redis_data.get(b'target_users', b'[]').decode())
                ),
                target_channels=set(
                    json.loads(redis_data.get(b'target_channels', b'[]').decode())
                ),
                delivery_count=int(redis_data.get(b'delivery_count', b'0').decode()),
                retry_count=int(redis_data.get(b'retry_count', b'0').decode()),
                compression_enabled=redis_data.get(b'compressed', b'false').decode() == 'true'
            )

            # Add to memory cache
            if len(self.memory_cache) < self.memory_cache_size:
                self.memory_cache[cache_key] = cached_msg

            self.cache_hits += 1
            return cached_msg

        except Exception as e:
            logger.error(f"Failed to retrieve cached message {message_id}: {e}")
            self.cache_misses += 1
            return None

    @alru_cache(maxsize=1000)
    async def get_connection_subscriptions(
        self,
        connection_id: str
    ) -> Dict[str, Set[str]]:
        """Get connection subscriptions with caching"""
        try:
            cache_key = f"ws:subscriptions:{connection_id}"
            subscription_data = await self.redis_client.hgetall(cache_key)

            if not subscription_data:
                return {}

            subscriptions = {}
            for key_bytes, value_bytes in subscription_data.items():
                key = key_bytes.decode()
                if ':' in key:
                    category, resource = key.split(':', 1)
                    if category not in subscriptions:
                        subscriptions[category] = set()
                    subscriptions[category].add(resource)

            return subscriptions

        except Exception as e:
            logger.error(f"Failed to get connection subscriptions {connection_id}: {e}")
            return {}

    async def invalidate_message_cache(self, message_id: str):
        """Invalidate cached message"""
        try:
            cache_key = f"ws:message:{message_id}"
            await self.redis_client.delete(cache_key)
            if cache_key in self.memory_cache:
                del self.memory_cache[cache_key]

        except Exception as e:
            logger.error(f"Failed to invalidate message cache {message_id}: {e}")

    async def _process_message_queues(self):
        """Process message queues by priority"""
        while self._running:
            try:
                # Process messages in priority order
                priorities = [
                    MessagePriority.URGENT,
                    MessagePriority.CRITICAL,
                    MessagePriority.HIGH,
                    MessagePriority.NORMAL,
                    MessagePriority.LOW
                ]

                messages_processed = 0
                for priority in priorities:
                    queue = self.priority_queues[priority]
                    processed_count = await self._process_priority_queue(queue, priority)
                    messages_processed += processed_count

                if messages_processed == 0:
                    await asyncio.sleep(0.1)  # Brief pause if no messages

            except Exception as e:
                logger.error(f"Error processing message queues: {e}")
                await asyncio.sleep(1)

    async def _process_priority_queue(
        self,
        queue: deque,
        priority: MessagePriority
    ) -> int:
        """Process messages in a priority queue"""
        processed = 0
        max_batch_size = 50  # Process max 50 messages per batch

        while queue and processed < max_batch_size:
            try:
                # Get next message
                cached_msg = queue.popleft()

                # Check if message is expired
                if cached_msg.is_expired():
                    await self.invalidate_message_cache(cached_msg.message_id)
                    continue

                # Check if message needs retry
                if not cached_msg.should_retry():
                    if cached_msg.delivery_count == 0:
                        # Mark as failed
                        await self._mark_message_failed(cached_msg)
                    continue

                # Calculate next retry time
                if cached_msg.retry_count > 0 and cached_msg.next_retry_at is None:
                    cached_msg.next_retry_at = time.time() + cached_msg.calculate_retry_delay()

                if cached_msg.next_retry_at and time.time() < cached_msg.next_retry_at:
                    # Put message back in queue
                    queue.append(cached_msg)
                    break

                # Attempt delivery (this would be implemented in the connection manager)
                # For now, just update metrics
                processed += 1

            except Exception as e:
                logger.error(f"Error processing message in queue: {e}")
                break

        return processed

    async def _cleanup_expired_messages(self):
        """Clean up expired messages from cache"""
        while self._running:
            try:
                expired_keys = []
                for cache_key, cached_msg in self.memory_cache.items():
                    if cached_msg.is_expired():
                        expired_keys.append(cache_key)

                # Remove from memory cache
                for key in expired_keys:
                    del self.memory_cache[key]

                # Clean up Redis (scan for expired messages)
                async for key in self.redis_client.scan_iter(match="ws:message:*", count=100):
                    try:
                        expires_at = await self.redis_client.hget(key, 'expires_at')
                        if expires_at:
                            expiry_time = float(expires_at.decode())
                            if time.time() > expiry_time:
                                await self.redis_client.delete(key)
                    except Exception as e:
                        logger.debug(f"Error checking message expiry for {key}: {e}")

                await asyncio.sleep(300)  # Cleanup every 5 minutes

            except Exception as e:
                logger.error(f"Error in cache cleanup: {e}")
                await asyncio.sleep(60)

    async def _collect_metrics(self):
        """Collect performance metrics"""
        while self._running:
            try:
                # Calculate cache hit rate
                total_requests = self.cache_hits + self.cache_misses
                if total_requests > 0:
                    self.metrics['cache_hit_rate'] = self.cache_hits / total_requests

                # Log metrics
                logger.debug(
                    f"WebSocket cache metrics: "
                    f"hit_rate={self.metrics['cache_hit_rate']:.2%}, "
                    f"messages_cached={self.metrics['messages_cached']}, "
                    f"memory_cache_size={len(self.memory_cache)}"
                )

                await asyncio.sleep(60)  # Collect metrics every minute

            except Exception as e:
                logger.error(f"Error collecting metrics: {e}")
                await asyncio.sleep(60)

    async def _mark_message_failed(self, cached_msg: CachedMessage):
        """Mark message as failed"""
        try:
            cache_key = f"ws:message:{cached_msg.message_id}"
            await self.redis_client.hset(cache_key, 'delivery_status', 'failed')
            await self.redis_client.expire(cache_key, 3600)  # Keep failed messages for 1 hour

        except Exception as e:
            logger.error(f"Failed to mark message as failed: {e}")

    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        total_requests = self.cache_hits + self.cache_misses
        cache_hit_rate = self.cache_hits / total_requests if total_requests > 0 else 0

        return {
            'cache_hit_rate': cache_hit_rate,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'memory_cache_size': len(self.memory_cache),
            'messages_cached': self.metrics['messages_cached'],
            'compression_ratio': self.metrics['compression_ratio'],
            'queue_lengths': {
                priority.value: len(queue)
                for priority, queue in self.priority_queues.items()
            },
            'circuit_breaker_states': {
                name: breaker.state.value
                for name, breaker in self.circuit_breakers.items()
            }
        }

class ResilientMessageDelivery:
    """Resilient message delivery with retry logic and circuit breakers"""

    def __init__(self, cache: WebSocketCache):
        self.cache = cache
        self.delivery_handlers: Dict[str, Callable] = {}
        self.retry_queue = asyncio.Queue()

    async def send_message(
        self,
        connection_id: str,
        message: dict,
        message_type: str,
        priority: MessagePriority = MessagePriority.NORMAL,
        max_retries: int = 3,
        timeout_seconds: int = 30
    ) -> bool:
        """Send message with resilience patterns"""
        try:
            # Check circuit breaker for WebSocket delivery
            if not self.cache.circuit_breakers['websocket'].can_execute():
                logger.warning(f"Circuit breaker open for WebSocket delivery")
                return False

            message_id = self._generate_message_id(message)

            # Cache message first
            success = await self.cache.cache_message(
                message_id=message_id,
                message_data=message,
                message_type=message_type,
                priority=priority,
                expires_in_seconds=timeout_seconds,
                target_connections={connection_id},
                compress=True
            )

            if not success:
                return False

            # Attempt immediate delivery
            delivery_success = await self._attempt_delivery(
                connection_id, message_id, message, timeout_seconds
            )

            if delivery_success:
                self.cache.circuit_breakers['websocket'].record_success()
                return True
            else:
                self.cache.circuit_breakers['websocket'].record_failure()
                # Message will be retried from cache
                return False

        except Exception as e:
            logger.error(f"Failed to send message to {connection_id}: {e}")
            self.cache.circuit_breakers['websocket'].record_failure()
            return False

    async def _attempt_delivery(
        self,
        connection_id: str,
        message_id: str,
        message: dict,
        timeout_seconds: int
    ) -> bool:
        """Attempt message delivery with timeout"""
        try:
            # Get delivery handler (would be injected by connection manager)
            handler = self.delivery_handlers.get('websocket_send')
            if not handler:
                return False

            # Send with timeout
            return await asyncio.wait_for(
                handler(connection_id, message),
                timeout=timeout_seconds
            )

        except asyncio.TimeoutError:
            logger.warning(f"Message delivery timeout for {connection_id}")
            return False
        except Exception as e:
            logger.error(f"Message delivery error: {e}")
            return False

    def _generate_message_id(self, message: dict) -> str:
        """Generate unique message ID"""
        content = json.dumps(message, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def register_delivery_handler(self, handler_type: str, handler: Callable):
        """Register message delivery handler"""
        self.delivery_handlers[handler_type] = handler