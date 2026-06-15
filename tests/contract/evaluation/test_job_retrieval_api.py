"""
Contract tests for Evaluation Job Retrieval API endpoints
GET /api/v1/evaluation/jobs/{id}
GET /api/v1/evaluation/jobs
"""

import pytest
import uuid
import random
from httpx import AsyncClient
from unittest.mock import patch, Mock
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

from tests.contract.evaluation.fixtures.data_generators import JobDataGenerator, MetricDataGenerator


class TestJobRetrievalContract:
    """Contract tests for evaluation job retrieval endpoints"""

    # Contract definitions
    SINGLE_JOB_CONTRACT = {
        "endpoint": "GET /api/v1/evaluation/jobs/{id}",
        "method": "GET",
        "headers": {
            "required": ["Authorization"]
        },
        "authentication": "required",
        "path_parameters": {
            "required": ["id"],
            "constraints": {
                "id": {"type": str, "format": "uuid"}
            }
        },
        "response": {
            "status_codes": [200, 401, 403, 404, 500],
            "success_schema": {
                "required_fields": [
                    "job_id", "name", "description", "status", "evaluation_type",
                    "created_at", "started_at", "completed_at", "duration_seconds",
                    "dataset_size", "processed_count", "parameters"
                ],
                "field_types": {
                    "job_id": str,
                    "name": str,
                    "description": str,
                    "status": str,
                    "evaluation_type": str,
                    "created_at": str,
                    "started_at": type(None),
                    "completed_at": type(None),
                    "duration_seconds": type(None),
                    "dataset_size": int,
                    "processed_count": int,
                    "parameters": dict
                },
                "optional_fields": [
                    "overall_score", "success_rate", "error_message",
                    "metrics_summary", "threshold_violations"
                ]
            }
        }
    }

    JOB_LIST_CONTRACT = {
        "endpoint": "GET /api/v1/evaluation/jobs",
        "method": "GET",
        "headers": {
            "required": ["Authorization"]
        },
        "authentication": "required",
        "query_parameters": {
            "optional": ["limit", "offset", "status", "evaluation_type"],
            "constraints": {
                "limit": {"type": int, "min": 1, "max": 100, "default": 20},
                "offset": {"type": int, "min": 0, "default": 0},
                "status": {"type": str, "enum": ["pending", "running", "completed", "failed", "cancelled"]},
                "evaluation_type": {"type": str}
            }
        },
        "response": {
            "status_codes": [200, 401, 403, 422, 500],
            "success_schema": {
                "type": "array",
                "item_schema": {
                    "required_fields": [
                        "id", "name", "description", "status", "evaluation_type",
                        "created_at", "started_at", "completed_at", "duration_seconds",
                        "dataset_size", "processed_count"
                    ],
                    "field_types": {
                        "id": str,
                        "name": str,
                        "status": str,
                        "evaluation_type": str,
                        "created_at": str,
                        "dataset_size": int,
                        "processed_count": int
                    },
                    "optional_fields": [
                        "overall_score", "success_rate", "error_message"
                    ]
                }
            }
        }
    }

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_get_evaluation_job_success_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_user,
        test_organization,
        job_data_generator: JobDataGenerator,
        contract_validator,
        performance_tracker,
        mock_rag_evaluation_service
    ):
        """Test successful evaluation job retrieval"""
        performance_tracker.start_timer("get_evaluation_job_success")

        # Generate test job data
        job_record = job_data_generator.generate_job_record(
            organization_id=str(test_organization.id),
            user_id=str(test_user.id),
            status="completed"
        )

        # Mock database query
        mock_job = Mock()
        mock_job.id = job_record["id"]
        mock_job.name = job_record["name"]
        mock_job.description = job_record["description"]
        mock_job.status = job_record["status"]
        mock_job.evaluation_type = job_record["evaluation_type"]
        mock_job.created_at = job_record["created_at"]
        mock_job.started_at = job_record["started_at"]
        mock_job.completed_at = job_record["completed_at"]
        mock_job.duration_seconds = job_record["duration_seconds"]
        mock_job.dataset_size = job_record["dataset_size"]
        mock_job.processed_count = job_record["processed_count"]
        mock_job.parameters = job_record["parameters"]
        mock_job.overall_score = job_record["overall_score"]
        mock_job.success_rate = job_record["success_rate"]
        mock_job.error_message = job_record["error_message"]

        # Mock the evaluation summary
        mock_rag_evaluation_service.get_evaluation_summary.return_value = (
            job_data_generator.generate_job_summary_response(job_record)
        )

        # Mock database session
        with patch('src.api.evaluation.db') as mock_db:
            mock_db.query.return_value.filter.return_value.first.return_value = mock_job

            response = await async_client.get(
                f"/api/v1/evaluation/jobs/{job_record['id']}",
                headers=auth_headers
            )

        performance_tracker.end_timer("get_evaluation_job_success")

        # Contract validation
        assert response.status_code == 200

        response_data = response.json()

        # Validate response structure
        required_fields = self.SINGLE_JOB_CONTRACT["response"]["success_schema"]["required_fields"]
        assert contract_validator.validate_response_structure(response_data, required_fields)

        # Validate data types
        field_types = self.SINGLE_JOB_CONTRACT["response"]["success_schema"]["field_types"]
        type_errors = contract_validator.validate_data_types(response_data, field_types)
        assert not type_errors, f"Type validation errors: {type_errors}"

        # Validate business rules
        assert response_data["job_id"] == str(job_record["id"])
        assert response_data["name"] == job_record["name"]
        assert response_data["status"] == job_record["status"]
        assert response_data["dataset_size"] == job_record["dataset_size"]

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_get_evaluation_job_not_found_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test evaluation job not found"""
        non_existent_id = str(uuid.uuid4())

        # Mock database query returning None
        with patch('src.api.evaluation.db') as mock_db:
            mock_db.query.return_value.filter.return_value.first.return_value = None

            response = await async_client.get(
                f"/api/v1/evaluation/jobs/{non_existent_id}",
                headers=auth_headers
            )

        assert response.status_code == 404
        response_data = response.json()
        assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_get_evaluation_job_invalid_id_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test evaluation job with invalid ID"""
        invalid_ids = [
            "invalid-uuid",
            "12345",
            "not-a-uuid-at-all",
            "",
            "00000000-0000-0000-0000-000000000000"  # Valid format but non-existent
        ]

        for invalid_id in invalid_ids:
            response = await async_client.get(
                f"/api/v1/evaluation/jobs/{invalid_id}",
                headers=auth_headers
            )

            # Should return 404 for invalid IDs
            assert response.status_code == 404
            response_data = response.json()
            assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_get_evaluation_job_unauthorized_contract(
        self,
        async_client: AsyncClient,
        contract_validator
    ):
        """Test evaluation job retrieval without authentication"""
        job_id = str(uuid.uuid4())

        response = await async_client.get(
            f"/api/v1/evaluation/jobs/{job_id}"
        )

        assert response.status_code == 401
        response_data = response.json()
        assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_get_evaluation_job_cross_organization_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_organization,
        job_data_generator: JobDataGenerator,
        contract_validator
    ):
        """Test accessing job from different organization (should be blocked)"""
        # Generate job for different organization
        other_org_id = str(uuid.uuid4())
        job_record = job_data_generator.generate_job_record(
            organization_id=other_org_id,
            user_id=str(uuid.uuid4())
        )

        # Mock database query returning job from different organization
        mock_job = Mock()
        mock_job.id = job_record["id"]
        mock_job.organization_id = other_org_id

        with patch('src.api.evaluation.db') as mock_db:
            mock_db.query.return_value.filter.return_value.first.return_value = None  # No access

            response = await async_client.get(
                f"/api/v1/evaluation/jobs/{job_record['id']}",
                headers=auth_headers
            )

        assert response.status_code == 404
        response_data = response.json()
        assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_list_evaluation_jobs_success_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_user,
        test_organization,
        job_data_generator: JobDataGenerator,
        contract_validator,
        performance_tracker
    ):
        """Test successful evaluation jobs listing"""
        performance_tracker.start_timer("list_evaluation_jobs_success")

        # Generate multiple job records
        job_records = [
            job_data_generator.generate_job_record(
                organization_id=str(test_organization.id),
                user_id=str(test_user.id),
                status=random.choice(["completed", "running", "pending", "failed"])
            )
            for _ in range(5)
        ]

        # Mock database query
        mock_jobs = []
        for job_record in job_records:
            mock_job = Mock()
            mock_job.id = job_record["id"]
            mock_job.name = job_record["name"]
            mock_job.description = job_record["description"]
            mock_job.status = job_record["status"]
            mock_job.evaluation_type = job_record["evaluation_type"]
            mock_job.created_at = job_record["created_at"]
            mock_job.started_at = job_record["started_at"]
            mock_job.completed_at = job_record["completed_at"]
            mock_job.duration_seconds = job_record["duration_seconds"]
            mock_job.dataset_size = job_record["dataset_size"]
            mock_job.processed_count = job_record["processed_count"]
            mock_job.overall_score = job_record["overall_score"]
            mock_job.success_rate = job_record["success_rate"]
            mock_job.error_message = job_record["error_message"]
            mock_jobs.append(mock_job)

        with patch('src.api.evaluation.db') as mock_db:
            mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = mock_jobs

            response = await async_client.get(
                "/api/v1/evaluation/jobs",
                headers=auth_headers
            )

        performance_tracker.end_timer("list_evaluation_jobs_success")

        # Contract validation
        assert response.status_code == 200

        response_data = response.json()
        assert isinstance(response_data, list)
        assert len(response_data) == len(mock_jobs)

        # Validate each job in the list
        for job_data in response_data:
            required_fields = self.JOB_LIST_CONTRACT["response"]["success_schema"]["item_schema"]["required_fields"]
            assert contract_validator.validate_response_structure(job_data, required_fields)

            # Validate data types
            field_types = self.JOB_LIST_CONTRACT["response"]["success_schema"]["item_schema"]["field_types"]
            type_errors = contract_validator.validate_data_types(job_data, field_types)
            assert not type_errors, f"Type validation errors: {type_errors}"

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_list_evaluation_jobs_with_pagination_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_user,
        test_organization,
        job_data_generator: JobDataGenerator,
        contract_validator
    ):
        """Test evaluation jobs listing with pagination"""
        # Generate many job records
        job_records = [
            job_data_generator.generate_job_record(
                organization_id=str(test_organization.id),
                user_id=str(test_user.id)
            )
            for _ in range(25)
        ]

        # Mock database query for paginated results
        mock_jobs_page = []
        for job_record in job_records[:10]:  # First page of 10
            mock_job = Mock()
            mock_job.id = job_record["id"]
            mock_job.name = job_record["name"]
            mock_job.status = job_record["status"]
            mock_job.evaluation_type = job_record["evaluation_type"]
            mock_job.created_at = job_record["created_at"]
            mock_job.dataset_size = job_record["dataset_size"]
            mock_job.processed_count = job_record["processed_count"]
            mock_job.overall_score = job_record["overall_score"]
            mock_job.success_rate = job_record["success_rate"]
            mock_job.error_message = job_record["error_message"]
            mock_jobs_page.append(mock_job)

        with patch('src.api.evaluation.db') as mock_db:
            mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = mock_jobs_page

            response = await async_client.get(
                "/api/v1/evaluation/jobs?limit=10&offset=0",
                headers=auth_headers
            )

        assert response.status_code == 200

        response_data = response.json()
        assert isinstance(response_data, list)
        assert len(response_data) <= 10

        # Validate pagination parameters
        for job_data in response_data:
            required_fields = self.JOB_LIST_CONTRACT["response"]["success_schema"]["item_schema"]["required_fields"]
            assert contract_validator.validate_response_structure(job_data, required_fields)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_list_evaluation_jobs_with_filters_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_user,
        test_organization,
        job_data_generator: JobDataGenerator,
        contract_validator
    ):
        """Test evaluation jobs listing with filters"""
        # Test status filter
        completed_job = job_data_generator.generate_job_record(
            organization_id=str(test_organization.id),
            user_id=str(test_user.id),
            status="completed"
        )

        mock_completed_job = Mock()
        mock_completed_job.id = completed_job["id"]
        mock_completed_job.name = completed_job["name"]
        mock_completed_job.status = completed_job["status"]
        mock_completed_job.evaluation_type = completed_job["evaluation_type"]
        mock_completed_job.created_at = completed_job["created_at"]
        mock_completed_job.dataset_size = completed_job["dataset_size"]
        mock_completed_job.processed_count = completed_job["processed_count"]
        mock_completed_job.overall_score = completed_job["overall_score"]
        mock_completed_job.success_rate = completed_job["success_rate"]

        with patch('src.api.evaluation.db') as mock_db:
            mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_completed_job]

            response = await async_client.get(
                "/api/v1/evaluation/jobs?status=completed",
                headers=auth_headers
            )

        assert response.status_code == 200

        response_data = response.json()
        assert isinstance(response_data, list)
        assert all(job["status"] == "completed" for job in response_data)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_list_evaluation_jobs_invalid_pagination_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test evaluation jobs listing with invalid pagination parameters"""
        invalid_params = [
            "limit=0",  # Limit too small
            "limit=101",  # Limit too large
            "limit=abc",  # Invalid limit format
            "offset=-1",  # Negative offset
            "offset=abc",  # Invalid offset format
        ]

        for params in invalid_params:
            response = await async_client.get(
                f"/api/v1/evaluation/jobs?{params}",
                headers=auth_headers
            )

            # Should handle invalid pagination gracefully
            assert response.status_code in [400, 422]

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_list_evaluation_jobs_unauthorized_contract(
        self,
        async_client: AsyncClient,
        contract_validator
    ):
        """Test evaluation jobs listing without authentication"""
        response = await async_client.get("/api/v1/evaluation/jobs")

        assert response.status_code == 401
        response_data = response.json()
        assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_list_evaluation_jobs_empty_result_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test evaluation jobs listing with no results"""
        # Mock empty database query
        with patch('src.api.evaluation.db') as mock_db:
            mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

            response = await async_client.get(
                "/api/v1/evaluation/jobs",
                headers=auth_headers
            )

        assert response.status_code == 200

        response_data = response.json()
        assert isinstance(response_data, list)
        assert len(response_data) == 0

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_job_retrieval_response_time_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_user,
        test_organization,
        job_data_generator: JobDataGenerator,
        performance_tracker
    ):
        """Test response time for job retrieval"""
        performance_tracker.start_timer("job_retrieval_response_time")

        # Generate test job
        job_record = job_data_generator.generate_job_record(
            organization_id=str(test_organization.id),
            user_id=str(test_user.id)
        )

        # Mock database query
        mock_job = Mock()
        mock_job.id = job_record["id"]
        mock_job.name = job_record["name"]
        mock_job.status = job_record["status"]
        mock_job.evaluation_type = job_record["evaluation_type"]
        mock_job.created_at = job_record["created_at"]
        mock_job.dataset_size = job_record["dataset_size"]
        mock_job.processed_count = job_record["processed_count"]

        with patch('src.api.evaluation.db') as mock_db:
            mock_db.query.return_value.filter.return_value.first.return_value = mock_job
            mock_rag_evaluation_service = Mock()
            mock_rag_evaluation_service.get_evaluation_summary.return_value = job_data_generator.generate_job_summary_response(job_record)

            with patch('src.api.evaluation.rag_evaluation_service', mock_rag_evaluation_service):
                response = await async_client.get(
                    f"/api/v1/evaluation/jobs/{job_record['id']}",
                    headers=auth_headers
                )

        response_time = performance_tracker.end_timer("job_retrieval_response_time")

        # Response time should be reasonable (less than 1 second)
        assert response_time < 1.0, f"Response time {response_time}s exceeds 1 second"

        assert response.status_code == 200

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_job_retrieval_different_status_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_user,
        test_organization,
        job_data_generator: JobDataGenerator,
        contract_validator
    ):
        """Test retrieving jobs with different statuses"""
        statuses = ["pending", "running", "completed", "failed", "cancelled"]

        for status in statuses:
            job_record = job_data_generator.generate_job_record(
                organization_id=str(test_organization.id),
                user_id=str(test_user.id),
                status=status
            )

            # Mock database query
            mock_job = Mock()
            mock_job.id = job_record["id"]
            mock_job.name = job_record["name"]
            mock_job.status = job_record["status"]
            mock_job.evaluation_type = job_record["evaluation_type"]
            mock_job.created_at = job_record["created_at"]
            mock_job.started_at = job_record["started_at"]
            mock_job.completed_at = job_record["completed_at"]
            mock_job.dataset_size = job_record["dataset_size"]
            mock_job.processed_count = job_record["processed_count"]
            mock_job.error_message = job_record["error_message"]

            with patch('src.api.evaluation.db') as mock_db:
                mock_db.query.return_value.filter.return_value.first.return_value = mock_job
                mock_rag_evaluation_service = Mock()
                mock_rag_evaluation_service.get_evaluation_summary.return_value = job_data_generator.generate_job_summary_response(job_record)

                with patch('src.api.evaluation.rag_evaluation_service', mock_rag_evaluation_service):
                    response = await async_client.get(
                        f"/api/v1/evaluation/jobs/{job_record['id']}",
                        headers=auth_headers
                    )

            assert response.status_code == 200

            response_data = response.json()
            assert response_data["status"] == status

            # Validate required fields are present for all statuses
            required_fields = self.SINGLE_JOB_CONTRACT["response"]["success_schema"]["required_fields"]
            assert contract_validator.validate_response_structure(response_data, required_fields)