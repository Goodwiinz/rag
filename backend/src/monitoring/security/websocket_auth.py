"""
Secure WebSocket Authentication Module

Implements proper authentication and authorization for WebSocket connections
to prevent unauthorized access to real-time monitoring data.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

import jwt
from fastapi import HTTPException, Query, WebSocket

from src.auth.rbac_decorator import AnalyticsPermissionsChecker
from src.core.config import settings

logger = logging.getLogger(__name__)


class WebSocketAuthenticator:
    """Secure WebSocket authentication and authorization"""

    def __init__(self):
        self.redis_client = None
        self.session_cache = {}

    async def authenticate_websocket(
        self, websocket: WebSocket, token: str
    ) -> Optional[Dict[str, Any]]:
        """
        Authenticate WebSocket connection with proper token validation

        Args:
            websocket: WebSocket connection
            token: Authentication token from query parameter

        Returns:
            User information if authentication successful, None otherwise
        """
        try:
            # Validate token format
            if not token or not isinstance(token, str):
                await self._close_connection(websocket, 4001, "Invalid token format")
                return None

            # Decode and validate JWT token with signature verification
            try:
                payload = jwt.decode(
                    token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
                )
            except jwt.ExpiredSignatureError:
                await self._close_connection(websocket, 4001, "Token expired")
                return None
            except jwt.JWTError as e:
                logger.warning(f"Invalid WebSocket token: {e}")
                await self._close_connection(websocket, 4001, "Invalid token")
                return None

            # Check token type (must be access token)
            token_type = payload.get("type")
            if token_type != "access":
                await self._close_connection(websocket, 4001, "Invalid token type")
                return None

            # Extract user information
            user_id = payload.get("sub")
            user_role = payload.get("role")
            org_id = payload.get("org_id")

            if not user_id or not user_role:
                await self._close_connection(websocket, 4001, "Invalid token payload")
                return None

            # Check if token is revoked (if Redis is available)
            if await self._is_token_revoked(payload.get("jti")):
                await self._close_connection(websocket, 4001, "Token revoked")
                return None

            # Validate user permissions for WebSocket access
            if not await self._has_websocket_permission(user_role):
                await self._close_connection(
                    websocket, 4003, "Insufficient permissions"
                )
                return None

            # Log successful authentication
            logger.info(f"WebSocket authenticated: user_id={user_id}, role={user_role}")

            return {
                "user_id": user_id,
                "role": user_role,
                "org_id": org_id,
                "token_id": payload.get("jti"),
                "expires_at": datetime.fromtimestamp(payload.get("exp")),
            }

        except Exception as e:
            logger.error(f"WebSocket authentication error: {e}")
            await self._close_connection(websocket, 4001, "Authentication failed")
            return None

    async def authorize_websocket_access(
        self, user_info: Dict[str, Any], endpoint: str
    ) -> bool:
        """
        Authorize WebSocket access to specific endpoints

        Args:
            user_info: Authenticated user information
            endpoint: WebSocket endpoint being accessed

        Returns:
            True if authorized, False otherwise
        """
        user_role = user_info.get("role")

        # Define WebSocket access permissions by role
        websocket_permissions = {
            "admin": ["metrics", "traces", "logs", "alerts", "health", "dashboard"],
            "monitoring": [
                "metrics",
                "traces",
                "logs",
                "alerts",
                "health",
                "dashboard",
            ],
            "analyst": ["metrics", "traces", "logs", "dashboard"],
            "user": ["dashboard"],
            "guest": ["health"],
        }

        allowed_endpoints = websocket_permissions.get(user_role, [])
        return endpoint in allowed_endpoints

    async def validate_websocket_subscription(
        self, user_info: Dict[str, Any], subscription_data: Dict[str, Any]
    ) -> bool:
        """
        Validate WebSocket subscription request for data access

        Args:
            user_info: Authenticated user information
            subscription_data: Subscription request data

        Returns:
            True if subscription is allowed, False otherwise
        """
        user_role = user_info.get("role")
        org_id = user_info.get("org_id")

        # Check organization-based access
        if subscription_data.get("org_id") and org_id:
            if str(subscription_data["org_id"]) != str(org_id):
                logger.warning(
                    f"Cross-org WebSocket access attempt: user_org={org_id}, target_org={subscription_data['org_id']}"
                )
                return False

        # Validate subscription type based on user role
        subscription_type = subscription_data.get("type")
        allowed_subscriptions = {
            "admin": ["all", "metrics", "traces", "logs", "alerts", "system"],
            "monitoring": ["all", "metrics", "traces", "logs", "alerts"],
            "analyst": ["metrics", "traces", "logs"],
            "user": ["user-metrics", "dashboard"],
            "guest": ["health-status"],
        }

        user_allowed = allowed_subscriptions.get(user_role, [])
        return subscription_type in user_allowed or "all" in user_allowed

    async def _is_token_revoked(self, token_id: str) -> bool:
        """Check if token has been revoked"""
        if not self.redis_client:
            return False

        try:
            revoked = await self.redis_client.get(f"revoked_token:{token_id}")
            return revoked is not None
        except Exception:
            # If Redis is unavailable, assume token is not revoked
            return False

    async def _has_websocket_permission(self, user_role: str) -> bool:
        """Check if user role allows WebSocket access"""
        websocket_allowed_roles = ["admin", "monitoring", "analyst", "user", "guest"]
        return user_role in websocket_allowed_roles

    async def _close_connection(self, websocket: WebSocket, code: int, reason: str):
        """Close WebSocket connection with error code and reason"""
        try:
            await websocket.close(code=code, reason=reason)
        except Exception as e:
            logger.warning(f"Failed to close WebSocket connection: {e}")


# Global WebSocket authenticator instance
websocket_authenticator = WebSocketAuthenticator()


async def require_websocket_auth(
    websocket: WebSocket, token: str = Query(...)
) -> Optional[Dict[str, Any]]:
    """
    FastAPI dependency for WebSocket authentication

    Args:
        websocket: WebSocket connection
        token: Authentication token from query parameter

    Returns:
        Authenticated user information

    Raises:
        HTTPException: If authentication fails
    """
    user_info = await websocket_authenticator.authenticate_websocket(websocket, token)
    if not user_info:
        raise HTTPException(status_code=401, detail="WebSocket authentication failed")
    return user_info


class WebSocketConnectionManager:
    """Enhanced WebSocket connection manager with security controls"""

    def __init__(self):
        self._connections: Dict[str, Dict[str, Any]] = {}
        self._user_connections: Dict[str, set] = {}
        self._connection_limits = {
            "admin": 10,
            "monitoring": 5,
            "analyst": 3,
            "user": 2,
            "guest": 1,
        }

    async def add_connection(
        self,
        websocket: WebSocket,
        connection_id: str,
        user_info: Dict[str, Any],
        endpoint: str,
    ):
        """Add WebSocket connection with security validation"""
        user_id = user_info["user_id"]
        user_role = user_info["role"]

        # Check connection limits per user
        if not await self._check_connection_limit(user_id, user_role):
            await websocket.close(4003, "Connection limit exceeded")
            return False

        # Store connection with security metadata
        self._connections[connection_id] = {
            "websocket": websocket,
            "user_info": user_info,
            "endpoint": endpoint,
            "connected_at": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
            "subscriptions": set(),
        }

        # Track user connections
        if user_id not in self._user_connections:
            self._user_connections[user_id] = set()
        self._user_connections[user_id].add(connection_id)

        logger.info(f"WebSocket connection added: {connection_id} for user {user_id}")
        return True

    async def remove_connection(self, connection_id: str):
        """Remove WebSocket connection"""
        if connection_id in self._connections:
            connection_data = self._connections[connection_id]
            user_id = connection_data["user_info"]["user_id"]

            # Remove from user connections
            if user_id in self._user_connections:
                self._user_connections[user_id].discard(connection_id)
                if not self._user_connections[user_id]:
                    del self._user_connections[user_id]

            # Remove connection
            del self._connections[connection_id]
            logger.info(f"WebSocket connection removed: {connection_id}")

    async def _check_connection_limit(self, user_id: str, user_role: str) -> bool:
        """Check if user has exceeded connection limits"""
        max_connections = self._connection_limits.get(user_role, 1)
        current_connections = len(self._user_connections.get(user_id, set()))
        return current_connections < max_connections

    def get_connections_for_user(self, user_id: str) -> set:
        """Get all connections for a specific user"""
        return self._user_connections.get(user_id, set())

    def get_connection_info(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Get connection information"""
        return self._connections.get(connection_id)


# Secure WebSocket connection manager
secure_websocket_manager = WebSocketConnectionManager()
