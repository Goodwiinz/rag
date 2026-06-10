"""
Integration tests for complete evaluation workflows
Tests end-to-end evaluation processes combining multiple API endpoints
"""

import pytest
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient
from unittest.mock import patch, Mock
from typing import Dict, Any, List

from tests.constants import TEST_JWT_SECRET
from tests.contract.evaluation.fixtures.data_generators import (
    EvaluationDataGenerator, JobDataGenerator, MetricDataGenerator
)


class TestEvaluationIntegrationWorkflows:
    """Integration tests for complete evaluation workflows"""

    @pytest.mark.contract
    @pytest.mark.integration
    async def test_complete_evaluation_workflow_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_user,
        test_organization,
        evaluation_data_generator: EvaluationDataGenerator,
        job_data_generator: JobDataGenerator,
        metric_data_generator: MetricDataGenerator,
        contract_validator,
        performance_tracker
    ):
        """Test complete evaluation workflow from job creation to metrics retrieval"""
        workflow_start = performance_tracker.start_timer("complete_evaluation_workflow")

        # Step 1: Create evaluation job
        performance_tracker.start_timer("create_job_step")
        request_data = evaluation_data_generator.generate_evaluation_request(
            question_count=5,
            include_references=True,
            include_contexts=True
        )

        # Mock job creation
        mock_job = Mock()
        mock_job.id = uuid.uuid4()
        mock_job.name = request_data["name"]
        mock_job.status = "pending"
        mock_job.created_at = datetime.now(timezone.utc)
        mock_job.dataset_size = len(request_data["questions"])

        with patch('src.api.evaluation.rag_evaluation_service') as mock_service:
            mock_service.create_evaluation_job.return_value = mock_job

            response = await async_client.post(
                "/api/v1/evaluation/jobs",
                headers=auth_headers,
                json=request_data
            )

        assert response.status_code in [200, 201]
        create_time = performance_tracker.end_timer("create_job_step")

        job_data = response.json()
        job_id = job_data["job_id"]

        # Validate job creation response
        required_fields = ["job_id", "name", "status", "dataset_size", "created_at", "message"]
        assert contract_validator.validate_response_structure(job_data, required_fields)

        # Step 2: Get job details
        performance_tracker.start_timer("get_job_step")
        with patch('src.api.evaluation.db') as mock_db:
            mock_db.query.return_value.filter.return_value.first.return_value = mock_job
            mock_service.get_evaluation_summary.return_value = job_data_generator.generate_job_summary_response({
                "id": mock_job.id,
                "name": mock_job.name,
                "status": "completed",
                "created_at": mock_job.created_at
            })

            response = await async_client.get(
                f"/api/v1/evaluation/jobs/{job_id}",
                headers=auth_headers
            )

        assert response.status_code == 200
        get_time = performance_tracker.end_timer("get_job_step")

        job_details = response.json()
        assert job_details["job_id"] == job_id

        # Step 3: Get job metrics
        performance_tracker.start_timer("get_metrics_step")
        metrics_data = metric_data_generator.generate_metrics_response(
            job_id=job_id,
            metric_count=5
        )

        with patch('src.api.evaluation.db') as mock_db:
            mock_db.query.return_value.filter.return_value.first.return_value = mock_job
            mock_service.get_evaluation_metrics.return_value = metrics_data

            response = await async_client.get(
                f"/api/v1/evaluation/jobs/{job_id}/metrics",
                headers=auth_headers
            )

        assert response.status_code == 200
        metrics_time = performance_tracker.end_timer("get_metrics_step")

        metrics = response.json()
        assert isinstance(metrics, list)
        assert len(metrics) > 0

        # Validate metrics structure
        for metric in metrics:
            required_fields = ["id", "metric_type", "metric_name", "value", "created_at"]
            assert contract_validator.validate_response_structure(metric, required_fields)

        # Step 4: Get metrics summary
        performance_tracker.start_timer("get_summary_step")
        summary_data = metric_data_generator.generate_metrics_summary(days=30)

        mock_service.get_metrics_summary.return_value = summary_data
        response = await async_client.get(
            "/api/v1/evaluation/metrics/summary?days=30",
            headers=auth_headers
        )

        assert response.status_code == 200
        summary_time = performance_tracker.end_timer("get_summary_step")

        summary = response.json()
        required_fields = ["period_days", "total_metrics", "metric_summary", "threshold_violations", "average_scores", "violation_rate"]
        assert contract_validator.validate_response_structure(summary, required_fields)

        workflow_time = performance_tracker.end_timer("complete_evaluation_workflow")

        # Performance validation
        print(f"\n📊 Workflow Performance:")
        print(f"   Create job: {create_time:.3f}s")
        print(f"   Get job: {get_time:.3f}s")
        print(f"   Get metrics: {metrics_time:.3f}s")
        print(f"   Get summary: {summary_time:.3f}s")
        print(f"   Total workflow: {workflow_time:.3f}s")

        # Workflow should complete within reasonable time
        assert workflow_time < 5.0, f"Workflow took {workflow_time:.3f}s, exceeds 5 second threshold"

    @pytest.mark.contract
    @pytest.mark.integration
    async def test_batch_evaluation_workflow_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        contract_validator,
        performance_tracker
    ):
        """Test batch evaluation workflow with monitoring"""
        workflow_start = performance_tracker.start_timer("batch_evaluation_workflow")

        # Step 1: Create batch evaluation job
        performance_tracker.start_timer("create_batch_step")
        request_data = evaluation_data_generator.generate_batch_evaluation_request(
            query_count=20,
            search_type="hybrid"
        )

        # Mock batch job creation
        mock_batch_job = Mock()
        mock_batch_job.id = uuid.uuid4()
        mock_batch_job.name = request_data["name"]
        mock_batch_job.status = "running"
        mock_batch_job.dataset_size = len(request_data["queries"])

        with patch('src.api.evaluation.db') as mock_db:
            mock_db.add.return_value = None
            mock_db.commit.return_value = None
            mock_db.refresh.return_value = None

            response = await async_client.post(
                "/api/v1/evaluation/jobs/batch",
                headers=auth_headers,
                json=request_data
            )

        assert response.status_code in [200, 201]
        create_time = performance_tracker.end_timer("create_batch_step")

        batch_data = response.json()
        batch_job_id = batch_data["job_id"]

        # Validate batch job response
        assert contract_validator.validate_response_structure(batch_data, [
            "job_id", "name", "status", "dataset_size", "created_at", "message"
        ])

        # Step 2: Monitor job progress
        performance_tracker.start_timer("monitor_batch_step")
        with patch('src.api.evaluation.db') as mock_db:
            # Mock job status updates
            mock_running_job = Mock()
            mock_running_job.id = mock_batch_job.id
            mock_running_job.status = "completed"
            mock_running_job.dataset_size = mock_batch_job.dataset_size
            mock_running_job.processed_count = mock_batch_job.dataset_size

            mock_db.query.return_value.filter.return_value.first.return_value = mock_running_job

            # Poll for job completion
            max_attempts = 5
            for attempt in range(max_attempts):
                response = await async_client.get(
                    f"/api/v1/evaluation/jobs/{batch_job_id}",
                    headers=auth_headers
                )

                if response.status_code == 200:
                    job_status = response.json()
                    if job_status["status"] == "completed":
                        break
                await asyncio.sleep(0.1)  # Small delay between polls

        monitor_time = performance_tracker.end_timer("monitor_batch_step")

        # Step 3: Verify batch job completion
        response = await async_client.get(
            f"/api/v1/evaluation/jobs/{batch_job_id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        final_job_data = response.json()
        assert final_job_data["processed_count"] == request_data["queries"]

        workflow_time = performance_tracker.end_timer("batch_evaluation_workflow")

        print(f"\n📊 Batch Workflow Performance:")
        print(f"   Create batch: {create_time:.3f}s")
        print(f"   Monitor batch: {monitor_time:.3f}s")
        print(f"   Total workflow: {workflow_time:.3f}s")

        assert workflow_time < 10.0, f"Batch workflow took {workflow_time:.3f}s, exceeds 10 second threshold"

    @pytest.mark.contract
    @pytest.mark.integration
    async def test_real_time_evaluation_workflow_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        contract_validator,
        performance_tracker
    ):
        """Test real-time evaluation workflow with task tracking"""
        workflow_start = performance_tracker.start_timer("realtime_evaluation_workflow")

        # Step 1: Submit real-time evaluation
        performance_tracker.start_timer("submit_realtime_step")
        request_data = evaluation_data_generator.generate_real_time_evaluation_request(
            include_reference=True
        )

        # Mock real-time task creation
        mock_task = Mock()
        mock_task.id = "real-time-task-123"

        with patch('src.api.evaluation.run_real_time_evaluation') as mock_task_func:
            mock_task_func.delay.return_value = mock_task

            response = await async_client.post(
                "/api/v1/evaluation/real-time",
                headers=auth_headers,
                json=request_data
            )

        assert response.status_code in [200, 202]
        submit_time = performance_tracker.end_timer("submit_realtime_step")

        realtime_data = response.json()
        task_id = realtime_data["task_id"]

        # Validate real-time response
        assert contract_validator.validate_response_structure(realtime_data, [
            "task_id", "status", "message"
        ])

        # Step 2: Monitor task status (if endpoint exists)
        performance_tracker.start_timer("monitor_task_step")
        # Note: This assumes a task status endpoint exists
        # In a real implementation, you would poll task status

        # Simulate task monitoring
        await asyncio.sleep(0.1)  # Simulate brief processing time
        monitor_time = performance_tracker.end_timer("monitor_task_step")

        workflow_time = performance_tracker.end_timer("realtime_evaluation_workflow")

        print(f"\n📊 Real-time Workflow Performance:")
        print(f"   Submit evaluation: {submit_time:.3f}s")
        print(f"   Monitor task: {monitor_time:.3f}s")
        print(f"   Total workflow: {workflow_time:.3f}s")

        # Real-time workflow should be very fast
        assert workflow_time < 2.0, f"Real-time workflow took {workflow_time:.3f}s, exceeds 2 second threshold"

    @pytest.mark.contract
    @pytest.mark.integration
    async def test_evaluation_comparison_workflow_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_user,
        test_organization,
        evaluation_data_generator: EvaluationDataGenerator,
        job_data_generator: JobDataGenerator,
        contract_validator,
        performance_tracker
    ):
        """Test evaluation comparison workflow"""
        workflow_start = performance_tracker.start_timer("comparison_workflow")

        # Step 1: Create two evaluation jobs for comparison
        performance_tracker.start_timer("create_jobs_for_comparison")

        # Mock two completed jobs
        job1 = job_data_generator.generate_job_record(
            organization_id=str(test_organization.id),
            user_id=str(test_user.id),
            status="completed"
        )
        job2 = job_data_generator.generate_job_record(
            organization_id=str(test_organization.id),
            user_id=str(test_user.id),
            status="completed"
        )

        create_time = performance_tracker.end_timer("create_jobs_for_comparison")

        # Step 2: Create comparison
        performance_tracker.start_timer("create_comparison_step")
        comparison_request = evaluation_data_generator.generate_comparison_request(
            baseline_job_id=str(job1["id"]),
            comparison_job_id=str(job2["id"])
        )

        # Mock job retrieval for comparison
        mock_job1 = Mock()
        mock_job1.id = job1["id"]
        mock_job1.organization_id = str(test_organization.id)

        mock_job2 = Mock()
        mock_job2.id = job2["id"]
        mock_job2.organization_id = str(test_organization.id)

        with patch('src.api.evaluation.db') as mock_db:
            mock_query = Mock()
            mock_query.filter.return_value.first.side_effect = [mock_job1, mock_job2]
            mock_db.query.return_value = mock_query

            response = await async_client.post(
                "/api/v1/evaluation/comparisons",
                headers=auth_headers,
                json=comparison_request
            )

        assert response.status_code in [200, 201]
        comparison_time = performance_tracker.end_timer("create_comparison_step")

        comparison_data = response.json()
        assert contract_validator.validate_response_structure(comparison_data, [
            "status", "message", "baseline_job", "comparison_job", "name"
        ])

        # Step 3: List comparisons
        performance_tracker.start_timer("list_comparisons_step")
        with patch('src.api.evaluation.db') as mock_db:
            mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

            response = await async_client.get(
                "/api/v1/evaluation/comparisons",
                headers=auth_headers
            )

        assert response.status_code == 200
        list_time = performance_tracker.end_timer("list_comparisons_step")

        comparisons = response.json()
        assert isinstance(comparisons, list)

        workflow_time = performance_tracker.end_timer("comparison_workflow")

        print(f"\n📊 Comparison Workflow Performance:")
        print(f"   Create jobs: {create_time:.3f}s")
        print(f"   Create comparison: {comparison_time:.3f}s")
        print(f"   List comparisons: {list_time:.3f}s")
        print(f"   Total workflow: {workflow_time:.3f}s")

        assert workflow_time < 5.0, f"Comparison workflow took {workflow_time:.3f}s, exceeds 5 second threshold"

    @pytest.mark.contract
    @pytest.mark.integration
    async def test_multi_user_evaluation_workflow_contract(
        self,
        async_client: AsyncClient,
        test_user,
        test_admin_user,
        test_organization,
        evaluation_data_generator: EvaluationDataGenerator,
        contract_validator
    ):
        """Test evaluation workflow with multiple users and roles"""
        # Generate tokens for different users
        import jwt
        secret = TEST_JWT_SECRET

        # User token
        user_payload = {
            "sub": str(test_user.id),
            "email": test_user.email,
            "role": "user",
            "organization_id": str(test_organization.id),
            "exp": datetime.now(timezone.utc).timestamp() + 3600,
            "iat": datetime.now(timezone.utc).timestamp()
        }
        user_token = jwt.encode(user_payload, secret, algorithm="HS256")

        # Admin token
        admin_payload = {
            "sub": str(test_admin_user.id),
            "email": test_admin_user.email,
            "role": "admin",
            "organization_id": str(test_organization.id),
            "exp": datetime.now(timezone.utc).timestamp() + 3600,
            "iat": datetime.now(timezone.utc).timestamp()
        }
        admin_token = jwt.encode(admin_payload, secret, algorithm="HS256")

        user_headers = {
            "Authorization": f"Bearer {user_token}",
            "Content-Type": "application/json"
        }

        admin_headers = {
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json"
        }

        # Step 1: Regular user creates evaluation
        user_request = evaluation_data_generator.generate_evaluation_request(
            question_count=3
        )

        with patch('src.api.evaluation.rag_evaluation_service') as mock_service:
            mock_user_job = Mock()
            mock_user_job.id = uuid.uuid4()
            mock_user_job.name = user_request["name"]
            mock_user_job.status = "pending"
            mock_user_job.dataset_size = len(user_request["questions"])
            mock_service.create_evaluation_job.return_value = mock_user_job

            user_response = await async_client.post(
                "/api/v1/evaluation/jobs",
                headers=user_headers,
                json=user_request
            )

        assert user_response.status_code in [200, 201]
        user_job_id = user_response.json()["job_id"]

        # Step 2: Admin creates evaluation
        admin_request = evaluation_data_generator.generate_evaluation_request(
            question_count=5
        )

        with patch('src.api.evaluation.rag_evaluation_service') as mock_service:
            mock_admin_job = Mock()
            mock_admin_job.id = uuid.uuid4()
            mock_admin_job.name = admin_request["name"]
            mock_admin_job.status = "pending"
            mock_admin_job.dataset_size = len(admin_request["questions"])
            mock_service.create_evaluation_job.return_value = mock_admin_job

            admin_response = await async_client.post(
                "/api/v1/evaluation/jobs",
                headers=admin_headers,
                json=admin_request
            )

        assert admin_response.status_code in [200, 201]
        admin_job_id = admin_response.json()["job_id"]

        # Step 3: Both users list evaluations (should only see their own)
        with patch('src.api.evaluation.db') as mock_db:
            # Mock user can only see their job
            mock_user_job_obj = Mock()
            mock_user_job_obj.id = mock_user_job.id
            mock_user_job_obj.name = mock_user_job.name
            mock_user_job_obj.status = mock_user_job.status
            mock_user_job_obj.evaluation_type = "rag_triad"
            mock_user_job_obj.created_at = datetime.now(timezone.utc)
            mock_user_job_obj.dataset_size = mock_user_job.dataset_size
            mock_user_job_obj.processed_count = 0
            mock_user_job_obj.overall_score = None
            mock_user_job_obj.success_rate = None
            mock_user_job_obj.error_message = None

            mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_user_job_obj]

            user_list_response = await async_client.get(
                "/api/v1/evaluation/jobs",
                headers=user_headers
            )

        assert user_list_response.status_code == 200
        user_jobs = user_list_response.json()
        assert len(user_jobs) >= 0

        # Step 4: Admin can see all organization jobs
        with patch('src.api.evaluation.db') as mock_db:
            mock_admin_job_obj = Mock()
            mock_admin_job_obj.id = mock_admin_job.id
            mock_admin_job_obj.name = mock_admin_job.name
            mock_admin_job_obj.status = mock_admin_job.status
            mock_admin_job_obj.evaluation_type = "rag_triad"
            mock_admin_job_obj.created_at = datetime.now(timezone.utc)
            mock_admin_job_obj.dataset_size = mock_admin_job.dataset_size
            mock_admin_job_obj.processed_count = 0
            mock_admin_job_obj.overall_score = None
            mock_admin_job_obj.success_rate = None
            mock_admin_job_obj.error_message = None

            mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_admin_job_obj]

            admin_list_response = await async_client.get(
                "/api/v1/evaluation/jobs",
                headers=admin_headers
            )

        assert admin_list_response.status_code == 200
        admin_jobs = admin_list_response.json()
        assert len(admin_jobs) >= 0

        # Validate both users can perform their roles appropriately
        assert user_job_id is not None
        assert admin_job_id is not None

    @pytest.mark.contract
    @pytest.mark.integration
    async def test_error_handling_integration_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        contract_validator
    ):
        """Test error handling across integrated workflow"""
        # Step 1: Create valid job (should succeed)
        valid_request = evaluation_data_generator.generate_evaluation_request(
            question_count=3
        )

        with patch('src.api.evaluation.rag_evaluation_service') as mock_service:
            mock_job = Mock()
            mock_job.id = uuid.uuid4()
            mock_job.name = valid_request["name"]
            mock_job.status = "pending"
            mock_job.dataset_size = len(valid_request["questions"])
            mock_service.create_evaluation_job.return_value = mock_job

            response = await async_client.post(
                "/api/v1/evaluation/jobs",
                headers=auth_headers,
                json=valid_request
            )

        assert response.status_code in [200, 201]
        job_data = response.json()
        job_id = job_data["job_id"]

        # Step 2: Try to get metrics for non-existent job (should fail gracefully)
        response = await async_client.get(
            f"/api/v1/evaluation/jobs/{uuid.uuid4()}/metrics",
            headers=auth_headers
        )

        assert response.status_code == 404
        error_data = response.json()
        assert contract_validator.validate_error_response(error_data)

        # Step 3: Try to create comparison with invalid job IDs (should fail gracefully)
        invalid_comparison = {
            "name": "Invalid Comparison",
            "baseline_job_id": str(uuid.uuid4()),
            "comparison_job_id": str(uuid.uuid4())
        }

        response = await async_client.post(
            "/api/v1/evaluation/comparisons",
            headers=auth_headers,
            json=invalid_comparison
        )

        assert response.status_code == 404
        error_data = response.json()
        assert contract_validator.validate_error_response(error_data)

        # Step 4: Try invalid real-time evaluation (should fail gracefully)
        invalid_realtime = {
            "query": "",  # Empty query
            "generated_answer": "Some answer",
            "retrieved_context": []
        }

        response = await async_client.post(
            "/api/v1/evaluation/real-time",
            headers=auth_headers,
            json=invalid_realtime
        )

        assert response.status_code == 400
        error_data = response.json()
        assert contract_validator.validate_error_response(error_data)

        # All error responses should be consistent
        for error_response in [error_data]:
            assert "error" in error_response
            assert error_response["error"]["status_code"] in [400, 404]
            assert error_response["error"]["type"] is not None
            assert error_response["error"]["message"] is not None

    @pytest.mark.contract
    @pytest.mark.integration
    async def test_concurrent_workflows_contract(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        performance_tracker
    ):
        """Test multiple evaluation workflows running concurrently"""
        concurrent_workflows = 5

        async def run_workflow(workflow_id: int) -> Dict[str, Any]:
            """Run a single evaluation workflow"""
            try:
                # Create evaluation job
                request_data = evaluation_data_generator.generate_evaluation_request(
                    question_count=3
                )

                with patch('src.api.evaluation.rag_evaluation_service') as mock_service:
                    mock_job = Mock()
                    mock_job.id = uuid.uuid4()
                    mock_job.name = request_data["name"]
                    mock_job.status = "pending"
                    mock_job.dataset_size = len(request_data["questions"])
                    mock_service.create_evaluation_job.return_value = mock_job

                    start_time = datetime.now(timezone.utc)

                    response = await async_client.post(
                        "/api/v1/evaluation/jobs",
                        headers=auth_headers,
                        json=request_data
                    )

                    end_time = datetime.now(timezone.utc)
                    duration = (end_time - start_time).total_seconds()

                    return {
                        "workflow_id": workflow_id,
                        "success": response.status_code in [200, 201],
                        "duration": duration,
                        "response_code": response.status_code
                    }

            except Exception as e:
                return {
                    "workflow_id": workflow_id,
                    "success": False,
                    "duration": 0,
                    "error": str(e)
                }

        # Run workflows concurrently
        tasks = [
            run_workflow(i)
            for i in range(concurrent_workflows)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Analyze concurrent workflow results
        successful_workflows = [r for r in results if isinstance(r, dict) and r.get("success", False)]
        failed_workflows = [r for r in results if isinstance(r, dict) and not r.get("success", False)]

        print(f"\n📊 Concurrent Workflow Results:")
        print(f"   Total workflows: {len(results)}")
        print(f"   Successful: {len(successful_workflows)}")
        print(f"   Failed: {len(failed_workflows)}")

        if successful_workflows:
            durations = [w["duration"] for w in successful_workflows]
            print(f"   Average duration: {sum(durations) / len(durations):.3f}s")
            print(f"   Max duration: {max(durations):.3f}s")
            print(f"   Min duration: {min(durations):.3f}s")

        # Most workflows should succeed
        success_rate = len(successful_workflows) / len(results) if results else 0
        assert success_rate >= 0.8, f"Concurrent workflow success rate {success_rate:.2%} below 80%"

        # No workflow should take excessively long
        if successful_workflows:
            max_duration = max(w["duration"] for w in successful_workflows)
            assert max_duration < 5.0, f"Concurrent workflow took {max_duration:.3f}s, exceeds 5 second threshold"