"""
Performance Testing Framework for the Multimodal Enterprise RAG System

This comprehensive testing framework provides load testing, stress testing,
benchmarking, and performance regression testing capabilities.
"""

import asyncio
import time
import json
import logging
import statistics
import threading
import subprocess
import psutil
import requests
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import aiohttp
import httpx
import locust
from locust import HttpUser, task, between
import pytest
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
import seaborn as sns
from jinja2 import Template

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TestScenario:
    """Performance test scenario definition"""
    name: str
    description: str
    endpoints: List[Dict[str, Any]]
    user_count: int
    spawn_rate: int
    duration: int
    think_time: float
    weight: float = 1.0

@dataclass
class TestResult:
    """Performance test result"""
    scenario_name: str
    start_time: datetime
    end_time: datetime
    duration: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    requests_per_second: float
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    p50_response_time: float
    p95_response_time: float
    p99_response_time: float
    error_rate: float
    throughput: float
    cpu_usage: float
    memory_usage: float
    errors: List[Dict[str, Any]]

@dataclass
class Benchmark:
    """Performance benchmark definition"""
    name: str
    description: str
    baseline_metrics: Dict[str, float]
    acceptable_degradation: Dict[str, float]
    test_scenarios: List[TestScenario]

class PerformanceTestRunner:
    """Main performance test runner"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results: List[TestResult] = []
        self.benchmarks: Dict[str, Benchmark] = {}
        self.scenarios: Dict[str, TestScenario] = {}
        self.monitoring_active = False
        self.system_metrics: List[Dict[str, Any]] = []

    def register_scenario(self, scenario: TestScenario):
        """Register a test scenario"""
        self.scenarios[scenario.name] = scenario
        logger.info(f"Registered scenario: {scenario.name}")

    def register_benchmark(self, benchmark: Benchmark):
        """Register a performance benchmark"""
        self.benchmarks[benchmark.name] = benchmark
        logger.info(f"Registered benchmark: {benchmark.name}")

    async def run_scenario(self, scenario_name: str) -> TestResult:
        """Run a single performance test scenario"""
        if scenario_name not in self.scenarios:
            raise ValueError(f"Scenario '{scenario_name}' not found")

        scenario = self.scenarios[scenario_name]
        logger.info(f"Starting scenario: {scenario.name}")

        # Start system monitoring
        monitoring_thread = threading.Thread(
            target=self._monitor_system_resources,
            daemon=True
        )
        monitoring_thread.start()

        start_time = datetime.now()
        results = []
        errors = []

        # Run the test
        try:
            results, errors = await self._execute_scenario(scenario)
        except Exception as e:
            logger.error(f"Error executing scenario {scenario_name}: {e}")
            raise
        finally:
            self.monitoring_active = False
            monitoring_thread.join(timeout=5)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Calculate metrics
        response_times = [r['response_time'] for r in results]
        successful_requests = [r for r in results if r['status_code'] < 400]

        test_result = TestResult(
            scenario_name=scenario.name,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            total_requests=len(results),
            successful_requests=len(successful_requests),
            failed_requests=len(errors),
            requests_per_second=len(results) / duration,
            avg_response_time=statistics.mean(response_times) if response_times else 0,
            min_response_time=min(response_times) if response_times else 0,
            max_response_time=max(response_times) if response_times else 0,
            p50_response_time=np.percentile(response_times, 50) if response_times else 0,
            p95_response_time=np.percentile(response_times, 95) if response_times else 0,
            p99_response_time=np.percentile(response_times, 99) if response_times else 0,
            error_rate=len(errors) / max(1, len(results)),
            throughput=len(successful_requests) / duration,
            cpu_usage=self._get_avg_cpu_usage(),
            memory_usage=self._get_avg_memory_usage(),
            errors=errors
        )

        self.results.append(test_result)
        logger.info(f"Scenario completed: {scenario.name}")
        return test_result

    async def _execute_scenario(self, scenario: TestScenario) -> tuple[List[Dict], List[Dict]]:
        """Execute a test scenario with concurrent users"""
        self.monitoring_active = True
        results = []
        errors = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Create user tasks
            tasks = []
            for user_id in range(scenario.user_count):
                task = asyncio.create_task(
                    self._simulate_user(client, scenario, user_id)
                )
                tasks.append(task)

            # Wait for all users to complete
            user_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Collect results
            for user_result in user_results:
                if isinstance(user_result, Exception):
                    errors.append({
                        "error": str(user_result),
                        "timestamp": datetime.now().isoformat()
                    })
                else:
                    user_requests, user_errors = user_result
                    results.extend(user_requests)
                    errors.extend(user_errors)

        return results, errors

    async def _simulate_user(
        self,
        client: httpx.Client,
        scenario: TestScenario,
        user_id: int
    ) -> tuple[List[Dict], List[Dict]]:
        """Simulate a single user's behavior"""
        results = []
        errors = []
        start_time = time.time()

        while time.time() - start_time < scenario.duration:
            for endpoint in scenario.endpoints:
                try:
                    # Add think time
                    if scenario.think_time > 0:
                        await asyncio.sleep(scenario.think_time)

                    # Make request
                    result = await self._make_request(client, endpoint, user_id)
                    results.append(result)

                except Exception as e:
                    errors.append({
                        "user_id": user_id,
                        "endpoint": endpoint.get('path', ''),
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    })

            # Small delay between iterations
            await asyncio.sleep(0.1)

        return results, errors

    async def _make_request(
        self,
        client: httpx.Client,
        endpoint: Dict[str, Any],
        user_id: int
    ) -> Dict[str, Any]:
        """Make a single HTTP request"""
        method = endpoint.get('method', 'GET')
        path = endpoint.get('path', '/')
        url = f"{self.base_url}{path}"
        headers = endpoint.get('headers', {})
        params = endpoint.get('params', {})
        json_data = endpoint.get('json', None)

        start_time = time.time()

        try:
            if method.upper() == 'GET':
                response = await client.get(url, headers=headers, params=params)
            elif method.upper() == 'POST':
                response = await client.post(url, headers=headers, json=json_data)
            elif method.upper() == 'PUT':
                response = await client.put(url, headers=headers, json=json_data)
            elif method.upper() == 'DELETE':
                response = await client.delete(url, headers=headers, params=params)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response_time = (time.time() - start_time) * 1000  # Convert to ms

            return {
                "method": method,
                "url": url,
                "status_code": response.status_code,
                "response_time": response_time,
                "response_size": len(response.content),
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id
            }

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            raise

    def _monitor_system_resources(self):
        """Monitor system resources during test execution"""
        self.monitoring_active = True

        while self.monitoring_active:
            try:
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk_io = psutil.disk_io_counters()
                network_io = psutil.net_io_counters()

                metrics = {
                    "timestamp": datetime.now().isoformat(),
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_used_gb": memory.used / (1024**3),
                    "memory_available_gb": memory.available / (1024**3),
                    "disk_read_mb": (disk_io.read_bytes / (1024**2)) if disk_io else 0,
                    "disk_write_mb": (disk_io.write_bytes / (1024**2)) if disk_io else 0,
                    "network_sent_mb": (network_io.bytes_sent / (1024**2)) if network_io else 0,
                    "network_recv_mb": (network_io.bytes_recv / (1024**2)) if network_io else 0
                }

                self.system_metrics.append(metrics)

                # Keep only last 1000 metrics
                if len(self.system_metrics) > 1000:
                    self.system_metrics = self.system_metrics[-1000:]

            except Exception as e:
                logger.error(f"Error monitoring system resources: {e}")

            time.sleep(1)

    def _get_avg_cpu_usage(self) -> float:
        """Get average CPU usage during test"""
        if not self.system_metrics:
            return 0.0
        return statistics.mean(m["cpu_percent"] for m in self.system_metrics)

    def _get_avg_memory_usage(self) -> float:
        """Get average memory usage during test"""
        if not self.system_metrics:
            return 0.0
        return statistics.mean(m["memory_percent"] for m in self.system_metrics)

    async def run_benchmark(self, benchmark_name: str) -> Dict[str, Any]:
        """Run a complete benchmark"""
        if benchmark_name not in self.benchmarks:
            raise ValueError(f"Benchmark '{benchmark_name}' not found")

        benchmark = self.benchmarks[benchmark_name]
        logger.info(f"Starting benchmark: {benchmark.name}")

        results = []
        for scenario in benchmark.test_scenarios:
            result = await self.run_scenario(scenario.name)
            results.append(result)

        # Compare with baseline
        comparison = self._compare_with_baseline(benchmark, results)

        return {
            "benchmark": benchmark.name,
            "results": results,
            "comparison": comparison,
            "passed": comparison["passed"]
        }

    def _compare_with_baseline(
        self,
        benchmark: Benchmark,
        results: List[TestResult]
    ) -> Dict[str, Any]:
        """Compare test results with baseline metrics"""
        comparison = {
            "passed": True,
            "metrics": {},
            "violations": []
        }

        for result in results:
            # Calculate current metrics
            current_metrics = {
                "avg_response_time": result.avg_response_time,
                "p95_response_time": result.p95_response_time,
                "requests_per_second": result.requests_per_second,
                "error_rate": result.error_rate,
                "cpu_usage": result.cpu_usage,
                "memory_usage": result.memory_usage
            }

            # Compare with baseline
            for metric, current_value in current_metrics.items():
                baseline_value = benchmark.baseline_metrics.get(metric)
                acceptable_degradation = benchmark.acceptable_degradation.get(metric, 0.1)

                if baseline_value:
                    degradation = (current_value - baseline_value) / baseline_value

                    # For metrics where lower is better (response times, error rates, resource usage)
                    if metric in ["avg_response_time", "p95_response_time", "error_rate", "cpu_usage", "memory_usage"]:
                        if degradation > acceptable_degradation:
                            comparison["passed"] = False
                            comparison["violations"].append({
                                "scenario": result.scenario_name,
                                "metric": metric,
                                "baseline": baseline_value,
                                "current": current_value,
                                "degradation": degradation,
                                "acceptable": acceptable_degradation
                            })
                    # For metrics where higher is better (throughput)
                    else:
                        if degradation < -acceptable_degradation:
                            comparison["passed"] = False
                            comparison["violations"].append({
                                "scenario": result.scenario_name,
                                "metric": metric,
                                "baseline": baseline_value,
                                "current": current_value,
                                "degradation": degradation,
                                "acceptable": -acceptable_degradation
                            })

                    comparison["metrics"][f"{result.scenario_name}_{metric}"] = {
                        "baseline": baseline_value,
                        "current": current_value,
                        "degradation": degradation,
                        "passed": degradation <= acceptable_degradation
                    }

        return comparison

    def generate_report(self, output_dir: str = "reports") -> str:
        """Generate performance test report"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = output_path / f"performance_report_{timestamp}.html"

        # Generate report data
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "summary": self._generate_summary(),
            "results": [asdict(r) for r in self.results],
            "system_metrics": self.system_metrics[-100:],  # Last 100 metrics
            "charts": self._generate_charts()
        }

        # Generate HTML report
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Performance Test Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50">
    <div class="container mx-auto px-4 py-8">
        <h1 class="text-3xl font-bold mb-6">Performance Test Report</h1>
        <p class="text-gray-600 mb-8">Generated: {{ timestamp }}</p>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <div class="bg-white p-6 rounded-lg shadow">
                <h3 class="text-lg font-semibold mb-2">Total Tests</h3>
                <p class="text-3xl font-bold text-blue-600">{{ summary.total_tests }}</p>
            </div>
            <div class="bg-white p-6 rounded-lg shadow">
                <h3 class="text-lg font-semibold mb-2">Avg Response Time</h3>
                <p class="text-3xl font-bold text-green-600">{{ "%.2f"|format(summary.avg_response_time) }}ms</p>
            </div>
            <div class="bg-white p-6 rounded-lg shadow">
                <h3 class="text-lg font-semibold mb-2">Requests/sec</h3>
                <p class="text-3xl font-bold text-purple-600">{{ "%.2f"|format(summary.requests_per_second) }}</p>
            </div>
        </div>

        <div class="bg-white p-6 rounded-lg shadow mb-8">
            <h2 class="text-xl font-semibold mb-4">Test Results</h2>
            <div class="overflow-x-auto">
                <table class="min-w-full table-auto">
                    <thead class="bg-gray-100">
                        <tr>
                            <th class="px-4 py-2 text-left">Scenario</th>
                            <th class="px-4 py-2 text-left">Duration</th>
                            <th class="px-4 py-2 text-left">Requests</th>
                            <th class="px-4 py-2 text-left">Success Rate</th>
                            <th class="px-4 py-2 text-left">Avg Response</th>
                            <th class="px-4 py-2 text-left">P95 Response</th>
                            <th class="px-4 py-2 text-left">RPS</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for result in results %}
                        <tr class="border-b">
                            <td class="px-4 py-2">{{ result.scenario_name }}</td>
                            <td class="px-4 py-2">{{ "%.1f"|format(result.duration) }}s</td>
                            <td class="px-4 py-2">{{ result.total_requests }}</td>
                            <td class="px-4 py-2">{{ "%.1f"|format((1 - result.error_rate) * 100) }}%</td>
                            <td class="px-4 py-2">{{ "%.2f"|format(result.avg_response_time) }}ms</td>
                            <td class="px-4 py-2">{{ "%.2f"|format(result.p95_response_time) }}ms</td>
                            <td class="px-4 py-2">{{ "%.2f"|format(result.requests_per_second) }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div class="bg-white p-6 rounded-lg shadow">
                <h3 class="text-lg font-semibold mb-4">Response Time Distribution</h3>
                <canvas id="responseTimeChart"></canvas>
            </div>
            <div class="bg-white p-6 rounded-lg shadow">
                <h3 class="text-lg font-semibold mb-4">System Resources</h3>
                <canvas id="resourceChart"></canvas>
            </div>
        </div>
    </div>

    <script>
        // Response Time Chart
        const responseCtx = document.getElementById('responseTimeChart').getContext('2d');
        new Chart(responseCtx, {
            type: 'bar',
            data: {
                labels: [{% for result in results %}'{{ result.scenario_name }}'{% if not loop.last %},{% endif %}{% endfor %}],
                datasets: [{
                    label: 'Average Response Time (ms)',
                    data: [{% for result in results %}{{ result.avg_response_time }}{% if not loop.last %},{% endif %}{% endfor %}],
                    backgroundColor: 'rgba(59, 130, 246, 0.5)'
                }, {
                    label: 'P95 Response Time (ms)',
                    data: [{% for result in results %}{{ result.p95_response_time }}{% if not loop.last %},{% endif %}{% endfor %}],
                    backgroundColor: 'rgba(16, 185, 129, 0.5)'
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });

        // System Resources Chart
        const resourceCtx = document.getElementById('resourceChart').getContext('2d');
        new Chart(resourceCtx, {
            type: 'line',
            data: {
                labels: [{% for metric in system_metrics %}'{{ metric.timestamp[-8:] }}'{% if not loop.last %},{% endif %}{% endfor %}],
                datasets: [{
                    label: 'CPU %',
                    data: [{% for metric in system_metrics %}{{ metric.cpu_percent }}{% if not loop.last %},{% endif %}{% endfor %}],
                    borderColor: 'rgb(239, 68, 68)',
                    tension: 0.1
                }, {
                    label: 'Memory %',
                    data: [{% for metric in system_metrics %}{{ metric.memory_percent }}{% if not loop.last %},{% endif %}{% endfor %}],
                    borderColor: 'rgb(59, 130, 246)',
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100
                    }
                }
            }
        });
    </script>
</body>
</html>
        """

        template = Template(html_template)
        html_content = template.render(**report_data)

        # Write report
        with open(report_file, 'w') as f:
            f.write(html_content)

        logger.info(f"Performance report generated: {report_file}")
        return str(report_file)

    def _generate_summary(self) -> Dict[str, Any]:
        """Generate summary statistics"""
        if not self.results:
            return {}

        total_requests = sum(r.total_requests for r in self.results)
        successful_requests = sum(r.successful_requests for r in self.results)
        failed_requests = sum(r.failed_requests for r in self.results)

        response_times = []
        for result in self.results:
            response_times.extend([result.avg_response_time])

        return {
            "total_tests": len(self.results),
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "success_rate": successful_requests / max(1, total_requests),
            "avg_response_time": statistics.mean(response_times) if response_times else 0,
            "requests_per_second": sum(r.requests_per_second for r in self.results) / max(1, len(self.results))
        }

    def _generate_charts(self) -> Dict[str, List]:
        """Generate chart data"""
        if not self.results:
            return {}

        return {
            "response_times": [
                {
                    "scenario": r.scenario_name,
                    "avg": r.avg_response_time,
                    "p50": r.p50_response_time,
                    "p95": r.p95_response_time,
                    "p99": r.p99_response_time
                }
                for r in self.results
            ],
            "throughput": [
                {
                    "scenario": r.scenario_name,
                    "rps": r.requests_per_second
                }
                for r in self.results
            ],
            "error_rates": [
                {
                    "scenario": r.scenario_name,
                    "error_rate": r.error_rate * 100
                }
                for r in self.results
            ]
        }

    def export_results(self, filename: str, format: str = "json"):
        """Export test results"""
        if format.lower() == "json":
            data = {
                "timestamp": datetime.now().isoformat(),
                "results": [asdict(r) for r in self.results],
                "system_metrics": self.system_metrics
            }
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2, default=str)

        elif format.lower() == "csv":
            if self.results:
                df = pd.DataFrame([asdict(r) for r in self.results])
                df.to_csv(filename, index=False)

        logger.info(f"Results exported to {filename}")

# Locust integration for distributed load testing
class RAGSystemUser(HttpUser):
    """Locust user class for RAG system load testing"""

    wait_time = between(1, 3)

    def on_start(self):
        """Called when a user starts"""
        pass

    @task(3)
    def search_documents(self):
        """Search for documents"""
        response = self.client.get(
            "/api/search",
            params={"query": "test query", "limit": 10}
        )
        if response.status_code != 200:
            response.failure("Search failed")

    @task(2)
    def get_analytics(self):
        """Get analytics dashboard"""
        response = self.client.get("/api/analytics/dashboard")
        if response.status_code != 200:
            response.failure("Analytics request failed")

    @task(1)
    def upload_document(self):
        """Upload a document"""
        files = {
            "file": ("test.txt", "Test content", "text/plain")
        }
        response = self.client.post("/api/documents/upload", files=files)
        if response.status_code not in [200, 201]:
            response.failure("Upload failed")

    @task(1)
    def get_knowledge_graph(self):
        """Get knowledge graph data"""
        response = self.client.get("/api/graph/entities")
        if response.status_code != 200:
            response.failure("Graph request failed")

# Predefined test scenarios
def create_standard_scenarios() -> List[TestScenario]:
    """Create standard performance test scenarios"""
    return [
        TestScenario(
            name="light_load",
            description="Light load test with 10 concurrent users",
            endpoints=[
                {"method": "GET", "path": "/api/search", "params": {"query": "test"}},
                {"method": "GET", "path": "/api/analytics/dashboard"},
                {"method": "GET", "path": "/api/graph/entities"}
            ],
            user_count=10,
            spawn_rate=2,
            duration=60,
            think_time=1.0,
            weight=1.0
        ),
        TestScenario(
            name="moderate_load",
            description="Moderate load test with 50 concurrent users",
            endpoints=[
                {"method": "GET", "path": "/api/search", "params": {"query": "test"}},
                {"method": "GET", "path": "/api/analytics/dashboard"},
                {"method": "POST", "path": "/api/documents/upload", "json": {"content": "test"}},
                {"method": "GET", "path": "/api/graph/entities"}
            ],
            user_count=50,
            spawn_rate=5,
            duration=120,
            think_time=0.5,
            weight=2.0
        ),
        TestScenario(
            name="heavy_load",
            description="Heavy load test with 200 concurrent users",
            endpoints=[
                {"method": "GET", "path": "/api/search", "params": {"query": "test"}},
                {"method": "GET", "path": "/api/analytics/dashboard"},
                {"method": "POST", "path": "/api/documents/upload", "json": {"content": "test"}},
                {"method": "GET", "path": "/api/graph/entities"},
                {"method": "GET", "path": "/api/evaluation/metrics"}
            ],
            user_count=200,
            spawn_rate=20,
            duration=180,
            think_time=0.2,
            weight=3.0
        ),
        TestScenario(
            name="stress_test",
            description="Stress test with 500 concurrent users",
            endpoints=[
                {"method": "GET", "path": "/api/search", "params": {"query": "test"}},
                {"method": "GET", "path": "/api/analytics/dashboard"}
            ],
            user_count=500,
            spawn_rate=50,
            duration=300,
            think_time=0.1,
            weight=4.0
        )
    ]

def create_baseline_benchmark() -> Benchmark:
    """Create baseline performance benchmark"""
    return Benchmark(
        name="baseline_performance",
        description="Baseline performance metrics for RAG system",
        baseline_metrics={
            "avg_response_time": 500.0,  # ms
            "p95_response_time": 1500.0,  # ms
            "requests_per_second": 100.0,
            "error_rate": 0.01,  # 1%
            "cpu_usage": 0.70,  # 70%
            "memory_usage": 0.80  # 80%
        },
        acceptable_degradation={
            "avg_response_time": 0.20,  # 20% degradation allowed
            "p95_response_time": 0.30,
            "requests_per_second": -0.15,  # 15% degradation allowed
            "error_rate": 0.02,
            "cpu_usage": 0.10,
            "memory_usage": 0.10
        },
        test_scenarios=create_standard_scenarios()
    )

# Pytest integration
@pytest.fixture
def performance_test_runner():
    """Pytest fixture for performance testing"""
    runner = PerformanceTestRunner()

    # Register standard scenarios
    for scenario in create_standard_scenarios():
        runner.register_scenario(scenario)

    # Register baseline benchmark
    runner.register_benchmark(create_baseline_benchmark())

    yield runner

    # Cleanup
    runner.results.clear()

@pytest.mark.asyncio
async def test_light_load_performance(performance_test_runner):
    """Test light load performance"""
    result = await performance_test_runner.run_scenario("light_load")

    # Assert performance requirements
    assert result.avg_response_time < 1000, f"Avg response time too high: {result.avg_response_time}ms"
    assert result.error_rate < 0.05, f"Error rate too high: {result.error_rate}"
    assert result.requests_per_second > 10, f"RPS too low: {result.requests_per_second}"

@pytest.mark.asyncio
async def test_moderate_load_performance(performance_test_runner):
    """Test moderate load performance"""
    result = await performance_test_runner.run_scenario("moderate_load")

    # Assert performance requirements
    assert result.avg_response_time < 2000, f"Avg response time too high: {result.avg_response_time}ms"
    assert result.error_rate < 0.10, f"Error rate too high: {result.error_rate}"
    assert result.requests_per_second > 50, f"RPS too low: {result.requests_per_second}"

@pytest.mark.asyncio
async def test_baseline_benchmark(performance_test_runner):
    """Test against baseline benchmark"""
    result = await performance_test_runner.run_benchmark("baseline_performance")

    assert result["passed"], f"Benchmark failed: {result['comparison']['violations']}"

# Command line interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Performance Testing Framework")
    parser.add_argument("--scenario", help="Test scenario to run")
    parser.add_argument("--benchmark", help="Benchmark to run")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL for testing")
    parser.add_argument("--report-dir", default="reports", help="Report output directory")

    args = parser.parse_args()

    async def main():
        runner = PerformanceTestRunner(args.url)

        # Register standard scenarios and benchmarks
        for scenario in create_standard_scenarios():
            runner.register_scenario(scenario)
        runner.register_benchmark(create_baseline_benchmark())

        if args.benchmark:
            result = await runner.run_benchmark(args.benchmark)
            print(f"Benchmark result: {'PASSED' if result['passed'] else 'FAILED'}")
        elif args.scenario:
            result = await runner.run_scenario(args.scenario)
            print(f"Scenario completed: {result.scenario_name}")
            print(f"  Requests: {result.total_requests}")
            print(f"  Success rate: {(1 - result.error_rate) * 100:.1f}%")
            print(f"  Avg response time: {result.avg_response_time:.2f}ms")
            print(f"  RPS: {result.requests_per_second:.2f}")
        else:
            # Run all scenarios
            for scenario in create_standard_scenarios():
                await runner.run_scenario(scenario.name)

        # Generate report
        report_path = runner.generate_report(args.report_dir)
        print(f"Report generated: {report_path}")

    asyncio.run(main())