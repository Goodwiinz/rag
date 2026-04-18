"""
General WebSocket endpoint for real-time updates
"""

import json
import logging
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


# Simple in-memory connection manager for v1 API
class SimpleConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        logger.info(f"WebSocket connected for user {user_id}")

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        logger.info(f"WebSocket disconnected for user {user_id}")

    async def send_message(self, websocket: WebSocket, message: dict):
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending message: {e}")


manager = SimpleConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
):
    """
    General WebSocket endpoint for real-time updates

    SECURITY: Authentication is performed via Sec-WebSocket-Protocol header,
    NOT URL query parameters (tokens in URLs are logged by proxies).

    Authentication: Sec-WebSocket-Protocol: access_token.<jwt>

    This endpoint provides:
    - Connection heartbeat/ping
    - System notifications
    - Document processing updates (future)
    - Query status updates (future)
    """

    # Extract token from Sec-WebSocket-Protocol header
    protocols = websocket.headers.get("sec-websocket-protocol", "")
    token = None
    for protocol in protocols.split(","):
        protocol = protocol.strip()
        if protocol.startswith("access_token."):
            token = protocol.replace("access_token.", "", 1)

    # Authenticate user from token
    try:
        if not token:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Missing authentication token",
            )
            return

        # Validate Supabase JWT
        from src.core.security import verify_token

        token_data = verify_token(token)
        if not token_data or not token_data.user_id:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or expired token"
            )
            return

        user_id = token_data.user_id

    except Exception as e:
        logger.error(f"WebSocket authentication error: {e}")
        await websocket.close(
            code=status.WS_1011_INTERNAL_ERROR, reason="Authentication error"
        )
        return

    # Accept connection
    await manager.connect(websocket, user_id)

    try:
        # Send welcome message
        await manager.send_message(
            websocket,
            {
                "type": "connected",
                "message": "WebSocket connection established",
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": user_id,
            },
        )

        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages from client
                data = await websocket.receive_text()

                # Parse message
                try:
                    message = json.loads(data)
                    message_type = message.get("type")

                    # Handle ping/pong
                    if message_type == "ping":
                        await manager.send_message(
                            websocket,
                            {
                                "type": "pong",
                                "timestamp": datetime.utcnow().isoformat(),
                            },
                        )

                    # Handle other message types
                    elif message_type == "subscribe":
                        # Future: Handle subscriptions to specific events
                        await manager.send_message(
                            websocket,
                            {
                                "type": "subscribed",
                                "channel": message.get("channel"),
                                "timestamp": datetime.utcnow().isoformat(),
                            },
                        )

                    else:
                        logger.warning(f"Unknown message type: {message_type}")

                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON received: {data}")

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in WebSocket loop: {e}")
                break

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket, user_id)


@router.get("/ws/status")
async def websocket_status():
    """Get WebSocket connection statistics"""
    total_connections = sum(len(conns) for conns in manager.active_connections.values())
    return {
        "status": "available",
        "total_connections": total_connections,
        "active_users": len(manager.active_connections),
        "timestamp": datetime.utcnow().isoformat(),
    }
