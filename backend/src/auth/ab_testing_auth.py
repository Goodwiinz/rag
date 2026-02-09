"""
A/B Testing Authentication and Authorization

This module provides comprehensive authentication and authorization for A/B testing services,
including role-based access control, experiment-specific permissions, and API key management
for service-to-service communication.
"""

import asyncio
import functools
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import (
    ARRAY,
    UUID,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Session, relationship

from src.models.ab_testing import Experiment, ExperimentStatus
from src.models.base import BaseModel
from src.models.organization import Organization
from src.models.user import User

from ..cache.cache_keys import get_ab_testing_cache_key
from ..core.config import settings
from ..core.database import get_db
from ..services.rbac_service import rbac_service

# ============================================================================
# PERMISSIONS AND ROLES
# ============================================================================


class ABTestingPermission(str, Enum):
    """A/B Testing specific permissions"""

    # Experiment Management
    EXPERIMENT_CREATE = "ab_testing:experiment:create"
    EXPERIMENT_READ = "ab_testing:experiment:read"
    EXPERIMENT_UPDATE = "ab_testing:experiment:update"
    EXPERIMENT_DELETE = "ab_testing:experiment:delete"
    EXPERIMENT_START = "ab_testing:experiment:start"
    EXPERIMENT_STOP = "ab_testing:experiment:stop"
    EXPERIMENT_ANALYZE = "ab_testing:experiment:analyze"

    # Variant Management
    VARIANT_CREATE = "ab_testing:variant:create"
    VARIANT_READ = "ab_testing:variant:read"
    VARIANT_UPDATE = "ab_testing:variant:update"
    VARIANT_DELETE = "ab_testing:variant:delete"

    # Metrics and Analytics
    METRICS_SUBMIT = "ab_testing:metrics:submit"
    METRICS_READ = "ab_testing:metrics:read"
    METRICS_ANALYZE = "ab_testing:metrics:analyze"

    # Query Routing
    ROUTING_ASSIGN = "ab_testing:routing:assign"
    ROUTING_OVERRIDE = "ab_testing:routing:override"

    # User Segmentation
    SEGMENT_CREATE = "ab_testing:segment:create"
    SEGMENT_READ = "ab_testing:segment:read"
    SEGMENT_UPDATE = "ab_testing:segment:update"
    SEGMENT_DELETE = "ab_testing:segment:delete"

    # Organization-wide permissions
    ORG_ADMIN = "ab_testing:org:admin"
    ORG_ANALYTICS = "ab_testing:org:analytics"

    # System-wide permissions
    SYSTEM_ADMIN = "ab_testing:system:admin"
    SYSTEM_ANALYTICS = "ab_testing:system:analytics"


class ServiceRole(str, Enum):
    """Service roles for API key authentication"""

    QUERY_ROUTER = "query_router"
    METRICS_COLLECTOR = "metrics_collector"
    ANALYTICS_SERVICE = "analytics_service"
    INTERNAL_SERVICE = "internal_service"


# ============================================================================
# AUTHENTICATION SCHEMES
# ============================================================================

# User authentication via JWT tokens
user_auth_scheme = HTTPBearer(auto_error=False)

# Service authentication via API keys
service_auth_scheme = HTTPBearer(auto_error=False)


# ============================================================================
# USER AUTHENTICATION AND AUTHORIZATION
# ============================================================================


async def get_current_user_from_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(user_auth_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Authenticate user from JWT token

    Args:
        credentials: Bearer token credentials
        db: Database session

    Returns:
        Authenticated user or None if token invalid

    Raises:
        HTTPException: If authentication fails
    """
    if not credentials:
        return None

    try:
        # Decode JWT token
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )

        user_id: str = payload.get("sub")
        organization_id: str = payload.get("org_id")
        exp: int = payload.get("exp")

        if not user_id or not organization_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload"
            )

        # Check token expiration
        if exp and datetime.fromtimestamp(exp, timezone.utc) < datetime.now(
            timezone.utc
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired"
            )

        # Get user from database
        user = (
            db.query(User)
            .filter(
                User.id == uuid.UUID(user_id),
                User.organization_id == uuid.UUID(organization_id),
                User.is_active == True,
            )
            .first()
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        return user

    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication error: {str(e)}",
        )


async def get_current_user_or_service(
    user_credentials: Optional[HTTPAuthorizationCredentials] = Security(
        user_auth_scheme
    ),
    service_credentials: Optional[HTTPAuthorizationCredentials] = Security(
        service_auth_scheme
    ),
    db: Session = Depends(get_db),
) -> Union[User, Dict[str, Any]]:
    """
    Authenticate either user or service

    Returns either an authenticated user or service context.
    Used for endpoints that can be called by both users and services.

    Args:
        user_credentials: User JWT token
        service_credentials: Service API key
        db: Database session

    Returns:
        User object or service context dictionary

    Raises:
        HTTPException: If neither user nor service can be authenticated
    """
    # Try user authentication first
    if user_credentials:
        user = await get_current_user_from_token(user_credentials, db)
        if user:
            return user

    # Try service authentication
    if service_credentials:
        service_context = await authenticate_service(
            service_credentials.credentials, db
        )
        if service_context:
            return service_context

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Valid user token or service API key required",
    )


# ============================================================================
# SERVICE AUTHENTICATION
# ============================================================================


async def authenticate_service(api_key: str, db: Session) -> Optional[Dict[str, Any]]:
    """
    Authenticate service using API key

    Args:
        api_key: Service API key
        db: Database session

    Returns:
        Service context or None if authentication fails
    """
    try:
        # Hash the provided API key for comparison
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        # Look up API key in database (assuming api_keys table)
        # This would be implemented based on your API key storage strategy
        api_key_record = (
            db.query(ApiKey)
            .filter(ApiKey.key_hash == api_key_hash, ApiKey.is_active == True)
            .first()
        )

        if not api_key_record:
            return None

        # Check if API key has expired
        if api_key_record.expires_at and api_key_record.expires_at < datetime.now(
            timezone.utc
        ):
            return None

        # Update last used timestamp
        api_key_record.last_used_at = datetime.now(timezone.utc)
        db.commit()

        return {
            "service_id": api_key_record.service_id,
            "service_role": api_key_record.service_role,
            "organization_id": api_key_record.organization_id,
            "permissions": api_key_record.permissions,
            "rate_limit": api_key_record.rate_limit,
        }

    except Exception:
        return None


# ============================================================================
# PERMISSION DECORATORS
# ============================================================================


def require_permission(permission: ABTestingPermission):
    """
    Decorator to require specific permission for endpoint access

    Args:
        permission: Required permission

    Returns:
        Decorator function
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Extract user/service from kwargs
            current_user = kwargs.get("current_user")

            if isinstance(current_user, User):
                # User authentication
                if not await rbac_service.user_has_permission(
                    user_id=current_user.id,
                    permission=permission,
                    organization_id=current_user.organization_id,
                    db=kwargs.get("db"),
                ):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Insufficient permissions. Required: {permission}",
                    )
            else:
                # Service authentication
                service_context = current_user
                if not service_context or permission not in service_context.get(
                    "permissions", []
                ):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Service lacks required permission: {permission}",
                    )

            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Extract user/service from kwargs
            current_user = kwargs.get("current_user")

            if isinstance(current_user, User):
                # User authentication - for sync functions, we need to handle this differently
                # This is a limitation - sync functions can't use async RBAC service
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Sync functions not supported for permission checking",
                )
            else:
                # Service authentication
                service_context = current_user
                if not service_context or permission not in service_context.get(
                    "permissions", []
                ):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Service lacks required permission: {permission}",
                    )

            return func(*args, **kwargs)

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def require_experiment_access(
    experiment_id: uuid.UUID, required_permissions: List[ABTestingPermission]
):
    """
    Decorator to require specific permissions for a particular experiment

    Args:
        experiment_id: Experiment ID
        required_permissions: List of required permissions

    Returns:
        Decorator function
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")
            db = kwargs.get("db")

            # Get experiment
            experiment = (
                db.query(Experiment)
                .filter(Experiment.id == experiment_id, Experiment.is_deleted == False)
                .first()
            )

            if not experiment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found"
                )

            if isinstance(current_user, User):
                # Check organization access
                if current_user.organization_id != experiment.organization_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied to experiment",
                    )

                # Check user permissions for this experiment
                for permission in required_permissions:
                    has_permission = await rbac_service.user_has_experiment_permission(
                        user_id=current_user.id,
                        experiment_id=experiment_id,
                        permission=permission,
                        db=db,
                    )

                    if not has_permission:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Insufficient permissions for experiment. Required: {permission}",
                        )

            # Add experiment to kwargs for use in endpoint
            kwargs["experiment"] = experiment

            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")
            db = kwargs.get("db")

            # Get experiment
            experiment = (
                db.query(Experiment)
                .filter(Experiment.id == experiment_id, Experiment.is_deleted == False)
                .first()
            )

            if not experiment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found"
                )

            if isinstance(current_user, User):
                # Check organization access
                if current_user.organization_id != experiment.organization_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied to experiment",
                    )

                # Sync functions can't use async RBAC service
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Sync functions not supported for experiment permission checking",
                )

            # Add experiment to kwargs for use in endpoint
            kwargs["experiment"] = experiment

            return func(*args, **kwargs)

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# ============================================================================
# RATE LIMITING
# ============================================================================


class ABTestingRateLimiter:
    """Rate limiting for A/B testing endpoints"""

    def __init__(self, redis_client):
        self.redis_client = redis_client

    async def check_rate_limit(
        self, identifier: str, limit: int, window_seconds: int, endpoint: str
    ) -> bool:
        """
        Check if identifier exceeds rate limit

        Args:
            identifier: User ID, service ID, or IP address
            limit: Maximum requests allowed
            window_seconds: Time window in seconds
            endpoint: Endpoint identifier

        Returns:
            True if within rate limit, False otherwise
        """
        key = f"ab_testing_rate_limit:{endpoint}:{identifier}"

        try:
            # Get current count
            current_count = await self.redis_client.get(key)
            if current_count is None:
                # First request in window
                await self.redis_client.setex(key, window_seconds, 1)
                return True

            current_count = int(current_count)
            if current_count >= limit:
                return False

            # Increment counter
            await self.redis_client.incr(key)
            return True

        except Exception:
            # Fail open - allow request if Redis is unavailable
            return True


# ============================================================================
# SECURITY DEPENDENCIES
# ============================================================================


async def get_current_user_with_permissions(
    credentials: HTTPAuthorizationCredentials = Security(user_auth_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Get authenticated user and verify they have basic A/B testing permissions
    """
    user = await get_current_user_from_token(credentials, db)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )

    # Check if user has any A/B testing permissions
    has_permissions = await rbac_service.user_has_any_ab_testing_permission(
        user_id=user.id, organization_id=user.organization_id, db=db
    )

    if not has_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No A/B testing permissions assigned",
        )

    return user


async def get_experiment_manager_user(
    credentials: HTTPAuthorizationCredentials = Security(user_auth_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Get authenticated user with experiment management permissions
    """
    user = await get_current_user_from_token(credentials, db)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )

    # Check experiment management permissions
    required_permissions = [
        ABTestingPermission.EXPERIMENT_READ,
        ABTestingPermission.EXPERIMENT_CREATE,
        ABTestingPermission.EXPERIMENT_UPDATE,
    ]

    has_any_permission = await rbac_service.user_has_any_permission(
        user_id=user.id,
        permissions=required_permissions,
        organization_id=user.organization_id,
        db=db,
    )

    if not has_any_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Experiment management permissions required",
        )

    return user


async def get_analytics_user(
    credentials: HTTPAuthorizationCredentials = Security(user_auth_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Get authenticated user with analytics permissions
    """
    user = await get_current_user_from_token(credentials, db)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )

    # Check analytics permissions
    analytics_permissions = [
        ABTestingPermission.METRICS_READ,
        ABTestingPermission.METRICS_ANALYZE,
        ABTestingPermission.ORG_ANALYTICS,
        ABTestingPermission.SYSTEM_ANALYTICS,
    ]

    has_analytics_permission = await rbac_service.user_has_any_permission(
        user_id=user.id,
        permissions=analytics_permissions,
        organization_id=user.organization_id,
        db=db,
    )

    if not has_analytics_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Analytics permissions required",
        )

    return user


# ============================================================================
# API KEY MANAGEMENT
# ============================================================================


class ApiKey(BaseModel):
    """API Key model for service authentication"""

    __tablename__ = "ab_testing_api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    service_id = Column(String(255), nullable=False, index=True)
    service_role = Column(Enum(ServiceRole), nullable=False)

    # Security
    key_hash = Column(String(64), nullable=False, unique=True, index=True)
    key_prefix = Column(
        String(20), nullable=False
    )  # First few characters for identification

    # Permissions
    permissions = Column(ARRAY(String), nullable=False)

    # Access control
    organization_id = Column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True
    )
    allowed_endpoints = Column(ARRAY(String), nullable=True)

    # Rate limiting
    rate_limit = Column(Integer, default=1000)  # Requests per hour

    # Lifecycle
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    created_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Relationships
    organization = relationship("Organization")
    created_by_user = relationship("User")


def generate_api_key() -> Tuple[str, str, str]:
    """
    Generate a new API key

    Returns:
        Tuple of (api_key, key_hash, key_prefix)
    """
    # Generate secure random key
    api_key = f"ab_test_{secrets.token_urlsafe(32)}"

    # Create hash for storage
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    # Store prefix for identification (first 8 characters)
    key_prefix = api_key[:8]

    return api_key, key_hash, key_prefix


# ============================================================================
# SECURITY MIDDLEWARE
# ============================================================================


class ABTestingSecurityMiddleware:
    """Security middleware for A/B testing endpoints"""

    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.rate_limiter = ABTestingRateLimiter(redis_client)

    async def __call__(self, request, call_next):
        """
        Security middleware for request processing

        Args:
            request: FastAPI request
            call_next: Next middleware in chain

        Returns:
            Response from next middleware
        """
        # Log security-relevant information
        await self.log_security_event(request)

        # Check for suspicious activity
        if await self.detect_suspicious_activity(request):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
            )

        # Process request
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"

        return response

    async def log_security_event(self, request):
        """Log security-relevant events"""
        try:
            event_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "method": request.method,
                "url": str(request.url),
                "client_ip": request.client.host,
                "user_agent": request.headers.get("user-agent"),
                "endpoint": request.url.path,
            }

            # Log to security monitoring system
            await self.redis_client.lpush(
                "ab_testing_security_events", json.dumps(event_data)
            )

            # Keep only last 10000 events
            await self.redis_client.ltrim("ab_testing_security_events", 0, 9999)

        except Exception:
            # Don't fail the request if logging fails
            pass

    async def detect_suspicious_activity(self, request) -> bool:
        """Detect suspicious activity patterns"""
        try:
            client_ip = request.client.host
            endpoint = request.url.path

            # Check for excessive requests from single IP
            key = f"ab_testing_ip_rate:{client_ip}"
            request_count = await self.redis_client.incr(key)

            if request_count == 1:
                await self.redis_client.expire(key, 300)  # 5 minutes

            # Block if more than 1000 requests in 5 minutes
            if request_count > 1000:
                return True

            return False

        except Exception:
            return False


# ============================================================================
# INITIALIZATION
# ============================================================================


def create_default_permissions():
    """Create default A/B testing permissions in the system"""
    permissions = [
        # Experiment permissions
        {
            "name": ABTestingPermission.EXPERIMENT_CREATE,
            "description": "Create A/B testing experiments",
        },
        {
            "name": ABTestingPermission.EXPERIMENT_READ,
            "description": "Read A/B testing experiments",
        },
        {
            "name": ABTestingPermission.EXPERIMENT_UPDATE,
            "description": "Update A/B testing experiments",
        },
        {
            "name": ABTestingPermission.EXPERIMENT_DELETE,
            "description": "Delete A/B testing experiments",
        },
        {
            "name": ABTestingPermission.EXPERIMENT_START,
            "description": "Start A/B testing experiments",
        },
        {
            "name": ABTestingPermission.EXPERIMENT_STOP,
            "description": "Stop A/B testing experiments",
        },
        {
            "name": ABTestingPermission.EXPERIMENT_ANALYZE,
            "description": "Analyze A/B testing results",
        },
        # Variant permissions
        {
            "name": ABTestingPermission.VARIANT_CREATE,
            "description": "Create experiment variants",
        },
        {
            "name": ABTestingPermission.VARIANT_READ,
            "description": "Read experiment variants",
        },
        {
            "name": ABTestingPermission.VARIANT_UPDATE,
            "description": "Update experiment variants",
        },
        {
            "name": ABTestingPermission.VARIANT_DELETE,
            "description": "Delete experiment variants",
        },
        # Metrics permissions
        {
            "name": ABTestingPermission.METRICS_SUBMIT,
            "description": "Submit experiment metrics",
        },
        {
            "name": ABTestingPermission.METRICS_READ,
            "description": "Read experiment metrics",
        },
        {
            "name": ABTestingPermission.METRICS_ANALYZE,
            "description": "Analyze experiment metrics",
        },
        # Routing permissions
        {
            "name": ABTestingPermission.ROUTING_ASSIGN,
            "description": "Assign experiment variants",
        },
        {
            "name": ABTestingPermission.ROUTING_OVERRIDE,
            "description": "Override experiment assignments",
        },
        # Segment permissions
        {
            "name": ABTestingPermission.SEGMENT_CREATE,
            "description": "Create user segments",
        },
        {"name": ABTestingPermission.SEGMENT_READ, "description": "Read user segments"},
        {
            "name": ABTestingPermission.SEGMENT_UPDATE,
            "description": "Update user segments",
        },
        {
            "name": ABTestingPermission.SEGMENT_DELETE,
            "description": "Delete user segments",
        },
        # Organization permissions
        {
            "name": ABTestingPermission.ORG_ADMIN,
            "description": "Organization A/B testing administration",
        },
        {
            "name": ABTestingPermission.ORG_ANALYTICS,
            "description": "Organization analytics access",
        },
        # System permissions
        {
            "name": ABTestingPermission.SYSTEM_ADMIN,
            "description": "System-wide A/B testing administration",
        },
        {
            "name": ABTestingPermission.SYSTEM_ANALYTICS,
            "description": "System-wide analytics access",
        },
    ]

    return permissions


def create_default_roles():
    """Create default A/B testing roles"""
    roles = [
        {
            "name": "AB Testing Analyst",
            "permissions": [
                ABTestingPermission.EXPERIMENT_READ,
                ABTestingPermission.VARIANT_READ,
                ABTestingPermission.METRICS_READ,
                ABTestingPermission.METRICS_ANALYZE,
                ABTestingPermission.SEGMENT_READ,
                ABTestingPermission.ORG_ANALYTICS,
            ],
        },
        {
            "name": "AB Testing Manager",
            "permissions": [
                ABTestingPermission.EXPERIMENT_CREATE,
                ABTestingPermission.EXPERIMENT_READ,
                ABTestingPermission.EXPERIMENT_UPDATE,
                ABTestingPermission.EXPERIMENT_START,
                ABTestingPermission.EXPERIMENT_STOP,
                ABTestingPermission.EXPERIMENT_ANALYZE,
                ABTestingPermission.VARIANT_CREATE,
                ABTestingPermission.VARIANT_READ,
                ABTestingPermission.VARIANT_UPDATE,
                ABTestingPermission.VARIANT_DELETE,
                ABTestingPermission.METRICS_READ,
                ABTestingPermission.METRICS_ANALYZE,
                ABTestingPermission.SEGMENT_CREATE,
                ABTestingPermission.SEGMENT_READ,
                ABTestingPermission.SEGMENT_UPDATE,
                ABTestingPermission.SEGMENT_DELETE,
                ABTestingPermission.ORG_ANALYTICS,
            ],
        },
        {
            "name": "AB Testing Admin",
            "permissions": [
                ABTestingPermission.EXPERIMENT_CREATE,
                ABTestingPermission.EXPERIMENT_READ,
                ABTestingPermission.EXPERIMENT_UPDATE,
                ABTestingPermission.EXPERIMENT_DELETE,
                ABTestingPermission.EXPERIMENT_START,
                ABTestingPermission.EXPERIMENT_STOP,
                ABTestingPermission.EXPERIMENT_ANALYZE,
                ABTestingPermission.VARIANT_CREATE,
                ABTestingPermission.VARIANT_READ,
                ABTestingPermission.VARIANT_UPDATE,
                ABTestingPermission.VARIANT_DELETE,
                ABTestingPermission.METRICS_SUBMIT,
                ABTestingPermission.METRICS_READ,
                ABTestingPermission.METRICS_ANALYZE,
                ABTestingPermission.ROUTING_ASSIGN,
                ABTestingPermission.ROUTING_OVERRIDE,
                ABTestingPermission.SEGMENT_CREATE,
                ABTestingPermission.SEGMENT_READ,
                ABTestingPermission.SEGMENT_UPDATE,
                ABTestingPermission.SEGMENT_DELETE,
                ABTestingPermission.ORG_ADMIN,
                ABTestingPermission.ORG_ANALYTICS,
            ],
        },
    ]

    return roles
