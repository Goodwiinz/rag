"""
WebSocket Authentication and Authorization Service
Handles JWT validation, permission checking, and connection security
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple

import jwt
from fastapi import HTTPException, WebSocket, status
from jose import JWTError
from jose import jwt as jose_jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.security import get_client_ip
from src.core.database import get_async_session
from src.models.organization import Organization
from src.models.rbac import Permission, Role, UserRole
from src.models.user import User

logger = logging.getLogger(__name__)


class WebSocketAuthError(Exception):
    """WebSocket authentication error"""

    def __init__(self, message: str, error_code: str = "AUTH_ERROR"):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class WebSocketAuthenticator:
    """Handles WebSocket connection authentication and authorization"""

    def __init__(self):
        self.jwt_secret = settings.JWT_SECRET_KEY
        self.jwt_algorithm = settings.JWT_ALGORITHM
        self.token_expiry_minutes = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expiry_days = settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS

        # Connection tracking for security
        self.connection_attempts: Dict[str, List[float]] = {}
        self.blocked_ips: Dict[str, float] = {}

        # Rate limiting
        self.max_attempts_per_minute = 10
        self.block_duration_minutes = 5

    async def authenticate_websocket_connection(
        self,
        websocket: WebSocket,
        token: Optional[str] = None,
        organization_id: Optional[str] = None,
        connection_type: str = "document_updates",
        **kwargs,
    ) -> Tuple[User, Organization]:
        """
        Authenticate and authorize WebSocket connection

        Returns:
            Tuple[User, Organization]: Authenticated user and organization
        """
        try:
            # Validate input parameters
            if not token:
                raise WebSocketAuthError(
                    "Missing authentication token", "MISSING_TOKEN"
                )

            if not organization_id:
                raise WebSocketAuthError("Missing organization ID", "MISSING_ORG_ID")

            # Rate limiting check
            client_ip = self._get_client_ip(websocket)
            self._check_rate_limit(client_ip)

            # Validate JWT token
            user_id = self._validate_jwt_token(token)

            # Get database session
            async for session in get_async_session():
                try:
                    # Validate user exists and is active
                    user = await self._validate_user(session, user_id)

                    # Validate organization access
                    organization = await self._validate_organization_access(
                        session, user, organization_id
                    )

                    # Check WebSocket-specific permissions
                    await self._check_websocket_permissions(
                        session, user, organization, connection_type
                    )

                    # Record successful authentication
                    self._record_successful_attempt(client_ip)

                    logger.info(
                        f"WebSocket authentication successful: user={user_id}, "
                        f"org={organization_id}, type={connection_type}"
                    )

                    return user, organization

                finally:
                    await session.close()

        except WebSocketAuthError:
            # Record failed attempt
            client_ip = self._get_client_ip(websocket)
            self._record_failed_attempt(client_ip)
            raise
        except Exception as e:
            logger.error(f"WebSocket authentication error: {e}")
            raise WebSocketAuthError("Authentication failed", "INTERNAL_ERROR")

    def _get_client_ip(self, websocket: WebSocket) -> str:
        """Extract client IP from WebSocket connection"""
        headers = websocket.headers if hasattr(websocket, 'headers') else None
        client_host = websocket.client.host if websocket.client else None
        return get_client_ip(headers, client_host)

    def _check_rate_limit(self, client_ip: str):
        """Check rate limiting for connection attempts"""
        now = time.time()

        # Check if IP is blocked
        if client_ip in self.blocked_ips:
            block_expiry = self.blocked_ips[client_ip]
            if now < block_expiry:
                raise WebSocketAuthError(
                    "Too many connection attempts. Please try again later.",
                    "RATE_LIMITED",
                )
            else:
                del self.blocked_ips[client_ip]

        # Check recent attempts
        recent_attempts = self.connection_attempts.get(client_ip, [])
        # Remove attempts older than 1 minute
        recent_attempts = [t for t in recent_attempts if now - t < 60]

        if len(recent_attempts) >= self.max_attempts_per_minute:
            # Block the IP
            self.blocked_ips[client_ip] = now + (self.block_duration_minutes * 60)
            raise WebSocketAuthError(
                "Too many connection attempts. Please try again later.", "RATE_LIMITED"
            )

    def _record_failed_attempt(self, client_ip: str):
        """Record failed authentication attempt"""
        now = time.time()
        if client_ip not in self.connection_attempts:
            self.connection_attempts[client_ip] = []
        self.connection_attempts[client_ip].append(now)

    def _record_successful_attempt(self, client_ip: str):
        """Record successful authentication (reset rate limiting)"""
        if client_ip in self.connection_attempts:
            del self.connection_attempts[client_ip]

    def _validate_jwt_token(self, token: str) -> str:
        """Validate JWT token and return user ID"""
        try:
            # Remove "Bearer " prefix if present
            if token.startswith("Bearer "):
                token = token[7:]

            payload = jose_jwt.decode(
                token, self.jwt_secret, algorithms=[self.jwt_algorithm]
            )

            user_id = payload.get("sub")
            if not user_id:
                raise WebSocketAuthError("Invalid token payload", "INVALID_TOKEN")

            # Check token expiration
            exp = payload.get("exp")
            if exp:
                exp_datetime = datetime.fromtimestamp(exp, timezone.utc)
                if datetime.now(timezone.utc) > exp_datetime:
                    raise WebSocketAuthError("Token expired", "TOKEN_EXPIRED")

            # Check token type (should be access token)
            token_type = payload.get("token_type")
            if token_type != "access":
                raise WebSocketAuthError("Invalid token type", "INVALID_TOKEN_TYPE")

            return user_id

        except JWTError as e:
            logger.warning(f"JWT validation failed: {e}")
            raise WebSocketAuthError("Invalid token", "INVALID_TOKEN")

    async def _validate_user(self, session: AsyncSession, user_id: str) -> User:
        """Validate user exists and is active"""
        try:
            result = await session.execute(
                select(User).where(
                    User.id == user_id, User.is_active == True, User.is_deleted == False
                )
            )
            user = result.scalar_one_or_none()

            if not user:
                raise WebSocketAuthError("User not found or inactive", "USER_NOT_FOUND")

            # Check if user is locked due to security issues
            if user.is_locked:
                raise WebSocketAuthError("User account is locked", "USER_LOCKED")

            # Update last activity
            user.last_login_at = datetime.now(timezone.utc)
            await session.commit()

            return user

        except WebSocketAuthError:
            raise
        except Exception as e:
            logger.error(f"User validation error: {e}")
            raise WebSocketAuthError("User validation failed", "USER_VALIDATION_ERROR")

    async def _validate_organization_access(
        self, session: AsyncSession, user: User, organization_id: str
    ) -> Organization:
        """Validate user has access to the specified organization"""
        try:
            # Get organization
            result = await session.execute(
                select(Organization).where(
                    Organization.id == organization_id,
                    Organization.is_active == True,
                    Organization.is_deleted == False,
                )
            )
            organization = result.scalar_one_or_none()

            if not organization:
                raise WebSocketAuthError("Organization not found", "ORG_NOT_FOUND")

            # Check if user is a member of the organization
            result = await session.execute(
                select(UserRole).where(
                    UserRole.user_id == user.id,
                    UserRole.organization_id == organization_id,
                    UserRole.is_active == True,
                )
            )
            user_role = result.scalar_one_or_none()

            if not user_role:
                raise WebSocketAuthError(
                    "Access denied to organization", "ORG_ACCESS_DENIED"
                )

            # Check if role is active
            if not user_role.is_active:
                raise WebSocketAuthError("User role is inactive", "ROLE_INACTIVE")

            return organization

        except WebSocketAuthError:
            raise
        except Exception as e:
            logger.error(f"Organization validation error: {e}")
            raise WebSocketAuthError(
                "Organization validation failed", "ORG_VALIDATION_ERROR"
            )

    async def _check_websocket_permissions(
        self,
        session: AsyncSession,
        user: User,
        organization: Organization,
        connection_type: str,
    ):
        """Check user has WebSocket-specific permissions"""
        try:
            # Define required permissions for different connection types
            permission_mapping = {
                "document_updates": ["websocket:document_updates"],
                "system_status": ["websocket:system_status"],
                "search_results": ["websocket:search_results"],
                "all": ["websocket:*"],
            }

            required_permissions = permission_mapping.get(
                connection_type, permission_mapping["document_updates"]
            )

            # Get user's permissions
            user_permissions = await self._get_user_permissions(
                session, user.id, organization.id
            )

            # Check if user has required permissions
            has_permission = any(
                perm in user_permissions for perm in required_permissions
            )

            if not has_permission:
                # For system-wide connections, check if user is admin
                if connection_type == "system_status":
                    is_admin = await self._is_organization_admin(
                        session, user.id, organization.id
                    )
                    if not is_admin:
                        raise WebSocketAuthError(
                            "Insufficient permissions for WebSocket connection",
                            "INSUFFICIENT_PERMISSIONS",
                        )
                else:
                    raise WebSocketAuthError(
                        "Insufficient permissions for WebSocket connection",
                        "INSUFFICIENT_PERMISSIONS",
                    )

        except WebSocketAuthError:
            raise
        except Exception as e:
            logger.error(f"Permission check error: {e}")
            raise WebSocketAuthError(
                "Permission check failed", "PERMISSION_CHECK_ERROR"
            )

    async def _get_user_permissions(
        self, session: AsyncSession, user_id: str, organization_id: str
    ) -> Set[str]:
        """Get all permissions for a user in an organization"""
        try:
            # Query user permissions through roles
            query = (
                select(Permission.name)
                .join(Role.permissions)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(
                    UserRole.user_id == user_id,
                    UserRole.organization_id == organization_id,
                    UserRole.is_active == True,
                    Permission.is_active == True,
                )
            )

            result = await session.execute(query)
            permissions = set(row[0] for row in result.all())

            return permissions

        except Exception as e:
            logger.error(f"Error getting user permissions: {e}")
            return set()

    async def _is_organization_admin(
        self, session: AsyncSession, user_id: str, organization_id: str
    ) -> bool:
        """Check if user is an administrator of the organization"""
        try:
            result = await session.execute(
                select(UserRole)
                .join(Role)
                .where(
                    UserRole.user_id == user_id,
                    UserRole.organization_id == organization_id,
                    UserRole.is_active == True,
                    Role.name.in_(["admin", "administrator", "owner"]),
                )
            )
            return result.scalar_one_or_none() is not None

        except Exception as e:
            logger.error(f"Error checking admin status: {e}")
            return False

    def generate_connection_token(
        self,
        user_id: str,
        organization_id: str,
        connection_type: str = "document_updates",
    ) -> str:
        """Generate short-lived WebSocket connection token"""
        try:
            now = datetime.now(timezone.utc)
            exp = now + timedelta(minutes=15)  # 15 minute expiry for connection tokens

            payload = {
                "sub": user_id,
                "org": organization_id,
                "connection_type": connection_type,
                "token_type": "websocket",
                "iat": now,
                "exp": exp,
            }

            token = jose_jwt.encode(
                payload, self.jwt_secret, algorithm=self.jwt_algorithm
            )

            return token

        except Exception as e:
            logger.error(f"Error generating connection token: {e}")
            raise WebSocketAuthError(
                "Token generation failed", "TOKEN_GENERATION_ERROR"
            )

    def validate_connection_token(
        self, token: str, expected_connection_type: Optional[str] = None
    ) -> Dict[str, str]:
        """Validate WebSocket connection token"""
        try:
            payload = jose_jwt.decode(
                token, self.jwt_secret, algorithms=[self.jwt_algorithm]
            )

            # Validate token type
            if payload.get("token_type") != "websocket":
                raise WebSocketAuthError("Invalid token type", "INVALID_TOKEN_TYPE")

            # Validate connection type if specified
            if expected_connection_type:
                actual_type = payload.get("connection_type")
                if actual_type != expected_connection_type:
                    raise WebSocketAuthError(
                        "Invalid connection type", "INVALID_CONNECTION_TYPE"
                    )

            return {
                "user_id": payload.get("sub"),
                "organization_id": payload.get("org"),
                "connection_type": payload.get("connection_type"),
            }

        except JWTError as e:
            logger.warning(f"Connection token validation failed: {e}")
            raise WebSocketAuthError("Invalid connection token", "INVALID_TOKEN")


class WebSocketAuthorizer:
    """Handles authorization checks for WebSocket operations"""

    def __init__(self):
        self.authenticator = WebSocketAuthenticator()

    async def can_access_document(
        self, user: User, organization: Organization, document_id: str
    ) -> bool:
        """Check if user can access a specific document"""
        try:
            # Super admin can access all documents
            if user.is_super_admin:
                return True

            # Organization admin can access all documents in organization
            if await self._is_organization_admin(user.id, organization.id):
                return True

            # Check document ownership or explicit access
            async for session in get_async_session():
                try:
                    from src.models.document import Document

                    result = await session.execute(
                        select(Document).where(
                            Document.id == document_id,
                            Document.organization_id == organization.id,
                            Document.is_deleted == False,
                        )
                    )
                    document = result.scalar_one_or_none()

                    if not document:
                        return False

                    # Check if user uploaded the document
                    if document.uploaded_by_user_id == user.id:
                        return True

                    # Check if document is public
                    if document.is_public:
                        return True

                    # Check if user has explicit access (would need DocumentAccess model)
                    # This would be implemented based on your access control model

                    return False

                finally:
                    await session.close()

        except Exception as e:
            logger.error(f"Error checking document access: {e}")
            return False

    async def can_subscribe_to_document_updates(
        self, user: User, organization: Organization, document_id: str
    ) -> bool:
        """Check if user can subscribe to document updates"""
        return await self.can_access_document(user, organization, document_id)

    async def can_receive_system_notifications(
        self, user: User, organization: Organization
    ) -> bool:
        """Check if user can receive system notifications"""
        try:
            # Check if user has websocket:system_notifications permission
            async for session in get_async_session():
                try:
                    permissions = await self.authenticator._get_user_permissions(
                        session, user.id, organization.id
                    )

                    return any(
                        perm in permissions
                        for perm in [
                            "websocket:system_notifications",
                            "websocket:*",
                            "system:*",
                        ]
                    )

                finally:
                    await session.close()

        except Exception as e:
            logger.error(f"Error checking notification permissions: {e}")
            return False

    async def get_accessible_documents(
        self, user: User, organization: Organization
    ) -> List[str]:
        """Get list of document IDs user can access"""
        try:
            async for session in get_async_session():
                try:
                    from src.models.document import Document

                    query = select(Document.id).where(
                        Document.organization_id == organization.id,
                        Document.is_deleted == False,
                    )

                    # Non-admin users only see their own or public documents
                    if (
                        not user.is_super_admin
                        and not await self._is_organization_admin(
                            user.id, organization.id
                        )
                    ):
                        query = query.where(
                            (Document.uploaded_by_user_id == user.id)
                            | (Document.is_public == True)
                        )

                    result = await session.execute(query)
                    return [row[0] for row in result.all()]

                finally:
                    await session.close()

        except Exception as e:
            logger.error(f"Error getting accessible documents: {e}")
            return []


# Global instances
websocket_authenticator = WebSocketAuthenticator()
websocket_authorizer = WebSocketAuthorizer()
