"""
Performance testing automation for the Multimodal RAG System.
"""

import asyncio
import time
import json
import logging
import statistics
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import concurrent.futures
import aiohttp
import psutil
import threading
from contextlib import asynccontextmanager

from .config import config
from .metrics import record_histogram, increment_counter
from .logging import get_logger

logger = get_logger(__name__)


@dataclass
class PerformanceTestResult:
    """Performance test result data structure."""
    test_name: str
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    requests_per_second: float
    average_response_time: float
    min_response_time: float
    max_response_time: float
    p50_response_time: float
    p95_response_time: float
    p99_response_time: float
    error_rate: float
    status_code_distribution: Dict[str, int]
    errors: List[str]
    system_metrics: Dict[str, Any]
    custom_metrics: Dict[str, Any]


@dataclass
class LoadTestConfig:
    """Configuration for load testing."""
    name: str
    target_url: str
    method: str = "GET"
    headers: Optional[Dict[str, str]] = None
    body: Optional[str] = None
    concurrent_users: int = 10
    requests_per_second: int = 100
    test_duration_seconds: int = 60
    warmup_seconds: int = 10
    timeout_seconds: int = 30
    think_time_seconds: float = 0.1
    custom_metrics: Optional[List[str]] = None


class PerformanceTestRunner:
    """Advanced performance testing runner."""

    def __init__(self):
        self.results_history: List[PerformanceTestResult] = []
        self.active_tests: Dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    async def run_load_test(self, test_config: LoadTestConfig) -> PerformanceTestResult:
        """Run a comprehensive load test."""
        logger.info(f"Starting load test: {test_config.name}")
        start_time = datetime.utcnow()

        # Initialize metrics collection
        response_times = []
        status_codes = {}
        errors = []
        success_count = 0
        error_count = 0

        # Start system metrics monitoring
        system_monitor = SystemMetricsMonitor()
        system_monitor.start()

        try:
            # Warmup phase
            if test_config.warmup_seconds > 0:
                await self._warmup_phase(test_config)

            # Main test phase
            results = await self._execute_load_test(test_config, system_monitor)

            # Calculate final metrics
            end_time = datetime.utcnow()
            total_duration = (end_time - start_time).total_seconds()

            test_result = PerformanceTestResult(
                test_name=test_config.name,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=total_duration,
                total_requests=results['total_requests'],
                successful_requests=results['successful_requests'],
                failed_requests=results['failed_requests'],
                requests_per_second=results['requests_per_second'],
                average_response_time=statistics.mean(results['response_times']) if results['response_times'] else 0,
                min_response_time=min(results['response_times']) if results['response_times'] else 0,
                max_response_time=max(results['response_times']) if results['response_times'] else 0,
                p50_response_time=self._percentile(results['response_times'], 50),
                p95_response_time=self._percentile(results['response_times'], 95),
                p99_response_time=self._percentile(results['response_times'], 99),
                error_rate=results['error_rate'],
                status_code_distribution=results['status_codes'],
                errors=results['errors'],
                system_metrics=system_monitor.get_metrics(),
                custom_metrics=results.get('custom_metrics', {})
            )

            # Store result
            with self._lock:
                self.results_history.append(test_result)

            # Record metrics to monitoring system
            self._record_test_metrics(test_result)

            logger.info(f"Load test completed: {test_config.name}")
            return test_result

        finally:
            system_monitor.stop()

    async def _warmup_phase(self, test_config: LoadTestConfig):
        """Execute warmup phase to stabilize system."""
        logger.info(f"Warming up for {test_config.warmup_seconds} seconds")

        warmup_requests = min(50, test_config.concurrent_users * 2)
        warmup_tasks = [
            self._make_request(test_config, is_warmup=True)
            for _ in range(warmup_requests)
        ]

        await asyncio.gather(*warmup_tasks, return_exceptions=True)
        await asyncio.sleep(test_config.warmup_seconds)

    async def _execute_load_test(
        self,
        test_config: LoadTestConfig,
        system_monitor: 'SystemMetricsMonitor'
    ) -> Dict[str, Any]:
        """Execute the main load test."""
        response_times = []
        status_codes = {}
        errors = []
        successful_requests = 0
        failed_requests = 0
        custom_metrics = {}

        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(test_config.concurrent_users)

        async def make_tracked_request():
            async with semaphore:
                result = await self._make_request(test_config)
                if result['success']:
                    response_times.append(result['response_time'])
                    successful_requests += 1
                else:
                    failed_requests += 1
                    errors.append(result.get('error', 'Unknown error'))

                status_code = str(result.get('status_code', 'unknown'))
                status_codes[status_code] = status_codes.get(status_code, 0) + 1

                return result

        # Calculate requests per user
        total_requests = test_config.requests_per_second * test_config.test_duration_seconds
        requests_per_user = total_requests // test_config.concurrent_users

        # Create task schedule
        start_time = time.time()
        tasks = []

        for user_id in range(test_config.concurrent_users):
            for request_id in range(requests_per_user):
                # Calculate delay to maintain RPS
                delay = (request_id / test_config.requests_per_second) + (user_id * 0.01)
                if delay < test_config.test_duration_seconds:
                    task = asyncio.create_task(
                        self._delayed_request(delay, make_tracked_request)
                    )
                    tasks.append(task)

        # Execute all tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Calculate final metrics
        total_requests = successful_requests + failed_requests
        actual_duration = time.time() - start_time
        rps = total_requests / actual_duration if actual_duration > 0 else 0
        error_rate = failed_requests / total_requests if total_requests > 0 else 0

        return {
            'total_requests': total_requests,
            'successful_requests': successful_requests,
            'failed_requests': failed_requests,
            'requests_per_second': rps,
            'response_times': response_times,
            'status_codes': status_codes,
            'errors': errors,
            'error_rate': error_rate,
            'custom_metrics': custom_metrics
        }

    async def _delayed_request(self, delay: float, request_func: Callable):
        """Execute request with specified delay."""
        await asyncio.sleep(delay)
        return await request_func()

    async def _make_request(
        self,
        test_config: LoadTestConfig,
        is_warmup: bool = False
    ) -> Dict[str, Any]:
        """Make a single HTTP request."""
        start_time = time.time()

        try:
            timeout = aiohttp.ClientTimeout(total=test_config.timeout_seconds)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(
                    method=test_config.method,
                    url=test_config.target_url,
                    headers=test_config.headers,
                    data=test_config.body
                ) as response:
                    content = await response.text()
                    response_time = time.time() - start_time

                    return {
                        'success': True,
                        'status_code': response.status,
                        'response_time': response_time,
                        'content_length': len(content),
                        'is_warmup': is_warmup
                    }

        except Exception as e:
            response_time = time.time() - start_time
            return {
                'success': False,
                'response_time': response_time,
                'error': str(e),
                'is_warmup': is_warmup
            }

    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of response times."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]

    def _record_test_metrics(self, result: PerformanceTestResult):
        """Record test metrics to monitoring system."""
        # Record RPS
        record_histogram(
            "performance_test_rps",
            result.requests_per_second,
            {"test_name": result.test_name}
        )

        # Record response times
        record_histogram(
            "performance_test_response_time_avg",
            result.average_response_time,
            {"test_name": result.test_name}
        )

        record_histogram(
            "performance_test_response_time_p95",
            result.p95_response_time,
            {"test_name": result.test_name}
        )

        record_histogram(
            "performance_test_response_time_p99",
            result.p99_response_time,
            {"test_name": result.test_name}
        )

        # Record error rate
        record_histogram(
            "performance_test_error_rate",
            result.error_rate,
            {"test_name": result.test_name}
        )

        # Increment test counters
        increment_counter(
            "performance_test_total",
            result.total_requests,
            {"test_name": result.test_name}
        )

        increment_counter(
            "performance_test_successful",
            result.successful_requests,
            {"test_name": result.test_name}
        )

        increment_counter(
            "performance_test_failed",
            result.failed_requests,
            {"test_name": result.test_name}
        )

    async def run_stress_test(self, base_config: LoadTestConfig) -> List[PerformanceTestResult]:
        """Run a progressive stress test."""
        logger.info(f"Starting stress test: {base_config.name}")

        # Start with low load and gradually increase
        stress_results = []
        max_users = min(500, base_config.concurrent_users * 10)
        user_step = max(10, base_config.concurrent_users // 2)

        for users in range(user_step, max_users + 1, user_step):
            # Create stress test configuration
            stress_config = LoadTestConfig(
                name=f"{base_config.name}_stress_{users}users",
                target_url=base_config.target_url,
                method=base_config.method,
                headers=base_config.headers,
                body=base_config.body,
                concurrent_users=users,
                requests_per_second=min(users * 10, 1000),
                test_duration_seconds=30,  # Shorter duration for stress test
                warmup_seconds=5,
                timeout_seconds=base_config.timeout_seconds
            )

            try:
                result = await self.run_load_test(stress_config)
                stress_results.append(result)

                # Stop if error rate is too high
                if result.error_rate > 0.1:  # 10% error rate threshold
                    logger.warning(f"Stopping stress test due to high error rate: {result.error_rate:.2%}")
                    break

            except Exception as e:
                logger.error(f"Stress test failed at {users} users: {e}")
                break

        return stress_results

    async def run_endurance_test(self, test_config: LoadTestConfig) -> PerformanceTestResult:
        """Run a long-duration endurance test."""
        logger.info(f"Starting endurance test: {test_config.name}")

        endurance_config = LoadTestConfig(
            name=f"{test_config.name}_endurance",
            target_url=test_config.target_url,
            method=test_config.method,
            headers=test_config.headers,
            body=test_config.body,
            concurrent_users=test_config.concurrent_users // 2,  # Lower load for endurance
            requests_per_second=test_config.requests_per_second // 2,
            test_duration_seconds=3600,  # 1 hour
            warmup_seconds=30,
            timeout_seconds=test_config.timeout_seconds
        )

        return await self.run_load_test(endurance_config)

    def get_test_results(self, test_name: Optional[str] = None) -> List[PerformanceTestResult]:
        """Get test results filtered by name."""
        with self._lock:
            if test_name:
                return [r for r in self.results_history if r.test_name == test_name]
            return self.results_history.copy()

    def generate_performance_report(self, test_results: List[PerformanceTestResult]) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        if not test_results:
            return {"error": "No test results available"}

        # Aggregate metrics across all tests
        total_requests = sum(r.total_requests for r in test_results)
        total_successful = sum(r.successful_requests for r in test_results)
        total_failed = sum(r.failed_requests for r in test_results)

        avg_rps = statistics.mean([r.requests_per_second for r in test_results])
        avg_response_time = statistics.mean([r.average_response_time for r in test_results])
        avg_p95_response_time = statistics.mean([r.p95_response_time for r in test_results])
        avg_error_rate = statistics.mean([r.error_rate for r in test_results])

        # Find best and worst performing tests
        best_rps = max(test_results, key=lambda r: r.requests_per_second)
        best_response_time = min(test_results, key=lambda r: r.p95_response_time)
        worst_error_rate = max(test_results, key=lambda r: r.error_rate)

        return {
            "summary": {
                "test_count": len(test_results),
                "total_requests": total_requests,
                "total_successful": total_successful,
                "total_failed": total_failed,
                "overall_success_rate": (total_successful / total_requests * 100) if total_requests > 0 else 0
            },
            "performance_metrics": {
                "average_rps": avg_rps,
                "average_response_time": avg_response_time,
                "average_p95_response_time": avg_p95_response_time,
                "average_error_rate": avg_error_rate
            },
            "best_performance": {
                "highest_rps": {
                    "test_name": best_rps.test_name,
                    "rps": best_rps.requests_per_second
                },
                "fastest_response": {
                    "test_name": best_response_time.test_name,
                    "p95_response_time": best_response_time.p95_response_time
                }
            },
            "worst_performance": {
                "highest_error_rate": {
                    "test_name": worst_error_rate.test_name,
                    "error_rate": worst_error_rate.error_rate
                }
            },
            "detailed_results": [asdict(result) for result in test_results]
        }


class SystemMetricsMonitor:
    """Monitor system metrics during performance tests."""

    def __init__(self):
        self.monitoring = False
        self.metrics = {
            'cpu_percent': [],
            'memory_percent': [],
            'memory_used_mb': [],
            'disk_usage_percent': [],
            'network_io': [],
            'timestamps': []
        }
        self._process = psutil.Process()
        self._thread = None

    def start(self):
        """Start monitoring system metrics."""
        self.monitoring = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop monitoring system metrics."""
        self.monitoring = False
        if self._thread:
            self._thread.join(timeout=5)

    def _monitor_loop(self):
        """Main monitoring loop."""
        while self.monitoring:
            try:
                timestamp = time.time()
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                network = psutil.net_io_counters()

                self.metrics['cpu_percent'].append(cpu_percent)
                self.metrics['memory_percent'].append(memory.percent)
                self.metrics['memory_used_mb'].append(memory.used / 1024 / 1024)
                self.metrics['disk_usage_percent'].append(disk.percent)
                self.metrics['network_io'].append({
                    'bytes_sent': network.bytes_sent,
                    'bytes_recv': network.bytes_recv
                })
                self.metrics['timestamps'].append(timestamp)

            except Exception as e:
                logger.error(f"Error monitoring system metrics: {e}")

    def get_metrics(self) -> Dict[str, Any]:
        """Get collected system metrics."""
        if not self.metrics['cpu_percent']:
            return {}

        return {
            'cpu': {
                'average': statistics.mean(self.metrics['cpu_percent']),
                'max': max(self.metrics['cpu_percent']),
                'min': min(self.metrics['cpu_percent'])
            },
            'memory': {
                'average_percent': statistics.mean(self.metrics['memory_percent']),
                'max_percent': max(self.metrics['memory_percent']),
                'average_used_mb': statistics.mean(self.metrics['memory_used_mb']),
                'max_used_mb': max(self.metrics['memory_used_mb'])
            },
            'disk': {
                'average_usage_percent': statistics.mean(self.metrics['disk_usage_percent']),
                'max_usage_percent': max(self.metrics['disk_usage_percent'])
            },
            'network': {
                'total_bytes_sent': self.metrics['network_io'][-1]['bytes_sent'] if self.metrics['network_io'] else 0,
                'total_bytes_recv': self.metrics['network_io'][-1]['bytes_recv'] if self.metrics['network_io'] else 0
            },
            'duration': {
                'start': self.metrics['timestamps'][0] if self.metrics['timestamps'] else None,
                'end': self.metrics['timestamps'][-1] if self.metrics['timestamps'] else None,
                'total_seconds': self.metrics['timestamps'][-1] - self.metrics['timestamps'][0] if len(self.metrics['timestamps']) > 1 else 0
            }
        }


class RAGPerformanceTestSuite:
    """Specialized performance test suite for RAG operations."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.runner = PerformanceTestRunner()

    async def test_search_performance(self, query: str, concurrent_users: int = 50) -> PerformanceTestResult:
        """Test search/query performance."""
        config = LoadTestConfig(
            name="rag_search_test",
            target_url=f"{self.base_url}/api/search",
            method="POST",
            headers={"Content-Type": "application/json"},
            body=json.dumps({"query": query, "top_k": 10}),
            concurrent_users=concurrent_users,
            requests_per_second=concurrent_users * 2,
            test_duration_seconds=60,
            warmup_seconds=10
        )

        return await self.runner.run_load_test(config)

    async def test_document_ingestion(self, file_size_mb: int = 1, concurrent_uploads: int = 10) -> PerformanceTestResult:
        """Test document ingestion performance."""
        # Create test document
        test_content = "x" * (file_size_mb * 1024 * 1024)

        config = LoadTestConfig(
            name="rag_document_ingestion_test",
            target_url=f"{self.base_url}/api/documents/upload",
            method="POST",
            headers={"Content-Type": "multipart/form-data"},
            concurrent_users=concurrent_uploads,
            requests_per_second=concurrent_uploads,
            test_duration_seconds=120,
            warmup_seconds=15
        )

        return await self.runner.run_load_test(config)

    async def test_rag_quality_performance(self, queries: List[str]) -> PerformanceTestResult:
        """Test RAG pipeline performance with quality metrics."""
        config = LoadTestConfig(
            name="rag_quality_test",
            target_url=f"{self.base_url}/api/rag/query",
            method="POST",
            headers={"Content-Type": "application/json"},
            concurrent_users=20,
            requests_per_second=40,
            test_duration_seconds=180,
            warmup_seconds=20
        )

        # Test with multiple queries
        results = []
        for query in queries[:5]:  # Limit to 5 queries for performance test
            config.body = json.dumps({"query": query, "include_quality": True})
            result = await self.runner.run_load_test(config)
            results.append(result)

        # Return aggregated result
        if results:
            return PerformanceTestResult(
                test_name="rag_quality_test_aggregated",
                start_time=min(r.start_time for r in results),
                end_time=max(r.end_time for r in results),
                duration_seconds=sum(r.duration_seconds for r in results),
                total_requests=sum(r.total_requests for r in results),
                successful_requests=sum(r.successful_requests for r in results),
                failed_requests=sum(r.failed_requests for r in results),
                requests_per_second=statistics.mean([r.requests_per_second for r in results]),
                average_response_time=statistics.mean([r.average_response_time for r in results]),
                min_response_time=min(r.min_response_time for r in results),
                max_response_time=max(r.max_response_time for r in results),
                p50_response_time=statistics.mean([r.p50_response_time for r in results]),
                p95_response_time=statistics.mean([r.p95_response_time for r in results]),
                p99_response_time=statistics.mean([r.p99_response_time for r in results]),
                error_rate=statistics.mean([r.error_rate for r in results]),
                status_code_distribution={},
                errors=[],
                system_metrics={},
                custom_metrics={}
            )

        return PerformanceTestResult(
            test_name="rag_quality_test_empty",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            duration_seconds=0,
            total_requests=0,
            successful_requests=0,
            failed_requests=0,
            requests_per_second=0,
            average_response_time=0,
            min_response_time=0,
            max_response_time=0,
            p50_response_time=0,
            p95_response_time=0,
            p99_response_time=0,
            error_rate=0,
            status_code_distribution={},
            errors=[],
            system_metrics={},
            custom_metrics={}
        )


# Global performance test runner
test_runner = PerformanceTestRunner()