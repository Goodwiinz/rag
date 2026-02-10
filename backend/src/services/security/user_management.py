"""
User Management Service - Port 8007
Handles authentication, authorization, user management, and RBAC
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

# from passlib.context import CryptContext  # Removed
import redis.asyncio as redis
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database import get_db
from src.core.security import get_password_hash, verify_password  # Imported
from src.models.organization import Organization, StorageTier
from src.models.user import User
from src.models.user import UserRole as UserRoleEnum
from src.shared.exceptions import (
    AuthenticationError,
    AuthorizationError,
    BaseCustomException,
    ConflictError,
    NotFoundError,
    ValidationError,
    handle_exceptions,
)
from src.shared.schemas import (
    BaseResponse,
    CreateUserRequest,
    ErrorResponse,
    HealthCheckResponse,
    LoginRequest,
    LoginResponse,
    OrganizationContext,
    TokenRequest,
    TokenResponse,
    UpdateUserRequest,
    UserDetailResponse,
    UserResponse,
    UserRole,
)
from src.shared.utils import (
    CorrelationIdMiddleware,
    EventLogger,
    HealthChecker,
    MetricsCollector,
    RateLimiter,
    generate_cache_key,
    retry_async,
)

# Configuration
USER_SERVICE_CONFIG = {
    "service_name": "user-management",
    "version": "1.0.0",
    "port": 8007,
    "host": "0.0.0.0",
    "password_min_length": 8,
    "max_login_attempts": 5,
    "account_lockout_minutes": 15,
    "session_timeout_hours": 24,
    "refresh_token_days": 30,
}

# Initialize FastAPI app
app = FastAPI(
    title="User Management Service",
    version=USER_SERVICE_CONFIG["version"],
    description="Service for user authentication, authorization, and management",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(CorrelationIdMiddleware)

# Initialize components
event_logger = EventLogger(USER_SERVICE_CONFIG["service_name"])
health_checker = HealthChecker(USER_SERVICE_CONFIG["service_name"])
metrics = MetricsCollector(USER_SERVICE_CONFIG["service_name"])
rate_limiter = RateLimiter(settings.REDIS_URL)
cache = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

# Password hashing
# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")  # Removed
security = HTTPBearer()


class AuthService:
    """Authentication service"""

    def __init__(self):
        self.secret_key = settings.JWT_SECRET_KEY
        self.algorithm = settings.JWT_ALGORITHM
        self.access_token_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = USER_SERVICE_CONFIG["refresh_token_days"]

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return verify_password(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        """Generate password hash"""
        return get_password_hash(password)

    def validate_password_strength(self, password: str) -> tuple[bool, List[str]]:
        """Validate password strength"""
        errors = []

        if len(password) < USER_SERVICE_CONFIG["password_min_length"]:
            errors.append(
                f"Password must be at least {USER_SERVICE_CONFIG['password_min_length']} characters long"
            )

        if not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")

        if not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")

        if not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one digit")

        # Special characters (optional but recommended)
        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        if not any(c in special_chars for c in password):
            errors.append("Password must contain at least one special character")

        return len(errors) == 0, errors

    async def create_access_token(
        self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create JWT access token"""
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=self.access_token_expire_minutes
            )

        to_encode.update(
            {"exp": expire, "iat": datetime.now(timezone.utc), "type": "access"}
        )

        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    async def create_refresh_token(self, user_id: str, organization_id: str) -> str:
        """Create JWT refresh token"""
        expire = datetime.now(timezone.utc) + timedelta(
            days=self.refresh_token_expire_days
        )

        to_encode = {
            "sub": user_id,
            "organization_id": organization_id,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "refresh",
            "jti": str(uuid.uuid4()),  # Unique identifier for refresh token
        }

        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

        # Store refresh token in Redis for revocation capability
        await cache.setex(
            f"refresh_token:{to_encode['jti']}",
            timedelta(days=self.refresh_token_expire_days).total_seconds(),
            str(user_id),
        )

        return encoded_jwt

    async def verify_token(
        self, token: str, token_type: str = "access"
    ) -> Dict[str, Any]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            # Check token type
            if payload.get("type") != token_type:
                raise AuthenticationError(f"Invalid token type: expected {token_type}")

            # For refresh tokens, check if it's revoked
            if token_type == "refresh":
                jti = payload.get("jti")
                if jti and not await cache.exists(f"refresh_token:{jti}"):
                    raise AuthenticationError("Refresh token has been revoked")

            return payload

        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except jwt.JWTError as e:
            raise AuthenticationError(f"Invalid token: {str(e)}")

    async def revoke_refresh_token(self, jti: str) -> bool:
        """Revoke a refresh token"""
        return await cache.delete(f"refresh_token:{jti}")

    async def check_login_attempts(self, identifier: str) -> tuple[bool, int]:
        """Check if user has exceeded login attempts"""
        attempts_key = f"login_attempts:{identifier}"
        attempts = await cache.get(attempts_key)

        if attempts is None:
            return True, 0

        attempts = int(attempts)
        max_attempts = USER_SERVICE_CONFIG["max_login_attempts"]

        if attempts >= max_attempts:
            # Check if lockout period has expired
            lockout_key = f"account_locked:{identifier}"
            if await cache.exists(lockout_key):
                return False, attempts
            else:
                # Reset attempts after lockout period
                await cache.delete(attempts_key)
                return True, 0

        return True, attempts

    async def record_login_attempt(self, identifier: str, success: bool):
        """Record login attempt"""
        attempts_key = f"login_attempts:{identifier}"

        if success:
            # Reset attempts on successful login
            await cache.delete(attempts_key)
            await cache.delete(f"account_locked:{identifier}")
        else:
            # Increment failed attempts
            attempts = await cache.incr(attempts_key)
            await cache.expire(attempts_key, 3600)  # 1 hour

            # Lock account if max attempts reached
            if attempts >= USER_SERVICE_CONFIG["max_login_attempts"]:
                lockout_key = f"account_locked:{identifier}"
                lockout_duration = USER_SERVICE_CONFIG["account_lockout_minutes"] * 60
                await cache.setex(lockout_key, lockout_duration, "1")

    async def revoke_all_user_tokens(self, user_id: str):
        """Revoke all refresh tokens for a user"""
        pattern = f"refresh_token:*"
        keys = await cache.keys(pattern)

        for key in keys:
            owner_id = await cache.get(key)
            if owner_id == user_id:
                await cache.delete(key)


# Initialize auth service
auth_service = AuthService()


class RBACService:
    """Role-Based Access Control service"""

    def __init__(self):
        self.role_permissions = {
            UserRole.ADMIN: [
                "read:documents:all",
                "write:documents:all",
                "delete:documents:all",
                "manage:users:all",
                "manage:organizations:all",
                "read:analytics:all",
                "write:analytics:all",
                "read:system:all",
                "manage:system:all",
            ],
            UserRole.CONTENT_MANAGER: [
                "read:documents:all",
                "write:documents:all",
                "delete:documents:all",
                "read:analytics:all",
                "write:analytics:all",
            ],
            UserRole.USER: [
                "read:documents:own",
                "write:documents:own",
                "delete:documents:own",
                "read:search",
                "read:analytics:own",
            ],
            UserRole.ANALYST: [
                "read:documents:all",
                "read:search:all",
                "read:analytics:all",
                "write:analytics:all",
            ],
            UserRole.VIEWER: ["read:documents:public", "read:search:public"],
        }

    def get_permissions(self, role: UserRole) -> List[str]:
        """Get permissions for a role"""
        return self.role_permissions.get(role, [])

    def has_permission(self, user_role: UserRole, required_permission: str) -> bool:
        """Check if user role has required permission"""
        permissions = self.get_permissions(user_role)
        return required_permission in permissions

    def has_any_permission(
        self, user_role: UserRole, required_permissions: List[str]
    ) -> bool:
        """Check if user role has any of the required permissions"""
        permissions = self.get_permissions(user_role)
        return any(perm in permissions for perm in required_permissions)

    def has_all_permissions(
        self, user_role: UserRole, required_permissions: List[str]
    ) -> bool:
        """Check if user role has all required permissions"""
        permissions = self.get_permissions(user_role)
        return all(perm in permissions for perm in required_permissions)


# Initialize RBAC service
rbac_service = RBACService()


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current authenticated user"""
    if not credentials:
        raise AuthenticationError("Authentication credentials required")

    # Verify token
    token = credentials.credentials
    payload = await auth_service.verify_token(token, "access")

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Invalid token: missing user ID")

    # Get user from database
    result = await db.execute(
        select(User).where(and_(User.id == uuid.UUID(user_id), User.is_active == True))
    )
    user = result.scalar_one_or_none()

    if not user:
        raise AuthenticationError("User not found or inactive")

    return user


async def get_user_context(
    current_user: User = Depends(get_current_user),
) -> OrganizationContext:
    """Get user organization context"""
    # Get storage quota and usage
    storage_quota_mb = 5120  # Default 5GB
    storage_used_mb = 0.0

    # Calculate actual storage usage
    # This would be calculated from document service
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://localhost:8001/storage/quota?organization_id={current_user.organization_id}"
            )
            if response.status_code == 200:
                data = response.json()
                storage_quota_mb = data.get("quota_limit_mb", storage_quota_mb)
                storage_used_mb = data.get("current_usage_mb", storage_used_mb)
    except Exception:
        pass  # Use defaults if service unavailable

    return OrganizationContext(
        organization_id=current_user.organization_id,
        user_role=UserRole(current_user.role.value),
        permissions=rbac_service.get_permissions(UserRole(current_user.role.value)),
        storage_quota_mb=storage_quota_mb,
        storage_used_mb=storage_used_mb,
    )


def require_permission(permission: str):
    """Decorator to require specific permission"""

    def permission_dependency(
        user_context: OrganizationContext = Depends(get_user_context),
    ):
        if not rbac_service.has_permission(user_context.user_role, permission):
            raise AuthorizationError(
                message="Insufficient permissions", required_permission=permission
            )
        return user_context

    return permission_dependency


def require_role(required_role: UserRole):
    """Decorator to require specific role"""

    def role_dependency(current_user: User = Depends(get_current_user)):
        user_role = UserRole(current_user.role.value)
        if not rbac_service.has_permission(user_role, f"role:{required_role.value}"):
            raise AuthorizationError(
                message=f"Requires {required_role.value} role or higher"
            )
        return current_user

    return role_dependency


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    await event_logger.log_event(
        event_type="service_startup",
        event_data={"version": USER_SERVICE_CONFIG["version"]},
    )

    # Add health checks
    health_checker.add_check(
        "database", lambda: True
    )  # Would check actual DB connection
    health_checker.add_check(
        "redis", lambda: True
    )  # Would check actual Redis connection


@app.post("/auth/login", response_model=LoginResponse)
@handle_exceptions
async def login(
    request: LoginRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """User login"""
    identifier = request.email.lower()

    # Check rate limiting
    can_login, attempts = await auth_service.check_login_attempts(identifier)
    if not can_login:
        raise AuthenticationError(
            message=f"Account temporarily locked due to too many failed attempts. Try again later.",
            details={"attempts": attempts},
        )

    # Check rate limiting for endpoint
    is_allowed, rate_info = await rate_limiter.is_allowed(
        key="login_attempts", limit=5, window=300, identifier=identifier  # 5 minutes
    )

    if not is_allowed:
        raise AuthenticationError(
            message="Too many login attempts. Please try again later.",
            details={"retry_after": rate_info["retry_after"]},
        )

    # Find user
    result = await db.execute(
        select(User).where(and_(User.email == identifier, User.is_active == True))
    )
    user = result.scalar_one_or_none()

    if not user or not auth_service.verify_password(
        request.password, user.password_hash
    ):
        # Record failed attempt
        await auth_service.record_login_attempt(identifier, False)

        await event_logger.log_event(
            event_type="login_failed",
            event_data={"identifier": identifier, "reason": "invalid_credentials"},
        )

        raise AuthenticationError("Invalid email or password")

    # Record successful login
    await auth_service.record_login_attempt(identifier, True)

    # Update user login info
    user.update_last_login()
    await db.commit()

    # Create tokens
    access_token = await auth_service.create_access_token(
        {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "organization_id": str(user.organization_id),
            "permissions": rbac_service.get_permissions(UserRole(user.role.value)),
        }
    )

    refresh_token = await auth_service.create_refresh_token(
        str(user.id), str(user.organization_id)
    )

    # Log successful login
    await event_logger.log_event(
        event_type="login_successful",
        event_data={
            "user_id": str(user.id),
            "email": user.email,
            "organization_id": str(user.organization_id),
        },
        user_id=str(user.id),
        organization_id=str(user.organization_id),
    )

    # Record metrics
    metrics.increment_counter("logins", labels={"role": user.role.value})

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user={
            "id": str(user.id),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role.value,
            "organization_id": str(user.organization_id),
            "is_active": user.is_active,
            "created_at": user.created_at,
            "last_login": user.last_login,
        },
    )


@app.post("/auth/refresh", response_model=TokenResponse)
@handle_exceptions
async def refresh_token(request: TokenRequest):
    """Refresh access token"""
    try:
        # Verify refresh token
        payload = await auth_service.verify_token(request.refresh_token, "refresh")

        user_id = payload.get("sub")
        organization_id = payload.get("organization_id")
        jti = payload.get("jti")

        if not all([user_id, organization_id, jti]):
            raise AuthenticationError("Invalid refresh token")

        # Create new access token
        access_token = await auth_service.create_access_token(
            {"sub": user_id, "organization_id": organization_id, "type": "access"}
        )

        await event_logger.log_event(
            event_type="token_refreshed", event_data={"user_id": user_id}
        )

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    except Exception as e:
        await event_logger.log_error(e, {"operation": "refresh_token"})
        raise AuthenticationError("Invalid or expired refresh token")


@app.post("/auth/logout")
@handle_exceptions
async def logout(
    background_tasks: BackgroundTasks, current_user: User = Depends(get_current_user)
):
    """User logout"""
    # Revoke all user tokens in background
    background_tasks.add_task(auth_service.revoke_all_user_tokens, str(current_user.id))

    await event_logger.log_event(
        event_type="logout",
        event_data={"user_id": str(current_user.id)},
        user_id=str(current_user.id),
        organization_id=str(current_user.organization_id),
    )

    return BaseResponse(success=True, message="Logged out successfully")


@app.get("/users/me", response_model=UserDetailResponse)
@handle_exceptions
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    user_context: OrganizationContext = Depends(get_user_context),
):
    """Get current user information"""
    return UserDetailResponse(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        role=UserRole(current_user.role.value),
        organization_id=current_user.organization_id,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        last_login=current_user.last_login,
        storage_quota_mb=user_context.storage_quota_mb,
        storage_used_mb=user_context.storage_used_mb,
        preferences={},  # Would load from database
        permissions=user_context.permissions,
    )


@app.get("/users", response_model=List[UserResponse])
@handle_exceptions
async def list_users(
    organization_id: uuid.UUID = Query(...),
    role: Optional[UserRole] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_permission("read:users:all")),
    db: AsyncSession = Depends(get_db),
):
    """List users (admin only)"""
    # Build query
    query = select(User).where(
        and_(User.organization_id == organization_id, User.is_deleted == False)
    )

    if role:
        query = query.where(User.role == UserRoleEnum(role.value))

    # Add pagination
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit).order_by(desc(User.created_at))

    result = await db.execute(query)
    users = result.scalars().all()

    return [
        UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            role=UserRole(user.role.value),
            organization_id=user.organization_id,
            is_active=user.is_active,
            created_at=user.created_at,
            last_login=user.last_login,
        )
        for user in users
    ]


@app.post("/users", response_model=UserResponse)
@handle_exceptions
async def create_user(
    request: CreateUserRequest,
    current_user: User = Depends(require_permission("manage:users:all")),
    db: AsyncSession = Depends(get_db),
):
    """Create new user (admin only)"""
    # Validate email uniqueness
    existing_user = await db.execute(
        select(User).where(User.email == request.email.lower())
    )
    if existing_user.scalar_one_or_none():
        raise ConflictError("User with this email already exists")

    # Validate password strength
    is_valid, errors = auth_service.validate_password_strength(request.password)
    if not is_valid:
        raise ValidationError(
            "Password does not meet security requirements", details={"errors": errors}
        )

    # Create user
    user = User(
        email=request.email.lower(),
        first_name=request.first_name,
        last_name=request.last_name,
        role=UserRoleEnum(request.role.value),
        organization_id=request.organization_id,
        is_active=True,
    )
    user.set_password(request.password)

    db.add(user)
    await db.commit()

    await event_logger.log_event(
        event_type="user_created",
        event_data={
            "new_user_id": str(user.id),
            "email": user.email,
            "role": user.role.value,
        },
        user_id=str(current_user.id),
        organization_id=str(current_user.organization_id),
    )

    metrics.increment_counter("users_created", labels={"role": user.role.value})

    return UserResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=UserRole(user.role.value),
        organization_id=user.organization_id,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login=user.last_login,
    )


@app.put("/users/{user_id}", response_model=UserResponse)
@handle_exceptions
async def update_user(
    user_id: uuid.UUID,
    request: UpdateUserRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user"""
    # Check permissions
    if str(current_user.id) != str(user_id):
        # Updating another user requires admin permissions
        if not rbac_service.has_permission(
            UserRole(current_user.role.value), "manage:users:all"
        ):
            raise AuthorizationError("Cannot update other users")

    # Get user to update
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundError(
            "User not found", resource_type="user", resource_id=str(user_id)
        )

    # Update fields
    if request.first_name is not None:
        user.first_name = request.first_name

    if request.last_name is not None:
        user.last_name = request.last_name

    if request.role is not None:
        # Only admins can change roles
        if not rbac_service.has_permission(
            UserRole(current_user.role.value), "manage:users:all"
        ):
            raise AuthorizationError("Cannot change user role")
        user.role = UserRoleEnum(request.role.value)

    if request.is_active is not None:
        # Only admins can deactivate users
        if not rbac_service.has_permission(
            UserRole(current_user.role.value), "manage:users:all"
        ):
            raise AuthorizationError("Cannot change user active status")
        user.is_active = request.is_active

    if request.preferences is not None:
        # User preferences would be stored in separate table
        pass

    await db.commit()

    await event_logger.log_event(
        event_type="user_updated",
        event_data={
            "updated_user_id": str(user_id),
            "updated_fields": request.dict(exclude_unset=True),
        },
        user_id=str(current_user.id),
        organization_id=str(current_user.organization_id),
    )

    return UserResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=UserRole(user.role.value),
        organization_id=user.organization_id,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login=user.last_login,
    )


@app.delete("/users/{user_id}")
@handle_exceptions
async def delete_user(
    user_id: uuid.UUID,
    current_user: User = Depends(require_permission("manage:users:all")),
    db: AsyncSession = Depends(get_db),
):
    """Delete user (soft delete, admin only)"""
    # Prevent self-deletion
    if str(current_user.id) == str(user_id):
        raise ValidationError("Cannot delete your own account")

    # Get user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundError(
            "User not found", resource_type="user", resource_id=str(user_id)
        )

    # Soft delete
    user.soft_delete()
    await db.commit()

    # Revoke all tokens
    await auth_service.revoke_all_user_tokens(str(user_id))

    await event_logger.log_event(
        event_type="user_deleted",
        event_data={"deleted_user_id": str(user_id), "email": user.email},
        user_id=str(current_user.id),
        organization_id=str(current_user.organization_id),
    )

    return BaseResponse(success=True, message="User deleted successfully")


@app.get("/auth/permissions")
@handle_exceptions
async def get_user_permissions(
    user_context: OrganizationContext = Depends(get_user_context),
):
    """Get current user permissions"""
    return {
        "role": user_context.user_role.value,
        "permissions": user_context.permissions,
        "organization_id": str(user_context.organization_id),
    }


@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Service health check"""
    health_data = await health_checker.check_health()

    return HealthCheckResponse(
        status=health_data["status"],
        version=USER_SERVICE_CONFIG["version"],
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc),
        services=health_data["checks"],
        uptime_seconds=0,  # Would track actual uptime
    )


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await cache.close()
    await event_logger.log_event(event_type="service_shutdown", event_data={})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.services.user_management:app",
        host=USER_SERVICE_CONFIG["host"],
        port=USER_SERVICE_CONFIG["port"],
        log_level=settings.LOG_LEVEL.lower(),
    )
