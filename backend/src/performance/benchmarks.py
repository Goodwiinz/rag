"""
Comprehensive performance benchmarks and validation tests
Automated load testing, performance regression detection, and SLA validation
"""

import asyncio
import time
import json
import statistics
import psutil
import aiohttp
import websockets
from datetime import datetime, timezone as dt_timezone, timedelta
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict
import numpy as np
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import uuid

logger = logging.getLogger(__name__)

class BenchmarkStatus(Enum):
    """Benchmark execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TestType(Enum):
    """Types of performance tests"""
    LOAD_TEST = "load_test"
    STRESS_TEST = "stress_test"
    SPIKE_TEST = "spike_test"
    ENDURANCE_TEST = "endurance_test"
    LATENCY_TEST = "latency_test"
    THROUGHPUT_TEST = "throughput_test"

@dataclass
class BenchmarkConfig:
    """Configuration for performance benchmarks"""
    name: str
    test_type: TestType
    target_endpoint: str
    concurrent_users: int = 10
    duration_seconds: int = 60
    ramp_up_seconds: int = 10
    requests_per_second: int = 100
    timeout_seconds: int = 30
    think_time_ms: int = 100
    success_criteria: Dict[str, float] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    payload: Dict[str, Any] = field(default_factory=dict)
    websocket_test: bool = False
    enable_monitoring: bool = True

@dataclass
class BenchmarkResult:
    """Results of a performance benchmark"""
    config: BenchmarkConfig
    status: BenchmarkStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    response_times: List[float] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    system_metrics: Dict[str, Any] = field(default_factory=dict)
    success: bool = False

    def __post_init__(self):
        if self.config.success_criteria is None:
            self.config.success_criteria = {}

    @property
    def duration_seconds(self) -> float:
        """Get total duration in seconds"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return (datetime.utcnow() - self.start_time).total_seconds()

    @property
    def requests_per_second(self) -> float:
        """Calculate requests per second"""
        duration = self.duration_seconds
        return self.total_requests / max(0.1, duration)

    @property
    def success_rate_percent(self) -> float:
        """Calculate success rate percentage"""
        if self.total_requests == 0:
            return 0
        return (self.successful_requests / self.total_requests) * 100

    @property
    def avg_response_time_ms(self) -> float:
        """Calculate average response time in milliseconds"""
        if not self.response_times:
            return 0
        return statistics.mean(self.response_times)

    @property
    def p95_response_time_ms(self) -> float:
        """Calculate 95th percentile response time"""
        if not self.response_times:
            return 0
        return np.percentile(self.response_times, 95)

    @property
    def p99_response_time_ms(self) -> float:
        """Calculate 99th percentile response time"""
        if not self.response_times:
            return 0
        return np.percentile(self.response_times, 99)

    def meets_success_criteria(self) -> bool:
        """Check if benchmark meets success criteria"""
        criteria = self.config.success_criteria

        # Check response time criteria
        if 'max_avg_response_time_ms' in criteria:
            if self.avg_response_time_ms > criteria['max_avg_response_time_ms']:
                return False

        if 'max_p95_response_time_ms' in criteria:
            if self.p95_response_time_ms > criteria['max_p95_response_time_ms']:
                return False

        # Check success rate criteria
        if 'min_success_rate_percent' in criteria:
            if self.success_rate_percent < criteria['min_success_rate_percent']:
                return False

        # Check throughput criteria
        if 'min_requests_per_second' in criteria:
            if self.requests_per_second < criteria['min_requests_per_second']:
                return False

        return True

class PerformanceBenchmark:
    """Executes performance benchmarks and validates results"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
        self.results: List[BenchmarkResult] = []
        self.monitoring_data: Dict[str, Any] = {}

    async def initialize(self):
        """Initialize benchmark environment"""
        # Create HTTP session with optimized settings
        timeout = aiohttp.ClientTimeout(total=60, connect=10)
        connector = aiohttp.TCPConnector(
            limit=1000,  # Total connection pool size
            limit_per_host=500,  # Per-host connection limit
            ttl_dns_cache=300,  # DNS cache TTL
            use_dns_cache=True,
        )

        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={
                'User-Agent': 'RAG-Performance-Benchmark/1.0',
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            }
        )

        logger.info("Performance benchmark initialized")

    async def cleanup(self):
        """Clean up benchmark environment"""
        if self.session:
            await self.session.close()

    async def run_benchmark(self, config: BenchmarkConfig) -> BenchmarkResult:
        """Run a single benchmark with the given configuration"""
        result = BenchmarkResult(
            config=config,
            status=BenchmarkStatus.RUNNING,
            start_time=datetime.utcnow()
        )

        try:
            logger.info(f"Starting benchmark: {config.name}")

            if config.websocket_test:
                await self._run_websocket_benchmark(result)
            else:
                await self._run_http_benchmark(result)

            result.status = BenchmarkStatus.COMPLETED
            result.success = result.meets_success_criteria()

            logger.info(f"Benchmark completed: {config.name} - Success: {result.success}")

        except Exception as e:
            result.status = BenchmarkStatus.FAILED
            result.errors.append(str(e))
            logger.error(f"Benchmark failed: {config.name} - Error: {e}")

        finally:
            result.end_time = datetime.utcnow()
            self.results.append(result)

        return result

    async def _run_http_benchmark(self, result: BenchmarkResult):
        """Run HTTP-based benchmark"""
        config = result.config

        # Create tasks for concurrent users
        tasks = []
        for user_id in range(config.concurrent_users):
            task = asyncio.create_task(
                self._simulate_user(result, user_id)
            )
            tasks.append(task)

        # Add monitoring task if enabled
        if config.enable_monitoring:
            monitor_task = asyncio.create_task(
                self._monitor_system_resources(result)
            )
            tasks.append(monitor_task)

        try:
            # Wait for all tasks to complete or timeout
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=config.duration_seconds + config.ramp_up_seconds + 30
            )
        except asyncio.TimeoutError:
            logger.warning(f"Benchmark {config.name} timed out")
            for task in tasks:
                task.cancel()

    async def _simulate_user(self, result: BenchmarkResult, user_id: int):
        """Simulate a single user's behavior"""
        config = result.config
        start_time = time.time()
        end_time = start_time + config.duration_seconds

        # Ramp-up delay
        ramp_delay = (config.ramp_up_seconds / config.concurrent_users) * user_id
        await asyncio.sleep(ramp_delay)

        while time.time() < end_time:
            try:
                request_start = time.time()

                # Make HTTP request
                async with self.session.request(
                    'GET' if not config.payload else 'POST',
                    config.target_endpoint,
                    headers=config.headers,
                    json=config.payload if config.payload else None
                ) as response:

                    content = await response.read()
                    request_time = (time.time() - request_start) * 1000

                    # Record metrics
                    result.total_requests += 1
                    result.response_times.append(request_time)

                    if response.status < 400:
                        result.successful_requests += 1
                    else:
                        result.failed_requests += 1
                        result.errors.append(f"HTTP {response.status}: {response.reason}")

                # Think time between requests
                await asyncio.sleep(config.think_time_ms / 1000)

            except asyncio.CancelledError:
                break
            except Exception as e:
                result.total_requests += 1
                result.failed_requests += 1
                result.errors.append(str(e))
                logger.error(f"User {user_id} request failed: {e}")

    async def _run_websocket_benchmark(self, result: BenchmarkResult):
        """Run WebSocket-based benchmark"""
        config = result.config
        ws_url = config.target_endpoint.replace('http://', 'ws://').replace('https://', 'wss://')

        tasks = []
        for user_id in range(config.concurrent_users):
            task = asyncio.create_task(
                self._simulate_websocket_user(result, user_id, ws_url)
            )
            tasks.append(task)

        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=config.duration_seconds + config.ramp_up_seconds + 30
            )
        except asyncio.TimeoutError:
            logger.warning(f"WebSocket benchmark {config.name} timed out")
            for task in tasks:
                task.cancel()

    async def _simulate_websocket_user(self, result: BenchmarkResult, user_id: int, ws_url: str):
        """Simulate a WebSocket user"""
        config = result.config
        start_time = time.time()
        end_time = start_time + config.duration_seconds

        # Ramp-up delay
        ramp_delay = (config.ramp_up_seconds / config.concurrent_users) * user_id
        await asyncio.sleep(ramp_delay)

        try:
            async with websockets.connect(ws_url) as websocket:
                # Send initial message
                await websocket.send(json.dumps({
                    'type': 'subscribe',
                    'channel': 'performance_test',
                    'user_id': user_id
                }))

                message_count = 0
                while time.time() < end_time:
                    try:
                        # Receive message
                        receive_start = time.time()
                        message = await asyncio.wait_for(
                            websocket.recv(),
                            timeout=config.timeout_seconds
                        )
                        receive_time = (time.time() - receive_start) * 1000

                        result.total_requests += 1
                        result.response_times.append(receive_time)
                        result.successful_requests += 1
                        message_count += 1

                        # Send acknowledgment every 10 messages
                        if message_count % 10 == 0:
                            send_start = time.time()
                            await websocket.send(json.dumps({
                                'type': 'ack',
                                'message_id': str(uuid.uuid4()),
                                'user_id': user_id
                            }))
                            send_time = (time.time() - send_start) * 1000

                        await asyncio.sleep(config.think_time_ms / 1000)

                    except asyncio.TimeoutError:
                        result.total_requests += 1
                        result.failed_requests += 1
                        result.errors.append("WebSocket receive timeout")
                    except Exception as e:
                        result.total_requests += 1
                        result.failed_requests += 1
                        result.errors.append(f"WebSocket error: {e}")

        except Exception as e:
            logger.error(f"WebSocket user {user_id} failed: {e}")
            result.errors.append(f"WebSocket connection failed: {e}")

    async def _monitor_system_resources(self, result: BenchmarkResult):
        """Monitor system resources during benchmark"""
        config = result.config
        start_time = time.time()
        end_time = start_time + config.duration_seconds + config.ramp_up_seconds

        monitoring_interval = 1.0  # seconds
        resource_metrics = {
            'cpu_percent': [],
            'memory_percent': [],
            'memory_usage_mb': [],
            'network_io': [],
            'timestamps': []
        }

        initial_network = psutil.net_io_counters()

        while time.time() < end_time:
            try:
                timestamp = datetime.utcnow()
                cpu = psutil.cpu_percent()
                memory = psutil.virtual_memory()
                network = psutil.net_io_counters()

                resource_metrics['cpu_percent'].append(cpu)
                resource_metrics['memory_percent'].append(memory.percent)
                resource_metrics['memory_usage_mb'].append(memory.used / (1024 * 1024))
                resource_metrics['network_io'].append({
                    'bytes_sent': network.bytes_sent - initial_network.bytes_sent,
                    'bytes_recv': network.bytes_recv - initial_network.bytes_recv,
                    'packets_sent': network.packets_sent - initial_network.packets_sent,
                    'packets_recv': network.packets_recv - initial_network.packets_recv,
                })
                resource_metrics['timestamps'].append(timestamp)

                await asyncio.sleep(monitoring_interval)

            except Exception as e:
                logger.error(f"System monitoring error: {e}")
                await asyncio.sleep(monitoring_interval)

        result.system_metrics = {
            'max_cpu_percent': max(resource_metrics['cpu_percent']) if resource_metrics['cpu_percent'] else 0,
            'avg_cpu_percent': statistics.mean(resource_metrics['cpu_percent']) if resource_metrics['cpu_percent'] else 0,
            'max_memory_percent': max(resource_metrics['memory_percent']) if resource_metrics['memory_percent'] else 0,
            'avg_memory_percent': statistics.mean(resource_metrics['memory_percent']) if resource_metrics['memory_percent'] else 0,
            'max_memory_mb': max(resource_metrics['memory_usage_mb']) if resource_metrics['memory_usage_mb'] else 0,
            'avg_memory_mb': statistics.mean(resource_metrics['memory_usage_mb']) if resource_metrics['memory_usage_mb'] else 0,
            'total_samples': len(resource_metrics['timestamps']),
        }

    def get_results_summary(self) -> Dict[str, Any]:
        """Get summary of all benchmark results"""
        if not self.results:
            return {'message': 'No benchmarks run yet'}

        summary = {
            'total_benchmarks': len(self.results),
            'successful_benchmarks': sum(1 for r in self.results if r.success),
            'failed_benchmarks': sum(1 for r in self.results if r.status == BenchmarkStatus.FAILED),
            'benchmarks': []
        }

        for result in self.results:
            summary['benchmarks'].append({
                'name': result.config.name,
                'type': result.config.test_type.value,
                'status': result.status.value,
                'success': result.success,
                'duration_seconds': result.duration_seconds,
                'total_requests': result.total_requests,
                'requests_per_second': result.requests_per_second,
                'success_rate_percent': result.success_rate_percent,
                'avg_response_time_ms': result.avg_response_time_ms,
                'p95_response_time_ms': result.p95_response_time_ms,
                'p99_response_time_ms': result.p99_response_time_ms,
                'errors_count': len(result.errors),
                'system_metrics': result.system_metrics
            })

        return summary

class PerformanceRegressionDetector:
    """Detects performance regressions by comparing benchmark results"""

    def __init__(self):
        self.baseline_results: Dict[str, BenchmarkResult] = {}
        self.regression_threshold_percent = 20.0  # 20% degradation threshold

    def set_baseline(self, test_name: str, result: BenchmarkResult):
        """Set baseline result for comparison"""
        self.baseline_results[test_name] = result
        logger.info(f"Baseline set for test: {test_name}")

    def detect_regression(self, test_name: str, current_result: BenchmarkResult) -> Dict[str, Any]:
        """Detect performance regression compared to baseline"""
        if test_name not in self.baseline_results:
            return {
                'regression_detected': False,
                'message': 'No baseline available for comparison'
            }

        baseline = self.baseline_results[test_name]
        regressions = []

        # Check response time regression
        baseline_avg = baseline.avg_response_time_ms
        current_avg = current_result.avg_response_time_ms

        if baseline_avg > 0:
            avg_change = ((current_avg - baseline_avg) / baseline_avg) * 100
            if avg_change > self.regression_threshold_percent:
                regressions.append({
                    'metric': 'avg_response_time_ms',
                    'baseline': baseline_avg,
                    'current': current_avg,
                    'change_percent': avg_change
                })

        # Check success rate regression
        baseline_success = baseline.success_rate_percent
        current_success = current_result.success_rate_percent

        success_change = baseline_success - current_success
        if success_change > self.regression_threshold_percent:
            regressions.append({
                'metric': 'success_rate_percent',
                'baseline': baseline_success,
                'current': current_success,
                'change_percent': -success_change  # Positive for regression
            })

        # Check throughput regression
        baseline_rps = baseline.requests_per_second
        current_rps = current_result.requests_per_second

        if baseline_rps > 0:
            rps_change = ((baseline_rps - current_rps) / baseline_rps) * 100
            if rps_change > self.regression_threshold_percent:
                regressions.append({
                    'metric': 'requests_per_second',
                    'baseline': baseline_rps,
                    'current': current_rps,
                    'change_percent': rps_change
                })

        return {
            'regression_detected': len(regressions) > 0,
            'regressions': regressions,
            'summary': f"{'Performance regression detected' if regressions else 'No performance regression detected'} for {test_name}"
        }

class AutomatedTestSuite:
    """Automated test suite with predefined benchmarks"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.benchmark = PerformanceBenchmark(base_url)
        self.regression_detector = PerformanceRegressionDetector()

    async def run_full_suite(self) -> Dict[str, Any]:
        """Run complete performance test suite"""
        await self.benchmark.initialize()

        test_configs = [
            # API Response Time Tests
            BenchmarkConfig(
                name="api_health_check",
                test_type=TestType.LATENCY_TEST,
                target_endpoint=f"{self.base_url}/health",
                concurrent_users=1,
                duration_seconds=10,
                requests_per_second=10,
                success_criteria={
                    'max_avg_response_time_ms': 50,
                    'max_p95_response_time_ms': 100,
                    'min_success_rate_percent': 100
                }
            ),

            BenchmarkConfig(
                name="api_documents_list",
                test_type=TestType.LOAD_TEST,
                target_endpoint=f"{self.base_url}/api/v1/documents/",
                concurrent_users=50,
                duration_seconds=60,
                requests_per_second=100,
                success_criteria={
                    'max_avg_response_time_ms': 200,
                    'max_p95_response_time_ms': 500,
                    'min_success_rate_percent': 95,
                    'min_requests_per_second': 90
                }
            ),

            # WebSocket Performance Tests
            BenchmarkConfig(
                name="websocket_connections",
                test_type=TestType.LOAD_TEST,
                target_endpoint=f"{self.base_url.replace('http://', 'ws://')}/ws",
                concurrent_users=100,
                duration_seconds=60,
                websocket_test=True,
                success_criteria={
                    'max_avg_response_time_ms': 100,
                    'min_success_rate_percent': 95
                }
            ),

            # Stress Tests
            BenchmarkConfig(
                name="high_load_stress",
                test_type=TestType.STRESS_TEST,
                target_endpoint=f"{self.base_url}/api/v1/documents/search",
                concurrent_users=200,
                duration_seconds=120,
                requests_per_second=500,
                payload={'query': 'test', 'limit': 10},
                success_criteria={
                    'max_avg_response_time_ms': 1000,
                    'min_success_rate_percent': 90,
                    'min_requests_per_second': 400
                }
            ),
        ]

        results = []
        try:
            for config in test_configs:
                logger.info(f"Running benchmark: {config.name}")
                result = await self.benchmark.run_benchmark(config)
                results.append(result)

                # Check for regressions
                regression_check = self.regression_detector.detect_regression(config.name, result)
                if regression_check['regression_detected']:
                    logger.warning(f"Performance regression detected: {regression_check['summary']}")

        finally:
            await self.benchmark.cleanup()

        return {
            'timestamp': datetime.utcnow().isoformat(),
            'total_tests': len(test_configs),
            'successful_tests': sum(1 for r in results if r.success),
            'failed_tests': sum(1 for r in results if r.status == BenchmarkStatus.FAILED),
            'results': [asdict(r) for r in results],
            'summary': self.benchmark.get_results_summary()
        }

    async def run_quick_validation(self) -> Dict[str, Any]:
        """Run quick validation tests"""
        await self.benchmark.initialize()

        quick_config = BenchmarkConfig(
            name="quick_validation",
            test_type=TestType.LATENCY_TEST,
            target_endpoint=f"{self.base_url}/health",
            concurrent_users=5,
            duration_seconds=30,
            requests_per_second=10,
            success_criteria={
                'max_avg_response_time_ms': 100,
                'min_success_rate_percent': 100
            }
        )

        try:
            result = await self.benchmark.run_benchmark(quick_config)
            return {
                'validation_passed': result.success,
                'avg_response_time_ms': result.avg_response_time_ms,
                'success_rate_percent': result.success_rate_percent,
                'requests_per_second': result.requests_per_second
            }
        finally:
            await self.benchmark.cleanup()

# Usage examples and utility functions
async def run_performance_benchmarks(base_url: str = "http://localhost:8000") -> Dict[str, Any]:
    """Run comprehensive performance benchmarks"""
    test_suite = AutomatedTestSuite(base_url)
    return await test_suite.run_full_suite()

async def validate_performance_sla(base_url: str = "http://localhost:8000") -> bool:
    """Validate that performance meets SLA requirements"""
    test_suite = AutomatedTestSuite(base_url)
    validation_result = await test_suite.run_quick_validation()
    return validation_result['validation_passed']

if __name__ == "__main__":
    # Example usage
    async def main():
        print("Running performance benchmarks...")
        results = await run_performance_benchmarks()
        print(f"Benchmarks completed. Success rate: {results['successful_tests']}/{results['total_tests']}")

        print("Validating SLA...")
        sla_passed = await validate_performance_sla()
        print(f"SLA validation: {'PASSED' if sla_passed else 'FAILED'}")

    asyncio.run(main())