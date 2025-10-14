"""
Authentication service for user management and security
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
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

    def __init__(self, db: Session):
        self.db = db

    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password"""
        # Check rate limiting
        if not auth_rate_limiter.is_allowed(email):
            raise AuthenticationError(
                "Too many login attempts. Please try again later."
            )

        user = self.db.query(User).filter(
            and_(
                User.email == email.lower(),
                User.is_active == True,
                User.is_deleted == False
            )
        ).first()

        if not user or not verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid email or password")

        # Update last login
        user.update_last_login()
        self.db.commit()

        return user

    def login_user(self, email: str, password: str) -> Dict[str, Any]:
        """Login user and return tokens"""
        user = self.authenticate_user(email, password)

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

        # Create refresh token
        refresh_token = create_refresh_token(
            data={"sub": str(user.id)}
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": user.to_dict(exclude_sensitive=True)
        }

    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token using refresh token"""
        token_data = verify_refresh_token(refresh_token)

        if not token_data:
            raise AuthenticationError("Invalid refresh token")

        user = self.db.query(User).filter(
            and_(
                User.id == token_data.user_id,
                User.is_active == True,
                User.is_deleted == False
            )
        ).first()

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

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }

    def register_user(
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
        existing_user = self.db.query(User).filter(
            User.email == email.lower()
        ).first()

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
            organization = self.db.query(Organization).filter(
                and_(
                    Organization.id == organization_id,
                    Organization.is_active == True,
                    Organization.is_deleted == False
                )
            ).first()

            if not organization:
                raise RegistrationError("Organization not found")

        elif organization_name:
            # Check if organization already exists
            organization = self.db.query(Organization).filter(
                and_(
                    Organization.name == organization_name,
                    Organization.is_active == True,
                    Organization.is_deleted == False
                )
            ).first()

            if not organization:
                # Create new organization
                organization = Organization(
                    name=organization_name,
                    storage_tier=StorageTier.FREE,
                    storage_limit_bytes=Organization.get_default_storage_limit(StorageTier.FREE),
                    is_active=True
                )
                self.db.add(organization)
                self.db.flush()  # Get the organization ID

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
        self.db.commit()
        self.db.refresh(user)

        return user

    def change_password(
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
        self.db.commit()

        return True

    def initiate_password_reset(self, email: str) -> str:
        """Initiate password reset process"""
        user = self.db.query(User).filter(
            and_(
                User.email == email.lower(),
                User.is_active == True,
                User.is_deleted == False
            )
        ).first()

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

    def update_user_profile(
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
            existing_user = self.db.query(User).filter(
                and_(
                    User.email == email.lower(),
                    User.id != user.id
                )
            ).first()

            if existing_user:
                raise RegistrationError("Email already in use")

            user.email = email.lower()

        self.db.commit()
        self.db.refresh(user)

        return user

    def update_user_role(
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
            admin_count = self.db.query(User).filter(
                and_(
                    User.organization_id == admin_user.organization_id,
                    User.role == UserRole.ADMIN,
                    User.is_active == True,
                    User.is_deleted == False
                )
            ).count()

            if admin_count <= 1:
                raise AuthorizationError("Cannot remove admin role from last admin")

        target_user.role = new_role
        self.db.commit()
        self.db.refresh(target_user)

        return target_user

    def deactivate_user(self, admin_user: User, target_user: User) -> bool:
        """Deactivate a user (admin only)"""
        if not admin_user.has_permission(UserRole.ADMIN):
            raise AuthorizationError("Only admins can deactivate users")

        if target_user.id == admin_user.id:
            raise AuthorizationError("Cannot deactivate your own account")

        target_user.is_active = False
        self.db.commit()

        return True

    def get_organization_users(
        self,
        organization_id: str,
        skip: int = 0,
        limit: int = 100,
        role: UserRole = None,
        is_active: bool = None
    ) -> List[User]:
        """Get users in an organization"""
        query = self.db.query(User).filter(
            and_(
                User.organization_id == organization_id,
                User.is_deleted == False
            )
        )

        if role:
            query = query.filter(User.role == role)

        if is_active is not None:
            query = query.filter(User.is_active == is_active)

        return query.offset(skip).limit(limit).all()

    def get_user_statistics(self, organization_id: str) -> Dict[str, Any]:
        """Get user statistics for an organization"""
        total_users = self.db.query(User).filter(
            and_(
                User.organization_id == organization_id,
                User.is_deleted == False
            )
        ).count()

        active_users = self.db.query(User).filter(
            and_(
                User.organization_id == organization_id,
                User.is_active == True,
                User.is_deleted == False
            )
        ).count()

        # Users by role
        role_stats = {}
        for role in UserRole:
            count = self.db.query(User).filter(
                and_(
                    User.organization_id == organization_id,
                    User.role == role,
                    User.is_deleted == False
                )
            ).count()
            role_stats[role.value] = count

        # Recent activity (users who logged in within last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_active = self.db.query(User).filter(
            and_(
                User.organization_id == organization_id,
                User.last_login >= thirty_days_ago,
                User.is_deleted == False
            )
        ).count()

        return {
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": total_users - active_users,
            "recent_active_users": recent_active,
            "users_by_role": role_stats
        }

    def cleanup_inactive_users(
        self,
        organization_id: str,
        days_inactive: int = 90
    ) -> int:
        """Soft delete users inactive for specified days"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_inactive)

        inactive_users = self.db.query(User).filter(
            and_(
                User.organization_id == organization_id,
                User.last_login < cutoff_date,
                User.is_deleted == False
            )
        ).all()

        for user in inactive_users:
            user.soft_delete()

        self.db.commit()
        return len(inactive_users)

def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    """Get authentication service instance"""
    return AuthService(db)