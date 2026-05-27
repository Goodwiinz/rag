"""
Enhanced WebSocket connection manager for enterprise real-time communications
"""

import asyncio
import json
import logging
import re
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

import redis.asyncio as redis
from fastapi import HTTPException, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database import get_async_session
from src.models.document import ProcessingStatus
from src.models.processing import JobStatus
from src.models.websocket_status import (
    ConnectionEvent,
    ConnectionStatus,
    Priority,
    StatusUpdate,
    UpdateType,
    WebSocketConnection,
)
from src.services.base import BaseService

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """WebSocket message types"""

    CONNECT = "connect"
    DISCONNECT = "disconnect"
    PING = "ping"
    PONG = "pong"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    ERROR = "error"
    STATUS_UPDATE = "status_update"
    DOCUMENT_PROCESSING = "document_processing"
    JOB_STATUS = "job_status"
    SYSTEM_NOTIFICATION = "system_notification"
    # Thread activity events
    THREAD_CREATED = "thread_created"
    THREAD_UPDATED = "thread_updated"
    THREAD_DELETED = "thread_deleted"
    THREADS_BULK_UPDATED = "threads_bulk_updated"
    MESSAGE_CREATED = "message_created"
    MESSAGE_UPDATED = "message_updated"
    CONVERSATION_UPDATED = "conversation_updated"


@dataclass
class WebSocketMessage:
    """Structured WebSocket message"""

    type: MessageType
    data: Dict[str, Any]
    timestamp: datetime
    message_id: str = None
    priority: Priority = Priority.NORMAL
    target_channels: List[str] = None
    expires_at: Optional[datetime] = None

    def __post_init__(self):
        if self.message_id is None:
            self.message_id = str(uuid.uuid4())
        if self.target_channels is None:
            self.target_channels = []
        if isinstance(self.type, str):
            self.type = MessageType(self.type)
        if isinstance(self.priority, str):
            self.priority = Priority(self.priority)


@dataclass
class ConnectionInfo:
    """Connection metadata"""

    user_id: str
    organization_id: str
    connection_id: str
    websocket: WebSocket
    connected_at: datetime
    last_heartbeat: datetime
    subscribed_channels: Set[str]
    message_filter: Dict[str, Any] = None
    client_info: Dict[str, Any] = None

    def update_heartbeat(self):
        """Update connection heartbeat timestamp"""
        self.last_heartbeat = datetime.now(dt_timezone.utc)

    def is_subscribed_to_channel(self, channel: str) -> bool:
        """Check if connection is subscribed to channel"""
        return channel in self.subscribed_channels

    def should_receive_message(self, message: WebSocketMessage) -> bool:
        """Check if connection should receive this message"""
        # Check channel subscription
        if message.target_channels and not any(
            self.is_subscribed_to_channel(ch) for ch in message.target_channels
        ):
            return False

        # Check message filter
        if self.message_filter and message.data:
            # Apply filtering logic based on connection's filter
            for key, filter_value in self.message_filter.items():
                if key in message.data:
                    message_value = message.data[key]
                    if isinstance(filter_value, list):
                        if message_value not in filter_value:
                            return False
                    elif filter_value != message_value:
                        return False

        return True


class EnhancedConnectionManager(BaseService):
    """Enterprise-grade WebSocket connection manager with Redis clustering support"""

    _background_tasks: set[asyncio.Task] = set()

    @staticmethod
    def _fire_and_forget(coro):
        task = asyncio.create_task(coro)
        EnhancedConnectionManager._background_tasks.add(task)
        task.add_done_callback(EnhancedConnectionManager._background_tasks.discard)
        return task

    def __init__(self):
        super().__init__()
        self.active_connections: Dict[str, ConnectionInfo] = {}
        self.user_connections: Dict[str, Set[str]] = defaultdict(set)
        self.organization_connections: Dict[str, Set[str]] = defaultdict(set)
        self.channel_subscribers: Dict[str, Set[str]] = defaultdict(set)

        # Redis for clustering and message broadcasting
        self.redis_client: Optional[redis.Redis] = None
        self.redis_pubsub: Optional[redis.PubSub] = None

        # Background tasks
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        self.redis_listener_task: Optional[asyncio.Task] = None

        # Configuration
        self.heartbeat_interval = 30  # seconds
        self.connection_timeout = 300  # 5 minutes
        self.max_connections = 10000
        self.message_queue = asyncio.Queue(maxsize=1000)

    async def initialize(self):
        """Initialize the connection manager"""
        await super().initialize()

        # Initialize Redis client for clustering
        try:
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                health_check_interval=30,
            )

            # Test Redis connection
            await self.redis_client.ping()
            logger.info("Redis connection established for WebSocket clustering")

            # Initialize pubsub for inter-cluster communication
            self.redis_pubsub = self.redis_client.pubsub()
            await self.redis_pubsub.subscribe("websocket_broadcast")

            # Start background tasks
            self.heartbeat_task = asyncio.create_task(self._heartbeat_monitor())
            self.cleanup_task = asyncio.create_task(self._cleanup_stale_connections())
            self.redis_listener_task = asyncio.create_task(
                self._redis_message_listener()
            )

        except Exception as e:
            logger.warning(f"Redis not available, running in single-instance mode: {e}")
            self.redis_client = None

        logger.info("Enhanced WebSocket Connection Manager initialized")

    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down WebSocket Connection Manager...")

        # Cancel background tasks
        tasks = [self.heartbeat_task, self.cleanup_task, self.redis_listener_task]
        for task in tasks:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Close all connections
        for connection_info in list(self.active_connections.values()):
            try:
                await connection_info.websocket.close(code=status.WS_1001_GOING_AWAY)
            except Exception:
                pass

        # Close Redis connections
        if self.redis_pubsub:
            await self.redis_pubsub.close()
        if self.redis_client:
            await self.redis_client.close()

        await super().shutdown()
        logger.info("WebSocket Connection Manager shutdown complete")

    async def authenticate_websocket(
        self, websocket: WebSocket, token: str
    ) -> Optional[Dict[str, Any]]:
        """Authenticate WebSocket connection using JWT token.

        On auth failure, accepts the WebSocket before closing it to ensure
        proper protocol ordering (close frame requires an accepted connection).
        """
        async def _reject(code: int, reason: str) -> None:
            """Accept then immediately close to avoid connection leak."""
            try:
                await websocket.accept()
            except Exception:
                pass  # Already accepted or connection lost
            try:
                await websocket.close(code=code, reason=reason)
            except Exception:
                pass  # Best-effort close

        try:
            if not token:
                await _reject(
                    status.WS_1008_POLICY_VIOLATION,
                    "Authentication token required",
                )
                return None

            # Decode JWT token
            payload = jwt.decode(
                token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
            )

            user_id = payload.get("sub")
            organization_id = payload.get("organization_id")

            if not user_id or not organization_id:
                await _reject(
                    status.WS_1008_POLICY_VIOLATION, "Invalid token payload"
                )
                return None

            return {
                "user_id": user_id,
                "organization_id": organization_id,
                "token_payload": payload,
            }

        except JWTError as e:
            logger.warning(f"JWT authentication failed: {e}")
            await _reject(
                status.WS_1008_POLICY_VIOLATION, "Invalid or expired token"
            )
            return None
        except Exception as e:
            logger.error(f"WebSocket authentication error: {e}")
            await _reject(
                status.WS_1011_INTERNAL_ERROR, "Authentication error"
            )
            return None

    async def _connect_internal(
        self,
        websocket: WebSocket,
        user_id: str,
        organization_id: str,
        client_info: Dict[str, Any] = None,
        auth_method: Optional[str] = None,
    ) -> str:
        """
        Internal helper that handles the common connection setup logic.

        This method is called after authentication and WebSocket accept have
        been handled by the public connect methods.

        Args:
            websocket: The already-accepted WebSocket connection
            user_id: Authenticated user's ID
            organization_id: User's organization ID
            client_info: Optional client metadata
            auth_method: Optional auth method label for welcome message

        Returns:
            Connection ID
        """
        # Generate connection ID
        connection_id = str(uuid.uuid4())

        # Create connection info
        connection_info = ConnectionInfo(
            user_id=user_id,
            organization_id=organization_id,
            connection_id=connection_id,
            websocket=websocket,
            connected_at=datetime.now(dt_timezone.utc),
            last_heartbeat=datetime.now(dt_timezone.utc),
            subscribed_channels=set(),
            message_filter=client_info.get("message_filter") if client_info else None,
            client_info=client_info or {},
        )

        # Store connection
        self.active_connections[connection_id] = connection_info
        self.user_connections[user_id].add(connection_id)
        self.organization_connections[organization_id].add(connection_id)

        # Log connection to database
        await self._log_connection_event(
            connection_id=connection_id,
            event_type="connect",
            user_id=user_id,
            organization_id=organization_id,
            client_info=client_info,
        )

        # Build welcome message data
        welcome_data = {
            "connection_id": connection_id,
            "user_id": user_id,
            "organization_id": organization_id,
            "server_time": datetime.now(dt_timezone.utc).isoformat(),
            "heartbeat_interval": self.heartbeat_interval,
        }
        if auth_method:
            welcome_data["auth_method"] = auth_method

        # Send welcome message
        welcome_message = WebSocketMessage(
            type=MessageType.CONNECT,
            data=welcome_data,
            timestamp=datetime.now(dt_timezone.utc),
        )

        await self.send_message_to_connection(connection_id, welcome_message)

        # Log connection established
        auth_label = f" ({auth_method})" if auth_method else ""
        logger.info(
            f"WebSocket connection established{auth_label}: {connection_id} for user {user_id}"
        )

        return connection_id

    async def connect(
        self, websocket: WebSocket, token: str, client_info: Dict[str, Any] = None
    ) -> Optional[str]:
        """Accept and manage new WebSocket connection with token authentication"""
        # Authenticate connection
        auth_result = await self.authenticate_websocket(websocket, token)
        if not auth_result:
            return None

        # Check connection limits — accept then close to avoid connection leak
        if len(self.active_connections) >= self.max_connections:
            try:
                await websocket.accept()
            except Exception:
                pass
            try:
                await websocket.close(
                    code=status.WS_1013_TRY_AGAIN_LATER, reason="Server at maximum capacity"
                )
            except Exception:
                pass
            return None

        # Accept connection
        await websocket.accept()

        # Delegate to internal helper
        return await self._connect_internal(
            websocket=websocket,
            user_id=auth_result["user_id"],
            organization_id=auth_result["organization_id"],
            client_info=client_info,
            auth_method=None,
        )

    async def connect_authenticated(
        self,
        websocket: WebSocket,
        user_id: str,
        organization_id: str,
        client_info: Dict[str, Any] = None,
        subprotocol: Optional[str] = None,
    ) -> Optional[str]:
        """
        Accept and manage a pre-authenticated WebSocket connection.

        This method is used when authentication has already been performed
        (e.g., via the WebSocketAuthenticator helper) to avoid token exposure
        in URL query parameters.

        Args:
            websocket: The WebSocket connection
            user_id: Authenticated user's ID
            organization_id: User's organization ID
            client_info: Optional client metadata
            subprotocol: Optional subprotocol to respond with

        Returns:
            Connection ID if successful, None otherwise
        """
        # Check connection limits — accept then close to avoid connection leak
        if len(self.active_connections) >= self.max_connections:
            try:
                await websocket.accept()
            except Exception:
                pass
            try:
                await websocket.close(
                    code=status.WS_1013_TRY_AGAIN_LATER, reason="Server at maximum capacity"
                )
            except Exception:
                pass
            return None

        # Accept connection with appropriate subprotocol
        if subprotocol:
            await websocket.accept(subprotocol=subprotocol)
        else:
            await websocket.accept()

        # Delegate to internal helper
        return await self._connect_internal(
            websocket=websocket,
            user_id=user_id,
            organization_id=organization_id,
            client_info=client_info,
            auth_method="secure",
        )

    async def disconnect(self, connection_id: str, reason: str = None):
        """Handle WebSocket disconnection"""
        if connection_id not in self.active_connections:
            return

        connection_info = self.active_connections[connection_id]

        # Remove from tracking
        del self.active_connections[connection_id]
        self.user_connections[connection_info.user_id].discard(connection_id)
        self.organization_connections[connection_info.organization_id].discard(
            connection_id
        )

        # Remove from channel subscriptions
        for channel in connection_info.subscribed_channels:
            self.channel_subscribers[channel].discard(connection_id)

        # Log disconnection to database
        await self._log_connection_event(
            connection_id=connection_id,
            event_type="disconnect",
            user_id=connection_info.user_id,
            organization_id=connection_info.organization_id,
            event_data={"reason": reason},
        )

        logger.info(
            f"WebSocket connection closed: {connection_id} - {reason or 'Unknown reason'}"
        )

    async def subscribe_to_channel(self, connection_id: str, channel: str) -> bool:
        """Subscribe connection to a channel"""
        if connection_id not in self.active_connections:
            return False

        connection_info = self.active_connections[connection_id]
        connection_info.subscribed_channels.add(channel)
        self.channel_subscribers[channel].add(connection_id)

        # Send confirmation
        confirmation_message = WebSocketMessage(
            type=MessageType.SUBSCRIBE,
            data={"channel": channel, "subscribed": True},
            timestamp=datetime.now(dt_timezone.utc),
        )

        await self.send_message_to_connection(connection_id, confirmation_message)
        return True

    async def unsubscribe_from_channel(self, connection_id: str, channel: str) -> bool:
        """Unsubscribe connection from a channel"""
        if connection_id not in self.active_connections:
            return False

        connection_info = self.active_connections[connection_id]
        connection_info.subscribed_channels.discard(channel)
        self.channel_subscribers[channel].discard(connection_id)

        # Send confirmation
        confirmation_message = WebSocketMessage(
            type=MessageType.UNSUBSCRIBE,
            data={"channel": channel, "subscribed": False},
            timestamp=datetime.now(dt_timezone.utc),
        )

        await self.send_message_to_connection(connection_id, confirmation_message)
        return True

    async def send_message_to_connection(
        self, connection_id: str, message: WebSocketMessage
    ) -> bool:
        """Send message to specific connection"""
        if connection_id not in self.active_connections:
            return False

        connection_info = self.active_connections[connection_id]

        try:
            # Prepare message payload
            payload = {
                "id": message.message_id,
                "type": message.type.value,
                "data": message.data,
                "timestamp": message.timestamp.isoformat(),
                "priority": message.priority.value,
            }

            # Send message
            await connection_info.websocket.send_json(payload)

            # Record message metrics if we have a database record
            await self._record_message_metrics(
                connection_id, "sent", len(json.dumps(payload))
            )

            return True

        except Exception as e:
            logger.error(f"Failed to send message to {connection_id}: {e}")

            # Connection might be dead, schedule cleanup
            self._fire_and_forget(self.disconnect(connection_id, f"Send error: {str(e)}"))
            return False

    async def broadcast_to_channel(self, channel: str, message: WebSocketMessage):
        """Broadcast message to all subscribers of a channel"""
        # Validate channel name to prevent injection
        if not re.match(r'^[a-zA-Z0-9_.\-]+$', channel):
            raise ValueError(f"Invalid channel name: {channel}")

        # Add channel to target channels if not already present
        if channel not in message.target_channels:
            message.target_channels.append(channel)

        # Get subscribers
        subscriber_ids = self.channel_subscribers.get(channel, set())

        # Send to local connections
        for connection_id in subscriber_ids:
            if connection_id in self.active_connections:
                connection_info = self.active_connections[connection_id]
                if connection_info.should_receive_message(message):
                    await self.send_message_to_connection(connection_id, message)

        # Broadcast to other instances via Redis
        if self.redis_client:
            try:
                broadcast_payload = {
                    "channel": channel,
                    "message": asdict(message),
                    "source_instance": getattr(self, "instance_id", "unknown"),
                }
                await self.redis_client.publish(
                    "websocket_broadcast", json.dumps(broadcast_payload)
                )
            except Exception as e:
                logger.error(f"Failed to broadcast message via Redis: {e}")

    async def broadcast_to_user(self, user_id: str, message: WebSocketMessage):
        """Broadcast message to all connections for a user"""
        connection_ids = self.user_connections.get(user_id, set())

        for connection_id in connection_ids:
            if connection_id in self.active_connections:
                connection_info = self.active_connections[connection_id]
                if connection_info.should_receive_message(message):
                    await self.send_message_to_connection(connection_id, message)

    async def broadcast_to_organization(
        self, organization_id: str, message: WebSocketMessage
    ):
        """Broadcast message to all connections in an organization"""
        connection_ids = self.organization_connections.get(organization_id, set())

        for connection_id in connection_ids:
            if connection_id in self.active_connections:
                connection_info = self.active_connections[connection_id]
                if connection_info.should_receive_message(message):
                    await self.send_message_to_connection(connection_id, message)

    async def handle_client_message(self, connection_id: str, raw_message: str):
        """Handle incoming message from client"""
        if connection_id not in self.active_connections:
            return

        connection_info = self.active_connections[connection_id]
        connection_info.update_heartbeat()

        try:
            # Parse message
            data = json.loads(raw_message)
            message_type = data.get("type")
            message_data = data.get("data", {})

            # Handle different message types
            if message_type == MessageType.PING.value:
                pong_message = WebSocketMessage(
                    type=MessageType.PONG,
                    data={"timestamp": datetime.now(dt_timezone.utc).isoformat()},
                    timestamp=datetime.now(dt_timezone.utc),
                )
                await self.send_message_to_connection(connection_id, pong_message)

            elif message_type == MessageType.SUBSCRIBE.value:
                channel = message_data.get("channel")
                if channel:
                    await self.subscribe_to_channel(connection_id, channel)

            elif message_type == MessageType.UNSUBSCRIBE.value:
                channel = message_data.get("channel")
                if channel:
                    await self.unsubscribe_from_channel(connection_id, channel)

            elif message_type == MessageType.STATUS_UPDATE.value:
                # Update connection status or heartbeat
                await self._handle_status_update(connection_id, message_data)

            else:
                logger.warning(
                    f"Unknown message type: {message_type} from {connection_id}"
                )

        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from {connection_id}: {raw_message}")
        except Exception as e:
            logger.error(f"Error handling message from {connection_id}: {e}")

            error_message = WebSocketMessage(
                type=MessageType.ERROR,
                data={
                    "error": "Message processing failed",
                    "details": str(e) if settings.DEBUG else "Internal error",
                },
                timestamp=datetime.now(dt_timezone.utc),
            )
            await self.send_message_to_connection(connection_id, error_message)

    async def _handle_status_update(
        self, connection_id: str, status_data: Dict[str, Any]
    ):
        """Handle status update from client"""
        connection_info = self.active_connections[connection_id]

        # Update heartbeat
        connection_info.update_heartbeat()

        # Update message filter if provided
        if "message_filter" in status_data:
            connection_info.message_filter = status_data["message_filter"]

        # Record status update in database
        await self._log_connection_event(
            connection_id=connection_id,
            event_type="status_update",
            user_id=connection_info.user_id,
            organization_id=connection_info.organization_id,
            event_data=status_data,
        )

    async def _heartbeat_monitor(self):
        """Monitor connection heartbeats and detect stale connections"""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)

                current_time = datetime.now(dt_timezone.utc)
                stale_connections = []

                for connection_id, connection_info in self.active_connections.items():
                    # Check if connection is stale
                    time_since_heartbeat = (
                        current_time - connection_info.last_heartbeat
                    ).total_seconds()

                    if time_since_heartbeat > self.connection_timeout:
                        stale_connections.append(connection_id)
                    elif time_since_heartbeat > self.heartbeat_interval * 2:
                        # Send ping request
                        ping_message = WebSocketMessage(
                            type=MessageType.PING,
                            data={"timestamp": current_time.isoformat()},
                            timestamp=current_time,
                        )
                        await self.send_message_to_connection(
                            connection_id, ping_message
                        )

                # Clean up stale connections
                for connection_id in stale_connections:
                    await self.disconnect(
                        connection_id, "Connection timeout - no heartbeat"
                    )

                if stale_connections:
                    logger.info(
                        f"Cleaned up {len(stale_connections)} stale WebSocket connections"
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat monitor: {e}")
                await asyncio.sleep(5)  # Brief pause before retrying

    async def _cleanup_stale_connections(self):
        """Periodic cleanup of stale connections and expired data"""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes

                # Clean up database records
                async with get_async_session() as session:
                    try:
                        # Clean up expired status updates
                        expired_cutoff = datetime.utcnow() - timedelta(hours=24)

                        # This would require adding the delete method to the base model
                        # For now, we'll just log the cleanup need
                        logger.info("Database cleanup task completed")

                    except Exception as e:
                        logger.error(f"Database cleanup error: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
                await asyncio.sleep(30)  # Brief pause before retrying

    async def _redis_message_listener(self):
        """Listen for broadcast messages from other instances"""
        if not self.redis_client:
            return

        while True:
            try:
                message = await self.redis_pubsub.get_message(timeout=1.0)
                if message and message["type"] == "message":
                    try:
                        broadcast_data = json.loads(message["data"])

                        # Ignore our own broadcasts
                        source_instance = broadcast_data.get("source_instance")
                        if source_instance == getattr(self, "instance_id", "unknown"):
                            continue

                        # Process the broadcast
                        channel = broadcast_data["channel"]
                        message_dict = broadcast_data["message"]

                        # Reconstruct WebSocketMessage
                        message = WebSocketMessage(
                            type=MessageType(message_dict["type"]),
                            data=message_dict["data"],
                            timestamp=datetime.fromisoformat(message_dict["timestamp"]),
                            message_id=message_dict["id"],
                            priority=Priority(message_dict["priority"]),
                            target_channels=message_dict.get("target_channels", []),
                        )

                        # Forward to local subscribers
                        await self.broadcast_to_channel(channel, message)

                    except (json.JSONDecodeError, KeyError, ValueError) as e:
                        logger.error(f"Invalid broadcast message format: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Redis message listener error: {e}")
                await asyncio.sleep(1)

    async def _log_connection_event(
        self,
        connection_id: str,
        event_type: str,
        user_id: str,
        organization_id: str,
        client_info: Dict = None,
        event_data: Dict = None,
    ):
        """Log connection event to database"""
        try:
            async with get_async_session() as session:
                # For now, just log the event - full database implementation
                # would require proper async session handling
                logger.debug(f"Connection event: {event_type} for {connection_id}")

        except Exception as e:
            logger.error(f"Failed to log connection event: {e}")

    async def _record_message_metrics(
        self, connection_id: str, direction: str, size_bytes: int
    ):
        """Record message metrics in database"""
        try:
            # For now, just log metrics - full implementation would update
            # the WebSocketConnection record in the database
            logger.debug(
                f"Message metrics: {direction} {size_bytes} bytes to {connection_id}"
            )

        except Exception as e:
            logger.error(f"Failed to record message metrics: {e}")

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        return {
            "total_connections": len(self.active_connections),
            "unique_users": len(self.user_connections),
            "unique_organizations": len(self.organization_connections),
            "channel_subscriptions": {
                channel: len(subscribers)
                for channel, subscribers in self.channel_subscribers.items()
            },
            "max_connections": self.max_connections,
            "redis_enabled": self.redis_client is not None,
        }

    def get_user_connections(self, user_id: str) -> List[str]:
        """Get all connection IDs for a user"""
        return list(self.user_connections.get(user_id, set()))

    def get_organization_connections(self, organization_id: str) -> List[str]:
        """Get all connection IDs for an organization"""
        return list(self.organization_connections.get(organization_id, set()))


# Global connection manager instance
connection_manager = EnhancedConnectionManager()
