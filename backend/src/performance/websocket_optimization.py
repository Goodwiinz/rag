"""
High-performance WebSocket message batching and throttling system
Optimized for real-time status streaming with sub-100ms latency
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone as dt_timezone, timedelta
from typing import Dict, List, Optional, Any, Set, Callable, Union
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
import logging
import gzip
import numpy as np
from concurrent.futures import ThreadPoolExecutor

from ..models.websocket_status import Priority, MessageType
from .optimization import SmartCache, CacheConfig

logger = logging.getLogger(__name__)

class BatchingStrategy(Enum):
    """Message batching strategies"""
    TIME_BASED = "time_based"          # Batch by time interval
    SIZE_BASED = "size_based"          # Batch by message count
    ADAPTIVE = "adaptive"              # Adaptive batching based on load
    PRIORITY_QUEUE = "priority_queue"  # Priority-based batching

@dataclass
class BatchConfig:
    """Configuration for message batching"""
    max_batch_size: int = 100          # Maximum messages per batch
    max_batch_time_ms: int = 50        # Maximum batch time in milliseconds
    compression_threshold: int = 1024  # Compress batches larger than this
    enable_compression: bool = True
    strategy: BatchingStrategy = BatchingStrategy.ADAPTIVE
    priority_levels: Dict[Priority, int] = field(default_factory=lambda: {
        Priority.HIGH: 5,      # Process every 5ms
        Priority.NORMAL: 50,   # Process every 50ms
        Priority.LOW: 200      # Process every 200ms
    })

@dataclass
class MessageBatch:
    """Batch of WebSocket messages"""
    messages: List[Dict[str, Any]]
    target_connections: Set[str]
    created_at: datetime
    priority: Priority
    batch_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self):
        if not self.messages:
            raise ValueError("Batch cannot be empty")

    def add_message(self, message: Dict[str, Any], connection_id: str):
        """Add message to batch"""
        self.messages.append(message)
        self.target_connections.add(connection_id)

    def get_size(self) -> int:
        """Get current batch size"""
        return len(self.messages)

    def should_flush(self, config: BatchConfig, age_ms: int) -> bool:
        """Check if batch should be flushed"""
        if self.get_size() >= config.max_batch_size:
            return True

        if age_ms >= config.priority_levels.get(self.priority, config.max_batch_time_ms):
            return True

        return False

class AdaptiveBatcher:
    """Adaptive message batching that adjusts to system load"""

    def __init__(self, config: BatchConfig):
        self.config = config
        self.batches: Dict[Priority, MessageBatch] = {}
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.performance_metrics = {
            'avg_batch_size': defaultdict(list),
            'processing_times': defaultdict(list),
            'compression_ratios': [],
            'last_adjustment': datetime.utcnow()
        }

        # Adaptive parameters
        self.current_batch_sizes = {p: config.max_batch_size for p in Priority}
        self.current_batch_times = {p: config.max_batch_time_ms for p in Priority}
        self.load_factor = 1.0

    def create_batch(self, priority: Priority) -> MessageBatch:
        """Create a new batch for the given priority"""
        return MessageBatch(
            messages=[],
            target_connections=set(),
            created_at=datetime.utcnow(),
            priority=priority
        )

    def get_or_create_batch(self, priority: Priority) -> MessageBatch:
        """Get existing batch or create new one"""
        if priority not in self.batches or not self.batches[priority]:
            self.batches[priority] = self.create_batch(priority)
        return self.batches[priority]

    async def add_message(self, message_data: Dict[str, Any],
                         connection_id: str, priority: Priority) -> bool:
        """Add message to appropriate batch"""
        try:
            batch = self.get_or_create_batch(priority)
            batch.add_message(message_data, connection_id)
            return True
        except Exception as e:
            logger.error(f"Failed to add message to batch: {e}")
            return False

    async def process_batches(self) -> List[MessageBatch]:
        """Process and return batches ready for sending"""
        ready_batches = []
        current_time = datetime.utcnow()

        for priority in Priority:
            if priority not in self.batches:
                continue

            batch = self.batches[priority]
            if not batch.messages:
                continue

            # Calculate batch age in milliseconds
            age_ms = int((current_time - batch.created_at).total_seconds() * 1000)

            # Check if batch should be flushed
            if batch.should_flush(self.config, age_ms):
                ready_batches.append(batch)
                self.batches[priority] = self.create_batch(priority)

                # Record metrics
                self.performance_metrics['avg_batch_size'][priority.name].append(batch.get_size())
                self.performance_metrics['processing_times'][priority.name].append(age_ms)

        # Adapt batching parameters based on performance
        await self._adapt_parameters()

        return ready_batches

    async def _adapt_parameters(self):
        """Adapt batching parameters based on system load and performance"""
        now = datetime.utcnow()
        if (now - self.performance_metrics['last_adjustment']).seconds < 30:
            return

        for priority in Priority:
            metric_key = priority.name
            if metric_key not in self.performance_metrics['avg_batch_size']:
                continue

            batch_sizes = self.performance_metrics['avg_batch_size'][metric_key]
            processing_times = self.performance_metrics['processing_times'][metric_key]

            if len(batch_sizes) < 10:  # Need sufficient data
                continue

            # Calculate performance metrics
            avg_batch_size = np.mean(batch_sizes[-10:])  # Last 10 batches
            avg_processing_time = np.mean(processing_times[-10:])

            # Adaptive logic
            if avg_processing_time > 100:  # Processing is slow
                # Reduce batch size for faster processing
                new_size = max(10, int(avg_batch_size * 0.8))
                new_time = max(10, self.current_batch_times[priority] * 0.8)
            elif avg_processing_time < 20:  # Processing is fast
                # Increase batch size for better efficiency
                new_size = min(self.config.max_batch_size, int(avg_batch_size * 1.2))
                new_time = min(200, self.current_batch_times[priority] * 1.2)
            else:
                continue  # No adjustment needed

            self.current_batch_sizes[priority] = new_size
            self.current_batch_times[priority] = new_time

            # Clear old metrics
            self.performance_metrics['avg_batch_size'][metric_key] = batch_sizes[-5:]
            self.performance_metrics['processing_times'][metric_key] = processing_times[-5:]

        self.performance_metrics['last_adjustment'] = now

class WebSocketThrottler:
    """Advanced connection throttling with intelligent rate limiting"""

    def __init__(self, cache: SmartCache):
        self.cache = cache
        self.connection_limits: Dict[str, Dict] = {}
        self.global_rate_limit = 1000  # messages per second
        self.connection_rate_limit = 100  # messages per second per connection

        # Throttling windows
        self.window_size = 60  # seconds
        self.burst_allowance = 10

    async def check_connection_limit(self, connection_id: str,
                                    user_id: str, organization_id: str) -> bool:
        """Check if connection can send message"""
        try:
            current_time = int(time.time())
            window_start = current_time - self.window_size

            # Check global rate limit
            global_key = f"ws:global:rate:{current_time // 1}"
            global_count = await self.cache.get([global_key])
            if global_count and global_count >= self.global_rate_limit:
                return False

            # Check connection-specific limit
            conn_key = f"ws:conn:{connection_id}:rate:{current_time // 1}"
            conn_count = await self.cache.get([conn_key])
            if conn_count and conn_count >= self.connection_rate_limit:
                return False

            # Check user limit
            user_key = f"ws:user:{user_id}:rate:{current_time // 10}"
            user_count = await self.cache.get([user_key])
            if user_count and user_count >= 500:  # 500 messages per 10 seconds per user
                return False

            # Check organization limit
            org_key = f"ws:org:{organization_id}:rate:{current_time // 10}"
            org_count = await self.cache.get([org_key])
            if org_count and org_count >= 2000:  # 2000 messages per 10 seconds per org
                return False

            # Update counters
            await self._increment_counter(global_key, 1, ttl=1)
            await self._increment_counter(conn_key, 1, ttl=1)
            await self._increment_counter(user_key, 1, ttl=10)
            await self._increment_counter(org_key, 1, ttl=10)

            return True

        except Exception as e:
            logger.error(f"Error checking connection limit: {e}")
            return True  # Allow on error

    async def _increment_counter(self, key: str, increment: int, ttl: int):
        """Increment rate limit counter"""
        try:
            current = await self.cache.get([key]) or 0
            await self.cache.set([key], current + increment, ttl=ttl)
        except Exception as e:
            logger.error(f"Error incrementing counter: {e}")

class MessageCompressor:
    """Intelligent message compression with adaptive algorithms"""

    def __init__(self):
        self.compression_stats = {
            'total_compressed': 0,
            'total_bytes_saved': 0,
            'compression_times': [],
            'compression_ratios': []
        }

    async def compress_batch(self, batch: MessageBatch,
                           threshold: int = 1024) -> tuple[bytes, bool]:
        """Compress message batch if beneficial"""
        try:
            # Serialize batch
            serialized = json.dumps({
                'batch_id': batch.batch_id,
                'messages': batch.messages,
                'target_connections': list(batch.target_connections),
                'priority': batch.priority.value,
                'created_at': batch.created_at.isoformat()
            }).encode('utf-8')

            # Check if compression is worthwhile
            if len(serialized) < threshold:
                return serialized, False

            # Compress with gzip
            start_time = time.time()
            compressed = gzip.compress(serialized, compresslevel=6)
            compression_time = time.time() - start_time

            # Calculate compression ratio
            ratio = len(compressed) / len(serialized)

            # Only use compression if it's beneficial (saves > 20%)
            if ratio < 0.8:
                # Update stats
                self.compression_stats['total_compressed'] += 1
                self.compression_stats['total_bytes_saved'] += len(serialized) - len(compressed)
                self.compression_stats['compression_times'].append(compression_time)
                self.compression_stats['compression_ratios'].append(ratio)

                return compressed, True
            else:
                return serialized, False

        except Exception as e:
            logger.error(f"Error compressing batch: {e}")
            # Fallback to uncompressed
            return json.dumps({
                'batch_id': batch.batch_id,
                'messages': batch.messages,
                'target_connections': list(batch.target_connections),
                'priority': batch.priority.value,
                'created_at': batch.created_at.isoformat()
            }).encode('utf-8'), False

    async def decompress_batch(self, data: bytes, compressed: bool) -> Dict[str, Any]:
        """Decompress message batch"""
        try:
            if compressed:
                decompressed = gzip.decompress(data)
            else:
                decompressed = data

            return json.loads(decompressed.decode('utf-8'))

        except Exception as e:
            logger.error(f"Error decompressing batch: {e}")
            raise

class HighPerformanceWebSocketManager:
    """High-performance WebSocket manager with advanced optimization"""

    def __init__(self, redis_client=None):
        self.redis_client = redis_client

        # Initialize components
        batch_config = BatchConfig(
            max_batch_size=100,
            max_batch_time_ms=50,
            enable_compression=True,
            strategy=BatchingStrategy.ADAPTIVE
        )

        self.batcher = AdaptiveBatcher(batch_config)
        self.throttler = WebSocketThrottler(
            SmartCache(redis_client, CacheConfig(ttl=60))
        )
        self.compressor = MessageCompressor()

        # Performance metrics
        self.metrics = {
            'messages_processed': 0,
            'batches_sent': 0,
            'avg_latency_ms': 0,
            'compression_savings_mb': 0,
            'connection_count': 0,
            'start_time': datetime.utcnow()
        }

        # Background tasks
        self.batch_processor_task = None
        self.metrics_collector_task = None

    async def start(self):
        """Start the high-performance WebSocket manager"""
        self.batch_processor_task = asyncio.create_task(self._batch_processor_loop())
        self.metrics_collector_task = asyncio.create_task(self._metrics_collector_loop())
        logger.info("High-performance WebSocket manager started")

    async def stop(self):
        """Stop the WebSocket manager"""
        if self.batch_processor_task:
            self.batch_processor_task.cancel()
        if self.metrics_collector_task:
            self.metrics_collector_task.cancel()
        logger.info("High-performance WebSocket manager stopped")

    async def send_message(self, message_data: Dict[str, Any],
                          connection_id: str, user_id: str,
                          organization_id: str, priority: Priority = Priority.NORMAL) -> bool:
        """Send message with batching and throttling"""
        try:
            # Check throttling limits
            if not await self.throttler.check_connection_limit(
                connection_id, user_id, organization_id
            ):
                logger.warning(f"Message throttled for connection {connection_id}")
                return False

            # Add message to batcher
            success = await self.batcher.add_message(
                message_data, connection_id, priority
            )

            if success:
                self.metrics['messages_processed'] += 1

            return success

        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False

    async def _batch_processor_loop(self):
        """Background task to process message batches"""
        while True:
            try:
                # Get ready batches
                ready_batches = await self.batcher.process_batches()

                # Process each batch
                for batch in ready_batches:
                    await self._process_batch(batch)

                # Small sleep to prevent CPU spinning
                await asyncio.sleep(0.001)  # 1ms

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in batch processor: {e}")
                await asyncio.sleep(0.01)  # 10ms on error

    async def _process_batch(self, batch: MessageBatch):
        """Process and send a message batch"""
        try:
            start_time = time.time()

            # Compress batch if beneficial
            compressed_data, is_compressed = await self.compressor.compress_batch(batch)

            # Send to all target connections
            successful_sends = 0
            total_sends = len(batch.target_connections)

            # This would be integrated with the actual WebSocket connection manager
            # For now, we'll simulate the sending process
            for connection_id in batch.target_connections:
                try:
                    # Simulate WebSocket send
                    send_time = time.time()

                    # In real implementation, this would send via WebSocket
                    # await self._send_to_connection(connection_id, compressed_data, is_compressed)

                    send_latency = (time.time() - send_time) * 1000
                    successful_sends += 1

                except Exception as e:
                    logger.error(f"Failed to send batch to {connection_id}: {e}")

            # Update metrics
            processing_time = (time.time() - start_time) * 1000
            self.metrics['batches_sent'] += 1

            # Update average latency (exponential moving average)
            alpha = 0.1  # Smoothing factor
            self.metrics['avg_latency_ms'] = (
                alpha * processing_time +
                (1 - alpha) * self.metrics['avg_latency_ms']
            )

            # Update compression savings
            if is_compressed:
                original_size = len(json.dumps(batch.messages).encode('utf-8'))
                compressed_size = len(compressed_data)
                savings_mb = (original_size - compressed_size) / (1024 * 1024)
                self.metrics['compression_savings_mb'] += savings_mb

            logger.debug(
                f"Processed batch {batch.batch_id}: {successful_sends}/{total_sends} "
                f"connections, {processing_time:.2f}ms, compressed={is_compressed}"
            )

        except Exception as e:
            logger.error(f"Error processing batch {batch.batch_id}: {e}")

    async def _metrics_collector_loop(self):
        """Background task to collect and report metrics"""
        while True:
            try:
                await asyncio.sleep(60)  # Collect metrics every minute

                # Calculate performance metrics
                uptime = (datetime.utcnow() - self.metrics['start_time']).total_seconds()
                messages_per_second = self.metrics['messages_processed'] / uptime if uptime > 0 else 0

                performance_report = {
                    'uptime_seconds': uptime,
                    'messages_processed': self.metrics['messages_processed'],
                    'batches_sent': self.metrics['batches_sent'],
                    'messages_per_second': messages_per_second,
                    'avg_latency_ms': self.metrics['avg_latency_ms'],
                    'compression_savings_mb': self.metrics['compression_savings_mb'],
                    'compression_stats': self.compressor.compression_stats,
                    'batcher_performance': self.batcher.performance_metrics
                }

                logger.info(f"WebSocket Performance: {performance_report}")

                # Cache metrics for monitoring dashboard
                if self.redis_client:
                    await self.redis_client.setex(
                        f"ws:performance_metrics:{int(time.time())}",
                        300,  # 5 minutes TTL
                        json.dumps(performance_report)
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in metrics collector: {e}")
                await asyncio.sleep(60)

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        uptime = (datetime.utcnow() - self.metrics['start_time']).total_seconds()
        messages_per_second = self.metrics['messages_processed'] / uptime if uptime > 0 else 0

        return {
            'uptime_seconds': uptime,
            'messages_processed': self.metrics['messages_processed'],
            'batches_sent': self.metrics['batches_sent'],
            'messages_per_second': messages_per_second,
            'avg_latency_ms': self.metrics['avg_latency_ms'],
            'compression_savings_mb': self.metrics['compression_savings_mb'],
            'compression_ratio': (
                self.compressor.compression_stats['total_bytes_saved'] /
                max(1, sum(self.compressor.compression_stats['compression_ratios']))
            ),
            'batch_efficiency': (
                self.metrics['messages_processed'] / max(1, self.metrics['batches_sent'])
            )
        }

# Global high-performance WebSocket manager
_high_perf_manager = None

def get_high_performance_websocket_manager(redis_client=None) -> HighPerformanceWebSocketManager:
    """Get or create the global high-performance WebSocket manager"""
    global _high_perf_manager
    if _high_perf_manager is None:
        _high_perf_manager = HighPerformanceWebSocketManager(redis_client)
    return _high_perf_manager