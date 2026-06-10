"""
Contract tests for Authentication and Authorization in Evaluation API endpoints
Tests JWT token validation, role-based access control, organization scoping, and API key authentication
"""

import pytest
import jwt
import uuid
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient
from unittest.mock import patch, Mock
from typing import Dict, Any

from tests.constants import TEST_JWT_SECRET
from tests.contract.evaluation.fixtures.data_generators import EvaluationDataGenerator, JobDataGenerator


class TestEvaluationAuthContract:
    """Contract tests for evaluation API authentication and authorization"""

    # Authentication contract specifications
    AUTH_CONTRACT = {
        "jwt_token": {
            "algorithm": "HS256",
            "required_claims": ["sub", "email", "role", "organization_id", "exp", "iat"],
            "header_format": "Bearer <token>",
            "token_expiry": 3600  # 1 hour
        },
        "role_hierarchy": {
            "user": ["read_own", "create_own"],
            "admin": ["read_own", "create_own", "read_org", "manage_org", "delete_own"],
            "super_admin": ["read_own", "create_own", "read_org", "manage_org", "delete_own", "read_all", "manage_all"]
        },
        "organization_scoping": {
            "requirement": "Users can only access resources within their organization",
            "implementation": "All queries must filter by organization_id"
        },
        "error_responses": {
            "missing_auth": {"status": 401, "type": "authentication_error"},
            "invalid_token": {"status": 401, "type": "authentication_error"},
            "expired_token": {"status": 401, "type": "authentication_error"},
            "insufficient_permissions": {"status": 403, "type": "authorization_error"},
            "cross_organization": {"status": 404, "type": "not_found"}  # Hide existence
        }
    }

    @pytest.mark.contract
    @pytest.mark.auth_contract
    async def test_evaluation_jwt_token_validation_contract(
        self,
        async_client: AsyncClient,
        test_user,
        test_organization,
        contract_validator
    ):
        """Test JWT token validation contract"""
        # Generate valid JWT token
        payload = {
            "sub": str(test_user.id),
            "email": test_user.email,
            "role": test_user.role.value,
            "organization_id": str(test_organization.id),
            "exp": datetime.now(timezone.utc).timestamp() + 3600,
            "iat": datetime.now(timezone.utc).timestamp()
        }

        secret = TEST_JWT_SECRET  # Should match app secret
        token = jwt.encode(payload, secret, algorithm="HS256")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        # Test with valid token
        response = await async_client.get(
            "/api/v1/evaluation/jobs",
            headers=headers
        )

        # Should succeed with valid token
        assert response.status_code in [200, 404]  # 404 if no jobs exist

    @pytest.mark.contract
    @pytest.mark.auth_contract
    async def test_evaluation_missing_authentication_contract(
        self,
        async_client: AsyncClient,
        contract_validator
    ):
        """Test missing authentication"""
        # Test without Authorization header
        response = await async_client.get("/api/v1/evaluation/jobs")

        assert response.status_code == 401
        response_data = response.json()
        assert contract_validator.validate_error_response(response_data)

        # Test with empty Authorization header
        headers = {"Authorization": ""}
        response = await async_client.get("/api/v1/evaluation/jobs", headers=headers)

        assert response.status_code == 401
        response_data = response.json()
        assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.auth_contract
    async def test_evaluation_invalid_token_format_contract(
        self,
        async_client: AsyncClient,
        contract_validator
    ):
        """Test invalid token formats"""
        invalid_tokens = [
            "invalid-token",  # Missing Bearer prefix
            "Bearer",  # Missing token
            "Bearer ",  # Empty token
            "Bearer invalid.token.format",  # Invalid JWT format
            "Bearer not-a-jwt-at-all",  # Completely invalid
            "Basic dGVzdDoxMjM0",  # Wrong auth scheme
        ]

        for auth_header in invalid_tokens:
            headers = {"Authorization": auth_header}
            response = await async_client.get("/api/v1/evaluation/jobs", headers=headers)

            assert response.status_code == 401
            response_data = response.json()
            assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.auth_contract
    async def test_evaluation_expired_token_contract(
        self,
        async_client: AsyncClient,
        test_user,
        test_organization,
        contract_validator
    ):
        """Test expired JWT token"""
        # Generate expired token
        payload = {
            "sub": str(test_user.id),
            "email": test_user.email,
            "role": test_user.role.value,
            "organization_id": str(test_organization.id),
            "exp": (datetime.now(timezone.utc) - timedelta(minutes=5)).timestamp(),  # Expired 5 minutes ago
            "iat": (datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()
        }

        secret = TEST_JWT_SECRET
        token = jwt.encode(payload, secret, algorithm="HS256")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        response = await async_client.get("/api/v1/evaluation/jobs", headers=headers)

        assert response.status_code == 401
        response_data = response.json()
        assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.auth_contract
    async def test_evaluation_token_with_invalid_signature_contract(
        self,
        async_client: AsyncClient,
        test_user,
        test_organization,
        contract_validator
    ):
        """Test token with invalid signature"""
        payload = {
            "sub": str(test_user.id),
            "email": test_user.email,
            "role": test_user.role.value,
            "organization_id": str(test_organization.id),
            "exp": datetime.now(timezone.utc).timestamp() + 3600,
            "iat": datetime.now(timezone.utc).timestamp()
        }

        # Encode with wrong secret
        token = jwt.encode(payload, "wrong-secret", algorithm="HS256")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        response = await async_client.get("/api/v1/evaluation/jobs", headers=headers)

        assert response.status_code == 401
        response_data = response.json()
        assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.auth_contract
    async def test_evaluation_missing_required_claims_contract(
        self,
        async_client: AsyncClient,
        test_organization,
        contract_validator
    ):
        """Test token missing required claims"""
        required_claims = ["sub", "email", "role", "organization_id", "exp", "iat"]

        for claim in required_claims:
            # Create payload missing one required claim
            payload = {
                "sub": str(uuid.uuid4()),
                "email": "test@example.com",
                "role": "user",
                "organization_id": str(test_organization.id),
                "exp": datetime.now(timezone.utc).timestamp() + 3600,
                "iat": datetime.now(timezone.utc).timestamp()
            }
            del payload[claim]

            secret = TEST_JWT_SECRET
            token = jwt.encode(payload, secret, algorithm="HS256")

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            response = await async_client.get("/api/v1/evaluation/jobs", headers=headers)

            assert response.status_code == 401
            response_data = response.json()
            assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.auth_contract
    async def test_evaluation_organization_scoping_contract(
        self,
        async_client: AsyncClient,
        test_user,
        evaluation_data_generator: EvaluationDataGenerator,
        contract_validator
    ):
        """Test organization scoping for evaluation resources"""
        # Generate token for user in organization A
        org_a_id = str(uuid.uuid4())
        payload = {
            "sub": str(test_user.id),
            "email": test_user.email,
            "role": test_user.role.value,
            "organization_id": org_a_id,
            "exp": datetime.now(timezone.utc).timestamp() + 3600,
            "iat": datetime.now(timezone.utc).timestamp()
        }

        secret = TEST_JWT_SECRET
        token = jwt.encode(payload, secret, algorithm="HS256")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        # Try to access job from different organization
        other_org_job_id = str(uuid.uuid4())

        with patch('src.api.evaluation.db') as mock_db:
            # Mock database to return no job (user shouldn't have access)
            mock_db.query.return_value.filter.return_value.first.return_value = None

            response = await async_client.get(
                f"/api/v1/evaluation/jobs/{other_org_job_id}",
                headers=headers
            )

        # Should return 404, not 403 (to prevent existence discovery)
        assert response.status_code == 404
        response_data = response.json()
        assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.auth_contract
    async def test_evaluation_role_based_access_contract(
        self,
        async_client: AsyncClient,
        test_user,
        test_admin_user,
        evaluation_data_generator: EvaluationDataGenerator,
        contract_validator
    ):
        """Test role-based access control"""
        # Test user role - should only access own resources
        user_payload = {
            "sub": str(test_user.id),
            "email": test_user.email,
            "role": "user",
            "organization_id": str(test_user.organization_id),
            "exp": datetime.now(timezone.utc).timestamp() + 3600,
            "iat": datetime.now(timezone.utc).timestamp()
        }

        # Test admin role - should access organization resources
        admin_payload = {
            "sub": str(test_admin_user.id),
            "email": test_admin_user.email,
            "role": "admin",
            "organization_id": str(test_admin_user.organization_id),
            "exp": datetime.now(timezone.utc).timestamp() + 3600,
            "iat": datetime.now(timezone.utc).timestamp()
        }

        secret = TEST_JWT_SECRET
        user_token = jwt.encode(user_payload, secret, algorithm="HS256")
        admin_token = jwt.encode(admin_payload, secret, algorithm="HS256")

        user_headers = {
            "Authorization": f"Bearer {user_token}",
            "Content-Type": "application/json"
        }

        admin_headers = {
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json"
        }

        # Test evaluation creation - both roles should be able to create
        request_data = evaluation_data_generator.generate_evaluation_request(
            question_count=3
        )

        # User should be able to create evaluation
        user_response = await async_client.post(
            "/api/v1/evaluation/jobs",
            headers=user_headers,
            json=request_data
        )
        assert user_response.status_code in [200, 201, 400]  # 400 if validation fails, not auth

        # Admin should be able to create evaluation
        admin_response = await async_client.post(
            "/api/v1/evaluation/jobs",
            headers=admin_headers,
            json=request_data
        )
        assert admin_response.status_code in [200, 201, 400]

    @pytest.mark.contract
    @pytest.mark.auth_contract
    async def test_evaluation_api_key_authentication_contract(
        self,
        async_client: AsyncClient,
        contract_validator
    ):
        """Test API key authentication (if supported)"""
        # Test with API key in header
        api_key_headers = {
            "X-API-Key": "test-api-key-12345",
            "Content-Type": "application/json"
        }

        response = await async_client.get(
            "/api/v1/evaluation/jobs",
            headers=api_key_headers
        )

        # API key authentication may or may not be supported
        # If supported, should succeed (200/404). If not supported, should require JWT (401)
        assert response.status_code in [200, 401, 404]

        if response.status_code == 401:
            response_data = response.json()
            assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.auth_contract
    async def test_evaluation_token_tampering_contract(
        self,
        async_client: AsyncClient,
        test_user,
        test_organization,
        contract_validator
    ):
        """Test detection of token tampering"""
        # Create valid token
        payload = {
            "sub": str(test_user.id),
            "email": test_user.email,
            "role": test_user.role.value,
            "organization_id": str(test_organization.id),
            "exp": datetime.now(timezone.utc).timestamp() + 3600,
            "iat": datetime.now(timezone.utc).timestamp()
        }

        secret = TEST_JWT_SECRET
        token = jwt.encode(payload, secret, algorithm="HS256")

        # Tamper with token by changing one character
        tampered_token = token[:-10] + "tampered" + token[-5:]

        headers = {
            "Authorization": f"Bearer {tampered_token}",
            "Content-Type": "application/json"
        }

        response = await async_client.get("/api/v1/evaluation/jobs", headers=headers)

        assert response.status_code == 401
        response_data = response.json()
        assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.auth_contract
    async def test_evaluation_concurrent_requests_auth_contract(
        self,
        async_client: AsyncClient,
        test_user,
        test_organization
    ):
        """Test authentication with concurrent requests"""
        import asyncio

        # Generate valid token
        payload = {
            "sub": str(test_user.id),
            "email": test_user.email,
            "role": test_user.role.value,
            "organization_id": str(test_organization.id),
            "exp": datetime.now(timezone.utc).timestamp() + 3600,
            "iat": datetime.now(timezone.utc).timestamp()
        }

        secret = TEST_JWT_SECRET
        token = jwt.encode(payload, secret, algorithm="HS256")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        # Send multiple concurrent requests
        tasks = [
            async_client.get("/api/v1/evaluation/jobs", headers=headers)
            for _ in range(10)
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # All requests should be authenticated successfully
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                pytest.fail(f"Concurrent auth request {i} failed: {response}")

            # Should not fail authentication
            assert response.status_code != 401, f"Request {i} failed authentication"

    @pytest.mark.contract
    @pytest.mark.auth_contract
    async def test_evaluation_auth_response_time_contract(
        self,
        async_client: AsyncClient,
        test_user,
        test_organization,
        performance_tracker
    ):
        """Test authentication response time"""
        performance_tracker.start_timer("auth_response_time")

        # Generate valid token
        payload = {
            "sub": str(test_user.id),
            "email": test_user.email,
            "role": test_user.role.value,
            "organization_id": str(test_organization.id),
            "exp": datetime.now(timezone.utc).timestamp() + 3600,
            "iat": datetime.now(timezone.utc).timestamp()
        }

        secret = TEST_JWT_SECRET
        token = jwt.encode(payload, secret, algorithm="HS256")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        response = await async_client.get("/api/v1/evaluation/jobs", headers=headers)

        response_time = performance_tracker.end_timer("auth_response_time")

        # Authentication should be fast (less than 100ms)
        assert response_time < 0.1, f"Authentication response time {response_time}s exceeds 100ms"

        # Should not fail authentication
        assert response.status_code != 401

    @pytest.mark.contract
    @pytest.mark.auth_contract
    async def test_evaluation_auth_error_message_contract(
        self,
        async_client: AsyncClient,
        contract_validator
    ):
        """Test authentication error message consistency"""
        # Test different auth failure scenarios
        auth_failures = [
            {},  # No headers
            {"Authorization": ""},  # Empty auth
            {"Authorization": "Bearer"},  # Missing token
            {"Authorization": "Bearer invalid-token"},  # Invalid token
            {"Authorization": "Invalid token"}  # Wrong format
        ]

        error_responses = []

        for headers in auth_failures:
            response = await async_client.get("/api/v1/evaluation/jobs", headers=headers)
            assert response.status_code == 401

            response_data = response.json()
            assert contract_validator.validate_error_response(response_data)
            error_responses.append(response_data)

        # All auth errors should have consistent structure
        for error_response in error_responses:
            assert "error" in error_response
            assert error_response["error"]["status_code"] == 401
            assert error_response["error"]["type"] in ["authentication_error", "unauthorized"]

    @pytest.mark.contract
    @pytest.mark.auth_contract
    async def test_evaluation_token_refresh_contract(
        self,
        async_client: AsyncClient,
        test_user,
        test_organization
    ):
        """Test token refresh behavior"""
        # Generate token that's about to expire
        payload = {
            "sub": str(test_user.id),
            "email": test_user.email,
            "role": test_user.role.value,
            "organization_id": str(test_organization.id),
            "exp": (datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp(),  # Expires in 5 minutes
            "iat": datetime.now(timezone.utc).timestamp()
        }

        secret = TEST_JWT_SECRET
        token = jwt.encode(payload, secret, algorithm="HS256")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        # Token should still be valid
        response = await async_client.get("/api/v1/evaluation/jobs", headers=headers)
        assert response.status_code != 401

        # If refresh endpoint exists, test it
        refresh_response = await async_client.post(
            "/api/v1/auth/refresh",
            headers=headers,
            json={"refresh_token": "dummy-refresh-token"}
        )

        # Refresh endpoint may or may not be implemented
        assert refresh_response.status_code in [200, 401, 404, 422]

    @pytest.mark.contract
    @pytest.mark.auth_contract
    async def test_evaluation_malformed_jwt_contract(
        self,
        async_client: AsyncClient,
        contract_validator
    ):
        """Test handling of malformed JWT tokens"""
        malformed_tokens = [
            "Bearer not.jwt.at.all",  # Wrong number of parts
            "Bearer onlyonepart",  # Single part
            "Bearer two.parts",  # Two parts
            "Bearer " + "a" * 1000,  # Very long invalid token
            "Bearer " + "",  # Empty after Bearer
            "Bearer . . ",  # Empty parts
            "Bearer invalid.base64.signature",  # Invalid base64
        ]

        for malformed_token in malformed_tokens:
            headers = {"Authorization": malformed_token}
            response = await async_client.get("/api/v1/evaluation/jobs", headers=headers)

            assert response.status_code == 401
            response_data = response.json()
            assert contract_validator.validate_error_response(response_data)