"""
API Endpoint Test Template

Copy this template when creating tests for new API endpoints.
Replace RESOURCE_NAME with your resource name throughout.

Usage:
    cp tests/templates/test_api_template.py tests/api/test_resource_api.py
"""

import pytest
from datetime import datetime
from typing import Any, Dict
from unittest.mock import patch


# =============================================================================
# Test Configuration
# =============================================================================


class APITestConfig:
    """Configuration for RESOURCE_NAME API tests."""

    BASE_URL = "/api/v1/resources"
    RESOURCE_ID = "test-resource-123"

    # Valid payloads
    CREATE_PAYLOAD = {
        "name": "Test Resource",
        "description": "A test resource",
        "type": "standard",
    }

    UPDATE_PAYLOAD = {
        "name": "Updated Resource",
        "description": "Updated description",
    }

    # Invalid payloads for validation testing
    INVALID_PAYLOADS = [
        ({"name": ""}, "name cannot be empty"),
        ({"name": None}, "name is required"),
        ({"type": "invalid_type"}, "invalid type"),
    ]


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def created_resource(client, auth_headers):
    """Create a resource for testing and clean up after."""
    response = client.post(
        APITestConfig.BASE_URL,
        json=APITestConfig.CREATE_PAYLOAD,
        headers=auth_headers,
    )
    if response.status_code == 201:
        resource = response.json()
        yield resource
        # Cleanup
        client.delete(
            f"{APITestConfig.BASE_URL}/{resource['id']}",
            headers=auth_headers,
        )
    else:
        yield None


@pytest.fixture
def multiple_resources(client, auth_headers):
    """Create multiple resources for pagination testing."""
    resources = []
    for i in range(25):
        payload = {
            **APITestConfig.CREATE_PAYLOAD,
            "name": f"Test Resource {i}",
        }
        response = client.post(
            APITestConfig.BASE_URL,
            json=payload,
            headers=auth_headers,
        )
        if response.status_code == 201:
            resources.append(response.json())

    yield resources

    # Cleanup
    for resource in resources:
        client.delete(
            f"{APITestConfig.BASE_URL}/{resource['id']}",
            headers=auth_headers,
        )


# =============================================================================
# Authentication Tests
# =============================================================================


@pytest.mark.unit
class TestRESOURCE_NAMEAuthentication:
    """Authentication tests for RESOURCE_NAME API."""

    def test_requires_authentication(self, client):
        """All endpoints require authentication."""
        endpoints = [
            ("GET", APITestConfig.BASE_URL),
            ("POST", APITestConfig.BASE_URL),
            ("GET", f"{APITestConfig.BASE_URL}/{APITestConfig.RESOURCE_ID}"),
            ("PUT", f"{APITestConfig.BASE_URL}/{APITestConfig.RESOURCE_ID}"),
            ("DELETE", f"{APITestConfig.BASE_URL}/{APITestConfig.RESOURCE_ID}"),
        ]

        for method, url in endpoints:
            response = getattr(client, method.lower())(url)
            assert response.status_code == 401, f"{method} {url} should require auth"

    def test_invalid_token_rejected(self, client):
        """Invalid tokens are rejected."""
        headers = {"Authorization": "Bearer invalid-token"}
        response = client.get(APITestConfig.BASE_URL, headers=headers)
        assert response.status_code == 401

    def test_expired_token_rejected(self, client):
        """Expired tokens are rejected."""
        # Generate expired token
        from src.core.security import create_access_token
        from datetime import timedelta

        expired_token = create_access_token(
            data={"sub": "test-user"},
            expires_delta=timedelta(seconds=-1),
        )
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = client.get(APITestConfig.BASE_URL, headers=headers)
        assert response.status_code == 401


# =============================================================================
# CREATE (POST) Tests
# =============================================================================


@pytest.mark.integration
class TestRESOURCE_NAMECreate:
    """POST endpoint tests for RESOURCE_NAME."""

    def test_create_success(self, client, auth_headers):
        """Successfully create a resource."""
        response = client.post(
            APITestConfig.BASE_URL,
            json=APITestConfig.CREATE_PAYLOAD,
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["name"] == APITestConfig.CREATE_PAYLOAD["name"]

    def test_create_returns_location_header(self, client, auth_headers):
        """Create returns Location header with resource URL."""
        response = client.post(
            APITestConfig.BASE_URL,
            json=APITestConfig.CREATE_PAYLOAD,
            headers=auth_headers,
        )

        assert response.status_code == 201
        # assert "Location" in response.headers
        # assert response.headers["Location"].endswith(response.json()["id"])

    @pytest.mark.parametrize("invalid_payload,error_msg", APITestConfig.INVALID_PAYLOADS)
    def test_create_validation_errors(self, client, auth_headers, invalid_payload, error_msg):
        """Create returns 422 for invalid payloads."""
        response = client.post(
            APITestConfig.BASE_URL,
            json=invalid_payload,
            headers=auth_headers,
        )

        assert response.status_code == 422

    def test_create_duplicate_returns_409(self, client, auth_headers, created_resource):
        """Create returns 409 for duplicate resource."""
        if created_resource is None:
            pytest.skip("Could not create test resource")

        # Try to create with same unique identifier
        response = client.post(
            APITestConfig.BASE_URL,
            json=APITestConfig.CREATE_PAYLOAD,
            headers=auth_headers,
        )

        # Depends on your uniqueness constraints
        # assert response.status_code == 409


# =============================================================================
# READ (GET) Tests
# =============================================================================


@pytest.mark.integration
class TestRESOURCE_NAMERead:
    """GET endpoint tests for RESOURCE_NAME."""

    def test_get_single_success(self, client, auth_headers, created_resource):
        """Successfully get a single resource."""
        if created_resource is None:
            pytest.skip("Could not create test resource")

        response = client.get(
            f"{APITestConfig.BASE_URL}/{created_resource['id']}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created_resource["id"]

    def test_get_not_found(self, client, auth_headers):
        """Get returns 404 for non-existent resource."""
        response = client.get(
            f"{APITestConfig.BASE_URL}/nonexistent-id",
            headers=auth_headers,
        )

        assert response.status_code == 404

    def test_list_success(self, client, auth_headers):
        """Successfully list resources."""
        response = client.get(
            APITestConfig.BASE_URL,
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data or isinstance(data, list)

    def test_list_pagination(self, client, auth_headers, multiple_resources):
        """List supports pagination."""
        if not multiple_resources:
            pytest.skip("Could not create test resources")

        # First page
        response = client.get(
            f"{APITestConfig.BASE_URL}?page=1&size=10",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data.get("items", [])) <= 10

        # Second page
        response = client.get(
            f"{APITestConfig.BASE_URL}?page=2&size=10",
            headers=auth_headers,
        )

        assert response.status_code == 200

    def test_list_filtering(self, client, auth_headers, multiple_resources):
        """List supports filtering."""
        if not multiple_resources:
            pytest.skip("Could not create test resources")

        response = client.get(
            f"{APITestConfig.BASE_URL}?type=standard",
            headers=auth_headers,
        )

        assert response.status_code == 200

    def test_list_sorting(self, client, auth_headers, multiple_resources):
        """List supports sorting."""
        if not multiple_resources:
            pytest.skip("Could not create test resources")

        response = client.get(
            f"{APITestConfig.BASE_URL}?sort_by=created_at&sort_order=desc",
            headers=auth_headers,
        )

        assert response.status_code == 200


# =============================================================================
# UPDATE (PUT/PATCH) Tests
# =============================================================================


@pytest.mark.integration
class TestRESOURCE_NAMEUpdate:
    """PUT/PATCH endpoint tests for RESOURCE_NAME."""

    def test_update_success(self, client, auth_headers, created_resource):
        """Successfully update a resource."""
        if created_resource is None:
            pytest.skip("Could not create test resource")

        response = client.put(
            f"{APITestConfig.BASE_URL}/{created_resource['id']}",
            json=APITestConfig.UPDATE_PAYLOAD,
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == APITestConfig.UPDATE_PAYLOAD["name"]

    def test_partial_update_success(self, client, auth_headers, created_resource):
        """Successfully partial update with PATCH."""
        if created_resource is None:
            pytest.skip("Could not create test resource")

        response = client.patch(
            f"{APITestConfig.BASE_URL}/{created_resource['id']}",
            json={"name": "Partially Updated"},
            headers=auth_headers,
        )

        # Note: May return 200 or 405 depending on implementation
        assert response.status_code in [200, 405]

    def test_update_not_found(self, client, auth_headers):
        """Update returns 404 for non-existent resource."""
        response = client.put(
            f"{APITestConfig.BASE_URL}/nonexistent-id",
            json=APITestConfig.UPDATE_PAYLOAD,
            headers=auth_headers,
        )

        assert response.status_code == 404

    def test_update_validation_errors(self, client, auth_headers, created_resource):
        """Update returns 422 for invalid payload."""
        if created_resource is None:
            pytest.skip("Could not create test resource")

        response = client.put(
            f"{APITestConfig.BASE_URL}/{created_resource['id']}",
            json={"name": ""},  # Invalid
            headers=auth_headers,
        )

        assert response.status_code == 422


# =============================================================================
# DELETE Tests
# =============================================================================


@pytest.mark.integration
class TestRESOURCE_NAMEDelete:
    """DELETE endpoint tests for RESOURCE_NAME."""

    def test_delete_success(self, client, auth_headers):
        """Successfully delete a resource."""
        # Create resource first
        create_response = client.post(
            APITestConfig.BASE_URL,
            json=APITestConfig.CREATE_PAYLOAD,
            headers=auth_headers,
        )

        if create_response.status_code != 201:
            pytest.skip("Could not create test resource")

        resource_id = create_response.json()["id"]

        # Delete it
        response = client.delete(
            f"{APITestConfig.BASE_URL}/{resource_id}",
            headers=auth_headers,
        )

        assert response.status_code == 204 or response.status_code == 200

        # Verify it's gone
        get_response = client.get(
            f"{APITestConfig.BASE_URL}/{resource_id}",
            headers=auth_headers,
        )
        assert get_response.status_code == 404

    def test_delete_not_found(self, client, auth_headers):
        """Delete returns 404 for non-existent resource."""
        response = client.delete(
            f"{APITestConfig.BASE_URL}/nonexistent-id",
            headers=auth_headers,
        )

        assert response.status_code == 404

    def test_delete_idempotent(self, client, auth_headers):
        """Delete is idempotent - second delete returns 404."""
        # Create and delete resource
        create_response = client.post(
            APITestConfig.BASE_URL,
            json=APITestConfig.CREATE_PAYLOAD,
            headers=auth_headers,
        )

        if create_response.status_code != 201:
            pytest.skip("Could not create test resource")

        resource_id = create_response.json()["id"]

        # First delete
        client.delete(
            f"{APITestConfig.BASE_URL}/{resource_id}",
            headers=auth_headers,
        )

        # Second delete should return 404
        response = client.delete(
            f"{APITestConfig.BASE_URL}/{resource_id}",
            headers=auth_headers,
        )

        assert response.status_code == 404


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.integration
class TestRESOURCE_NAMEErrorHandling:
    """Error handling tests for RESOURCE_NAME API."""

    def test_invalid_json_returns_400(self, client, auth_headers):
        """Invalid JSON returns 400."""
        response = client.post(
            APITestConfig.BASE_URL,
            content="invalid json{",
            headers={**auth_headers, "Content-Type": "application/json"},
        )

        assert response.status_code == 400 or response.status_code == 422

    def test_unsupported_media_type(self, client, auth_headers):
        """Unsupported media type returns 415."""
        response = client.post(
            APITestConfig.BASE_URL,
            content="plain text",
            headers={**auth_headers, "Content-Type": "text/plain"},
        )

        # FastAPI typically returns 422 for this
        assert response.status_code in [415, 422]

    def test_method_not_allowed(self, client, auth_headers):
        """Unsupported method returns 405."""
        response = client.options(
            f"{APITestConfig.BASE_URL}/{APITestConfig.RESOURCE_ID}",
            headers=auth_headers,
        )

        # OPTIONS may be allowed for CORS
        # Test a truly unsupported method if available


# =============================================================================
# Authorization Tests
# =============================================================================


@pytest.mark.integration
class TestRESOURCE_NAMEAuthorization:
    """Authorization tests for RESOURCE_NAME API."""

    def test_user_cannot_access_other_user_resource(
        self,
        client,
        auth_headers,
        admin_auth_headers,
    ):
        """Users cannot access other users' resources."""
        # This depends on your authorization model
        # Implement based on your specific requirements
        pass

    def test_admin_can_access_all_resources(
        self,
        client,
        admin_auth_headers,
    ):
        """Admins can access all resources."""
        # Implement based on your authorization model
        pass
