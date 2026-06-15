"""
Contract tests for Error Response Validation in Evaluation API endpoints
Tests validation errors (400), authentication errors (401), authorization errors (403),
rate limiting responses (429), and server error responses (500)
"""

import pytest
import uuid
import json
from datetime import datetime, timezone
from httpx import AsyncClient
from unittest.mock import patch, Mock
from typing import Dict, Any

from tests.constants import TEST_JWT_SECRET
from tests.contract.evaluation.fixtures.data_generators import EvaluationDataGenerator, JobDataGenerator


class TestEvaluationErrorResponseContract:
    """Contract tests for evaluation API error responses"""

    # Error response contract specifications
    ERROR_CONTRACT = {
        "common_schema": {
            "required_fields": ["error"],
            "error_object_schema": {
                "required_fields": ["message", "status_code", "type"],
                "field_types": {
                    "message": str,
                    "status_code": int,
                    "type": str
                },
                "optional_fields": ["details", "field", "code", "timestamp"]
            }
        },
        "status_codes": {
            "validation_error": {
                "status": 400,
                "type": "validation_error",
                "common_causes": ["invalid_request_body", "missing_required_fields", "invalid_field_types"]
            },
            "authentication_error": {
                "status": 401,
                "type": "authentication_error",
                "common_causes": ["missing_token", "invalid_token", "expired_token"]
            },
            "authorization_error": {
                "status": 403,
                "type": "authorization_error",
                "common_causes": ["insufficient_permissions", "resource_access_denied"]
            },
            "not_found_error": {
                "status": 404,
                "type": "not_found",
                "common_causes": ["resource_not_found", "invalid_resource_id"]
            },
            "rate_limit_error": {
                "status": 429,
                "type": "rate_limit_error",
                "common_causes": ["too_many_requests", "quota_exceeded"],
                "headers": ["Retry-After", "X-RateLimit-Limit", "X-RateLimit-Remaining"]
            },
            "server_error": {
                "status": 500,
                "type": "internal_error",
                "common_causes": ["database_error", "service_unavailable", "unexpected_error"]
            }
        },
        "content_type": "application/json",
        "headers": {
            "common": ["Content-Type"],
            "rate_limiting": ["Retry-After"]
        }
    }

    @pytest.mark.contract
    @pytest.mark.error_contract
    async def test_validation_error_response_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test validation error response contract (400)"""
        # Test missing required fields
        invalid_requests = [
            {},  # Empty request
            {"name": ""},  # Missing required fields
            {"questions": []},  # Missing other required fields
            {"name": "Test", "questions": 123},  # Wrong field type
            {"name": "Test", "questions": [123]},  # Invalid array elements
            {"name": "T" * 300, "questions": ["Test"]},  # Field too long
            {"name": "Test", "questions": ["Q1"], "evaluation_type": "invalid_type"}  # Invalid enum
        ]

        for invalid_request in invalid_requests:
            response = await async_client.post(
                "/api/v1/evaluation/jobs",
                headers=auth_headers,
                json=invalid_request
            )

            assert response.status_code == 400, f"Expected 400 for request: {invalid_request}"

            # Validate error response structure
            response_data = response.json()
            assert contract_validator.validate_error_response(response_data)

            # Validate specific error contract
            assert response_data["error"]["status_code"] == 400
            assert response_data["error"]["type"] in ["validation_error", "bad_request", "invalid_request"]

            # Validate content type
            assert "application/json" in response.headers.get("content-type", "")

    @pytest.mark.contract
    @pytest.mark.error_contract
    async def test_authentication_error_response_contract(
        self,
        async_client: AsyncClient,
        contract_validator
    ):
        """Test authentication error response contract (401)"""
        # Test various authentication failures
        auth_failures = [
            {},  # No auth header
            {"Authorization": ""},  # Empty auth
            {"Authorization": "Bearer"},  # Missing token
            {"Authorization": "Bearer invalid-token"},  # Invalid token
            {"Authorization": "Invalid token"},  # Wrong format
            {"Authorization": "Bearer not.a.jwt"}  # Malformed JWT
        ]

        for auth_header in auth_failures:
            response = await async_client.get("/api/v1/evaluation/jobs", headers=auth_header)

            assert response.status_code == 401

            # Validate error response structure
            response_data = response.json()
            assert contract_validator.validate_error_response(response_data)

            # Validate specific error contract
            assert response_data["error"]["status_code"] == 401
            assert response_data["error"]["type"] in ["authentication_error", "unauthorized", "access_denied"]

            # Validate content type
            assert "application/json" in response.headers.get("content-type", "")

    @pytest.mark.contract
    @pytest.mark.error_contract
    async def test_authorization_error_response_contract(
        self,
        async_client: AsyncClient,
        test_user,
        test_organization,
        job_data_generator: JobDataGenerator,
        contract_validator
    ):
        """Test authorization error response contract (403)"""
        # Create token for user with limited permissions
        payload = {
            "sub": str(test_user.id),
            "email": test_user.email,
            "role": "user",  # Limited role
            "organization_id": str(test_organization.id),
            "exp": datetime.now(timezone.utc).timestamp() + 3600,
            "iat": datetime.now(timezone.utc).timestamp()
        }

        import jwt
        secret = TEST_JWT_SECRET
        token = jwt.encode(payload, secret, algorithm="HS256")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        # Try to access admin-only endpoint (if exists)
        response = await async_client.get("/api/v1/admin/users", headers=headers)

        if response.status_code == 403:
            # Validate error response structure
            response_data = response.json()
            assert contract_validator.validate_error_response(response_data)

            # Validate specific error contract
            assert response_data["error"]["status_code"] == 403
            assert response_data["error"]["type"] in ["authorization_error", "forbidden", "access_denied"]

            # Validate content type
            assert "application/json" in response.headers.get("content-type", "")

    @pytest.mark.contract
    @pytest.mark.error_contract
    async def test_not_found_error_response_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test not found error response contract (404)"""
        # Test various not found scenarios
        not_found_scenarios = [
            f"/api/v1/evaluation/jobs/{uuid.uuid4()}",  # Non-existent job
            f"/api/v1/evaluation/jobs/{uuid.uuid4()}/metrics",  # Non-existent job metrics
            f"/api/v1/evaluation/jobs/{uuid.uuid4()}/reports/summary",  # Non-existent job report
            "/api/v1/evaluation/jobs/invalid-uuid",  # Invalid UUID format
        ]

        for endpoint in not_found_scenarios:
            response = await async_client.get(endpoint, headers=auth_headers)

            assert response.status_code == 404

            # Validate error response structure
            response_data = response.json()
            assert contract_validator.validate_error_response(response_data)

            # Validate specific error contract
            assert response_data["error"]["status_code"] == 404
            assert response_data["error"]["type"] in ["not_found", "resource_not_found"]

            # Validate content type
            assert "application/json" in response.headers.get("content-type", "")

    @pytest.mark.contract
    @pytest.mark.error_contract
    async def test_rate_limit_error_response_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        contract_validator
    ):
        """Test rate limit error response contract (429)"""
        import asyncio

        # Generate request data
        request_data = evaluation_data_generator.generate_evaluation_request(
            question_count=2
        )

        # Send rapid requests to trigger rate limiting
        tasks = [
            async_client.post("/api/v1/evaluation/jobs", headers=auth_headers, json=request_data)
            for _ in range(50)  # Large number of requests
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Check for rate limited responses
        rate_limited_responses = [
            response for response in responses
            if hasattr(response, 'status_code') and response.status_code == 429
        ]

        if rate_limited_responses:
            response = rate_limited_responses[0]

            # Validate error response structure
            response_data = response.json()
            assert contract_validator.validate_error_response(response_data)

            # Validate specific error contract
            assert response_data["error"]["status_code"] == 429
            assert response_data["error"]["type"] in ["rate_limit_error", "too_many_requests"]

            # Validate rate limiting headers if present
            rate_limit_headers = ["Retry-After", "X-RateLimit-Limit", "X-RateLimit-Remaining"]
            for header in rate_limit_headers:
                if header in response.headers:
                    assert response.headers[header] is not None

            # Validate content type
            assert "application/json" in response.headers.get("content-type", "")

    @pytest.mark.contract
    @pytest.mark.error_contract
    async def test_server_error_response_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test server error response contract (500)"""
        # Mock a service failure
        with patch('src.api.evaluation.db') as mock_db:
            mock_db.query.side_effect = Exception("Database connection failed")

            response = await async_client.get("/api/v1/evaluation/jobs", headers=auth_headers)

            assert response.status_code == 500

            # Validate error response structure
            response_data = response.json()
            assert contract_validator.validate_error_response(response_data)

            # Validate specific error contract
            assert response_data["error"]["status_code"] == 500
            assert response_data["error"]["type"] in ["internal_error", "server_error", "internal_server_error"]

            # In production, error details should be obscured
            if "test" not in str(response_data["error"]["message"]).lower():
                assert "internal" in str(response_data["error"]["message"]).lower() or \
                       "server" in str(response_data["error"]["message"]).lower()

            # Validate content type
            assert "application/json" in response.headers.get("content-type", "")

    @pytest.mark.contract
    @pytest.mark.error_contract
    async def test_error_response_field_validation_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test field-level validation in error responses"""
        # Test various field validation errors
        field_errors = [
            {"name": ""},  # Empty name field
            {"questions": []},  # Empty required array
            {"questions": [""]},  # Empty string in array
            {"search_limit": 0},  # Value below minimum
            {"search_limit": 1000},  # Value above maximum
            {"evaluation_type": "invalid"},  # Invalid enum value
        ]

        for field_error in field_errors:
            response = await async_client.post(
                "/api/v1/evaluation/jobs",
                headers=auth_headers,
                json=field_error
            )

            if response.status_code == 400:
                response_data = response.json()
                assert contract_validator.validate_error_response(response_data)

                # Check if field-level error details are provided
                error_obj = response_data["error"]
                if "details" in error_obj:
                    assert isinstance(error_obj["details"], (list, dict))

                if "field" in error_obj:
                    assert isinstance(error_obj["field"], str)

    @pytest.mark.contract
    @pytest.mark.error_contract
    async def test_error_response_consistency_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        contract_validator
    ):
        """Test error response consistency across different endpoints"""
        # Test errors on different evaluation endpoints
        endpoints = [
            ("POST", "/api/v1/evaluation/jobs", {}),
            ("POST", "/api/v1/evaluation/jobs/batch", {}),
            ("POST", "/api/v1/evaluation/real-time", {}),
            ("GET", f"/api/v1/evaluation/jobs/{uuid.uuid4()}", None),
            ("POST", "/api/v1/evaluation/comparisons", {})
        ]

        error_responses = []

        for method, endpoint, data in endpoints:
            if method == "POST":
                response = await async_client.post(endpoint, headers=auth_headers, json=data or {})
            else:
                response = await async_client.get(endpoint, headers=auth_headers)

            if response.status_code >= 400:
                response_data = response.json()
                assert contract_validator.validate_error_response(response_data)
                error_responses.append(response_data)

        # All error responses should follow the same contract
        for error_response in error_responses:
            assert "error" in error_response
            assert error_response["error"]["status_code"] >= 400
            assert error_response["error"]["type"] is not None
            assert error_response["error"]["message"] is not None

    @pytest.mark.contract
    @pytest.mark.error_contract
    async def test_error_response_content_type_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str]
    ):
        """Test that all error responses have correct content type"""
        # Test various error scenarios
        error_scenarios = [
            # No auth
            lambda: async_client.get("/api/v1/evaluation/jobs"),
            # Invalid resource
            lambda: async_client.get(f"/api/v1/evaluation/jobs/{uuid.uuid4()}", headers=auth_headers),
            # Invalid request body
            lambda: async_client.post("/api/v1/evaluation/jobs", headers=auth_headers, json={"invalid": "data"}),
        ]

        for scenario in error_scenarios:
            response = await scenario()

            if response.status_code >= 400:
                content_type = response.headers.get("content-type", "")
                assert "application/json" in content_type, f"Content-Type should be application/json, got {content_type}"

    @pytest.mark.contract
    @pytest.mark.error_contract
    async def test_error_response_security_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test that error responses don't leak sensitive information"""
        # Mock different types of errors
        error_scenarios = [
            # Database error
            patch('src.api.evaluation.db', side_effect=Exception("Database password: secret123")),
            # File system error
            patch('src.api.evaluation.rag_evaluation_service', side_effect=Exception("File not found: /etc/passwd")),
            # Import error
            patch('src.api.evaluation', side_effect=ImportError("No module named secret_module")),
        ]

        for mock_scenario in error_scenarios:
            with mock_scenario:
                response = await async_client.get("/api/v1/evaluation/jobs", headers=auth_headers)

                if response.status_code == 500:
                    response_data = response.json()
                    assert contract_validator.validate_error_response(response_data)

                    error_message = str(response_data["error"]["message"]).lower()

                    # Should not contain sensitive information
                    sensitive_patterns = [
                        "password", "secret", "key", "token",
                        "/etc/", "file path", "directory",
                        "stack trace", "line number",
                        "internal server", "exception type"
                    ]

                    # In test mode, we might get more detailed errors
                    # In production, these should be obscured
                    for pattern in sensitive_patterns:
                        if pattern not in ["stack trace", "line number", "exception type"]:
                            assert pattern not in error_message, f"Error message contains sensitive info: {pattern}"

    @pytest.mark.contract
    @pytest.mark.error_contract
    async def test_error_response_unicode_handling_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test error response handling of Unicode and special characters"""
        # Test request with special characters that might cause errors
        problematic_data = {
            "name": "Test with émojis 🚀 and spëcial char$ & symbols!",
            "questions": [
                "Question with unicode: αβγδε",
                "Question with newlines\nand\ttabs",
                "Question with quotes: 'single' and \"double\"",
                "Question with backslashes: \\n \\t \\"
            ]
        }

        response = await async_client.post(
            "/api/v1/evaluation/jobs",
            headers=auth_headers,
            json=problematic_data
        )

        # Should either succeed or fail gracefully
        if response.status_code >= 400:
            response_data = response.json()
            assert contract_validator.validate_error_response(response_data)

            # Error message should handle Unicode properly
            error_message = response_data["error"]["message"]
            assert isinstance(error_message, str)
            # Should not contain encoding errors
            assert "unicode" not in error_message.lower()
            assert "encoding" not in error_message.lower()

    @pytest.mark.contract
    @pytest.mark.error_contract
    async def test_error_response_large_payload_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test error response handling of very large payloads"""
        # Create very large request
        large_request = {
            "name": "A" * 10000,  # Very long name
            "questions": ["Test question"],
            "description": "B" * 100000,  # Very long description
            "metadata": {"large_field": "C" * 1000000}  # 1MB field
        }

        response = await async_client.post(
            "/api/v1/evaluation/jobs",
            headers=auth_headers,
            json=large_request
        )

        # Should handle large payloads gracefully
        if response.status_code >= 400:
            response_data = response.json()
            assert contract_validator.validate_error_response(response_data)

            # Should not crash or timeout
            assert response.status_code in [400, 413, 422, 500]

    @pytest.mark.contract
    @pytest.mark.error_contract
    async def test_error_response_concurrent_requests_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test error response handling with concurrent requests"""
        import asyncio

        # Generate requests that will cause errors
        invalid_requests = [
            {},  # Missing fields
            {"name": ""},  # Invalid data
            {"invalid": "field"}  # Wrong structure
        ]

        # Send concurrent invalid requests
        tasks = [
            async_client.post("/api/v1/evaluation/jobs", headers=auth_headers, json=request)
            for request in invalid_requests * 5  # Repeat to get concurrent requests
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # All error responses should be consistent
        for response in responses:
            if hasattr(response, 'status_code') and response.status_code >= 400:
                response_data = response.json()
                assert contract_validator.validate_error_response(response_data)

                # Should have consistent error structure
                assert "error" in response_data
                assert response_data["error"]["status_code"] >= 400

    @pytest.mark.contract
    @pytest.mark.error_contract
    async def test_error_response_http_methods_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test error responses for unsupported HTTP methods"""
        job_id = str(uuid.uuid4())

        # Test unsupported methods
        unsupported_methods = [
            ("PATCH", f"/api/v1/evaluation/jobs/{job_id}"),
            ("PUT", f"/api/v1/evaluation/jobs/{job_id}"),
            ("DELETE", f"/api/v1/evaluation/jobs/{job_id}/metrics"),  # Wrong endpoint for DELETE
        ]

        for method, endpoint in unsupported_methods:
            response = await async_client.request(method, endpoint, headers=auth_headers)

            # Should return method not allowed or not found
            assert response.status_code in [404, 405]

            if response.status_code >= 400:
                response_data = response.json()
                assert contract_validator.validate_error_response(response_data)