"""
Authentication API endpoints.

Supabase handles registration, login, token refresh, and password reset.
This module provides profile management, session info, password change,
admin user management, and API key endpoints.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database import get_db
from src.core.dependencies import get_current_user, require_admin
from src.core.security import (
    auth_rate_limiter,
    get_client_ip,
    get_current_user_token,
)
from src.models.user import User, UserRole
from src.services.security.auth_service import (
    AuthService,
    get_auth_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


# Request/Response Models
class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class ProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None


class RoleUpdate(BaseModel):
    role: UserRole


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
    token_data=Depends(get_current_user_token),
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Change user password"""
    client_ip = get_client_ip(request)

    # IP-layer rate check first (before auth DB query)
    ip_allowed, ip_retry = await auth_rate_limiter.check_rate_limit(client_ip, prefix="chpw_ip")
    if not ip_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many password change attempts from this IP. Please try again later.",
            headers={"Retry-After": str(ip_retry)},
        )

    # Resolve authenticated user manually (after rate check)
    current_user = await get_current_user(token_data=token_data, db=db)

    # Email-layer rate check
    email_allowed, email_retry = await auth_rate_limiter.check_rate_limit(
        current_user.email, prefix="chpw_email"
    )
    if not email_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many password change attempts for this account. Please try again later.",
            headers={"Retry-After": str(email_retry)},
        )

    try:
        await auth_service.change_password(
            user=current_user,
            current_password=password_data.current_password,
            new_password=password_data.new_password,
        )

        # Success: no recording
        return {"message": "Password changed successfully"}

    except Exception as e:
        # Failure: record attempts for both layers
        await auth_rate_limiter.record_attempt(client_ip, prefix="chpw_ip")
        await auth_rate_limiter.record_attempt(current_user.email, prefix="chpw_email")

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


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
