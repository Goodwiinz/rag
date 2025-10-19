"""
Contract tests for Evaluation Comparison API endpoints
POST /api/v1/evaluation/comparisons
GET /api/v1/evaluation/comparisons
"""

import pytest
import uuid
import random
import asyncio
from httpx import AsyncClient
from unittest.mock import patch, Mock
from datetime import datetime, timedelta
from typing import Dict, Any

from tests.contract.evaluation.fixtures.data_generators import EvaluationDataGenerator, JobDataGenerator


class TestEvaluationComparisonsContract:
    """Contract tests for evaluation comparison endpoints"""

    # Contract definitions
    CREATE_COMPARISON_CONTRACT = {
        "endpoint": "POST /api/v1/evaluation/comparisons",
        "method": "POST",
        "headers": {
            "required": ["Authorization", "Content-Type"],
            "Content-Type": "application/json"
        },
        "authentication": "required",
        "request_body": {
            "required_fields": ["name", "baseline_job_id", "comparison_job_id"],
            "field_types": {
                "name": str,
                "baseline_job_id": str,
                "comparison_job_id": str
            },
            "constraints": {
                "baseline_job_id": {"type": str, "format": "uuid"},
                "comparison_job_id": {"type": str, "format": "uuid"},
                "name": {"min_length": 1, "max_length": 255}
            }
        },
        "response": {
            "status_codes": [200, 201, 400, 401, 403, 404, 422, 500],
            "success_schema": {
                "required_fields": [
                    "status", "message", "baseline_job", "comparison_job", "name"
                ],
                "field_types": {
                    "status": str,
                    "message": str,
                    "baseline_job": str,
                    "comparison_job": str,
                    "name": str
                },
                "enum_values": {
                    "status": ["started", "pending", "processing"]
                }
            }
        }
    }

    LIST_COMPARISONS_CONTRACT = {
        "endpoint": "GET /api/v1/evaluation/comparisons",
        "method": "GET",
        "headers": {
            "required": ["Authorization"]
        },
        "authentication": "required",
        "query_parameters": {
            "optional": ["limit", "offset"],
            "constraints": {
                "limit": {"type": int, "min": 1, "max": 100, "default": 20},
                "offset": {"type": int, "min": 0, "default": 0}
            }
        },
        "response": {
            "status_codes": [200, 401, 403, 422, 500],
            "success_schema": {
                "type": "array",
                "item_schema": {
                    "required_fields": [
                        "id", "name", "description", "baseline_job_id",
                        "comparison_job_id", "created_at"
                    ],
                    "field_types": {
                        "id": str,
                        "name": str,
                        "description": str,
                        "baseline_job_id": str,
                        "comparison_job_id": str,
                        "created_at": str
                    },
                    "optional_fields": [
                        "baseline_score", "comparison_score", "improvement_percentage",
                        "statistical_significance"
                    ]
                }
            }
        }
    }

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_evaluation_comparison_success_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_user,
        test_organization,
        job_data_generator: JobDataGenerator,
        evaluation_data_generator: EvaluationDataGenerator,
        contract_validator,
        performance_tracker,
        mock_background_tasks
    ):
        """Test successful evaluation comparison creation"""
        performance_tracker.start_timer("create_evaluation_comparison_success")

        # Generate test jobs for comparison
        baseline_job = job_data_generator.generate_job_record(
            organization_id=str(test_organization.id),
            user_id=str(test_user.id),
            status="completed"
        )

        comparison_job = job_data_generator.generate_job_record(
            organization_id=str(test_organization.id),
            user_id=str(test_user.id),
            status="completed"
        )

        request_data = evaluation_data_generator.generate_comparison_request(
            baseline_job_id=str(baseline_job["id"]),
            comparison_job_id=str(comparison_job["id"])
        )

        # Mock job queries
        mock_baseline_job = Mock()
        mock_baseline_job.id = baseline_job["id"]
        mock_baseline_job.organization_id = str(test_organization.id)

        mock_comparison_job = Mock()
        mock_comparison_job.id = comparison_job["id"]
        mock_comparison_job.organization_id = str(test_organization.id)

        with patch('src.api.evaluation.db') as mock_db:
            # Mock both job queries
            mock_query = Mock()
            mock_query.filter.return_value.first.side_effect = [
                mock_baseline_job,
                mock_comparison_job
            ]
            mock_db.query.return_value = mock_query

            response = await async_client.post(
                "/api/v1/evaluation/comparisons",
                headers=auth_headers,
                json=request_data
            )

        performance_tracker.end_timer("create_evaluation_comparison_success")

        # Contract validation
        assert response.status_code in [200, 201]

        response_data = response.json()

        # Validate response structure
        required_fields = self.CREATE_COMPARISON_CONTRACT["response"]["success_schema"]["required_fields"]
        assert contract_validator.validate_response_structure(response_data, required_fields)

        # Validate data types
        field_types = self.CREATE_COMPARISON_CONTRACT["response"]["success_schema"]["field_types"]
        type_errors = contract_validator.validate_data_types(response_data, field_types)
        assert not type_errors, f"Type validation errors: {type_errors}"

        # Validate business rules
        assert response_data["name"] == request_data["name"]
        assert response_data["baseline_job"] == request_data["baseline_job_id"]
        assert response_data["comparison_job"] == request_data["comparison_job_id"]
        assert response_data["status"] in ["started", "pending", "processing"]
        assert "comparison" in response_data["message"].lower()

        # Verify background task was initiated
        mock_background_tasks.add_task.assert_called_once()

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_evaluation_comparison_validation_errors_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test validation error responses"""
        invalid_requests = [
            {},  # Missing all required fields
            {"name": "Test Comparison"},  # Missing job IDs
            {"baseline_job_id": str(uuid.uuid4())},  # Missing name and comparison job
            {"name": "", "baseline_job_id": str(uuid.uuid4()), "comparison_job_id": str(uuid.uuid4())},  # Empty name
            {"name": "Test", "baseline_job_id": "invalid-uuid", "comparison_job_id": str(uuid.uuid4())},  # Invalid baseline ID
            {"name": "Test", "baseline_job_id": str(uuid.uuid4()), "comparison_job_id": "invalid-uuid"},  # Invalid comparison ID
            {"name": "Test", "baseline_job_id": str(uuid.uuid4()), "comparison_job_id": str(uuid.uuid4())}  # Both jobs don't exist
        ]

        for invalid_request in invalid_requests:
            response = await async_client.post(
                "/api/v1/evaluation/comparisons",
                headers=auth_headers,
                json=invalid_request
            )

            assert response.status_code in [400, 404, 422]
            response_data = response.json()
            assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_evaluation_comparison_same_job_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test comparison with same job ID (should be rejected)"""
        job_id = str(uuid.uuid4())

        request_data = {
            "name": "Self Comparison Test",
            "baseline_job_id": job_id,
            "comparison_job_id": job_id  # Same as baseline
        }

        response = await async_client.post(
            "/api/v1/evaluation/comparisons",
            headers=auth_headers,
            json=request_data
        )

        # Should reject comparison of same job
        assert response.status_code in [400, 422]
        response_data = response.json()
        assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_evaluation_comparison_job_not_found_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_user,
        test_organization,
        job_data_generator: JobDataGenerator,
        evaluation_data_generator: EvaluationDataGenerator,
        contract_validator
    ):
        """Test comparison with non-existent jobs"""
        # Generate one existing job
        existing_job = job_data_generator.generate_job_record(
            organization_id=str(test_organization.id),
            user_id=str(test_user.id),
            status="completed"
        )

        # Try to compare with non-existent job
        request_data = evaluation_data_generator.generate_comparison_request(
            baseline_job_id=str(existing_job["id"]),
            comparison_job_id=str(uuid.uuid4())  # Non-existent
        )

        mock_existing_job = Mock()
        mock_existing_job.id = existing_job["id"]
        mock_existing_job.organization_id = str(test_organization.id)

        with patch('src.api.evaluation.db') as mock_db:
            mock_query = Mock()
            mock_query.filter.return_value.first.side_effect = [
                mock_existing_job,  # Baseline job exists
                None  # Comparison job doesn't exist
            ]
            mock_db.query.return_value = mock_query

            response = await async_client.post(
                "/api/v1/evaluation/comparisons",
                headers=auth_headers,
                json=request_data
            )

        assert response.status_code == 404
        response_data = response.json()
        assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_evaluation_comparison_cross_organization_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_user,
        test_organization,
        job_data_generator: JobDataGenerator,
        evaluation_data_generator: EvaluationDataGenerator,
        contract_validator
    ):
        """Test comparison with job from different organization (should be blocked)"""
        # Generate job in test organization
        valid_job = job_data_generator.generate_job_record(
            organization_id=str(test_organization.id),
            user_id=str(test_user.id),
            status="completed"
        )

        # Generate job in different organization
        other_org_job = job_data_generator.generate_job_record(
            organization_id=str(uuid.uuid4()),  # Different organization
            user_id=str(uuid.uuid4()),
            status="completed"
        )

        request_data = evaluation_data_generator.generate_comparison_request(
            baseline_job_id=str(valid_job["id"]),
            comparison_job_id=str(other_org_job["id"])
        )

        mock_valid_job = Mock()
        mock_valid_job.id = valid_job["id"]
        mock_valid_job.organization_id = str(test_organization.id)

        with patch('src.api.evaluation.db') as mock_db:
            mock_query = Mock()
            mock_query.filter.return_value.first.side_effect = [
                mock_valid_job,  # Baseline job accessible
                None  # Comparison job not accessible (different org)
            ]
            mock_db.query.return_value = mock_query

            response = await async_client.post(
                "/api/v1/evaluation/comparisons",
                headers=auth_headers,
                json=request_data
            )

        assert response.status_code == 404
        response_data = response.json()
        assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_evaluation_comparison_authentication_contract(
        self,
        async_client: AsyncClient,
        evaluation_data_generator: EvaluationDataGenerator,
        contract_validator
    ):
        """Test comparison creation without authentication"""
        request_data = evaluation_data_generator.generate_comparison_request()

        response = await async_client.post(
            "/api/v1/evaluation/comparisons",
            json=request_data
        )

        assert response.status_code == 401
        response_data = response.json()
        assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_create_evaluation_comparison_special_characters_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_user,
        test_organization,
        job_data_generator: JobDataGenerator,
        evaluation_data_generator: EvaluationDataGenerator,
        contract_validator,
        mock_background_tasks
    ):
        """Test comparison with special characters in name"""
        baseline_job = job_data_generator.generate_job_record(
            organization_id=str(test_organization.id),
            user_id=str(test_user.id),
            status="completed"
        )

        comparison_job = job_data_generator.generate_job_record(
            organization_id=str(test_organization.id),
            user_id=str(test_user.id),
            status="completed"
        )

        request_data = {
            "name": "Comparison with émojis 🚀 & spëcial char$!",
            "baseline_job_id": str(baseline_job["id"]),
            "comparison_job_id": str(comparison_job["id"])
        }

        mock_baseline_job = Mock()
        mock_baseline_job.id = baseline_job["id"]
        mock_baseline_job.organization_id = str(test_organization.id)

        mock_comparison_job = Mock()
        mock_comparison_job.id = comparison_job["id"]
        mock_comparison_job.organization_id = str(test_organization.id)

        with patch('src.api.evaluation.db') as mock_db:
            mock_query = Mock()
            mock_query.filter.return_value.first.side_effect = [
                mock_baseline_job,
                mock_comparison_job
            ]
            mock_db.query.return_value = mock_query

            response = await async_client.post(
                "/api/v1/evaluation/comparisons",
                headers=auth_headers,
                json=request_data
            )

        if response.status_code in [200, 201]:
            response_data = response.json()
            required_fields = self.CREATE_COMPARISON_CONTRACT["response"]["success_schema"]["required_fields"]
            assert contract_validator.validate_response_structure(response_data, required_fields)

            # Verify special characters are preserved
            assert "émojis" in response_data["name"] or "spëcial" in response_data["name"]

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_list_evaluation_comparisons_success_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_user,
        test_organization,
        job_data_generator: JobDataGenerator,
        contract_validator,
        performance_tracker
    ):
        """Test successful evaluation comparisons listing"""
        performance_tracker.start_timer("list_evaluation_comparisons_success")

        # Generate mock comparison records
        comparison_records = []
        for i in range(5):
            record = {
                "id": uuid.uuid4(),
                "name": f"Comparison Test {i}",
                "description": f"Test comparison {i}",
                "baseline_job_id": str(uuid.uuid4()),
                "comparison_job_id": str(uuid.uuid4()),
                "baseline_score": random.uniform(0.6, 0.9),
                "comparison_score": random.uniform(0.6, 0.9),
                "improvement_percentage": random.uniform(-20, 30),
                "statistical_significance": random.uniform(0.01, 0.1),
                "created_at": datetime.utcnow() - timedelta(hours=i)
            }
            comparison_records.append(record)

        # Mock comparison query
        mock_comparisons = []
        for record in comparison_records:
            mock_comparison = Mock()
            mock_comparison.id = record["id"]
            mock_comparison.name = record["name"]
            mock_comparison.description = record["description"]
            mock_comparison.baseline_job_id = record["baseline_job_id"]
            mock_comparison.comparison_job_id = record["comparison_job_id"]
            mock_comparison.baseline_score = record["baseline_score"]
            mock_comparison.comparison_score = record["comparison_score"]
            mock_comparison.improvement_percentage = record["improvement_percentage"]
            mock_comparison.statistical_significance = record["statistical_significance"]
            mock_comparison.created_at = record["created_at"]
            mock_comparisons.append(mock_comparison)

        with patch('src.api.evaluation.db') as mock_db:
            mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = mock_comparisons

            response = await async_client.get(
                "/api/v1/evaluation/comparisons",
                headers=auth_headers
            )

        performance_tracker.end_timer("list_evaluation_comparisons_success")

        # Contract validation
        assert response.status_code == 200

        response_data = response.json()
        assert isinstance(response_data, list)
        assert len(response_data) == len(mock_comparisons)

        # Validate each comparison in the list
        for comparison_data in response_data:
            required_fields = self.LIST_COMPARISONS_CONTRACT["response"]["success_schema"]["item_schema"]["required_fields"]
            assert contract_validator.validate_response_structure(comparison_data, required_fields)

            # Validate data types
            field_types = self.LIST_COMPARISONS_CONTRACT["response"]["success_schema"]["item_schema"]["field_types"]
            type_errors = contract_validator.validate_data_types(comparison_data, field_types)
            assert not type_errors, f"Type validation errors: {type_errors}"

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_list_evaluation_comparisons_with_pagination_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_user,
        test_organization,
        job_data_generator: JobDataGenerator,
        contract_validator
    ):
        """Test evaluation comparisons listing with pagination"""
        # Generate many comparison records
        comparison_records = []
        for i in range(25):
            record = {
                "id": uuid.uuid4(),
                "name": f"Comparison {i}",
                "description": f"Description {i}",
                "baseline_job_id": str(uuid.uuid4()),
                "comparison_job_id": str(uuid.uuid4()),
                "created_at": datetime.utcnow() - timedelta(hours=i)
            }
            comparison_records.append(record)

        # Mock paginated results
        mock_comparisons_page = []
        for record in comparison_records[:10]:  # First page of 10
            mock_comparison = Mock()
            mock_comparison.id = record["id"]
            mock_comparison.name = record["name"]
            mock_comparison.description = record["description"]
            mock_comparison.baseline_job_id = record["baseline_job_id"]
            mock_comparison.comparison_job_id = record["comparison_job_id"]
            mock_comparison.created_at = record["created_at"]
            mock_comparisons_page.append(mock_comparison)

        with patch('src.api.evaluation.db') as mock_db:
            mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = mock_comparisons_page

            response = await async_client.get(
                "/api/v1/evaluation/comparisons?limit=10&offset=0",
                headers=auth_headers
            )

        assert response.status_code == 200

        response_data = response.json()
        assert isinstance(response_data, list)
        assert len(response_data) <= 10

        # Validate pagination parameters
        for comparison_data in response_data:
            required_fields = self.LIST_COMPARISONS_CONTRACT["response"]["success_schema"]["item_schema"]["required_fields"]
            assert contract_validator.validate_response_structure(comparison_data, required_fields)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_list_evaluation_comparisons_empty_result_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test evaluation comparisons listing with no results"""
        with patch('src.api.evaluation.db') as mock_db:
            mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

            response = await async_client.get(
                "/api/v1/evaluation/comparisons",
                headers=auth_headers
            )

        assert response.status_code == 200

        response_data = response.json()
        assert isinstance(response_data, list)
        assert len(response_data) == 0

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_list_evaluation_comparisons_unauthorized_contract(
        self,
        async_client: AsyncClient,
        contract_validator
    ):
        """Test evaluation comparisons listing without authentication"""
        response = await async_client.get("/api/v1/evaluation/comparisons")

        assert response.status_code == 401
        response_data = response.json()
        assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_list_evaluation_comparisons_invalid_pagination_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test evaluation comparisons listing with invalid pagination parameters"""
        invalid_params = [
            "limit=0",  # Limit too small
            "limit=101",  # Limit too large
            "limit=abc",  # Invalid limit format
            "offset=-1",  # Negative offset
            "offset=abc",  # Invalid offset format
        ]

        for params in invalid_params:
            response = await async_client.get(
                f"/api/v1/evaluation/comparisons?{params}",
                headers=auth_headers
            )

            # Should handle invalid pagination gracefully
            assert response.status_code in [400, 422]

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_evaluation_comparison_response_time_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_user,
        test_organization,
        job_data_generator: JobDataGenerator,
        evaluation_data_generator: EvaluationDataGenerator,
        performance_tracker,
        mock_background_tasks
    ):
        """Test response time for comparison creation"""
        performance_tracker.start_timer("comparison_creation_response_time")

        baseline_job = job_data_generator.generate_job_record(
            organization_id=str(test_organization.id),
            user_id=str(test_user.id),
            status="completed"
        )

        comparison_job = job_data_generator.generate_job_record(
            organization_id=str(test_organization.id),
            user_id=str(test_user.id),
            status="completed"
        )

        request_data = evaluation_data_generator.generate_comparison_request(
            baseline_job_id=str(baseline_job["id"]),
            comparison_job_id=str(comparison_job["id"])
        )

        mock_baseline_job = Mock()
        mock_baseline_job.id = baseline_job["id"]
        mock_baseline_job.organization_id = str(test_organization.id)

        mock_comparison_job = Mock()
        mock_comparison_job.id = comparison_job["id"]
        mock_comparison_job.organization_id = str(test_organization.id)

        with patch('src.api.evaluation.db') as mock_db:
            mock_query = Mock()
            mock_query.filter.return_value.first.side_effect = [
                mock_baseline_job,
                mock_comparison_job
            ]
            mock_db.query.return_value = mock_query

            response = await async_client.post(
                "/api/v1/evaluation/comparisons",
                headers=auth_headers,
                json=request_data
            )

        response_time = performance_tracker.end_timer("comparison_creation_response_time")

        # Response time should be reasonable (less than 1 second)
        assert response_time < 1.0, f"Response time {response_time}s exceeds 1 second"

        assert response.status_code in [200, 201]

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_evaluation_comparison_concurrent_requests_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_user,
        test_organization,
        job_data_generator: JobDataGenerator,
        evaluation_data_generator: EvaluationDataGenerator,
        performance_tracker
    ):
        """Test concurrent comparison requests"""
        # Generate multiple jobs for concurrent comparisons
        jobs = [
            job_data_generator.generate_job_record(
                organization_id=str(test_organization.id),
                user_id=str(test_user.id),
                status="completed"
            )
            for _ in range(6)  # Need 6 jobs for 3 comparisons
        ]

        # Generate comparison requests
        requests = []
        for i in range(3):
            request_data = evaluation_data_generator.generate_comparison_request(
                baseline_job_id=str(jobs[i*2]["id"]),
                comparison_job_id=str(jobs[i*2+1]["id"])
            )
            requests.append(request_data)

        performance_tracker.start_timer("concurrent_comparisons")

        # Mock all job queries
        mock_jobs = []
        for job in jobs:
            mock_job = Mock()
            mock_job.id = job["id"]
            mock_job.organization_id = str(test_organization.id)
            mock_jobs.append(mock_job)

        with patch('src.api.evaluation.db') as mock_db:
            # Set up mock to return appropriate jobs for each query
            mock_query = Mock()
            mock_query.filter.return_value.first.side_effect = mock_jobs
            mock_db.query.return_value = mock_query

            tasks = [
                async_client.post("/api/v1/evaluation/comparisons", headers=auth_headers, json=request)
                for request in requests
            ]

            responses = await asyncio.gather(*tasks, return_exceptions=True)

        performance_tracker.end_timer("concurrent_comparisons")

        # Validate responses
        successful_count = 0
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                pytest.fail(f"Concurrent comparison request {i} failed: {response}")

            if response.status_code in [200, 201]:
                response_data = response.json()
                assert "name" in response_data
                assert "baseline_job" in response_data
                assert "comparison_job" in response_data
                successful_count += 1
            elif response.status_code == 429:
                # Rate limiting is acceptable
                pass
            else:
                pytest.fail(f"Unexpected status code {response.status_code} for concurrent comparison request {i}")

        # At least some requests should succeed
        assert successful_count > 0, "No concurrent comparison requests succeeded"