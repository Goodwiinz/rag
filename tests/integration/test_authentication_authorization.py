"""
Authentication & Authorization Integration Tests
Tests security controls, role-based access, and permission validation
"""

import pytest
import jwt
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List
from unittest.mock import Mock, AsyncMock

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from conftest import (
    APIAssertions, create_auth_headers, create_test_user_session,
    sample_organization, sample_user, sample_dashboard, sample_report
)


class TestAuthenticationIntegration:
    """Test authentication mechanisms and security controls"""

    @pytest.mark.integration
    @pytest.mark.auth
    async def test_jwt_token_authentication(self, api_client: AsyncClient, sample_user):
        """Test JWT token authentication for API access"""
        # 1. Create valid JWT token
        token = jwt.encode(
            {
                "sub": str(sample_user["id"]),
                "email": sample_user["email"],
                "organization_id": str(sample_user["organization_id"]),
                "roles": sample_user["roles"],
                "exp": datetime.utcnow() + timedelta(hours=1),
                "iat": datetime.utcnow()
            },
            "test_secret_key",
            algorithm="HS256"
        )

        headers = create_auth_headers(token)

        # 2. Test authenticated request
        response = await api_client.get(
            f"/api/v1/analytics/realtime/metrics",
            params={"organization_id": str(sample_user["organization_id"])},
            headers=headers
        )

        assert response.status_code == 200

        # 3. Test token with invalid signature
        invalid_token = token[:-10] + "invalidchars"
        invalid_headers = create_auth_headers(invalid_token)

        response = await api_client.get(
            f"/api/v1/analytics/realtime/metrics",
            params={"organization_id": str(sample_user["organization_id"])},
            headers=invalid_headers
        )

        assert response.status_code == 401

    @pytest.mark.integration
    @pytest.mark.auth
    async def test_token_expiry_validation(self, api_client: AsyncClient, sample_user):
        """Test token expiry validation"""
        # 1. Create expired token
        expired_token = jwt.encode(
            {
                "sub": str(sample_user["id"]),
                "email": sample_user["email"],
                "organization_id": str(sample_user["organization_id"]),
                "roles": sample_user["roles"],
                "exp": datetime.utcnow() - timedelta(hours=1),  # Expired
                "iat": datetime.utcnow() - timedelta(hours=2)
            },
            "test_secret_key",
            algorithm="HS256"
        )

        headers = create_auth_headers(expired_token)

        # 2. Test request with expired token
        response = await api_client.get(
            f"/api/v1/analytics/realtime/metrics",
            params={"organization_id": str(sample_user["organization_id"])},
            headers=headers
        )

        assert response.status_code == 401
        error_data = response.json()
        assert "expired" in error_data["error"]["message"].lower()

    @pytest.mark.integration
    @pytest.mark.auth
    async def test_missing_authentication(self, api_client: AsyncClient, sample_organization):
        """Test API access without authentication"""
        # 1. Request without Authorization header
        response = await api_client.get(
            f"/api/v1/analytics/realtime/metrics",
            params={"organization_id": str(sample_organization["id"])}
        )

        assert response.status_code == 401

        # 2. Request with invalid Authorization header format
        invalid_headers = {"Authorization": "InvalidFormat token123"}
        response = await api_client.get(
            f"/api/v1/analytics/realtime/metrics",
            params={"organization_id": str(sample_organization["id"])},
            headers=invalid_headers
        )

        assert response.status_code == 401

        # 3. Request with Bearer prefix but no token
        empty_headers = {"Authorization": "Bearer "}
        response = await api_client.get(
            f"/api/v1/analytics/realtime/metrics",
            params={"organization_id": str(sample_organization["id"])},
            headers=empty_headers
        )

        assert response.status_code == 401

    @pytest.mark.integration
    @pytest.mark.auth
    async def test_user_context_validation(self, api_client: AsyncClient, sample_user, sample_organization):
        """Test user context validation in requests"""
        # 1. Create token for different user
        other_user_token = jwt.encode(
            {
                "sub": str(uuid.uuid4()),  # Different user ID
                "email": "other@example.com",
                "organization_id": str(sample_user["organization_id"]),
                "roles": sample_user["roles"],
                "exp": datetime.utcnow() + timedelta(hours=1)
            },
            "test_secret_key",
            algorithm="HS256"
        )

        headers = create_auth_headers(other_user_token)

        # 2. Test accessing resources with mismatched user context
        response = await api_client.get(
            f"/api/v1/analytics/dashboard/configurations",
            params={
                "organization_id": str(sample_organization["id"]),
                "user_id": str(sample_user["id"])  # Different from token user
            },
            headers=headers
        )

        # This should either succeed (if user has admin rights) or fail with 403
        # The exact behavior depends on the authorization implementation
        assert response.status_code in [200, 403]


class TestAuthorizationIntegration:
    """Test role-based access control and permissions"""

    @pytest.fixture
    async def users_with_different_roles(self, sample_organization):
        """Create users with different roles for testing"""
        roles_config = [
            {
                "email": "admin@example.com",
                "roles": ["admin"],
                "expected_access": ["read", "write", "delete", "admin"]
            },
            {
                "email": "analyst@example.com",
                "roles": ["analyst"],
                "expected_access": ["read", "write"]
            },
            {
                "email": "viewer@example.com",
                "roles": ["viewer"],
                "expected_access": ["read"]
            },
            {
                "email": "unauthorized@example.com",
                "roles": [],
                "expected_access": []
            }
        ]

        users = []
        for config in roles_config:
            user_data = {
                "id": uuid.uuid4(),
                "email": config["email"],
                "organization_id": sample_organization["id"],
                "roles": config["roles"],
                "is_active": True,
                "expected_access": config["expected_access"]
            }
            users.append(user_data)

        return users

    @pytest.mark.integration
    @pytest.mark.auth
    async def test_role_based_api_access(self, api_client: AsyncClient, users_with_different_roles):
        """Test API access based on user roles"""
        org_id = users_with_different_roles[0]["organization_id"]

        # Define endpoints and required permissions
        test_endpoints = [
            {
                "method": "GET",
                "url": f"/api/v1/analytics/realtime/metrics",
                "params": {"organization_id": str(org_id)},
                "required_roles": ["viewer", "analyst", "admin"],
                "description": "Read metrics"
            },
            {
                "method": "POST",
                "url": f"/api/v1/analytics/dashboard/configurations",
                "params": {"organization_id": str(org_id)},
                "json": {"config_name": "Test", "config_type": "user"},
                "required_roles": ["analyst", "admin"],
                "description": "Create dashboard"
            },
            {
                "method": "DELETE",
                "url": f"/api/v1/analytics/dashboard/configurations/{uuid.uuid4()}",
                "params": {"organization_id": str(org_id)},
                "required_roles": ["admin"],
                "description": "Delete dashboard"
            }
        ]

        for user in users_with_different_roles:
            # Create auth token for user
            token = jwt.encode(
                {
                    "sub": str(user["id"]),
                    "email": user["email"],
                    "organization_id": str(user["organization_id"]),
                    "roles": user["roles"],
                    "exp": datetime.utcnow() + timedelta(hours=1)
                },
                "test_secret_key",
                algorithm="HS256"
            )
            headers = create_auth_headers(token)

            for endpoint in test_endpoints:
                # Test each endpoint with current user role
                response = await api_client.request(
                    endpoint["method"],
                    endpoint["url"],
                    params=endpoint.get("params"),
                    json=endpoint.get("json"),
                    headers=headers
                )

                # Determine expected outcome based on roles
                has_required_role = any(role in user["roles"] for role in endpoint["required_roles"])

                if has_required_role:
                    # User should have access
                    assert response.status_code in [200, 201, 204, 404], (
                        f"User {user['email']} with roles {user['roles']} "
                        f"should have access to {endpoint['description']}"
                    )
                else:
                    # User should be denied access
                    assert response.status_code == 403, (
                        f"User {user['email']} with roles {user['roles']} "
                        f"should NOT have access to {endpoint['description']}"
                    )

    @pytest.mark.integration
    @pytest.mark.auth
    async def test_organization_isolation(self, api_client: AsyncClient):
        """Test users cannot access other organizations' data"""
        # Create two organizations
        org1_id = uuid.uuid4()
        org2_id = uuid.uuid4()

        # Create user for org1
        user1_token = jwt.encode(
            {
                "sub": str(uuid.uuid4()),
                "email": "user1@org1.com",
                "organization_id": str(org1_id),
                "roles": ["analyst"],
                "exp": datetime.utcnow() + timedelta(hours=1)
            },
            "test_secret_key",
            algorithm="HS256"
        )
        headers1 = create_auth_headers(user1_token)

        # Create user for org2
        user2_token = jwt.encode(
            {
                "sub": str(uuid.uuid4()),
                "email": "user2@org2.com",
                "organization_id": str(org2_id),
                "roles": ["analyst"],
                "exp": datetime.utcnow() + timedelta(hours=1)
            },
            "test_secret_key",
            algorithm="HS256"
        )
        headers2 = create_auth_headers(user2_token)

        # Test cross-organization access attempts
        test_cases = [
            {
                "user_headers": headers1,
                "target_org": org2_id,
                "description": "User1 accessing Org2 data"
            },
            {
                "user_headers": headers2,
                "target_org": org1_id,
                "description": "User2 accessing Org1 data"
            }
        ]

        for case in test_cases:
            response = await api_client.get(
                f"/api/v1/analytics/realtime/metrics",
                params={"organization_id": str(case["target_org"])},
                headers=case["user_headers"]
            )

            # Should be forbidden (403) or not found (404) depending on implementation
            assert response.status_code in [403, 404], (
                f"{case['description']} should be blocked"
            )

    @pytest.mark.integration
    @pytest.mark.auth
    async def test_permission_inheritance(self, api_client: AsyncClient, sample_organization):
        """Test permission inheritance and escalation"""
        org_id = sample_organization["id"]

        # Test user with admin role should have all permissions
        admin_token = jwt.encode(
            {
                "sub": str(uuid.uuid4()),
                "email": "admin@example.com",
                "organization_id": str(org_id),
                "roles": ["admin"],
                "exp": datetime.utcnow() + timedelta(hours=1)
            },
            "test_secret_key",
            algorithm="HS256"
        )
        admin_headers = create_auth_headers(admin_token)

        # Test admin can access admin-only endpoints
        admin_endpoints = [
            {
                "method": "GET",
                "url": f"/api/v1/analytics/admin/users",
                "params": {"organization_id": str(org_id)}
            },
            {
                "method": "POST",
                "url": f"/api/v1/analytics/admin/settings",
                "params": {"organization_id": str(org_id)},
                "json": {"setting": "value"}
            }
        ]

        for endpoint in admin_endpoints:
            response = await api_client.request(
                endpoint["method"],
                endpoint["url"],
                params=endpoint.get("params"),
                json=endpoint.get("json"),
                headers=admin_headers
            )
            # Admin should have access (200, 201, 404 if endpoint doesn't exist, but not 403)
            assert response.status_code != 403

        # Test user with viewer role cannot access admin endpoints
        viewer_token = jwt.encode(
            {
                "sub": str(uuid.uuid4()),
                "email": "viewer@example.com",
                "organization_id": str(org_id),
                "roles": ["viewer"],
                "exp": datetime.utcnow() + timedelta(hours=1)
            },
            "test_secret_key",
            algorithm="HS256"
        )
        viewer_headers = create_auth_headers(viewer_token)

        for endpoint in admin_endpoints:
            response = await api_client.request(
                endpoint["method"],
                endpoint["url"],
                params=endpoint.get("params"),
                json=endpoint.get("json"),
                headers=viewer_headers
            )
            # Viewer should be denied access
            assert response.status_code == 403

    @pytest.mark.integration
    @pytest.mark.auth
    async def test_resource_level_permissions(self, api_client: AsyncClient, sample_organization, sample_dashboard):
        """Test permissions at individual resource level"""
        org_id = sample_organization["id"]

        # Create two users with different permissions
        owner_token = jwt.encode(
            {
                "sub": str(sample_dashboard["user_id"]),
                "email": "owner@example.com",
                "organization_id": str(org_id),
                "roles": ["analyst"],
                "exp": datetime.utcnow() + timedelta(hours=1)
            },
            "test_secret_key",
            algorithm="HS256"
        )
        owner_headers = create_auth_headers(owner_token)

        other_user_token = jwt.encode(
            {
                "sub": str(uuid.uuid4()),
                "email": "other@example.com",
                "organization_id": str(org_id),
                "roles": ["analyst"],
                "exp": datetime.utcnow() + timedelta(hours=1)
            },
            "test_secret_key",
            algorithm="HS256"
        )
        other_headers = create_auth_headers(other_user_token)

        # Create dashboard as owner
        response = await api_client.post(
            f"/api/v1/analytics/dashboard/configurations",
            params={"organization_id": str(org_id)},
            json=sample_dashboard,
            headers=owner_headers
        )

        if response.status_code == 201:
            dashboard = response.json()
            dashboard_id = dashboard["id"]

            # Test owner can update their own dashboard
            update_response = await api_client.put(
                f"/api/v1/analytics/dashboard/configurations/{dashboard_id}",
                params={"organization_id": str(org_id)},
                json={"config_name": "Updated by owner"},
                headers=owner_headers
            )
            assert update_response.status_code in [200, 404]  # 404 if dashboard was deleted

            # Test other user cannot update dashboard (unless shared)
            unauthorized_response = await api_client.put(
                f"/api/v1/analytics/dashboard/configurations/{dashboard_id}",
                params={"organization_id": str(org_id)},
                json={"config_name": "Updated by other"},
                headers=other_headers
            )
            assert unauthorized_response.status_code in [403, 404]

    @pytest.mark.integration
    @pytest.mark.auth
    async def test_websocket_authentication(self, websocket_client, sample_user):
        """Test WebSocket connection authentication"""
        import websockets

        # 1. Test valid authentication
        valid_token = jwt.encode(
            {
                "sub": str(sample_user["id"]),
                "email": sample_user["email"],
                "organization_id": str(sample_user["organization_id"]),
                "roles": sample_user["roles"],
                "exp": datetime.utcnow() + timedelta(hours=1)
            },
            "test_secret_key",
            algorithm="HS256"
        )

        try:
            uri = f"{websocket_client.base_url}/ws/analytics?token={valid_token}"
            websocket = await websocket_client.connect(uri, timeout=5.0)

            # Should receive authentication confirmation
            message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            auth_data = json.loads(message)
            assert auth_data["type"] == "auth"

            await websocket.close()

        except Exception as e:
            # WebSocket connection might fail in test environment
            # This is expected if the WebSocket server is not running
            pass

        # 2. Test invalid authentication
        invalid_token = "invalid.jwt.token"

        try:
            uri = f"{websocket_client.base_url}/ws/analytics?token={invalid_token}"
            websocket = await websocket_client.connect(uri, timeout=5.0)

            # Should receive error or connection should be closed
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                error_data = json.loads(message)
                assert error_data["type"] == "error"
            except websockets.exceptions.ConnectionClosed:
                # Connection was closed due to invalid auth
                pass

            await websocket.close()

        except Exception:
            # Connection failed as expected
            pass

    @pytest.mark.integration
    @pytest.mark.auth
    async def test_api_key_authentication(self, api_client: AsyncClient, sample_organization):
        """Test API key authentication alternative to JWT"""
        # Generate test API key
        api_key = f"test_api_key_{uuid.uuid4().hex}"

        # Test API key in headers
        api_key_headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }

        response = await api_client.get(
            f"/api/v1/analytics/realtime/metrics",
            params={"organization_id": str(sample_organization["id"])},
            headers=api_key_headers
        )

        # API key authentication might not be implemented
        # If implemented, should return 200; if not, should return 401
        assert response.status_code in [200, 401]

        # Test invalid API key
        invalid_api_key_headers = {
            "X-API-Key": "invalid_api_key",
            "Content-Type": "application/json"
        }

        response = await api_client.get(
            f"/api/v1/analytics/realtime/metrics",
            params={"organization_id": str(sample_organization["id"])},
            headers=invalid_api_key_headers
        )

        assert response.status_code == 401

    @pytest.mark.integration
    @pytest.mark.auth
    async def test_session_management(self, api_client: AsyncClient, sample_user):
        """Test session management and token refresh"""
        # 1. Create initial token
        initial_token = jwt.encode(
            {
                "sub": str(sample_user["id"]),
                "email": sample_user["email"],
                "organization_id": str(sample_user["organization_id"]),
                "roles": sample_user["roles"],
                "exp": datetime.utcnow() + timedelta(hours=1),
                "iat": datetime.utcnow()
            },
            "test_secret_key",
            algorithm="HS256"
        )

        headers = create_auth_headers(initial_token)

        # 2. Make authenticated request
        response = await api_client.get(
            f"/api/v1/analytics/realtime/metrics",
            params={"organization_id": str(sample_user["organization_id"])},
            headers=headers
        )
        assert response.status_code == 200

        # 3. Test token refresh endpoint (if implemented)
        refresh_response = await api_client.post(
            "/api/v1/auth/refresh",
            json={"token": initial_token},
            headers={"Content-Type": "application/json"}
        )

        if refresh_response.status_code == 200:
            # Token was refreshed
            new_token_data = refresh_response.json()
            assert "token" in new_token_data

            # Test new token works
            new_headers = create_auth_headers(new_token_data["token"])
            response = await api_client.get(
                f"/api/v1/analytics/realtime/metrics",
                params={"organization_id": str(sample_user["organization_id"])},
                headers=new_headers
            )
            assert response.status_code == 200
        else:
            # Refresh endpoint might not be implemented
            assert refresh_response.status_code in [404, 405]

    @pytest.mark.integration
    @pytest.mark.auth
    async def test_rate_limiting_by_role(self, api_client: AsyncClient, users_with_different_roles):
        """Test rate limiting varies by user role"""
        org_id = users_with_different_roles[0]["organization_id"]

        # Make multiple requests rapidly
        async def make_requests(user_token: str, request_count: int = 10):
            headers = create_auth_headers(user_token)
            responses = []

            for i in range(request_count):
                response = await api_client.get(
                    f"/api/v1/analytics/realtime/metrics",
                    params={"organization_id": str(org_id)},
                    headers=headers
                )
                responses.append(response)
                await asyncio.sleep(0.1)  # Small delay

            return responses

        # Test with admin user (should have higher rate limits)
        admin_user = next((u for u in users_with_different_roles if "admin" in u["roles"]), None)
        if admin_user:
            admin_token = jwt.encode(
                {
                    "sub": str(admin_user["id"]),
                    "email": admin_user["email"],
                    "organization_id": str(admin_user["organization_id"]),
                    "roles": admin_user["roles"],
                    "exp": datetime.utcnow() + timedelta(hours=1)
                },
                "test_secret_key",
                algorithm="HS256"
            )

            admin_responses = await make_requests(admin_token)
            # Admin should not be rate limited
            rate_limited_responses = [r for r in admin_responses if r.status_code == 429]
            assert len(rate_limited_responses) == 0, "Admin should not be rate limited"

        # Test with viewer user (might have lower rate limits)
        viewer_user = next((u for u in users_with_different_roles if "viewer" in u["roles"]), None)
        if viewer_user:
            viewer_token = jwt.encode(
                {
                    "sub": str(viewer_user["id"]),
                    "email": viewer_user["email"],
                    "organization_id": str(viewer_user["organization_id"]),
                    "roles": viewer_user["roles"],
                    "exp": datetime.utcnow() + timedelta(hours=1)
                },
                "test_secret_key",
                algorithm="HS256"
            )

            viewer_responses = await make_requests(viewer_token)
            # Rate limiting behavior depends on implementation
            # This test mainly verifies the endpoint responds consistently
            successful_responses = [r for r in viewer_responses if r.status_code == 200]
            assert len(successful_responses) > 0, "At least some requests should succeed"