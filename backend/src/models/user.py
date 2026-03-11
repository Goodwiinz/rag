"""
User model and related functionality
"""

from sqlalchemy import Column, String, Boolean, DateTime, Enum, ForeignKey, Integer, Index
from sqlalchemy.orm import relationship, selectinload, joinedload
from enum import Enum as PyEnum
import bcrypt
from datetime import datetime
from enum import Enum as PyEnum

import bcrypt
from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .base import GUID, BaseModel


class UserRole(PyEnum):
    """User roles"""

    ADMIN = "admin"
    CONTENT_MANAGER = "content_manager"
    USER = "user"
    ANALYST = "analyst"


class User(BaseModel):
    """User account model"""

    __tablename__ = "users"

    # Basic information
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)

    # Role and permissions
    role = Column(Enum(UserRole), nullable=False, default=UserRole.USER)
    is_active = Column(Boolean, default=True, nullable=False)

    # Organization
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)

    # Authentication tracking
    last_login = Column(DateTime(timezone=True), nullable=True)
    login_count = Column(Integer, default=0, nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="users")
    documents = relationship("Document", back_populates="uploaded_by_user")
    search_queries = relationship("SearchQuery", back_populates="user")

    # Analytics relationships (using string references to avoid circular imports)
    sessions = relationship(
        "src.models.user_session.UserSession", back_populates="user"
    )
    analytics_events = relationship(
        "src.models.analytics_event.AnalyticsEvent", back_populates="user"
    )
    search_sessions = relationship("SearchSession", back_populates="user")
    search_events = relationship("SearchEvent", back_populates="user")

    # Encrypted profile relationship
    encrypted_profile = relationship(
        "EncryptedUserProfile", back_populates="user", uselist=False
    )

    # Audit relationship
    audit_events = relationship("AuditEvent", back_populates="user")

    # A/B Testing relationships
    created_experiments = relationship("Experiment", back_populates="creator")

    # Database indexes for performance optimization
    __table_args__ = (
        Index('idx_user_email_active', 'email', 'is_active'),
        Index('idx_user_org_role', 'organization_id', 'role'),
        Index('idx_user_org_active', 'organization_id', 'is_active'),
        Index('idx_user_last_login_active', 'last_login', 'is_active'),
        Index('idx_user_role_active', 'role', 'is_active'),
    )

    def __repr__(self):
        return f"<User(email={self.email}, role={self.role.value})>"

    @property
    def full_name(self) -> str:
        """Get user's full name"""
        return f"{self.first_name} {self.last_name}"

    def set_password(self, password: str):
        """Set user password with secure hashing"""
        from src.core.security import get_password_hash

        self.password_hash = get_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Check if provided password matches stored hash"""
        from src.core.security import verify_password

        return verify_password(password, self.password_hash)

    def update_last_login(self):
        """Update last login timestamp and increment login count"""
        self.last_login = datetime.utcnow()
        self.login_count += 1

    def has_permission(self, required_role: UserRole) -> bool:
        """Check if user has required or higher permission level"""
        if isinstance(required_role, str):
            try:
                required_role = UserRole(required_role)
            except ValueError:
                # Invalid role string, deny permission securely
                return False

        role_hierarchy = {
            UserRole.USER: 0,
            UserRole.ANALYST: 1,
            UserRole.CONTENT_MANAGER: 2,
            UserRole.ADMIN: 3,
        }

        # Use 100 as default for unknown required roles to fail securely
        # (user level will never be >= 100)
        return role_hierarchy.get(self.role, 0) >= role_hierarchy.get(required_role, 100)

    def can_upload_documents(self) -> bool:
        """Check if user can upload documents"""
        return self.has_permission(UserRole.USER)

    def can_manage_users(self) -> bool:
        """Check if user can manage other users"""
        return self.has_permission(UserRole.ADMIN)

    def can_view_analytics(self) -> bool:
        """Check if user can view analytics"""
        return self.has_permission(UserRole.ANALYST)

    @classmethod
    def get_with_organization(cls, user_id):
        """Get user with organization eagerly loaded to avoid N+1 queries"""
        from sqlalchemy.orm import sessionmaker
        return cls.query.options(joinedload(cls.organization)).filter(cls.id == user_id).first()
    
    @classmethod
    def get_with_recent_activity(cls, user_id):
        """Get user with recent activity data eagerly loaded"""
        from sqlalchemy.orm import sessionmaker
        from src.models.quality_metrics import SearchSession
        return cls.query.options(
            joinedload(cls.organization),
            selectinload(cls.search_sessions).options(
                selectinload(SearchSession.searches)
            ),
            selectinload(cls.sessions)
        ).filter(cls.id == user_id).first()
    
    @classmethod
    def get_org_users_with_details(cls, organization_id):
        """Get organization users with common relationships loaded to avoid N+1"""
        return cls.query.options(
            joinedload(cls.organization),
            selectinload(cls.search_sessions),
            selectinload(cls.analytics_events)
        ).filter(cls.organization_id == organization_id).all()


    def to_dict(self, exclude_sensitive: bool = True) -> dict:
        """Convert to dictionary, optionally excluding sensitive data"""
        data = super().to_dict()

        if exclude_sensitive:
            data.pop("password_hash", None)

        # Add computed fields
        data["full_name"] = self.full_name
        data["role"] = self.role.value if self.role else None

        return data
