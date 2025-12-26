"""
Permission and role models for comprehensive RBAC system
Defines fine-grained permissions, roles, and role assignments for multi-tenant access control
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum

from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
import uuid

from .base import Base


class PermissionCategory(str, Enum):
    """Categories of permissions for organization"""
    ORGANIZATION = "organization"
    USER_MANAGEMENT = "user_management"
    DOCUMENTS = "documents"
    ANALYTICS = "analytics"
    SYSTEM = "system"
    BILLING = "billing"
    API = "api"
    AUDIT = "audit"


class PermissionScope(str, Enum):
    """Scope of permission"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    MANAGE = "manage"
    ADMIN = "admin"


class Permission(Base):
    """Individual permission that can be granted to roles"""
    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    roles: Mapped[List["Role"]] = relationship(
        "Role", secondary="role_permissions", back_populates="permissions"
    )

    def __repr__(self):
        return f"<Permission(name={self.name}, category={self.category}, scope={self.scope})>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert permission to dictionary"""
        return {
            "id": str(self.id),
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "category": self.category,
            "scope": self.scope,
            "resource": self.resource,
            "is_system": self.is_system,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class Role(Base):
    """Role that groups permissions for assignment to users"""
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # Higher priority overrides lower
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="roles")
    permissions: Mapped[List[Permission]] = relationship(
        "Permission", secondary="role_permissions", back_populates="roles"
    )
    user_assignments: Mapped[List["UserRoleAssignment"]] = relationship(
        "UserRoleAssignment", back_populates="role", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Role(name={self.name}, org={self.organization_id}, priority={self.priority})>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert role to dictionary"""
        return {
            "id": str(self.id),
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "organization_id": str(self.organization_id),
            "is_system": self.is_system,
            "is_active": self.is_active,
            "priority": self.priority,
            "permissions": [perm.to_dict() for perm in self.permissions],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

    def has_permission(self, permission_name: str) -> bool:
        """Check if role has specific permission"""
        return any(perm.name == permission_name for perm in self.permissions if perm.is_active)

    def get_permission_names(self) -> List[str]:
        """Get list of permission names for this role"""
        return [perm.name for perm in self.permissions if perm.is_active]


class UserRoleAssignment(Base):
    """Assignment of role to user within organization"""
    __tablename__ = "user_role_assignments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    assigned_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    role: Mapped["Role"] = relationship("Role", back_populates="user_assignments")
    organization: Mapped["Organization"] = relationship("Organization", foreign_keys=[organization_id])
    assigned_by_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[assigned_by])

    def __repr__(self):
        return f"<UserRoleAssignment(user={self.user_id}, role={self.role_id}, org={self.organization_id})>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert assignment to dictionary"""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "role_id": str(self.role_id),
            "organization_id": str(self.organization_id),
            "assigned_by": str(self.assigned_by) if self.assigned_by else None,
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_active": self.is_active,
            "role": self.role.to_dict() if self.role else None
        }

    def is_expired(self) -> bool:
        """Check if role assignment has expired"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at


# Association tables for many-to-many relationships

# Role-Permission association table
role_permissions = Table(
    'role_permissions',
    Base.metadata,
    Column('role_id', UUID(as_uuid=True), ForeignKey('roles.id'), primary_key=True),
    Column('permission_id', UUID(as_uuid=True), ForeignKey('permissions.id'), primary_key=True),
    Column('granted_at', DateTime(timezone=True), server_default=func.now()),
    Column('granted_by', UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
)


# Predefined system permissions
SYSTEM_PERMISSIONS = [
    # Organization permissions
    ("organization_read", "Read Organization", "View organization details and settings",
     PermissionCategory.ORGANIZATION, PermissionScope.READ),
    ("organization_update", "Update Organization", "Modify organization settings and configuration",
     PermissionCategory.ORGANIZATION, PermissionScope.WRITE),
    ("organization_delete", "Delete Organization", "Delete organization and all associated data",
     PermissionCategory.ORGANIZATION, PermissionScope.DELETE),
    ("organization_create", "Create Organization", "Create new organizations",
     PermissionCategory.ORGANIZATION, PermissionScope.WRITE),

    # User management permissions
    ("user_read", "Read Users", "View user profiles and information",
     PermissionCategory.USER_MANAGEMENT, PermissionScope.READ),
    ("user_create", "Create Users", "Create new user accounts",
     PermissionCategory.USER_MANAGEMENT, PermissionScope.WRITE),
    ("user_update", "Update Users", "Modify user profiles and settings",
     PermissionCategory.USER_MANAGEMENT, PermissionScope.WRITE),
    ("user_delete", "Delete Users", "Delete user accounts",
     PermissionCategory.USER_MANAGEMENT, PermissionScope.DELETE),
    ("user_manage_roles", "Manage User Roles", "Assign and revoke user roles",
     PermissionCategory.USER_MANAGEMENT, PermissionScope.MANAGE),

    # Document permissions
    ("document_read", "Read Documents", "View and access documents",
     PermissionCategory.DOCUMENTS, PermissionScope.READ),
    ("document_create", "Create Documents", "Upload and create new documents",
     PermissionCategory.DOCUMENTS, PermissionScope.WRITE),
    ("document_update", "Update Documents", "Modify existing documents",
     PermissionCategory.DOCUMENTS, PermissionScope.WRITE),
    ("document_delete", "Delete Documents", "Remove documents",
     PermissionCategory.DOCUMENTS, PermissionScope.DELETE),
    ("document_share", "Share Documents", "Share documents with other users",
     PermissionCategory.DOCUMENTS, PermissionScope.WRITE),

    # Analytics permissions
    ("analytics_read", "Read Analytics", "View analytics reports and dashboards",
     PermissionCategory.ANALYTICS, PermissionScope.READ),
    ("analytics_export", "Export Analytics", "Export analytics data",
     PermissionCategory.ANALYTICS, PermissionScope.READ),
    ("analytics_manage", "Manage Analytics", "Configure analytics settings",
     PermissionCategory.ANALYTICS, PermissionScope.MANAGE),

    # System permissions
    ("system_admin", "System Administrator", "Full system access",
     PermissionCategory.SYSTEM, PermissionScope.ADMIN),
    ("system_health", "System Health", "View system health and status",
     PermissionCategory.SYSTEM, PermissionScope.READ),
    ("system_logs", "System Logs", "View system logs and diagnostics",
     PermissionCategory.SYSTEM, PermissionScope.READ),

    # API permissions
    ("api_read", "Read API", "Access API endpoints for reading data",
     PermissionCategory.API, PermissionScope.READ),
    ("api_write", "Write API", "Access API endpoints for writing data",
     PermissionCategory.API, PermissionScope.WRITE),
    ("api_delete", "Delete API", "Access API endpoints for deleting data",
     PermissionCategory.API, PermissionScope.DELETE),

    # Billing permissions
    ("billing_read", "Read Billing", "View billing information and invoices",
     PermissionCategory.BILLING, PermissionScope.READ),
    ("billing_manage", "Manage Billing", "Manage billing settings and subscriptions",
     PermissionCategory.BILLING, PermissionScope.MANAGE),

    # Audit permissions
    ("audit_read", "Read Audit Logs", "View audit logs and compliance reports",
     PermissionCategory.AUDIT, PermissionScope.READ),
    ("audit_manage", "Manage Audit", "Configure audit settings and retention",
     PermissionCategory.AUDIT, PermissionScope.MANAGE)
]


# Predefined system roles
SYSTEM_ROLES = [
    ("super_admin", "Super Administrator", "Full system access across all organizations", 1000),
    ("admin", "Administrator", "Full organizational access", 800),
    ("content_manager", "Content Manager", "Manage documents and content", 600),
    ("analyst", "Analyst", "View analytics and reports", 400),
    ("user", "User", "Basic user access", 200),
    ("viewer", "Viewer", "Read-only access", 100)
]