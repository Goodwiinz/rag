"""
Performance tests for critical API endpoints
"""

import pytest
import asyncio
import time
import statistics
from unittest.mock import Mock, patch
from concurrent.futures import ThreadPoolExecutor
import psutil
import gc
from typing import List, Dict, Any

from conftest_fastapi import *


class TestEndpointPerformance:
    """Performance tests for API endpoints"""

    @pytest.fixture
    def performance_thresholds(self):
        """Performance thresholds for endpoints"""
        return {
            "search_response_time": 2.0,  # 2 seconds
            "auth_response_time": 1.0,    # 1 second
            "document_upload_time": 5.0,  # 5 seconds
            "document_list_time": 1.5,    # 1.5 seconds
            "health_check_time": 0.5,     # 0.5 seconds
            "max_memory_usage_mb": 500,   # 500 MB
            "max_cpu_usage_percent": 80    # 80%
        }

    @pytest.fixture
    def performance_monitor(self):
        """Monitor system performance during tests"""
        class PerformanceMonitor:
            def __init__(self):
                self.process = psutil.Process()
                self.measurements = []

            def start_measurement(self):
                """Start performance measurement"""
                gc.collect()  # Clean up before measurement
                self.start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
                self.start_cpu_percent = self.process.cpu_percent()
                self.start_time = time.time()

            def end_measurement(self) -> Dict[str, float]:
                """End measurement and return metrics"""
                end_time = time.time()
                end_memory = self.process.memory_info().rss / 1024 / 1024  # MB
                end_cpu_percent = self.process.cpu_percent()

                metrics = {
                    "duration": end_time - self.start_time,
                    "memory_used": end_memory,
                    "memory_delta": end_memory - self.start_memory,
                    "cpu_percent": end_cpu_percent,
                    "peak_memory": end_memory
                }

                self.measurements.append(metrics)
                return metrics

            def get_summary(self) -> Dict[str, float]:
                """Get performance summary"""
                if not self.measurements:
                    return {}

                durations = [m["duration"] for m in self.measurements]
                memory_deltas = [m["memory_delta"] for m in self.measurements]
                peak_memories = [m["peak_memory"] for m in self.measurements]

                return {
                    "avg_duration": statistics.mean(durations),
                    "max_duration": max(durations),
                    "min_duration": min(durations),
                    "avg_memory_delta": statistics.mean(memory_deltas),
                    "max_memory_delta": max(memory_deltas),
                    "max_peak_memory": max(peak_memories),
                    "total_requests": len(self.measurements)
                }

        return PerformanceMonitor()

    @pytest.mark.performance
    @pytest.mark.slow
    def test_search_endpoint_performance(self, test_client: TestClient, hybrid_search_service_mock, sample_search_results, mock_auth_headers, performance_monitor, performance_thresholds):
        """Test search endpoint performance under load"""
        # Setup mock response
        hybrid_search_service_mock.search.return_value = {
            "results": sample_search_results,
            "total": len(sample_search_results),
            "search_metadata": {
                "search_type": "hybrid",
                "execution_time_ms": 100
            }
        }

        search_data = {
            "query": "machine learning",
            "search_type": "hybrid",
            "limit": 10
        }

        # Test multiple concurrent requests
        async def make_request():
            performance_monitor.start_measurement()
            response = test_client.post("/api/v1/search/", json=search_data, headers=mock_auth_headers)
            metrics = performance_monitor.end_measurement()
            return response, metrics

        # Run concurrent requests
        async def run_concurrent_requests(num_requests: int = 20):
            tasks = [make_request() for _ in range(num_requests)]
            return await asyncio.gather(*tasks)

        # Execute performance test
        loop = asyncio.get_event_loop()
        results = loop.run_until_complete(run_concurrent_requests())

        # Analyze results
        responses = [r[0] for r in results]
        metrics_list = [r[1] for r in results]

        # All requests should succeed
        assert all(r.status_code == 200 for r in responses)

        # Check performance thresholds
        summary = performance_monitor.get_summary()
        assert summary["avg_duration"] < performance_thresholds["search_response_time"]
        assert summary["max_duration"] < performance_thresholds["search_response_time"] * 2
        assert summary["max_peak_memory"] < performance_thresholds["max_memory_usage_mb"]

        print(f"Search Performance Summary:")
        print(f"  Average response time: {summary['avg_duration']:.3f}s")
        print(f"  Max response time: {summary['max_duration']:.3f}s")
        print(f"  Peak memory usage: {summary['max_peak_memory']:.1f} MB")
        print(f"  Total requests: {summary['total_requests']}")

    @pytest.mark.performance
    @pytest.mark.slow
    def test_auth_endpoint_performance(self, test_client: TestClient, auth_service_mock, mock_user, mock_auth_headers, performance_monitor, performance_thresholds):
        """Test authentication endpoint performance"""
        # Setup mock responses
        auth_service_mock.authenticate_user.return_value = mock_user
        auth_service_mock.create_access_token.return_value = "test-token"
        auth_service_mock.create_refresh_token.return_value = "refresh-token"

        login_data = {
            "email": "test@example.com",
            "password": "testpassword"
        }

        # Test login performance
        async def test_login():
            performance_monitor.start_measurement()
            response = test_client.post("/api/v1/auth/login", json=login_data)
            metrics = performance_monitor.end_measurement()
            return response, metrics

        # Run multiple login attempts
        async def run_login_tests(num_attempts: int = 50):
            tasks = [test_login() for _ in range(num_attempts)]
            return await asyncio.gather(*tasks)

        # Execute performance test
        loop = asyncio.get_event_loop()
        results = loop.run_until_complete(run_login_tests())

        # Analyze results
        responses = [r[0] for r in results]
        metrics_list = [r[1] for r in results]

        # All requests should succeed
        assert all(r.status_code == 200 for r in responses)

        # Check performance thresholds
        summary = performance_monitor.get_summary()
        assert summary["avg_duration"] < performance_thresholds["auth_response_time"]
        assert summary["max_duration"] < performance_thresholds["auth_response_time"] * 2

        print(f"Auth Performance Summary:")
        print(f"  Average login time: {summary['avg_duration']:.3f}s")
        print(f"  Max login time: {summary['max_duration']:.3f}s")
        print(f"  Total login attempts: {summary['total_requests']}")

    @pytest.mark.performance
    @pytest.mark.slow
    def test_document_list_performance(self, test_client: TestClient, document_service_mock, sample_documents_data, mock_auth_headers, performance_monitor, performance_thresholds):
        """Test document list endpoint performance"""
        # Setup mock response with pagination
        def mock_get_documents(*args, **kwargs):
            # Simulate larger dataset
            large_dataset = []
            for i in range(1000):
                doc = {
                    "id": f"doc-{i}",
                    "title": f"Document {i}",
                    "created_at": "2024-01-01T10:00:00Z",
                    "size": 1024 * i
                }
                large_dataset.append(doc)

            return {
                "documents": large_dataset,
                "total": len(large_dataset),
                "page": 1,
                "per_page": 50,
                "total_pages": 20
            }

        document_service_mock.get_documents.side_effect = mock_get_documents

        # Test different page sizes
        page_sizes = [10, 50, 100]

        for page_size in page_sizes:
            performance_monitor.measurements = []  # Reset for each test

            async def test_pagination():
                performance_monitor.start_measurement()
                response = test_client.get(
                    f"/api/v1/documents/",
                    params={"limit": page_size, "offset": 0},
                    headers=mock_auth_headers
                )
                metrics = performance_monitor.end_measurement()
                return response, metrics

            # Run multiple requests for each page size
            async def run_pagination_tests(num_requests: int = 10):
                tasks = [test_pagination() for _ in range(num_requests)]
                return await asyncio.gather(*tasks)

            loop = asyncio.get_event_loop()
            results = loop.run_until_complete(run_pagination_tests())

            # Analyze results
            responses = [r[0] for r in results]
            summary = performance_monitor.get_summary()

            # All requests should succeed
            assert all(r.status_code == 200 for r in responses)

            # Check performance thresholds
            assert summary["avg_duration"] < performance_thresholds["document_list_time"]

            print(f"Document List Performance (page_size={page_size}):")
            print(f"  Average response time: {summary['avg_duration']:.3f}s")
            print(f"  Max response time: {summary['max_duration']:.3f}s")

    @pytest.mark.performance
    @pytest.mark.slow
    def test_concurrent_mixed_requests(self, test_client: TestClient, hybrid_search_service_mock, auth_service_mock, document_service_mock, sample_search_results, mock_user, mock_auth_headers, performance_monitor):
        """Test performance with mixed concurrent requests"""
        # Setup mocks
        hybrid_search_service_mock.search.return_value = {
            "results": sample_search_results,
            "total": len(sample_search_results)
        }
        auth_service_mock.authenticate_user.return_value = mock_user
        auth_service_mock.create_access_token.return_value = "test-token"
        auth_service_mock.create_refresh_token.return_value = "refresh-token"

        document_service_mock.get_documents.return_value = {
            "documents": [],
            "total": 0
        }

        async def make_search_request():
            performance_monitor.start_measurement()
            response = test_client.post(
                "/api/v1/search/",
                json={"query": "test", "search_type": "hybrid"},
                headers=mock_auth_headers
            )
            metrics = performance_monitor.end_measurement()
            return response, metrics

        async def make_auth_request():
            performance_monitor.start_measurement()
            response = test_client.post(
                "/api/v1/auth/login",
                json={"email": "test@example.com", "password": "testpassword"}
            )
            metrics = performance_monitor.end_measurement()
            return response, metrics

        async def make_document_request():
            performance_monitor.start_measurement()
            response = test_client.get("/api/v1/documents/", headers=mock_auth_headers)
            metrics = performance_monitor.end_measurement()
            return response, metrics

        # Mix different types of requests
        async def run_mixed_requests():
            tasks = []
            # Add 20 search requests
            tasks.extend([make_search_request() for _ in range(20)])
            # Add 10 auth requests
            tasks.extend([make_auth_request() for _ in range(10)])
            # Add 15 document requests
            tasks.extend([make_document_request() for _ in range(15)])

            return await asyncio.gather(*tasks)

        # Execute performance test
        loop = asyncio.get_event_loop()
        start_time = time.time()
        results = loop.run_until_complete(run_mixed_requests())
        total_time = time.time() - start_time

        # Analyze results
        responses = [r[0] for r in results]
        metrics_list = [r[1] for r in results]

        # All requests should succeed
        assert all(r.status_code in [200, 201] for r in responses)

        summary = performance_monitor.get_summary()

        print(f"Mixed Requests Performance Summary:")
        print(f"  Total requests: {len(responses)}")
        print(f"  Total time: {total_time:.3f}s")
        print(f"  Requests per second: {len(responses) / total_time:.2f}")
        print(f"  Average response time: {summary['avg_duration']:.3f}s")
        print(f"  Peak memory usage: {summary['max_peak_memory']:.1f} MB")

        # Performance assertions
        assert summary["avg_duration"] < 3.0  # Average response time under 3 seconds
        assert len(responses) / total_time > 10  # At least 10 requests per second

    @pytest.mark.performance
    def test_health_check_performance(self, test_client: TestClient, performance_monitor, performance_thresholds):
        """Test health check endpoint performance"""
        async def test_health_check():
            performance_monitor.start_measurement()
            response = test_client.get("/health")
            metrics = performance_monitor.end_measurement()
            return response, metrics

        # Run multiple health checks
        async def run_health_checks(num_checks: int = 100):
            tasks = [test_health_check() for _ in range(num_checks)]
            return await asyncio.gather(*tasks)

        loop = asyncio.get_event_loop()
        results = loop.run_until_complete(run_health_checks())

        # Analyze results
        responses = [r[0] for r in results]
        summary = performance_monitor.get_summary()

        # All requests should succeed
        assert all(r.status_code == 200 for r in responses)

        # Health check should be very fast
        assert summary["avg_duration"] < performance_thresholds["health_check_time"]
        assert summary["max_duration"] < performance_thresholds["health_check_time"] * 2

        print(f"Health Check Performance Summary:")
        print(f"  Average response time: {summary['avg_duration']:.4f}s")
        print(f"  Max response time: {summary['max_duration']:.4f}s")
        print(f"  Total health checks: {summary['total_requests']}")

    @pytest.mark.performance
    @pytest.mark.slow
    def test_memory_leak_detection(self, test_client: TestClient, hybrid_search_service_mock, sample_search_results, mock_auth_headers, performance_monitor):
        """Test for memory leaks during repeated requests"""
        hybrid_search_service_mock.search.return_value = {
            "results": sample_search_results,
            "total": len(sample_search_results)
        }

        search_data = {
            "query": "memory leak test",
            "search_type": "hybrid"
        }

        # Run many requests to detect memory leaks
        initial_memory = None
        memory_samples = []

        for batch in range(10):  # 10 batches of 50 requests each
            async def make_batch_requests():
                tasks = []
                for _ in range(50):
                    performance_monitor.start_measurement()
                    response = test_client.post("/api/v1/search/", json=search_data, headers=mock_auth_headers)
                    metrics = performance_monitor.end_measurement()
                    tasks.append((response, metrics))

                return await asyncio.gather(*tasks)

            loop = asyncio.get_event_loop()
            results = loop.run_until_complete(make_batch_requests())

            # Collect memory sample
            current_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            if initial_memory is None:
                initial_memory = current_memory
            memory_samples.append(current_memory)

            # Force garbage collection
            gc.collect()

            print(f"Batch {batch + 1}: Memory usage = {current_memory:.1f} MB")

            # Small delay between batches
            time.sleep(0.1)

        # Analyze memory growth
        final_memory = memory_samples[-1]
        memory_growth = final_memory - initial_memory

        print(f"Memory Leak Analysis:")
        print(f"  Initial memory: {initial_memory:.1f} MB")
        print(f"  Final memory: {final_memory:.1f} MB")
        print(f"  Memory growth: {memory_growth:.1f} MB")
        print(f"  Requests processed: {10 * 50}")

        # Memory growth should be minimal (less than 50MB)
        assert memory_growth < 50, f"Potential memory leak detected: {memory_growth:.1f} MB growth"

    @pytest.mark.performance
    @pytest.mark.slow
    def test_database_connection_pool_performance(self, mock_db_engine, performance_monitor):
        """Test database connection pool performance"""
        # Test concurrent database connections
        async def make_database_query():
            performance_monitor.start_measurement()
            with mock_db_engine.connect() as conn:
                result = conn.execute(text("SELECT 1, pg_sleep(0.01)"))
                row = result.fetchone()
            metrics = performance_monitor.end_measurement()
            return row, metrics

        # Run concurrent database queries
        async def run_database_queries(num_queries: int = 20):
            tasks = [make_database_query() for _ in range(num_queries)]
            return await asyncio.gather(*tasks)

        loop = asyncio.get_event_loop()
        results = loop.run_until_complete(run_database_queries())

        # Analyze results
        queries = [r[0] for r in results]
        metrics_list = [r[1] for r in results]

        # All queries should succeed
        assert all(q[0] == 1 for q in queries)

        summary = performance_monitor.get_summary()

        print(f"Database Connection Pool Performance:")
        print(f"  Average query time: {summary['avg_duration']:.3f}s")
        print(f"  Max query time: {summary['max_duration']:.3f}s")
        print(f"  Total queries: {summary['total_requests']}")

        # Queries should complete reasonably fast
        assert summary["avg_duration"] < 0.5  # Under 500ms average

    @pytest.mark.performance
    def test_cache_performance(self, mock_redis_client, performance_monitor):
        """Test Redis cache performance"""
        # Setup mock responses
        mock_redis_client.get.return_value = b"cached_value"
        mock_redis_client.set.return_value = True

        # Test cache operations
        async def cache_operations():
            # Test set operation
            performance_monitor.start_measurement()
            mock_redis_client.set("test_key", "test_value", ex=3600)
            set_metrics = performance_monitor.end_measurement()

            # Test get operation
            performance_monitor.start_measurement()
            result = mock_redis_client.get("test_key")
            get_metrics = performance_monitor.end_measurement()

            return set_metrics, get_metrics

        # Run multiple cache operations
        async def run_cache_operations(num_operations: int = 100):
            tasks = [cache_operations() for _ in range(num_operations)]
            return await asyncio.gather(*tasks)

        loop = asyncio.get_event_loop()
        results = loop.run_until_complete(run_cache_operations())

        # Analyze set operations
        set_metrics_list = [r[0] for r in results]
        get_metrics_list = [r[1] for r in results]

        avg_set_time = statistics.mean([m["duration"] for m in set_metrics_list])
        avg_get_time = statistics.mean([m["duration"] for m in get_metrics_list])

        print(f"Cache Performance Summary:")
        print(f"  Average SET time: {avg_set_time:.6f}s")
        print(f"  Average GET time: {avg_get_time:.6f}s")
        print(f"  Total operations: {len(results) * 2}")

        # Cache operations should be very fast
        assert avg_set_time < 0.001  # Under 1ms
        assert avg_get_time < 0.001  # Under 1ms

    @pytest.mark.performance
    @pytest.mark.slow
    def test_embedding_generation_performance(self, mock_embeddings_service, performance_monitor):
        """Test embedding generation performance"""
        # Setup mock responses
        mock_embeddings_service.embed_query.return_value = [0.1, 0.2, 0.3] * 128  # 384-dim vector

        # Test embedding generation for different text sizes
        test_texts = [
            "Short text",
            "This is a medium length text that contains multiple sentences and should take slightly longer to process.",
            "This is a very long text that contains many words and sentences. " * 20  # Much longer text
        ]

        for i, text in enumerate(test_texts):
            performance_monitor.measurements = []  # Reset for each test

            async def generate_embeddings():
                performance_monitor.start_measurement()
                embedding = mock_embeddings_service.embed_query(text)
                metrics = performance_monitor.end_measurement()
                return embedding, metrics

            # Run multiple embedding generations
            async def run_embedding_tests(num_tests: int = 10):
                tasks = [generate_embeddings() for _ in range(num_tests)]
                return await asyncio.gather(*tasks)

            loop = asyncio.get_event_loop()
            results = loop.run_until_complete(run_embedding_tests())

            # Analyze results
            embeddings = [r[0] for r in results]
            summary = performance_monitor.get_summary()

            # All embeddings should be valid
            assert all(len(emb) == 384 for emb in embeddings)

            text_type = ["short", "medium", "long"][i]
            print(f"Embedding Generation Performance ({text_type} text):")
            print(f"  Text length: {len(text)} chars")
            print(f"  Average time: {summary['avg_duration']:.4f}s")
            print(f"  Max time: {summary['max_duration']:.4f}s")

            # Performance should be reasonable
            assert summary["avg_duration"] < 1.0  # Under 1 second average