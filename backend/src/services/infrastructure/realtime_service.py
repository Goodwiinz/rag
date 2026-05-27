"""
Real-time Communications Service - Port 8008
Handles WebSocket connections, real-time status updates, live notifications, and streaming responses
"""

import asyncio
import json
import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

import redis.asyncio as redis
import redis.asyncio as aioredis
from fastapi import (
    Depends,
    FastAPI,
    Form,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.core.config import settings
from src.shared.exceptions import (
    AuthenticationError,
    BaseCustomException,
    ValidationError,
    handle_exceptions,
)
from src.shared.schemas import (
    BaseResponse,
    HealthCheckResponse,
    NotificationType,
    ProcessingStatusUpdate,
    SearchProgressUpdate,
    SystemNotification,
    WebSocketMessage,
)
from src.shared.utils import (
    CorrelationIdMiddleware,
    EventLogger,
    HealthChecker,
    MetricsCollector,
    get_correlation_id,
)

# Configuration
REALTIME_SERVICE_CONFIG = {
    "service_name": "realtime-communications",
    "version": "1.0.0",
    "port": 8008,
    "host": "0.0.0.0",
    "max_connections_per_user": 10,
    "connection_timeout_seconds": 300,
    "heartbeat_interval_seconds": 30,
    "message_queue_size": 1000,
    "notification_retention_hours": 24,
}

# Initialize FastAPI app
app = FastAPI(
    title="Real-time Communications Service",
    version=REALTIME_SERVICE_CONFIG["version"],
    description="Service for real-time WebSocket communications and live updates",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(CorrelationIdMiddleware)

# Initialize components
event_logger = EventLogger(REALTIME_SERVICE_CONFIG["service_name"])
health_checker = HealthChecker(REALTIME_SERVICE_CONFIG["service_name"])
metrics = MetricsCollector(REALTIME_SERVICE_CONFIG["service_name"])

# Redis clients
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
pubsub = redis_client.pubsub()


# WebSocket connection management
class ConnectionManager:
    """Manages WebSocket connections"""

    def __init__(self):
        # Active connections by user_id
        self.user_connections: Dict[str, Set[WebSocket]] = {}
        # Connection metadata
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
        # Message queues for offline users
        self.message_queues: Dict[str, List[WebSocketMessage]] = {}
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

    async def connect(
        self, websocket: WebSocket, user_id: str, client_id: str, token: str
    ):
        """Accept and register WebSocket connection"""
        await websocket.accept()

        # Verify token (simplified - would integrate with user management service)
        try:
            # In production, verify JWT token with user management service
            payload = {"sub": user_id, "valid": True}  # Placeholder
            if not payload.get("valid"):
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return False
        except Exception:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return False

        # Check connection limit per user
        async with self._lock:
            user_conns = self.user_connections.get(user_id, set())
            if len(user_conns) >= REALTIME_SERVICE_CONFIG["max_connections_per_user"]:
                await websocket.close(code=status.WS_1013_TRY_AGAIN_LATER)
                return False

            # Add connection
            user_conns.add(websocket)
            self.user_connections[user_id] = user_conns

            # Store connection metadata
            connection_id = f"{user_id}:{client_id}"
            self.connection_metadata[connection_id] = {
                "websocket": websocket,
                "user_id": user_id,
                "client_id": client_id,
                "connected_at": datetime.now(timezone.utc),
                "last_heartbeat": datetime.now(timezone.utc),
                "ip_address": websocket.client.host if websocket.client else "unknown",
            }

        # Send queued messages if any
        await self._send_queued_messages(user_id)

        # Log connection
        await event_logger.log_event(
            event_type="websocket_connected",
            event_data={
                "user_id": user_id,
                "client_id": client_id,
                "connection_id": connection_id,
            },
            user_id=user_id,
        )

        # Record metrics
        metrics.increment_counter("websocket_connections", labels={"action": "connect"})
        metrics.set_gauge("active_connections", len(self.connection_metadata))

        return True

    async def disconnect(self, websocket: WebSocket, user_id: str, client_id: str):
        """Remove WebSocket connection"""
        connection_id = f"{user_id}:{client_id}"

        async with self._lock:
            # Remove from user connections
            if user_id in self.user_connections:
                self.user_connections[user_id].discard(websocket)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]

            # Remove metadata
            if connection_id in self.connection_metadata:
                del self.connection_metadata[connection_id]

        # Log disconnection
        await event_logger.log_event(
            event_type="websocket_disconnected",
            event_data={
                "user_id": user_id,
                "client_id": client_id,
                "connection_id": connection_id,
            },
            user_id=user_id,
        )

        # Record metrics
        metrics.increment_counter(
            "websocket_connections", labels={"action": "disconnect"}
        )
        metrics.set_gauge("active_connections", len(self.connection_metadata))

    async def send_to_user(self, user_id: str, message: WebSocketMessage):
        """Send message to all connections for a user"""
        connections = self.user_connections.get(user_id, set())

        if not connections:
            # Queue message for offline user
            await self._queue_message(user_id, message)
            return

        # Send to all active connections
        message_json = json.dumps(asdict(message), default=str)
        disconnected_connections = set()

        for connection in connections:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                # Mark failed connections for removal
                disconnected_connections.add(connection)
                await event_logger.log_error(
                    e, {"operation": "send_to_user", "user_id": user_id}
                )

        # Clean up disconnected connections
        if disconnected_connections:
            async with self._lock:
                if user_id in self.user_connections:
                    self.user_connections[user_id] -= disconnected_connections
                    if not self.user_connections[user_id]:
                        del self.user_connections[user_id]

        # Record metrics
        metrics.increment_counter("messages_sent", labels={"recipient_type": "user"})

    async def send_to_users(self, user_ids: List[str], message: WebSocketMessage):
        """Send message to multiple users"""
        for user_id in user_ids:
            await self.send_to_user(user_id, message)

    async def broadcast(
        self, message: WebSocketMessage, exclude_users: Optional[List[str]] = None
    ):
        """Broadcast message to all connected users"""
        exclude_set = set(exclude_users) if exclude_users else set()

        for user_id, connections in self.user_connections.items():
            if user_id not in exclude_set:
                await self.send_to_user(user_id, message)

        # Record metrics
        metrics.increment_counter(
            "messages_sent", labels={"recipient_type": "broadcast"}
        )

    async def _queue_message(self, user_id: str, message: WebSocketMessage):
        """Queue message for offline user"""
        if user_id not in self.message_queues:
            self.message_queues[user_id] = []

        # Add to queue
        self.message_queues[user_id].append(message)

        # Limit queue size
        max_queue_size = REALTIME_SERVICE_CONFIG["message_queue_size"]
        if len(self.message_queues[user_id]) > max_queue_size:
            # Remove oldest messages
            self.message_queues[user_id] = self.message_queues[user_id][
                -max_queue_size:
            ]

    async def _send_queued_messages(self, user_id: str):
        """Send queued messages to newly connected user"""
        if user_id not in self.message_queues:
            return

        queued_messages = self.message_queues.pop(user_id, [])

        for message in queued_messages:
            await self.send_to_user(user_id, message)

    async def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        async with self._lock:
            return {
                "total_connections": len(self.connection_metadata),
                "unique_users": len(self.user_connections),
                "connections_per_user": {
                    user_id: len(connections)
                    for user_id, connections in self.user_connections.items()
                },
                "queued_messages": sum(
                    len(queue) for queue in self.message_queues.values()
                ),
            }

    async def cleanup_stale_connections(self):
        """Clean up stale connections"""
        now = datetime.now(timezone.utc)
        timeout = REALTIME_SERVICE_CONFIG["connection_timeout_seconds"]
        heartbeat_interval = REALTIME_SERVICE_CONFIG["heartbeat_interval_seconds"]

        stale_connections = []

        async with self._lock:
            for connection_id, metadata in self.connection_metadata.items():
                last_heartbeat = metadata.get(
                    "last_heartbeat", metadata["connected_at"]
                )
                if (now - last_heartbeat).total_seconds() > timeout:
                    stale_connections.append(
                        (
                            metadata["websocket"],
                            metadata["user_id"],
                            metadata["client_id"],
                        )
                    )

        # Close stale connections
        for websocket, user_id, client_id in stale_connections:
            try:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                await self.disconnect(websocket, user_id, client_id)
            except Exception:
                pass  # Connection already closed

        if stale_connections:
            await event_logger.log_event(
                event_type="stale_connections_cleaned",
                event_data={"count": len(stale_connections)},
            )


class NotificationService:
    """Service for managing system notifications"""

    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
        self.notification_store = redis_client

    async def create_notification(
        self,
        notification_type: NotificationType,
        title: str,
        message: str,
        target_users: Optional[List[str]] = None,
        target_roles: Optional[List[str]] = None,
        actions: Optional[List[Dict[str, str]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create and send notification"""
        notification_id = str(uuid.uuid4())

        notification = SystemNotification(
            type="system_notification",
            data={
                "notification_id": notification_id,
                "notification_type": notification_type.value,
                "title": title,
                "message": message,
                "actions": actions or [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **(metadata or {}),
            },
        )

        # Store notification
        await self._store_notification(notification_id, notification)

        # Send to target users
        if target_users:
            await self.connection_manager.send_to_users(target_users, notification)
        else:
            # Broadcast to all users (or filter by role in production)
            await self.connection_manager.broadcast(notification)

        await event_logger.log_event(
            event_type="notification_created",
            event_data={
                "notification_id": notification_id,
                "type": notification_type.value,
                "title": title,
                "target_users": target_users or [],
                "target_roles": target_roles or [],
            },
        )

        return notification_id

    async def _store_notification(
        self, notification_id: str, notification: SystemNotification
    ):
        """Store notification in Redis"""
        key = f"notification:{notification_id}"
        await self.notification_store.setex(
            key,
            REALTIME_SERVICE_CONFIG["notification_retention_hours"] * 3600,
            json.dumps(asdict(notification), default=str),
        )

    async def get_user_notifications(
        self, user_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get recent notifications for user"""
        # This would query user-specific notifications
        # For now, return empty list
        return []


class EventProcessor:
    """Processes events from other services"""

    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager

    async def start_listening(self):
        """Start listening to Redis pub/sub for events"""
        await pubsub.subscribe("document_processing", "search_updates", "system_events")

        async for message in pubsub.listen():
            if message["type"] == "message":
                await self._process_event(message["data"])

    async def _process_event(self, event_data: str):
        """Process incoming event"""
        try:
            event = json.loads(event_data)
            event_type = event.get("type")

            if event_type == "processing_status_update":
                await self._handle_processing_update(event)
            elif event_type == "search_progress":
                await self._handle_search_progress(event)
            elif event_type == "system_notification":
                await self._handle_system_notification(event)

        except Exception as e:
            await event_logger.log_error(e, {"event_data": event_data})

    async def _handle_processing_update(self, event: Dict[str, Any]):
        """Handle document processing status update"""
        data = event.get("data", {})
        user_id = data.get("user_id")
        organization_id = data.get("organization_id")

        if user_id:
            message = ProcessingStatusUpdate(type="processing_status_update", data=data)
            await self.connection_manager.send_to_user(user_id, message)

    async def _handle_search_progress(self, event: Dict[str, Any]):
        """Handle search progress update"""
        data = event.get("data", {})
        user_id = data.get("user_id")

        if user_id:
            message = SearchProgressUpdate(type="search_progress", data=data)
            await self.connection_manager.send_to_user(user_id, message)

    async def _handle_system_notification(self, event: Dict[str, Any]):
        """Handle system notification"""
        data = event.get("data", {})
        target_users = data.get("target_users", [])
        notification_type = NotificationType(data.get("notification_type", "info"))

        message = SystemNotification(type="system_notification", data=data)

        if target_users:
            await self.connection_manager.send_to_users(target_users, message)
        else:
            await self.connection_manager.broadcast(message)


# Store background task references to prevent garbage collection
_background_tasks: set[asyncio.Task] = set()


def _fire_and_forget(coro):
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


# Initialize services
connection_manager = ConnectionManager()
notification_service = NotificationService(connection_manager)
event_processor = EventProcessor(connection_manager)


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    await event_logger.log_event(
        event_type="service_startup",
        event_data={"version": REALTIME_SERVICE_CONFIG["version"]},
    )

    # Add health checks
    health_checker.add_check(
        "redis", lambda: True
    )  # Would check actual Redis connection

    # Start background tasks
    _fire_and_forget(event_processor.start_listening())
    _fire_and_forget(heartbeat_monitor())
    _fire_and_forget(cleanup_stale_connections())


@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    client_id: str = Query(...),
    user_id: str = Query(...),
):
    """Main WebSocket endpoint"""
    # Verify and establish connection
    connected = await connection_manager.connect(websocket, user_id, client_id, token)
    if not connected:
        return

    connection_id = f"{user_id}:{client_id}"

    try:
        # Send welcome message
        welcome_message = WebSocketMessage(
            type="connected",
            data={
                "session_id": str(uuid.uuid4()),
                "user_id": user_id,
                "server_time": datetime.now(timezone.utc).isoformat(),
            },
        )
        await websocket.send_text(json.dumps(asdict(welcome_message), default=str))

        # Handle messages
        while True:
            try:
                # Receive message with timeout
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=REALTIME_SERVICE_CONFIG["heartbeat_interval_seconds"] + 10,
                )

                # Parse message
                message_data = json.loads(data)
                await handle_websocket_message(
                    websocket, user_id, client_id, message_data
                )

            except asyncio.TimeoutError:
                # Send heartbeat
                heartbeat = WebSocketMessage(
                    type="heartbeat",
                    data={"timestamp": datetime.now(timezone.utc).isoformat()},
                )
                await websocket.send_text(json.dumps(asdict(heartbeat), default=str))

                # Update last heartbeat
                async with connection_manager._lock:
                    if connection_id in connection_manager.connection_metadata:
                        connection_manager.connection_metadata[connection_id][
                            "last_heartbeat"
                        ] = datetime.now(timezone.utc)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await event_logger.log_error(
            e,
            {
                "user_id": user_id,
                "client_id": client_id,
                "operation": "websocket_connection",
            },
        )
    finally:
        await connection_manager.disconnect(websocket, user_id, client_id)


async def handle_websocket_message(
    websocket: WebSocket, user_id: str, client_id: str, message_data: Dict[str, Any]
):
    """Handle incoming WebSocket message"""
    message_type = message_data.get("type")

    if message_type == "heartbeat_response":
        # Update heartbeat timestamp
        connection_id = f"{user_id}:{client_id}"
        async with connection_manager._lock:
            if connection_id in connection_manager.connection_metadata:
                connection_manager.connection_metadata[connection_id][
                    "last_heartbeat"
                ] = datetime.now(timezone.utc)

    elif message_type == "subscribe":
        # Handle subscription to specific events
        channels = message_data.get("channels", [])
        # Would implement channel subscriptions here

    elif message_type == "unsubscribe":
        # Handle unsubscription from events
        channels = message_data.get("channels", [])
        # Would implement channel unsubscriptions here

    else:
        # Handle unknown message types
        await event_logger.log_event(
            event_type="unknown_websocket_message",
            event_data={
                "user_id": user_id,
                "message_type": message_type,
                "message_data": message_data,
            },
        )


@app.post("/notifications")
@handle_exceptions
async def create_notification(
    notification_type: NotificationType,
    title: str = Form(...),
    message: str = Form(...),
    target_users: str = Form(default="[]"),
    target_roles: str = Form(default="[]"),
    actions: str = Form(default="[]"),
    metadata: str = Form(default="{}"),
):
    """Create system notification"""
    try:
        users = json.loads(target_users) if target_users else []
        roles = json.loads(target_roles) if target_roles else []
        actions_list = json.loads(actions) if actions else []
        metadata_dict = json.loads(metadata) if metadata else {}

        notification_id = await notification_service.create_notification(
            notification_type=notification_type,
            title=title,
            message=message,
            target_users=users,
            target_roles=roles,
            actions=actions_list,
            metadata=metadata_dict,
        )

        return BaseResponse(
            success=True,
            message="Notification created successfully",
            data={"notification_id": notification_id},
        )

    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON in form data: {e}")


@app.get("/notifications")
@handle_exceptions
async def get_notifications(
    user_id: str = Query(...), limit: int = Query(20, ge=1, le=100)
):
    """Get user notifications"""
    notifications = await notification_service.get_user_notifications(user_id, limit)
    return {"notifications": notifications, "count": len(notifications)}


@app.get("/connections/stats")
@handle_exceptions
async def get_connection_stats():
    """Get WebSocket connection statistics"""
    return await connection_manager.get_connection_stats()


@app.post("/broadcast")
@handle_exceptions
async def broadcast_message(
    message_type: str = Form(...),
    message_data: str = Form(...),
    exclude_users: str = Form(default="[]"),
):
    """Broadcast message to all connected users"""
    try:
        data = json.loads(message_data)
        exclude = json.loads(exclude_users) if exclude_users else []

        message = WebSocketMessage(type=message_type, data=data)

        await connection_manager.broadcast(message, exclude_users=exclude)

        return BaseResponse(success=True, message="Message broadcasted successfully")

    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON in message data: {e}")


@app.post("/events/processing-status")
@handle_exceptions
async def send_processing_status_update(
    user_id: str = Form(...),
    document_id: str = Form(...),
    status: str = Form(...),
    progress: float = Form(0),
    error_message: str = Form(default=""),
):
    """Send processing status update to user"""
    message = ProcessingStatusUpdate(
        type="processing_status_update",
        data={
            "document_id": document_id,
            "status": status,
            "progress_percentage": progress,
            "error_message": error_message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )

    await connection_manager.send_to_user(user_id, message)

    return BaseResponse(success=True, message="Processing status update sent")


@app.post("/events/search-progress")
@handle_exceptions
async def send_search_progress_update(
    user_id: str = Form(...),
    search_id: str = Form(...),
    stage: str = Form(...),
    progress: float = Form(0),
    intermediate_results: str = Form(default="[]"),
):
    """Send search progress update to user"""
    try:
        results = json.loads(intermediate_results) if intermediate_results else []
    except json.JSONDecodeError:
        results = []

    message = SearchProgressUpdate(
        type="search_progress",
        data={
            "search_id": search_id,
            "stage": stage,
            "progress_percentage": progress,
            "intermediate_results": results,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )

    await connection_manager.send_to_user(user_id, message)

    return BaseResponse(success=True, message="Search progress update sent")


@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Service health check"""
    health_data = await health_checker.check_health()

    # Add WebSocket stats to health check
    connection_stats = await connection_manager.get_connection_stats()

    return HealthCheckResponse(
        status=health_data["status"],
        version=REALTIME_SERVICE_CONFIG["version"],
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc),
        services={
            **health_data["checks"],
            "websocket_connections": {
                "status": "healthy",
                "active_connections": connection_stats["total_connections"],
                "unique_users": connection_stats["unique_users"],
            },
        },
        uptime_seconds=0,  # Would track actual uptime
    )


async def heartbeat_monitor():
    """Monitor connection heartbeats"""
    while True:
        try:
            await connection_manager.cleanup_stale_connections()
            await asyncio.sleep(REALTIME_SERVICE_CONFIG["heartbeat_interval_seconds"])
        except Exception as e:
            await event_logger.log_error(e, {"task": "heartbeat_monitor"})
            await asyncio.sleep(60)


async def cleanup_stale_connections():
    """Background task to clean up stale connections"""
    while True:
        try:
            await connection_manager.cleanup_stale_connections()
            await asyncio.sleep(300)  # Check every 5 minutes
        except Exception as e:
            await event_logger.log_error(e, {"task": "cleanup_stale_connections"})
            await asyncio.sleep(600)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await pubsub.close()
    await redis_client.close()
    await event_logger.log_event(event_type="service_shutdown", event_data={})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.services.realtime_service:app",
        host=REALTIME_SERVICE_CONFIG["host"],
        port=REALTIME_SERVICE_CONFIG["port"],
        log_level=settings.LOG_LEVEL.lower(),
    )
