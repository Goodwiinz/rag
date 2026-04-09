"""
Secure WebSocket Authentication Helper

This module provides secure authentication for WebSocket connections
without exposing JWT tokens in URL query parameters.

Security improvements:
- Tokens transmitted via headers instead of URLs
- Supports multiple authentication methods for browser compatibility
- No token exposure in server logs, browser history, or dev tools
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException, WebSocket, status
from jose import jwt

from .config import settings

logger = logging.getLogger(__name__)


class WebSocketAuthError(Exception):
    """Custom exception for WebSocket authentication errors."""

    def __init__(self, message: str, code: int = 4001):
        self.message = message
        self.code = code
        super().__init__(message)


class WebSocketAuthenticator:
    """
    Secure WebSocket authentication using headers or subprotocol.

    This class provides multiple authentication methods to support
    various client environments while avoiding token exposure in URLs.
    """

    @staticmethod
    async def authenticate(websocket: WebSocket) -> Dict[str, Any]:
        """
        Authenticate WebSocket connection using secure methods.

        Attempts authentication in order of preference:
        1. Authorization header (Bearer token) - Most secure
        2. Sec-WebSocket-Protocol header - Browser workaround
        3. Cookie (for session-based auth) - Fallback

        Args:
            websocket: The WebSocket connection to authenticate

        Returns:
            dict: Decoded JWT payload with user info including:
                - sub: User ID
                - exp: Token expiration
                - Additional custom claims

        Raises:
            WebSocketAuthError: If authentication fails with specific error codes:
                - 4001: No authentication token provided
                - 4002: Token has expired
                - 4003: Invalid token format or signature
        """
        token = None
        auth_method = None

        # Method 1: Authorization header (preferred for programmatic clients)
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            auth_method = "bearer_header"
            logger.debug("Using Authorization header for WebSocket auth")

        # Method 2: Sec-WebSocket-Protocol (browser workaround)
        # Format: "auth, <base64_token>" - browser sends this, we respond with "auth"
        if not token:
            protocol_header = websocket.headers.get("sec-websocket-protocol")
            if protocol_header:
                protocols = [p.strip() for p in protocol_header.split(",")]
                if len(protocols) >= 2 and protocols[0] == "auth":
                    token = protocols[1]
                    auth_method = "subprotocol"
                    logger.debug("Using Sec-WebSocket-Protocol for WebSocket auth")

        # Method 3: Cookie fallback (for session-based auth)
        if not token:
            cookies = websocket.cookies
            token = cookies.get("access_token")
            if token:
                auth_method = "cookie"
                logger.debug("Using cookie for WebSocket auth")

        if not token:
            logger.warning("WebSocket authentication failed: No token provided")
            raise WebSocketAuthError(
                "No authentication token provided. Use Authorization header, "
                "Sec-WebSocket-Protocol, or access_token cookie.",
                code=4001,
            )

        try:
            # Validate Supabase JWT (HS256 via shared secret)
            if not settings.SUPABASE_JWT_SECRET:
                logger.error("SUPABASE_JWT_SECRET not configured")
                raise WebSocketAuthError(
                    "Server authentication not configured.", code=4003
                )

            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
            )
            # Map Supabase JWT claims to expected format
            app_metadata = payload.get("app_metadata", {})
            if "role" not in payload:
                payload["role"] = app_metadata.get("role", "USER")

            payload["_auth_method"] = auth_method
            payload["_authenticated_at"] = datetime.now(timezone.utc).isoformat()

            logger.info(
                f"WebSocket authenticated (Supabase): user={payload.get('sub')} method={auth_method}"
            )
            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("WebSocket authentication failed: Token expired")
            raise WebSocketAuthError(
                "Authentication token has expired. Please refresh and reconnect.",
                code=4002,
            )
        except jwt.JWTError as e:
            logger.warning(f"WebSocket authentication failed: Invalid token - {e}")
            raise WebSocketAuthError(
                f"Invalid authentication token: {str(e)}", code=4003
            )

    @staticmethod
    def get_subprotocol_response(websocket: WebSocket) -> Optional[str]:
        """
        Get the subprotocol to respond with if using subprotocol auth.

        When client uses Sec-WebSocket-Protocol for auth, we need to
        respond with the protocol name to complete the handshake.

        Args:
            websocket: The WebSocket connection

        Returns:
            str or None: "auth" if using subprotocol auth, None otherwise
        """
        protocol_header = websocket.headers.get("sec-websocket-protocol")
        if protocol_header and protocol_header.startswith("auth"):
            return "auth"
        return None

    @staticmethod
    async def authenticate_and_accept(
        websocket: WebSocket,
    ) -> tuple[Dict[str, Any], bool]:
        """
        Authenticate and accept WebSocket connection in one operation.

        This is a convenience method that handles authentication and
        connection acceptance, including proper subprotocol response.

        Args:
            websocket: The WebSocket connection

        Returns:
            tuple: (user_payload, accepted) where:
                - user_payload: Decoded JWT with user info
                - accepted: Whether connection was accepted

        Raises:
            WebSocketAuthError: If authentication fails
        """
        # Authenticate first
        payload = await WebSocketAuthenticator.authenticate(websocket)

        # Determine if we need to respond with subprotocol
        subprotocol = WebSocketAuthenticator.get_subprotocol_response(websocket)

        # Accept connection with appropriate response
        if subprotocol:
            await websocket.accept(subprotocol=subprotocol)
        else:
            await websocket.accept()

        return payload, True


# Singleton instance for convenience
websocket_authenticator = WebSocketAuthenticator()
