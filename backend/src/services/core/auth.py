"""
Authentication and authorization for microservices
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import jwt
from fastapi import Depends, HTTPException, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..config.knowledge_graph_config import config

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme
security = HTTPBearer()


class User:
    """User model for authentication"""

    def __init__(
        self, id: str, email: str, tenant_id: str, role: str, permissions: list = None
    ):
        self.id = id
        self.email = email
        self.tenant_id = tenant_id
        self.role = role
        self.permissions = permissions or []

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission"""
        return permission in self.permissions

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role"""
        return self.role == role


async def decode_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode JWT token and return payload"""
    try:
        payload = jwt.decode(
            token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token has expired")
        return None
    except jwt.JWTError as e:
        logger.warning(f"JWT token error: {e}")
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    """Get current user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = await decode_jwt_token(credentials.credentials)
        if payload is None:
            raise credentials_exception

        user_id: str = payload.get("sub")
        email: str = payload.get("email")
        tenant_id: str = payload.get("tenant_id")
        role: str = payload.get("role", "user")
        permissions: list = payload.get("permissions", [])

        if user_id is None or email is None or tenant_id is None:
            raise credentials_exception

        return User(
            id=user_id,
            email=email,
            tenant_id=tenant_id,
            role=role,
            permissions=permissions,
        )

    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise credentials_exception


async def verify_websocket_token(token: str) -> Optional[User]:
    """Verify WebSocket token and return user"""
    try:
        payload = await decode_jwt_token(token)
        if payload is None:
            return None

        user_id: str = payload.get("sub")
        email: str = payload.get("email")
        tenant_id: str = payload.get("tenant_id")
        role: str = payload.get("role", "user")
        permissions: list = payload.get("permissions", [])

        if user_id is None or email is None or tenant_id is None:
            return None

        return User(
            id=user_id,
            email=email,
            tenant_id=tenant_id,
            role=role,
            permissions=permissions,
        )

    except Exception as e:
        logger.error(f"WebSocket authentication error: {e}")
        return None


def require_permission(permission: str):
    """Decorator to require specific permission"""

    def permission_dependency(current_user: User = Depends(get_current_user)):
        if not current_user.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required",
            )
        return current_user

    return permission_dependency


def require_role(role: str):
    """Decorator to require specific role"""

    def role_dependency(current_user: User = Depends(get_current_user)):
        if not current_user.has_role(role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=f"Role '{role}' required"
            )
        return current_user

    return role_dependency


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=config.JWT_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM
    )
    return encoded_jwt


# Token verification for WebSocket connections
async def get_websocket_user(websocket: WebSocket, token: str) -> Optional[User]:
    """Get user from WebSocket token"""
    user = await verify_websocket_token(token)
    if not user:
        await websocket.close(code=4003, reason="Invalid token")
        return None
    return user


# Rate limiting by user
class UserRateLimiter:
    """Simple in-memory rate limiter by user"""

    def __init__(self):
        self.requests = {}

    async def is_allowed(
        self, user_id: str, limit: int = 100, window: int = 60
    ) -> bool:
        """Check if user is allowed to make request"""
        now = datetime.utcnow().timestamp()

        if user_id not in self.requests:
            self.requests[user_id] = []

        # Remove old requests outside the window
        self.requests[user_id] = [
            req_time for req_time in self.requests[user_id] if now - req_time < window
        ]

        # Check if under limit
        if len(self.requests[user_id]) < limit:
            self.requests[user_id].append(now)
            return True

        return False


# Global rate limiter instance
rate_limiter = UserRateLimiter()


async def rate_limit_by_user(current_user: User = Depends(get_current_user)):
    """Rate limiting dependency"""
    if not await rate_limiter.is_allowed(current_user.id, limit=1000, window=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded"
        )
    return current_user
