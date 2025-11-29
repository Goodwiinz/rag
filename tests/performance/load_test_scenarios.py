"""
Comprehensive load testing scenarios for the Multimodal Enterprise RAG System
"""

import asyncio
import time
import random
import json
import aiohttp
import statistics
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
import logging
import uuid
from locust import HttpUser, task, between, events
import numpy as np

logger = logging.getLogger(__name__)

@dataclass
class LoadTestConfig:
    """Load test configuration"""
    base_url: str = "http://localhost:8000"
    concurrent_users: int = 50
    test_duration: int = 300  # seconds
    spawn_rate: int = 5  # users per second

    # Performance targets
    target_response_time_p95: float = 2.0  # seconds
    target_response_time_p99: float = 5.0  # seconds
    target_error_rate: float = 0.01  # 1%
    target_throughput: float = 100  # requests per second

@dataclass
class LoadTestResults:
    """Load test results"""
    test_name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    error_rate: float
    avg_response_time: float
    p50_response_time: float
    p95_response_time: float
    p99_response_time: float
    min_response_time: float
    max_response_time: float
    throughput: float  # requests per second
    test_duration: float
    cpu_usage: List[float]
    memory_usage: List[float]
    errors_by_type: Dict[str, int]

class PerformanceTestCase:
    """Base class for performance test cases"""

    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self.results: List[Dict] = []

    async def setup(self):
        """Setup test environment"""
        connector = aiohttp.TCPConnector(
            limit=100,
            limit_per_host=50,
            ttl_dns_cache=300,
            use_dns_cache=True,
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )

        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={'User-Agent': 'RAG-LoadTest/1.0'}
        )

    async def teardown(self):
        """Cleanup test environment"""
        if self.session:
            await self.session.close()

    async def make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make HTTP request and record metrics"""
        start_time = time.time()

        try:
            async with self.session.request(method, f"{self.config.base_url}{endpoint}", **kwargs) as response:
                content = await response.text()
                response_time = time.time() - start_time

                result = {
                    'method': method,
                    'endpoint': endpoint,
                    'status_code': response.status,
                    'response_time': response_time,
                    'success': 200 <= response.status_code < 400,
                    'timestamp': time.time(),
                    'content_length': len(content)
                }

                if not result['success']:
                    result['error'] = f"HTTP {response.status_code}"

                return result

        except Exception as e:
            response_time = time.time() - start_time
            return {
                'method': method,
                'endpoint': endpoint,
                'status_code': 0,
                'response_time': response_time,
                'success': False,
                'timestamp': time.time(),
                'error': str(e),
                'content_length': 0
            }

    async def run_test(self, name: str, duration: int, concurrency: int) -> LoadTestResults:
        """Run load test with specified parameters"""
        logger.info(f"Starting load test: {name} (concurrency: {concurrency}, duration: {duration}s)")

        await self.setup()
        start_time = time.time()

        # Create concurrent tasks
        tasks = []
        for i in range(concurrency):
            task = asyncio.create_task(self._run_user_session(duration))
            tasks.append(task)

        # Wait for all tasks to complete
        await asyncio.gather(*tasks)

        test_duration = time.time() - start_time
        await self.teardown()

        # Analyze results
        return self._analyze_results(name, test_duration)

    async def _run_user_session(self, duration: int):
        """Run individual user session"""
        end_time = time.time() + duration

        while time.time() < end_time:
            # This should be implemented by specific test cases
            await self._execute_user_action()

            # Small delay between requests
            await asyncio.sleep(random.uniform(0.1, 2.0))

    async def _execute_user_action(self):
        """Execute user action - to be implemented by subclasses"""
        raise NotImplementedError

    def _analyze_results(self, test_name: str, test_duration: float) -> LoadTestResults:
        """Analyze test results"""
        if not self.results:
            return LoadTestResults(test_name, 0, 0, 0, 1.0, 0, 0, 0, 0, 0, 0, test_duration, [], [], {})

        successful = [r for r in self.results if r['success']]
        failed = [r for r in self.results if not r['success']]

        response_times = [r['response_time'] for r in self.results]

        errors_by_type = {}
        for result in failed:
            error_type = result.get('error', f"HTTP {result['status_code']}")
            errors_by_type[error_type] = errors_by_type.get(error_type, 0) + 1

        return LoadTestResults(
            test_name=test_name,
            total_requests=len(self.results),
            successful_requests=len(successful),
            failed_requests=len(failed),
            error_rate=len(failed) / len(self.results),
            avg_response_time=statistics.mean(response_times),
            p50_response_time=np.percentile(response_times, 50),
            p95_response_time=np.percentile(response_times, 95),
            p99_response_time=np.percentile(response_times, 99),
            min_response_time=min(response_times),
            max_response_time=max(response_times),
            throughput=len(self.results) / test_duration,
            test_duration=test_duration,
            cpu_usage=[],  # Would be populated by monitoring
            memory_usage=[],  # Would be populated by monitoring
            errors_by_type=errors_by_type
        )

class DocumentUploadTest(PerformanceTestCase):
    """Document upload load test"""

    def __init__(self, config: LoadTestConfig):
        super().__init__(config)
        self.test_files = self._prepare_test_files()

    def _prepare_test_files(self) -> List[Dict]:
        """Prepare test files for upload"""
        return [
            {
                'name': 'test_document.pdf',
                'content': b'PDF content for testing' * 1000,
                'content_type': 'application/pdf'
            },
            {
                'name': 'test_document.txt',
                'content': b'Text content for testing' * 1000,
                'content_type': 'text/plain'
            }
        ]

    async def _execute_user_action(self):
        """Execute document upload action"""
        file_data = random.choice(self.test_files)

        # Create multipart form data
        form_data = aiohttp.FormData()
        form_data.add_field(
            'file',
            file_data['content'],
            filename=file_data['name'],
            content_type=file_data['content_type']
        )
        form_data.add_field('title', f'Test Document {uuid.uuid4()}')
        form_data.add_field('document_type', 'test')

        result = await self.make_request('POST', '/api/v1/files/upload', data=form_data)
        self.results.append(result)

class SearchTest(PerformanceTestCase):
    """Search functionality load test"""

    def __init__(self, config: LoadTestConfig):
        super().__init__(config)
        self.search_queries = [
            'machine learning algorithms',
            'data science techniques',
            'artificial intelligence research',
            'neural networks',
            'deep learning applications',
            'natural language processing',
            'computer vision systems',
            'predictive analytics',
            'big data technologies',
            'cloud computing platforms'
        ]

    async def _execute_user_action(self):
        """Execute search action"""
        query = random.choice(self.search_queries)
        params = {
            'q': query,
            'limit': random.randint(10, 50),
            'offset': random.randint(0, 100)
        }

        result = await self.make_request('GET', '/api/v1/search', params=params)
        self.results.append(result)

class HybridSearchTest(PerformanceTestCase):
    """Hybrid search (vector + graph + keyword) load test"""

    def __init__(self, config: LoadTestConfig):
        super().__init__(config)
        self.complex_queries = [
            {
                'query': 'machine learning algorithms',
                'filters': {'document_type': 'research_paper'},
                'search_type': 'hybrid'
            },
            {
                'query': 'data analysis techniques',
                'filters': {'modality': 'text'},
                'search_type': 'semantic'
            },
            {
                'query': 'AI research trends',
                'filters': {'date_range': '2023-2024'},
                'search_type': 'vector'
            }
        ]

    async def _execute_user_action(self):
        """Execute hybrid search action"""
        query_config = random.choice(self.complex_queries)

        params = {
            'q': query_config['query'],
            'search_type': query_config['search_type'],
            'limit': random.randint(5, 20)
        }
        params.update(query_config['filters'])

        result = await self.make_request('POST', '/api/v1/search/hybrid', json=params)
        self.results.append(result)

class KnowledgeGraphTest(PerformanceTestCase):
    """Knowledge graph operations load test"""

    def __init__(self, config: LoadTestConfig):
        super().__init__(config)
        self.entity_queries = [
            'artificial intelligence',
            'machine learning',
            'data science',
            'neural networks',
            'deep learning'
        ]

    async def _execute_user_action(self):
        """Execute knowledge graph action"""
        query = random.choice(self.entity_queries)

        # Test different graph endpoints
        endpoints = [
            f'/api/v1/knowledge-graph/entities/search?q={query}',
            f'/api/v1/knowledge-graph/relationships?entity={query}',
            '/api/v1/knowledge-graph/subgraph'
        ]

        endpoint = random.choice(endpoints)

        if 'subgraph' in endpoint:
            result = await self.make_request('POST', endpoint, json={
                'entities': [query],
                'max_depth': 2,
                'max_nodes': 50
            })
        else:
            result = await self.make_request('GET', endpoint)

        self.results.append(result)

class MultiAgentSearchTest(PerformanceTestCase):
    """Multi-agent search load test"""

    def __init__(self, config: LoadTestConfig):
        super().__init__(config)
        self.agent_workflows = [
            'factual_lookup',
            'reasoning',
            'multimodal'
        ]

    async def _execute_user_action(self):
        """Execute multi-agent search action"""
        workflow = random.choice(self.agent_workflows)

        payload = {
            'query': f'Test query for {workflow} workflow',
            'workflow_type': workflow,
            'context': {
                'user_preferences': {
                    'response_format': 'detailed',
                    'include_sources': True
                }
            }
        }

        result = await self.make_request('POST', '/api/v1/multi-agent/search', json=payload)
        self.results.append(result)

class AnalyticsTest(PerformanceTestCase):
    """Analytics and metrics load test"""

    def __init__(self, config: LoadTestConfig):
        super().__init__(config)
        self.analytics_endpoints = [
            '/api/v1/analytics/performance/summary',
            '/api/v1/analytics/quality/metrics',
            '/api/v1/analytics/behavior/stats',
            '/api/v1/analytics/recommendations/suggestions'
        ]

    async def _execute_user_action(self):
        """Execute analytics query"""
        endpoint = random.choice(self.analytics_endpoints)
        params = {
            'time_range': '24h',
            'granularity': 'hour'
        }

        result = await self.make_request('GET', endpoint, params=params)
        self.results.append(result)

class LoadTestRunner:
    """Main load test runner"""

    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.test_results: List[LoadTestResults] = []

    async def run_all_tests(self) -> List[LoadTestResults]:
        """Run all load test scenarios"""
        logger.info("Starting comprehensive load testing suite")

        test_cases = [
            ('Document Upload', DocumentUploadTest),
            ('Basic Search', SearchTest),
            ('Hybrid Search', HybridSearchTest),
            ('Knowledge Graph', KnowledgeGraphTest),
            ('Multi-Agent Search', MultiAgentSearchTest),
            ('Analytics', AnalyticsTest)
        ]

        for test_name, test_class in test_cases:
            try:
                # Run different load levels
                for concurrency, duration in [
                    (10, 60),    # Light load
                    (25, 120),   # Medium load
                    (50, 300),   # Heavy load
                ]:
                    test_instance = test_class(self.config)
                    result = await test_instance.run_test(
                        f"{test_name} - {concurrency} users",
                        duration,
                        concurrency
                    )
                    self.test_results.append(result)

                    # Check if targets met
                    self._check_performance_targets(result)

                    # Small delay between tests
                    await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Test {test_name} failed: {e}")

        return self.test_results

    def _check_performance_targets(self, result: LoadTestResults):
        """Check if performance targets are met"""
        targets_met = True

        if result.p95_response_time > self.config.target_response_time_p95:
            logger.warning(f"P95 response time target missed: {result.p95_response_time:.2f}s > {self.config.target_response_time_p95}s")
            targets_met = False

        if result.p99_response_time > self.config.target_response_time_p99:
            logger.warning(f"P99 response time target missed: {result.p99_response_time:.2f}s > {self.config.target_response_time_p99}s")
            targets_met = False

        if result.error_rate > self.config.target_error_rate:
            logger.warning(f"Error rate target missed: {result.error_rate:.2%} > {self.config.target_error_rate:.2%}")
            targets_met = False

        if result.throughput < self.config.target_throughput:
            logger.warning(f"Throughput target missed: {result.throughput:.2f} req/s < {self.config.target_throughput} req/s")
            targets_met = False

        if targets_met:
            logger.info(f"✅ All performance targets met for {result.test_name}")
        else:
            logger.error(f"❌ Performance targets missed for {result.test_name}")

    def generate_report(self) -> str:
        """Generate comprehensive load test report"""
        report = ["# Load Test Report\n"]

        # Summary table
        report.append("## Test Summary\n")
        report.append("| Test Name | Total Requests | Success Rate | Avg Response Time | P95 Response Time | Throughput |\n")
        report.append("|-----------|----------------|--------------|-------------------|-------------------|------------|\n")

        for result in self.test_results:
            success_rate = (result.successful_requests / result.total_requests) * 100 if result.total_requests > 0 else 0
            report.append(
                f"| {result.test_name} | {result.total_requests} | {success_rate:.1f}% | "
                f"{result.avg_response_time:.3f}s | {result.p95_response_time:.3f}s | "
                f"{result.throughput:.1f} req/s |\n"
            )

        # Detailed results
        report.append("\n## Detailed Results\n")

        for result in self.test_results:
            report.append(f"### {result.test_name}\n")
            report.append(f"- **Total Requests**: {result.total_requests}\n")
            report.append(f"- **Successful**: {result.successful_requests}\n")
            report.append(f"- **Failed**: {result.failed_requests}\n")
            report.append(f"- **Error Rate**: {result.error_rate:.2%}\n")
            report.append(f"- **Average Response Time**: {result.avg_response_time:.3f}s\n")
            report.append(f"- **P50 Response Time**: {result.p50_response_time:.3f}s\n")
            report.append(f"- **P95 Response Time**: {result.p95_response_time:.3f}s\n")
            report.append(f"- **P99 Response Time**: {result.p99_response_time:.3f}s\n")
            report.append(f"- **Min Response Time**: {result.min_response_time:.3f}s\n")
            report.append(f"- **Max Response Time**: {result.max_response_time:.3f}s\n")
            report.append(f"- **Throughput**: {result.throughput:.1f} requests/second\n")

            if result.errors_by_type:
                report.append("- **Errors by Type**:\n")
                for error_type, count in result.errors_by_type.items():
                    report.append(f"  - {error_type}: {count}\n")

            report.append("\n")

        # Performance analysis
        report.append("## Performance Analysis\n")

        # Find best and worst performing tests
        if self.test_results:
            best_throughput = max(self.test_results, key=lambda r: r.throughput)
            worst_p95 = max(self.test_results, key=lambda r: r.p95_response_time)
            highest_error_rate = max(self.test_results, key=lambda r: r.error_rate)

            report.append(f"- **Best Throughput**: {best_throughput.test_name} ({best_throughput.throughput:.1f} req/s)\n")
            report.append(f"- **Worst P95 Response Time**: {worst_p95.test_name} ({worst_p95.p95_response_time:.3f}s)\n")
            report.append(f"- **Highest Error Rate**: {highest_error_rate.test_name} ({highest_error_rate.error_rate:.2%})\n")

        # Recommendations
        report.append("\n## Recommendations\n")

        for result in self.test_results:
            if result.p95_response_time > self.config.target_response_time_p95:
                report.append(f"- **{result.test_name}**: Optimize for faster response times (current: {result.p95_response_time:.3f}s)\n")

            if result.error_rate > self.config.target_error_rate:
                report.append(f"- **{result.test_name}**: Improve error handling (current error rate: {result.error_rate:.2%})\n")

            if result.throughput < self.config.target_throughput:
                report.append(f"- **{result.test_name}**: Increase throughput (current: {result.throughput:.1f} req/s)\n")

        return "".join(report)

# Locust integration for distributed load testing
class RAGSystemUser(HttpUser):
    """Locust user class for RAG system load testing"""

    wait_time = between(1, 3)

    def on_start(self):
        """Called when a user starts"""
        # Login or setup user session
        response = self.client.post("/api/v1/auth/login", json={
            "username": "test_user",
            "password": "test_password"
        })
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.client.headers.update({"Authorization": f"Bearer {self.token}"})

    @task(3)
    def search_documents(self):
        """Search documents task"""
        queries = [
            "machine learning",
            "data science",
            "artificial intelligence",
            "neural networks"
        ]
        query = random.choice(queries)

        self.client.get(
            "/api/v1/search",
            params={"q": query, "limit": 20}
        )

    @task(2)
    def hybrid_search(self):
        """Hybrid search task"""
        self.client.post(
            "/api/v1/search/hybrid",
            json={
                "query": "test query",
                "search_type": "hybrid",
                "limit": 10
            }
        )

    @task(1)
    def get_analytics(self):
        """Get analytics task"""
        self.client.get("/api/v1/analytics/performance/summary")

    @task(1)
    def upload_document(self):
        """Upload document task"""
        # This would need actual file content
        pass

# Custom event handlers for Locust
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Custom request event handler"""
    if exception:
        logger.error(f"Request failed: {name} - {exception}")
    else:
        logger.debug(f"Request completed: {name} in {response_time}ms")

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Test start event handler"""
    logger.info("Load test started")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Test stop event handler"""
    logger.info("Load test completed")

# Main execution function
async def main():
    """Main function to run load tests"""
    config = LoadTestConfig(
        base_url="http://localhost:8000",
        concurrent_users=50,
        test_duration=300
    )

    runner = LoadTestRunner(config)
    results = await runner.run_all_tests()

    # Generate and save report
    report = runner.generate_report()
    with open("load_test_report.md", "w") as f:
        f.write(report)

    logger.info("Load test completed. Report saved to load_test_report.md")

if __name__ == "__main__":
    asyncio.run(main())