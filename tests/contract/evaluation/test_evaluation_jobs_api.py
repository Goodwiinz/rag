"""
Contract tests for Evaluation Jobs API endpoints
POST /api/v1/evaluation/jobs
"""

import pytest
import json
from httpx import AsyncClient
from unittest.mock import patch, Mock
from datetime import datetime, timezone
from typing import Dict, Any

from tests.contract.evaluation.fixtures.data_generators import (
    EvaluationDataGenerator, JobDataGenerator, MetricDataGenerator
)


class TestEvaluationJobsContract:
    """Contract tests for evaluation jobs creation endpoint"""

    # Contract definition
    CONTRACT_SPEC = {
        "endpoint": "POST /api/v1/evaluation/jobs",
        "method": "POST",
        "headers": {
            "required": ["Authorization", "Content-Type"],
            "Content-Type": "application/json"
        },
        "authentication": "required",
        "request_body": {
            "required_fields": ["name", "questions"],
            "optional_fields": ["description", "evaluation_type", "reference_answers", "contexts", "search_type", "search_limit"],
            "field_types": {
                "name": str,
                "questions": list,
                "description": str,
                "evaluation_type": str,
                "reference_answers": list,
                "contexts": list,
                "search_type": str,
                "search_limit": int
            },
            "enum_values": {
                "evaluation_type": ["rag_triad", "answer_relevancy", "faithfulness", "contextual_relevancy", "custom_metric"],
                "search_type": ["vector", "graph", "hybrid"]
            }
        },
        "response": {
            "status_codes": [200, 201, 400, 401, 403, 429, 500],
            "success_schema": {
                "required_fields": ["job_id", "name", "status", "dataset_size", "created_at", "message"],
                "field_types": {
                    "job_id": str,
                    "name": str,
                    "status": str,
                    "dataset_size": int,
                    "created_at": str,
                    "message": str
                },
                "enum_values": {
                    "status": ["pending", "running", "completed", "failed", "cancelled"]
                }
            },
            "error_schema": {
                "required_fields": ["error"],
                "error_fields": ["message", "status_code", "type"]
            }
        }
    }

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_evaluation_job_success_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        contract_validator,
        performance_tracker
    ):
        """Test successful evaluation job creation contract"""
        performance_tracker.start_timer("create_evaluation_job_success")

        # Generate valid request data
        request_data = evaluation_data_generator.generate_evaluation_request(
            question_count=5,
            include_references=True,
            include_contexts=True
        )

        response = await async_client.post(
            "/api/v1/evaluation/jobs",
            headers=auth_headers,
            json=request_data
        )

        performance_tracker.end_timer("create_evaluation_job_success")

        # Contract validation
        assert response.status_code in [200, 201], f"Expected 200 or 201, got {response.status_code}"

        response_data = response.json()

        # Validate response structure
        required_fields = self.CONTRACT_SPEC["response"]["success_schema"]["required_fields"]
        assert contract_validator.validate_response_structure(response_data, required_fields)

        # Validate data types
        field_types = self.CONTRACT_SPEC["response"]["success_schema"]["field_types"]
        type_errors = contract_validator.validate_data_types(response_data, field_types)
        assert not type_errors, f"Type validation errors: {type_errors}"

        # Validate enum values
        enum_values = self.CONTRACT_SPEC["response"]["success_schema"]["enum_values"]
        enum_errors = contract_validator.validate_enum_values(response_data, enum_values)
        assert not enum_errors, f"Enum validation errors: {enum_errors}"

        # Validate specific business rules
        assert len(response_data["job_id"]) > 0, "Job ID should not be empty"
        assert response_data["name"] == request_data["name"], "Job name should match request"
        assert response_data["status"] in ["pending", "running"], "Initial status should be pending or running"
        assert response_data["dataset_size"] == len(request_data["questions"]), "Dataset size should match question count"
        assert response_data["message"] is not None, "Message should be provided"

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_evaluation_job_minimal_request_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        contract_validator
    ):
        """Test evaluation job creation with minimal required fields"""
        # Generate minimal request data
        request_data = {
            "name": "Minimal Evaluation Job",
            "questions": ["What is machine learning?"]
        }

        response = await async_client.post(
            "/api/v1/evaluation/jobs",
            headers=auth_headers,
            json=request_data
        )

        # Contract validation
        assert response.status_code in [200, 201]

        response_data = response.json()

        # Validate response structure
        required_fields = self.CONTRACT_SPEC["response"]["success_schema"]["required_fields"]
        assert contract_validator.validate_response_structure(response_data, required_fields)

        # Validate minimal response contains required fields
        assert response_data["name"] == request_data["name"]
        assert response_data["dataset_size"] == 1
        assert response_data["status"] in ["pending", "running"]

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_evaluation_job_validation_errors_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test validation error responses"""
        # Test missing required fields
        invalid_requests = [
            {},  # Missing all required fields
            {"name": "Test Job"},  # Missing questions
            {"questions": []},  # Missing name and empty questions
            {"name": "", "questions": []},  # Empty name and questions
            {"name": "Test", "questions": ["Q1"], "evaluation_type": "invalid_type"}  # Invalid enum
        ]

        for invalid_request in invalid_requests:
            response = await async_client.post(
                "/api/v1/evaluation/jobs",
                headers=auth_headers,
                json=invalid_request
            )

            assert response.status_code == 400, f"Expected 400 for invalid request: {invalid_request}"

            response_data = response.json()
            assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_evaluation_job_array_length_validation_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test array length validation"""
        # Test mismatched array lengths
        invalid_request = {
            "name": "Invalid Arrays Job",
            "questions": ["Question 1", "Question 2"],
            "reference_answers": ["Answer 1"]  # Mismatched length
        }

        response = await async_client.post(
            "/api/v1/evaluation/jobs",
            headers=auth_headers,
            json=invalid_request
        )

        assert response.status_code == 400
        response_data = response.json()
        assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_evaluation_job_authentication_contract(
        self,
        async_client: AsyncClient,
        evaluation_data_generator: EvaluationDataGenerator,
        contract_validator
    ):
        """Test authentication requirement"""
        request_data = evaluation_data_generator.generate_evaluation_request()

        # Test without authentication
        response = await async_client.post(
            "/api/v1/evaluation/jobs",
            json=request_data
        )

        assert response.status_code == 401
        response_data = response.json()
        assert contract_validator.validate_error_response(response_data)

        # Test with invalid token
        invalid_headers = {"Authorization": "Bearer invalid-token", "Content-Type": "application/json"}
        response = await async_client.post(
            "/api/v1/evaluation/jobs",
            headers=invalid_headers,
            json=request_data
        )

        assert response.status_code == 401
        response_data = response.json()
        assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_evaluation_job_content_type_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator
    ):
        """Test Content-Type header requirement"""
        request_data = evaluation_data_generator.generate_evaluation_request()

        # Test with incorrect content type
        headers = auth_headers.copy()
        headers["Content-Type"] = "text/plain"

        response = await async_client.post(
            "/api/v1/evaluation/jobs",
            headers=headers,
            data=json.dumps(request_data)
        )

        # FastAPI should handle this gracefully, but the contract should be validated
        assert response.status_code in [400, 422, 415]

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_evaluation_job_request_size_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        contract_validator
    ):
        """Test large request handling"""
        # Generate request with many questions
        large_request = evaluation_data_generator.generate_evaluation_request(
            question_count=100,  # Large number of questions
            include_references=True,
            include_contexts=True
        )

        response = await async_client.post(
            "/api/v1/evaluation/jobs",
            headers=auth_headers,
            json=large_request
        )

        # Should either succeed or return appropriate error for large payload
        if response.status_code in [200, 201]:
            response_data = response.json()
            required_fields = self.CONTRACT_SPEC["response"]["success_schema"]["required_fields"]
            assert contract_validator.validate_response_structure(response_data, required_fields)
        else:
            assert response.status_code in [400, 413, 422]  # Bad Request, Payload Too Large, or Unprocessable Entity

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_evaluation_job_concurrent_requests_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        performance_tracker
    ):
        """Test concurrent request handling"""
        import asyncio

        # Generate multiple requests
        requests = [
            evaluation_data_generator.generate_evaluation_request(question_count=3)
            for _ in range(5)
        ]

        performance_tracker.start_timer("concurrent_requests")

        # Send concurrent requests
        tasks = [
            async_client.post("/api/v1/evaluation/jobs", headers=auth_headers, json=request)
            for request in requests
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        performance_tracker.end_timer("concurrent_requests")

        # Validate all responses
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                pytest.fail(f"Request {i} failed with exception: {response}")

            # Should either succeed or return rate limiting error
            if response.status_code in [200, 201]:
                response_data = response.json()
                assert "job_id" in response_data
                assert "name" in response_data
            elif response.status_code == 429:
                # Rate limiting is acceptable
                pass
            else:
                pytest.fail(f"Unexpected status code {response.status_code} for concurrent request {i}")

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_evaluation_job_data_types_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test data type validation in request"""
        # Test requests with incorrect data types
        type_mismatch_requests = [
            {"name": 123, "questions": ["Valid question"]},  # name should be string
            {"name": "Valid name", "questions": "not a list"},  # questions should be list
            {"name": "Valid name", "questions": [123]},  # question should be string
            {"name": "Valid name", "questions": ["Q1"], "search_limit": "not a number"},  # search_limit should be int
            {"name": "Valid name", "questions": ["Q1"], "evaluation_type": 123}  # evaluation_type should be string
        ]

        for invalid_request in type_mismatch_requests:
            response = await async_client.post(
                "/api/v1/evaluation/jobs",
                headers=auth_headers,
                json=invalid_request
            )

            # Should return validation error
            assert response.status_code in [400, 422]
            response_data = response.json()
            assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_evaluation_job_special_characters_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        contract_validator
    ):
        """Test handling of special characters in request data"""
        # Generate request with special characters
        request_data = evaluation_data_generator.generate_evaluation_request(
            job_name="Test Job with émojis 🚀 & spëcial char$!",
            question_count=3
        )

        # Add special characters to questions
        request_data["questions"] = [
            "Question with émojis 🤖?",
            "Question with spëcial char$ & symbols!",
            "Question with unicode: αβγδε"
        ]

        response = await async_client.post(
            "/api/v1/evaluation/jobs",
            headers=auth_headers,
            json=request_data
        )

        if response.status_code in [200, 201]:
            response_data = response.json()
            required_fields = self.CONTRACT_SPEC["response"]["success_schema"]["required_fields"]
            assert contract_validator.validate_response_structure(response_data, required_fields)

            # Verify special characters are preserved
            assert "émojis" in response_data["name"] or "spëcial" in response_data["name"]

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_evaluation_job_response_headers_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator
    ):
        """Test response headers contract"""
        request_data = evaluation_data_generator.generate_evaluation_request()

        response = await async_client.post(
            "/api/v1/evaluation/jobs",
            headers=auth_headers,
            json=request_data
        )

        # Validate response headers for successful responses
        if response.status_code in [200, 201]:
            # Check content type header
            assert "content-type" in response.headers
            assert "application/json" in response.headers["content-type"]

            # Check for CORS headers if applicable
            # Note: This depends on CORS configuration
            if "access-control-allow-origin" in response.headers:
                assert response.headers["access-control-allow-origin"] is not None

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_evaluation_job_database_error_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        contract_validator,
        mock_rag_evaluation_service
    ):
        """Test database error handling"""
        request_data = evaluation_data_generator.generate_evaluation_request()

        # Mock database error
        mock_rag_evaluation_service.create_evaluation_job.side_effect = Exception("Database connection failed")

        response = await async_client.post(
            "/api/v1/evaluation/jobs",
            headers=auth_headers,
            json=request_data
        )

        # Should return server error
        assert response.status_code == 500
        response_data = response.json()
        assert contract_validator.validate_error_response(response_data)

        # Verify error structure
        assert "error" in response_data
        assert response_data["error"]["status_code"] == 500
        assert response_data["error"]["type"] in ["internal_error", "database_error"]