"""
Load testing scenarios for Evaluation API endpoints
Tests concurrent evaluation job creation, batch evaluation processing, real-time evaluation throughput,
and metrics retrieval performance under load
"""

import pytest
import asyncio
import time
import uuid
import random
from datetime import datetime
from httpx import AsyncClient, ASGITransport
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import statistics

from tests.contract.evaluation.fixtures.data_generators import (
    EvaluationDataGenerator, JobDataGenerator, MetricDataGenerator
)


class TestEvaluationLoadScenarios:
    """Load testing scenarios for evaluation endpoints"""

    # Load testing configuration
    LOAD_CONFIG = {
        "concurrent_users": {
            "light": 10,
            "moderate": 50,
            "heavy": 100
        },
        "request_burst": {
            "small": 20,
            "medium": 100,
            "large": 500
        },
        "sustained_load": {
            "duration_minutes": 5,
            "requests_per_second": 10
        },
        "performance_thresholds": {
            "response_time_p95": 2.0,  # seconds
            "response_time_p99": 5.0,  # seconds
            "error_rate": 0.05,  # 5% error rate threshold
            "throughput_min": 5  # requests per second
        }
    }

    class LoadTestResults:
        """Container for load test results"""
        def __init__(self):
            self.total_requests = 0
            self.successful_requests = 0
            self.failed_requests = 0
            self.response_times = []
            self.errors = []
            self.start_time = None
            self.end_time = None

        def add_result(self, success: bool, response_time: float, error: str = None):
            self.total_requests += 1
            if success:
                self.successful_requests += 1
            else:
                self.failed_requests += 1
                if error:
                    self.errors.append(error)

            self.response_times.append(response_time)

        def get_statistics(self) -> Dict[str, Any]:
            if not self.response_times:
                return {}

            duration = (self.end_time - self.start_time).total_seconds() if self.end_time and self.start_time else 0
            throughput = self.total_requests / duration if duration > 0 else 0

            return {
                "total_requests": self.total_requests,
                "successful_requests": self.successful_requests,
                "failed_requests": self.failed_requests,
                "success_rate": self.successful_requests / self.total_requests if self.total_requests > 0 else 0,
                "error_rate": self.failed_requests / self.total_requests if self.total_requests > 0 else 0,
                "throughput_rps": throughput,
                "response_time_avg": statistics.mean(self.response_times),
                "response_time_min": min(self.response_times),
                "response_time_max": max(self.response_times),
                "response_time_p50": statistics.median(self.response_times),
                "response_time_p95": self._percentile(self.response_times, 95),
                "response_time_p99": self._percentile(self.response_times, 99),
                "duration_seconds": duration,
                "unique_errors": list(set(self.errors))
            }

        def _percentile(self, data: List[float], percentile: int) -> float:
            """Calculate percentile of data"""
            if not data:
                return 0
            sorted_data = sorted(data)
            index = int(len(sorted_data) * percentile / 100)
            return sorted_data[min(index, len(sorted_data) - 1)]

    @pytest.mark.load_test
    @pytest.mark.slow
    async def test_concurrent_evaluation_job_creation_load(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        performance_tracker
    ):
        """Test concurrent evaluation job creation under load"""
        concurrent_users = self.LOAD_CONFIG["concurrent_users"]["moderate"]
        requests_per_user = 5

        results = self.LoadTestResults()
        evaluation_data_generator_instance = evaluation_data_generator

        async def create_evaluation_job(user_id: int) -> None:
            """Create evaluation jobs for a single user"""
            for request_num in range(requests_per_user):
                request_data = evaluation_data_generator_instance.generate_evaluation_request(
                    question_count=random.randint(1, 10)
                )

                start_time = time.time()
                try:
                    response = await async_client.post(
                        "/api/v1/evaluation/jobs",
                        headers=auth_headers,
                        json=request_data,
                        timeout=30.0
                    )
                    response_time = time.time() - start_time

                    success = response.status_code in [200, 201]
                    error = None if success else f"HTTP {response.status_code}: {response.text}"

                    results.add_result(success, response_time, error)

                except Exception as e:
                    response_time = time.time() - start_time
                    results.add_result(False, response_time, str(e))

                # Small delay between requests
                await asyncio.sleep(0.1)

        # Start load test
        print(f"\n🚀 Starting concurrent evaluation job creation load test")
        print(f"   Concurrent users: {concurrent_users}")
        print(f"   Requests per user: {requests_per_user}")
        print(f"   Total requests: {concurrent_users * requests_per_user}")

        results.start_time = datetime.utcnow()

        # Run concurrent users
        tasks = [
            create_evaluation_job(user_id)
            for user_id in range(concurrent_users)
        ]

        await asyncio.gather(*tasks, return_exceptions=True)

        results.end_time = datetime.utcnow()

        # Analyze results
        stats = results.get_statistics()

        print(f"\n📊 Load Test Results:")
        print(f"   Total requests: {stats['total_requests']}")
        print(f"   Success rate: {stats['success_rate']:.2%}")
        print(f"   Error rate: {stats['error_rate']:.2%}")
        print(f"   Throughput: {stats['throughput_rps']:.2f} RPS")
        print(f"   Avg response time: {stats['response_time_avg']:.3f}s")
        print(f"   P95 response time: {stats['response_time_p95']:.3f}s")
        print(f"   P99 response time: {stats['response_time_p99']:.3f}s")

        if stats['unique_errors']:
            print(f"   Unique errors: {len(stats['unique_errors'])}")
            for error in stats['unique_errors'][:5]:  # Show first 5 errors
                print(f"     - {error}")

        # Performance assertions
        assert stats['success_rate'] >= (1 - self.LOAD_CONFIG["performance_thresholds"]["error_rate"]), \
            f"Success rate {stats['success_rate']:.2%} below threshold"

        assert stats['response_time_p95'] <= self.LOAD_CONFIG["performance_thresholds"]["response_time_p95"], \
            f"P95 response time {stats['response_time_p95']:.3f}s exceeds threshold"

        assert stats['throughput_rps'] >= self.LOAD_CONFIG["performance_thresholds"]["throughput_min"], \
            f"Throughput {stats['throughput_rps']:.2f} RPS below minimum"

    @pytest.mark.load_test
    @pytest.mark.slow
    async def test_real_time_evaluation_throughput_load(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        performance_tracker
    ):
        """Test real-time evaluation throughput under load"""
        burst_size = self.LOAD_CONFIG["request_burst"]["medium"]

        results = self.LoadTestResults()
        evaluation_data_generator_instance = evaluation_data_generator

        print(f"\n⚡ Starting real-time evaluation throughput load test")
        print(f"   Burst size: {burst_size}")

        results.start_time = datetime.utcnow()

        # Generate burst of real-time evaluation requests
        tasks = []
        for i in range(burst_size):
            request_data = evaluation_data_generator_instance.generate_real_time_evaluation_request()

            async def evaluate_real_time(request_data: Dict[str, Any], request_id: int) -> None:
                start_time = time.time()
                try:
                    response = await async_client.post(
                        "/api/v1/evaluation/real-time",
                        headers=auth_headers,
                        json=request_data,
                        timeout=10.0  # Shorter timeout for real-time
                    )
                    response_time = time.time() - start_time

                    success = response.status_code in [200, 202]
                    error = None if success else f"HTTP {response.status_code}"

                    results.add_result(success, response_time, error)

                except Exception as e:
                    response_time = time.time() - start_time
                    results.add_result(False, response_time, str(e))

            tasks.append(evaluate_real_time(request_data, i))

        # Execute all requests concurrently
        await asyncio.gather(*tasks, return_exceptions=True)

        results.end_time = datetime.utcnow()

        # Analyze results
        stats = results.get_statistics()

        print(f"\n📊 Real-time Evaluation Load Test Results:")
        print(f"   Total requests: {stats['total_requests']}")
        print(f"   Success rate: {stats['success_rate']:.2%}")
        print(f"   Throughput: {stats['throughput_rps']:.2f} RPS")
        print(f"   Avg response time: {stats['response_time_avg']:.3f}s")
        print(f"   P95 response time: {stats['response_time_p95']:.3f}s")

        # Real-time evaluation should be faster
        assert stats['response_time_p95'] <= 1.0, \
            f"Real-time evaluation P95 {stats['response_time_p95']:.3f}s exceeds 1 second threshold"

        assert stats['success_rate'] >= 0.90, \
            f"Real-time evaluation success rate {stats['success_rate']:.2%} below 90%"

    @pytest.mark.load_test
    @pytest.mark.slow
    async def test_sustained_evaluation_metrics_load(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        job_data_generator: JobDataGenerator,
        metric_data_generator: MetricDataGenerator,
        performance_tracker
    ):
        """Test sustained load on metrics retrieval endpoint"""
        duration_minutes = 2  # Shorter for test environment
        requests_per_second = 5

        results = self.LoadTestResults()
        job_id = str(uuid.uuid4())

        print(f"\n🔄 Starting sustained metrics load test")
        print(f"   Duration: {duration_minutes} minutes")
        print(f"   Target RPS: {requests_per_second}")

        # Mock metrics data
        metrics_data = metric_data_generator.generate_metrics_response(
            job_id=job_id,
            metric_count=100
        )

        # Mock job and metrics retrieval
        mock_job = Mock()
        mock_job.id = job_id
        mock_job.organization_id = str(uuid.uuid4())

        with patch('src.api.evaluation.db') as mock_db:
            mock_db.query.return_value.filter.return_value.first.return_value = mock_job

            with patch('src.api.evaluation.rag_evaluation_service') as mock_service:
                mock_service.get_evaluation_metrics.return_value = metrics_data

                results.start_time = datetime.utcnow()
                end_time = results.start_time.timestamp() + (duration_minutes * 60)

                request_count = 0
                while time.time() < end_time:
                    batch_start = time.time()

                    # Send requests in batches
                    tasks = []
                    for _ in range(requests_per_second):
                        task = async_client.get(
                            f"/api/v1/evaluation/jobs/{job_id}/metrics",
                            headers=auth_headers,
                            timeout=5.0
                        )
                        tasks.append(task)

                    responses = await asyncio.gather(*tasks, return_exceptions=True)

                    for response in responses:
                        request_count += 1
                        if isinstance(response, Exception):
                            results.add_result(False, 0, str(response))
                        else:
                            success = response.status_code == 200
                            error = None if success else f"HTTP {response.status_code}"
                            results.add_result(success, 0, error)  # Response time not tracked for sustained test

                    # Rate limiting - wait for next second
                    elapsed = time.time() - batch_start
                    if elapsed < 1.0:
                        await asyncio.sleep(1.0 - elapsed)

                results.end_time = datetime.utcnow()

        # Analyze results
        stats = results.get_statistics()

        print(f"\n📊 Sustained Load Test Results:")
        print(f"   Total requests: {stats['total_requests']}")
        print(f"   Success rate: {stats['success_rate']:.2%}")
        print(f"   Actual RPS: {stats['throughput_rps']:.2f}")
        print(f"   Duration: {stats['duration_seconds']:.1f}s")

        # Sustained load should maintain high success rate
        assert stats['success_rate'] >= 0.95, \
            f"Sustained load success rate {stats['success_rate']:.2%} below 95%"

        # Should maintain reasonable throughput
        assert stats['throughput_rps'] >= (requests_per_second * 0.8), \
            f"Throughput {stats['throughput_rps']:.2f} RPS below 80% of target"

    @pytest.mark.load_test
    @pytest.mark.slow
    async def test_batch_evaluation_processing_load(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        performance_tracker
    ):
        """Test batch evaluation processing under load"""
        concurrent_batches = 10
        queries_per_batch = 50

        results = self.LoadTestResults()
        evaluation_data_generator_instance = evaluation_data_generator

        print(f"\n📦 Starting batch evaluation processing load test")
        print(f"   Concurrent batches: {concurrent_batches}")
        print(f"   Queries per batch: {queries_per_batch}")

        async def process_batch(batch_id: int) -> None:
            """Process a single batch evaluation"""
            request_data = evaluation_data_generator_instance.generate_batch_evaluation_request(
                query_count=queries_per_batch
            )

            start_time = time.time()
            try:
                response = await async_client.post(
                    "/api/v1/evaluation/jobs/batch",
                    headers=auth_headers,
                    json=request_data,
                    timeout=60.0  # Longer timeout for batch processing
                )
                response_time = time.time() - start_time

                success = response.status_code in [200, 201]
                error = None if success else f"HTTP {response.status_code}"

                results.add_result(success, response_time, error)

            except Exception as e:
                response_time = time.time() - start_time
                results.add_result(False, response_time, str(e))

        results.start_time = datetime.utcnow()

        # Process batches concurrently
        tasks = [
            process_batch(batch_id)
            for batch_id in range(concurrent_batches)
        ]

        await asyncio.gather(*tasks, return_exceptions=True)

        results.end_time = datetime.utcnow()

        # Analyze results
        stats = results.get_statistics()

        print(f"\n📊 Batch Processing Load Test Results:")
        print(f"   Total batches: {stats['total_requests']}")
        print(f"   Success rate: {stats['success_rate']:.2%}")
        print(f"   Avg response time: {stats['response_time_avg']:.3f}s")
        print(f"   Total queries processed: {stats['total_requests'] * queries_per_batch}")

        # Batch processing can be slower but should be reliable
        assert stats['success_rate'] >= 0.90, \
            f"Batch processing success rate {stats['success_rate']:.2%} below 90%"

        # Response time should be reasonable for batch size
        max_acceptable_time = queries_per_batch * 0.1  # 100ms per query max
        assert stats['response_time_p95'] <= max_acceptable_time, \
            f"Batch processing P95 {stats['response_time_p95']:.3f}s exceeds {max_acceptable_time:.3f}s"

    @pytest.mark.load_test
    @pytest.mark.slow
    async def test_mixed_workload_load(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        performance_tracker
    ):
        """Test mixed workload with different evaluation endpoint types"""
        duration_seconds = 60  # 1 minute mixed workload
        total_requests = 200

        results = self.LoadTestResults()
        evaluation_data_generator_instance = evaluation_data_generator

        workload_distribution = [
            ("job_creation", 0.4),      # 40% job creation
            ("real_time_eval", 0.3),    # 30% real-time evaluation
            ("job_retrieval", 0.2),     # 20% job retrieval
            ("metrics", 0.1)            # 10% metrics retrieval
        ]

        print(f"\n🎯 Starting mixed workload load test")
        print(f"   Duration: {duration_seconds}s")
        print(f"   Total requests: {total_requests}")
        print(f"   Workload distribution: {workload_distribution}")

        async def execute_mixed_request(request_type: str) -> None:
            """Execute a request based on type"""
            start_time = time.time()

            try:
                if request_type == "job_creation":
                    request_data = evaluation_data_generator_instance.generate_evaluation_request(
                        question_count=random.randint(1, 5)
                    )
                    response = await async_client.post(
                        "/api/v1/evaluation/jobs",
                        headers=auth_headers,
                        json=request_data,
                        timeout=30.0
                    )

                elif request_type == "real_time_eval":
                    request_data = evaluation_data_generator_instance.generate_real_time_evaluation_request()
                    response = await async_client.post(
                        "/api/v1/evaluation/real-time",
                        headers=auth_headers,
                        json=request_data,
                        timeout=10.0
                    )

                elif request_type == "job_retrieval":
                    job_id = str(uuid.uuid4())
                    response = await async_client.get(
                        f"/api/v1/evaluation/jobs/{job_id}",
                        headers=auth_headers,
                        timeout=10.0
                    )

                elif request_type == "metrics":
                    job_id = str(uuid.uuid4())
                    response = await async_client.get(
                        f"/api/v1/evaluation/jobs/{job_id}/metrics",
                        headers=auth_headers,
                        timeout=10.0
                    )

                else:
                    return

                response_time = time.time() - start_time
                success = response.status_code in [200, 201, 202, 404]  # 404 acceptable for retrieval
                error = None if success else f"HTTP {response.status_code}"

                results.add_result(success, response_time, error)

            except Exception as e:
                response_time = time.time() - start_time
                results.add_result(False, response_time, str(e))

        # Generate request types based on distribution
        request_types = []
        for request_type, percentage in workload_distribution:
            count = int(total_requests * percentage)
            request_types.extend([request_type] * count)

        random.shuffle(request_types)

        results.start_time = datetime.utcnow()

        # Execute requests with controlled timing
        interval = duration_seconds / len(request_types)
        for request_type in request_types:
            await execute_mixed_request(request_type)
            await asyncio.sleep(interval)

        results.end_time = datetime.utcnow()

        # Analyze results
        stats = results.get_statistics()

        print(f"\n📊 Mixed Workload Load Test Results:")
        print(f"   Total requests: {stats['total_requests']}")
        print(f"   Success rate: {stats['success_rate']:.2%}")
        print(f"   Throughput: {stats['throughput_rps']:.2f} RPS")
        print(f"   Avg response time: {stats['response_time_avg']:.3f}s")
        print(f"   P95 response time: {stats['response_time_p95']:.3f}s")

        # Mixed workload should maintain reasonable performance
        assert stats['success_rate'] >= 0.85, \
            f"Mixed workload success rate {stats['success_rate']:.2%} below 85%"

        assert stats['response_time_p95'] <= 3.0, \
            f"Mixed workload P95 {stats['response_time_p95']:.3f}s exceeds 3 seconds"

    @pytest.mark.load_test
    @pytest.mark.slow
    async def test_stress_test_maximum_capacity(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        evaluation_data_generator: EvaluationDataGenerator,
        performance_tracker
    ):
        """Stress test to find maximum sustainable capacity"""
        max_concurrent = self.LOAD_CONFIG["concurrent_users"]["heavy"]
        step_size = 10
        results_by_step = []

        print(f"\n💪 Starting stress test for maximum capacity")
        print(f"   Max concurrent: {max_concurrent}")
        print(f"   Step size: {step_size}")

        for concurrent in range(step_size, max_concurrent + 1, step_size):
            print(f"\n--- Testing with {concurrent} concurrent users ---")

            step_results = self.LoadTestResults()
            evaluation_data_generator_instance = evaluation_data_generator

            async def stress_request(user_id: int) -> None:
                request_data = evaluation_data_generator_instance.generate_evaluation_request(
                    question_count=3
                )

                start_time = time.time()
                try:
                    response = await async_client.post(
                        "/api/v1/evaluation/jobs",
                        headers=auth_headers,
                        json=request_data,
                        timeout=30.0
                    )
                    response_time = time.time() - start_time

                    success = response.status_code in [200, 201]
                    error = None if success else f"HTTP {response.status_code}"

                    step_results.add_result(success, response_time, error)

                except Exception as e:
                    response_time = time.time() - start_time
                    step_results.add_result(False, response_time, str(e))

            step_results.start_time = datetime.utcnow()

            # Run concurrent requests
            tasks = [
                stress_request(user_id)
                for user_id in range(concurrent)
            ]

            await asyncio.gather(*tasks, return_exceptions=True)

            step_results.end_time = datetime.utcnow()
            step_stats = step_results.get_statistics()
            results_by_step.append((concurrent, step_stats))

            print(f"   Success rate: {step_stats['success_rate']:.2%}")
            print(f"   P95 response time: {step_stats['response_time_p95']:.3f}s")
            print(f"   Throughput: {step_stats['throughput_rps']:.2f} RPS")

            # Stop test if performance degrades significantly
            if step_stats['success_rate'] < 0.80 or step_stats['response_time_p95'] > 5.0:
                print(f"   🛑 Performance degradation detected, stopping stress test")
                break

        # Analyze stress test results
        print(f"\n📈 Stress Test Summary:")
        for concurrent, stats in results_by_step:
            print(f"   {concurrent:3d} concurrent: {stats['success_rate']:.2%} success, "
                  f"{stats['response_time_p95']:.3f}s P95, {stats['throughput_rps']:.1f} RPS")

        # Find maximum sustainable capacity
        sustainable_steps = [
            (concurrent, stats) for concurrent, stats in results_by_step
            if stats['success_rate'] >= 0.90 and stats['response_time_p95'] <= 2.0
        ]

        if sustainable_steps:
            max_sustainable = max(sustainable_steps, key=lambda x: x[0])
            print(f"\n✅ Maximum sustainable concurrent users: {max_sustainable[0]}")
        else:
            print(f"\n⚠️  No sustainable configuration found with current thresholds")

        # At least some level should be sustainable
        assert len(sustainable_steps) > 0, "No sustainable configuration found during stress test"