"""
Redis integration patterns for high-performance WebSocket services
Includes pub/sub, caching, session management, and distributed coordination
"""

import asyncio
import json
import logging
import time
import zlib
from typing import Dict, List, Optional, Any, Callable, Union, Set
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
import redis.asyncio as redis
from redis.asyncio import ConnectionPool
import uuid

logger = logging.getLogger(__name__)

class CacheStrategy(Enum):
    LRU = "lru"
    LFU = "lfu"
    TTL_BASED = "ttl_based"
    WRITE_THROUGH = "write_through"
    WRITE_BEHIND = "write_behind"

class SerializationMethod(Enum):
    JSON = "json"
    COMPRESSED_JSON = "compressed_json"

@dataclass
class RedisConfig:
    """Redis configuration for WebSocket services"""
    url: str = "redis://localhost:6379"
    max_connections: int = 100
    retry_on_timeout: bool = True
    socket_timeout: int = 5
    socket_connect_timeout: int = 5
    health_check_interval: int = 30
    decode_responses: bool = True

@dataclass
class CacheConfig:
    """Cache configuration"""
    default_ttl: int = 3600  # 1 hour
    max_size: int = 10000
    cleanup_interval: int = 300  # 5 minutes
    compression_threshold: int = 1024  # Compress if > 1KB
    serialization_method: SerializationMethod = SerializationMethod.JSON

@dataclass
class PubSubConfig:
    """Pub/Sub configuration"""
    max_subscribers: int = 1000
    message_queue_size: int = 10000
    retry_attempts: int = 3
    retry_delay: float = 1.0
    dead_letter_queue: str = "ws:dlq"

class WebSocketRedisManager:
    """
    High-performance Redis integration for WebSocket services
    """

    def __init__(
        self,
        redis_config: RedisConfig = None,
        cache_config: CacheConfig = None,
        pubsub_config: PubSubConfig = None
    ):
        self.redis_config = redis_config or RedisConfig()
        self.cache_config = cache_config or CacheConfig()
        self.pubsub_config = pubsub_config or PubSubConfig()

        # Redis clients
        self._redis_client: Optional[redis.Redis] = None
        self._redis_pool: Optional[ConnectionPool] = None
        self._pubsub: Optional[redis.PubSub] = None

        # Local caches
        self._local_cache: Dict[str, Any] = {}
        self._cache_access_times: Dict[str, float] = {}
        self._cache_sizes: Dict[str, int] = {}

        # Pub/Sub subscribers
        self._subscribers: Dict[str, Set[Callable]] = {}
        self._subscriber_tasks: Dict[str, asyncio.Task] = {}

        # Performance metrics
        self._metrics = {
            'cache_hits': 0,
            'cache_misses': 0,
            'cache_sets': 0,
            'cache_deletes': 0,
            'pubsub_messages_sent': 0,
            'pubsub_messages_received': 0,
            'redis_commands': 0,
            'redis_errors': 0,
            'serialization_time': 0,
            'compression_time': 0
        }

        # Background tasks
        self._cleanup_task: Optional[asyncio.Task] = None
        self._health_check_task: Optional[asyncio.Task] = None

    async def initialize(self):
        """Initialize Redis connections and background tasks"""
        try:
            # Create connection pool
            self._redis_pool = ConnectionPool.from_url(
                self.redis_config.url,
                max_connections=self.redis_config.max_connections,
                retry_on_timeout=self.redis_config.retry_on_timeout,
                socket_timeout=self.redis_config.socket_timeout,
                socket_connect_timeout=self.redis_config.socket_connect_timeout,
                decode_responses=self.redis_config.decode_responses
            )

            # Create Redis client
            self._redis_client = redis.Redis(connection_pool=self._redis_pool)

            # Test connection
            await self._redis_client.ping()

            # Initialize pub/sub
            self._pubsub = self._redis_client.pubsub()

            # Start background tasks
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            self._health_check_task = asyncio.create_task(self._health_check_loop())

            logger.info("WebSocket Redis manager initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize WebSocket Redis manager: {e}")
            raise

    async def shutdown(self):
        """Graceful shutdown"""
        # Cancel background tasks
        for task in [self._cleanup_task, self._health_check_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Cancel subscriber tasks
        for task in self._subscriber_tasks.values():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Close Redis connections
        if self._pubsub:
            await self._pubsub.close()
        if self._redis_client:
            await self._redis_client.close()
        if self._redis_pool:
            await self._redis_pool.disconnect()

        logger.info("WebSocket Redis manager shutdown complete")

    # Cache operations

    async def get(self, key: str, use_local_cache: bool = True) -> Optional[Any]:
        """Get value from cache (local cache first, then Redis)"""
        start_time = time.time()

        try:
            # Try local cache first
            if use_local_cache:
                local_value = self._get_from_local_cache(key)
                if local_value is not None:
                    self._metrics['cache_hits'] += 1
                    return local_value

            # Try Redis
            redis_value = await self._redis_client.get(key)
            if redis_value is not None:
                # Deserialize
                deserialized_value = await self._deserialize(redis_value)

                # Update local cache
                if use_local_cache:
                    self._set_local_cache(key, deserialized_value)

                self._metrics['cache_hits'] += 1
                return deserialized_value

            self._metrics['cache_misses'] += 1
            return None

        except Exception as e:
            self._metrics['redis_errors'] += 1
            logger.error(f"Error getting cache key {key}: {e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        use_local_cache: bool = True,
        serialize_method: Optional[SerializationMethod] = None
    ) -> bool:
        """Set value in cache (Redis and optionally local cache)"""
        start_time = time.time()

        try:
            # Serialize value
            serialization_start = time.time()
            serialized_value = await self._serialize(
                value,
                serialize_method or self.cache_config.serialization_method
            )
            self._metrics['serialization_time'] += time.time() - serialization_start

            # Set in Redis
            ttl = ttl or self.cache_config.default_ttl
            await self._redis_client.setex(key, ttl, serialized_value)

            # Set in local cache
            if use_local_cache:
                self._set_local_cache(key, value, ttl)

            self._metrics['cache_sets'] += 1
            self._metrics['redis_commands'] += 1
            return True

        except Exception as e:
            self._metrics['redis_errors'] += 1
            logger.error(f"Error setting cache key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            await self._redis_client.delete(key)
            self._delete_from_local_cache(key)
            self._metrics['cache_deletes'] += 1
            self._metrics['redis_commands'] += 1
            return True

        except Exception as e:
            self._metrics['redis_errors'] += 1
            logger.error(f"Error deleting cache key {key}: {e}")
            return False

    async def get_multiple(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from cache efficiently"""
        try:
            # Use Redis MGET for efficiency
            values = await self._redis_client.mget(keys)
            result = {}

            for key, value in zip(keys, values):
                if value is not None:
                    try:
                        result[key] = await self._deserialize(value)
                    except Exception as e:
                        logger.error(f"Error deserializing key {key}: {e}")
                        result[key] = None
                else:
                    result[key] = None

            self._metrics['redis_commands'] += 1
            return result

        except Exception as e:
            self._metrics['redis_errors'] += 1
            logger.error(f"Error getting multiple cache keys: {e}")
            return {key: None for key in keys}

    async def set_multiple(
        self,
        items: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """Set multiple values in cache efficiently"""
        try:
            pipe = self._redis_client.pipeline()
            ttl = ttl or self.cache_config.default_ttl

            for key, value in items.items():
                serialized_value = await self._serialize(value)
                pipe.setex(key, ttl, serialized_value)

            await pipe.execute()
            self._metrics['cache_sets'] += len(items)
            self._metrics['redis_commands'] += 1
            return True

        except Exception as e:
            self._metrics['redis_errors'] += 1
            logger.error(f"Error setting multiple cache keys: {e}")
            return False

    # Pub/Sub operations

    async def publish(self, channel: str, message: Dict[str, Any]) -> bool:
        """Publish message to channel"""
        try:
            serialized_message = json.dumps(message, default=str)
            await self._redis_client.publish(channel, serialized_message)
            self._metrics['pubsub_messages_sent'] += 1
            self._metrics['redis_commands'] += 1
            return True

        except Exception as e:
            self._metrics['redis_errors'] += 1
            logger.error(f"Error publishing to channel {channel}: {e}")
            return False

    async def subscribe(self, channel: str, handler: Callable) -> bool:
        """Subscribe to channel with message handler"""
        try:
            if channel not in self._subscribers:
                self._subscribers[channel] = set()

                # Start listener task for new channel
                task = asyncio.create_task(self._channel_listener(channel))
                self._subscriber_tasks[channel] = task

            self._subscribers[channel].add(handler)
            return True

        except Exception as e:
            self._metrics['redis_errors'] += 1
            logger.error(f"Error subscribing to channel {channel}: {e}")
            return False

    async def unsubscribe(self, channel: str, handler: Callable) -> bool:
        """Unsubscribe handler from channel"""
        try:
            if channel in self._subscribers:
                self._subscribers[channel].discard(handler)

                # Clean up if no more subscribers
                if not self._subscribers[channel]:
                    self._subscribers.pop(channel, None)
                    if channel in self._subscriber_tasks:
                        task = self._subscriber_tasks.pop(channel)
                        task.cancel()

            return True

        except Exception as e:
            self._metrics['redis_errors'] += 1
            logger.error(f"Error unsubscribing from channel {channel}: {e}")
            return False

    # Session management

    async def create_session(
        self,
        session_id: str,
        user_id: str,
        organization_id: str,
        data: Dict[str, Any],
        ttl: int = 3600
    ) -> bool:
        """Create WebSocket session in Redis"""
        session_key = f"ws:session:{session_id}"
        session_data = {
            'session_id': session_id,
            'user_id': user_id,
            'organization_id': organization_id,
            'created_at': datetime.utcnow().isoformat(),
            'last_activity': datetime.utcnow().isoformat(),
            'data': json.dumps(data)
        }

        return await self.set(session_key, session_data, ttl, use_local_cache=False)

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get WebSocket session from Redis"""
        session_key = f"ws:session:{session_id}"
        session_data = await self.get(session_key, use_local_cache=False)

        if session_data:
            # Parse JSON data
            if isinstance(session_data.get('data'), str):
                try:
                    session_data['data'] = json.loads(session_data['data'])
                except json.JSONDecodeError:
                    pass

        return session_data

    async def update_session_activity(self, session_id: str) -> bool:
        """Update session last activity timestamp"""
        session_key = f"ws:session:{session_id}"
        try:
            await self._redis_client.hset(
                session_key,
                'last_activity',
                datetime.utcnow().isoformat()
            )
            return True
        except Exception as e:
            logger.error(f"Error updating session activity: {e}")
            return False

    async def delete_session(self, session_id: str) -> bool:
        """Delete WebSocket session"""
        session_key = f"ws:session:{session_id}"
        return await self.delete(session_key)

    # Connection management

    async def add_connection(
        self,
        connection_id: str,
        user_id: str,
        organization_id: str,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """Add WebSocket connection to registry"""
        conn_key = f"ws:connection:{connection_id}"
        conn_data = {
            'connection_id': connection_id,
            'user_id': user_id,
            'organization_id': organization_id,
            'created_at': datetime.utcnow().isoformat(),
            'metadata': json.dumps(metadata or {})
        }

        return await self.set(conn_key, conn_data, ttl=7200, use_local_cache=False)  # 2 hours

    async def remove_connection(self, connection_id: str) -> bool:
        """Remove WebSocket connection from registry"""
        conn_key = f"ws:connection:{connection_id}"
        return await self.delete(conn_key)

    async def get_user_connections(self, user_id: str) -> List[str]:
        """Get all connection IDs for a user"""
        try:
            pattern = "ws:connection:*"
            keys = await self._redis_client.keys(pattern)
            user_connections = []

            for key in keys:
                conn_data = await self.get(key, use_local_cache=False)
                if conn_data and conn_data.get('user_id') == user_id:
                    user_connections.append(conn_data['connection_id'])

            return user_connections

        except Exception as e:
            logger.error(f"Error getting user connections: {e}")
            return []

    async def get_organization_connections(self, organization_id: str) -> List[str]:
        """Get all connection IDs for an organization"""
        try:
            pattern = "ws:connection:*"
            keys = await self._redis_client.keys(pattern)
            org_connections = []

            for key in keys:
                conn_data = await self.get(key, use_local_cache=False)
                if conn_data and conn_data.get('organization_id') == organization_id:
                    org_connections.append(conn_data['connection_id'])

            return org_connections

        except Exception as e:
            logger.error(f"Error getting organization connections: {e}")
            return []

    # Performance monitoring

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        try:
            # Get Redis info
            redis_info = await self._redis_client.info()

            return {
                'redis_metrics': {
                    'connected_clients': redis_info.get('connected_clients', 0),
                    'used_memory': redis_info.get('used_memory', 0),
                    'used_memory_human': redis_info.get('used_memory_human', '0B'),
                    'total_commands_processed': redis_info.get('total_commands_processed', 0),
                    'instantaneous_ops_per_sec': redis_info.get('instantaneous_ops_per_sec', 0),
                    'keyspace_hits': redis_info.get('keyspace_hits', 0),
                    'keyspace_misses': redis_info.get('keyspace_misses', 0),
                },
                'websocket_metrics': self._metrics.copy(),
                'local_cache_metrics': {
                    'local_cache_size': len(self._local_cache),
                    'cache_hit_ratio': self._calculate_hit_ratio(),
                    'local_memory_usage': sum(self._cache_sizes.values())
                },
                'subscription_metrics': {
                    'active_subscriptions': len(self._subscribers),
                    'total_subscribers': sum(len(subs) for subs in self._subscribers.values())
                }
            }

        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return {'error': str(e), 'websocket_metrics': self._metrics}

    # Private methods

    def _get_from_local_cache(self, key: str) -> Optional[Any]:
        """Get value from local cache"""
        if key in self._local_cache:
            self._cache_access_times[key] = time.time()
            return self._local_cache[key]
        return None

    def _set_local_cache(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in local cache with LRU eviction"""
        # Check size limit
        if len(self._local_cache) >= self.cache_config.max_size:
            self._evict_lru()

        # Store value
        self._local_cache[key] = value
        self._cache_access_times[key] = time.time()
        self._cache_sizes[key] = len(str(value))

    def _delete_from_local_cache(self, key: str):
        """Delete value from local cache"""
        self._local_cache.pop(key, None)
        self._cache_access_times.pop(key, None)
        self._cache_sizes.pop(key, None)

    def _evict_lru(self):
        """Evict least recently used item from local cache"""
        if not self._cache_access_times:
            return

        # Find least recently used key
        lru_key = min(self._cache_access_times.items(), key=lambda x: x[1])[0]
        self._delete_from_local_cache(lru_key)

    async def _serialize(self, value: Any, method: SerializationMethod) -> str:
        """Serialize value based on method"""
        if method == SerializationMethod.JSON:
            return json.dumps(value, default=str)

        elif method == SerializationMethod.COMPRESSED_JSON:
            json_str = json.dumps(value, default=str)
            compressed = zlib.compress(json_str.encode('utf-8'))
            return compressed.hex()

        else:
            raise ValueError(f"Unsupported serialization method: {method}")

    async def _deserialize(self, value: str) -> Any:
        """Deserialize value based on content"""
        try:
            # Try JSON first
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            try:
                # Try hex-decoded compressed JSON
                decoded = bytes.fromhex(value)
                decompressed = zlib.decompress(decoded).decode('utf-8')
                return json.loads(decompressed)
            except (ValueError, zlib.error, json.JSONDecodeError):
                # Return as string if all else fails
                return value

    async def _channel_listener(self, channel: str):
        """Listen for messages on a channel"""
        try:
            await self._pubsub.subscribe(channel)

            async for message in self._pubsub.listen():
                if message['type'] == 'message':
                    try:
                        # Parse message
                        data = json.loads(message['data'])
                        self._metrics['pubsub_messages_received'] += 1

                        # Call all handlers for this channel
                        if channel in self._subscribers:
                            for handler in self._subscribers[channel]:
                                try:
                                    await handler(data)
                                except Exception as e:
                                    logger.error(f"Error in pubsub handler for {channel}: {e}")

                    except json.JSONDecodeError as e:
                        logger.error(f"Error parsing pubsub message from {channel}: {e}")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in channel listener for {channel}: {e}")

    async def _cleanup_loop(self):
        """Background cleanup loop"""
        while True:
            try:
                await asyncio.sleep(self.cache_config.cleanup_interval)

                # Clean up expired local cache entries
                await self._cleanup_local_cache()

                # Clean up expired sessions and connections
                await self._cleanup_expired_sessions()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def _cleanup_local_cache(self):
        """Clean up expired entries from local cache"""
        current_time = time.time()
        expired_keys = []

        for key, access_time in self._cache_access_times.items():
            # Remove if not accessed in 1 hour
            if current_time - access_time > 3600:
                expired_keys.append(key)

        for key in expired_keys:
            self._delete_from_local_cache(key)

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired local cache entries")

    async def _cleanup_expired_sessions(self):
        """Clean up expired sessions from Redis"""
        try:
            # Find expired sessions
            pattern = "ws:session:*"
            keys = await self._redis_client.keys(pattern)
            current_time = datetime.utcnow()

            expired_count = 0
            for key in keys:
                session_data = await self.get(key, use_local_cache=False)
                if session_data:
                    try:
                        last_activity = datetime.fromisoformat(session_data.get('last_activity', ''))
                        if (current_time - last_activity).seconds > 7200:  # 2 hours
                            await self.delete(key)
                            expired_count += 1
                    except (ValueError, TypeError):
                        # Invalid timestamp, delete session
                        await self.delete(key)
                        expired_count += 1

            if expired_count > 0:
                logger.info(f"Cleaned up {expired_count} expired sessions")

        except Exception as e:
            logger.error(f"Error cleaning up expired sessions: {e}")

    async def _health_check_loop(self):
        """Health check loop for Redis connection"""
        while True:
            try:
                await asyncio.sleep(self.redis_config.health_check_interval)

                # Ping Redis
                await self._redis_client.ping()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Redis health check failed: {e}")
                # Attempt reconnection
                try:
                    await self._redis_client.ping()
                except Exception:
                    logger.warning("Redis reconnection failed")

    def _calculate_hit_ratio(self) -> float:
        """Calculate cache hit ratio"""
        total_requests = self._metrics['cache_hits'] + self._metrics['cache_misses']
        if total_requests == 0:
            return 0.0
        return (self._metrics['cache_hits'] / total_requests) * 100

# Global Redis manager instance
_websocket_redis_manager: Optional[WebSocketRedisManager] = None

def get_websocket_redis_manager() -> WebSocketRedisManager:
    """Get or create the global WebSocket Redis manager"""
    global _websocket_redis_manager
    if _websocket_redis_manager is None:
        _websocket_redis_manager = WebSocketRedisManager()
    return _websocket_redis_manager