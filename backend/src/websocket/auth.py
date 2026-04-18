"""
WebSocket authentication middleware with JWT integration
Supports token validation, session management, and security policies
"""

import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

import redis.asyncio as redis
from fastapi import HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt
from redis.asyncio import Redis

from src.models.organization import Organization
from src.models.user import User

from ..core.config import settings

logger = logging.getLogger(__name__)


class WebSocketAuthenticator:
    """
    WebSocket authentication handler with JWT validation and Redis session management
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        session_ttl: int = 3600,  # 1 hour
        refresh_threshold: int = 300,  # 5 minutes before expiry
        max_concurrent_sessions: int = 10,
        rate_limit_per_minute: int = 60,
    ):
        self.redis_url = redis_url
        self.session_ttl = session_ttl
        self.refresh_threshold = refresh_threshold
        self.max_concurrent_sessions = max_concurrent_sessions
        self.rate_limit_per_minute = rate_limit_per_minute

        self._redis_client: Optional[Redis] = None

        # Security policies
        self.security_policies = {
            "require_https": not settings.DEBUG,
            "allow_origin_refresh": True,
            "strict_user_agent_validation": False,
            "ip_binding": True,  # Bind session to IP address
            "concurrent_session_limit": True,
        }

    async def initialize(self):
        """Initialize Redis client and other resources"""
        try:
            self._redis_client = redis.from_url(self.redis_url, decode_responses=True)
            await self._redis_client.ping()
            logger.info("WebSocket authenticator initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize WebSocket authenticator: {e}")
            raise

    async def shutdown(self):
        """Clean up resources"""
        if self._redis_client:
            await self._redis_client.close()

    async def authenticate_websocket(
        self,
        websocket: WebSocket,
        token: Optional[str] = None,
        organization_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        client_ip: Optional[str] = None,
    ) -> Tuple[User, str, str]:
        """
        Authenticate WebSocket connection and return user with session ID

        Args:
            websocket: WebSocket connection object
            token: JWT token from query parameter
            organization_id: Organization context
            user_agent: Client user agent string
            client_ip: Client IP address

        Returns:
            Tuple of (User, session_id, organization_id)

        Raises:
            WebSocketDisconnect: If authentication fails
        """
        try:
            # Validate required parameters
            if not token:
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="Missing authentication token",
                )
                raise WebSocketDisconnect(code=status.WS_1008_POLICY_VIOLATION)

            # Parse and validate JWT token
            user_info = await self._validate_jwt_token(token)
            if not user_info:
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="Invalid or expired token",
                )
                raise WebSocketDisconnect(code=status.WS_1008_POLICY_VIOLATION)

            user_id = user_info["sub"]
            user_email = user_info.get("email")

            # Get user from database
            user = await self._get_user(user_id)
            if not user or not user.is_active:
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="User not found or inactive",
                )
                raise WebSocketDisconnect(code=status.WS_1008_POLICY_VIOLATION)

            # Validate organization access
            org_id = organization_id or str(user.organization_id)
            organization = await self._validate_organization_access(user, org_id)
            if not organization:
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="Invalid organization access",
                )
                raise WebSocketDisconnect(code=status.WS_1008_POLICY_VIOLATION)

            # Check rate limiting
            if not await self._check_rate_limit(user_id):
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION, reason="Rate limit exceeded"
                )
                raise WebSocketDisconnect(code=status.WS_1008_POLICY_VIOLATION)

            # Check concurrent sessions
            if not await self._check_concurrent_sessions(user_id):
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="Maximum concurrent sessions exceeded",
                )
                raise WebSocketDisconnect(code=status.WS_1008_POLICY_VIOLATION)

            # Create session
            session_id = await self._create_websocket_session(
                user_id=user_id,
                organization_id=org_id,
                token=token,
                user_agent=user_agent,
                client_ip=client_ip,
            )

            logger.info(
                f"WebSocket authenticated: user={user_id}, session={session_id}, org={org_id}"
            )
            return user, session_id, org_id

        except WebSocketDisconnect:
            raise
        except Exception as e:
            logger.error(f"WebSocket authentication error: {e}")
            await websocket.close(
                code=status.WS_1011_INTERNAL_ERROR, reason="Authentication error"
            )
            raise WebSocketDisconnect(code=status.WS_1011_INTERNAL_ERROR)

    async def refresh_session(self, session_id: str) -> Optional[str]:
        """
        Refresh WebSocket session if near expiry

        Returns:
            New JWT token if refreshed, None otherwise
        """
        try:
            if not self._redis_client:
                return None

            session_key = f"ws:session:{session_id}"
            session_data = await self._redis_client.hgetall(session_key)

            if not session_data:
                return None

            # Check if refresh is needed
            expiry_time = datetime.fromisoformat(session_data.get("expires_at"))
            if datetime.utcnow() > (
                expiry_time - timedelta(seconds=self.refresh_threshold)
            ):
                # Generate new token
                user_id = session_data.get("user_id")
                organization_id = session_data.get("organization_id")

                new_token = await self._generate_refresh_token(user_id, organization_id)

                # Update session with new token
                await self._redis_client.hset(session_key, "token", new_token)
                await self._redis_client.hset(
                    session_key, "refreshed_at", datetime.utcnow().isoformat()
                )

                logger.info(f"Session refreshed: {session_id}")
                return new_token

            return None

        except Exception as e:
            logger.error(f"Error refreshing session {session_id}: {e}")
            return None

    async def invalidate_session(self, session_id: str, reason: str = "Logout"):
        """Invalidate a WebSocket session"""
        try:
            if not self._redis_client:
                return

            session_key = f"ws:session:{session_id}"

            # Get session data for audit
            session_data = await self._redis_client.hgetall(session_key)

            # Delete session
            await self._redis_client.delete(session_key)

            # Log session invalidation
            logger.info(
                f"Session invalidated: {session_id}, reason: {reason}, user: {session_data.get('user_id')}"
            )

        except Exception as e:
            logger.error(f"Error invalidating session {session_id}: {e}")

    async def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session information"""
        try:
            if not self._redis_client:
                return None

            session_key = f"ws:session:{session_id}"
            session_data = await self._redis_client.hgetall(session_key)

            if not session_data:
                return None

            return {
                "session_id": session_id,
                "user_id": session_data.get("user_id"),
                "organization_id": session_data.get("organization_id"),
                "created_at": session_data.get("created_at"),
                "last_activity": session_data.get("last_activity"),
                "expires_at": session_data.get("expires_at"),
                "client_ip": session_data.get("client_ip"),
                "user_agent": session_data.get("user_agent"),
                "is_active": True,
            }

        except Exception as e:
            logger.error(f"Error getting session info for {session_id}: {e}")
            return None

    async def update_session_activity(self, session_id: str):
        """Update session last activity timestamp"""
        try:
            if not self._redis_client:
                return

            session_key = f"ws:session:{session_id}"
            await self._redis_client.hset(
                session_key, "last_activity", datetime.utcnow().isoformat()
            )

        except Exception as e:
            logger.error(f"Error updating session activity for {session_id}: {e}")

    async def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        try:
            if not self._redis_client:
                return

            pattern = "ws:session:*"
            keys = await self._redis_client.keys(pattern)

            now = datetime.utcnow()
            expired_count = 0

            for key in keys:
                expires_at_str = await self._redis_client.hget(key, "expires_at")
                if expires_at_str:
                    expires_at = datetime.fromisoformat(expires_at_str)
                    if now > expires_at:
                        await self._redis_client.delete(key)
                        expired_count += 1

            if expired_count > 0:
                logger.info(f"Cleaned up {expired_count} expired WebSocket sessions")

        except Exception as e:
            logger.error(f"Error cleaning up expired sessions: {e}")

    # Private methods

    async def _validate_jwt_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate Supabase JWT token and return payload."""
        try:
            if not settings.SUPABASE_JWT_SECRET:
                logger.error("SUPABASE_JWT_SECRET not configured for WebSocket auth")
                return None

            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
            )

            # Check required claims
            user_id = payload.get("sub")
            if not user_id:
                return None

            # Map Supabase app_metadata role to top-level
            app_metadata = payload.get("app_metadata", {})
            if "role" not in payload:
                payload["role"] = app_metadata.get("role", "USER")

            return payload

        except ExpiredSignatureError:
            logger.warning("JWT token has expired")
            return None
        except JWTError as e:
            logger.warning(f"JWT validation error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error validating JWT token: {e}")
            return None

    async def _get_user(self, user_id: str) -> Optional[User]:
        """Get user from database"""
        try:
            # Import here to avoid circular imports
            from ..core.database import get_db_session

            async with get_db_session() as session:
                result = await session.execute(
                    "SELECT * FROM users WHERE id = :user_id AND is_deleted = false",
                    {"user_id": user_id},
                )
                user_data = result.fetchone()

                if user_data:
                    return User(**dict(user_data))
                return None

        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            return None

    async def _validate_organization_access(
        self, user: User, organization_id: str
    ) -> Optional[Organization]:
        """Validate user has access to organization"""
        try:
            # Import here to avoid circular imports
            from ..core.database import get_db_session

            async with get_db_session() as session:
                result = await session.execute(
                    """
                    SELECT o.* FROM organizations o
                    LEFT JOIN user_organization_roles uor ON o.id = uor.organization_id
                    WHERE o.id = :org_id
                    AND (o.is_public = true OR uor.user_id = :user_id)
                    AND o.is_deleted = false
                    """,
                    {"org_id": organization_id, "user_id": str(user.id)},
                )
                org_data = result.fetchone()

                if org_data:
                    return Organization(**dict(org_data))
                return None

        except Exception as e:
            logger.error(f"Error validating organization access: {e}")
            return None

    async def _check_rate_limit(self, user_id: str) -> bool:
        """Check if user is within rate limits"""
        try:
            if not self._redis_client:
                return True

            rate_limit_key = f"ws:rate_limit:{user_id}"
            current_count = await self._redis_client.incr(rate_limit_key)

            if current_count == 1:
                # Set expiry for the first increment
                await self._redis_client.expire(rate_limit_key, 60)  # 1 minute

            return current_count <= self.rate_limit_per_minute

        except Exception as e:
            logger.error(f"Error checking rate limit for user {user_id}: {e}")
            return True  # Allow on error

    async def _check_concurrent_sessions(self, user_id: str) -> bool:
        """Check if user has exceeded concurrent session limit"""
        if not self.security_policies["concurrent_session_limit"]:
            return True

        try:
            if not self._redis_client:
                return True

            pattern = f"ws:session:*"
            keys = await self._redis_client.keys(pattern)

            user_sessions = 0
            for key in keys:
                session_user_id = await self._redis_client.hget(key, "user_id")
                if session_user_id == user_id:
                    user_sessions += 1

            return user_sessions < self.max_concurrent_sessions

        except Exception as e:
            logger.error(f"Error checking concurrent sessions for user {user_id}: {e}")
            return True  # Allow on error

    async def _create_websocket_session(
        self,
        user_id: str,
        organization_id: str,
        token: str,
        user_agent: Optional[str] = None,
        client_ip: Optional[str] = None,
    ) -> str:
        """Create a new WebSocket session"""
        try:
            if not self._redis_client:
                return str(uuid.uuid4())

            session_id = str(uuid.uuid4())
            session_key = f"ws:session:{session_id}"

            now = datetime.utcnow()
            expires_at = now + timedelta(seconds=self.session_ttl)

            session_data = {
                "session_id": session_id,
                "user_id": user_id,
                "organization_id": organization_id,
                "token": token,
                "user_agent": user_agent or "Unknown",
                "client_ip": client_ip or "Unknown",
                "created_at": now.isoformat(),
                "last_activity": now.isoformat(),
                "expires_at": expires_at.isoformat(),
                "refreshed_at": now.isoformat(),
            }

            await self._redis_client.hset(session_key, mapping=session_data)
            await self._redis_client.expire(session_key, self.session_ttl)

            return session_id

        except Exception as e:
            logger.error(f"Error creating WebSocket session: {e}")
            return str(uuid.uuid4())

    async def _generate_refresh_token(self, user_id: str, organization_id: str) -> str:
        """Generate a new JWT token for session refresh"""
        try:
            now = datetime.utcnow()
            expires_at = now + timedelta(seconds=self.session_ttl)

            payload = {
                "sub": user_id,
                "organization_id": organization_id,
                "iat": now,
                "exp": expires_at,
                "type": "websocket_refresh",
                "jti": str(uuid.uuid4()),
            }

            return jwt.encode(
                payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
            )

        except Exception as e:
            logger.error(f"Error generating refresh token: {e}")
            return ""


# Global authenticator instance
_websocket_authenticator: Optional[WebSocketAuthenticator] = None


def get_websocket_authenticator() -> WebSocketAuthenticator:
    """Get or create the global WebSocket authenticator instance"""
    global _websocket_authenticator
    if _websocket_authenticator is None:
        _websocket_authenticator = WebSocketAuthenticator()
    return _websocket_authenticator


# Authentication decorator for WebSocket endpoints


async def websocket_auth_required(
    websocket: WebSocket, **kwargs
) -> Tuple[User, str, str]:
    """
    WebSocket authentication decorator

    Usage:
        user, session_id, organization_id = await websocket_auth_required(websocket)
    """
    authenticator = get_websocket_authenticator()

    # Extract token from query parameters
    token = kwargs.get("token")
    organization_id = kwargs.get("organization_id")

    # Get client information
    client = websocket.client
    client_ip = client.host if client else None
    headers = websocket.headers
    user_agent = headers.get("user-agent") if headers else None

    return await authenticator.authenticate_websocket(
        websocket=websocket,
        token=token,
        organization_id=organization_id,
        user_agent=user_agent,
        client_ip=client_ip,
    )
