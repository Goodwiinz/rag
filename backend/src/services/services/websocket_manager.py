"""
WebSocket manager for real-time graph updates
"""

import asyncio
import json
import logging
from typing import Dict, List, Set
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime

from ..core.cache import websocket_cache

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections by tenant"""

    def __init__(self):
        # Store connections by tenant_id
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # Store connection metadata
        self.connection_metadata: Dict[WebSocket, Dict] = {}
        # Track subscriber counts for analytics
        self.subscriber_counts: Dict[str, int] = {}

    async def connect(self, websocket: WebSocket, tenant_id: str, metadata: Dict = None):
        """Accept WebSocket connection and add to tenant group"""
        await websocket.accept()

        # Add to tenant connections
        if tenant_id not in self.active_connections:
            self.active_connections[tenant_id] = []

        self.active_connections[tenant_id].append(websocket)

        # Store metadata
        self.connection_metadata[websocket] = {
            "tenant_id": tenant_id,
            "connected_at": datetime.utcnow(),
            "last_ping": datetime.utcnow(),
            "metadata": metadata or {}
        }

        # Update subscriber count
        self.subscriber_counts[tenant_id] = len(self.active_connections[tenant_id])

        # Track in Redis for multi-instance support
        await self._track_connection_in_redis(tenant_id, "connect")

        logger.info(f"WebSocket connected for tenant {tenant_id}. "
                   f"Total connections for tenant: {len(self.active_connections[tenant_id])}")

    def disconnect(self, websocket: WebSocket, tenant_id: str):
        """Remove WebSocket connection from tenant group"""
        if tenant_id in self.active_connections:
            if websocket in self.active_connections[tenant_id]:
                self.active_connections[tenant_id].remove(websocket)

            # Clean up empty tenant groups
            if not self.active_connections[tenant_id]:
                del self.active_connections[tenant_id]

        # Remove metadata
        if websocket in self.connection_metadata:
            del self.connection_metadata[websocket]

        # Update subscriber count
        self.subscriber_counts[tenant_id] = len(self.active_connections.get(tenant_id, []))

        logger.info(f"WebSocket disconnected for tenant {tenant_id}. "
                   f"Remaining connections for tenant: {len(self.active_connections.get(tenant_id, []))}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send message to specific WebSocket connection"""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            # Don't disconnect here, let the caller handle cleanup

    async def broadcast_to_tenant(self, tenant_id: str, message: Dict):
        """Broadcast message to all connections for a tenant"""
        if tenant_id not in self.active_connections:
            return

        message_str = json.dumps(message, default=str)
        disconnected = []

        for connection in self.active_connections[tenant_id]:
            try:
                await connection.send_text(message_str)
                # Update last ping
                if connection in self.connection_metadata:
                    self.connection_metadata[connection]["last_ping"] = datetime.utcnow()
            except Exception as e:
                logger.warning(f"Failed to send message to WebSocket: {e}")
                disconnected.append(connection)

        # Clean up disconnected connections
        for connection in disconnected:
            self.disconnect(connection, tenant_id)

        # Track message in Redis
        await self._track_message_in_redis(tenant_id, message.get("type", "unknown"))

        logger.debug(f"Broadcasted message to {len(self.active_connections.get(tenant_id, []))} "
                    f"connections for tenant {tenant_id}")

    async def broadcast_to_all(self, message: Dict):
        """Broadcast message to all connected clients"""
        message_str = json.dumps(message, default=str)

        all_disconnected = []
        for tenant_id, connections in self.active_connections.items():
            tenant_disconnected = []
            for connection in connections:
                try:
                    await connection.send_text(message_str)
                    if connection in self.connection_metadata:
                        self.connection_metadata[connection]["last_ping"] = datetime.utcnow()
                except Exception as e:
                    logger.warning(f"Failed to send broadcast message: {e}")
                    tenant_disconnected.append(connection)
            all_disconnected.extend(tenant_disconnected)

        # Clean up disconnected connections
        for connection in all_disconnected:
            # Find tenant_id for this connection
            tenant_id = None
            if connection in self.connection_metadata:
                tenant_id = self.connection_metadata[connection]["tenant_id"]
            if tenant_id:
                self.disconnect(connection, tenant_id)

        logger.info(f"Broadcasted message to all clients")

    async def get_connection_count(self, tenant_id: str = None) -> int:
        """Get number of active connections"""
        if tenant_id:
            return len(self.active_connections.get(tenant_id, []))
        else:
            return sum(len(connections) for connections in self.active_connections.values())

    async def get_tenant_stats(self, tenant_id: str) -> Dict:
        """Get statistics for a specific tenant"""
        connections = self.active_connections.get(tenant_id, [])
        now = datetime.utcnow()

        connection_ages = []
        last_pings = []

        for connection in connections:
            if connection in self.connection_metadata:
                metadata = self.connection_metadata[connection]
                connection_ages.append((now - metadata["connected_at"]).total_seconds())
                last_pings.append((now - metadata["last_ping"]).total_seconds())

        return {
            "tenant_id": tenant_id,
            "active_connections": len(connections),
            "avg_connection_age_seconds": sum(connection_ages) / len(connection_ages) if connection_ages else 0,
            "avg_last_ping_seconds": sum(last_pings) / len(last_pings) if last_pings else 0,
            "oldest_connection_age_seconds": max(connection_ages) if connection_ages else 0,
            "oldest_ping_seconds": max(last_pings) if last_pings else 0
        }

    async def cleanup_stale_connections(self, max_idle_seconds: int = 300):
        """Remove connections that haven't been active"""
        now = datetime.utcnow()
        stale_connections = []

        for connection, metadata in self.connection_metadata.items():
            idle_time = (now - metadata["last_ping"]).total_seconds()
            if idle_time > max_idle_seconds:
                stale_connections.append((connection, metadata["tenant_id"]))

        for connection, tenant_id in stale_connections:
            try:
                await connection.close(code=4000, reason="Connection idle timeout")
            except Exception as e:
                logger.warning(f"Error closing stale connection: {e}")
            finally:
                self.disconnect(connection, tenant_id)

        if stale_connections:
            logger.info(f"Cleaned up {len(stale_connections)} stale connections")

    async def ping_all_connections(self):
        """Send ping to all connections to check connectivity"""
        ping_message = {"type": "ping", "timestamp": datetime.utcnow().isoformat()}

        all_disconnected = []
        for tenant_id, connections in self.active_connections.items():
            for connection in connections:
                try:
                    await connection.send_text(json.dumps(ping_message, default=str))
                except Exception as e:
                    logger.debug(f"Ping failed for connection: {e}")
                    all_disconnected.append((connection, tenant_id))

        # Clean up failed connections
        for connection, tenant_id in all_disconnected:
            self.disconnect(connection, tenant_id)

        logger.debug(f"Pinged {sum(len(conns) for conns in self.active_connections.values())} connections")

    async def _track_connection_in_redis(self, tenant_id: str, action: str):
        """Track connection events in Redis for analytics"""
        try:
            # This would be implemented when Redis client is available
            # For now, just log
            logger.debug(f"Connection {action} tracked for tenant {tenant_id}")
        except Exception as e:
            logger.error(f"Error tracking connection in Redis: {e}")

    async def _track_message_in_redis(self, tenant_id: str, message_type: str):
        """Track message broadcasts in Redis for analytics"""
        try:
            # This would be implemented when Redis client is available
            # For now, just log
            logger.debug(f"Message {message_type} tracked for tenant {tenant_id}")
        except Exception as e:
            logger.error(f"Error tracking message in Redis: {e}")


class WebSocketManager:
    """Enhanced WebSocket manager with event handling"""

    def __init__(self):
        self.connection_manager = ConnectionManager()
        self.event_handlers = {}
        self.running = True

    def register_event_handler(self, event_type: str, handler):
        """Register handler for specific event types"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)

    async def connect(self, websocket: WebSocket, tenant_id: str, metadata: Dict = None):
        """Connect WebSocket and register with connection manager"""
        await self.connection_manager.connect(websocket, tenant_id, metadata)

        # Trigger connection event
        await self._trigger_event("connection", {
            "tenant_id": tenant_id,
            "action": "connect",
            "metadata": metadata
        })

    def disconnect(self, websocket: WebSocket, tenant_id: str):
        """Disconnect WebSocket and clean up"""
        # Trigger disconnection event
        asyncio.create_task(self._trigger_event("connection", {
            "tenant_id": tenant_id,
            "action": "disconnect"
        }))

        self.connection_manager.disconnect(websocket, tenant_id)

    async def broadcast_to_tenant(self, tenant_id: str, message: Dict):
        """Broadcast message to tenant"""
        await self.connection_manager.broadcast_to_tenant(tenant_id, message)

        # Trigger message event
        await self._trigger_event("message", {
            "tenant_id": tenant_id,
            "message_type": message.get("type"),
            "message": message
        })

    async def broadcast_to_all(self, message: Dict):
        """Broadcast message to all tenants"""
        await self.connection_manager.broadcast_to_all(message)

        # Trigger broadcast event
        await self._trigger_event("broadcast", {
            "message_type": message.get("type"),
            "message": message
        })

    async def _trigger_event(self, event_type: str, data: Dict):
        """Trigger registered event handlers"""
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    await handler(data)
                except Exception as e:
                    logger.error(f"Error in event handler for {event_type}: {e}")

    async def start_background_tasks(self):
        """Start background maintenance tasks"""
        asyncio.create_task(self._maintenance_loop())

    async def _maintenance_loop(self):
        """Background maintenance loop"""
        while self.running:
            try:
                # Ping all connections every 30 seconds
                await self.connection_manager.ping_all_connections()

                # Clean up stale connections every 5 minutes
                await asyncio.sleep(300)
                await self.connection_manager.cleanup_stale_connections()

            except Exception as e:
                logger.error(f"Error in maintenance loop: {e}")
                await asyncio.sleep(60)  # Wait before retrying

    def stop(self):
        """Stop background tasks"""
        self.running = False


# Global WebSocket manager instance
websocket_manager = WebSocketManager()