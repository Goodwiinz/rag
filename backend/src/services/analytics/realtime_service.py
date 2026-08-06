"""
Real-time Analytics Service with WebSocket support
"""

import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set, Union

import redis.asyncio as redis
from fastapi import HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.config import settings
from src.core.database import get_async_session
from src.models.analytics.realtime_models import (
    ChannelMetrics,
    ConnectionStats,
    ConnectionStatus,
    EventStream,
    EventStreamData,
    LiveMetric,
    LiveMetricData,
    RealtimeAnalyticsSummary,
    RealtimeSubscription,
    SubscriptionCreate,
    SubscriptionResponse,
    SubscriptionType,
    WebSocketConnection,
    WebSocketMessage,
    WebSocketMessageType,
)
from src.models.base import GUID

logger = logging.getLogger(__name__)


class RealtimeAnalyticsService:
    """Real-time analytics service with WebSocket streaming"""

    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.active_connections: Dict[str, WebSocket] = {}
        self.subscriptions: Dict[
            str, Dict[str, Any]
        ] = {}  # websocket_id -> subscriptions
        self.event_handlers: Dict[str, List[Callable]] = {}
        self.running = False
        self.background_tasks: Set[asyncio.Task] = set()

    async def initialize(self):
        """Initialize the real-time service"""
        try:
            # Initialize Redis connection
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                retry_on_timeout=True,
                socket_keepalive=True,
                socket_keepalive_options={},
                health_check_interval=30,
            )

            # Test Redis connection
            await self.redis_client.ping()
            logger.info("Real-time analytics service initialized successfully")

            self.running = True

            # Start background tasks
            await self.start_background_tasks()

        except Exception as e:
            logger.error(f"Failed to initialize real-time analytics service: {e}")
            raise

    async def shutdown(self):
        """Shutdown the real-time service"""
        self.running = False

        # Cancel background tasks
        for task in self.background_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Close all active connections
        for connection_id, websocket in list(self.active_connections.items()):
            try:
                await websocket.close()
            except Exception:
                pass

        # Close Redis connection
        if self.redis_client:
            await self.redis_client.close()

        logger.info("Real-time analytics service shut down")

    async def start_background_tasks(self):
        """Start background processing tasks"""
        # Heartbeat task
        heartbeat_task = asyncio.create_task(self.heartbeat_loop())
        self.background_tasks.add(heartbeat_task)
        heartbeat_task.add_done_callback(self.background_tasks.discard)

        # Metrics aggregation task
        metrics_task = asyncio.create_task(self.metrics_aggregation_loop())
        self.background_tasks.add(metrics_task)
        metrics_task.add_done_callback(self.background_tasks.discard)

        # Event processing task
        event_task = asyncio.create_task(self.event_processing_loop())
        self.background_tasks.add(event_task)
        event_task.add_done_callback(self.background_tasks.discard)

        # Cleanup task
        cleanup_task = asyncio.create_task(self.cleanup_loop())
        self.background_tasks.add(cleanup_task)
        cleanup_task.add_done_callback(self.background_tasks.discard)

    async def websocket_endpoint(
        self, websocket: WebSocket, user_id: uuid.UUID, session_id: str
    ):
        """WebSocket endpoint for real-time analytics"""
        connection_id = str(uuid.uuid4())

        try:
            await websocket.accept()

            # Store connection
            self.active_connections[connection_id] = websocket

            # Track connection in database
            async with get_async_session() as db:
                # Canonical WebSocketConnection (src/models/websocket_status.py)
                # requires a non-null organization_id — resolve it from the
                # connecting user so the tenant boundary is recorded.
                from src.models.user import User

                user = await db.get(User, user_id)
                db_connection = WebSocketConnection(
                    connection_id=connection_id,
                    user_id=user_id,
                    organization_id=user.organization_id if user else None,
                    session_id=session_id,
                    ip_address=websocket.client.host if websocket.client else "unknown",
                    user_agent=websocket.headers.get("user-agent"),
                )
                db.add(db_connection)
                await db.commit()

            logger.info(
                f"WebSocket connection established: {connection_id} for user {user_id}"
            )

            # Send welcome message
            await self.send_message(
                connection_id,
                {
                    "type": WebSocketMessageType.AUTH,
                    "data": {
                        "connection_id": connection_id,
                        "user_id": str(user_id),
                        "session_id": session_id,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                },
            )

            # Handle WebSocket messages
            while self.running:
                try:
                    # Receive message with timeout
                    message = await asyncio.wait_for(
                        websocket.receive_text(), timeout=30.0
                    )

                    # Process message
                    await self.handle_websocket_message(connection_id, message)

                except asyncio.TimeoutError:
                    # Send heartbeat ping
                    await self.send_message(
                        connection_id,
                        {
                            "type": WebSocketMessageType.PING,
                            "data": {"timestamp": datetime.utcnow().isoformat()},
                        },
                    )

                except WebSocketDisconnect:
                    break

        except Exception as e:
            logger.error(f"WebSocket error for connection {connection_id}: {e}")

        finally:
            # Cleanup connection
            await self.cleanup_connection(connection_id)

    async def handle_websocket_message(self, connection_id: str, message: str):
        """Handle incoming WebSocket message"""
        try:
            data = json.loads(message)
            message_type = data.get("type")

            if message_type == WebSocketMessageType.SUBSCRIBE:
                await self.handle_subscribe(connection_id, data)

            elif message_type == WebSocketMessageType.UNSUBSCRIBE:
                await self.handle_unsubscribe(connection_id, data)

            elif message_type == WebSocketMessageType.PONG:
                await self.handle_pong(connection_id, data)

            elif message_type == WebSocketMessageType.PING:
                await self.send_message(
                    connection_id,
                    {
                        "type": WebSocketMessageType.PONG,
                        "data": {"timestamp": datetime.utcnow().isoformat()},
                    },
                )

            else:
                logger.warning(f"Unknown message type: {message_type}")

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON message: {message}")
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
            await self.send_error(connection_id, "Invalid message format")

    async def handle_subscribe(self, connection_id: str, data: Dict[str, Any]):
        """Handle subscription request"""
        try:
            subscription_type = SubscriptionType(data.get("subscription_type"))
            channel = data.get("channel")

            # Validate channel
            if not self.validate_channel(channel):
                await self.send_error(connection_id, "Invalid channel name")
                return

            # Create subscription
            subscription_id = str(uuid.uuid4())

            # Store subscription
            if connection_id not in self.subscriptions:
                self.subscriptions[connection_id] = {}

            self.subscriptions[connection_id][subscription_id] = {
                "type": subscription_type,
                "channel": channel,
                "filters": data.get("filters", {}),
                "batch_size": data.get("batch_size", 100),
                "update_interval": data.get("update_interval", 1000),
                "created_at": datetime.utcnow(),
            }

            # Store in database
            async with get_async_session() as db:
                db_subscription = RealtimeSubscription(
                    user_id=uuid.UUID(data.get("user_id")),  # Should come from auth
                    session_id=data.get("session_id"),
                    websocket_id=connection_id,
                    subscription_type=subscription_type,
                    channel=channel,
                    filters=data.get("filters"),
                    batch_size=data.get("batch_size", 100),
                    update_interval=data.get("update_interval", 1000),
                )
                db.add(db_subscription)
                await db.commit()

            # Send confirmation
            await self.send_message(
                connection_id,
                {
                    "type": WebSocketMessageType.DATA,
                    "data": {
                        "subscription_id": subscription_id,
                        "status": "subscribed",
                        "channel": channel,
                        "type": subscription_type,
                    },
                },
            )

            logger.info(
                f"Subscription created: {subscription_id} for connection {connection_id}"
            )

        except Exception as e:
            logger.error(f"Error creating subscription: {e}")
            await self.send_error(connection_id, "Failed to create subscription")

    async def handle_unsubscribe(self, connection_id: str, data: Dict[str, Any]):
        """Handle unsubscription request"""
        try:
            subscription_id = data.get("subscription_id")
            channel = data.get("channel")
            subscription_type = data.get("subscription_type")

            if connection_id in self.subscriptions:
                if subscription_id:
                    # Remove specific subscription
                    if subscription_id in self.subscriptions[connection_id]:
                        del self.subscriptions[connection_id][subscription_id]
                elif channel and subscription_type:
                    # Remove all subscriptions for channel/type
                    to_remove = [
                        sub_id
                        for sub_id, sub in self.subscriptions[connection_id].items()
                        if sub["channel"] == channel
                        and sub["type"] == subscription_type
                    ]
                    for sub_id in to_remove:
                        del self.subscriptions[connection_id][sub_id]
                else:
                    # Remove all subscriptions
                    self.subscriptions[connection_id].clear()

            # Update database
            async with get_async_session() as db:
                query = delete(RealtimeSubscription).where(
                    and_(
                        RealtimeSubscription.websocket_id == connection_id,
                        or_(
                            RealtimeSubscription.id
                            == (
                                uuid.UUID(subscription_id) if subscription_id else None
                            ),
                            and_(
                                RealtimeSubscription.channel == channel,
                                RealtimeSubscription.subscription_type
                                == subscription_type,
                            )
                            if channel and subscription_type
                            else False,
                        ),
                    )
                )
                await db.execute(query)
                await db.commit()

            # Send confirmation
            await self.send_message(
                connection_id,
                {
                    "type": WebSocketMessageType.DATA,
                    "data": {
                        "status": "unsubscribed",
                        "subscription_id": subscription_id,
                        "channel": channel,
                        "type": subscription_type,
                    },
                },
            )

            logger.info(f"Unsubscription completed for connection {connection_id}")

        except Exception as e:
            logger.error(f"Error handling unsubscription: {e}")
            await self.send_error(connection_id, "Failed to unsubscribe")

    async def handle_pong(self, connection_id: str, data: Dict[str, Any]):
        """Handle pong response"""
        try:
            # Update connection ping time
            async with get_async_session() as db:
                query = (
                    update(WebSocketConnection)
                    .where(WebSocketConnection.connection_id == connection_id)
                    .values(last_heartbeat=datetime.utcnow())
                )
                await db.execute(query)
                await db.commit()

        except Exception as e:
            logger.error(f"Error handling pong: {e}")

    async def send_message(self, connection_id: str, message: Dict[str, Any]):
        """Send message to WebSocket connection"""
        try:
            if connection_id in self.active_connections:
                websocket = self.active_connections[connection_id]
                await websocket.send_text(json.dumps(message))

                # Update connection stats
                async with get_async_session() as db:
                    query = (
                        update(WebSocketConnection)
                        .where(WebSocketConnection.connection_id == connection_id)
                        .values(
                            messages_sent=WebSocketConnection.messages_sent + 1,
                            bytes_sent=WebSocketConnection.bytes_sent
                            + len(json.dumps(message)),
                        )
                    )
                    await db.execute(query)
                    await db.commit()

        except Exception as e:
            logger.error(f"Error sending message to {connection_id}: {e}")
            # Remove connection if it's broken
            if connection_id in self.active_connections:
                del self.active_connections[connection_id]

    async def send_error(
        self, connection_id: str, error_message: str, error_code: str = None
    ):
        """Send error message to WebSocket connection"""
        await self.send_message(
            connection_id,
            {
                "type": WebSocketMessageType.ERROR,
                "error": error_message,
                "error_code": error_code,
            },
        )

    async def broadcast_to_channel(self, channel: str, message: Dict[str, Any]):
        """Broadcast message to all subscribers of a channel"""
        try:
            # Find all subscriptions for this channel
            target_connections = []
            for connection_id, subscriptions in self.subscriptions.items():
                for subscription in subscriptions.values():
                    if subscription["channel"] == channel:
                        target_connections.append(connection_id)
                        break

            # Send to all target connections
            for connection_id in target_connections:
                await self.send_message(
                    connection_id,
                    {
                        "type": WebSocketMessageType.DATA,
                        "data": {"channel": channel, **message},
                    },
                )

            # Also publish to Redis for other instances
            if self.redis_client:
                await self.redis_client.publish(
                    f"analytics:{channel}",
                    json.dumps(
                        {
                            "type": "broadcast",
                            "channel": channel,
                            "message": message,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    ),
                )

        except Exception as e:
            logger.error(f"Error broadcasting to channel {channel}: {e}")

    async def publish_metric(self, metric_data: LiveMetricData):
        """Publish live metric data"""
        try:
            # Store in database
            async with get_async_session() as db:
                db_metric = LiveMetric(
                    metric_id=metric_data.metric_id,
                    metric_name=metric_data.metric_name,
                    channel=metric_data.channel,
                    current_value=metric_data.current_value,
                    previous_value=metric_data.previous_value,
                    change_percentage=metric_data.change_percentage,
                    timestamp=metric_data.timestamp,
                    time_window=metric_data.time_window,
                    aggregation_type=metric_data.aggregation_type,
                    sample_count=metric_data.sample_count,
                    data_quality_score=metric_data.data_quality_score,
                    dimensions=metric_data.dimensions,
                    tags=metric_data.tags,
                    is_anomaly=metric_data.is_anomaly,
                    alert_threshold_min=metric_data.alert_threshold_min,
                    alert_threshold_max=metric_data.alert_threshold_max,
                    source=metric_data.source,
                    confidence=metric_data.confidence,
                )
                db.add(db_metric)
                await db.commit()

            # Broadcast to subscribers
            await self.broadcast_to_channel(
                metric_data.channel,
                {"type": "metric_update", "metric": metric_data.model_dump()},
            )

        except Exception as e:
            logger.error(f"Error publishing metric: {e}")

    async def publish_event(self, event_data: EventStreamData):
        """Publish event stream data"""
        try:
            # Store in database
            async with get_async_session() as db:
                db_event = EventStream(
                    event_type=event_data.event_type,
                    event_name=event_data.event_name,
                    source=event_data.source,
                    payload=event_data.payload,
                    metadata=event_data.metadata,
                    user_id=event_data.user_id,
                    session_id=event_data.session_id,
                    request_id=event_data.request_id,
                    correlation_id=event_data.correlation_id,
                    processed_at=event_data.processed_at,
                    processing_latency_ms=event_data.processing_latency_ms,
                    status=event_data.status,
                    error_message=event_data.error_message,
                    routing_key=event_data.routing_key,
                    channels=event_data.channels,
                )
                db.add(db_event)
                await db.commit()

            # Broadcast to channels
            channels = event_data.channels or [f"events:{event_data.event_type}"]
            for channel in channels:
                await self.broadcast_to_channel(
                    channel, {"type": "event", "event": event_data.model_dump()}
                )

        except Exception as e:
            logger.error(f"Error publishing event: {e}")

    async def heartbeat_loop(self):
        """Background task for sending heartbeats"""
        while self.running:
            try:
                await asyncio.sleep(30)  # Send heartbeat every 30 seconds

                # Send heartbeat to all connections
                for connection_id in list(self.active_connections.keys()):
                    await self.send_message(
                        connection_id,
                        {
                            "type": WebSocketMessageType.PING,
                            "data": {"timestamp": datetime.utcnow().isoformat()},
                        },
                    )

            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")

    async def metrics_aggregation_loop(self):
        """Background task for metrics aggregation"""
        while self.running:
            try:
                await asyncio.sleep(5)  # Process every 5 seconds

                # Get recent live metrics and aggregate
                async with get_async_session() as db:
                    # Find metrics that need aggregation
                    query = (
                        select(LiveMetric)
                        .where(
                            and_(
                                LiveMetric.timestamp
                                > datetime.utcnow() - timedelta(minutes=5),
                                LiveMetric.time_window.in_(["1m", "5m"]),
                            )
                        )
                        .order_by(LiveMetric.timestamp.desc())
                    )

                    result = await db.execute(query)
                    metrics = result.scalars().all()

                    # Group by metric and time window
                    metric_groups = {}
                    for metric in metrics:
                        key = f"{metric.metric_id}:{metric.time_window}"
                        if key not in metric_groups:
                            metric_groups[key] = []
                        metric_groups[key].append(metric)

                    # Aggregate each group
                    for key, metric_list in metric_groups.items():
                        if len(metric_list) > 1:
                            await self.aggregate_metrics(metric_list)

            except Exception as e:
                logger.error(f"Error in metrics aggregation loop: {e}")

    async def event_processing_loop(self):
        """Background task for processing event streams"""
        while self.running:
            try:
                await asyncio.sleep(1)  # Process every second

                # Check Redis for new events
                if self.redis_client:
                    # Process events from Redis streams or queues
                    pass  # Implementation depends on your event system

            except Exception as e:
                logger.error(f"Error in event processing loop: {e}")

    async def cleanup_loop(self):
        """Background task for cleanup operations"""
        while self.running:
            try:
                await asyncio.sleep(300)  # Cleanup every 5 minutes

                # Clean up expired subscriptions
                await self.cleanup_expired_subscriptions()

                # Clean up inactive connections
                await self.cleanup_inactive_connections()

                # Clean up old live metrics
                await self.cleanup_old_metrics()

            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def cleanup_connection(self, connection_id: str):
        """Clean up WebSocket connection"""
        try:
            # Remove from active connections
            if connection_id in self.active_connections:
                del self.active_connections[connection_id]

            # Remove subscriptions
            if connection_id in self.subscriptions:
                del self.subscriptions[connection_id]

            # Update database
            async with get_async_session() as db:
                query = (
                    update(WebSocketConnection)
                    .where(WebSocketConnection.connection_id == connection_id)
                    .values(
                        connection_status=ConnectionStatus.DISCONNECTED,
                        disconnected_at=datetime.utcnow(),
                    )
                )
                await db.execute(query)

                # Remove subscriptions from database
                query = delete(RealtimeSubscription).where(
                    RealtimeSubscription.websocket_id == connection_id
                )
                await db.execute(query)
                await db.commit()

            logger.info(f"Connection cleaned up: {connection_id}")

        except Exception as e:
            logger.error(f"Error cleaning up connection {connection_id}: {e}")

    async def cleanup_expired_subscriptions(self):
        """Clean up expired subscriptions"""
        try:
            async with get_async_session() as db:
                query = delete(RealtimeSubscription).where(
                    and_(
                        RealtimeSubscription.expires_at < datetime.utcnow(),
                        RealtimeSubscription.auto_renew == False,
                    )
                )
                result = await db.execute(query)
                await db.commit()

                if result.rowcount > 0:
                    logger.info(f"Cleaned up {result.rowcount} expired subscriptions")

        except Exception as e:
            logger.error(f"Error cleaning up expired subscriptions: {e}")

    async def cleanup_inactive_connections(self):
        """Clean up inactive WebSocket connections"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(minutes=5)

            async with get_async_session() as db:
                query = (
                    update(WebSocketConnection)
                    .where(
                        and_(
                            WebSocketConnection.connection_status
                            == ConnectionStatus.CONNECTED,
                            WebSocketConnection.last_heartbeat < cutoff_time,
                        )
                    )
                    .values(
                        connection_status=ConnectionStatus.DISCONNECTED,
                        disconnected_at=datetime.utcnow(),
                    )
                )
                result = await db.execute(query)
                await db.commit()

                if result.rowcount > 0:
                    logger.info(f"Marked {result.rowcount} connections as inactive")

        except Exception as e:
            logger.error(f"Error cleaning up inactive connections: {e}")

    async def cleanup_old_metrics(self):
        """Clean up old live metrics"""
        try:
            # Keep metrics for 24 hours
            cutoff_time = datetime.utcnow() - timedelta(hours=24)

            async with get_async_session() as db:
                query = delete(LiveMetric).where(LiveMetric.timestamp < cutoff_time)
                result = await db.execute(query)
                await db.commit()

                if result.rowcount > 0:
                    logger.info(f"Cleaned up {result.rowcount} old metrics")

        except Exception as e:
            logger.error(f"Error cleaning up old metrics: {e}")

    async def aggregate_metrics(self, metrics: List[LiveMetric]):
        """Aggregate a list of metrics"""
        try:
            if not metrics:
                return

            # Simple aggregation - can be enhanced based on requirements
            latest_metric = metrics[0]  # Already ordered by timestamp desc

            # Calculate aggregates
            values = [m.current_value for m in metrics]
            avg_value = sum(values) / len(values)
            min_value = min(values)
            max_value = max(values)

            # Store aggregated result (implementation depends on your aggregation strategy)
            # This could create a new aggregated metric or update existing ones

        except Exception as e:
            logger.error(f"Error aggregating metrics: {e}")

    def validate_channel(self, channel: str) -> bool:
        """Validate channel name"""
        import re

        return bool(re.match(r"^[a-zA-Z0-9._-]+$", channel))

    async def get_connection_stats(
        self, connection_id: str
    ) -> Optional[ConnectionStats]:
        """Get connection statistics"""
        try:
            async with get_async_session() as db:
                query = select(WebSocketConnection).where(
                    WebSocketConnection.connection_id == connection_id
                )
                result = await db.execute(query)
                connection = result.scalar_one_or_none()

                if connection:
                    # Calculate uptime
                    uptime = None
                    if connection.connected_at:
                        end_time = connection.disconnected_at or datetime.utcnow()
                        uptime = int(
                            (end_time - connection.connected_at).total_seconds()
                        )

                    return ConnectionStats(
                        connection_id=connection.connection_id,
                        user_id=connection.user_id,
                        session_id=connection.session_id,
                        client_ip=connection.ip_address,
                        is_connected=connection.connection_status
                        == ConnectionStatus.CONNECTED,
                        connected_at=connection.connected_at,
                        disconnected_at=connection.disconnected_at,
                        # Canonical model keeps one heartbeat timestamp, not a
                        # ping/pong pair — surface it in both stat slots.
                        last_ping=connection.last_heartbeat,
                        last_pong=connection.last_heartbeat,
                        messages_sent=connection.messages_sent,
                        messages_received=connection.messages_received,
                        bytes_sent=connection.bytes_sent,
                        bytes_received=connection.bytes_received,
                        active_subscriptions=len(
                            connection.subscription_channels or []
                        ),
                        max_subscriptions=0,  # no per-connection cap on canonical model
                        uptime_seconds=uptime,
                    )

        except Exception as e:
            logger.error(f"Error getting connection stats: {e}")

        return None

    async def get_realtime_summary(self) -> RealtimeAnalyticsSummary:
        """Get real-time analytics summary"""
        try:
            async with get_async_session() as db:
                # Count active connections
                connections_query = select(WebSocketConnection).where(
                    WebSocketConnection.connection_status == ConnectionStatus.CONNECTED
                )
                result = await db.execute(connections_query)
                total_connections = len(result.scalars().all())

                # Count active subscriptions
                subscriptions_query = select(RealtimeSubscription).where(
                    RealtimeSubscription.is_active == True
                )
                result = await db.execute(subscriptions_query)
                active_subscriptions = len(result.scalars().all())

                # Get recent metrics count
                metrics_query = select(LiveMetric).where(
                    LiveMetric.timestamp > datetime.utcnow() - timedelta(minutes=5)
                )
                result = await db.execute(metrics_query)
                metrics_updated = len(result.scalars().all())

                # Calculate rates (simplified)
                messages_per_second = 0.0  # Would need more sophisticated calculation
                events_per_second = 0.0
                alerts_triggered = 0  # Would need alert tracking

                return RealtimeAnalyticsSummary(
                    total_connections=total_connections,
                    active_subscriptions=active_subscriptions,
                    messages_per_second=messages_per_second,
                    events_per_second=events_per_second,
                    metrics_updated=metrics_updated,
                    alerts_triggered=alerts_triggered,
                    system_health="healthy",  # Would need health check logic
                    last_updated=datetime.utcnow(),
                )

        except Exception as e:
            logger.error(f"Error getting realtime summary: {e}")
            return RealtimeAnalyticsSummary(
                total_connections=0,
                active_subscriptions=0,
                messages_per_second=0.0,
                events_per_second=0.0,
                metrics_updated=0,
                alerts_triggered=0,
                system_health="error",
                last_updated=datetime.utcnow(),
            )

    async def get_channel_metrics(self, channel: str) -> ChannelMetrics:
        """Get channel-specific metrics"""
        try:
            async with get_async_session() as db:
                # Count subscriptions for channel
                query = select(RealtimeSubscription).where(
                    and_(
                        RealtimeSubscription.channel == channel,
                        RealtimeSubscription.is_active == True,
                    )
                )
                result = await db.execute(query)
                subscription_count = len(result.scalars().all())

                # Calculate message rate and size (simplified)
                messages_per_second = 0.0
                average_message_size = 0.0
                error_rate = 0.0

                # Get last message time
                last_message_at = None
                if self.redis_client:
                    # Could check Redis for last message timestamp
                    pass

                return ChannelMetrics(
                    channel=channel,
                    subscription_count=subscription_count,
                    messages_per_second=messages_per_second,
                    average_message_size=average_message_size,
                    last_message_at=last_message_at,
                    error_rate=error_rate,
                )

        except Exception as e:
            logger.error(f"Error getting channel metrics: {e}")
            return ChannelMetrics(
                channel=channel,
                subscription_count=0,
                messages_per_second=0.0,
                average_message_size=0.0,
                last_message_at=None,
                error_rate=0.0,
            )


# Global instance
realtime_service = RealtimeAnalyticsService()
