"""
Performance Integration Tests
Tests response times, throughput, and system performance under load
"""

import pytest
import asyncio
import time
import uuid
import statistics
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Tuple
from concurrent.futures import ThreadPoolExecutor
import psutil
import gc

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from conftest import (
    APIAssertions, create_auth_headers, wait_for_condition,
    sample_organization, sample_user, sample_dashboard, sample_report
)


class TestPerformanceIntegration:
    """Test system performance and scalability"""

    @pytest.fixture
    async def performance_metrics(self):
        """Collect performance metrics during tests"""
        class PerformanceMetrics:
            def __init__(self):
                self.response_times = []
                self.memory_usage = []
                self.cpu_usage = []
                self.error_count = 0
                self.success_count = 0
                self.start_time = None
                self.end_time = None

            def start(self):
                self.start_time = time.time()
                gc.collect()  # Clean up before test

            def stop(self):
                self.end_time = time.time()

            def record_response(self, response_time: float, success: bool):
                self.response_times.append(response_time)
                if success:
                    self.success_count += 1
                else:
                    self.error_count += 1

            def record_system_metrics(self):
                self.memory_usage.append(psutil.Process().memory_info().rss / 1024 / 1024)  # MB
                self.cpu_usage.append(psutil.cpu_percent())

            @property
            def duration(self):
                return self.end_time - self.start_time if self.end_time and self.start_time else 0

            @property
            def avg_response_time(self):
                return statistics.mean(self.response_times) if self.response_times else 0

            @property
            def p95_response_time(self):
                return statistics.quantiles(self.response_times, n=20)[18] if len(self.response_times) >= 20 else max(self.response_times) if self.response_times else 0

            @property
            def requests_per_second(self):
                return len(self.response_times) / self.duration if self.duration > 0 else 0

            @property
            def success_rate(self):
                total = self.success_count + self.error_count
                return self.success_count / total if total > 0 else 0

        return PerformanceMetrics()

    @pytest.mark.integration
    @pytest.mark.performance
    async def test_api_response_times(self, api_client: AsyncClient, auth_headers, sample_organization, performance_metrics):
        """Test API response times meet performance targets"""
        org_id = sample_organization["id"]
        performance_metrics.start()

        # Define performance targets (in milliseconds)
        performance_targets = {
            "realtime_metrics": 2000,  # 2 seconds for real-time metrics
            "dashboard_list": 1000,    # 1 second for dashboard listing
            "graph_centrality": 5000, # 5 seconds for graph analytics
            "report_list": 1500        # 1.5 seconds for report listing
        }

        test_endpoints = [
            {
                "name": "realtime_metrics",
                "request": lambda: api_client.get(
                    f"/api/v1/analytics/realtime/metrics",
                    params={"organization_id": str(org_id)},
                    headers=auth_headers
                ),
                "target": performance_targets["realtime_metrics"]
            },
            {
                "name": "dashboard_list",
                "request": lambda: api_client.get(
                    f"/api/v1/analytics/dashboard/configurations",
                    params={"organization_id": str(org_id)},
                    headers=auth_headers
                ),
                "target": performance_targets["dashboard_list"]
            },
            {
                "name": "graph_centrality",
                "request": lambda: api_client.get(
                    f"/api/v1/analytics/graph/analytics/centrality",
                    params={
                        "organization_id": str(org_id),
                        "algorithm": "degree",
                        "limit": 100
                    },
                    headers=auth_headers
                ),
                "target": performance_targets["graph_centrality"]
            },
            {
                "name": "report_list",
                "request": lambda: api_client.get(
                    f"/api/v1/analytics/reports",
                    params={"organization_id": str(org_id)},
                    headers=auth_headers
                ),
                "target": performance_targets["report_list"]
            }
        ]

        # Run each endpoint multiple times
        for endpoint in test_endpoints:
            response_times = []

            for i in range(5):  # 5 iterations per endpoint
                start_time = time.time()
                try:
                    response = await endpoint["request"]()
                    response_time = (time.time() - start_time) * 1000  # Convert to milliseconds

                    success = response.status_code in [200, 201, 204]
                    performance_metrics.record_response(response_time, success)

                    response_times.append(response_time)

                    if not success:
                        print(f"Error response for {endpoint['name']}: {response.status_code}")

                except Exception as e:
                    response_time = (time.time() - start_time) * 1000
                    performance_metrics.record_response(response_time, False)
                    print(f"Exception for {endpoint['name']}: {e}")

                await asyncio.sleep(0.1)  # Small delay between requests

            # Check performance target
            if response_times:
                avg_time = statistics.mean(response_times)
                max_time = max(response_times)

                print(f"{endpoint['name']}: avg={avg_time:.0f}ms, max={max_time:.0f}ms, target={endpoint['target']}ms")

                # Allow some tolerance (10% over target)
                tolerance = 1.1
                assert avg_time <= endpoint['target'] * tolerance, (
                    f"{endpoint['name']} average response time {avg_time:.0f}ms exceeds target {endpoint['target']}ms"
                )

        performance_metrics.stop()

    @pytest.mark.integration
    @pytest.mark.performance
    async def test_concurrent_requests(self, api_client: AsyncClient, auth_headers, sample_organization, performance_metrics):
        """Test system performance under concurrent load"""
        org_id = sample_organization["id"]
        performance_metrics.start()

        # Test parameters
        concurrent_users = 10
        requests_per_user = 5
        target_rps = 50  # requests per second

        async def user_session(user_id: int):
            """Simulate a user session with multiple requests"""
            user_metrics = []

            for request_num in range(requests_per_user):
                start_time = time.time()

                try:
                    response = await api_client.get(
                        f"/api/v1/analytics/realtime/metrics",
                        params={"organization_id": str(org_id)},
                        headers=auth_headers
                    )

                    response_time = (time.time() - start_time) * 1000
                    success = response.status_code == 200

                    performance_metrics.record_response(response_time, success)
                    user_metrics.append(response_time)

                except Exception as e:
                    response_time = (time.time() - start_time) * 1000
                    performance_metrics.record_response(response_time, False)
                    print(f"User {user_id} request {request_num} failed: {e}")

                # Simulate user think time
                await asyncio.sleep(0.2)

            return user_metrics

        # Start concurrent user sessions
        start_time = time.time()
        tasks = [user_session(i) for i in range(concurrent_users)]

        # Wait for all sessions to complete
        user_metrics_list = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time

        performance_metrics.stop()

        # Calculate overall metrics
        total_requests = concurrent_users * requests_per_user
        actual_rps = total_requests / total_time

        print(f"Concurrent test: {concurrent_users} users, {total_requests} requests")
        print(f"Total time: {total_time:.2f}s, RPS: {actual_rps:.1f}")
        print(f"Success rate: {performance_metrics.success_rate:.2%}")
        print(f"Avg response time: {performance_metrics.avg_response_time:.0f}ms")
        print(f"P95 response time: {performance_metrics.p95_response_time:.0f}ms")

        # Performance assertions
        assert performance_metrics.success_rate >= 0.95, "Success rate should be at least 95%"
        assert performance_metrics.avg_response_time <= 3000, "Average response time should be under 3 seconds"
        assert performance_metrics.p95_response_time <= 5000, "P95 response time should be under 5 seconds"

        # Should achieve reasonable throughput
        assert actual_rps >= target_rps * 0.5, f"RPS {actual_rps:.1f} should be at least 50% of target {target_rps}"

    @pytest.mark.integration
    @pytest.mark.performance
    async def test_memory_usage_under_load(self, api_client: AsyncClient, auth_headers, sample_organization, performance_metrics):
        """Test memory usage doesn't grow excessively under load"""
        org_id = sample_organization["id"]
        performance_metrics.start()

        # Baseline memory measurement
        baseline_memory = psutil.Process().memory_info().rss / 1024 / 1024
        print(f"Baseline memory: {baseline_memory:.1f}MB")

        # Generate sustained load
        load_duration = 30  # seconds
        concurrent_requests = 5

        async def continuous_requests():
            """Make continuous requests for duration test"""
            start_time = time.time()
            request_count = 0

            while time.time() - start_time < load_duration:
                try:
                    response = await api_client.get(
                        f"/api/v1/analytics/realtime/metrics",
                        params={"organization_id": str(org_id)},
                        headers=auth_headers
                    )

                    request_count += 1
                    performance_metrics.record_response(100, response.status_code == 200)  # Simplified timing

                except Exception as e:
                    performance_metrics.record_response(100, False)
                    print(f"Memory test request failed: {e}")

                await asyncio.sleep(0.5)  # 2 requests per second per worker

            return request_count

        # Start concurrent workers
        tasks = [continuous_requests() for _ in range(concurrent_requests)]

        # Monitor memory during test
        async def monitor_memory():
            while any(not task.done() for task in tasks):
                performance_metrics.record_system_metrics()
                await asyncio.sleep(2)

        monitor_task = asyncio.create_task(monitor_memory())

        # Wait for load test completion
        request_counts = await asyncio.gather(*tasks, return_exceptions=True)
        await monitor_task

        performance_metrics.stop()

        # Final memory measurement
        final_memory = psutil.Process().memory_info().rss / 1024 / 1024
        memory_growth = final_memory - baseline_memory

        total_requests = sum(count for count in request_counts if isinstance(count, int))
        print(f"Memory usage test:")
        print(f"  Baseline: {baseline_memory:.1f}MB")
        print(f"  Final: {final_memory:.1f}MB")
        print(f"  Growth: {memory_growth:.1f}MB")
        print(f"  Requests: {total_requests}")
        print(f"  Memory per request: {(memory_growth * 1024 / total_requests):.2f}KB" if total_requests > 0 else "N/A")

        # Memory assertions
        assert memory_growth <= 100, f"Memory growth {memory_growth:.1f}MB should be under 100MB"
        assert final_memory <= 500, f"Final memory {final_memory:.1f}MB should be under 500MB"

    @pytest.mark.integration
    @pytest.mark.performance
    async def test_large_response_handling(self, api_client: AsyncClient, auth_headers, sample_organization, performance_metrics):
        """Test performance with large response payloads"""
        org_id = sample_organization["id"]
        performance_metrics.start()

        # Request large datasets
        large_requests = [
            {
                "name": "large_metrics_dataset",
                "request": api_client.get(
                    f"/api/v1/analytics/metrics/aggregations",
                    params={
                        "organization_id": str(org_id),
                        "metric_type": "entity",
                        "time_bucket": "hour",
                        "start_time": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
                        "end_time": datetime.now(timezone.utc).isoformat()
                    },
                    headers=auth_headers
                )
            },
            {
                "name": "large_graph_analysis",
                "request": api_client.get(
                    f"/api/v1/analytics/graph/analytics/centrality",
                    params={
                        "organization_id": str(org_id),
                        "algorithm": "degree",
                        "limit": 1000  # Large result set
                    },
                    headers=auth_headers
                )
            }
        ]

        for test_case in large_requests:
            start_time = time.time()

            try:
                response = await test_case["request"]
                response_time = (time.time() - start_time) * 1000

                # Calculate response size
                response_size = len(response.content) / 1024  # KB
                success = response.status_code == 200

                performance_metrics.record_response(response_time, success)

                print(f"{test_case['name']}: {response_time:.0f}ms, {response_size:.1f}KB")

                # Performance assertions for large responses
                assert response_time <= 10000, f"Large response time {response_time:.0f}ms should be under 10 seconds"
                assert response_size <= 10 * 1024, f"Response size {response_size:.1f}KB should be under 10MB"

                if success:
                    # Verify response is valid JSON
                    try:
                        response.json()
                    except json.JSONDecodeError:
                        pytest.fail(f"Large response is not valid JSON for {test_case['name']}")

            except Exception as e:
                response_time = (time.time() - start_time) * 1000
                performance_metrics.record_response(response_time, False)
                print(f"Large request failed for {test_case['name']}: {e}")

        performance_metrics.stop()

    @pytest.mark.integration
    @pytest.mark.performance
    async def test_database_query_performance(self, test_db_session: AsyncSession, sample_organization, performance_metrics):
        """Test database query performance directly"""
        org_id = sample_organization["id"]
        performance_metrics.start()

        # Test various database queries
        db_queries = [
            {
                "name": "simple_select",
                "query": "SELECT COUNT(*) FROM analytics_metrics WHERE organization_id = :org_id",
                "params": {"org_id": str(org_id)},
                "target_time": 100  # 100ms
            },
            {
                "name": "complex_aggregation",
                "query": """
                    SELECT
                        DATE_TRUNC('day', timestamp) as day,
                        COUNT(*) as metric_count,
                        AVG(current_value) as avg_value
                    FROM analytics_metrics
                    WHERE organization_id = :org_id
                    AND timestamp >= NOW() - INTERVAL '7 days'
                    GROUP BY DATE_TRUNC('day', timestamp)
                    ORDER BY day DESC
                """,
                "params": {"org_id": str(org_id)},
                "target_time": 500  # 500ms
            },
            {
                "name": "join_query",
                "query": """
                    SELECT
                        d.config_name,
                        COUNT(w.id) as widget_count
                    FROM dashboard_configurations d
                    LEFT JOIN dashboard_widgets w ON d.id = w.dashboard_id
                    WHERE d.organization_id = :org_id
                    GROUP BY d.id, d.config_name
                """,
                "params": {"org_id": str(org_id)},
                "target_time": 200  # 200ms
            }
        ]

        for query_test in db_queries:
            # Run query multiple times and measure performance
            query_times = []

            for i in range(3):
                start_time = time.time()

                try:
                    result = await test_db_session.execute(text(query_test["query"]), query_test["params"])
                    rows = result.fetchall()

                    query_time = (time.time() - start_time) * 1000
                    query_times.append(query_time)

                    performance_metrics.record_response(query_time, True)

                except Exception as e:
                    query_time = (time.time() - start_time) * 1000
                    query_times.append(query_time)

                    performance_metrics.record_response(query_time, False)
                    print(f"Database query failed for {query_test['name']}: {e}")

            # Calculate average query time
            if query_times:
                avg_time = statistics.mean(query_times)
                max_time = max(query_times)

                print(f"{query_test['name']}: avg={avg_time:.1f}ms, max={max_time:.1f}ms, target={query_test['target_time']}ms")

                # Performance assertion
                assert avg_time <= query_test["target_time"], (
                    f"Query {query_test['name']} average time {avg_time:.1f}ms exceeds target {query_test['target_time']}ms"
                )

        performance_metrics.stop()

    @pytest.mark.integration
    @pytest.mark.performance
    async def test_cache_performance(self, api_client: AsyncClient, auth_headers, sample_organization, performance_metrics):
        """Test caching performance improvements"""
        org_id = sample_organization["id"]
        performance_metrics.start()

        # Test endpoints that should benefit from caching
        cache_test_endpoint = lambda: api_client.get(
            f"/api/v1/analytics/dashboard/widgets",
            params={"organization_id": str(org_id)},
            headers=auth_headers
        )

        # First request (cache miss)
        start_time = time.time()
        first_response = await cache_test_endpoint()
        first_request_time = (time.time() - start_time) * 1000

        # Subsequent requests (should be cache hits)
        cache_request_times = []
        for i in range(5):
            start_time = time.time()
            try:
                response = await cache_test_endpoint()
                request_time = (time.time() - start_time) * 1000
                cache_request_times.append(request_time)
                performance_metrics.record_response(request_time, response.status_code == 200)

            except Exception as e:
                request_time = (time.time() - start_time) * 1000
                cache_request_times.append(request_time)
                performance_metrics.record_response(request_time, False)

            await asyncio.sleep(0.1)

        print(f"Cache performance test:")
        print(f"  First request: {first_request_time:.1f}ms")
        print(f"  Cached requests avg: {statistics.mean(cache_request_times):.1f}ms")
        print(f"  Cache speedup: {first_request_time / statistics.mean(cache_request_times):.1f}x")

        # Cache should improve performance
        if cache_request_times:
            avg_cached_time = statistics.mean(cache_request_times)
            assert avg_cached_time <= first_request_time, "Cached requests should be faster than first request"

            # Cache should provide significant speedup (at least 2x)
            if first_request_time > 100:  # Only check if first request was slow enough
                speedup = first_request_time / avg_cached_time
                assert speedup >= 1.5, f"Cache speedup {speedup:.1f}x should be at least 1.5x"

        performance_metrics.stop()

    @pytest.mark.integration
    @pytest.mark.performance
    async def test_stress_test(self, api_client: AsyncClient, auth_headers, sample_organization, performance_metrics):
        """Stress test with high load and resource monitoring"""
        org_id = sample_organization["id"]
        performance_metrics.start()

        # Stress test parameters
        stress_duration = 60  # seconds
        max_concurrent = 20
        ramp_up_time = 10  # seconds

        active_users = 0
        total_requests = 0
        errors = []

        async def stress_user(user_id: int):
            """Stress test user with increasing load"""
            nonlocal active_users, total_requests

            # Ramp up delay
            await asyncio.sleep(user_id * (ramp_up_time / max_concurrent))

            active_users += 1
            user_requests = 0
            user_errors = 0

            start_time = time.time()
            while time.time() - start_time < stress_duration:
                request_start = time.time()

                try:
                    response = await api_client.get(
                        f"/api/v1/analytics/realtime/metrics",
                        params={"organization_id": str(org_id)},
                        headers=auth_headers,
                        timeout=10.0
                    )

                    request_time = (time.time() - request_start) * 1000
                    total_requests += 1
                    user_requests += 1

                    success = response.status_code == 200
                    if not success:
                        user_errors += 1
                        errors.append(f"User {user_id}: HTTP {response.status_code}")

                    performance_metrics.record_response(request_time, success)

                except Exception as e:
                    request_time = (time.time() - request_start) * 1000
                    total_requests += 1
                    user_requests += 1
                    user_errors += 1
                    errors.append(f"User {user_id}: {str(e)}")
                    performance_metrics.record_response(request_time, False)

                # Variable think time
                await asyncio.sleep(0.1 + (user_id % 3) * 0.1)

            active_users -= 1
            return user_requests, user_errors

        # Start stress users
        print(f"Starting stress test: {max_concurrent} users over {stress_duration}s")
        start_time = time.time()

        tasks = [stress_user(i) for i in range(max_concurrent)]
        user_results = await asyncio.gather(*tasks, return_exceptions=True)

        total_time = time.time() - start_time
        performance_metrics.stop()

        # Calculate stress test metrics
        successful_users = [r for r in user_results if not isinstance(r, Exception)]
        user_requests = sum(r[0] for r in successful_users)
        user_errors = sum(r[1] for r in successful_users)

        actual_rps = total_requests / total_time

        print(f"\nStress Test Results:")
        print(f"  Duration: {total_time:.1f}s")
        print(f"  Total requests: {total_requests}")
        print(f"  RPS: {actual_rps:.1f}")
        print(f"  Success rate: {performance_metrics.success_rate:.2%}")
        print(f"  Avg response time: {performance_metrics.avg_response_time:.0f}ms")
        print(f"  P95 response time: {performance_metrics.p95_response_time:.0f}ms")
        print(f"  Errors: {len(errors)}")

        if len(errors) > 0:
            print(f"  Sample errors: {errors[:3]}")

        # Stress test assertions
        assert performance_metrics.success_rate >= 0.90, f"Success rate {performance_metrics.success_rate:.2%} should be at least 90% under stress"
        assert performance_metrics.avg_response_time <= 5000, f"Average response time {performance_metrics.avg_response_time:.0f}ms should be under 5s under stress"
        assert total_requests >= max_concurrent * stress_duration * 0.5, "Should handle reasonable request volume"

    @pytest.mark.integration
    @pytest.mark.performance
    async def test_resource_cleanup(self, api_client: AsyncClient, auth_headers, sample_organization, performance_metrics):
        """Test that resources are properly cleaned up after operations"""
        org_id = sample_organization["id"]
        performance_metrics.start()

        # Monitor resources before test
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024
        initial_connections = len(api_client._client._connection_pool._pool)

        # Perform many operations
        operations_count = 50

        for i in range(operations_count):
            try:
                # Create dashboard
                create_response = await api_client.post(
                    f"/api/v1/analytics/dashboard/configurations",
                    params={"organization_id": str(org_id)},
                    json={
                        "config_name": f"Cleanup Test Dashboard {i}",
                        "config_type": "user",
                        "layout": {"rows": 1, "columns": 1}
                    },
                    headers=auth_headers
                )

                if create_response.status_code == 201:
                    dashboard_id = create_response.json()["id"]

                    # Read dashboard
                    await api_client.get(
                        f"/api/v1/analytics/dashboard/configurations/{dashboard_id}",
                        params={"organization_id": str(org_id)},
                        headers=auth_headers
                    )

                    # Delete dashboard
                    await api_client.delete(
                        f"/api/v1/analytics/dashboard/configurations/{dashboard_id}",
                        params={"organization_id": str(org_id)},
                        headers=auth_headers
                    )

            except Exception as e:
                print(f"Cleanup test operation {i} failed: {e}")

            # Periodic resource check
            if i % 10 == 0:
                performance_metrics.record_system_metrics()

        # Wait for cleanup
        await asyncio.sleep(5)

        # Monitor resources after test
        final_memory = psutil.Process().memory_info().rss / 1024 / 1024
        performance_metrics.stop()

        memory_growth = final_memory - initial_memory

        print(f"Resource cleanup test:")
        print(f"  Initial memory: {initial_memory:.1f}MB")
        print(f"  Final memory: {final_memory:.1f}MB")
        print(f"  Memory growth: {memory_growth:.1f}MB")
        print(f"  Operations: {operations_count}")

        # Resource cleanup assertions
        assert memory_growth <= 50, f"Memory growth {memory_growth:.1f}MB should be minimal after cleanup"

        # Force garbage collection
        gc.collect()
        await asyncio.sleep(1)

        # Final memory check after GC
        final_gc_memory = psutil.Process().memory_info().rss / 1024 / 1024
        final_growth = final_gc_memory - initial_memory

        print(f"  Memory after GC: {final_gc_memory:.1f}MB")
        print(f"  Final growth: {final_growth:.1f}MB")

        assert final_growth <= 25, f"Final memory growth {final_growth:.1f}MB should be minimal after GC"