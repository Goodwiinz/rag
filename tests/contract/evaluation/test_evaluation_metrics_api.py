"""
Contract tests for Evaluation Metrics API endpoints
GET /api/v1/evaluation/jobs/{id}/metrics
GET /api/v1/evaluation/metrics/summary
"""

import pytest
import uuid
import random
from httpx import AsyncClient
from unittest.mock import patch, Mock
from datetime import datetime
from typing import Dict, Any

from tests.contract.evaluation.fixtures.data_generators import JobDataGenerator, MetricDataGenerator


class TestEvaluationMetricsContract:
    """Contract tests for evaluation metrics endpoints"""

    # Contract definitions
    JOB_METRICS_CONTRACT = {
        "endpoint": "GET /api/v1/evaluation/jobs/{id}/metrics",
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
        "query_parameters": {
            "optional": ["metric_types", "limit"],
            "constraints": {
                "metric_types": {"type": list, "max_items": 10},
                "limit": {"type": int, "min": 1, "max": 1000, "default": 100}
            }
        },
        "response": {
            "status_codes": [200, 401, 403, 404, 422, 500],
            "success_schema": {
                "type": "array",
                "item_schema": {
                    "required_fields": [
                        "id", "metric_type", "metric_name", "value", "created_at"
                    ],
                    "field_types": {
                        "id": str,
                        "metric_type": str,
                        "metric_name": str,
                        "value": (int, float),
                        "created_at": str
                    },
                    "optional_fields": [
                        "min_value", "max_value", "mean_value", "threshold_min",
                        "threshold_max", "is_threshold_violation", "query",
                        "calculation_method", "model_used"
                    ]
                }
            }
        }
    }

    METRICS_SUMMARY_CONTRACT = {
        "endpoint": "GET /api/v1/evaluation/metrics/summary",
        "method": "GET",
        "headers": {
            "required": ["Authorization"]
        },
        "authentication": "required",
        "query_parameters": {
            "optional": ["days"],
            "constraints": {
                "days": {"type": int, "min": 1, "max": 365, "default": 30}
            }
        },
        "response": {
            "status_codes": [200, 401, 403, 422, 500],
            "success_schema": {
                "required_fields": [
                    "period_days", "total_metrics", "metric_summary",
                    "threshold_violations", "average_scores", "violation_rate"
                ],
                "field_types": {
                    "period_days": int,
                    "total_metrics": int,
                    "metric_summary": dict,
                    "threshold_violations": int,
                    "average_scores": dict,
                    "violation_rate": (int, float)
                }
            }
        }
    }

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_get_evaluation_metrics_success_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_user,
        test_organization,
        job_data_generator: JobDataGenerator,
        metric_data_generator: MetricDataGenerator,
        contract_validator,
        performance_tracker,
        mock_rag_evaluation_service
    ):
        """Test successful evaluation metrics retrieval"""
        performance_tracker.start_timer("get_evaluation_metrics_success")

        # Generate test job and metrics
        job_record = job_data_generator.generate_job_record(
            organization_id=str(test_organization.id),
            user_id=str(test_user.id)
        )

        metrics_data = metric_data_generator.generate_metrics_response(
            job_id=str(job_record["id"]),
            metric_count=10
        )

        # Mock job and metrics retrieval
        mock_job = Mock()
        mock_job.id = job_record["id"]
        mock_job.organization_id = str(test_organization.id)

        mock_rag_evaluation_service.get_evaluation_metrics.return_value = metrics_data

        with patch('src.api.evaluation.db') as mock_db:
            mock_db.query.return_value.filter.return_value.first.return_value = mock_job

            response = await async_client.get(
                f"/api/v1/evaluation/jobs/{job_record['id']}/metrics",
                headers=auth_headers
            )

        performance_tracker.end_timer("get_evaluation_metrics_success")

        # Contract validation
        assert response.status_code == 200

        response_data = response.json()
        assert isinstance(response_data, list)
        assert len(response_data) == len(metrics_data)

        # Validate each metric in the list
        for metric_data in response_data:
            required_fields = self.JOB_METRICS_CONTRACT["response"]["success_schema"]["item_schema"]["required_fields"]
            assert contract_validator.validate_response_structure(metric_data, required_fields)

            # Validate data types
            field_types = self.JOB_METRICS_CONTRACT["response"]["success_schema"]["item_schema"]["field_types"]
            type_errors = contract_validator.validate_data_types(metric_data, field_types)
            assert not type_errors, f"Type validation errors: {type_errors}"

            # Validate business rules
            assert isinstance(metric_data["value"], (int, float))
            assert 0 <= metric_data["value"] <= 1  # Metrics should be normalized
            assert len(metric_data["id"]) > 0

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_get_evaluation_metrics_with_filters_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_user,
        test_organization,
        job_data_generator: JobDataGenerator,
        metric_data_generator: MetricDataGenerator,
        contract_validator,
        mock_rag_evaluation_service
    ):
        """Test evaluation metrics retrieval with filters"""
        job_record = job_data_generator.generate_job_record(
            organization_id=str(test_organization.id),
            user_id=str(test_user.id)
        )

        # Generate filtered metrics (only specific types)
        filtered_metrics = []
        for metric_type in ["rag_triad_answer_relevancy", "rag_triad_faithfulness"]:
            metric_record = metric_data_generator.generate_metric_record(
                job_id=str(job_record["id"]),
                metric_type=metric_type
            )
            metric_response = {
                "id": str(metric_record["id"]),
                "metric_type": metric_record["metric_type"],
                "metric_name": metric_record["metric_name"],
                "value": metric_record["value"],
                "created_at": metric_record["created_at"].isoformat()
            }
            filtered_metrics.append(metric_response)

        mock_job = Mock()
        mock_job.id = job_record["id"]
        mock_job.organization_id = str(test_organization.id)

        mock_rag_evaluation_service.get_evaluation_metrics.return_value = filtered_metrics

        with patch('src.api.evaluation.db') as mock_db:
            mock_db.query.return_value.filter.return_value.first.return_value = mock_job

            response = await async_client.get(
                f"/api/v1/evaluation/jobs/{job_record['id']}/metrics"
                f"?metric_types=rag_triad_answer_relevancy&metric_types=rag_triad_faithfulness&limit=10",
                headers=auth_headers
            )

        assert response.status_code == 200

        response_data = response.json()
        assert isinstance(response_data, list)
        assert len(response_data) <= 10  # Should respect limit

        # Verify returned metrics match requested types
        returned_types = {metric["metric_type"] for metric in response_data}
        expected_types = {"rag_triad_answer_relevancy", "rag_triad_faithfulness"}
        assert returned_types.issubset(expected_types)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_get_evaluation_metrics_job_not_found_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test evaluation metrics for non-existent job"""
        non_existent_id = str(uuid.uuid4())

        with patch('src.api.evaluation.db') as mock_db:
            mock_db.query.return_value.filter.return_value.first.return_value = None

            response = await async_client.get(
                f"/api/v1/evaluation/jobs/{non_existent_id}/metrics",
                headers=auth_headers
            )

        assert response.status_code == 404
        response_data = response.json()
        assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_get_evaluation_metrics_invalid_job_id_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test evaluation metrics with invalid job ID"""
        invalid_ids = [
            "invalid-uuid",
            "12345",
            "not-a-uuid",
            ""
        ]

        for invalid_id in invalid_ids:
            response = await async_client.get(
                f"/api/v1/evaluation/jobs/{invalid_id}/metrics",
                headers=auth_headers
            )

            assert response.status_code == 404
            response_data = response.json()
            assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_get_evaluation_metrics_unauthorized_contract(
        self,
        async_client: AsyncClient,
        contract_validator
    ):
        """Test evaluation metrics retrieval without authentication"""
        job_id = str(uuid.uuid4())

        response = await async_client.get(
            f"/api/v1/evaluation/jobs/{job_id}/metrics"
        )

        assert response.status_code == 401
        response_data = response.json()
        assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_get_evaluation_metrics_cross_organization_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_organization,
        job_data_generator: JobDataGenerator,
        contract_validator,
        mock_rag_evaluation_service
    ):
        """Test accessing metrics from different organization (should be blocked)"""
        # Generate job for different organization
        other_org_id = str(uuid.uuid4())
        job_record = job_data_generator.generate_job_record(
            organization_id=other_org_id,
            user_id=str(uuid.uuid4())
        )

        mock_job = Mock()
        mock_job.id = job_record["id"]
        mock_job.organization_id = other_org_id

        # Mock empty metrics (no access)
        mock_rag_evaluation_service.get_evaluation_metrics.return_value = []

        with patch('src.api.evaluation.db') as mock_db:
            mock_db.query.return_value.filter.return_value.first.return_value = None  # No access

            response = await async_client.get(
                f"/api/v1/evaluation/jobs/{job_record['id']}/metrics",
                headers=auth_headers
            )

        assert response.status_code == 404
        response_data = response.json()
        assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_get_evaluation_metrics_empty_result_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_user,
        test_organization,
        job_data_generator: JobDataGenerator,
        contract_validator,
        mock_rag_evaluation_service
    ):
        """Test evaluation metrics retrieval with no metrics"""
        job_record = job_data_generator.generate_job_record(
            organization_id=str(test_organization.id),
            user_id=str(test_user.id)
        )

        mock_job = Mock()
        mock_job.id = job_record["id"]
        mock_job.organization_id = str(test_organization.id)

        mock_rag_evaluation_service.get_evaluation_metrics.return_value = []

        with patch('src.api.evaluation.db') as mock_db:
            mock_db.query.return_value.filter.return_value.first.return_value = mock_job

            response = await async_client.get(
                f"/api/v1/evaluation/jobs/{job_record['id']}/metrics",
                headers=auth_headers
            )

        assert response.status_code == 200

        response_data = response.json()
        assert isinstance(response_data, list)
        assert len(response_data) == 0

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_get_evaluation_metrics_invalid_limit_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test evaluation metrics with invalid limit parameters"""
        job_id = str(uuid.uuid4())
        invalid_limits = ["0", "1001", "-1", "abc", ""]

        for limit in invalid_limits:
            response = await async_client.get(
                f"/api/v1/evaluation/jobs/{job_id}/metrics?limit={limit}",
                headers=auth_headers
            )

            # Should handle invalid limits gracefully
            assert response.status_code in [400, 422, 404]

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_get_metrics_summary_success_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        metric_data_generator: MetricDataGenerator,
        contract_validator,
        performance_tracker,
        mock_rag_evaluation_service
    ):
        """Test successful metrics summary retrieval"""
        performance_tracker.start_timer("get_metrics_summary_success")

        # Generate test summary data
        summary_data = metric_data_generator.generate_metrics_summary(days=30)

        mock_rag_evaluation_service.get_metrics_summary.return_value = summary_data

        response = await async_client.get(
            "/api/v1/evaluation/metrics/summary?days=30",
            headers=auth_headers
        )

        performance_tracker.end_timer("get_metrics_summary_success")

        # Contract validation
        assert response.status_code == 200

        response_data = response.json()

        # Validate response structure
        required_fields = self.METRICS_SUMMARY_CONTRACT["response"]["success_schema"]["required_fields"]
        assert contract_validator.validate_response_structure(response_data, required_fields)

        # Validate data types
        field_types = self.METRICS_SUMMARY_CONTRACT["response"]["success_schema"]["field_types"]
        type_errors = contract_validator.validate_data_types(response_data, field_types)
        assert not type_errors, f"Type validation errors: {type_errors}"

        # Validate business rules
        assert response_data["period_days"] == 30
        assert response_data["total_metrics"] >= 0
        assert isinstance(response_data["metric_summary"], dict)
        assert isinstance(response_data["average_scores"], dict)
        assert 0 <= response_data["violation_rate"] <= 100

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_get_metrics_summary_different_periods_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        metric_data_generator: MetricDataGenerator,
        contract_validator,
        mock_rag_evaluation_service
    ):
        """Test metrics summary for different time periods"""
        periods = [7, 30, 90, 365]

        for days in periods:
            summary_data = metric_data_generator.generate_metrics_summary(days=days)
            mock_rag_evaluation_service.get_metrics_summary.return_value = summary_data

            response = await async_client.get(
                f"/api/v1/evaluation/metrics/summary?days={days}",
                headers=auth_headers
            )

            assert response.status_code == 200

            response_data = response.json()
            assert response_data["period_days"] == days

            required_fields = self.METRICS_SUMMARY_CONTRACT["response"]["success_schema"]["required_fields"]
            assert contract_validator.validate_response_structure(response_data, required_fields)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_get_metrics_summary_invalid_days_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator
    ):
        """Test metrics summary with invalid days parameter"""
        invalid_days = ["0", "366", "-1", "abc", ""]

        for days in invalid_days:
            response = await async_client.get(
                f"/api/v1/evaluation/metrics/summary?days={days}",
                headers=auth_headers
            )

            # Should handle invalid days gracefully
            assert response.status_code in [400, 422]

            response_data = response.json()
            assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_get_metrics_summary_unauthorized_contract(
        self,
        async_client: AsyncClient,
        contract_validator
    ):
        """Test metrics summary without authentication"""
        response = await async_client.get("/api/v1/evaluation/metrics/summary")

        assert response.status_code == 401
        response_data = response.json()
        assert contract_validator.validate_error_response(response_data)

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_get_metrics_summary_empty_data_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        contract_validator,
        mock_rag_evaluation_service
    ):
        """Test metrics summary with no data"""
        empty_summary = {
            "period_days": 30,
            "total_metrics": 0,
            "metric_summary": {},
            "threshold_violations": 0,
            "average_scores": {},
            "violation_rate": 0
        }

        mock_rag_evaluation_service.get_metrics_summary.return_value = empty_summary

        response = await async_client.get(
            "/api/v1/evaluation/metrics/summary",
            headers=auth_headers
        )

        assert response.status_code == 200

        response_data = response.json()
        required_fields = self.METRICS_SUMMARY_CONTRACT["response"]["success_schema"]["required_fields"]
        assert contract_validator.validate_response_structure(response_data, required_fields)

        assert response_data["total_metrics"] == 0
        assert response_data["violation_rate"] == 0
        assert len(response_data["metric_summary"]) == 0

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_evaluation_metrics_response_time_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_user,
        test_organization,
        job_data_generator: JobDataGenerator,
        metric_data_generator: MetricDataGenerator,
        performance_tracker,
        mock_rag_evaluation_service
    ):
        """Test response time for metrics retrieval"""
        performance_tracker.start_timer("metrics_response_time")

        job_record = job_data_generator.generate_job_record(
            organization_id=str(test_organization.id),
            user_id=str(test_user.id)
        )

        # Generate many metrics to test performance
        metrics_data = metric_data_generator.generate_metrics_response(
            job_id=str(job_record["id"]),
            metric_count=500
        )

        mock_job = Mock()
        mock_job.id = job_record["id"]
        mock_job.organization_id = str(test_organization.id)

        mock_rag_evaluation_service.get_evaluation_metrics.return_value = metrics_data

        with patch('src.api.evaluation.db') as mock_db:
            mock_db.query.return_value.filter.return_value.first.return_value = mock_job

            response = await async_client.get(
                f"/api/v1/evaluation/jobs/{job_record['id']}/metrics?limit=500",
                headers=auth_headers
            )

        response_time = performance_tracker.end_timer("metrics_response_time")

        # Response time should be reasonable even with many metrics (less than 2 seconds)
        assert response_time < 2.0, f"Response time {response_time}s exceeds 2 seconds"

        assert response.status_code == 200

    @pytest.mark.contract
    @pytest.mark.evaluation_contract
    async def test_evaluation_metrics_all_types_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_user,
        test_organization,
        job_data_generator: JobDataGenerator,
        metric_data_generator: MetricDataGenerator,
        contract_validator,
        mock_rag_evaluation_service
    ):
        """Test retrieval of all metric types"""
        job_record = job_data_generator.generate_job_record(
            organization_id=str(test_organization.id),
            user_id=str(test_user.id)
        )

        # Generate metrics for all types
        all_metrics = []
        metric_types = [
            "rag_triad_answer_relevancy",
            "rag_triad_faithfulness",
            "rag_triad_contextual_relevancy",
            "response_time",
            "hallucination_rate",
            "cross_modal_coherence"
        ]

        for metric_type in metric_types:
            metric_record = metric_data_generator.generate_metric_record(
                job_id=str(job_record["id"]),
                metric_type=metric_type
            )
            metric_response = {
                "id": str(metric_record["id"]),
                "metric_type": metric_record["metric_type"],
                "metric_name": metric_record["metric_name"],
                "value": metric_record["value"],
                "created_at": metric_record["created_at"].isoformat()
            }
            all_metrics.append(metric_response)

        mock_job = Mock()
        mock_job.id = job_record["id"]
        mock_job.organization_id = str(test_organization.id)

        mock_rag_evaluation_service.get_evaluation_metrics.return_value = all_metrics

        with patch('src.api.evaluation.db') as mock_db:
            mock_db.query.return_value.filter.return_value.first.return_value = mock_job

            response = await async_client.get(
                f"/api/v1/evaluation/jobs/{job_record['id']}/metrics",
                headers=auth_headers
            )

        assert response.status_code == 200

        response_data = response.json()
        returned_types = {metric["metric_type"] for metric in response_data}

        # Should return all metric types
        for metric_type in metric_types:
            assert metric_type in returned_types, f"Metric type {metric_type} not found in response"

        # Validate each metric has required fields
        for metric_data in response_data:
            required_fields = self.JOB_METRICS_CONTRACT["response"]["success_schema"]["item_schema"]["required_fields"]
            assert contract_validator.validate_response_structure(metric_data, required_fields)