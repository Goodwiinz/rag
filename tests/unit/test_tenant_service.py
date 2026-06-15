"""
Unit tests for Tenant Service
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from src.services.security.tenant_service import TenantService, get_tenant_service, check_tenant_permission
from src.models.organization import Organization, StorageTier


class TestTenantService:
    """Test tenant management operations"""

    def test_create_organization(self):
        """Test creating a new organization"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        service = TenantService(db=mock_db)
        
        with patch.object(service, 'db', mock_db):
            org = service.create_organization("Test Org", StorageTier.FREE)
        
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
    
    def test_create_organization_duplicate_name(self):
        """Test creating organization with duplicate name raises error"""
        mock_db = MagicMock()
        existing_org = Organization(name="Test Org")
        mock_db.query.return_value.filter.return_value.first.return_value = existing_org
        
        service = TenantService(db=mock_db)
        
        with pytest.raises(Exception):
            service.create_organization("Test Org")
    
    def test_get_organization_not_found(self):
        """Test getting non-existent organization raises error"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        service = TenantService(db=mock_db)
        
        with patch.object(service, 'db', mock_db):
            with patch('src.middleware.multi_tenancy.validate_tenant_access', return_value=True):
                with pytest.raises(Exception):
                    service.get_organization("non-existent-id")
    
    def test_get_storage_quota_status(self):
        """Test getting storage quota status"""
        mock_db = MagicMock()
        mock_org = MagicMock()
        mock_org.storage_used_gb = 5.0
        mock_org.storage_limit_gb = 10.0
        mock_org.storage_percentage_used = 50.0
        mock_org.storage_tier = StorageTier.PROFESSIONAL
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_org
        
        service = TenantService(db=mock_db)
        
        with patch.object(service, 'db', mock_db):
            with patch('src.middleware.multi_tenancy.validate_tenant_access', return_value=True):
                quota = service.get_storage_quota_status("org-123")
        
        assert "limits_status" in quota
        assert quota["limits_status"]["storage"]["percentage"] == 50.0
    
    def test_upgrade_storage_tier(self):
        """Test upgrading storage tier"""
        mock_db = MagicMock()
        mock_org = MagicMock()
        mock_org.storage_tier = StorageTier.FREE
        mock_org.storage_used_bytes = 0
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_org
        
        service = TenantService(db=mock_db)
        
        with patch.object(service, 'db', mock_db):
            with patch('src.middleware.multi_tenancy.validate_tenant_access', return_value=True):
                result = service.upgrade_storage_tier("org-123", StorageTier.PROFESSIONAL)
        
        mock_db.commit.assert_called()
    
    def test_validate_organization_limits(self):
        """Test validating organization limits"""
        mock_db = MagicMock()
        mock_org = MagicMock()
        mock_org.storage_tier = StorageTier.FREE
        mock_org.storage_used_gb = 1.0
        mock_org.storage_limit_gb = 5.0
        mock_org.storage_percentage_used = 20.0
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_org
        mock_db.query.return_value.filter.return_value.scalar.side_effect = [3, 50]  # user_count, doc_count
        
        service = TenantService(db=mock_db)
        
        with patch.object(service, 'db', mock_db):
            with patch('src.middleware.multi_tenancy.validate_tenant_access', return_value=True):
                result = service.validate_organization_limits("org-123")
        
        assert result["overall_status"] == "ok"
        assert "limits_status" in result
    
    def test_tenant_permission_check(self):
        """Test tenant permission checking"""
        with patch('src.middleware.multi_tenancy.get_current_user_role', return_value="admin"):
            with patch('src.middleware.multi_tenancy.get_current_tenant_id', return_value="tenant-123"):
                assert check_tenant_permission("organization_read", "tenant-123") == True
        
        with patch('src.middleware.multi_tenancy.get_current_user_role', return_value="user"):
            with patch('src.middleware.multi_tenancy.get_current_tenant_id', return_value="tenant-123"):
                assert check_tenant_permission("organization_update", "tenant-123") == False


class TestTenantServiceEdgeCases:
    """Test edge cases and error handling"""

    def test_storage_quota_exceeded(self):
        """Test when storage quota is exceeded"""
        mock_db = MagicMock()
        mock_org = MagicMock()
        mock_org.storage_used_gb = 9.5
        mock_org.storage_limit_gb = 10.0
        mock_org.storage_percentage_used = 95.0
        mock_org.storage_tier = StorageTier.FREE
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_org
        mock_db.query.return_value.filter.return_value.scalar.side_effect = [5, 100]  # At limits
        
        service = TenantService(db=mock_db)
        
        with patch.object(service, 'db', mock_db):
            with patch('src.middleware.multi_tenancy.validate_tenant_access', return_value=True):
                result = service.validate_organization_limits("org-123")
        
        assert result["limits_status"]["storage"]["status"] == "warning"
        assert result["limits_status"]["users"]["status"] == "exceeded"
        assert result["limits_status"]["documents"]["status"] == "exceeded"
        assert result["overall_status"] == "error"
    
    def test_tenant_service_context_manager(self):
        """Test using TenantService as context manager"""
        mock_db = MagicMock()
        
        with TenantService(db=mock_db) as service:
            assert service.db == mock_db
        
        mock_db.close.assert_called_once()
    
    def test_unauthorized_tenant_access(self):
        """Test accessing unauthorized tenant"""
        mock_db = MagicMock()
        
        service = TenantService(db=mock_db)
        
        with patch('src.middleware.multi_tenancy.validate_tenant_access', return_value=False):
            with patch('src.middleware.multi_tenancy.get_current_user_role', return_value="user"):
                with pytest.raises(Exception):
                    service.get_organization("unauthorized-tenant")


class TestTenantServiceGetters:
    """Test getter methods"""

    def test_get_user_count(self):
        """Test getting user count"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.scalar.return_value = 10
        
        service = TenantService(db=mock_db)
        
        with patch.object(service, 'db', mock_db):
            with patch('src.middleware.multi_tenancy.validate_tenant_access', return_value=True):
                count = service.get_user_count("org-123")
        
        assert count == 10
    
    def test_get_organization_users(self):
        """Test getting organization users"""
        mock_db = MagicMock()
        mock_users = [MagicMock(), MagicMock()]
        mock_db.query.return_value.filter.return_value.offset.return_value.limit.return_value.all.return_value = mock_users
        
        service = TenantService(db=mock_db)
        
        with patch.object(service, 'db', mock_db):
            with patch('src.middleware.multi_tenancy.validate_tenant_access', return_value=True):
                users = service.get_organization_users("org-123", limit=10)
        
        assert len(users) == 2
    
    def test_get_organization_analytics(self):
        """Test getting organization analytics"""
        mock_db = MagicMock()
        mock_org = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_org
        mock_db.query.return_value.filter.return_value.scalar.side_effect = [100, 50]
        
        service = TenantService(db=mock_db)
        
        with patch.object(service, 'db', mock_db):
            with patch('src.middleware.multi_tenancy.validate_tenant_access', return_value=True):
                analytics = service.get_organization_analytics("org-123", days=30)
        
        assert analytics["period_days"] == 30
        assert "daily_averages" in analytics
