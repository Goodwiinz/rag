"""
Status Endpoints Performance Benchmarking

This module contains comprehensive performance benchmarks for status endpoints,
including response time analysis, throughput testing, and resource usage monitoring.
"""

import pytest
import asyncio
import json
import time
import psutil
import os
import statistics
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import threading
import requests
import httpx

from fastapi.testclient import TestClient
from httpx import AsyncClient

from backend.src.models.websocket_status import (
    WebSocketConnection,
    StatusUpdate,
    ConnectionEvent
)


@dataclass
class PerformanceMetrics:
    """Performance metrics collection"""
    endpoint: str
    method: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    p50_response_time: float
    p95_response_time: float
    p99_response_time: float
    requests_per_second: float
    data_transferred_mb: float
    cpu_usage_percent: float
    memory_usage_mb: float
    error_rate: float
    test_duration: float
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


@dataclass
class BenchmarkConfiguration:
    """Configuration for performance benchmarks"""
    endpoint_url: str
    method: str = "GET"
    concurrent_requests: int = 10
    total_requests: int = 1000
    ramp_up_time: float = 10.0
    test_duration: float = 60.0
    request_data: Dict[str, Any] = None
    headers: Dict[str, str] = None
    timeout: float = 30.0
    expected_status_code: int = 200

    # Performance thresholds
    max_avg_response_time: float = 1.0
    max_p95_response_time: float = 2.0
    max_p99_response_time: float = 5.0
    min_requests_per_second: float = 10.0
    max_error_rate: float = 0.01  # 1%
    max_memory_usage_mb: float = 100.0
    max_cpu_usage_percent: float = 80.0


class PerformanceBenchmarkRunner:
    """Runs performance benchmarks for API endpoints"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.process = psutil.Process(os.getpid())
        self.metrics_history: List[PerformanceMetrics] = []
        self.active_tests: Dict[str, threading.Thread] = {}

    async def run_benchmark(self, config: BenchmarkConfiguration) -> PerformanceMetrics:
        """Run a single performance benchmark"""
        print(f"Starting benchmark for {config.method} {config.endpoint_url}")
        print(f"Concurrent requests: {config.concurrent_requests}, Total requests: {config.total_requests}")

        start_time = time.time()
        initial_memory = self.process.memory_info().rss

        # Collect system metrics during test
        system_metrics = []
        metrics_thread = threading.Thread(
            target=self._collect_system_metrics,
            args=(system_metrics, config.test_duration),
            daemon=True
        )
        metrics_thread.start()

        # Execute benchmark
        response_times, data_sizes, errors = await self._execute_requests(config)

        # Stop metrics collection
        metrics_thread.join(timeout=1.0)

        # Calculate final metrics
        test_duration = time.time() - start_time
        final_memory = self.process.memory_info().rss

        # Calculate statistics
        successful_requests = len(response_times)
        failed_requests = len(errors)
        total_requests = successful_requests + failed_requests

        if response_times:
            response_times_sorted = sorted(response_times)
            metrics = PerformanceMetrics(
                endpoint=config.endpoint_url,
                method=config.method,
                total_requests=total_requests,
                successful_requests=successful_requests,
                failed_requests=failed_requests,
                avg_response_time=statistics.mean(response_times),
                min_response_time=min(response_times),
                max_response_time=max(response_times),
                p50_response_time=self._percentile(response_times_sorted, 50),
                p95_response_time=self._percentile(response_times_sorted, 95),
                p99_response_time=self._percentile(response_times_sorted, 99),
                requests_per_second=successful_requests / test_duration,
                data_transferred_mb=sum(data_sizes) / (1024 * 1024),
                cpu_usage_percent=statistics.mean([m["cpu"] for m in system_metrics]) if system_metrics else 0,
                memory_usage_mb=(final_memory - initial_memory) / (1024 * 1024),
                error_rate=failed_requests / total_requests if total_requests > 0 else 0,
                test_duration=test_duration,
                timestamp=datetime.utcnow()
            )
        else:
            metrics = PerformanceMetrics(
                endpoint=config.endpoint_url,
                method=config.method,
                total_requests=total_requests,
                successful_requests=0,
                failed_requests=failed_requests,
                avg_response_time=0,
                min_response_time=0,
                max_response_time=0,
                p50_response_time=0,
                p95_response_time=0,
                p99_response_time=0,
                requests_per_second=0,
                data_transferred_mb=0,
                cpu_usage_percent=0,
                memory_usage_mb=(final_memory - initial_memory) / (1024 * 1024),
                error_rate=1.0,
                test_duration=test_duration,
                timestamp=datetime.utcnow()
            )

        self.metrics_history.append(metrics)

        # Validate against thresholds
        self._validate_performance(metrics, config)

        print(f"Benchmark completed:")
        print(f"  Avg response time: {metrics.avg_response_time:.3f}s")
        print(f"  P95 response time: {metrics.p95_response_time:.3f}s")
        print(f"  Requests/sec: {metrics.requests_per_second:.2f}")
        print(f"  Error rate: {metrics.error_rate:.2%}")
        print(f"  Memory usage: {metrics.memory_usage_mb:.1f}MB")

        return metrics

    async def _execute_requests(self, config: BenchmarkConfiguration) -> Tuple[List[float], List[int], List[Dict]]:
        """Execute HTTP requests for benchmark"""
        response_times = []
        data_sizes = []
        errors = []

        # Create HTTP client
        timeout = httpx.Timeout(config.timeout)
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Calculate request distribution over time
            requests_per_second = config.concurrent_requests / config.ramp_up_time if config.ramp_up_time > 0 else config.concurrent_requests
            request_interval = 1.0 / requests_per_second if requests_per_second > 0 else 0

            # Execute requests
            semaphore = asyncio.Semaphore(config.concurrent_requests)

            async def make_request(request_id: int):
                async with semaphore:
                    try:
                        start_time = time.time()

                        # Make request
                        if config.method.upper() == "GET":
                            response = await client.get(
                                self.base_url + config.endpoint_url,
                                headers=config.headers
                            )
                        elif config.method.upper() == "POST":
                            response = await client.post(
                                self.base_url + config.endpoint_url,
                                json=config.request_data,
                                headers=config.headers
                            )
                        else:
                            raise ValueError(f"Unsupported method: {config.method}")

                        end_time = time.time()
                        response_time = end_time - start_time

                        # Check status code
                        if response.status_code == config.expected_status_code:
                            response_times.append(response_time)
                            data_sizes.append(len(response.content))
                        else:
                            errors.append({
                                "request_id": request_id,
                                "status_code": response.status_code,
                                "response": response.text[:500],
                                "response_time": response_time
                            })

                    except Exception as e:
                        errors.append({
                            "request_id": request_id,
                            "error": str(e),
                            "response_time": time.time() - start_time
                        })

            # Create tasks for all requests
            tasks = []
            for i in range(config.total_requests):
                task = asyncio.create_task(make_request(i))
                tasks.append(task)

                # Add delay for ramp-up
                if i > 0 and request_interval > 0:
                    await asyncio.sleep(request_interval)

            # Wait for all requests to complete
            await asyncio.gather(*tasks, return_exceptions=True)

        return response_times, data_sizes, errors

    def _collect_system_metrics(self, metrics_list: List[Dict], duration: float):
        """Collect system metrics during benchmark"""
        start_time = time.time()

        while time.time() - start_time < duration:
            try:
                cpu_percent = self.process.cpu_percent()
                memory_info = self.process.memory_info()
                memory_mb = memory_info.rss / (1024 * 1024)

                metrics_list.append({
                    "timestamp": time.time(),
                    "cpu": cpu_percent,
                    "memory_mb": memory_mb,
                    "threads": self.process.num_threads()
                })

                time.sleep(0.5)  # Collect every 500ms

            except Exception as e:
                print(f"Error collecting system metrics: {e}")
                break

    def _percentile(self, sorted_data: List[float], percentile: int) -> float:
        """Calculate percentile of sorted data"""
        if not sorted_data:
            return 0

        index = (percentile / 100) * (len(sorted_data) - 1)
        lower_index = int(index)
        upper_index = min(lower_index + 1, len(sorted_data) - 1)

        if lower_index == upper_index:
            return sorted_data[lower_index]

        # Linear interpolation
        weight = index - lower_index
        return sorted_data[lower_index] * (1 - weight) + sorted_data[upper_index] * weight

    def _validate_performance(self, metrics: PerformanceMetrics, config: BenchmarkConfiguration):
        """Validate performance against thresholds"""
        violations = []

        if metrics.avg_response_time > config.max_avg_response_time:
            violations.append(f"Average response time ({metrics.avg_response_time:.3f}s) exceeds threshold ({config.max_avg_response_time:.3f}s)")

        if metrics.p95_response_time > config.max_p95_response_time:
            violations.append(f"P95 response time ({metrics.p95_response_time:.3f}s) exceeds threshold ({config.max_p95_response_time:.3f}s)")

        if metrics.p99_response_time > config.max_p99_response_time:
            violations.append(f"P99 response time ({metrics.p99_response_time:.3f}s) exceeds threshold ({config.max_p99_response_time:.3f}s)")

        if metrics.requests_per_second < config.min_requests_per_second:
            violations.append(f"Requests/sec ({metrics.requests_per_second:.2f}) below threshold ({config.min_requests_per_second:.2f})")

        if metrics.error_rate > config.max_error_rate:
            violations.append(f"Error rate ({metrics.error_rate:.2%}) exceeds threshold ({config.max_error_rate:.2%})")

        if metrics.memory_usage_mb > config.max_memory_usage_mb:
            violations.append(f"Memory usage ({metrics.memory_usage_mb:.1f}MB) exceeds threshold ({config.max_memory_usage_mb:.1f}MB)")

        if metrics.cpu_usage_percent > config.max_cpu_usage_percent:
            violations.append(f"CPU usage ({metrics.cpu_usage_percent:.1f}%) exceeds threshold ({config.max_cpu_usage_percent:.1f}%)")

        if violations:
            print("Performance violations detected:")
            for violation in violations:
                print(f"  ❌ {violation}")
            raise AssertionError(f"Performance benchmark failed: {len(violations)} violations")

        print("✅ All performance thresholds met")

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get summary of all performance benchmarks"""
        if not self.metrics_history:
            return {"message": "No benchmarks run yet"}

        summary = {
            "total_benchmarks": len(self.metrics_history),
            "benchmarks": [metric.to_dict() for metric in self.metrics_history],
            "overall_stats": self._calculate_overall_stats()
        }

        return summary

    def _calculate_overall_stats(self) -> Dict[str, Any]:
        """Calculate overall statistics across all benchmarks"""
        if not self.metrics_history:
            return {}

        all_response_times = [m.avg_response_time for m in self.metrics_history if m.avg_response_time > 0]
        all_rps = [m.requests_per_second for m in self.metrics_history if m.requests_per_second > 0]
        all_errors = [m.error_rate for m in self.metrics_history]

        return {
            "avg_response_time": statistics.mean(all_response_times) if all_response_times else 0,
            "max_response_time": max(all_response_times) if all_response_times else 0,
            "avg_requests_per_second": statistics.mean(all_rps) if all_rps else 0,
            "max_requests_per_second": max(all_rps) if all_rps else 0,
            "overall_error_rate": statistics.mean(all_errors) if all_errors else 0,
            "total_requests": sum(m.total_requests for m in self.metrics_history),
            "total_successful_requests": sum(m.successful_requests for m in self.metrics_history)
        }


@pytest.mark.benchmark
@pytest.mark.performance
class TestStatusEndpointsBenchmark:
    """Performance benchmarks for status endpoints"""

    @pytest.fixture(autouse=True)
    def setup_benchmark_runner(self):
        """Setup benchmark runner"""
        self.runner = PerformanceBenchmarkRunner("http://localhost:8000")
        yield self.runner
        # Cleanup if needed

    @pytest.mark.asyncio
    async def test_system_health_endpoint_performance(self, test_client: TestClient, auth_headers):
        """Benchmark system health endpoint performance"""
        headers = auth_headers({"email": "benchmark@example.com", "first_name": "Benchmark", "last_name": "User"})

        config = BenchmarkConfiguration(
            endpoint_url="/api/v1/status/health",
            headers=headers,
            concurrent_requests=20,
            total_requests=500,
            ramp_up_time=5.0,
            test_duration=30.0,
            max_avg_response_time=0.5,
            max_p95_response_time=1.0,
            min_requests_per_second=15.0,
            max_error_rate=0.01
        )

        metrics = await self.runner.run_benchmark(config)

        # Validate basic performance expectations
        assert metrics.successful_requests > 0
        assert metrics.error_rate < 0.05  # Less than 5% error rate

    @pytest.mark.asyncio
    async def test_websocket_status_endpoint_performance(self, test_client: TestClient, auth_headers):
        """Benchmark WebSocket status endpoint performance"""
        headers = auth_headers({"email": "wsbenchmark@example.com", "first_name": "WS", "last_name": "Benchmark"})

        config = BenchmarkConfiguration(
            endpoint_url="/api/v1/status/websocket",
            headers=headers,
            concurrent_requests=15,
            total_requests=300,
            ramp_up_time=3.0,
            test_duration=20.0,
            max_avg_response_time=0.3,
            max_p95_response_time=0.8,
            min_requests_per_second=10.0,
            max_error_rate=0.01
        )

        metrics = await self.runner.run_benchmark(config)

        assert metrics.successful_requests > 0
        assert metrics.avg_response_time < 0.5

    @pytest.mark.asyncio
    async def test_detailed_websocket_status_performance(self, test_client: TestClient, auth_headers):
        """Benchmark detailed WebSocket status endpoint performance"""
        headers = auth_headers({"email": "detailbenchmark@example.com", "first_name": "Detail", "last_name": "Benchmark"})

        config = BenchmarkConfiguration(
            endpoint_url="/api/v1/status/websocket?detailed=true",
            headers=headers,
            concurrent_requests=10,
            total_requests=200,
            ramp_up_time=2.0,
            test_duration=15.0,
            max_avg_response_time=0.8,
            max_p95_response_time=1.5,
            min_requests_per_second=8.0,
            max_error_rate=0.02
        )

        metrics = await self.runner.run_benchmark(config)

        # Detailed endpoint might be slower, but should still be reasonable
        assert metrics.successful_requests > 0
        assert metrics.p95_response_time < 2.0

    @pytest.mark.asyncio
    async def test_database_status_endpoint_performance(self, test_client: TestClient, auth_headers):
        """Benchmark database status endpoint performance"""
        headers = auth_headers({"email": "dbbenchmark@example.com", "first_name": "Database", "last_name": "Benchmark"})

        config = BenchmarkConfiguration(
            endpoint_url="/api/v1/status/database",
            headers=headers,
            concurrent_requests=12,
            total_requests=250,
            ramp_up_time=4.0,
            test_duration=25.0,
            max_avg_response_time=0.6,
            max_p95_response_time=1.2,
            min_requests_per_second=8.0,
            max_error_rate=0.01
        )

        metrics = await self.runner.run_benchmark(config)

        assert metrics.successful_requests > 0
        assert metrics.error_rate < 0.05

    @pytest.mark.asyncio
    async def test_system_metrics_endpoint_performance(self, test_client: TestClient, auth_headers):
        """Benchmark system metrics endpoint performance"""
        headers = auth_headers({"email": "sysbenchmark@example.com", "first_name": "System", "last_name": "Benchmark"})

        config = BenchmarkConfiguration(
            endpoint_url="/api/v1/status/system/metrics",
            headers=headers,
            concurrent_requests=8,
            total_requests=150,
            ramp_up_time=3.0,
            test_duration=20.0,
            max_avg_response_time=1.0,
            max_p95_response_time=2.0,
            min_requests_per_second=5.0,
            max_error_rate=0.02
        )

        metrics = await self.runner.run_benchmark(config)

        # System metrics might be slower due to system calls
        assert metrics.successful_requests > 0
        assert metrics.avg_response_time < 1.5

    @pytest.mark.asyncio
    async def test_status_endpoint_load_scaling(self, test_client: TestClient, auth_headers):
        """Test performance scaling under different loads"""
        headers = auth_headers({"email": "scale@example.com", "first_name": "Scale", "last_name": "Test"})

        load_levels = [
            {"concurrent": 5, "total": 100, "name": "light"},
            {"concurrent": 15, "total": 300, "name": "medium"},
            {"concurrent": 30, "total": 600, "name": "heavy"}
        ]

        scaling_results = []

        for level in load_levels:
            print(f"Testing {level['name']} load: {level['concurrent']} concurrent, {level['total']} total")

            config = BenchmarkConfiguration(
                endpoint_url="/api/v1/status/health",
                headers=headers,
                concurrent_requests=level["concurrent"],
                total_requests=level["total"],
                ramp_up_time=min(10.0, level["concurrent"]),
                test_duration=30.0,
                max_avg_response_time=1.0,
                max_p95_response_time=2.0,
                min_requests_per_second=3.0,
                max_error_rate=0.05
            )

            metrics = await self.runner.run_benchmark(config)
            scaling_results.append({
                "level": level["name"],
                "metrics": metrics.to_dict()
            })

        # Analyze scaling behavior
        base_rps = scaling_results[0]["metrics"]["requests_per_second"]
        max_degradation = 0.5  # Allow 50% degradation at max load

        for result in scaling_results[1:]:
            current_rps = result["metrics"]["requests_per_second"]
            degradation = 1 - (current_rps / base_rps)
            assert degradation <= max_degradation, f"Performance degradation too high: {degradation:.2%}"

        print("✅ Load scaling test passed")
        for result in scaling_results:
            print(f"  {result['level']}: {result['metrics']['requests_per_second']:.2f} RPS")

    @pytest.mark.asyncio
    async def test_concurrent_endpoints_performance(self, test_client: TestClient, auth_headers):
        """Test performance with concurrent requests to multiple endpoints"""
        headers = auth_headers({"email": "concurrent@example.com", "first_name": "Concurrent", "last_name": "Test"})

        endpoints = [
            "/api/v1/status/health",
            "/api/v1/status/websocket",
            "/api/v1/status/database",
            "/api/v1/status/cache"
        ]

        # Run benchmarks concurrently
        async def run_endpoint_benchmark(endpoint):
            config = BenchmarkConfiguration(
                endpoint_url=endpoint,
                headers=headers,
                concurrent_requests=8,
                total_requests=100,
                ramp_up_time=2.0,
                test_duration=15.0,
                max_avg_response_time=1.0,
                max_p95_response_time=2.0,
                min_requests_per_second=5.0,
                max_error_rate=0.05
            )
            return await self.runner.run_benchmark(config)

        # Run all benchmarks concurrently
        tasks = [run_endpoint_benchmark(endpoint) for endpoint in endpoints]
        results = await asyncio.gather(*tasks)

        # Analyze concurrent performance
        total_successful = sum(r.successful_requests for r in results)
        total_requests = sum(r.total_requests for r in results)
        overall_error_rate = (total_requests - total_successful) / total_requests

        assert overall_error_rate < 0.1, f"Overall error rate too high: {overall_error_rate:.2%}"

        # All endpoints should have reasonable performance
        for result in results:
            assert result.avg_response_time < 2.0
            assert result.error_rate < 0.1

        print("✅ Concurrent endpoints test passed")
        for endpoint, result in zip(endpoints, results):
            print(f"  {endpoint}: {result.requests_per_second:.2f} RPS")

    @pytest.mark.asyncio
    async def test_status_endpoint_stress_test(self, test_client: TestClient, auth_headers):
        """Stress test status endpoints with high load"""
        headers = auth_headers({"email": "stress@example.com", "first_name": "Stress", "last_name": "Test"})

        # High load configuration
        config = BenchmarkConfiguration(
            endpoint_url="/api/v1/status/health",
            headers=headers,
            concurrent_requests=50,
            total_requests=2000,
            ramp_up_time=15.0,
            test_duration=60.0,
            max_avg_response_time=2.0,
            max_p95_response_time=5.0,
            min_requests_per_second=20.0,
            max_error_rate=0.05,  # Allow higher error rate under stress
            max_memory_usage_mb=200.0,
            max_cpu_usage_percent=90.0
        )

        metrics = await self.runner.run_benchmark(config)

        # Under stress, we allow more relaxed thresholds
        assert metrics.successful_requests > metrics.total_requests * 0.8  # At least 80% success
        assert metrics.avg_response_time < 3.0  # Still reasonable average response time

        print(f"✅ Stress test completed:")
        print(f"  Success rate: {metrics.successful_requests/metrics.total_requests:.2%}")
        print(f"  Avg response time: {metrics.avg_response_time:.3f}s")
        print(f"  Requests/sec: {metrics.requests_per_second:.2f}")
        print(f"  Peak memory: {metrics.memory_usage_mb:.1f}MB")


@pytest.mark.benchmark
@pytest.mark.regression
class TestStatusEndpointsRegression:
    """Regression tests for status endpoints performance"""

    @pytest.fixture(autouse=True)
    def setup_regression_runner(self):
        """Setup regression benchmark runner"""
        self.runner = PerformanceBenchmarkRunner("http://localhost:8000")
        yield self.runner

    @pytest.mark.asyncio
    async def test_regression_baseline_comparison(self, test_client: TestClient, auth_headers):
        """Compare current performance against baseline"""
        headers = auth_headers({"email": "regression@example.com", "first_name": "Regression", "last_name": "Test"})

        # Define baseline performance expectations
        baseline_expectations = {
            "/api/v1/status/health": {
                "max_avg_response_time": 0.3,
                "max_p95_response_time": 0.8,
                "min_requests_per_second": 25.0
            },
            "/api/v1/status/websocket": {
                "max_avg_response_time": 0.2,
                "max_p95_response_time": 0.6,
                "min_requests_per_second": 30.0
            },
            "/api/v1/status/database": {
                "max_avg_response_time": 0.4,
                "max_p95_response_time": 1.0,
                "min_requests_per_second": 20.0
            }
        }

        regression_results = []

        for endpoint, expectations in baseline_expectations.items():
            print(f"Testing {endpoint} against baseline...")

            config = BenchmarkConfiguration(
                endpoint_url=endpoint,
                headers=headers,
                concurrent_requests=20,
                total_requests=400,
                ramp_up_time=5.0,
                test_duration=20.0,
                **expectations
            )

            metrics = await self.runner.run_benchmark(config)

            # Compare against baseline
            regression_violations = []

            if metrics.avg_response_time > expectations["max_avg_response_time"]:
                regression_violations.append(
                    f"Avg response time ({metrics.avg_response_time:.3f}s) > baseline ({expectations['max_avg_response_time']:.3f}s)"
                )

            if metrics.p95_response_time > expectations["max_p95_response_time"]:
                regression_violations.append(
                    f"P95 response time ({metrics.p95_response_time:.3f}s) > baseline ({expectations['max_p95_response_time']:.3f}s)"
                )

            if metrics.requests_per_second < expectations["min_requests_per_second"]:
                regression_violations.append(
                    f"RPS ({metrics.requests_per_second:.2f}) < baseline ({expectations['min_requests_per_second']:.2f})"
                )

            regression_results.append({
                "endpoint": endpoint,
                "metrics": metrics.to_dict(),
                "violations": regression_violations,
                "passed": len(regression_violations) == 0
            })

        # Report regression results
        total_violations = sum(len(r["violations"]) for r in regression_results)
        passed_tests = sum(1 for r in regression_results if r["passed"])

        print(f"Regression test results:")
        print(f"  Passed: {passed_tests}/{len(regression_results)} endpoints")
        print(f"  Total violations: {total_violations}")

        if total_violations > 0:
            for result in regression_results:
                if result["violations"]:
                    print(f"  ❌ {result['endpoint']}:")
                    for violation in result["violations"]:
                        print(f"    {violation}")

            # Fail if there are regressions
            pytest.fail(f"Performance regression detected: {total_violations} violations")

        print("✅ No performance regressions detected")