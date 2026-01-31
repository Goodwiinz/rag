"""
Authentication service for user management and security
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy import and_, or_
from fastapi import Depends

from src.core.config import settings
from src.core.security import (
    verify_password, get_password_hash, create_access_token,
    create_refresh_token, verify_token, verify_refresh_token,
    generate_password_reset_token, check_password_strength,
    auth_rate_limiter
)
from src.core.database import get_db
from src.models.user import User, UserRole
from src.models.organization import Organization, StorageTier
from src.models.search import SearchQuery

# Pre-calculated dummy password hash for timing protection
# This ensures that invalid user checks take roughly the same time as valid user checks
# Generated with bcrypt cost 12
DUMMY_PASSWORD_HASH = "$2b$12$lUouH43LSTRXeBhV5vRtgeKeTJexParUQTmK5mT/No.yVCwiPX0um"

class AuthenticationError(Exception):
    """Authentication related errors"""
    pass

class AuthorizationError(Exception):
    """Authorization related errors"""
    pass

class RegistrationError(Exception):
    """Registration related errors"""
    pass

class AuthService:
    """Authentication service for user management"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password"""
        # Check rate limiting
        if not auth_rate_limiter.is_allowed(email):
            raise AuthenticationError(
                "Too many login attempts. Please try again later."
            )

        # Eager load organization relationship
        from sqlalchemy.orm import selectinload
        stmt = select(User).options(
            selectinload(User.organization)
        ).where(
            and_(
                User.email == email.lower(),
                User.is_active == True,
                User.is_deleted == False
            )
        )
        
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        # Always verify password to prevent timing attacks
        if user:
            password_valid = verify_password(password, user.password_hash)
        else:
            # Verify against dummy hash to simulate work
            verify_password(password, DUMMY_PASSWORD_HASH)
            password_valid = False

        if not user or not password_valid:
            raise AuthenticationError("Invalid email or password")

        # Update last login
        user.update_last_login()
        await self.db.commit()

        return user

    async def login_user(self, email: str, password: str, remember_me: bool = False) -> Dict[str, Any]:
        """Login user and return tokens

        Args:
            email: User email
            password: User password
            remember_me: If True, creates a 30-day session instead of 7-day
        """
        user = await self.authenticate_user(email, password)

        # Load organization relationship
        if user.organization:
            organization_data = user.organization.to_dict()
        else:
            organization_data = None

        # Create access token
        access_token_expires = timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "email": user.email,
                "organization_id": str(user.organization_id),
                "role": user.role.value
            },
            expires_delta=access_token_expires
        )

        # Create refresh token (30 days if remember_me, 7 days otherwise)
        refresh_token = create_refresh_token(
            data={"sub": str(user.id)},
            remember_me=remember_me
        )

        # Calculate refresh token expiration for frontend
        refresh_token_days = (
            settings.REMEMBER_ME_REFRESH_TOKEN_DAYS if remember_me
            else settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "refresh_expires_in": refresh_token_days * 24 * 60 * 60,  # In seconds
            "remember_me": remember_me,
            "user": user.to_dict(exclude_sensitive=True),
            "organization": organization_data
        }

    async def refresh_access_token(self, refresh_token: str, rotate_refresh: bool = True) -> Dict[str, Any]:
        """Refresh access token using refresh token

        Args:
            refresh_token: The refresh token to validate
            rotate_refresh: If True, also issue a new refresh token (recommended for security)
        """
        token_data = verify_refresh_token(refresh_token)

        if not token_data:
            raise AuthenticationError("Invalid refresh token")

        stmt = select(User).where(
            and_(
                User.id == token_data.user_id,
                User.is_active == True,
                User.is_deleted == False
            )
        )
        
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise AuthenticationError("User not found or inactive")

        # Create new access token
        access_token_expires = timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "email": user.email,
                "organization_id": str(user.organization_id),
                "role": user.role.value
            },
            expires_delta=access_token_expires
        )

        # Preserve the remember_me setting from the original refresh token
        remember_me = token_data.remember_me

        result = {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "remember_me": remember_me
        }

        # Optionally rotate refresh token (recommended for security)
        if rotate_refresh:
            new_refresh_token = create_refresh_token(
                data={"sub": str(user.id)},
                remember_me=remember_me
            )
            refresh_token_days = (
                settings.REMEMBER_ME_REFRESH_TOKEN_DAYS if remember_me
                else settings.REFRESH_TOKEN_EXPIRE_DAYS
            )
            result["refresh_token"] = new_refresh_token
            result["refresh_expires_in"] = refresh_token_days * 24 * 60 * 60

        return result

    async def register_user(
        self,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        organization_name: str = None,
        organization_id: str = None,
        role: UserRole = UserRole.USER
    ) -> User:
        """Register a new user"""
        # Check if user already exists
        stmt = select(User).where(User.email == email.lower())
        result = await self.db.execute(stmt)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            raise RegistrationError("User with this email already exists")

        # Check password strength
        password_check = check_password_strength(password)
        if not password_check["is_valid"]:
            raise RegistrationError(
                f"Password does not meet security requirements: {', '.join(password_check['issues'])}"
            )

        # Handle organization
        if organization_id:
            # Join existing organization
            stmt = select(Organization).where(
                and_(
                    Organization.id == organization_id,
                    Organization.is_active == True,
                    Organization.is_deleted == False
                )
            )
            result = await self.db.execute(stmt)
            organization = result.scalar_one_or_none()

            if not organization:
                raise RegistrationError("Organization not found")

        elif organization_name:
            # Check if organization already exists
            stmt = select(Organization).where(
                and_(
                    Organization.name == organization_name,
                    Organization.is_active == True,
                    Organization.is_deleted == False
                )
            )
            result = await self.db.execute(stmt)
            organization = result.scalar_one_or_none()

            if not organization:
                # Create new organization
                organization = Organization(
                    name=organization_name,
                    storage_tier=StorageTier.FREE,
                    storage_limit_bytes=Organization.get_default_storage_limit(StorageTier.FREE),
                    is_active=True
                )
                self.db.add(organization)
                await self.db.flush()  # Get the organization ID

                # First user in organization becomes admin
                role = UserRole.ADMIN
            # If organization exists, use default USER role (don't make them admin)

        else:
            raise RegistrationError("Either organization_name or organization_id must be provided")

        # Create user
        user = User(
            email=email.lower(),
            first_name=first_name,
            last_name=last_name,
            role=role,
            organization_id=organization.id,
            is_active=True
        )
        user.set_password(password)

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        return user

    async def change_password(
        self,
        user: User,
        current_password: str,
        new_password: str
    ) -> bool:
        """Change user password"""
        # Verify current password
        if not verify_password(current_password, user.password_hash):
            raise AuthenticationError("Current password is incorrect")

        # Check new password strength
        password_check = check_password_strength(new_password)
        if not password_check["is_valid"]:
            raise RegistrationError(
                f"New password does not meet security requirements: {', '.join(password_check['issues'])}"
            )

        # Update password
        user.set_password(new_password)
        await self.db.commit()

        return True

    async def initiate_password_reset(self, email: str) -> str:
        """Initiate password reset process"""
        stmt = select(User).where(
            and_(
                User.email == email.lower(),
                User.is_active == True,
                User.is_deleted == False
            )
        )
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            # Don't reveal if user exists or not
            return ""

        reset_token = generate_password_reset_token()

        # Store reset token (you might want to add a reset_token field to User model)
        # For now, we'll return it (in production, you'd email it)
        return reset_token

    def reset_password(self, reset_token: str, new_password: str) -> bool:
        """Reset password using reset token"""
        # In a real implementation, you'd verify the reset token
        # For now, this is a placeholder
        raise NotImplementedError("Password reset implementation requires database changes")

    async def update_user_profile(
        self,
        user: User,
        first_name: str = None,
        last_name: str = None,
        email: str = None
    ) -> User:
        """Update user profile information"""
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        if email and email.lower() != user.email:
            # Check if new email is already taken
            stmt = select(User).where(
                and_(
                    User.email == email.lower(),
                    User.id != user.id
                )
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
        self,
        admin_user: User,
        target_user: User,
        new_role: UserRole
    ) -> User:
        """Update user role (admin only)"""
        if not admin_user.has_permission(UserRole.ADMIN):
            raise AuthorizationError("Only admins can update user roles")

        # Prevent admins from demoting themselves unless they're the last admin
        if (target_user.id == admin_user.id and
            new_role != UserRole.ADMIN):
            # Check if there are other admins in the organization
            stmt = select(func.count(User.id)).where(
                and_(
                    User.organization_id == admin_user.organization_id,
                    User.role == UserRole.ADMIN,
                    User.is_active == True,
                    User.is_deleted == False
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
        is_active: bool = None
    ) -> List[User]:
        """Get users in an organization"""
        stmt = select(User).where(
            and_(
                User.organization_id == organization_id,
                User.is_deleted == False
            )
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
            and_(
                User.organization_id == organization_id,
                User.is_deleted == False
            )
        )
        result = await self.db.execute(stmt)
        total_users = result.scalar()

        stmt = select(func.count(User.id)).where(
            and_(
                User.organization_id == organization_id,
                User.is_active == True,
                User.is_deleted == False
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
                    User.is_deleted == False
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
                User.is_deleted == False
            )
        )
        result = await self.db.execute(stmt)
        recent_active = result.scalar()

        return {
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": total_users - active_users,
            "recent_active_users": recent_active,
            "users_by_role": role_stats
        }

    async def cleanup_inactive_users(
        self,
        organization_id: str,
        days_inactive: int = 90
    ) -> int:
        """Soft delete users inactive for specified days"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_inactive)

        stmt = select(User).where(
            and_(
                User.organization_id == organization_id,
                User.last_login < cutoff_date,
                User.is_deleted == False
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