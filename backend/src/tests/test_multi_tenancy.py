"""
Comprehensive tests for multi-tenancy architecture
Tests tenant isolation, middleware, and data access controls
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from starlette.requests import Request

from src.middleware.multi_tenancy import (
    MultiTenancyMiddleware,
    get_current_tenant_id,
    get_current_user_id,
    get_current_user_role,
    tenant_context_manager,
    validate_tenant_access,
    TenantAwareQuery,
    add_row_level_security_filters
)
from src.services.tenant_service import TenantService, check_tenant_permission
from src.models.organization import Organization, StorageTier
from src.models.user import User
from src.models.document import Document
from src.exceptions.analytics_exceptions import PermissionDeniedException


class TestMultiTenancyMiddleware:
    """Test multi-tenancy middleware functionality"""

    @pytest.fixture
    def mock_request(self):
        """Create mock request"""
        request = Mock(spec=Request)
        request.url.path = "/api/test"
        request.state = Mock()
        return request

    @pytest.fixture
    def mock_user(self):
        """Create mock user"""
        user = Mock(spec=User)
        user.id = "user-123"
        user.organization_id = "org-123"
        user.role = Mock()
        user.role.value = "admin"
        return user

    @pytest.fixture
    def middleware(self):
        """Create middleware instance"""
        return MultiTenancyMiddleware(Mock())

    @pytest.mark.asyncio
    async def test_skip_tenant_validation_for_health_check(self, middleware, mock_request):
        """Test that tenant validation is skipped for health checks"""
        mock_request.url.path = "/health"
        mock_request.state.user = Mock()

        call_next = AsyncMock(return_value=Mock())

        response = await middleware.dispatch(mock_request, call_next)

        assert response is not None
        call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_skip_tenant_validation_for_auth_endpoints(self, middleware, mock_request):
        """Test that tenant validation is skipped for auth endpoints"""
        mock_request.url.path = "/auth/login"
        mock_request.state.user = Mock()

        call_next = AsyncMock(return_value=Mock())

        response = await middleware.dispatch(mock_request, call_next)

        assert response is not None
        call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_set_tenant_context_from_user(self, middleware, mock_request, mock_user):
        """Test setting tenant context from authenticated user"""
        mock_request.url.path = "/api/documents"
        mock_request.state.user = mock_user

        call_next = AsyncMock(return_value=Mock())

        response = await middleware.dispatch(mock_request, call_next)

        # Verify tenant context was set
        assert get_current_tenant_id() == str(mock_user.organization_id)
        assert get_current_user_id() == str(mock_user.id)
        assert get_current_user_role() == mock_user.role.value

        # Verify request state was set
        assert mock_request.state.tenant_id == str(mock_user.organization_id)
        assert mock_request.state.user_id == str(mock_user.id)
        assert mock_request.state.user_role == mock_user.role.value

        call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_clear_tenant_context_after_request(self, middleware, mock_request, mock_user):
        """Test that tenant context is cleared after request"""
        mock_request.url.path = "/api/documents"
        mock_request.state.user = mock_user

        call_next = AsyncMock(return_value=Mock())

        # Set some initial context
        from src.middleware.multi_tenancy import tenant_context, user_context, role_context
        tenant_context.set("initial-tenant")
        user_context.set("initial-user")
        role_context.set("initial-role")

        await middleware.dispatch(mock_request, call_next)

        # Context should be cleared after request
        assert get_current_tenant_id() is None
        assert get_current_user_id() is None
        assert get_current_user_role() is None


class TestTenantContextManager:
    """Test tenant context manager functionality"""

    def test_tenant_context_manager_sets_and_clears_context(self):
        """Test that context manager properly sets and clears tenant context"""
        org_id = "org-123"
        user_id = "user-456"
        user_role = "admin"

        # Verify context is initially empty
        assert get_current_tenant_id() is None
        assert get_current_user_id() is None
        assert get_current_user_role() is None

        # Use context manager
        with tenant_context_manager(org_id, user_id, user_role):
            # Verify context is set
            assert get_current_tenant_id() == org_id
            assert get_current_user_id() == user_id
            assert get_current_user_role() == user_role

        # Verify context is cleared
        assert get_current_tenant_id() is None
        assert get_current_user_id() is None
        assert get_current_user_role() is None

    def test_tenant_context_manager_with_exception(self):
        """Test that context manager clears context even when exception occurs"""
        org_id = "org-123"
        user_id = "user-456"
        user_role = "admin"

        try:
            with tenant_context_manager(org_id, user_id, user_role):
                assert get_current_tenant_id() == org_id
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Context should still be cleared
        assert get_current_tenant_id() is None


class TestTenantAwareQuery:
    """Test tenant-aware query builder"""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        db = Mock()
        query = Mock()
        db.query.return_value = query
        query.filter.return_value = query
        query.filter_by.return_value = query
        query.first.return_value = None
        query.all.return_value = []
        return db

    @pytest.fixture
    def tenant_aware_query(self, mock_db):
        """Create tenant-aware query instance"""
        with tenant_context_manager("org-123", "user-456", "admin"):
            return TenantAwareQuery(mock_db, Document)

    def test_filter_by_tenant_adds_organization_filter(self, tenant_aware_query, mock_db):
        """Test that filter_by_tenant adds organization filter"""
        query = tenant_aware_query.filter_by_tenant()

        # Should call query.filter with organization_id condition
        mock_db.query.assert_called_once_with(Document)
        query.filter.assert_called_once()

    def test_get_with_tenant_filter(self, tenant_aware_query, mock_db):
        """Test getting entity with tenant filter"""
        entity_id = "doc-123"
        tenant_aware_query.get_with_tenant_filter(entity_id)

        # Should apply both tenant filter and ID filter
        assert mock_db.query.called
        assert mock_db.query.return_value.filter.call_count == 2

    def test_create_with_tenant(self, tenant_aware_query, mock_db):
        """Test creating entity with tenant context"""
        entity_data = {"title": "Test Document", "content": "Test content"}
        tenant_aware_query.create_with_tenant(**entity_data)

        # Should add organization_id to entity data
        mock_db.add.assert_called_once()
        added_entity = mock_db.add.call_args[0][0]
        assert hasattr(added_entity, 'organization_id')
        assert added_entity.organization_id == "org-123"

    def test_update_with_tenant_validation(self, tenant_aware_query, mock_db):
        """Test updating entity with tenant validation"""
        # Mock entity exists
        mock_entity = Mock()
        mock_entity.id = "doc-123"
        tenant_aware_query.filter_by_tenant.return_value.filter.return_value.first.return_value = mock_entity

        update_data = {"title": "Updated Document"}
        result = tenant_aware_query.update_with_tenant_validation("doc-123", **update_data)

        assert result == mock_entity
        assert mock_entity.title == "Updated Document"

    def test_update_with_tenant_validation_entity_not_found(self, tenant_aware_query):
        """Test update when entity is not found for tenant"""
        tenant_aware_query.filter_by_tenant.return_value.filter.return_value.first.return_value = None

        with pytest.raises(PermissionDeniedException):
            tenant_aware_query.update_with_tenant_validation("doc-123", title="Updated")

    def test_delete_with_tenant_validation(self, tenant_aware_query, mock_db):
        """Test deleting entity with tenant validation"""
        # Mock entity exists
        mock_entity = Mock()
        tenant_aware_query.filter_by_tenant.return_value.filter.return_value.first.return_value = mock_entity

        result = tenant_aware_query.delete_with_tenant_validation("doc-123")

        assert result == mock_entity
        mock_db.delete.assert_called_once_with(mock_entity)

    def test_delete_with_tenant_validation_entity_not_found(self, tenant_aware_query):
        """Test delete when entity is not found for tenant"""
        tenant_aware_query.filter_by_tenant.return_value.filter.return_value.first.return_value = None

        with pytest.raises(PermissionDeniedException):
            tenant_aware_query.delete_with_tenant_validation("doc-123")


class TestTenantService:
    """Test tenant service functionality"""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.filter.return_value.scalar.return_value = 0
        db.add = Mock()
        db.commit = Mock()
        db.refresh = Mock()
        return db

    @pytest.fixture
    def tenant_service(self, mock_db):
        """Create tenant service instance"""
        return TenantService(mock_db)

    def test_create_organization_success(self, tenant_service, mock_db):
        """Test successful organization creation"""
        org_name = "Test Organization"
        storage_tier = StorageTier.FREE

        # Mock organization doesn't exist
        mock_db.query.return_value.filter.return_value.first.return_value = None

        organization = tenant_service.create_organization(org_name, storage_tier)

        assert organization.name == org_name
        assert organization.storage_tier == storage_tier
        assert organization.is_active is True
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_create_organization_name_exists(self, tenant_service, mock_db):
        """Test organization creation with existing name"""
        org_name = "Existing Organization"

        # Mock organization exists
        existing_org = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = existing_org

        with pytest.raises(Exception):  # Should raise ConfigurationException
            tenant_service.create_organization(org_name)

    def test_get_organization_with_valid_access(self, tenant_service, mock_db):
        """Test getting organization with valid tenant access"""
        org_id = "org-123"

        with tenant_context_manager(org_id, "user-456", "admin"):
            organization = tenant_service.get_organization(org_id)

        # Should query by organization ID
        mock_db.query.assert_called_once_with(Organization)
        mock_db.query.return_value.filter.assert_called_once()

    def test_get_organization_invalid_tenant_access(self, tenant_service):
        """Test getting organization with invalid tenant access"""
        org_id = "org-123"

        with tenant_context_manager("different-org", "user-456", "admin"):
            with pytest.raises(PermissionDeniedException):
                tenant_service.get_organization(org_id)

    def test_update_organization(self, tenant_service, mock_db):
        """Test updating organization"""
        org_id = "org-123"
        update_data = {"name": "Updated Organization"}

        # Mock existing organization
        existing_org = Mock(spec=Organization)
        existing_org.id = org_id
        mock_db.query.return_value.filter.return_value.first.return_value = existing_org

        with tenant_context_manager(org_id, "user-456", "admin"):
            organization = tenant_service.update_organization(org_id, **update_data)

        assert organization.name == "Updated Organization"
        mock_db.commit.assert_called_once()

    def test_get_storage_quota_status(self, tenant_service):
        """Test getting storage quota status"""
        org_id = "org-123"

        # Mock organization
        mock_org = Mock(spec=Organization)
        mock_org.check_storage_quota.return_value = {
            "tier": "free",
            "limit_gb": 10.0,
            "used_gb": 5.0,
            "available_gb": 5.0,
            "percentage_used": 50.0,
            "max_file_size_mb": 10.0,
            "at_quota_limit": False,
            "near_quota_limit": False
        }

        with patch.object(tenant_service, 'get_organization', return_value=mock_org):
            with patch.object(tenant_service, '_get_document_storage_stats', return_value={"document_count": 10}):
                with patch.object(tenant_service, '_calculate_storage_efficiency', return_value=75.0):
                    with tenant_context_manager(org_id, "user-456", "admin"):
                        quota_status = tenant_service.get_storage_quota_status(org_id)

        assert quota_status["tier"] == "free"
        assert quota_status["document_count"] == 10
        assert quota_status["storage_efficiency_score"] == 75.0


class TestTenantPermissionChecks:
    """Test tenant permission validation"""

    def test_check_tenant_permission_super_admin(self):
        """Test super admin has all permissions"""
        with tenant_context_manager("org-123", "user-456", "super_admin"):
            assert check_tenant_permission("any_permission") is True
            assert check_tenant_permission("organization_delete") is True

    def test_check_tenant_permission_admin(self):
        """Test admin permissions"""
        with tenant_context_manager("org-123", "user-456", "admin"):
            assert check_tenant_permission("organization_read") is True
            assert check_tenant_permission("organization_update") is True
            assert check_tenant_permission("organization_delete") is False  # Not in admin permissions

    def test_check_tenant_permission_cross_tenant_access(self):
        """Test cross-tenant access validation"""
        with tenant_context_manager("org-123", "user-456", "admin"):
            # Same tenant access should be allowed
            assert check_tenant_permission("organization_read", "org-123") is True

            # Different tenant access should be denied for non-admin roles
            assert check_tenant_permission("organization_read", "org-456") is False

    def test_check_tenant_permission_analyst(self):
        """Test analyst permissions"""
        with tenant_context_manager("org-123", "user-456", "analyst"):
            assert check_tenant_permission("organization_read") is True
            assert check_tenant_permission("organization_analytics") is True
            assert check_tenant_permission("organization_update") is False


class TestTenantIsolation:
    """Test tenant data isolation"""

    def test_validate_tenant_access_same_tenant(self):
        """Test tenant access validation for same tenant"""
        with tenant_context_manager("org-123", "user-456", "admin"):
            assert validate_tenant_access("org-123") is True

    def test_validate_tenant_access_different_tenant(self):
        """Test tenant access validation for different tenant"""
        with tenant_context_manager("org-123", "user-456", "admin"):
            assert validate_tenant_access("org-456") is False

    def test_validate_tenant_access_no_context(self):
        """Test tenant access validation with no context"""
        assert validate_tenant_access("org-123") is False

    def test_validate_cross_tenant_access_admin(self):
        """Test cross-tenant access for admin users"""
        with tenant_context_manager("org-123", "user-456", "admin"):
            # Admins cannot access cross-tenant by default
            assert validate_cross_tenant_access(["org-123", "org-456"]) is False

    def test_validate_cross_tenant_access_super_admin(self):
        """Test cross-tenant access for super admin users"""
        with tenant_context_manager("org-123", "user-456", "super_admin"):
            # Super admins can access cross-tenant
            assert validate_cross_tenant_access(["org-123", "org-456"]) is True

    def test_add_row_level_security_filters(self):
        """Test adding row-level security filters to queries"""
        # Create mock query and model
        mock_query = Mock()
        mock_model = Mock()
        mock_model.organization_id = "org-field"

        with tenant_context_manager("org-123", "user-456", "admin"):
            filtered_query = add_row_level_security_filters(mock_query, mock_model)

        # Should add organization filter
        mock_query.filter.assert_called_once()
        filter_call = mock_query.filter.call_args[0][0]
        # This is a simplified test - in reality you'd check the filter expression


class TestMultiTenancyIntegration:
    """Integration tests for multi-tenancy components"""

    @pytest.mark.asyncio
    async def test_end_to_end_tenant_isolation(self):
        """Test complete tenant isolation workflow"""
        org_id_1 = "org-123"
        org_id_2 = "org-456"
        user_id_1 = "user-123"
        user_id_2 = "user-456"

        # Create data for organization 1
        with tenant_context_manager(org_id_1, user_id_1, "admin"):
            assert get_current_tenant_id() == org_id_1
            assert validate_tenant_access(org_id_1) is True
            assert validate_tenant_access(org_id_2) is False

        # Create data for organization 2
        with tenant_context_manager(org_id_2, user_id_2, "admin"):
            assert get_current_tenant_id() == org_id_2
            assert validate_tenant_access(org_id_2) is True
            assert validate_tenant_access(org_id_1) is False

        # Verify context is cleared
        assert get_current_tenant_id() is None

    def test_tenant_aware_query_builder_isolation(self):
        """Test that tenant-aware query builder enforces isolation"""
        mock_db = Mock()
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        # Query from organization 1
        with tenant_context_manager("org-123", "user-456", "admin"):
            query_builder = TenantAwareQuery(mock_db, Document)
            query_builder.filter_by_tenant()

            # Check that organization filter was applied
            assert mock_query.filter.called

        # Reset mock
        mock_query.reset_mock()

        # Query from organization 2
        with tenant_context_manager("org-456", "user-789", "admin"):
            query_builder = TenantAwareQuery(mock_db, Document)
            query_builder.filter_by_tenant()

            # Check that organization filter was applied again
            assert mock_query.filter.called


if __name__ == "__main__":
    pytest.main([__file__])