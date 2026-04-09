"""
Authentication service for user management and security.

Supabase handles registration, login, token refresh, and password reset.
This service provides profile management, password change, admin operations,
and user statistics.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import Depends
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.security import (
    check_password_strength,
    verify_password,
)
from src.core.supabase_client import get_supabase_client
from src.models.user import User, UserRole

logger = __import__("logging").getLogger(__name__)


class AuthenticationError(Exception):
    """Authentication related errors"""

    pass


class AuthorizationError(Exception):
    """Authorization related errors"""

    pass


class RegistrationError(Exception):
    """Registration related errors (used by password change validation)"""

    pass


class AuthService:
    """Authentication service for user management.

    Supabase handles registration, login, and token lifecycle.
    This service provides profile updates, password changes, and admin operations.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def change_password(
        self, user: User, current_password: str, new_password: str
    ) -> bool:
        """Change user password in both public.users and Supabase auth.users."""
        # Verify current password
        if not verify_password(current_password, user.password_hash):
            raise AuthenticationError("Current password is incorrect")

        # Check new password strength
        password_check = check_password_strength(new_password)
        if not password_check["is_valid"]:
            raise RegistrationError(
                f"New password does not meet security requirements: {', '.join(password_check['issues'])}"
            )

        # Sync password to Supabase auth.users first (fail fast if Supabase is down)
        supabase = get_supabase_client()
        if supabase:
            try:
                supabase.auth.admin.update_user_by_id(
                    str(user.id), {"password": new_password}
                )
            except Exception as exc:
                logger.error(f"Failed to update Supabase auth password: {exc}")
                raise AuthenticationError(
                    "Password change failed. Please try again later."
                )

        # Update local password hash
        user.set_password(new_password)
        await self.db.commit()

        return True

    async def update_user_profile(
        self,
        user: User,
        first_name: str = None,
        last_name: str = None,
        email: str = None,
    ) -> User:
        """Update user profile information"""
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        if email and email.lower() != user.email:
            # Check if new email is already taken
            stmt = select(User).where(
                and_(User.email == email.lower(), User.id != user.id)
            )
            result = await self.db.execute(stmt)
            existing_user = result.scalar_one_or_none()

            if existing_user:
                raise RegistrationError("Email already in use")

            user.email = email.lower()

        await self.db.commit()
        await self.db.refresh(user)

        return user

    async def update_user_role(
        self, admin_user: User, target_user: User, new_role: UserRole
    ) -> User:
        """Update user role (admin only)"""
        if not admin_user.has_permission(UserRole.ADMIN):
            raise AuthorizationError("Only admins can update user roles")

        # Prevent admins from demoting themselves unless they're the last admin
        if target_user.id == admin_user.id and new_role != UserRole.ADMIN:
            # Check if there are other admins in the organization
            stmt = select(func.count(User.id)).where(
                and_(
                    User.organization_id == admin_user.organization_id,
                    User.role == UserRole.ADMIN,
                    User.is_active == True,
                    User.is_deleted == False,
                )
            )
            result = await self.db.execute(stmt)
            admin_count = result.scalar()

            if admin_count <= 1:
                raise AuthorizationError("Cannot remove admin role from last admin")

        target_user.role = new_role
        await self.db.commit()
        await self.db.refresh(target_user)

        return target_user

    async def deactivate_user(self, admin_user: User, target_user: User) -> bool:
        """Deactivate a user (admin only)"""
        if not admin_user.has_permission(UserRole.ADMIN):
            raise AuthorizationError("Only admins can deactivate users")

        if target_user.id == admin_user.id:
            raise AuthorizationError("Cannot deactivate your own account")

        target_user.is_active = False
        await self.db.commit()

        return True

    async def get_organization_users(
        self,
        organization_id: str,
        skip: int = 0,
        limit: int = 100,
        role: UserRole = None,
        is_active: bool = None,
    ) -> List[User]:
        """Get users in an organization"""
        stmt = select(User).where(
            and_(User.organization_id == organization_id, User.is_deleted == False)
        )

        if role:
            stmt = stmt.where(User.role == role)

        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)

        stmt = stmt.offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_user_statistics(self, organization_id: str) -> Dict[str, Any]:
        """Get user statistics for an organization"""
        stmt = select(func.count(User.id)).where(
            and_(User.organization_id == organization_id, User.is_deleted == False)
        )
        result = await self.db.execute(stmt)
        total_users = result.scalar()

        stmt = select(func.count(User.id)).where(
            and_(
                User.organization_id == organization_id,
                User.is_active == True,
                User.is_deleted == False,
            )
        )
        result = await self.db.execute(stmt)
        active_users = result.scalar()

        # Users by role
        role_stats = {}
        for role in UserRole:
            stmt = select(func.count(User.id)).where(
                and_(
                    User.organization_id == organization_id,
                    User.role == role,
                    User.is_deleted == False,
                )
            )
            result = await self.db.execute(stmt)
            count = result.scalar()
            role_stats[role.value] = count

        # Recent activity (users who logged in within last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        stmt = select(func.count(User.id)).where(
            and_(
                User.organization_id == organization_id,
                User.last_login >= thirty_days_ago,
                User.is_deleted == False,
            )
        )
        result = await self.db.execute(stmt)
        recent_active = result.scalar()

        return {
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": total_users - active_users,
            "recent_active_users": recent_active,
            "users_by_role": role_stats,
        }

    async def cleanup_inactive_users(
        self, organization_id: str, days_inactive: int = 90
    ) -> int:
        """Soft delete users inactive for specified days"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_inactive)

        stmt = select(User).where(
            and_(
                User.organization_id == organization_id,
                User.last_login < cutoff_date,
                User.is_deleted == False,
            )
        )
        result = await self.db.execute(stmt)
        inactive_users = result.scalars().all()

        for user in inactive_users:
            user.soft_delete()

        await self.db.commit()
        return len(inactive_users)


def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    """Get authentication service instance"""
    return AuthService(db)
