"""
Unit tests for RBAC Service
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from src.services.security.rbac_service import RBACService, get_rbac_service, check_permission


class TestRBACService:
    """Test RBAC service operations"""

    def test_initialize_system_permissions(self):
        """Test initializing system permissions"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.count.return_value = 0
        
        service = RBACService(db=mock_db)
        
        with patch('src.models.permission.SYSTEM_PERMISSIONS', [
            ('perm1', 'Permission 1', 'Desc 1', 'cat1', 'scope1'),
            ('perm2', 'Permission 2', 'Desc 2', 'cat2', 'scope2'),
        ]):
            result = service.initialize_system_permissions()
        
        assert result == True
        mock_db.commit.assert_called_once()
    
    def test_initialize_system_permissions_already_exists(self):
        """Test when permissions already exist"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.count.return_value = 5
        
        service = RBACService(db=mock_db)
        
        result = service.initialize_system_permissions()
        
        assert result == True
        mock_db.commit.assert_not_called()
    
    def test_create_role(self):
        """Test creating a custom role"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        service = RBACService(db=mock_db)
        
        with patch('src.models.permission.SYSTEM_PERMISSIONS', []):
            role = service.create_role(
                "org-123", "custom_role", "Custom Role", "A custom role"
            )
        
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
    
    def test_create_role_duplicate(self):
        """Test creating duplicate role raises error"""
        mock_db = MagicMock()
        mock_existing = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_existing
        
        service = RBACService(db=mock_db)
        
        with pytest.raises(Exception):
            service.create_role("org-123", "existing_role", "Existing Role")
    
    def test_assign_role_to_user(self):
        """Test assigning role to user"""
        mock_db = MagicMock()
        mock_role = MagicMock()
        mock_role.id = "role-123"
        mock_role.name = "admin"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_role
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        service = RBACService(db=mock_db)
        
        assignment = service.assign_role_to_user(
            "user-123", "role-123", "org-123"
        )
        
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
    
    def test_revoke_role_from_user(self):
        """Test revoking role from user"""
        mock_db = MagicMock()
        mock_assignment = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_assignment
        
        service = RBACService(db=mock_db)
        
        result = service.revoke_role_from_user("user-123", "role-123", "org-123")
        
        assert result == True
        mock_assignment.is_active = False
        mock_db.commit.assert_called_once()
    
    def test_get_user_permissions(self):
        """Test getting user permissions"""
        mock_db = MagicMock()
        mock_perm = MagicMock()
        mock_perm.name = "document_read"
        mock_perm.is_active = True
        
        mock_role = MagicMock()
        mock_role.is_active = True
        mock_role.permissions = [mock_perm]
        
        mock_assignment = MagicMock()
        mock_assignment.role = mock_role
        mock_assignment.expires_at = None
        
        mock_db.query.return_value.options.return_value.filter.return_value.all.return_value = [mock_assignment]
        
        service = RBACService(db=mock_db)
        
        with patch('src.middleware.multi_tenancy.get_current_tenant_id', return_value="org-123"):
            perms = service.get_user_permissions("user-123", "org-123")
        
        assert "document_read" in perms
    
    def test_user_has_permission(self):
        """Test checking user permission"""
        mock_db = MagicMock()
        mock_perm = MagicMock()
        mock_perm.name = "document_read"
        mock_perm.is_active = True
        
        mock_role = MagicMock()
        mock_role.is_active = True
        mock_role.permissions = [mock_perm]
        
        mock_assignment = MagicMock()
        mock_assignment.role = mock_role
        mock_assignment.expires_at = None
        
        mock_db.query.return_value.options.return_value.filter.return_value.all.return_value = [mock_assignment]
        
        service = RBACService(db=mock_db)
        
        with patch('src.middleware.multi_tenancy.get_current_tenant_id', return_value="org-123"):
            assert service.user_has_permission("user-123", "document_read", "org-123") == True
            assert service.user_has_permission("user-123", "admin_access", "org-123") == False
    
    def test_user_has_any_permission(self):
        """Test checking if user has any of specified permissions"""
        mock_db = MagicMock()
        mock_perm = MagicMock()
        mock_perm.name = "document_read"
        mock_perm.is_active = True
        
        mock_role = MagicMock()
        mock_role.is_active = True
        mock_role.permissions = [mock_perm]
        
        mock_assignment = MagicMock()
        mock_assignment.role = mock_role
        mock_assignment.expires_at = None
        
        mock_db.query.return_value.options.return_value.filter.return_value.all.return_value = [mock_assignment]
        
        service = RBACService(db=mock_db)
        
        with patch('src.middleware.multi_tenancy.get_current_tenant_id', return_value="org-123"):
            assert service.user_has_any_permission("user-123", ["document_read", "admin_access"], "org-123") == True
            assert service.user_has_any_permission("user-123", ["admin_access"], "org-123") == False
    
    def test_user_has_all_permissions(self):
        """Test checking if user has all specified permissions"""
        mock_db = MagicMock()
        mock_perm = MagicMock()
        mock_perm.name = "document_read"
        mock_perm.is_active = True
        
        mock_role = MagicMock()
        mock_role.is_active = True
        mock_role.permissions = [mock_perm]
        
        mock_assignment = MagicMock()
        mock_assignment.role = mock_role
        mock_assignment.expires_at = None
        
        mock_db.query.return_value.options.return_value.filter.return_value.all.return_value = [mock_assignment]
        
        service = RBACService(db=mock_db)
        
        with patch('src.middleware.multi_tenancy.get_current_tenant_id', return_value="org-123"):
            assert service.user_has_all_permissions("user-123", ["document_read"], "org-123") == True
            assert service.user_has_all_permissions("user-123", ["document_read", "admin_access"], "org-123") == False


class TestRBACServiceRoleExpiration:
    """Test role expiration handling"""

    def test_expired_role_assignment(self):
        """Test that expired role assignments are not counted"""
        mock_db = MagicMock()
        mock_perm = MagicMock()
        mock_perm.name = "document_read"
        mock_perm.is_active = True
        
        mock_role = MagicMock()
        mock_role.is_active = True
        mock_role.permissions = [mock_perm]
        
        mock_assignment = MagicMock()
        mock_assignment.role = mock_role
        mock_assignment.expires_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
        
        mock_db.query.return_value.options.return_value.filter.return_value.all.return_value = [mock_assignment]
        
        service = RBACService(db=mock_db)
        
        with patch('src.middleware.multi_tenancy.get_current_tenant_id', return_value="org-123"):
            perms = service.get_user_permissions("user-123", "org-123")
        
        assert len(perms) == 0
    
    def test_cleanup_expired_assignments(self):
        """Test cleaning up expired assignments"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.update.return_value = 5
        
        service = RBACService(db=mock_db)
        
        count = service.cleanup_expired_assignments()
        
        assert count == 5
        mock_db.commit.assert_called_once()


class TestRBACServiceContextManager:
    """Test RBACService context manager"""

    def test_context_manager(self):
        """Test using RBACService as context manager"""
        mock_db = MagicMock()
        
        with RBACService(db=mock_db) as service:
            assert service.db == mock_db
        
        mock_db.close.assert_called_once()


class TestRBACServiceEdgeCases:
    """Test edge cases and error handling"""

    def test_get_user_permissions_no_org(self):
        """Test getting permissions with no organization"""
        mock_db = MagicMock()
        service = RBACService(db=mock_db)
        
        with patch('src.middleware.multi_tenancy.get_current_tenant_id', return_value=None):
            perms = service.get_user_permissions("user-123")
        
        assert perms == set()
    
    def test_get_user_roles_no_org(self):
        """Test getting roles with no organization"""
        mock_db = MagicMock()
        service = RBACService(db=mock_db)
        
        with patch('src.middleware.multi_tenancy.get_current_tenant_id', return_value=None):
            roles = service.get_user_roles("user-123")
        
        assert roles == []
    
    def test_revoke_nonexistent_role(self):
        """Test revoking a role that doesn't exist"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        service = RBACService(db=mock_db)
        
        result = service.revoke_role_from_user("user-123", "role-123", "org-123")
        
        assert result == False
    
    def test_get_organization_roles(self):
        """Test getting organization roles"""
        mock_db = MagicMock()
        mock_roles = [MagicMock(), MagicMock()]
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_roles
        
        service = RBACService(db=mock_db)
        
        roles = service.get_organization_roles("org-123")
        
        assert len(roles) == 2
    
    def test_get_permission_categories(self):
        """Test getting permission categories"""
        mock_db = MagicMock()
        mock_perm = MagicMock()
        mock_perm.category = "documents"
        mock_perm.to_dict.return_value = {"name": "document_read"}
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_perm]
        
        service = RBACService(db=mock_db)
        
        categories = service.get_permission_categories()
        
        assert len(categories) == 1
        assert categories[0]["category"] == "documents"
