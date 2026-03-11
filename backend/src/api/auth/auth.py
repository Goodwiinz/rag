"""
Authentication API endpoints
"""

import logging
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database import get_db
from src.core.dependencies import get_current_user, is_self_or_admin, require_admin
from src.core.security import auth_rate_limiter, get_client_ip
from jose import jwt
from src.models.user import User, UserRole
from src.services.security.auth_service import (
    AuthenticationError,
    AuthService,
    RegistrationError,
    get_auth_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


# Request/Response Models
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    refresh_expires_in: Optional[int] = None  # Refresh token expiration in seconds
    remember_me: bool = False  # Indicates if this is an extended 30-day session
    user: dict


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserRegistration(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    organization_name: Optional[str] = None
    organization_id: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False  # If True, session persists for 30 days instead of 7


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class PasswordReset(BaseModel):
    email: EmailStr


class ProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None


class RoleUpdate(BaseModel):
    role: UserRole


@router.post("/register", response_model=dict)
async def register(
    user_data: UserRegistration,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Register a new user"""
    # Get client IP for rate limiting
    client_ip = get_client_ip(request)

    if not await auth_rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Please try again later.",
        )

    try:
        user = await auth_service.register_user(
            email=user_data.email,
            password=user_data.password,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            organization_name=user_data.organization_name,
            organization_id=user_data.organization_id,
        )

        return {
            "message": "User registered successfully",
            "user": user.to_dict(exclude_sensitive=True),
        }

    except RegistrationError as e:
        # Return specific error for registration issues (e.g. weak password)
        # Note: This may leak "user exists" but is needed for UX
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/login", response_model=TokenResponse)
async def login(
    user_credentials: UserLogin,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Login user and return tokens

    Args:
        user_credentials: Email, password, and optional remember_me flag
            - remember_me=True: Session persists for 30 days
            - remember_me=False (default): Session persists for 7 days
    """
    # Dual-layer rate limiting: IP + email
    client_ip = get_client_ip(request)

    if not await auth_rate_limiter.is_allowed(client_ip, prefix="ip"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts from this IP. Please try again later."
        )

    if not await auth_rate_limiter.is_allowed(user_credentials.email, prefix="email"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts for this account. Please try again later."
        )

    try:
        token_data = await auth_service.login_user(
            email=user_credentials.email,
            password=user_credentials.password,
            remember_me=user_credentials.remember_me,
        )

        return token_data

    except AuthenticationError:
        # Return generic error message to prevent enumeration/leakage
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/refresh", response_model=dict)
async def refresh_token(
    token_request: RefreshTokenRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Refresh access token"""
    # Get client IP for rate limiting
    client_ip = get_client_ip(request)

    if not await auth_rate_limiter.is_allowed(client_ip, prefix="refresh_ip"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many refresh attempts. Please try again later.",
            headers={"Retry-After": str(settings.AUTH_RATE_LIMIT_WINDOW_MINUTES * 60)},
        )

    # Attempt to extract user_id from token payload for per-user rate limiting.
    # We do not verify signature here (the service will do that), just decoding for rate limit bucket.
    try:
        unverified_payload = jwt.decode(token_request.refresh_token, options={"verify_signature": False})
        user_id = unverified_payload.get("sub")
        if user_id:
            if not await auth_rate_limiter.is_allowed(user_id, prefix="refresh_user"):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many refresh attempts for this account. Please try again later.",
                    headers={"Retry-After": str(settings.AUTH_RATE_LIMIT_WINDOW_MINUTES * 60)},
                )
    except Exception:
        pass # If token is completely malformed, let the service layer reject it

    try:
        token_data = await auth_service.refresh_access_token(
            refresh_token=token_request.refresh_token
        )

        return token_data

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return {"user": current_user.to_dict(exclude_sensitive=True)}


@router.get("/session")
async def get_session_info(current_user: User = Depends(get_current_user)):
    """Get current session configuration info

    Returns session duration settings so frontend can configure proactive refresh.
    """
    return {
        "access_token_expires_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        "refresh_token_expires_days": settings.REFRESH_TOKEN_EXPIRE_DAYS,
        "remember_me_expires_days": settings.REMEMBER_ME_REFRESH_TOKEN_DAYS,
        "user_id": str(current_user.id),
    }


@router.put("/me")
async def update_profile(
    profile_data: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Update current user profile"""
    try:
        updated_user = await auth_service.update_user_profile(
            user=current_user,
            first_name=profile_data.first_name,
            last_name=profile_data.last_name,
            email=profile_data.email,
        )

        return {
            "message": "Profile updated successfully",
            "user": updated_user.to_dict(exclude_sensitive=True),
        }

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    request: Request,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Change user password"""
    # Dual-layer rate limiting: IP + email
    client_ip = get_client_ip(request)

    if not await auth_rate_limiter.is_allowed(client_ip, prefix="ip_change_pw"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many password change attempts from this IP. Please try again later.",
            headers={"Retry-After": str(settings.AUTH_RATE_LIMIT_WINDOW_MINUTES * 60)},
        )

    if not await auth_rate_limiter.is_allowed(current_user.email, prefix="email_change_pw"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many password change attempts for this account. Please try again later.",
            headers={"Retry-After": str(settings.AUTH_RATE_LIMIT_WINDOW_MINUTES * 60)},
        )

    try:
        await auth_service.change_password(
            user=current_user,
            current_password=password_data.current_password,
            new_password=password_data.new_password,
        )

        return {"message": "Password changed successfully"}

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/reset-password")
async def request_password_reset(
    reset_data: PasswordReset,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Request password reset"""
    # Get client IP for rate limiting
    client_ip = get_client_ip(request)

    if not await auth_rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many password reset attempts. Please try again later.",
        )

    try:
        reset_token = await auth_service.initiate_password_reset(email=reset_data.email)

        # In production, you would email the reset token
        # For now, we'll just return a success message
        return {
            "message": "If an account with this email exists, a password reset link has been sent"
        }

    except Exception as e:
        # Always return success to prevent email enumeration
        return {
            "message": "If an account with this email exists, a password reset link has been sent"
        }


@router.get("/users")
async def get_organization_users(
    skip: int = 0,
    limit: int = 100,
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
    current_user: User = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Get users in the organization (admin only)"""
    users = await auth_service.get_organization_users(
        organization_id=str(current_user.organization_id),
        skip=skip,
        limit=limit,
        role=role,
        is_active=is_active,
    )

    return {
        "users": [user.to_dict(exclude_sensitive=True) for user in users],
        "total": len(users),
        "skip": skip,
        "limit": limit,
    }


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    role_data: RoleUpdate,
    current_user: User = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
):
    """Update user role (admin only)"""
    stmt = select(User).where(
        User.id == user_id,
        User.organization_id == current_user.organization_id,
        User.is_deleted == False,
    )
    result = await db.execute(stmt)
    target_user = result.scalars().first()

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    try:
        updated_user = await auth_service.update_user_role(
            admin_user=current_user, target_user=target_user, new_role=role_data.role
        )

        return {
            "message": "User role updated successfully",
            "user": updated_user.to_dict(exclude_sensitive=True),
        }

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: str,
    current_user: User = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate a user (admin only)"""
    stmt = select(User).where(
        User.id == user_id,
        User.organization_id == current_user.organization_id,
        User.is_deleted == False,
    )
    result = await db.execute(stmt)
    target_user = result.scalars().first()

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    try:
        await auth_service.deactivate_user(
            admin_user=current_user, target_user=target_user
        )

        return {"message": "User deactivated successfully"}

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/statistics")
async def get_user_statistics(
    current_user: User = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Get user statistics for the organization (admin only)"""
    stats = await auth_service.get_user_statistics(
        organization_id=str(current_user.organization_id)
    )

    return stats


@router.post("/cleanup")
async def cleanup_inactive_users(
    days_inactive: int = 90,
    current_user: User = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Clean up inactive users (admin only)"""
    try:
        deleted_count = await auth_service.cleanup_inactive_users(
            organization_id=str(current_user.organization_id),
            days_inactive=days_inactive,
        )

        return {
            "message": f"Cleaned up {deleted_count} inactive users",
            "deleted_count": deleted_count,
        }

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
