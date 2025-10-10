"""
Comprehensive tests for RBAC service
Tests role and permission management, user assignments, and access control
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from src.services.rbac_service import RBACService, check_permission, require_permission
from src.models.permission import (
    Permission, Role, UserRoleAssignment, PermissionCategory, PermissionScope,
    SYSTEM_PERMISSIONS, SYSTEM_ROLES
)
from src.models.user import User
from src.models.organization import Organization
from src.exceptions.analytics_exceptions import (
    PermissionDeniedException,
    ConfigurationException
)


class TestRBACService:
    """Test RBAC service functionality"""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        db = Mock(spec=Session)
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.filter.return_value.all.return_value = []
        db.query.return_value.count.return_value = 0
        db.add = Mock()
        db.commit = Mock()
        db.flush = Mock()
        db.refresh = Mock()
        db.rollback = Mock()
        db.execute = Mock()
        return db

    @pytest.fixture
    def rbac_service(self, mock_db):
        """Create RBAC service instance"""
        return RBACService(mock_db)

    @pytest.fixture
    def mock_organization(self):
        """Create mock organization"""
        org = Mock(spec=Organization)
        org.id = "org-123"
        org.name = "Test Organization"
        return org

    @pytest.fixture
    def mock_user(self):
        """Create mock user"""
        user = Mock(spec=User)
        user.id = "user-123"
        user.email = "test@example.com"
        user.first_name = "Test"
        user.last_name = "User"
        return user

    @pytest.fixture
    def mock_permission(self):
        """Create mock permission"""
        permission = Mock(spec=Permission)
        permission.id = "perm-123"
        permission.name = "document_read"
        permission.display_name = "Read Documents"
        permission.description = "View documents"
        permission.category = PermissionCategory.DOCUMENTS
        permission.scope = PermissionScope.READ
        permission.is_system = False
        permission.is_active = True
        return permission

    @pytest.fixture
    def mock_role(self, mock_organization):
        """Create mock role"""
        role = Mock(spec=Role)
        role.id = "role-123"
        role.name = "content_manager"
        role.display_name = "Content Manager"
        role.description = "Manage content"
        role.organization_id = str(mock_organization.id)
        role.is_system = False
        role.is_active = True
        role.priority = 500
        role.permissions = []
        return role

    def test_initialize_system_permissions_new(self, rbac_service, mock_db):
        """Test initializing system permissions when none exist"""
        # Mock no existing permissions
        mock_db.query.return_value.filter.return_value.count.return_value = 0

        result = rbac_service.initialize_system_permissions()

        assert result is True
        assert mock_db.add.call_count == len(SYSTEM_PERMISSIONS)
        mock_db.commit.assert_called_once()

    def test_initialize_system_permissions_existing(self, rbac_service, mock_db):
        """Test initializing system permissions when some exist"""
        # Mock existing permissions
        mock_db.query.return_value.filter.return_value.count.return_value = 5

        result = rbac_service.initialize_system_permissions()

        assert result is True
        mock_db.add.assert_not_called()  # Should not add new permissions
        mock_db.commit.assert_not_called()

    def test_initialize_system_roles_new_org(self, rbac_service, mock_db, mock_organization):
        """Test initializing system roles for new organization"""
        # Mock system permissions
        mock_permission = Mock()
        mock_permission.name = "document_read"
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_permission]

        # Mock no existing roles
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = rbac_service.initialize_system_roles(str(mock_organization.id))

        assert result is True
        assert mock_db.add.call_count == len(SYSTEM_ROLES)
        mock_db.commit.assert_called_once()

    def test_create_role_success(self, rbac_service, mock_db, mock_organization, mock_permission):
        """Test successful role creation"""
        # Mock permission query
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_permission]

        # Mock no existing role
        mock_db.query.return_value.filter.return_value.first.return_value = None

        role = rbac_service.create_role(
            organization_id=str(mock_organization.id),
            name="custom_role",
            display_name="Custom Role",
            description="Custom role description",
            permission_names=["document_read"],
            priority=300
        )

        assert role is not None
        mock_db.add.assert_called()
        mock_db.commit.assert_called_once()

    def test_create_role_name_exists(self, rbac_service, mock_db, mock_organization):
        """Test role creation with existing name"""
        # Mock existing role
        existing_role = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = existing_role

        with pytest.raises(ConfigurationException):
            rbac_service.create_role(
                organization_id=str(mock_organization.id),
                name="existing_role",
                display_name="Existing Role"
            )

        mock_db.rollback.assert_called_once()

    def test_assign_permissions_to_role_success(self, rbac_service, mock_db, mock_permission):
        """Test successful permission assignment to role"""
        role_id = "role-123"
        permission_names = ["document_read"]

        # Mock role exists
        mock_role = Mock()
        mock_role.id = role_id
        mock_db.query.return_value.filter.return_value.first.return_value = mock_role

        # Mock permissions exist
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_permission]

        # Mock no existing assignment
        mock_db.execute.return_value.fetchone.return_value = None

        result = rbac_service.assign_permissions_to_role(role_id, permission_names)

        assert result is True
        mock_db.execute.assert_called()
        mock_db.commit.assert_called_once()

    def test_assign_permissions_to_role_not_found(self, rbac_service, mock_db):
        """Test assigning permissions to non-existent role"""
        role_id = "nonexistent-role"
        permission_names = ["document_read"]

        # Mock role doesn't exist
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ConfigurationException):
            rbac_service.assign_permissions_to_role(role_id, permission_names)

    def test_assign_role_to_user_success(self, rbac_service, mock_db, mock_role):
        """Test successful role assignment to user"""
        user_id = "user-123"
        role_id = str(mock_role.id)
        organization_id = str(mock_role.organization_id)

        # Mock role exists and belongs to organization
        mock_db.query.return_value.filter.return_value.first.return_value = mock_role

        # Mock no existing assignment
        mock_db.query.return_value.filter.return_value.first.return_value = None

        assignment = rbac_service.assign_role_to_user(
            user_id=user_id,
            role_id=role_id,
            organization_id=organization_id,
            assigned_by="admin-123"
        )

        assert assignment is not None
        mock_db.add.assert_called()
        mock_db.commit.assert_called_once()

    def test_assign_role_to_user_wrong_org(self, rbac_service, mock_db, mock_role):
        """Test role assignment with wrong organization"""
        user_id = "user-123"
        role_id = str(mock_role.id)
        wrong_org_id = "wrong-org-123"

        # Mock role exists but belongs to different organization
        mock_db.query.return_value.filter.return_value.first.return_value = mock_role

        with pytest.raises(ConfigurationException):
            rbac_service.assign_role_to_user(
                user_id=user_id,
                role_id=role_id,
                organization_id=wrong_org_id
            )

    def test_revoke_role_from_user_success(self, rbac_service, mock_db):
        """Test successful role revocation from user"""
        user_id = "user-123"
        role_id = "role-123"
        organization_id = "org-123"

        # Mock existing assignment
        mock_assignment = Mock(spec=UserRoleAssignment)
        mock_assignment.is_active = True
        mock_db.query.return_value.filter.return_value.first.return_value = mock_assignment

        result = rbac_service.revoke_role_from_user(user_id, role_id, organization_id)

        assert result is True
        assert mock_assignment.is_active is False
        mock_db.commit.assert_called_once()

    def test_revoke_role_from_user_not_found(self, rbac_service, mock_db):
        """Test revoking non-existent role assignment"""
        user_id = "user-123"
        role_id = "role-123"
        organization_id = "org-123"

        # Mock no existing assignment
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = rbac_service.revoke_role_from_user(user_id, role_id, organization_id)

        assert result is False

    def test_get_user_permissions(self, rbac_service, mock_db):
        """Test getting user permissions"""
        user_id = "user-123"
        organization_id = "org-123"

        # Mock role assignments with permissions
        mock_permission = Mock()
        mock_permission.name = "document_read"
        mock_permission.is_active = True

        mock_role = Mock()
        mock_role.is_active = True
        mock_role.permissions = [mock_permission]

        mock_assignment = Mock(spec=UserRoleAssignment)
        mock_assignment.role = mock_role
        mock_assignment.is_active = True
        mock_assignment.expires_at = None

        mock_db.query.return_value.options.return_value.filter.return_value.all.return_value = [mock_assignment]

        permissions = rbac_service.get_user_permissions(user_id, organization_id)

        assert "document_read" in permissions
        assert len(permissions) == 1

    def test_user_has_permission_true(self, rbac_service, mock_db):
        """Test user has permission check - positive case"""
        user_id = "user-123"
        permission_name = "document_read"
        organization_id = "org-123"

        # Mock permission exists
        with patch.object(rbac_service, 'get_user_permissions', return_value={"document_read"}):
            result = rbac_service.user_has_permission(user_id, permission_name, organization_id)

        assert result is True

    def test_user_has_permission_false(self, rbac_service, mock_db):
        """Test user has permission check - negative case"""
        user_id = "user-123"
        permission_name = "document_delete"
        organization_id = "org-123"

        # Mock permission doesn't exist
        with patch.object(rbac_service, 'get_user_permissions', return_value={"document_read"}):
            result = rbac_service.user_has_permission(user_id, permission_name, organization_id)

        assert result is False

    def test_user_has_any_permission_true(self, rbac_service, mock_db):
        """Test user has any permission check - positive case"""
        user_id = "user-123"
        permission_names = ["document_read", "document_delete"]
        organization_id = "org-123"

        with patch.object(rbac_service, 'get_user_permissions', return_value={"document_read"}):
            result = rbac_service.user_has_any_permission(user_id, permission_names, organization_id)

        assert result is True

    def test_user_has_all_permissions_true(self, rbac_service, mock_db):
        """Test user has all permissions check - positive case"""
        user_id = "user-123"
        permission_names = ["document_read", "document_write"]
        organization_id = "org-123"

        with patch.object(rbac_service, 'get_user_permissions', return_value={"document_read", "document_write"}):
            result = rbac_service.user_has_all_permissions(user_id, permission_names, organization_id)

        assert result is True

    def test_user_has_all_permissions_false(self, rbac_service, mock_db):
        """Test user has all permissions check - negative case"""
        user_id = "user-123"
        permission_names = ["document_read", "document_delete"]
        organization_id = "org-123"

        with patch.object(rbac_service, 'get_user_permissions', return_value={"document_read"}):
            result = rbac_service.user_has_all_permissions(user_id, permission_names, organization_id)

        assert result is False

    def test_get_user_roles(self, rbac_service, mock_db):
        """Test getting user roles"""
        user_id = "user-123"
        organization_id = "org-123"

        # Mock role assignments
        mock_role1 = Mock()
        mock_role1.name = "admin"
        mock_role1.priority = 800
        mock_role1.is_active = True

        mock_role2 = Mock()
        mock_role2.name = "user"
        mock_role2.priority = 200
        mock_role2.is_active = True

        mock_assignment1 = Mock(spec=UserRoleAssignment)
        mock_assignment1.role = mock_role1
        mock_assignment1.is_active = True
        mock_assignment1.expires_at = None

        mock_assignment2 = Mock(spec=UserRoleAssignment)
        mock_assignment2.role = mock_role2
        mock_assignment2.is_active = True
        mock_assignment2.expires_at = None

        mock_db.query.return_value.options.return_value.filter.return_value.all.return_value = [
            mock_assignment2, mock_assignment1  # Intentionally out of order
        ]

        roles = rbac_service.get_user_roles(user_id, organization_id)

        assert len(roles) == 2
        assert roles[0].name == "admin"  # Higher priority first
        assert roles[1].name == "user"

    def test_get_organization_roles(self, rbac_service, mock_db):
        """Test getting organization roles"""
        organization_id = "org-123"

        mock_role1 = Mock()
        mock_role1.priority = 800

        mock_role2 = Mock()
        mock_role2.priority = 200

        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            mock_role2, mock_role1  # Database returns in priority order
        ]

        roles = rbac_service.get_organization_roles(organization_id)

        assert len(roles) == 2
        mock_db.query.return_value.filter.assert_called()

    def test_get_users_with_role(self, rbac_service, mock_db):
        """Test getting users with specific role"""
        role_id = "role-123"
        organization_id = "org-123"

        mock_user = Mock()
        mock_user.id = "user-123"
        mock_user.email = "test@example.com"

        mock_assignment = Mock(spec=UserRoleAssignment)
        mock_assignment.user = mock_user
        mock_assignment.is_active = True
        mock_assignment.expires_at = None

        mock_db.query.return_value.options.return_value.filter.return_value.all.return_value = [mock_assignment]

        users = rbac_service.get_users_with_role(role_id, organization_id)

        assert len(users) == 1
        assert users[0].id == "user-123"

    def test_cleanup_expired_assignments(self, rbac_service, mock_db):
        """Test cleanup of expired assignments"""
        # Mock expired assignments exist
        mock_db.query.return_value.filter.return_value.update.return_value = 5

        expired_count = rbac_service.cleanup_expired_assignments()

        assert expired_count == 5
        mock_db.commit.assert_called_once()

    def test_get_permission_categories(self, rbac_service, mock_db):
        """Test getting permission categories"""
        mock_permission = Mock()
        mock_permission.category = "documents"
        mock_permission.to_dict.return_value = {
            "id": "perm-123",
            "name": "document_read",
            "category": "documents"
        }

        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_permission]

        categories = rbac_service.get_permission_categories()

        assert len(categories) == 1
        assert categories[0]["category"] == "documents"
        assert len(categories[0]["permissions"]) == 1


class TestRBACUtilityFunctions:
    """Test RBAC utility functions"""

    def test_check_permission_success(self):
        """Test successful permission check"""
        user_id = "user-123"
        permission_name = "document_read"
        organization_id = "org-123"

        with patch('src.services.rbac_service.RBACService') as mock_rbac_class:
            mock_rbac = Mock()
            mock_rbac.user_has_permission.return_value = True
            mock_rbac_class.return_value.__enter__.return_value = mock_rbac

            result = check_permission(user_id, permission_name, organization_id)

        assert result is True
        mock_rbac.user_has_permission.assert_called_once_with(user_id, permission_name, organization_id)

    def test_check_permission_failure(self):
        """Test failed permission check"""
        user_id = "user-123"
        permission_name = "document_delete"
        organization_id = "org-123"

        with patch('src.services.rbac_service.RBACService') as mock_rbac_class:
            mock_rbac = Mock()
            mock_rbac.user_has_permission.return_value = False
            mock_rbac_class.return_value.__enter__.return_value = mock_rbac

            result = check_permission(user_id, permission_name, organization_id)

        assert result is False

    def test_require_permission_decorator_success(self):
        """Test require_permission decorator - success case"""
        permission_name = "document_read"

        with patch('src.services.rbac_service.get_current_user_id', return_value="user-123"), \
             patch('src.services.rbac_service.get_current_tenant_id', return_value="org-123"), \
             patch('src.services.rbac_service.RBACService') as mock_rbac_class:

            mock_rbac = Mock()
            mock_rbac.user_has_permission.return_value = True
            mock_rbac_class.return_value.__enter__.return_value = mock_rbac

            @require_permission(permission_name)
            def test_function():
                return "success"

            result = test_function()

        assert result == "success"

    def test_require_permission_decorator_failure(self):
        """Test require_permission decorator - failure case"""
        permission_name = "document_delete"

        with patch('src.services.rbac_service.get_current_user_id', return_value="user-123"), \
             patch('src.services.rbac_service.get_current_tenant_id', return_value="org-123"), \
             patch('src.services.rbac_service.RBACService') as mock_rbac_class:

            mock_rbac = Mock()
            mock_rbac.user_has_permission.return_value = False
            mock_rbac_class.return_value.__enter__.return_value = mock_rbac

            @require_permission(permission_name)
            def test_function():
                return "success"

            with pytest.raises(PermissionDeniedException):
                test_function()

    def test_require_permission_decorator_no_auth(self):
        """Test require_permission decorator - no authentication"""
        permission_name = "document_read"

        with patch('src.services.rbac_service.get_current_user_id', return_value=None), \
             patch('src.services.rbac_service.get_current_tenant_id', return_value="org-123"):

            @require_permission(permission_name)
            def test_function():
                return "success"

            with pytest.raises(PermissionDeniedException):
                test_function()


class TestRBACIntegration:
    """Integration tests for RBAC system"""

    def test_end_to_end_role_assignment_and_permission_check(self):
        """Test complete workflow from role assignment to permission check"""
        user_id = "user-123"
        organization_id = "org-123"
        role_name = "content_manager"
        permission_name = "document_read"

        with patch('src.services.rbac_service.RBACService') as mock_rbac_class:
            mock_rbac = Mock()
            mock_permission = Mock()
            mock_permission.name = permission_name
            mock_permission.is_active = True

            mock_role = Mock()
            mock_role.name = role_name
            mock_role.is_active = True
            mock_role.permissions = [mock_permission]

            mock_assignment = Mock()
            mock_assignment.role = mock_role
            mock_assignment.is_active = True
            mock_assignment.expires_at = None

            mock_rbac.get_user_permissions.return_value = {permission_name}
            mock_rbac.get_user_roles.return_value = [mock_role]
            mock_rbac_class.return_value.__enter__.return_value = mock_rbac

            # Test permission check
            rbac_service = RBACService()
            has_permission = rbac_service.user_has_permission(user_id, permission_name, organization_id)

            # Test role retrieval
            roles = rbac_service.get_user_roles(user_id, organization_id)

        assert has_permission is True
        assert len(roles) == 1
        assert roles[0].name == role_name

    def test_multiple_role_permission_merge(self):
        """Test permission merging from multiple roles"""
        user_id = "user-123"
        organization_id = "org-123"

        with patch('src.services.rbac_service.RBACService') as mock_rbac_class:
            mock_rbac = Mock()

            # Create multiple roles with different permissions
            mock_permission1 = Mock()
            mock_permission1.name = "document_read"
            mock_permission1.is_active = True

            mock_permission2 = Mock()
            mock_permission2.name = "document_write"
            mock_permission2.is_active = True

            mock_role1 = Mock()
            mock_role1.name = "reader"
            mock_role1.is_active = True
            mock_role1.permissions = [mock_permission1]

            mock_role2 = Mock()
            mock_role2.name = "writer"
            mock_role2.is_active = True
            mock_role2.permissions = [mock_permission2]

            mock_assignment1 = Mock()
            mock_assignment1.role = mock_role1
            mock_assignment1.is_active = True
            mock_assignment1.expires_at = None

            mock_assignment2 = Mock()
            mock_assignment2.role = mock_role2
            mock_assignment2.is_active = True
            mock_assignment2.expires_at = None

            mock_rbac.get_user_permissions.return_value = {"document_read", "document_write"}
            mock_rbac.get_user_roles.return_value = [mock_role1, mock_role2]
            mock_rbac_class.return_value.__enter__.return_value = mock_rbac

            rbac_service = RBACService()
            permissions = rbac_service.get_user_permissions(user_id, organization_id)
            roles = rbac_service.get_user_roles(user_id, organization_id)

        assert "document_read" in permissions
        assert "document_write" in permissions
        assert len(roles) == 2

    def test_expired_role_assignment_exclusion(self):
        """Test that expired role assignments are excluded"""
        user_id = "user-123"
        organization_id = "org-123"

        with patch('src.services.rbac_service.RBACService') as mock_rbac_class:
            mock_rbac = Mock()

            # Create expired assignment
            expired_time = datetime.utcnow() - timedelta(days=1)
            mock_assignment = Mock()
            mock_assignment.role = Mock()
            mock_assignment.is_active = True
            mock_assignment.expires_at = expired_time

            mock_rbac.get_user_permissions.return_value = set()
            mock_rbac.get_user_roles.return_value = []
            mock_rbac_class.return_value.__enter__.return_value = mock_rbac

            rbac_service = RBACService()
            permissions = rbac_service.get_user_permissions(user_id, organization_id)
            roles = rbac_service.get_user_roles(user_id, organization_id)

        assert len(permissions) == 0
        assert len(roles) == 0


if __name__ == "__main__":
    pytest.main([__file__])