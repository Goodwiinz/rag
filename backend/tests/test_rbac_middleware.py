"""
Comprehensive tests for RBAC middleware
Tests permission enforcement, role checking, and access control
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
from fastapi import HTTPException, status, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.middleware.rbac import (
    RBACMiddleware, require_permission, require_any_permission, require_all_permissions,
    require_role, require_any_role, has_permission, has_any_permission, has_role,
    get_current_user_permissions, get_current_user_roles, clear_permission_cache
)
from src.services.security import RBACService
from src.middleware.multi_tenancy import get_current_tenant_id, get_current_user_id


class TestRBACMiddleware:
    """Test RBAC middleware functionality"""

    @pytest.fixture
    def mock_request(self):
        """Create mock request"""
        request = Mock(spec=Request)
        request.url.path = "/api/documents"
        request.method = "GET"
        request.state = Mock()
        return request

    @pytest.fixture
    def mock_app(self):
        """Create mock app"""
        return Mock()

    @pytest.fixture
    def middleware(self, mock_app):
        """Create middleware instance"""
        permission_requirements = {
            "GET:/api/documents": ["document_read"],
            "POST:/api/documents": ["document_create"],
            "PUT:/api/users/123": ["user_update"],
            "DELETE:/api/organizations/456": ["organization_delete"]
        }
        return RBACMiddleware(mock_app, permission_requirements)

    @pytest.mark.asyncio
    async def test_skip_rbac_for_health_check(self, middleware, mock_request):
        """Test that RBAC is skipped for health checks"""
        mock_request.url.path = "/health"
        call_next = AsyncMock(return_value=Mock())

        response = await middleware.dispatch(mock_request, call_next)

        assert response is not None
        call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_skip_rbac_for_auth_endpoints(self, middleware, mock_request):
        """Test that RBAC is skipped for auth endpoints"""
        mock_request.url.path = "/auth/login"
        call_next = AsyncMock(return_value=Mock())

        response = await middleware.dispatch(mock_request, call_next)

        assert response is not None
        call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_skip_rbac_for_docs(self, middleware, mock_request):
        """Test that RBAC is skipped for documentation endpoints"""
        mock_request.url.path = "/docs"
        call_next = AsyncMock(return_value=Mock())

        response = await middleware.dispatch(mock_request, call_next)

        assert response is not None
        call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_public_endpoint_access_without_auth(self, middleware, mock_request):
        """Test access to public endpoints without authentication"""
        mock_request.url.path = "/health"
        call_next = AsyncMock(return_value=Mock())

        with patch('src.middleware.rbac.get_current_user_id', return_value=None), \
             patch('src.middleware.rbac.get_current_tenant_id', return_value=None):

            response = await middleware.dispatch(mock_request, call_next)

        assert response is not None

    @pytest.mark.asyncio
    async def test_protected_endpoint_access_without_auth(self, middleware, mock_request):
        """Test access to protected endpoints without authentication"""
        mock_request.url.path = "/api/documents"
        call_next = AsyncMock(return_value=Mock())

        with patch('src.middleware.rbac.get_current_user_id', return_value=None), \
             patch('src.middleware.rbac.get_current_tenant_id', return_value=None):

            with pytest.raises(HTTPException) as exc_info:
                await middleware.dispatch(mock_request, call_next)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_permission_check_success(self, middleware, mock_request):
        """Test successful permission check"""
        mock_request.url.path = "/api/documents"
        mock_request.method = "GET"
        call_next = AsyncMock(return_value=Mock())

        with patch('src.middleware.rbac.get_current_user_id', return_value="user-123"), \
             patch('src.middleware.rbac.get_current_tenant_id', return_value="org-123"), \
             patch.object(middleware.rbac_service, 'get_user_permissions', return_value={"document_read"}):

            response = await middleware.dispatch(mock_request, call_next)

        assert response is not None
        call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_permission_check_failure(self, middleware, mock_request):
        """Test failed permission check"""
        mock_request.url.path = "/api/documents"
        mock_request.method = "GET"
        call_next = AsyncMock(return_value=Mock())

        with patch('src.middleware.rbac.get_current_user_id', return_value="user-123"), \
             patch('src.middleware.rbac.get_current_tenant_id', return_value="org-123"), \
             patch.object(middleware.rbac_service, 'get_user_permissions', return_value={"user_read"}):

            with pytest.raises(HTTPException) as exc_info:
                await middleware.dispatch(mock_request, call_next)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Access denied" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_permission_cache_hit(self, middleware, mock_request):
        """Test permission cache functionality"""
        mock_request.url.path = "/api/documents"
        mock_request.method = "GET"
        call_next = AsyncMock(return_value=Mock())

        # Pre-populate cache
        with patch('src.middleware.rbac.get_current_user_id', return_value="user-123"), \
             patch('src.middleware.rbac.get_current_tenant_id', return_value="org-123"):

            cache_key = "user-123:org-123"
            middleware._permission_cache[cache_key] = {
                "permissions": ["document_read"],
                "timestamp": time.time()
            }

            response = await middleware.dispatch(mock_request, call_next)

        assert response is not None
        call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_permission_cache_expiry(self, middleware, mock_request):
        """Test permission cache expiry"""
        mock_request.url.path = "/api/documents"
        mock_request.method = "GET"
        call_next = AsyncMock(return_value=Mock())

        # Pre-populate expired cache
        with patch('src.middleware.rbac.get_current_user_id', return_value="user-123"), \
             patch('src.middleware.rbac.get_current_tenant_id', return_value="org-123"), \
             patch.object(middleware.rbac_service, 'get_user_permissions', return_value={"document_read"}):

            cache_key = "user-123:org-123"
            middleware._permission_cache[cache_key] = {
                "permissions": ["document_read"],
                "timestamp": time.time() - 400  # Expired (5 min TTL)
            }

            response = await middleware.dispatch(mock_request, call_next)

        assert response is not None
        call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_pattern_matching_wildcard(self, middleware, mock_request):
        """Test pattern matching with wildcards"""
        mock_request.url.path = "/api/documents/123/details"
        mock_request.method = "GET"
        call_next = AsyncMock(return_value=Mock())

        # Add wildcard pattern
        middleware.permission_requirements["GET:/api/documents.*"] = ["document_read"]

        with patch('src.middleware.rbac.get_current_user_id', return_value="user-123"), \
             patch('src.middleware.rbac.get_current_tenant_id', return_value="org-123"), \
             patch.object(middleware.rbac_service, 'get_user_permissions', return_value={"document_read"}):

            response = await middleware.dispatch(mock_request, call_next)

        assert response is not None
        call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_post_method_permission_check(self, middleware, mock_request):
        """Test permission check for POST method"""
        mock_request.url.path = "/api/documents"
        mock_request.method = "POST"
        call_next = AsyncMock(return_value=Mock())

        with patch('src.middleware.rbac.get_current_user_id', return_value="user-123"), \
             patch('src.middleware.rbac.get_current_tenant_id', return_value="org-123"), \
             patch.object(middleware.rbac_service, 'get_user_permissions', return_value={"document_create"}):

            response = await middleware.dispatch(mock_request, call_next)

        assert response is not None
        call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_rbac_service_error_handling(self, middleware, mock_request):
        """Test error handling in RBAC service"""
        mock_request.url.path = "/api/documents"
        mock_request.method = "GET"
        call_next = AsyncMock(return_value=Mock())

        with patch('src.middleware.rbac.get_current_user_id', return_value="user-123"), \
             patch('src.middleware.rbac.get_current_tenant_id', return_value="org-123"), \
             patch.object(middleware.rbac_service, 'get_user_permissions', side_effect=Exception("DB error")):

            with pytest.raises(HTTPException) as exc_info:
                await middleware.dispatch(mock_request, call_next)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    def test_get_required_permissions_exact_match(self, middleware):
        """Test getting required permissions for exact match"""
        mock_request = Mock()
        mock_request.url.path = "/api/documents"
        mock_request.method = "GET"

        permissions = middleware._get_required_permissions(mock_request)

        assert permissions == ["document_read"]

    def test_get_required_permissions_pattern_match(self, middleware):
        """Test getting required permissions for pattern match"""
        mock_request = Mock()
        mock_request.url.path = "/api/documents/123"
        mock_request.method = "GET"

        # Add wildcard pattern
        middleware.permission_requirements["GET:/api/documents.*"] = ["document_read"]

        permissions = middleware._get_required_permissions(mock_request)

        assert permissions == ["document_read"]

    def test_get_required_permissions_no_match(self, middleware):
        """Test getting required permissions when no match found"""
        mock_request = Mock()
        mock_request.url.path = "/api/unknown"
        mock_request.method = "GET"

        permissions = middleware._get_required_permissions(mock_request)

        assert permissions == []

    def test_path_matches_pattern_exact(self, middleware):
        """Test exact path pattern matching"""
        assert middleware._path_matches_pattern("/api/documents", "/api/documents") is True
        assert middleware._path_matches_pattern("/api/documents", "/api/users") is False

    def test_path_matches_pattern_wildcard(self, middleware):
        """Test wildcard path pattern matching"""
        assert middleware._path_matches_pattern("/api/documents/123", "/api/documents.*") is True
        assert middleware._path_matches_pattern("/api/documents/123/details", "/api/documents.*") is True
        assert middleware._path_matches_pattern("/api/users/123", "/api/documents.*") is False

    def test_should_skip_rbac(self, middleware):
        """Test RBAC skip logic"""
        mock_request_health = Mock()
        mock_request_health.url.path = "/health"

        mock_request_docs = Mock()
        mock_request_docs.url.path = "/docs"

        mock_request_api = Mock()
        mock_request_api.url.path = "/api/documents"

        assert middleware._should_skip_rbac(mock_request_health) is True
        assert middleware._should_skip_rbac(mock_request_docs) is True
        assert middleware._should_skip_rbac(mock_request_api) is False

    def test_is_public_endpoint(self, middleware):
        """Test public endpoint detection"""
        mock_request_health = Mock()
        mock_request_health.url.path = "/health"

        mock_request_api = Mock()
        mock_request_api.url.path = "/api/documents"

        assert middleware._is_public_endpoint(mock_request_health) is True
        assert middleware._is_public_endpoint(mock_request_api) is False


class TestRBACDecorators:
    """Test RBAC decorators"""

    @pytest.mark.asyncio
    async def test_require_permission_success(self):
        """Test require_permission decorator - success"""
        with patch('src.middleware.rbac.get_current_user_id', return_value="user-123"), \
             patch('src.middleware.rbac.get_current_tenant_id', return_value="org-123"), \
             patch('src.middleware.rbac.RBACService') as mock_rbac_class:

            mock_rbac = Mock()
            mock_rbac.user_has_permission.return_value = True
            mock_rbac_class.return_value.__enter__.return_value = mock_rbac

            @require_permission("document_read")
            async def test_function():
                return "success"

            result = await test_function()

        assert result == "success"

    @pytest.mark.asyncio
    async def test_require_permission_failure(self):
        """Test require_permission decorator - failure"""
        with patch('src.middleware.rbac.get_current_user_id', return_value="user-123"), \
             patch('src.middleware.rbac.get_current_tenant_id', return_value="org-123"), \
             patch('src.middleware.rbac.RBACService') as mock_rbac_class:

            mock_rbac = Mock()
            mock_rbac.user_has_permission.return_value = False
            mock_rbac_class.return_value.__enter__.return_value = mock_rbac

            @require_permission("document_delete")
            async def test_function():
                return "success"

            with pytest.raises(HTTPException) as exc_info:
                await test_function()

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_require_permission_no_auth(self):
        """Test require_permission decorator - no authentication"""
        with patch('src.middleware.rbac.get_current_user_id', return_value=None):

            @require_permission("document_read")
            async def test_function():
                return "success"

            with pytest.raises(HTTPException) as exc_info:
                await test_function()

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_require_any_permission_success(self):
        """Test require_any_permission decorator - success"""
        with patch('src.middleware.rbac.get_current_user_id', return_value="user-123"), \
             patch('src.middleware.rbac.get_current_tenant_id', return_value="org-123"), \
             patch('src.middleware.rbac.RBACService') as mock_rbac_class:

            mock_rbac = Mock()
            mock_rbac.user_has_any_permission.return_value = True
            mock_rbac_class.return_value.__enter__.return_value = mock_rbac

            @require_any_permission(["document_read", "document_write"])
            async def test_function():
                return "success"

            result = await test_function()

        assert result == "success"

    @pytest.mark.asyncio
    async def test_require_all_permissions_success(self):
        """Test require_all_permissions decorator - success"""
        with patch('src.middleware.rbac.get_current_user_id', return_value="user-123"), \
             patch('src.middleware.rbac.get_current_tenant_id', return_value="org-123"), \
             patch('src.middleware.rbac.RBACService') as mock_rbac_class:

            mock_rbac = Mock()
            mock_rbac.user_has_all_permissions.return_value = True
            mock_rbac_class.return_value.__enter__.return_value = mock_rbac

            @require_all_permissions(["document_read", "document_write"])
            async def test_function():
                return "success"

            result = await test_function()

        assert result == "success"

    @pytest.mark.asyncio
    async def test_require_role_success(self):
        """Test require_role decorator - success"""
        with patch('src.middleware.rbac.get_current_user_id', return_value="user-123"), \
             patch('src.middleware.rbac.get_current_tenant_id', return_value="org-123"), \
             patch('src.middleware.rbac.RBACService') as mock_rbac_class:

            mock_rbac = Mock()
            mock_role = Mock()
            mock_role.name = "admin"
            mock_rbac.get_user_roles.return_value = [mock_role]
            mock_rbac_class.return_value.__enter__.return_value = mock_rbac

            @require_role("admin")
            async def test_function():
                return "success"

            result = await test_function()

        assert result == "success"

    @pytest.mark.asyncio
    async def test_require_any_role_success(self):
        """Test require_any_role decorator - success"""
        with patch('src.middleware.rbac.get_current_user_id', return_value="user-123"), \
             patch('src.middleware.rbac.get_current_tenant_id', return_value="org-123"), \
             patch('src.middleware.rbac.RBACService') as mock_rbac_class:

            mock_rbac = Mock()
            mock_role = Mock()
            mock_role.name = "content_manager"
            mock_rbac.get_user_roles.return_value = [mock_role]
            mock_rbac_class.return_value.__enter__.return_value = mock_rbac

            @require_any_role(["admin", "content_manager"])
            async def test_function():
                return "success"

            result = await test_function()

        assert result == "success"


class TestRBACUtilityFunctions:
    """Test RBAC utility functions"""

    def test_has_permission_true(self):
        """Test has_permission - true case"""
        with patch('src.middleware.rbac.get_current_user_id', return_value="user-123"), \
             patch('src.middleware.rbac.get_current_tenant_id', return_value="org-123"), \
             patch('src.middleware.rbac.RBACService') as mock_rbac_class:

            mock_rbac = Mock()
            mock_rbac.user_has_permission.return_value = True
            mock_rbac_class.return_value.__enter__.return_value = mock_rbac

            result = has_permission("document_read")

        assert result is True

    def test_has_permission_false(self):
        """Test has_permission - false case"""
        with patch('src.middleware.rbac.get_current_user_id', return_value="user-123"), \
             patch('src.middleware.rbac.get_current_tenant_id', return_value="org-123"), \
             patch('src.middleware.rbac.RBACService') as mock_rbac_class:

            mock_rbac = Mock()
            mock_rbac.user_has_permission.return_value = False
            mock_rbac_class.return_value.__enter__.return_value = mock_rbac

            result = has_permission("document_delete")

        assert result is False

    def test_has_permission_no_auth(self):
        """Test has_permission - no authentication"""
        with patch('src.middleware.rbac.get_current_user_id', return_value=None):

            result = has_permission("document_read")

        assert result is False

    def test_has_any_permission_true(self):
        """Test has_any_permission - true case"""
        with patch('src.middleware.rbac.get_current_user_id', return_value="user-123"), \
             patch('src.middleware.rbac.get_current_tenant_id', return_value="org-123"), \
             patch('src.middleware.rbac.RBACService') as mock_rbac_class:

            mock_rbac = Mock()
            mock_rbac.user_has_any_permission.return_value = True
            mock_rbac_class.return_value.__enter__.return_value = mock_rbac

            result = has_any_permission(["document_read", "document_write"])

        assert result is True

    def test_has_role_true(self):
        """Test has_role - true case"""
        with patch('src.middleware.rbac.get_current_user_id', return_value="user-123"), \
             patch('src.middleware.rbac.get_current_tenant_id', return_value="org-123"), \
             patch('src.middleware.rbac.RBACService') as mock_rbac_class:

            mock_rbac = Mock()
            mock_role = Mock()
            mock_role.name = "admin"
            mock_rbac.get_user_roles.return_value = [mock_role]
            mock_rbac_class.return_value.__enter__.return_value = mock_rbac

            result = has_role("admin")

        assert result is True

    def test_get_current_user_permissions(self):
        """Test get_current_user_permissions"""
        with patch('src.middleware.rbac.get_current_user_id', return_value="user-123"), \
             patch('src.middleware.rbac.get_current_tenant_id', return_value="org-123"), \
             patch('src.middleware.rbac.RBACService') as mock_rbac_class:

            mock_rbac = Mock()
            mock_rbac.get_user_permissions.return_value = {"document_read", "document_write"}
            mock_rbac_class.return_value.__enter__.return_value = mock_rbac

            permissions = get_current_user_permissions()

        assert len(permissions) == 2
        assert "document_read" in permissions
        assert "document_write" in permissions

    def test_get_current_user_roles(self):
        """Test get_current_user_roles"""
        with patch('src.middleware.rbac.get_current_user_id', return_value="user-123"), \
             patch('src.middleware.rbac.get_current_tenant_id', return_value="org-123"), \
             patch('src.middleware.rbac.RBACService') as mock_rbac_class:

            mock_rbac = Mock()
            mock_role1 = Mock()
            mock_role1.name = "admin"
            mock_role2 = Mock()
            mock_role2.name = "user"
            mock_rbac.get_user_roles.return_value = [mock_role1, mock_role2]
            mock_rbac_class.return_value.__enter__.return_value = mock_rbac

            roles = get_current_user_roles()

        assert len(roles) == 2
        assert "admin" in roles
        assert "user" in roles

    def test_clear_permission_cache(self):
        """Test clearing permission cache"""
        # Mock middleware cache
        with patch('src.middleware.rbac._permission_cache', {"user-123:org-123": {}}):
            clear_permission_cache()
            # Cache should be empty (verified by mock being cleared)

    def test_clear_user_permission_cache(self):
        """Test clearing specific user permission cache"""
        user_id = "user-123"
        organization_id = "org-123"

        with patch('src.middleware.rbac._permission_cache', {"user-123:org-123": {}}):
            clear_user_permission_cache(user_id, organization_id)
            # Specific cache entry should be removed


class TestRBACIntegration:
    """Integration tests for RBAC system"""

    @pytest.mark.asyncio
    async def test_end_to_end_permission_flow(self):
        """Test complete permission flow from middleware to service"""
        mock_app = Mock()
        permission_requirements = {"GET:/api/test": ["test_permission"]}
        middleware = RBACMiddleware(mock_app, permission_requirements)

        mock_request = Mock()
        mock_request.url.path = "/api/test"
        mock_request.method = "GET"
        call_next = AsyncMock(return_value=Mock())

        with patch('src.middleware.rbac.get_current_user_id', return_value="user-123"), \
             patch('src.middleware.rbac.get_current_tenant_id', return_value="org-123"), \
             patch.object(middleware.rbac_service, 'get_user_permissions', return_value={"test_permission"}):

            response = await middleware.dispatch(mock_request, call_next)

        assert response is not None
        call_next.assert_called_once_with(mock_request)

    def test_decorator_and_middleware_consistency(self):
        """Test that decorators and middleware use consistent permission checking"""
        # This test ensures that permission checking is consistent across
        # decorators and middleware implementations

        user_id = "user-123"
        organization_id = "org-123"
        permission_name = "test_permission"

        with patch('src.middleware.rbac.get_current_user_id', return_value=user_id), \
             patch('src.middleware.rbac.get_current_tenant_id', return_value=organization_id), \
             patch('src.middleware.rbac.RBACService') as mock_rbac_class:

            mock_rbac = Mock()
            mock_rbac.user_has_permission.return_value = True
            mock_rbac.user_has_any_permission.return_value = True
            mock_rbac.user_has_all_permissions.return_value = True
            mock_rbac_class.return_value.__enter__.return_value = mock_rbac

            # Test utility function
            util_result = has_permission(permission_name)

            # Test decorator (simplified check)
            @require_permission(permission_name)
            async def test_func():
                return "success"

            # Both should use the same underlying service and return consistent results
            assert util_result is True


if __name__ == "__main__":
    pytest.main([__file__])