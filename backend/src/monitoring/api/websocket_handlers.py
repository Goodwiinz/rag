"""
Secure WebSocket Handlers for Real-time Monitoring

WebSocket endpoints for real-time streaming of monitoring data including
metrics, traces, logs, alerts, and health status updates with proper authentication.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from pydantic import BaseModel

from ..services.observability_manager import get_observability_manager, ObservabilityManager
from ..security.websocket_auth import (
    websocket_authenticator,
    secure_websocket_manager,
    require_websocket_auth
)
from ...auth.rbac_decorator import AnalyticsPermissionsChecker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])


class WebSocketManager:
    """Manages WebSocket connections for real-time monitoring"""

    def __init__(self):
        # Active connections by type
        self._connections: Dict[str, Set[WebSocket]] = {
            "metrics": set(),
            "traces": set(),
            "logs": set(),
            "alerts": set(),
            "health": set(),
            "dashboard": set()
        }

        # Connection metadata
        self._connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}

        # Background broadcasting tasks
        self._broadcast_tasks: Dict[str, asyncio.Task] = {}
        self._running = False

    async def connect(self, websocket: WebSocket, connection_type: str, **metadata):
        """Accept a WebSocket connection"""
        await websocket.accept()

        if connection_type not in self._connections:
            raise ValueError(f"Invalid connection type: {connection_type}")

        self._connections[connection_type].add(websocket)
        self._connection_metadata[websocket] = {
            "type": connection_type,
            "connected_at": datetime.utcnow(),
            "metadata": metadata
        }

        logger.info(f"WebSocket connected: {connection_type} (total: {len(self._connections[connection_type])})")

        # Start background broadcast tasks if not running
        if not self._running:
            await self.start_broadcasting()

    async def disconnect(self, websocket: WebSocket):
        """Handle WebSocket disconnection"""
        # Find connection type
        connection_type = None
        for conn_type, connections in self._connections.items():
            if websocket in connections:
                connection_type = conn_type
                connections.remove(websocket)
                break

        # Remove metadata
        self._connection_metadata.pop(websocket, None)

        logger.info(f"WebSocket disconnected: {connection_type}")

        # Stop broadcasting if no connections
        total_connections = sum(len(conns) for conns in self._connections.values())
        if total_connections == 0:
            await self.stop_broadcasting()

    async def send_personal_message(self, websocket: WebSocket, message: Dict[str, Any]):
        """Send a message to a specific WebSocket connection"""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            await self.disconnect(websocket)

    async def broadcast_to_type(self, connection_type: str, message: Dict[str, Any]):
        """Broadcast a message to all connections of a specific type"""
        if connection_type not in self._connections:
            return

        disconnected = set()
        for websocket in self._connections[connection_type]:
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error broadcasting to {connection_type}: {e}")
                disconnected.add(websocket)

        # Clean up disconnected websockets
        for websocket in disconnected:
            await self.disconnect(websocket)

    async def start_broadcasting(self):
        """Start background broadcasting tasks"""
        if self._running:
            return

        self._running = True

        # Start broadcasting tasks for each connection type
        for connection_type in self._connections.keys():
            task = asyncio.create_task(self._broadcast_loop(connection_type))
            self._broadcast_tasks[connection_type] = task

    async def stop_broadcasting(self):
        """Stop background broadcasting tasks"""
        self._running = False

        # Cancel all broadcast tasks
        for task in self._broadcast_tasks.values():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._broadcast_tasks.clear()

    async def _broadcast_loop(self, connection_type: str):
        """Background loop for broadcasting data"""
        manager = get_observability_manager()

        while self._running and self._connections[connection_type]:
            try:
                if connection_type == "metrics":
                    await self._broadcast_metrics(manager)
                elif connection_type == "traces":
                    await self._broadcast_traces(manager)
                elif connection_type == "logs":
                    await self._broadcast_logs(manager)
                elif connection_type == "alerts":
                    await self._broadcast_alerts(manager)
                elif connection_type == "health":
                    await self._broadcast_health(manager)
                elif connection_type == "dashboard":
                    await self._broadcast_dashboard(manager)

                await asyncio.sleep(5)  # Broadcast every 5 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in broadcast loop for {connection_type}: {e}")
                await asyncio.sleep(10)

    async def _broadcast_metrics(self, manager: ObservabilityManager):
        """Broadcast recent metrics"""
        try:
            # Get metrics from last 5 minutes
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=5)

            metrics_data = await manager.get_metrics(
                start_time=start_time,
                end_time=end_time
            )

            message = {
                "type": "metrics_update",
                "timestamp": datetime.utcnow().isoformat(),
                "data": metrics_data
            }

            await self.broadcast_to_type("metrics", message)

        except Exception as e:
            logger.error(f"Error broadcasting metrics: {e}")

    async def _broadcast_traces(self, manager: ObservabilityManager):
        """Broadcast recent traces"""
        try:
            # Get traces from last 5 minutes
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=5)

            traces_data = await manager.get_traces(
                start_time=start_time,
                end_time=end_time,
                limit=50
            )

            message = {
                "type": "traces_update",
                "timestamp": datetime.utcnow().isoformat(),
                "data": traces_data
            }

            await self.broadcast_to_type("traces", message)

        except Exception as e:
            logger.error(f"Error broadcasting traces: {e}")

    async def _broadcast_logs(self, manager: ObservabilityManager):
        """Broadcast recent logs"""
        try:
            # Get logs from last 5 minutes
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=5)

            logs_data = await manager.get_logs(
                start_time=start_time,
                end_time=end_time,
                limit=100
            )

            message = {
                "type": "logs_update",
                "timestamp": datetime.utcnow().isoformat(),
                "data": logs_data
            }

            await self.broadcast_to_type("logs", message)

        except Exception as e:
            logger.error(f"Error broadcasting logs: {e}")

    async def _broadcast_alerts(self, manager: ObservabilityManager):
        """Broadcast recent alerts"""
        try:
            # Get active alerts
            alerts_data = await manager.get_alerts(
                status="open",
                limit=50
            )

            message = {
                "type": "alerts_update",
                "timestamp": datetime.utcnow().isoformat(),
                "data": alerts_data
            }

            await self.broadcast_to_type("alerts", message)

        except Exception as e:
            logger.error(f"Error broadcasting alerts: {e}")

    async def _broadcast_health(self, manager: ObservabilityManager):
        """Broadcast health status"""
        try:
            health_data = await manager.health_check()

            message = {
                "type": "health_update",
                "timestamp": datetime.utcnow().isoformat(),
                "data": health_data
            }

            await self.broadcast_to_type("health", message)

        except Exception as e:
            logger.error(f"Error broadcasting health: {e}")

    async def _broadcast_dashboard(self, manager: ObservabilityManager):
        """Broadcast dashboard overview data"""
        try:
            # Get comprehensive dashboard data
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=1)

            # Get health status
            health = await manager.health_check()

            # Get metrics summary
            metrics_data = await manager.get_metrics(
                start_time=start_time,
                end_time=end_time
            )

            # Get recent alerts
            alerts_data = await manager.get_alerts(
                start_time=start_time,
                end_time=end_time,
                limit=10
            )

            message = {
                "type": "dashboard_update",
                "timestamp": datetime.utcnow().isoformat(),
                "data": {
                    "health": health,
                    "metrics_summary": {
                        "total_metrics": len(metrics_data.get("metrics", {})),
                        "time_range": {
                            "start": start_time.isoformat(),
                            "end": end_time.isoformat()
                        }
                    },
                    "recent_alerts": alerts_data.get("alerts", {}),
                    "connections": {
                        "active_websockets": sum(len(conns) for conns in self._connections.values()),
                        "connection_types": {conn_type: len(conns) for conn_type, conns in self._connections.items()}
                    }
                }
            }

            await self.broadcast_to_type("dashboard", message)

        except Exception as e:
            logger.error(f"Error broadcasting dashboard: {e}")


# Global WebSocket manager
websocket_manager = WebSocketManager()


@router.websocket("/metrics")
async def websocket_metrics(
    websocket: WebSocket,
    token: str = Query(..., description="Authentication token")
):
    """WebSocket endpoint for real-time metrics updates"""
    connection_id = f"metrics_{datetime.utcnow().timestamp()}"

    # Authenticate WebSocket connection
    user_info = await websocket_authenticator.authenticate_websocket(websocket, token)
    if not user_info:
        return  # Connection already closed by authenticator

    # Authorize access to metrics endpoint
    if not await websocket_authenticator.authorize_websocket_access(user_info, "metrics"):
        await websocket.close(4003, "Insufficient permissions for metrics access")
        return

    # Add secure connection
    if not await secure_websocket_manager.add_connection(websocket, connection_id, user_info, "metrics"):
        return

    try:
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            "message": "Connected to metrics stream",
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_info['user_id'],
            "permissions": user_info['role']
        }))

        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)

                # Update last activity
                connection_info = secure_websocket_manager.get_connection_info(connection_id)
                if connection_info:
                    connection_info['last_activity'] = datetime.utcnow()

                # Handle client messages
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    }))
                elif message.get("type") == "subscribe":
                    # Validate subscription
                    if await websocket_authenticator.validate_websocket_subscription(user_info, message):
                        await websocket.send_text(json.dumps({
                            "type": "subscription_confirmed",
                            "metric": message.get("metric"),
                            "timestamp": datetime.utcnow().isoformat()
                        }))
                    else:
                        await websocket.send_text(json.dumps({
                            "type": "subscription_denied",
                            "reason": "Insufficient permissions for subscription",
                            "timestamp": datetime.utcnow().isoformat()
                        }))

            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON format",
                    "timestamp": datetime.utcnow().isoformat()
                }))
            except Exception as e:
                logger.error(f"Error in metrics WebSocket: {e}")
                break

    except WebSocketDisconnect:
        pass
    finally:
        await secure_websocket_manager.remove_connection(connection_id)
        logger.info(f"Metrics WebSocket disconnected for user {user_info['user_id']}")

    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            message = json.loads(data)

            # Handle client messages
            if message.get("type") == "ping":
                await websocket_manager.send_personal_message(websocket, {
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })
            elif message.get("type") == "subscribe":
                # Handle subscription to specific metrics
                await websocket_manager.send_personal_message(websocket, {
                    "type": "subscription_confirmed",
                    "metric": message.get("metric"),
                    "timestamp": datetime.utcnow().isoformat()
                })

    except WebSocketDisconnect:
        await websocket_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Error in metrics WebSocket: {e}")
        await websocket_manager.disconnect(websocket)


@router.websocket("/traces")
async def websocket_traces(
    websocket: WebSocket,
    token: str = Query(..., description="Authentication token")
):
    """WebSocket endpoint for real-time trace updates"""
    # TODO: Validate token here
    await websocket_manager.connect(websocket, "traces")

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "ping":
                await websocket_manager.send_personal_message(websocket, {
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })
            elif message.get("type") == "subscribe_trace":
                # Handle subscription to specific trace
                trace_id = message.get("trace_id")
                await websocket_manager.send_personal_message(websocket, {
                    "type": "trace_subscription_confirmed",
                    "trace_id": trace_id,
                    "timestamp": datetime.utcnow().isoformat()
                })

    except WebSocketDisconnect:
        await websocket_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Error in traces WebSocket: {e}")
        await websocket_manager.disconnect(websocket)


@router.websocket("/logs")
async def websocket_logs(
    websocket: WebSocket,
    token: str = Query(..., description="Authentication token")
):
    """WebSocket endpoint for real-time log updates"""
    # TODO: Validate token here
    await websocket_manager.connect(websocket, "logs")

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "ping":
                await websocket_manager.send_personal_message(websocket, {
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })
            elif message.get("type") == "subscribe_logs":
                # Handle subscription to specific log filters
                filters = message.get("filters", {})
                await websocket_manager.send_personal_message(websocket, {
                    "type": "logs_subscription_confirmed",
                    "filters": filters,
                    "timestamp": datetime.utcnow().isoformat()
                })

    except WebSocketDisconnect:
        await websocket_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Error in logs WebSocket: {e}")
        await websocket_manager.disconnect(websocket)


@router.websocket("/alerts")
async def websocket_alerts(
    websocket: WebSocket,
    token: str = Query(..., description="Authentication token")
):
    """WebSocket endpoint for real-time alert updates"""
    # TODO: Validate token here
    await websocket_manager.connect(websocket, "alerts")

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "ping":
                await websocket_manager.send_personal_message(websocket, {
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })
            elif message.get("type") == "subscribe_alerts":
                # Handle subscription to specific alert filters
                filters = message.get("filters", {})
                await websocket_manager.send_personal_message(websocket, {
                    "type": "alerts_subscription_confirmed",
                    "filters": filters,
                    "timestamp": datetime.utcnow().isoformat()
                })

    except WebSocketDisconnect:
        await websocket_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Error in alerts WebSocket: {e}")
        await websocket_manager.disconnect(websocket)


@router.websocket("/health")
async def websocket_health(
    websocket: WebSocket,
    token: str = Query(..., description="Authentication token")
):
    """WebSocket endpoint for real-time health status updates"""
    # TODO: Validate token here
    await websocket_manager.connect(websocket, "health")

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "ping":
                await websocket_manager.send_personal_message(websocket, {
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })

    except WebSocketDisconnect:
        await websocket_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Error in health WebSocket: {e}")
        await websocket_manager.disconnect(websocket)


@router.websocket("/dashboard")
async def websocket_dashboard(
    websocket: WebSocket,
    token: str = Query(..., description="Authentication token")
):
    """WebSocket endpoint for real-time dashboard updates"""
    # TODO: Validate token here
    await websocket_manager.connect(websocket, "dashboard")

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "ping":
                await websocket_manager.send_personal_message(websocket, {
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })

    except WebSocketDisconnect:
        await websocket_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Error in dashboard WebSocket: {e}")
        await websocket_manager.disconnect(websocket)