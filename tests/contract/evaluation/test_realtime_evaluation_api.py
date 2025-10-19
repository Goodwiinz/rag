"""
Contract tests for Real-time Evaluation API endpoints
POST /api/v1/evaluation/real-time
"""

import pytest
import asyncio
from httpx import AsyncClient
from unittest.mock import patch, Mock
from datetime import datetime
from typing import Dict, Any

from tests.contract.evaluation.fixtures.data_generators import EvaluationDataGenerator


class TestRealtimeEvaluationContract:
    """Contract tests for real-time evaluation endpoint"""

    # Contract definition
    CONTRACT_SPEC = {
        "endpoint": "POST /api/v1/evaluation/real-time",
        "method": "POST",
        "headers": {
            "required": ["Authorization", "Content-Type"],
            "Content-Type": "application/json"
        },
        "authentication": "required",
        "request_body": {
            "required_fields": ["query", "generated_answer", "retrieved_context"],
            "optional_fields": ["reference_answer"],
            "field_types": {
                "query": str,
                "generated_answer": str,
                "retrieved_context": list,
                "reference_answer": str
            },
            "constraints": {
                "query": {"min_length": 1, "max_length": 10000},
                "generated_answer": {"min_length": 1, "max_length": 50000},
                "retrieved_context": {"min_length": 1, "max_length": 50}
            }
        },
        "response": {
            "status_codes": [200, 202, 400, 401, 403, 429, 500],
            "success_schema": {
                "required_fields": ["task_id", "status", "message"],
                "field_types": {
                    "task_id": str,
                    "status": str,
                    "message": str
                },
                "enum_values": {
                    "status": ["started", "pending", "processing"]
                }
            }
        }
    }

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_realtime_evaluation_success_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        contract_validator,
        performance_tracker
    ):
        """Test successful real-time evaluation request"""
        performance_tracker.start_timer("realtime_evaluation_success")

        request_data = evaluation_data_generator.generate_real_time_evaluation_request(
            include_reference=True
        )

        response = await async_client.post(
            "/api/v1/evaluation/real-time",
            headers=auth_headers,
            json=request_data
        )

        performance_tracker.end_timer("realtime_evaluation_success")

        # Contract validation
        assert response.status_code in [200, 202]

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

        # Validate business rules
        assert len(response_data["task_id"]) > 0, "Task ID should not be empty"
        assert response_data["status"] in ["started", "pending", "processing"]
        assert "evaluation" in response_data["message"].lower()

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_realtime_evaluation_minimal_request_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test real-time evaluation with minimal required fields"""
        request_data = {
            "query": "What is machine learning?",
            "generated_answer": "Machine learning is a subset of AI that enables systems to learn from data.",
            "retrieved_context": [
                "Machine learning algorithms find patterns in data.",
                "Training data is essential for ML models.",
                "ML can make predictions without explicit programming."
            ]
        }

        response = await async_client.post(
            "/api/v1/evaluation/real-time",
            headers=auth_headers,
            json=request_data
        )

        assert response.status_code in [200, 202]

        response_data = response.json()
        required_fields = self.CONTRACT_SPEC["response"]["success_schema"]["required_fields"]
        assert contract_validator.validate_response_structure(response_data, required_fields)

        assert response_data["status"] in ["started", "pending", "processing"]

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_realtime_evaluation_with_reference_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        contract_validator
    ):
        """Test real-time evaluation with reference answer"""
        request_data = evaluation_data_generator.generate_real_time_evaluation_request(
            include_reference=True
        )

        response = await async_client.post(
            "/api/v1/evaluation/real-time",
            headers=auth_headers,
            json=request_data
        )

        assert response.status_code in [200, 202]

        response_data = response.json()
        required_fields = self.CONTRACT_SPEC["response"]["success_schema"]["required_fields"]
        assert contract_validator.validate_response_structure(response_data, required_fields)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_realtime_evaluation_validation_errors_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test validation error responses"""
        invalid_requests = [
            {},  # Missing all required fields
            {"query": "Test"},  # Missing generated_answer and retrieved_context
            {"query": "", "generated_answer": "Answer", "retrieved_context": []},  # Empty query
            {"query": "Test", "generated_answer": "", "retrieved_context": ["ctx"]},  # Empty answer
            {"query": "Test", "generated_answer": "Answer", "retrieved_context": []},  # Empty context
            {"query": 123, "generated_answer": "Answer", "retrieved_context": ["ctx"]},  # Invalid query type
            {"query": "Test", "generated_answer": 123, "retrieved_context": ["ctx"]},  # Invalid answer type
            {"query": "Test", "generated_answer": "Answer", "retrieved_context": "not a list"}  # Invalid context type
        ]

        for invalid_request in invalid_requests:
            response = await async_client.post(
                "/api/v1/evaluation/real-time",
                headers=auth_headers,
                json=invalid_request
            )

            assert response.status_code in [400, 422]
            response_data = response.json()
            assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_realtime_evaluation_large_context_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test real-time evaluation with large context"""
        # Generate a large context array
        large_context = [
            f"This is context passage {i} with sufficient length to be realistic."
            for i in range(100)  # 100 context passages
        ]

        request_data = {
            "query": "What is the main topic?",
            "generated_answer": "The main topic appears to be related to machine learning.",
            "retrieved_context": large_context
        }

        response = await async_client.post(
            "/api/v1/evaluation/real-time",
            headers=auth_headers,
            json=request_data
        )

        if response.status_code in [200, 202]:
            response_data = response.json()
            required_fields = self.CONTRACT_SPEC["response"]["success_schema"]["required_fields"]
            assert contract_validator.validate_response_structure(response_data, required_fields)
        else:
            # May reject due to size limits
            assert response.status_code in [400, 413, 422]

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_realtime_evaluation_long_text_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test real-time evaluation with very long text"""
        long_text = "This is an extremely long text " * 1000  # Very long text

        request_data = {
            "query": long_text,
            "generated_answer": long_text,
            "retrieved_context": [long_text, "Another context passage"]
        }

        response = await async_client.post(
            "/api/v1/evaluation/real-time",
            headers=auth_headers,
            json=request_data
        )

        if response.status_code in [200, 202]:
            response_data = response.json()
            required_fields = self.CONTRACT_SPEC["response"]["success_schema"]["required_fields"]
            assert contract_validator.validate_response_structure(response_data, required_fields)
        else:
            # May reject due to size limits
            assert response.status_code in [400, 413, 422]

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_realtime_evaluation_special_characters_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        contract_validator
    ):
        """Test real-time evaluation with special characters"""
        request_data = {
            "query": "Question with émojis 🤖 and spëcial char$ & symbols!",
            "generated_answer": "Answer with unicode: αβγδε and newlines\nand\ttabs and quotes: 'single' and \"double\"",
            "retrieved_context": [
                "Context with émojis 🚀",
                "Another context with spëcial char$",
                "Final context with unicode: αβγδε"
            ]
        }

        response = await async_client.post(
            "/api/v1/evaluation/real-time",
            headers=auth_headers,
            json=request_data
        )

        if response.status_code in [200, 202]:
            response_data = response.json()
            required_fields = self.CONTRACT_SPEC["response"]["success_schema"]["required_fields"]
            assert contract_validator.validate_response_structure(response_data, required_fields)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_realtime_evaluation_authentication_contract(
        self,
        async_client: AsyncClient,
        evaluation_data_generator: EvaluationDataGenerator,
        contract_validator
    ):
        """Test authentication requirement"""
        request_data = evaluation_data_generator.generate_real_time_evaluation_request()

        # Test without authentication
        response = await async_client.post(
            "/api/v1/evaluation/real-time",
            json=request_data
        )

        assert response.status_code == 401
        response_data = response.json()
        assert contract_validator.validate_error_response(response_data)

        # Test with invalid token
        invalid_headers = {"Authorization": "Bearer invalid-token", "Content-Type": "application/json"}
        response = await async_client.post(
            "/api/v1/evaluation/real-time",
            headers=invalid_headers,
            json=request_data
        )

        assert response.status_code == 401
        response_data = response.json()
        assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_realtime_evaluation_concurrent_requests_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        performance_tracker
    ):
        """Test concurrent real-time evaluation requests"""
        # Generate multiple requests
        requests = [
            evaluation_data_generator.generate_real_time_evaluation_request()
            for _ in range(5)
        ]

        performance_tracker.start_timer("concurrent_realtime_requests")

        tasks = [
            async_client.post("/api/v1/evaluation/real-time", headers=auth_headers, json=request)
            for request in requests
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        performance_tracker.end_timer("concurrent_realtime_requests")

        # Validate responses
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                pytest.fail(f"Concurrent real-time request {i} failed: {response}")

            if response.status_code in [200, 202]:
                response_data = response.json()
                assert "task_id" in response_data
                assert "status" in response_data
            elif response.status_code == 429:
                # Rate limiting is acceptable
                pass
            else:
                pytest.fail(f"Unexpected status code {response.status_code} for concurrent real-time request {i}")

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_realtime_evaluation_task_id_uniqueness_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator
    ):
        """Test that each request gets a unique task ID"""
        requests = [
            evaluation_data_generator.generate_real_time_evaluation_request()
            for _ in range(3)
        ]

        responses = await asyncio.gather(*[
            async_client.post("/api/v1/evaluation/real-time", headers=auth_headers, json=request)
            for request in requests
        ])

        task_ids = []
        for response in responses:
            if response.status_code in [200, 202]:
                response_data = response.json()
                task_ids.append(response_data["task_id"])

        # All task IDs should be unique
        assert len(task_ids) == len(set(task_ids)), "Task IDs should be unique"

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_realtime_evaluation_response_time_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        performance_tracker
    ):
        """Test response time for real-time evaluation"""
        performance_tracker.start_timer("realtime_evaluation_response_time")

        request_data = evaluation_data_generator.generate_real_time_evaluation_request()

        response = await async_client.post(
            "/api/v1/evaluation/real-time",
            headers=auth_headers,
            json=request_data
        )

        response_time = performance_tracker.end_timer("realtime_evaluation_response_time")

        # Real-time evaluation should be fast (less than 1 second)
        assert response_time < 1.0, f"Response time {response_time}s exceeds 1 second for real-time evaluation"

        assert response.status_code in [200, 202]

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_realtime_evaluation_single_context_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test real-time evaluation with single context passage"""
        request_data = {
            "query": "What is the main point?",
            "generated_answer": "The main point is about machine learning algorithms.",
            "retrieved_context": ["This is a single context passage about machine learning."]
        }

        response = await async_client.post(
            "/api/v1/evaluation/real-time",
            headers=auth_headers,
            json=request_data
        )

        assert response.status_code in [200, 202]

        response_data = response.json()
        required_fields = self.CONTRACT_SPEC["response"]["success_schema"]["required_fields"]
        assert contract_validator.validate_response_structure(response_data, required_fields)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_realtime_evaluation_empty_context_passages_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test real-time evaluation with empty context passages"""
        request_data = {
            "query": "What is AI?",
            "generated_answer": "AI is artificial intelligence.",
            "retrieved_context": ["", "   ", ""]  # Empty or whitespace-only passages
        }

        response = await async_client.post(
            "/api/v1/evaluation/real-time",
            headers=auth_headers,
            json=request_data
        )

        # May accept or reject empty context passages
        if response.status_code in [200, 202]:
            response_data = response.json()
            required_fields = self.CONTRACT_SPEC["response"]["success_schema"]["required_fields"]
            assert contract_validator.validate_response_structure(response_data, required_fields)
        else:
            assert response.status_code in [400, 422]

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_realtime_evaluation_background_task_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        mock_celery_tasks
    ):
        """Test that background task is properly initiated"""
        request_data = evaluation_data_generator.generate_real_time_evaluation_request()

        response = await async_client.post(
            "/api/v1/evaluation/real-time",
            headers=auth_headers,
            json=request_data
        )

        if response.status_code in [200, 202]:
            # Verify background task was called
            mock_celery_tasks.delay.assert_called_once()

            # Verify task was called with correct parameters
            call_args = mock_celery_tasks.delay.call_args[0]
            assert len(call_args) >= 4  # query, generated_answer, retrieved_context, reference_answer (optional)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_realtime_evaluation_rate_limiting_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        performance_tracker
    ):
        """Test rate limiting for real-time evaluation endpoint"""
        performance_tracker.start_timer("realtime_rate_limiting_test")

        # Send rapid requests to trigger rate limiting
        requests = [
            evaluation_data_generator.generate_real_time_evaluation_request()
            for _ in range(20)
        ]

        tasks = [
            async_client.post("/api/v1/evaluation/real-time", headers=auth_headers, json=request)
            for request in requests
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        performance_tracker.end_timer("realtime_rate_limiting_test")

        # Check for rate limiting responses
        rate_limited_count = sum(
            1 for response in responses
            if hasattr(response, 'status_code') and response.status_code == 429
        )

        successful_count = sum(
            1 for response in responses
            if hasattr(response, 'status_code') and response.status_code in [200, 202]
        )

        # At least some requests should succeed or be rate limited
        assert (successful_count + rate_limited_count) == len(responses)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_realtime_evaluation_server_error_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        contract_validator,
        mock_celery_tasks
    ):
        """Test server error handling"""
        request_data = evaluation_data_generator.generate_real_time_evaluation_request()

        # Mock server error
        mock_celery_tasks.delay.side_effect = Exception("Celery server unavailable")

        response = await async_client.post(
            "/api/v1/evaluation/real-time",
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
        assert response_data["error"]["type"] in ["internal_error", "server_error"]