"""
Performance and Load Testing for Multimodal Enterprise RAG System

Comprehensive performance testing including:
- Load testing with concurrent users
- Stress testing beyond capacity limits
- Performance regression testing
- Database performance under load
- API response time benchmarks
- Memory and resource usage monitoring
"""

import pytest
import asyncio
import time
import threading
import queue
import statistics
import json
import psutil
import gc
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from contextlib import contextmanager
import numpy as np

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.main import app
from src.core.database import get_db
from src.models.user import User, UserRole
from src.models.organization import Organization
from src.models.document import Document, DocumentType, ProcessingStatus
from tests.conftest import create_access_token


@dataclass
class PerformanceMetrics:
    """Performance metrics data structure"""
    operation: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    p95_response_time: float
    p99_response_time: float
    requests_per_second: float
    error_rate: float
    memory_usage_mb: float
    cpu_usage_percent: float


@dataclass
class LoadTestConfig:
    """Configuration for load testing"""
    concurrent_users: int
    requests_per_user: int
    ramp_up_time: float  # seconds
    test_duration: float  # seconds
    endpoint: str
    method: str = "GET"
    payload: Optional[Dict] = None
    headers: Optional[Dict] = None


class PerformanceMonitor:
    """Monitor system performance during tests"""

    def __init__(self):
        self.process = psutil.Process()
        self.monitoring = False
        self.metrics_history = []

    def start_monitoring(self):
        """Start performance monitoring"""
        self.monitoring = True
        self.metrics_history = []
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

    def stop_monitoring(self) -> Dict[str, float]:
        """Stop monitoring and return aggregated metrics"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)

        if not self.metrics_history:
            return {}

        # Aggregate metrics
        cpu_values = [m['cpu'] for m in self.metrics_history]
        memory_values = [m['memory_mb'] for m in self.metrics_history]

        return {
            'avg_cpu_percent': statistics.mean(cpu_values),
            'max_cpu_percent': max(cpu_values),
            'avg_memory_mb': statistics.mean(memory_values),
            'max_memory_mb': max(memory_values),
            'min_memory_mb': min(memory_values),
            'samples_count': len(self.metrics_history)
        }

    def _monitor_loop(self):
        """Monitoring loop running in separate thread"""
        while self.monitoring:
            try:
                cpu_percent = self.process.cpu_percent()
                memory_mb = self.process.memory_info().rss / 1024 / 1024

                self.metrics_history.append({
                    'timestamp': time.time(),
                    'cpu': cpu_percent,
                    'memory_mb': memory_mb
                })

                time.sleep(0.1)  # Sample every 100ms
            except Exception:
                break


class LoadTestRunner:
    """Load testing execution engine"""

    def __init__(self, base_url: str = "http://test"):
        self.base_url = base_url
        self.client = TestClient(app)
        self.monitor = PerformanceMonitor()

    def execute_load_test(self, config: LoadTestConfig) -> PerformanceMetrics:
        """Execute a load test with the given configuration"""
        print(f"Starting load test: {config.concurrent_users} users, {config.requests_per_user} requests each")
        print(f"Target endpoint: {config.method} {config.endpoint}")

        # Start performance monitoring
        self.monitor.start_monitoring()

        # Prepare requests queue
        request_queue = queue.Queue()
        for _ in range(config.concurrent_users * config.requests_per_user):
            request_queue.put(config)

        # Track results
        response_times = []
        success_count = 0
        error_count = 0
        errors = []

        # Worker function
        def worker():
            nonlocal success_count, error_count
            while not request_queue.empty():
                try:
                    test_config = request_queue.get()
                    start_time = time.time()

                    # Execute request
                    response = self._execute_request(test_config)
                    end_time = time.time()

                    response_time = (end_time - start_time) * 1000  # Convert to ms
                    response_times.append(response_time)

                    if response.status_code < 400:
                        success_count += 1
                    else:
                        error_count += 1
                        errors.append({
                            'status_code': response.status_code,
                            'response': response.text[:200]
                        })

                except Exception as e:
                    error_count += 1
                    errors.append({'exception': str(e)})
                finally:
                    request_queue.task_done()

        # Execute with concurrent workers
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=config.concurrent_users) as executor:
            # Submit workers with ramp-up
            for i in range(config.concurrent_users):
                if config.ramp_up_time > 0:
                    delay = (config.ramp_up_time / config.concurrent_users) * i
                    time.sleep(delay)
                executor.submit(worker)

            # Wait for completion
            executor.shutdown(wait=True)

        end_time = time.time()

        # Stop monitoring
        system_metrics = self.monitor.stop_monitoring()

        # Calculate metrics
        total_requests = success_count + error_count
        total_time = end_time - start_time

        if response_times:
            avg_response_time = statistics.mean(response_times)
            min_response_time = min(response_times)
            max_response_time = max(response_times)
            p95_response_time = np.percentile(response_times, 95)
            p99_response_time = np.percentile(response_times, 99)
        else:
            avg_response_time = min_response_time = max_response_time = 0
            p95_response_time = p99_response_time = 0

        rps = total_requests / total_time if total_time > 0 else 0
        error_rate = (error_count / total_requests * 100) if total_requests > 0 else 0

        metrics = PerformanceMetrics(
            operation=f"{config.method} {config.endpoint}",
            total_requests=total_requests,
            successful_requests=success_count,
            failed_requests=error_count,
            avg_response_time=avg_response_time,
            min_response_time=min_response_time,
            max_response_time=max_response_time,
            p95_response_time=p95_response_time,
            p99_response_time=p99_response_time,
            requests_per_second=rps,
            error_rate=error_rate,
            memory_usage_mb=system_metrics.get('avg_memory_mb', 0),
            cpu_usage_percent=system_metrics.get('avg_cpu_percent', 0)
        )

        # Print summary
        print(f"\nLoad Test Results:")
        print(f"  Total Requests: {total_requests}")
        print(f"  Success Rate: {((success_count/total_requests)*100):.2f}%")
        print(f"  Average Response Time: {avg_response_time:.2f}ms")
        print(f"  95th Percentile: {p95_response_time:.2f}ms")
        print(f"  Requests/Second: {rps:.2f}")
        print(f"  Error Rate: {error_rate:.2f}%")
        print(f"  Avg Memory Usage: {system_metrics.get('avg_memory_mb', 0):.2f}MB")
        print(f"  Avg CPU Usage: {system_metrics.get('avg_cpu_percent', 0):.2f}%")

        if errors and len(errors) <= 5:
            print(f"  Sample Errors: {errors[:3]}")

        return metrics

    def _execute_request(self, config: LoadTestConfig):
        """Execute a single HTTP request"""
        headers = config.headers or {}

        if config.method.upper() == "GET":
            return self.client.get(config.endpoint, headers=headers)
        elif config.method.upper() == "POST":
            return self.client.post(config.endpoint, json=config.payload, headers=headers)
        elif config.method.upper() == "PUT":
            return self.client.put(config.endpoint, json=config.payload, headers=headers)
        elif config.method.upper() == "DELETE":
            return self.client.delete(config.endpoint, headers=headers)
        else:
            raise ValueError(f"Unsupported method: {config.method}")

    def execute_stress_test(self, endpoint: str, max_users: int = 100,
                           step_size: int = 10) -> List[PerformanceMetrics]:
        """Execute stress test with gradually increasing load"""
        print(f"Starting stress test for {endpoint}")
        results = []

        for users in range(step_size, max_users + 1, step_size):
            print(f"\nTesting with {users} concurrent users...")

            config = LoadTestConfig(
                concurrent_users=users,
                requests_per_user=5,
                ramp_up_time=2.0,
                test_duration=30.0,
                endpoint=endpoint
            )

            metrics = self.execute_load_test(config)
            results.append(metrics)

            # Stop test if error rate is too high
            if metrics.error_rate > 50:
                print(f"Error rate too high ({metrics.error_rate:.2f}%), stopping stress test")
                break

            # Small pause between test runs
            time.sleep(2)

        return results


class TestAPIPerformance:
    """Test API performance under various load conditions"""

    @pytest.fixture(scope="class")
    def test_data(self, db_session):
        """Create test data for performance testing"""
        # Create test organization
        org = Organization(
            name="Performance Test Org",
            plan_tier="professional",
            max_users=100,
            storage_quota_gb=100.0,
            is_active=True
        )
        db_session.add(org)
        db_session.commit()
        db_session.refresh(org)

        # Create test user
        user = User(
            email="perf@test.com",
            first_name="Performance",
            last_name="Test",
            role=UserRole.USER,
            organization_id=org.id,
            is_active=True,
            email_verified=True
        )
        user.set_password("testpassword123")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create test documents
        documents = []
        for i in range(100):
            doc = Document(
                title=f"Performance Test Document {i}",
                filename=f"perf_test_{i}.txt",
                file_path=f"/test/perf_test_{i}.txt",
                file_size_bytes=1024,
                mime_type="text/plain",
                document_type=DocumentType.TEXT,
                processing_status=ProcessingStatus.COMPLETED,
                content_text=f"This is performance test document {i} with searchable content about machine learning, artificial intelligence, and data science.",
                processed_at=time.time(),
                organization_id=org.id,
                uploaded_by_user_id=user.id
            )
            db_session.add(doc)
            documents.append(doc)

        db_session.commit()

        return {
            "organization": org,
            "user": user,
            "documents": documents,
            "auth_headers": {"Authorization": f"Bearer {create_access_token(data={'sub': str(user.id)})}"}
        }

    def test_health_check_performance(self):
        """Test health check endpoint performance"""
        runner = LoadTestRunner()

        config = LoadTestConfig(
            concurrent_users=50,
            requests_per_user=10,
            ramp_up_time=1.0,
            test_duration=10.0,
            endpoint="/health"
        )

        metrics = runner.execute_load_test(config)

        # Health check should be very fast
        assert metrics.avg_response_time < 100  # < 100ms
        assert metrics.p95_response_time < 200  # < 200ms
        assert metrics.requests_per_second > 100  # > 100 RPS
        assert metrics.error_rate == 0.0

    def test_document_list_performance(self, test_data):
        """Test document listing performance"""
        runner = LoadTestRunner()

        config = LoadTestConfig(
            concurrent_users=20,
            requests_per_user=15,
            ramp_up_time=2.0,
            test_duration=15.0,
            endpoint="/api/v1/documents?limit=20",
            headers=test_data["auth_headers"]
        )

        metrics = runner.execute_load_test(config)

        # Document listing should be reasonably fast
        assert metrics.avg_response_time < 500  # < 500ms
        assert metrics.p95_response_time < 1000  # < 1s
        assert metrics.error_rate < 5.0  # < 5% error rate

    def test_document_search_performance(self, test_data):
        """Test document search performance"""
        runner = LoadTestRunner()

        config = LoadTestConfig(
            concurrent_users=15,
            requests_per_user=10,
            ramp_up_time=2.0,
            test_duration=20.0,
            endpoint="/api/v1/documents/search?query=machine learning&limit=10",
            headers=test_data["auth_headers"]
        )

        metrics = runner.execute_load_test(config)

        # Search should be optimized for speed
        assert metrics.avg_response_time < 800  # < 800ms
        assert metrics.p95_response_time < 1500  # < 1.5s
        assert metrics.error_rate < 10.0  # < 10% error rate

    def test_concurrent_document_upload_simulation(self, test_data, temp_upload_dir):
        """Test concurrent document upload simulation"""
        runner = LoadTestRunner()

        # Create test files
        test_files = []
        for i in range(20):
            file_path = os.path.join(temp_upload_dir, f"upload_test_{i}.txt")
            with open(file_path, "w") as f:
                f.write(f"Upload test file {i} with content for performance testing.")
            test_files.append(file_path)

        # Test upload performance (simulation)
        # Note: This simulates upload calls since we can't easily upload files in load tests
        config = LoadTestConfig(
            concurrent_users=10,
            requests_per_user=5,
            ramp_up_time=3.0,
            test_duration=30.0,
            endpoint="/api/v1/documents",  # This would normally be a POST with file
            method="GET",  # Simulated as GET for load testing
            headers=test_data["auth_headers"]
        )

        metrics = runner.execute_load_test(config)

        # Upload endpoints should handle moderate load
        assert metrics.avg_response_time < 2000  # < 2s
        assert metrics.error_rate < 15.0  # < 15% error rate (uploads can be resource-intensive)

    def test_authentication_performance(self):
        """Test authentication endpoint performance"""
        runner = LoadTestRunner()

        # Test login performance
        config = LoadTestConfig(
            concurrent_users=30,
            requests_per_user=8,
            ramp_up_time=2.0,
            test_duration=15.0,
            endpoint="/api/v1/auth/login",
            method="POST",
            payload={
                "email": "perf@test.com",
                "password": "testpassword123"
            }
        )

        metrics = runner.execute_load_test(config)

        # Authentication should be fast
        assert metrics.avg_response_time < 300  # < 300ms
        assert metrics.p95_response_time < 600  # < 600ms
        assert metrics.error_rate < 5.0  # < 5% error rate

    def test_memory_usage_under_load(self, test_data):
        """Test memory usage under sustained load"""
        runner = LoadTestRunner()

        # Monitor initial memory
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024

        config = LoadTestConfig(
            concurrent_users=25,
            requests_per_user=20,
            ramp_up_time=3.0,
            test_duration=60.0,  # Longer test to detect memory leaks
            endpoint="/api/v1/documents/search?query=test&limit=10",
            headers=test_data["auth_headers"]
        )

        metrics = runner.execute_load_test(config)

        # Check final memory
        final_memory = psutil.Process().memory_info().rss / 1024 / 1024
        memory_increase = final_memory - initial_memory

        print(f"Memory usage: {initial_memory:.2f}MB -> {final_memory:.2f}MB (+{memory_increase:.2f}MB)")

        # Memory increase should be reasonable (< 100MB for this test)
        assert memory_increase < 100, f"Memory increased by {memory_increase:.2f}MB, possible memory leak"

        # Force garbage collection
        gc.collect()


class TestDatabasePerformance:
    """Test database performance under load"""

    @pytest.fixture(scope="class")
    def db_engine(self):
        """Create test database engine"""
        test_db_url = settings.DATABASE_URL.replace("/rag", "/rag_perf_test")
        engine = create_engine(test_db_url, pool_size=20, max_overflow=30)
        yield engine
        engine.dispose()

    def test_database_connection_pool_performance(self, db_engine):
        """Test database connection pool performance under load"""
        def db_query():
            with db_engine.connect() as conn:
                result = conn.execute(text("SELECT 1, pg_sleep(0.01)"))  # Small delay
                return result.fetchone()

        # Test concurrent database queries
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(db_query) for _ in range(100)]
            results = [future.result() for future in as_completed(futures)]
        end_time = time.time()

        assert len(results) == 100
        assert all(result[0] == 1 for result in results)
        assert (end_time - start_time) < 10.0  # Should complete within 10 seconds

    def test_database_query_performance(self, db_session, test_data):
        """Test database query performance"""
        # Test document query performance
        start_time = time.time()
        documents = db_session.query(Document).filter(
            Document.organization_id == test_data["organization"].id
        ).limit(50).all()
        query_time = (time.time() - start_time) * 1000

        assert len(documents) > 0
        assert query_time < 100  # Query should complete in < 100ms

        # Test entity query performance
        start_time = time.time()
        entities = db_session.query(Entity).join(Document).filter(
            Document.organization_id == test_data["organization"].id
        ).limit(100).all()
        entity_query_time = (time.time() - start_time) * 1000

        assert entity_query_time < 150  # Entity query should complete in < 150ms

    def test_concurrent_database_operations(self, db_session, test_data):
        """Test concurrent database read/write operations"""
        def create_test_document(i):
            doc = Document(
                title=f"Concurrent Test Document {i}",
                filename=f"concurrent_test_{i}.txt",
                file_path=f"/test/concurrent_test_{i}.txt",
                file_size_bytes=512,
                mime_type="text/plain",
                document_type=DocumentType.TEXT,
                processing_status=ProcessingStatus.COMPLETED,
                content_text=f"Concurrent test document {i}",
                organization_id=test_data["organization"].id,
                uploaded_by_user_id=test_data["user"].id
            )
            db_session.add(doc)
            db_session.commit()
            return doc.id

        def read_documents():
            return db_session.query(Document).filter(
                Document.organization_id == test_data["organization"].id
            ).count()

        # Test concurrent writes
        with ThreadPoolExecutor(max_workers=20) as executor:
            write_futures = [executor.submit(create_test_document, i) for i in range(50)]
            write_results = [future.result() for future in as_completed(write_futures)]

        assert len(write_results) == 50
        assert all(result is not None for result in write_results)

        # Test concurrent reads
        with ThreadPoolExecutor(max_workers=30) as executor:
            read_futures = [executor.submit(read_documents) for _ in range(100)]
            read_results = [future.result() for future in as_completed(read_futures)]

        assert len(read_results) == 100
        assert all(result >= 50 for result in read_results)  # Should find at least the documents we created


class TestScalabilityLimits:
    """Test system scalability limits and breaking points"""

    def test_api_scalability_limits(self, test_data):
        """Find API scalability limits through stress testing"""
        runner = LoadTestRunner()

        # Start with moderate load and increase until breaking point
        max_users = 200
        step_size = 25

        stress_results = runner.execute_stress_test(
            endpoint="/api/v1/documents/search?query=test&limit=5",
            max_users=max_users,
            step_size=step_size
        )

        # Analyze results to find breaking point
        breaking_point = None
        for i, metrics in enumerate(stress_results):
            users = (i + 1) * step_size
            print(f"Users: {users}, RPS: {metrics.requests_per_second:.2f}, "
                  f"Error Rate: {metrics.error_rate:.2f}%, "
                  f"Avg Response: {metrics.avg_response_time:.2f}ms")

            # Define breaking point criteria
            if (metrics.error_rate > 25.0 or  # > 25% errors
                metrics.avg_response_time > 5000 or  # > 5s average response
                metrics.p95_response_time > 10000):  # > 10s 95th percentile
                breaking_point = users
                break

        if breaking_point:
            print(f"System breaking point detected at approximately {breaking_point} concurrent users")
        else:
            print(f"System handled up to {max_users} concurrent users without breaking")

        # System should handle at least 50 concurrent users
        assert len(stress_results) >= 2, "System should handle at least 50 concurrent users"

        # First test (25 users) should pass comfortably
        assert stress_results[0].error_rate < 10.0
        assert stress_results[0].avg_response_time < 2000

    def test_memory_scalability(self, test_data):
        """Test memory usage scales linearly with load"""
        runner = LoadTestRunner()

        # Test memory usage at different load levels
        load_levels = [5, 15, 30]
        memory_usage = []

        for users in load_levels:
            config = LoadTestConfig(
                concurrent_users=users,
                requests_per_user=10,
                ramp_up_time=1.0,
                test_duration=15.0,
                endpoint="/api/v1/documents?limit=10",
                headers=test_data["auth_headers"]
            )

            # Force garbage collection before test
            gc.collect()
            initial_memory = psutil.Process().memory_info().rss / 1024 / 1024

            metrics = runner.execute_load_test(config)

            final_memory = psutil.Process().memory_info().rss / 1024 / 1024
            memory_increase = final_memory - initial_memory

            memory_usage.append({
                'users': users,
                'memory_increase': memory_increase,
                'memory_per_user': memory_increase / users
            })

            print(f"Users: {users}, Memory Increase: {memory_increase:.2f}MB "
                  f"({memory_increase/users:.2f}MB per user)")

        # Memory usage should scale reasonably (not exponentially)
        if len(memory_usage) >= 2:
            # Check that memory per user doesn't increase dramatically
            memory_per_user_low = memory_usage[0]['memory_per_user']
            memory_per_user_high = memory_usage[-1]['memory_per_user']
            ratio = memory_per_user_high / memory_per_user_low

            assert ratio < 3.0, f"Memory per user increased by factor {ratio:.2f}, may indicate memory leak"

    def test_response_time_degradation(self, test_data):
        """Test how response times degrade under increasing load"""
        runner = LoadTestRunner()

        load_levels = [1, 5, 10, 20]
        response_times = []

        for users in load_levels:
            config = LoadTestConfig(
                concurrent_users=users,
                requests_per_user=15,
                ramp_up_time=1.0,
                test_duration=20.0,
                endpoint="/api/v1/documents/search?query=machine learning&limit=10",
                headers=test_data["auth_headers"]
            )

            metrics = runner.execute_load_test(config)
            response_times.append({
                'users': users,
                'avg_response': metrics.avg_response_time,
                'p95_response': metrics.p95_response_time
            })

            print(f"Users: {users}, Avg Response: {metrics.avg_response_time:.2f}ms, "
                  f"P95: {metrics.p95_response_time:.2f}ms")

        # Response times should degrade gracefully (not exponentially)
        if len(response_times) >= 2:
            baseline_response = response_times[0]['avg_response']
            max_response = max(rt['avg_response'] for rt in response_times)
            degradation_factor = max_response / baseline_response

            assert degradation_factor < 10.0, f"Response time degraded by factor {degradation_factor:.2f}"


class TestPerformanceRegression:
    """Test for performance regressions compared to baselines"""

    @pytest.mark.performance_regression
    def test_document_search_performance_regression(self, test_data):
        """Test document search performance against baseline"""
        runner = LoadTestRunner()

        config = LoadTestConfig(
            concurrent_users=10,
            requests_per_user=20,
            ramp_up_time=2.0,
            test_duration=30.0,
            endpoint="/api/v1/documents/search?query=test&limit=20",
            headers=test_data["auth_headers"]
        )

        metrics = runner.execute_load_test(config)

        # Performance baselines (these should be updated based on actual system capabilities)
        baselines = {
            'avg_response_time_ms': 400,
            'p95_response_time_ms': 800,
            'requests_per_second': 25,
            'error_rate_percent': 5.0
        }

        # Check against baselines with some tolerance
        assert metrics.avg_response_time < baselines['avg_response_time_ms'] * 1.2, \
            f"Average response time regression: {metrics.avg_response_time:.2f}ms vs baseline {baselines['avg_response_time_ms']}ms"

        assert metrics.p95_response_time < baselines['p95_response_time_ms'] * 1.3, \
            f"P95 response time regression: {metrics.p95_response_time:.2f}ms vs baseline {baselines['p95_response_time_ms']}ms"

        assert metrics.requests_per_second > baselines['requests_per_second'] * 0.8, \
            f"Throughput regression: {metrics.requests_per_second:.2f} RPS vs baseline {baselines['requests_per_second']} RPS"

        assert metrics.error_rate < baselines['error_rate_percent'] * 1.5, \
            f"Error rate regression: {metrics.error_rate:.2f}% vs baseline {baselines['error_rate_percent']}%"

    @pytest.mark.performance_regression
    def test_authentication_performance_regression(self):
        """Test authentication performance against baseline"""
        runner = LoadTestRunner()

        config = LoadTestConfig(
            concurrent_users=15,
            requests_per_user=10,
            ramp_up_time=1.5,
            test_duration=20.0,
            endpoint="/api/v1/auth/login",
            method="POST",
            payload={
                "email": "perf@test.com",
                "password": "testpassword123"
            }
        )

        metrics = runner.execute_load_test(config)

        # Authentication should be very fast
        baselines = {
            'avg_response_time_ms': 200,
            'p95_response_time_ms': 400,
            'requests_per_second': 50,
            'error_rate_percent': 2.0
        }

        assert metrics.avg_response_time < baselines['avg_response_time_ms'] * 1.2
        assert metrics.p95_response_time < baselines['p95_response_time_ms'] * 1.3
        assert metrics.requests_per_second > baselines['requests_per_second'] * 0.8
        assert metrics.error_rate < baselines['error_rate_percent'] * 2.0


# Performance test utilities and helpers
def generate_performance_report(test_results: List[PerformanceMetrics]) -> str:
    """Generate a performance test report"""
    report = ["# Performance Test Report\n"]
    report.append(f"Generated: {datetime.now().isoformat()}\n")

    for metrics in test_results:
        report.append(f"## {metrics.operation}\n")
        report.append(f"- Total Requests: {metrics.total_requests}")
        report.append(f"- Success Rate: {((metrics.successful_requests/metrics.total_requests)*100):.2f}%")
        report.append(f"- Average Response Time: {metrics.avg_response_time:.2f}ms")
        report.append(f"- 95th Percentile: {metrics.p95_response_time:.2f}ms")
        report.append(f"- 99th Percentile: {metrics.p99_response_time:.2f}ms")
        report.append(f"- Requests/Second: {metrics.requests_per_second:.2f}")
        report.append(f"- Error Rate: {metrics.error_rate:.2f}%")
        report.append(f"- Memory Usage: {metrics.memory_usage_mb:.2f}MB")
        report.append(f"- CPU Usage: {metrics.cpu_usage_percent:.2f}%\n")

    return "\n".join(report)


if __name__ == "__main__":
    # Run performance tests manually
    pytest.main([__file__, "-v", "-s", "--tb=short"])