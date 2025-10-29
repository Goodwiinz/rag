"""
Load testing scenarios for the RAG system
"""

import pytest
import asyncio
import time
import statistics
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock, patch
import psutil
import random
from typing import List, Dict, Any
import json

from conftest_fastapi import *


class TestLoadScenarios:
    """Load testing scenarios for system under stress"""

    @pytest.fixture
    def load_test_config(self):
        """Configuration for load tests"""
        return {
            "max_concurrent_users": 100,
            "ramp_up_time": 30,  # seconds
            "test_duration": 120,  # seconds
            "think_time": (1, 3),  # random think time between requests
            "success_rate_threshold": 0.95,  # 95% success rate
            "avg_response_time_threshold": 5.0,  # 5 seconds
            "error_rate_threshold": 0.05,  # 5% error rate
        }

    @pytest.fixture
    def load_test_results(self):
        """Store load test results"""
        return {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "response_times": [],
            "errors": [],
            "throughput": 0,
            "avg_cpu_usage": 0,
            "peak_memory_usage": 0,
        }

    class LoadTestUser:
        """Simulates a user performing load test operations"""

        def __init__(self, user_id: int, test_client: TestClient, auth_headers: Dict[str, str]):
            self.user_id = user_id
            self.test_client = test_client
            self.auth_headers = auth_headers
            self.results = {"requests": 0, "successes": 0, "failures": 0, "response_times": [], "errors": []}

        def perform_search(self, query: str = None) -> Dict[str, Any]:
            """Perform a search request"""
            if query is None:
                query = f"search query {random.randint(1, 1000)}"

            start_time = time.time()
            try:
                response = self.test_client.post(
                    "/api/v1/search/",
                    json={
                        "query": query,
                        "search_type": "hybrid",
                        "limit": random.randint(5, 20)
                    },
                    headers=self.auth_headers
                )
                response_time = time.time() - start_time

                self.results["requests"] += 1
                if response.status_code == 200:
                    self.results["successes"] += 1
                else:
                    self.results["failures"] += 1
                    self.results["errors"].append(f"Search failed: {response.status_code}")

                self.results["response_times"].append(response_time)
                return {"success": response.status_code == 200, "response_time": response_time}

            except Exception as e:
                response_time = time.time() - start_time
                self.results["requests"] += 1
                self.results["failures"] += 1
                self.results["errors"].append(f"Search exception: {str(e)}")
                self.results["response_times"].append(response_time)
                return {"success": False, "response_time": response_time, "error": str(e)}

        def perform_document_list(self) -> Dict[str, Any]:
            """Perform a document list request"""
            start_time = time.time()
            try:
                response = self.test_client.get(
                    "/api/v1/documents/",
                    params={
                        "limit": random.randint(10, 50),
                        "offset": random.randint(0, 100)
                    },
                    headers=self.auth_headers
                )
                response_time = time.time() - start_time

                self.results["requests"] += 1
                if response.status_code == 200:
                    self.results["successes"] += 1
                else:
                    self.results["failures"] += 1
                    self.results["errors"].append(f"Document list failed: {response.status_code}")

                self.results["response_times"].append(response_time)
                return {"success": response.status_code == 200, "response_time": response_time}

            except Exception as e:
                response_time = time.time() - start_time
                self.results["requests"] += 1
                self.results["failures"] += 1
                self.results["errors"].append(f"Document list exception: {str(e)}")
                self.results["response_times"].append(response_time)
                return {"success": False, "response_time": response_time, "error": str(e)}

        def perform_health_check(self) -> Dict[str, Any]:
            """Perform a health check request"""
            start_time = time.time()
            try:
                response = self.test_client.get("/health")
                response_time = time.time() - start_time

                self.results["requests"] += 1
                if response.status_code == 200:
                    self.results["successes"] += 1
                else:
                    self.results["failures"] += 1
                    self.results["errors"].append(f"Health check failed: {response.status_code}")

                self.results["response_times"].append(response_time)
                return {"success": response.status_code == 200, "response_time": response_time}

            except Exception as e:
                response_time = time.time() - start_time
                self.results["requests"] += 1
                self.results["failures"] += 1
                self.results["errors"].append(f"Health check exception: {str(e)}")
                self.results["response_times"].append(response_time)
                return {"success": False, "response_time": response_time, "error": str(e)}

        def simulate_user_session(self, duration: int, min_think: int = 1, max_think: int = 3):
            """Simulate a user session with random requests"""
            end_time = time.time() + duration

            while time.time() < end_time:
                # Choose random operation
                operation = random.choice(["search", "documents", "health"])

                if operation == "search":
                    self.perform_search()
                elif operation == "documents":
                    self.perform_document_list()
                else:
                    self.perform_health_check()

                # Random think time
                think_time = random.uniform(min_think, max_think)
                time.sleep(think_time)

    @pytest.mark.performance
    @pytest.mark.slow
    @pytest.mark.load
    def test_sustained_load_search_heavy(self, test_client: TestClient, hybrid_search_service_mock, sample_search_results, mock_auth_headers, load_test_config, load_test_results):
        """Test sustained load with search-heavy workload"""
        # Setup mock response
        hybrid_search_service_mock.search.return_value = {
            "results": sample_search_results,
            "total": len(sample_search_results),
            "search_metadata": {"execution_time_ms": random.randint(50, 200)}
        }

        num_users = 50
        test_duration = 60  # 1 minute

        print(f"Starting sustained load test: {num_users} users for {test_duration}s")

        # Create users
        users = [
            self.LoadTestUser(i, test_client, mock_auth_headers)
            for i in range(num_users)
        ]

        # Monitor system resources
        process = psutil.Process()
        cpu_samples = []
        memory_samples = []

        def monitor_resources():
            while True:
                cpu_samples.append(process.cpu_percent())
                memory_samples.append(process.memory_info().rss / 1024 / 1024)  # MB
                time.sleep(1)

        # Start monitoring
        monitor_thread = threading.Thread(target=monitor_resources, daemon=True)
        monitor_thread.start()

        # Start load test
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=num_users) as executor:
            # Submit user sessions
            futures = [
                executor.submit(user.simulate_user_session, test_duration, 0.5, 2.0)
                for user in users
            ]

            # Wait for all users to complete
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"User session failed: {e}")

        total_time = time.time() - start_time

        # Aggregate results
        for user in users:
            load_test_results["total_requests"] += user.results["requests"]
            load_test_results["successful_requests"] += user.results["successes"]
            load_test_results["failed_requests"] += user.results["failures"]
            load_test_results["response_times"].extend(user.results["response_times"])
            load_test_results["errors"].extend(user.results["errors"])

        # Calculate metrics
        load_test_results["throughput"] = load_test_results["total_requests"] / total_time
        load_test_results["avg_cpu_usage"] = statistics.mean(cpu_samples) if cpu_samples else 0
        load_test_results["peak_memory_usage"] = max(memory_samples) if memory_samples else 0

        # Print results
        print(f"\nSustained Load Test Results:")
        print(f"  Total requests: {load_test_results['total_requests']}")
        print(f"  Successful requests: {load_test_results['successful_requests']}")
        print(f"  Failed requests: {load_test_results['failed_requests']}")
        print(f"  Success rate: {load_test_results['successful_requests'] / load_test_results['total_requests'] * 100:.2f}%")
        print(f"  Throughput: {load_test_results['throughput']:.2f} requests/second")
        print(f"  Average CPU usage: {load_test_results['avg_cpu_usage']:.1f}%")
        print(f"  Peak memory usage: {load_test_results['peak_memory_usage']:.1f} MB")

        if load_test_results["response_times"]:
            avg_response_time = statistics.mean(load_test_results["response_times"])
            p95_response_time = statistics.quantiles(load_test_results["response_times"], n=20)[18]  # 95th percentile
            print(f"  Average response time: {avg_response_time:.3f}s")
            print(f"  95th percentile response time: {p95_response_time:.3f}s")

        if load_test_results["errors"]:
            print(f"  Sample errors: {load_test_results['errors'][:5]}")

        # Assertions
        success_rate = load_test_results["successful_requests"] / load_test_results["total_requests"]
        assert success_rate >= load_test_config["success_rate_threshold"], f"Success rate {success_rate:.2f} below threshold {load_test_config['success_rate_threshold']}"

        if load_test_results["response_times"]:
            avg_response_time = statistics.mean(load_test_results["response_times"])
            assert avg_response_time <= load_test_config["avg_response_time_threshold"], f"Average response time {avg_response_time:.3f}s above threshold {load_test_config['avg_response_time_threshold']}s"

    @pytest.mark.performance
    @pytest.mark.slow
    @pytest.mark.load
    def test_peak_load_spike(self, test_client: TestClient, hybrid_search_service_mock, document_service_mock, sample_search_results, mock_auth_headers, load_test_config):
        """Test system behavior under sudden load spikes"""
        # Setup mocks
        hybrid_search_service_mock.search.return_value = {
            "results": sample_search_results,
            "total": len(sample_search_results)
        }
        document_service_mock.get_documents.return_value = {
            "documents": [{"id": f"doc-{i}", "title": f"Document {i}"} for i in range(50)],
            "total": 50
        }

        # Test parameters
        baseline_users = 10
        spike_users = 90
        baseline_duration = 30  # 30 seconds baseline
        spike_duration = 60     # 60 seconds spike
        cooldown_duration = 30  # 30 seconds cooldown

        print(f"Starting peak load spike test:")
        print(f"  Baseline: {baseline_users} users for {baseline_duration}s")
        print(f"  Spike: {spike_users} users for {spike_duration}s")
        print(f"  Cooldown: {baseline_users} users for {cooldown_duration}s")

        results = {
            "baseline": {"requests": 0, "response_times": [], "errors": []},
            "spike": {"requests": 0, "response_times": [], "errors": []},
            "cooldown": {"requests": 0, "response_times": [], "errors": []}
        }

        def run_phase(num_users: int, duration: int, phase_name: str):
            """Run a test phase with specified number of users"""
            users = [
                self.LoadTestUser(i, test_client, mock_auth_headers)
                for i in range(num_users)
            ]

            start_time = time.time()

            with ThreadPoolExecutor(max_workers=num_users) as executor:
                futures = [
                    executor.submit(user.simulate_user_session, duration, 0.5, 1.5)
                    for user in users
                ]

                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        print(f"User session failed in {phase_name}: {e}")

            # Collect results
            for user in users:
                results[phase_name]["requests"] += user.results["requests"]
                results[phase_name]["response_times"].extend(user.results["response_times"])
                results[phase_name]["errors"].extend(user.results["errors"])

            print(f"  {phase_name.capitalize()} phase completed: {results[phase_name]['requests']} requests")

        # Run test phases
        print("Starting baseline phase...")
        run_phase(baseline_users, baseline_duration, "baseline")

        print("Starting spike phase...")
        run_phase(spike_users, spike_duration, "spike")

        print("Starting cooldown phase...")
        run_phase(baseline_users, cooldown_duration, "cooldown")

        # Analyze results
        print(f"\nPeak Load Spike Test Results:")
        for phase_name, phase_results in results.items():
            if phase_results["response_times"]:
                avg_time = statistics.mean(phase_results["response_times"])
                p95_time = statistics.quantiles(phase_results["response_times"], n=20)[18]
                error_rate = len(phase_results["errors"]) / phase_results["requests"] if phase_results["requests"] > 0 else 0

                print(f"  {phase_name.capitalize()}:")
                print(f"    Requests: {phase_results['requests']}")
                print(f"    Average response time: {avg_time:.3f}s")
                print(f"    95th percentile: {p95_time:.3f}s")
                print(f"    Error rate: {error_rate * 100:.2f}%")

                # Assert performance doesn't degrade too much during spike
                if phase_name == "spike":
                    assert avg_time < 10.0, f"Spike average response time {avg_time:.3f}s too high"
                    assert error_rate < 0.10, f"Spike error rate {error_rate:.2f} too high"

    @pytest.mark.performance
    @pytest.mark.slow
    @pytest.mark.load
    def test_endurance_load(self, test_client: TestClient, hybrid_search_service_mock, sample_search_results, mock_auth_headers):
        """Test system endurance under sustained load"""
        # Setup mock
        hybrid_search_service_mock.search.return_value = {
            "results": sample_search_results,
            "total": len(sample_search_results),
            "search_metadata": {"execution_time_ms": 100}
        }

        # Endurance test parameters
        num_users = 20
        test_duration = 300  # 5 minutes

        print(f"Starting endurance test: {num_users} users for {test_duration}s (5 minutes)")

        # Create users
        users = [
            self.LoadTestUser(i, test_client, mock_auth_headers)
            for i in range(num_users)
        ]

        # Monitor for memory leaks or performance degradation
        performance_snapshots = []
        memory_usage = []

        def take_performance_snapshot():
            """Take a snapshot of system performance"""
            process = psutil.Process()
            snapshot = {
                "timestamp": time.time(),
                "memory_mb": process.memory_info().rss / 1024 / 1024,
                "cpu_percent": process.cpu_percent()
            }
            performance_snapshots.append(snapshot)
            memory_usage.append(snapshot["memory_mb"])

        # Start performance monitoring
        def monitor_performance():
            while True:
                take_performance_snapshot()
                time.sleep(30)  # Take snapshot every 30 seconds

        monitor_thread = threading.Thread(target=monitor_performance, daemon=True)
        monitor_thread.start()

        # Run endurance test
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=num_users) as executor:
            futures = [
                executor.submit(user.simulate_user_session, test_duration, 1, 3)
                for user in users
            ]

            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"Endurance test user session failed: {e}")

        total_time = time.time() - start_time

        # Aggregate results
        total_requests = sum(user.results["requests"] for user in users)
        total_successful = sum(user.results["successes"] for user in users)
        all_response_times = []
        for user in users:
            all_response_times.extend(user.results["response_times"])

        print(f"\nEndurance Test Results:")
        print(f"  Test duration: {total_time:.1f}s")
        print(f"  Total requests: {total_requests}")
        print(f"  Successful requests: {total_successful}")
        print(f"  Success rate: {total_successful / total_requests * 100:.2f}%")
        print(f"  Average throughput: {total_requests / total_time:.2f} requests/second")

        if all_response_times:
            avg_time = statistics.mean(all_response_times)
            p95_time = statistics.quantiles(all_response_times, n=20)[18]
            print(f"  Average response time: {avg_time:.3f}s")
            print(f"  95th percentile response time: {p95_time:.3f}s")

        # Memory usage analysis
        if memory_usage:
            initial_memory = memory_usage[0]
            final_memory = memory_usage[-1]
            peak_memory = max(memory_usage)
            memory_growth = final_memory - initial_memory

            print(f"\nMemory Usage Analysis:")
            print(f"  Initial memory: {initial_memory:.1f} MB")
            print(f"  Final memory: {final_memory:.1f} MB")
            print(f"  Peak memory: {peak_memory:.1f} MB")
            print(f"  Memory growth: {memory_growth:.1f} MB")

            # Check for memory leaks
            assert memory_growth < 100, f"Potential memory leak: {memory_growth:.1f} MB growth"

        # Performance stability check
        if len(performance_snapshots) >= 3:
            # Check if response time degrades over time
            midpoint = len(all_response_times) // 2
            first_half_avg = statistics.mean(all_response_times[:midpoint])
            second_half_avg = statistics.mean(all_response_times[midpoint:])

            degradation_ratio = second_half_avg / first_half_avg if first_half_avg > 0 else 1
            print(f"\nPerformance Stability:")
            print(f"  First half avg response time: {first_half_avg:.3f}s")
            print(f"  Second half avg response time: {second_half_avg:.3f}s")
            print(f"  Performance degradation ratio: {degradation_ratio:.2f}")

            # Performance should not degrade significantly
            assert degradation_ratio < 1.5, f"Performance degraded by factor {degradation_ratio:.2f}"

    @pytest.mark.performance
    @pytest.mark.slow
    @pytest.mark.load
    def test_volume_load(self, test_client: TestClient, hybrid_search_service_mock, sample_search_results, mock_auth_headers):
        """Test system under high volume of requests in short duration"""
        # Setup mock
        hybrid_search_service_mock.search.return_value = {
            "results": sample_search_results,
            "total": len(sample_search_results)
        }

        # Volume test parameters
        total_requests = 1000
        concurrent_workers = 50

        print(f"Starting volume test: {total_requests} requests with {concurrent_workers} concurrent workers")

        results = {"requests": 0, "successes": 0, "failures": 0, "response_times": [], "errors": []}

        def make_request():
            """Make a single request"""
            user = self.LoadTestUser(0, test_client, mock_auth_headers)
            return user.perform_search(f"volume test query {random.randint(1, 10000)}")

        # Execute volume test
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=concurrent_workers) as executor:
            # Submit all requests
            futures = [executor.submit(make_request) for _ in range(total_requests)]

            # Collect results
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results["requests"] += 1
                    if result["success"]:
                        results["successes"] += 1
                    else:
                        results["failures"] += 1
                        if "error" in result:
                            results["errors"].append(result["error"])

                    results["response_times"].append(result["response_time"])

                except Exception as e:
                    results["requests"] += 1
                    results["failures"] += 1
                    results["errors"].append(str(e))

        total_time = time.time() - start_time

        # Calculate metrics
        success_rate = results["successes"] / results["requests"] if results["requests"] > 0 else 0
        throughput = results["requests"] / total_time

        print(f"\nVolume Test Results:")
        print(f"  Total requests: {results['requests']}")
        print(f"  Successful requests: {results['successes']}")
        print(f"  Failed requests: {results['failures']}")
        print(f"  Success rate: {success_rate * 100:.2f}%")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Throughput: {throughput:.2f} requests/second")

        if results["response_times"]:
            avg_time = statistics.mean(results["response_times"])
            min_time = min(results["response_times"])
            max_time = max(results["response_times"])
            p95_time = statistics.quantiles(results["response_times"], n=20)[18]

            print(f"  Response time statistics:")
            print(f"    Average: {avg_time:.3f}s")
            print(f"    Minimum: {min_time:.3f}s")
            print(f"    Maximum: {max_time:.3f}s")
            print(f"    95th percentile: {p95_time:.3f}s")

        # Assert volume handling capabilities
        assert success_rate >= 0.90, f"Success rate {success_rate:.2f} below 90%"
        assert throughput >= 50, f"Throughput {throughput:.2f} below 50 requests/second"

        if results["response_times"]:
            assert statistics.mean(results["response_times"]) <= 5.0, "Average response time above 5 seconds"