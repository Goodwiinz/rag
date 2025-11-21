"""
Advanced WebSocket connection manager for 10,000+ concurrent connections
Supports Redis-backed state management, connection pooling, and efficient message routing
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Set, Optional, Callable, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
import redis.asyncio as redis
from fastapi import WebSocket, WebSocketDisconnect, status
import uuid
import weakref

logger = logging.getLogger(__name__)

class ConnectionStatus(Enum):
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"

class MessageType(Enum):
    # Connection management
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    PING = "ping"
    PONG = "pong"
    ERROR = "error"

    # Document processing
    DOC_STATUS_UPDATE = "doc_status_update"
    DOC_PROCESSING_START = "doc_processing_start"
    DOC_PROCESSING_PROGRESS = "doc_processing_progress"
    DOC_PROCESSING_COMPLETE = "doc_processing_complete"
    DOC_PROCESSING_ERROR = "doc_processing_error"

    # System notifications
    SYSTEM_ANNOUNCEMENT = "system_announcement"
    USER_NOTIFICATION = "user_notification"
    ORG_NOTIFICATION = "org_notification"

    # Subscription management
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    SUBSCRIPTION_CONFIRMED = "subscription_confirmed"

@dataclass
class ConnectionInfo:
    connection_id: str
    user_id: str
    organization_id: str
    websocket: WebSocket
    status: ConnectionStatus
    connected_at: datetime
    last_ping: datetime
    last_activity: datetime
    subscriptions: Set[str]
    metadata: Dict[str, Any]

@dataclass
class WebSocketMessage:
    message_id: str
    message_type: MessageType
    timestamp: datetime
    user_id: Optional[str] = None
    organization_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class RedisBackedConnectionManager:
    """
    Redis-backed connection manager supporting horizontal scaling
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        connection_ttl: int = 3600,  # 1 hour
        ping_interval: int = 30,  # 30 seconds
        cleanup_interval: int = 60,  # 1 minute
        max_connections_per_user: int = 10,
        max_connections_total: int = 15000
    ):
        self.redis_url = redis_url
        self.connection_ttl = connection_ttl
        self.ping_interval = ping_interval
        self.cleanup_interval = cleanup_interval
        self.max_connections_per_user = max_connections_per_user
        self.max_connections_total = max_connections_total

        # In-memory connection tracking (weak references for cleanup)
        self._local_connections: Dict[str, weakref.ref] = {}
        self._user_connections: Dict[str, Set[str]] = {}
        self._org_connections: Dict[str, Set[str]] = {}

        # Redis clients
        self._redis_client: Optional[redis.Redis] = None
        self._redis_pubsub: Optional[redis.PubSub] = None

        # Background tasks
        self._cleanup_task: Optional[asyncio.Task] = None
        self._ping_task: Optional[asyncio.Task] = None
        self._pubsub_task: Optional[asyncio.Task] = None

        # Event handlers
        self._message_handlers: Dict[MessageType, List[Callable]] = {}
        self._connection_handlers: Dict[str, List[Callable]] = {
            'connect': [],
            'disconnect': [],
            'error': []
        }

        # Metrics
        self._metrics = {
            'total_connections': 0,
            'active_connections': 0,
            'messages_sent': 0,
            'messages_received': 0,
            'errors': 0
        }

    async def initialize(self):
        """Initialize Redis connections and start background tasks"""
        try:
            self._redis_client = redis.from_url(self.redis_url, decode_responses=True)
            self._redis_pubsub = self._redis_client.pubsub()

            # Test Redis connection
            await self._redis_client.ping()

            # Start background tasks
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            self._ping_task = asyncio.create_task(self._ping_loop())
            self._pubsub_task = asyncio.create_task(self._pubsub_listener())

            logger.info("WebSocket connection manager initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize connection manager: {e}")
            raise

    async def shutdown(self):
        """Graceful shutdown"""
        # Cancel background tasks
        for task in [self._cleanup_task, self._ping_task, self._pubsub_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Close Redis connections
        if self._redis_pubsub:
            await self._redis_pubsub.close()
        if self._redis_client:
            await self._redis_client.close()

        # Close all WebSocket connections
        for conn_ref in list(self._local_connections.values()):
            conn = conn_ref()
            if conn and conn['websocket']:
                try:
                    await conn['websocket'].close()
                except Exception:
                    pass

        logger.info("WebSocket connection manager shutdown complete")

    async def connect(
        self,
        websocket: WebSocket,
        user_id: str,
        organization_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Establish a new WebSocket connection
        """
        try:
            # Check connection limits
            await self._check_connection_limits(user_id)

            # Generate connection ID
            connection_id = str(uuid.uuid4())

            # Accept WebSocket connection
            await websocket.accept()

            # Create connection info
            now = datetime.utcnow()
            connection_info = ConnectionInfo(
                connection_id=connection_id,
                user_id=user_id,
                organization_id=organization_id,
                websocket=websocket,
                status=ConnectionStatus.CONNECTED,
                connected_at=now,
                last_ping=now,
                last_activity=now,
                subscriptions=set(),
                metadata=metadata or {}
            )

            # Store in Redis
            await self._store_connection_in_redis(connection_info)

            # Store in memory with weak reference
            self._local_connections[connection_id] = weakref.ref(
                {**asdict(connection_info), 'websocket': websocket}
            )

            # Update user/org mappings
            if user_id not in self._user_connections:
                self._user_connections[user_id] = set()
            self._user_connections[user_id].add(connection_id)

            if organization_id not in self._org_connections:
                self._org_connections[organization_id] = set()
            self._org_connections[organization_id].add(connection_id)

            # Update metrics
            self._metrics['total_connections'] += 1
            self._metrics['active_connections'] += 1

            # Send welcome message
            await self.send_message(connection_id, WebSocketMessage(
                message_id=str(uuid.uuid4()),
                message_type=MessageType.CONNECT,
                timestamp=now,
                user_id=user_id,
                organization_id=organization_id,
                data={"connection_id": connection_id}
            ))

            # Publish connection event
            await self._publish_event('connection_established', {
                'connection_id': connection_id,
                'user_id': user_id,
                'organization_id': organization_id,
                'timestamp': now.isoformat()
            })

            # Call connection handlers
            await self._call_connection_handlers('connect', connection_info)

            logger.info(f"WebSocket connection established: {connection_id} for user {user_id}")
            return connection_id

        except Exception as e:
            logger.error(f"Failed to establish WebSocket connection: {e}")
            await self._handle_connection_error(websocket, str(e))
            raise

    async def disconnect(self, connection_id: str, reason: str = "Normal closure"):
        """Close and clean up a WebSocket connection"""
        try:
            conn_ref = self._local_connections.get(connection_id)
            if not conn_ref:
                return

            conn_data = conn_ref()
            if not conn_data:
                return

            websocket = conn_data.get('websocket')
            user_id = conn_data.get('user_id')
            organization_id = conn_data.get('organization_id')

            # Close WebSocket
            if websocket:
                try:
                    await websocket.close(reason=reason)
                except Exception:
                    pass

            # Remove from Redis
            await self._remove_connection_from_redis(connection_id)

            # Remove from memory
            self._local_connections.pop(connection_id, None)

            # Update user/org mappings
            if user_id and user_id in self._user_connections:
                self._user_connections[user_id].discard(connection_id)
                if not self._user_connections[user_id]:
                    self._user_connections.pop(user_id, None)

            if organization_id and organization_id in self._org_connections:
                self._org_connections[organization_id].discard(connection_id)
                if not self._org_connections[organization_id]:
                    self._org_connections.pop(organization_id, None)

            # Update metrics
            self._metrics['active_connections'] = max(0, self._metrics['active_connections'] - 1)

            # Publish disconnection event
            await self._publish_event('connection_closed', {
                'connection_id': connection_id,
                'user_id': user_id,
                'organization_id': organization_id,
                'reason': reason,
                'timestamp': datetime.utcnow().isoformat()
            })

            logger.info(f"WebSocket connection closed: {connection_id} ({reason})")

        except Exception as e:
            logger.error(f"Error during WebSocket disconnect: {e}")

    async def send_message(self, connection_id: str, message: WebSocketMessage):
        """Send a message to a specific connection"""
        try:
            conn_ref = self._local_connections.get(connection_id)
            if not conn_ref:
                return False

            conn_data = conn_ref()
            if not conn_data:
                return False

            websocket = conn_data.get('websocket')
            if not websocket:
                return False

            # Prepare message payload
            payload = {
                'message_id': message.message_id,
                'type': message.message_type.value,
                'timestamp': message.timestamp.isoformat(),
                'user_id': message.user_id,
                'organization_id': message.organization_id,
                'data': message.data,
                'error': message.error
            }

            # Send message
            await websocket.send_json(payload)

            # Update metrics
            self._metrics['messages_sent'] += 1

            return True

        except Exception as e:
            logger.error(f"Failed to send message to {connection_id}: {e}")
            await self.disconnect(connection_id, f"Send error: {str(e)}")
            return False

    async def broadcast_to_user(self, user_id: str, message: WebSocketMessage):
        """Broadcast a message to all connections for a user"""
        connection_ids = self._user_connections.get(user_id, set()).copy()
        tasks = [
            self.send_message(conn_id, message)
            for conn_id in connection_ids
        ]

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            success_count = sum(1 for result in results if result is True)
            logger.info(f"Broadcasted to {success_count}/{len(tasks)} connections for user {user_id}")

    async def broadcast_to_organization(self, organization_id: str, message: WebSocketMessage):
        """Broadcast a message to all connections in an organization"""
        connection_ids = self._org_connections.get(organization_id, set()).copy()
        tasks = [
            self.send_message(conn_id, message)
            for conn_id in connection_ids
        ]

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            success_count = sum(1 for result in results if result is True)
            logger.info(f"Broadcasted to {success_count}/{len(tasks)} connections for org {organization_id}")

    async def broadcast_to_all(self, message: WebSocketMessage):
        """Broadcast a message to all active connections"""
        connection_ids = list(self._local_connections.keys())
        tasks = [
            self.send_message(conn_id, message)
            for conn_id in connection_ids
        ]

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            success_count = sum(1 for result in results if result is True)
            logger.info(f"Broadcasted to {success_count}/{len(tasks)} connections globally")

    async def handle_message(self, connection_id: str, raw_message: str):
        """Handle incoming message from client"""
        try:
            # Parse message
            data = json.loads(raw_message)
            message_type = MessageType(data.get('type'))

            # Create message object
            message = WebSocketMessage(
                message_id=data.get('message_id', str(uuid.uuid4())),
                message_type=message_type,
                timestamp=datetime.utcnow(),
                data=data.get('data'),
                user_id=data.get('user_id'),
                organization_id=data.get('organization_id')
            )

            # Update metrics
            self._metrics['messages_received'] += 1

            # Handle specific message types
            if message_type == MessageType.PING:
                await self._handle_ping(connection_id, message)
            elif message_type == MessageType.SUBSCRIBE:
                await self._handle_subscribe(connection_id, message)
            elif message_type == MessageType.UNSUBSCRIBE:
                await self._handle_unsubscribe(connection_id, message)
            else:
                await self._call_message_handlers(message_type, connection_id, message)

        except Exception as e:
            logger.error(f"Error handling message from {connection_id}: {e}")
            await self.send_message(connection_id, WebSocketMessage(
                message_id=str(uuid.uuid4()),
                message_type=MessageType.ERROR,
                timestamp=datetime.utcnow(),
                error=f"Message processing error: {str(e)}"
            ))

    def add_message_handler(self, message_type: MessageType, handler: Callable):
        """Add a custom message handler"""
        if message_type not in self._message_handlers:
            self._message_handlers[message_type] = []
        self._message_handlers[message_type].append(handler)

    def add_connection_handler(self, event: str, handler: Callable):
        """Add a connection event handler"""
        if event in self._connection_handlers:
            self._connection_handlers[event].append(handler)

    async def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        try:
            # Get Redis stats
            redis_stats = await self._get_redis_connection_stats()

            return {
                'local_connections': len(self._local_connections),
                'user_connections': len(self._user_connections),
                'organization_connections': len(self._org_connections),
                'redis_connections': redis_stats,
                'metrics': self._metrics.copy(),
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting connection stats: {e}")
            return {'error': str(e)}

    # Private methods

    async def _check_connection_limits(self, user_id: str):
        """Check if connection limits are exceeded"""
        # Check total connections
        if len(self._local_connections) >= self.max_connections_total:
            raise Exception("Maximum total connections reached")

        # Check per-user connections
        user_conn_count = len(self._user_connections.get(user_id, set()))
        if user_conn_count >= self.max_connections_per_user:
            raise Exception("Maximum connections per user reached")

    async def _store_connection_in_redis(self, connection_info: ConnectionInfo):
        """Store connection info in Redis"""
        if not self._redis_client:
            return

        key = f"ws:connection:{connection_info.connection_id}"
        data = {
            **asdict(connection_info),
            'status': connection_info.status.value,
            'connected_at': connection_info.connected_at.isoformat(),
            'last_ping': connection_info.last_ping.isoformat(),
            'last_activity': connection_info.last_activity.isoformat(),
            'subscriptions': list(connection_info.subscriptions)
        }

        await self._redis_client.hset(key, mapping=data)
        await self._redis_client.expire(key, self.connection_ttl)

    async def _remove_connection_from_redis(self, connection_id: str):
        """Remove connection info from Redis"""
        if not self._redis_client:
            return

        key = f"ws:connection:{connection_id}"
        await self._redis_client.delete(key)

    async def _get_redis_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics from Redis"""
        if not self._redis_client:
            return {}

        try:
            # Count active connections in Redis
            pattern = "ws:connection:*"
            keys = await self._redis_client.keys(pattern)

            active_count = 0
            for key in keys:
                status = await self._redis_client.hget(key, 'status')
                if status == ConnectionStatus.CONNECTED.value:
                    active_count += 1

            return {
                'total_stored': len(keys),
                'active': active_count
            }
        except Exception as e:
            logger.error(f"Error getting Redis stats: {e}")
            return {}

    async def _ping_loop(self):
        """Background task to ping connections and cleanup stale ones"""
        while True:
            try:
                await asyncio.sleep(self.ping_interval)

                ping_message = WebSocketMessage(
                    message_id=str(uuid.uuid4()),
                    message_type=MessageType.PING,
                    timestamp=datetime.utcnow()
                )

                # Send ping to all connections
                connection_ids = list(self._local_connections.keys())
                await self.broadcast_to_all(ping_message)

                # Check for stale connections (no recent activity)
                now = datetime.utcnow()
                stale_threshold = now - timedelta(seconds=self.ping_interval * 3)

                for conn_id in connection_ids:
                    conn_ref = self._local_connections.get(conn_id)
                    if conn_ref:
                        conn_data = conn_ref()
                        if conn_data:
                            last_activity_str = conn_data.get('last_activity')
                            if last_activity_str:
                                last_activity = datetime.fromisoformat(last_activity_str)
                                if last_activity < stale_threshold:
                                    await self.disconnect(conn_id, "Stale connection")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in ping loop: {e}")

    async def _cleanup_loop(self):
        """Background task to cleanup expired connections"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)

                # Clean up dead weak references
                dead_connections = []
                for conn_id, conn_ref in self._local_connections.items():
                    if conn_ref() is None:
                        dead_connections.append(conn_id)

                for conn_id in dead_connections:
                    self._local_connections.pop(conn_id, None)
                    await self._remove_connection_from_redis(conn_id)

                if dead_connections:
                    logger.info(f"Cleaned up {len(dead_connections)} dead connections")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def _pubsub_listener(self):
        """Listen for Redis pub/sub messages"""
        if not self._redis_pubsub:
            return

        try:
            await self._redis_pubsub.subscribe("ws:events")

            async for message in self._redis_pubsub.listen():
                if message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])
                        # Handle cross-node events
                        await self._handle_cross_node_event(data)
                    except Exception as e:
                        logger.error(f"Error processing pubsub message: {e}")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in pubsub listener: {e}")

    async def _publish_event(self, event_type: str, data: Dict[str, Any]):
        """Publish event to Redis pub/sub"""
        if not self._redis_client:
            return

        try:
            event = {
                'type': event_type,
                'data': data,
                'timestamp': datetime.utcnow().isoformat()
            }
            await self._redis_client.publish("ws:events", json.dumps(event))
        except Exception as e:
            logger.error(f"Error publishing event: {e}")

    async def _handle_cross_node_event(self, event: Dict[str, Any]):
        """Handle events from other WebSocket nodes"""
        event_type = event.get('type')
        data = event.get('data', {})

        if event_type == 'document_status_update':
            # Forward to relevant connections
            user_id = data.get('user_id')
            organization_id = data.get('organization_id')
            message_data = data.get('message', {})

            message = WebSocketMessage(
                message_id=str(uuid.uuid4()),
                message_type=MessageType.DOC_STATUS_UPDATE,
                timestamp=datetime.utcnow(),
                user_id=user_id,
                organization_id=organization_id,
                data=message_data
            )

            if user_id:
                await self.broadcast_to_user(user_id, message)
            if organization_id:
                await self.broadcast_to_organization(organization_id, message)

    async def _handle_ping(self, connection_id: str, message: WebSocketMessage):
        """Handle ping message"""
        # Update last activity
        conn_ref = self._local_connections.get(connection_id)
        if conn_ref:
            conn_data = conn_ref()
            if conn_data:
                conn_data['last_activity'] = datetime.utcnow().isoformat()

        # Send pong response
        await self.send_message(connection_id, WebSocketMessage(
            message_id=str(uuid.uuid4()),
            message_type=MessageType.PONG,
            timestamp=datetime.utcnow()
        ))

    async def _handle_subscribe(self, connection_id: str, message: WebSocketMessage):
        """Handle subscription request"""
        channel = message.data.get('channel') if message.data else None
        if not channel:
            return

        # Add to connection subscriptions
        conn_ref = self._local_connections.get(connection_id)
        if conn_ref:
            conn_data = conn_ref()
            if conn_data:
                subscriptions = conn_data.get('subscriptions', set())
                subscriptions.add(channel)
                conn_data['subscriptions'] = list(subscriptions)

        # Send confirmation
        await self.send_message(connection_id, WebSocketMessage(
            message_id=str(uuid.uuid4()),
            message_type=MessageType.SUBSCRIPTION_CONFIRMED,
            timestamp=datetime.utcnow(),
            data={'channel': channel}
        ))

    async def _handle_unsubscribe(self, connection_id: str, message: WebSocketMessage):
        """Handle unsubscribe request"""
        channel = message.data.get('channel') if message.data else None
        if not channel:
            return

        # Remove from connection subscriptions
        conn_ref = self._local_connections.get(connection_id)
        if conn_ref:
            conn_data = conn_ref()
            if conn_data:
                subscriptions = conn_data.get('subscriptions', set())
                subscriptions.discard(channel)
                conn_data['subscriptions'] = list(subscriptions)

    async def _handle_connection_error(self, websocket: WebSocket, error: str):
        """Handle connection establishment error"""
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason=error)
        except Exception:
            pass

    async def _call_message_handlers(self, message_type: MessageType, connection_id: str, message: WebSocketMessage):
        """Call registered message handlers"""
        handlers = self._message_handlers.get(message_type, [])
        for handler in handlers:
            try:
                await handler(connection_id, message)
            except Exception as e:
                logger.error(f"Error in message handler: {e}")

    async def _call_connection_handlers(self, event: str, connection_info: ConnectionInfo):
        """Call registered connection handlers"""
        handlers = self._connection_handlers.get(event, [])
        for handler in handlers:
            try:
                await handler(connection_info)
            except Exception as e:
                logger.error(f"Error in connection handler: {e}")