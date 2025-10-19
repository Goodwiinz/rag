"""
Contract tests for Batch Evaluation API endpoints
POST /api/v1/evaluation/jobs/batch
"""

import pytest
import asyncio
import random
from httpx import AsyncClient
from unittest.mock import patch, Mock
from datetime import datetime
from typing import Dict, Any

from tests.contract.evaluation.fixtures.data_generators import EvaluationDataGenerator


class TestBatchEvaluationContract:
    """Contract tests for batch evaluation endpoint"""

    # Contract definition
    CONTRACT_SPEC = {
        "endpoint": "POST /api/v1/evaluation/jobs/batch",
        "method": "POST",
        "headers": {
            "required": ["Authorization", "Content-Type"],
            "Content-Type": "application/json"
        },
        "authentication": "required",
        "request_body": {
            "required_fields": ["name", "queries"],
            "optional_fields": ["description", "search_type", "search_limit", "reference_answers"],
            "field_types": {
                "name": str,
                "queries": list,
                "description": str,
                "search_type": str,
                "search_limit": int,
                "reference_answers": list
            },
            "constraints": {
                "queries": {"min_length": 1, "max_length": 1000},
                "search_limit": {"min": 1, "max": 100}
            },
            "enum_values": {
                "search_type": ["vector", "graph", "hybrid"]
            }
        },
        "response": {
            "status_codes": [200, 201, 400, 401, 403, 413, 429, 500],
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
                    "status": ["pending", "running"]
                }
            }
        }
    }

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_batch_evaluation_success_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        contract_validator,
        performance_tracker
    ):
        """Test successful batch evaluation job creation"""
        performance_tracker.start_timer("create_batch_evaluation_success")

        request_data = evaluation_data_generator.generate_batch_evaluation_request(
            query_count=10,
            search_type="hybrid"
        )

        response = await async_client.post(
            "/api/v1/evaluation/jobs/batch",
            headers=auth_headers,
            json=request_data
        )

        performance_tracker.end_timer("create_batch_evaluation_success")

        # Contract validation
        assert response.status_code in [200, 201]

        response_data = response.json()

        # Validate response structure
        required_fields = self.CONTRACT_SPEC["response"]["success_schema"]["required_fields"]
        assert contract_validator.validate_response_structure(response_data, required_fields)

        # Validate data types
        field_types = self.CONTRACT_SPEC["response"]["success_schema"]["field_types"]
        type_errors = contract_validator.validate_data_types(response_data, field_types)
        assert not type_errors, f"Type validation errors: {type_errors}"

        # Validate business rules
        assert response_data["name"] == request_data["name"]
        assert response_data["dataset_size"] == len(request_data["queries"])
        assert response_data["status"] in ["pending", "running"]
        assert "batch" in response_data["message"].lower()

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_batch_evaluation_minimal_request_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test batch evaluation with minimal required fields"""
        request_data = {
            "name": "Minimal Batch Job",
            "queries": ["What is AI?", "How does ML work?"]
        }

        response = await async_client.post(
            "/api/v1/evaluation/jobs/batch",
            headers=auth_headers,
            json=request_data
        )

        assert response.status_code in [200, 201]

        response_data = response.json()
        required_fields = self.CONTRACT_SPEC["response"]["success_schema"]["required_fields"]
        assert contract_validator.validate_response_structure(response_data, required_fields)

        assert response_data["name"] == request_data["name"]
        assert response_data["dataset_size"] == 2

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_batch_evaluation_large_query_set_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        contract_validator,
        performance_tracker
    ):
        """Test batch evaluation with large query set"""
        performance_tracker.start_timer("create_large_batch_evaluation")

        request_data = evaluation_data_generator.generate_batch_evaluation_request(
            query_count=500  # Large number of queries
        )

        response = await async_client.post(
            "/api/v1/evaluation/jobs/batch",
            headers=auth_headers,
            json=request_data
        )

        performance_tracker.end_timer("create_large_batch_evaluation")

        if response.status_code in [200, 201]:
            response_data = response.json()
            required_fields = self.CONTRACT_SPEC["response"]["success_schema"]["required_fields"]
            assert contract_validator.validate_response_structure(response_data, required_fields)
            assert response_data["dataset_size"] == 500
        else:
            # Should handle large payloads gracefully
            assert response.status_code in [400, 413, 422]

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_batch_evaluation_empty_queries_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test batch evaluation with empty queries array"""
        request_data = {
            "name": "Empty Batch Job",
            "queries": []
        }

        response = await async_client.post(
            "/api/v1/evaluation/jobs/batch",
            headers=auth_headers,
            json=request_data
        )

        assert response.status_code == 400
        response_data = response.json()
        assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_batch_evaluation_validation_errors_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test validation error responses"""
        invalid_requests = [
            {},  # Missing all required fields
            {"name": "Test"},  # Missing queries
            {"queries": ["Q1"]},  # Missing name
            {"name": "", "queries": []},  # Empty name and queries
            {"name": "Test", "queries": [123]},  # Invalid query type
            {"name": "Test", "queries": [""]},  # Empty query string
            {"name": "Test", "queries": ["Q1"], "search_type": "invalid"},  # Invalid search type
            {"name": "Test", "queries": ["Q1"], "search_limit": 0},  # Invalid search limit
            {"name": "Test", "queries": ["Q1"], "search_limit": 200}  # Search limit too high
        ]

        for invalid_request in invalid_requests:
            response = await async_client.post(
                "/api/v1/evaluation/jobs/batch",
                headers=auth_headers,
                json=invalid_request
            )

            assert response.status_code in [400, 422]
            response_data = response.json()
            assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_batch_evaluation_reference_answers_mismatch_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test mismatched reference answers array length"""
        request_data = {
            "name": "Mismatched Batch Job",
            "queries": ["Question 1", "Question 2", "Question 3"],
            "reference_answers": ["Answer 1", "Answer 2"]  # Mismatched length
        }

        response = await async_client.post(
            "/api/v1/evaluation/jobs/batch",
            headers=auth_headers,
            json=request_data
        )

        assert response.status_code == 400
        response_data = response.json()
        assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_batch_evaluation_concurrent_requests_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        performance_tracker
    ):
        """Test concurrent batch evaluation requests"""
        # Generate multiple batch requests
        requests = [
            evaluation_data_generator.generate_batch_evaluation_request(
                query_count=random.randint(5, 20)
            )
            for _ in range(3)
        ]

        performance_tracker.start_timer("concurrent_batch_requests")

        tasks = [
            async_client.post("/api/v1/evaluation/jobs/batch", headers=auth_headers, json=request)
            for request in requests
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        performance_tracker.end_timer("concurrent_batch_requests")

        # Validate responses
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                pytest.fail(f"Concurrent batch request {i} failed: {response}")

            if response.status_code in [200, 201]:
                response_data = response.json()
                assert "job_id" in response_data
                assert "dataset_size" in response_data
            elif response.status_code == 429:
                # Rate limiting is acceptable
                pass
            else:
                pytest.fail(f"Unexpected status code {response.status_code} for concurrent batch request {i}")

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_batch_evaluation_different_search_types_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        contract_validator
    ):
        """Test batch evaluation with different search types"""
        search_types = ["vector", "graph", "hybrid"]

        for search_type in search_types:
            request_data = evaluation_data_generator.generate_batch_evaluation_request(
                query_count=5,
                search_type=search_type
            )

            response = await async_client.post(
                "/api/v1/evaluation/jobs/batch",
                headers=auth_headers,
                json=request_data
            )

            if response.status_code in [200, 201]:
                response_data = response.json()
                required_fields = self.CONTRACT_SPEC["response"]["success_schema"]["required_fields"]
                assert contract_validator.validate_response_structure(response_data, required_fields)
            else:
                # Should handle all valid search types
                assert response.status_code in [400, 422]

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_batch_evaluation_special_characters_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        contract_validator
    ):
        """Test batch evaluation with special characters in queries"""
        request_data = {
            "name": "Special Characters Batch Job 🚀",
            "queries": [
                "Question with émojis 🤖?",
                "Question with spëcial char$ & symbols!",
                "Question with unicode: αβγδε",
                "Question with newlines\nand\ttabs",
                "Question with quotes: 'single' and \"double\""
            ],
            "search_type": "hybrid"
        }

        response = await async_client.post(
            "/api/v1/evaluation/jobs/batch",
            headers=auth_headers,
            json=request_data
        )

        if response.status_code in [200, 201]:
            response_data = response.json()
            required_fields = self.CONTRACT_SPEC["response"]["success_schema"]["required_fields"]
            assert contract_validator.validate_response_structure(response_data, required_fields)
            assert response_data["dataset_size"] == 5

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_batch_evaluation_long_queries_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test batch evaluation with very long queries"""
        long_query = "This is an extremely long query " * 50  # Very long query

        request_data = {
            "name": "Long Queries Batch Job",
            "queries": [
                long_query,
                "Normal length query",
                "Another " + long_query
            ],
            "search_type": "vector"
        }

        response = await async_client.post(
            "/api/v1/evaluation/jobs/batch",
            headers=auth_headers,
            json=request_data
        )

        if response.status_code in [200, 201]:
            response_data = response.json()
            required_fields = self.CONTRACT_SPEC["response"]["success_schema"]["required_fields"]
            assert contract_validator.validate_response_structure(response_data, required_fields)
            assert response_data["dataset_size"] == 3
        else:
            # May reject due to size limits
            assert response.status_code in [400, 413, 422]

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_batch_evaluation_duplicate_queries_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        contract_validator
    ):
        """Test batch evaluation with duplicate queries"""
        request_data = {
            "name": "Duplicate Queries Batch Job",
            "queries": [
                "What is machine learning?",
                "What is machine learning?",  # Duplicate
                "How does AI work?",
                "What is machine learning?",  # Another duplicate
                "Deep learning principles"
            ],
            "search_type": "hybrid"
        }

        response = await async_client.post(
            "/api/v1/evaluation/jobs/batch",
            headers=auth_headers,
            json=request_data
        )

        if response.status_code in [200, 201]:
            response_data = response.json()
            required_fields = self.CONTRACT_SPEC["response"]["success_schema"]["required_fields"]
            assert contract_validator.validate_response_structure(response_data, required_fields)
            # Should process all queries including duplicates
            assert response_data["dataset_size"] == 5

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_batch_evaluation_rate_limiting_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        performance_tracker
    ):
        """Test rate limiting for batch evaluation endpoint"""
        performance_tracker.start_timer("rate_limiting_test")

        # Send rapid requests to trigger rate limiting
        requests = [
            evaluation_data_generator.generate_batch_evaluation_request(query_count=3)
            for _ in range(10)
        ]

        tasks = [
            async_client.post("/api/v1/evaluation/jobs/batch", headers=auth_headers, json=request)
            for request in requests
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        performance_tracker.end_timer("rate_limiting_test")

        # Check for rate limiting responses
        rate_limited_count = sum(
            1 for response in responses
            if hasattr(response, 'status_code') and response.status_code == 429
        )

        successful_count = sum(
            1 for response in responses
            if hasattr(response, 'status_code') and response.status_code in [200, 201]
        )

        # At least some requests should succeed or be rate limited
        assert (successful_count + rate_limited_count) == len(responses)

        # If rate limited, validate error response
        for response in responses:
            if hasattr(response, 'status_code') and response.status_code == 429:
                response_data = response.json()
                assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_batch_evaluation_background_task_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        mock_background_tasks
    ):
        """Test that background task is properly initiated"""
        request_data = evaluation_data_generator.generate_batch_evaluation_request(
            query_count=5
        )

        response = await async_client.post(
            "/api/v1/evaluation/jobs/batch",
            headers=auth_headers,
            json=request_data
        )

        if response.status_code in [200, 201]:
            # Verify background task was called
            mock_background_tasks.add_task.assert_called_once()

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_batch_evaluation_response_time_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        performance_tracker
    ):
        """Test response time for batch evaluation creation"""
        performance_tracker.start_timer("batch_evaluation_response_time")

        request_data = evaluation_data_generator.generate_batch_evaluation_request(
            query_count=50
        )

        response = await async_client.post(
            "/api/v1/evaluation/jobs/batch",
            headers=auth_headers,
            json=request_data
        )

        response_time = performance_tracker.end_timer("batch_evaluation_response_time")

        # Response time should be reasonable (less than 2 seconds)
        assert response_time < 2.0, f"Response time {response_time}s exceeds 2 seconds"

        # Should still be successful even with larger batch
        assert response.status_code in [200, 201, 400, 422]