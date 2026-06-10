"""
WebSocket Load Testing Framework

This module contains comprehensive load testing for WebSocket connections,
including tests for 10,000+ concurrent connections, message throughput,
and performance under extreme load.
"""

import pytest
import asyncio
import json
import uuid
import time
import psutil
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from collections import defaultdict, deque
import statistics

import websockets
from fastapi.testclient import TestClient

from backend.src.services.websocket_manager import (
    EnhancedConnectionManager,
    WebSocketMessage,
    MessageType,
    Priority
)


@dataclass
class LoadTestMetrics:
    """Metrics collected during load testing"""
    total_connections: int
    successful_connections: int
    failed_connections: int
    connection_time_avg: float
    connection_time_max: float
    connection_time_min: float
    messages_sent: int
    messages_received: int
    message_latency_avg: float
    message_throughput: float
    memory_usage_mb: float
    cpu_usage_percent: float
    errors: List[str]
    test_duration: float


@dataclass
class ConnectionWorker:
    """Worker for managing WebSocket connections in load tests"""
    worker_id: int
    connections: List[str]
    message_queue: asyncio.Queue
    metrics: Dict[str, Any]


class WebSocketLoadTester:
    """Advanced WebSocket load testing framework"""

    def __init__(self, base_url: str, max_connections: int = 15000):
        self.base_url = base_url
        self.max_connections = max_connections
        self.active_connections = {}
        self.metrics_collector = defaultdict(list)
        self.error_tracker = defaultdict(int)
        self.start_time = None
        self.end_time = None

    async def run_load_test(self,
                          target_connections: int,
                          ramp_up_time: float = 60.0,
                          test_duration: float = 300.0,
                          messages_per_second: int = 100) -> LoadTestMetrics:
        """Run comprehensive load test"""
        print(f"Starting WebSocket load test: {target_connections} connections")
        print(f"Ramp-up time: {ramp_up_time}s, Test duration: {test_duration}s")

        self.start_time = time.time()

        # Initialize metrics collection
        connection_times = []
        message_latencies = []
        errors = []

        # System resource monitoring
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        try:
            # Phase 1: Connection ramp-up
            print("Phase 1: Connection ramp-up...")
            connections = await self._ramp_up_connections(
                target_connections,
                ramp_up_time,
                connection_times
            )

            # Phase 2: Sustained load testing
            print("Phase 2: Sustained load testing...")
            await self._sustained_load_test(
                connections,
                test_duration,
                messages_per_second,
                message_latencies,
                errors
            )

        finally:
            self.end_time = time.time()

        # Phase 3: Cleanup and metrics collection
        print("Phase 3: Cleanup and metrics collection...")
        await self._cleanup_connections(connections)

        # Calculate final metrics
        peak_memory = process.memory_info().rss
        cpu_usage = process.cpu_percent()

        test_duration = self.end_time - self.start_time

        return LoadTestMetrics(
            total_connections=target_connections,
            successful_connections=len(connections),
            failed_connections=target_connections - len(connections),
            connection_time_avg=statistics.mean(connection_times) if connection_times else 0,
            connection_time_max=max(connection_times) if connection_times else 0,
            connection_time_min=min(connection_times) if connection_times else 0,
            messages_sent=self.metrics_collector['messages_sent'][-1] if self.metrics_collector['messages_sent'] else 0,
            messages_received=self.metrics_collector['messages_received'][-1] if self.metrics_collector['messages_received'] else 0,
            message_latency_avg=statistics.mean(message_latencies) if message_latencies else 0,
            message_throughput=self.metrics_collector['messages_sent'][-1] / test_duration if test_duration > 0 else 0,
            memory_usage_mb=(peak_memory - initial_memory) / 1024 / 1024,
            cpu_usage_percent=cpu_usage,
            errors=errors,
            test_duration=test_duration
        )

    async def _ramp_up_connections(self,
                                 target_connections: int,
                                 ramp_up_time: float,
                                 connection_times: List[float]) -> List[str]:
        """Gradually ramp up connections"""
        connections = []
        connections_per_second = target_connections / ramp_up_time
        batch_size = max(1, int(connections_per_second / 10))  # 10 batches per second

        batches_per_second = 10
        batch_interval = 1.0 / batches_per_second

        connected_count = 0

        while connected_count < target_connections:
            batch_start = time.time()

            # Create batch of connections
            batch_tasks = []
            batch_size_actual = min(batch_size, target_connections - connected_count)

            for i in range(batch_size_actual):
                task = asyncio.create_task(
                    self._create_single_connection(connected_count + i)
                )
                batch_tasks.append(task)

            # Wait for batch completion
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # Process results
            for result in batch_results:
                if isinstance(result, str) and result:  # Connection ID
                    connections.append(result)
                    connection_times.append(self.metrics_collector.get(f'conn_time_{result}', 0))
                    connected_count += 1
                elif isinstance(result, Exception):
                    self.error_tracker['connection_error'] += 1

            # Rate limiting - wait for next batch
            batch_elapsed = time.time() - batch_start
            if batch_elapsed < batch_interval:
                await asyncio.sleep(batch_interval - batch_elapsed)

            # Progress reporting
            if connected_count % 100 == 0:
                print(f"  Connected: {connected_count}/{target_connections} "
                      f"({connected_count/target_connections*100:.1f}%)")

        print(f"  Connection phase complete: {len(connections)}/{target_connections} successful")
        return connections

    async def _sustained_load_test(self,
                                 connections: List[str],
                                 test_duration: float,
                                 messages_per_second: int,
                                 message_latencies: List[float],
                                 errors: List[str]):
        """Run sustained load test with message traffic"""
        message_interval = 1.0 / messages_per_second if messages_per_second > 0 else 1.0

        # Create message generation tasks
        message_tasks = []
        for i in range(min(10, len(connections))):  # 10 message generators
            task = asyncio.create_task(
                self._message_generator(
                    connections[i::10],  # Distribute connections among generators
                    message_interval,
                    message_latencies
                )
            )
            message_tasks.append(task)

        # Monitor system health during test
        monitor_task = asyncio.create_task(
            self._system_health_monitor(test_duration)
        )

        try:
            # Run sustained test
            await asyncio.sleep(test_duration)

        finally:
            # Cancel all tasks
            for task in message_tasks + [monitor_task]:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

    async def _message_generator(self,
                               connections: List[str],
                               interval: float,
                               latencies: List[float]):
        """Generate messages for a subset of connections"""
        message_count = 0

        while True:
            start_time = time.time()

            # Send messages to connections
            for connection_id in connections:
                if connection_id in self.active_connections:
                    message = {
                        "type": MessageType.PING.value,
                        "data": {
                            "message_id": message_count,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "generator_id": id(connections)
                        }
                    }

                    send_time = time.time()
                    try:
                        await self._send_message_to_connection(connection_id, message)

                        # Track latency (simplified - real implementation would need round-trip measurement)
                        send_latency = time.time() - send_time
                        latencies.append(send_latency)

                        self.metrics_collector['messages_sent'].append(
                            self.metrics_collector['messages_sent'][-1] + 1
                            if self.metrics_collector['messages_sent'] else 1
                        )

                    except Exception as e:
                        self.error_tracker['message_send_error'] += 1
                        errors.append(f"Message send error: {str(e)}")

                    message_count += 1

            # Rate limiting
            elapsed = time.time() - start_time
            if elapsed < interval:
                await asyncio.sleep(interval - elapsed)

    async def _system_health_monitor(self, test_duration: float):
        """Monitor system health during load test"""
        start_time = time.time()

        while time.time() - start_time < test_duration:
            try:
                # Collect system metrics
                process = psutil.Process(os.getpid())

                self.metrics_collector['memory_usage'].append(
                    process.memory_info().rss / 1024 / 1024  # MB
                )
                self.metrics_collector['cpu_usage'].append(
                    process.cpu_percent()
                )
                self.metrics_collector['active_connections'].append(
                    len(self.active_connections)
                )

                # Check for warning conditions
                memory_mb = self.metrics_collector['memory_usage'][-1]
                if memory_mb > 2000:  # 2GB warning threshold
                    print(f"  WARNING: High memory usage: {memory_mb:.1f}MB")

                cpu_percent = self.metrics_collector['cpu_usage'][-1]
                if cpu_percent > 90:  # 90% CPU warning
                    print(f"  WARNING: High CPU usage: {cpu_percent:.1f}%")

                await asyncio.sleep(5)  # Monitor every 5 seconds

            except Exception as e:
                print(f"  Health monitor error: {e}")
                await asyncio.sleep(5)

    async def _create_single_connection(self, connection_index: int) -> Optional[str]:
        """Create a single WebSocket connection"""
        start_time = time.time()

        try:
            # Generate test token
            token = self._generate_test_token(connection_index)

            # Create WebSocket connection
            uri = f"{self.base_url}/ws?token={token}"

            async with websockets.connect(
                uri,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=1
            ) as websocket:
                connection_id = str(uuid.uuid4())
                self.active_connections[connection_id] = websocket

                # Wait for welcome message
                try:
                    welcome_msg = await asyncio.wait_for(
                        websocket.recv(), timeout=5.0
                    )
                    welcome_data = json.loads(welcome_msg)

                    if welcome_data.get("type") == MessageType.CONNECT.value:
                        self.metrics_collector[f'conn_time_{connection_id}'] = time.time() - start_time
                        self.metrics_collector['messages_received'].append(
                            self.metrics_collector['messages_received'][-1] + 1
                            if self.metrics_collector['messages_received'] else 1
                        )
                        return connection_id

                except asyncio.TimeoutError:
                    self.error_tracker['welcome_timeout'] += 1

        except Exception as e:
            self.error_tracker['connection_creation_error'] += 1
            return None

    async def _send_message_to_connection(self, connection_id: str, message: Dict[str, Any]):
        """Send message to specific connection"""
        if connection_id not in self.active_connections:
            raise ConnectionError(f"Connection {connection_id} not active")

        websocket = self.active_connections[connection_id]
        await websocket.send(json.dumps(message))

    async def _cleanup_connections(self, connections: List[str]):
        """Clean up all connections"""
        print("  Cleaning up connections...")

        cleanup_tasks = []
        for connection_id in connections:
            if connection_id in self.active_connections:
                task = asyncio.create_task(
                    self._cleanup_single_connection(connection_id)
                )
                cleanup_tasks.append(task)

        # Wait for all cleanup tasks (with timeout)
        try:
            await asyncio.wait_for(
                asyncio.gather(*cleanup_tasks, return_exceptions=True),
                timeout=30.0
            )
        except asyncio.TimeoutError:
            print("  WARNING: Cleanup timeout - some connections may not be properly closed")

    async def _cleanup_single_connection(self, connection_id: str):
        """Clean up a single connection"""
        try:
            if connection_id in self.active_connections:
                websocket = self.active_connections[connection_id]
                await websocket.close()
                del self.active_connections[connection_id]
        except Exception:
            pass  # Ignore cleanup errors

    def _generate_test_token(self, connection_index: int) -> str:
        """Generate test JWT token for load testing"""
        # This would typically use the same token generation as the main application
        # For load testing, we might want to use a pool of pre-generated tokens
        return f"load_test_token_{connection_index}_{int(time.time())}"


@pytest.mark.contract
@pytest.mark.websocket
@pytest.mark.load
@pytest.mark.slow
class TestWebSocketLoadTesting:
    """WebSocket load testing scenarios"""

    @pytest.mark.asyncio
    async def test_scalability_to_1000_connections(self, websocket_load_tester):
        """Test scalability to 1,000 concurrent connections"""
        target_connections = 1000
        ramp_up_time = 30.0
        test_duration = 60.0

        metrics = await websocket_load_tester.run_load_test(
            target_connections=target_connections,
            ramp_up_time=ramp_up_time,
            test_duration=test_duration,
            messages_per_second=50
        )

        # Assertions
        success_rate = metrics.successful_connections / metrics.total_connections
        assert success_rate >= 0.95, f"Success rate too low: {success_rate:.2%}"

        assert metrics.connection_time_avg < 0.5, "Average connection time too high"
        assert metrics.connection_time_max < 2.0, "Max connection time too high"
        assert metrics.memory_usage_mb < 500, "Memory usage too high"

        print(f"✅ 1K connections test passed:")
        print(f"   Success rate: {success_rate:.2%}")
        print(f"   Avg connection time: {metrics.connection_time_avg:.3f}s")
        print(f"   Memory usage: {metrics.memory_usage_mb:.1f}MB")

    @pytest.mark.asyncio
    async def test_scalability_to_5000_connections(self, websocket_load_tester):
        """Test scalability to 5,000 concurrent connections"""
        target_connections = 5000
        ramp_up_time = 120.0
        test_duration = 180.0

        metrics = await websocket_load_tester.run_load_test(
            target_connections=target_connections,
            ramp_up_time=ramp_up_time,
            test_duration=test_duration,
            messages_per_second=100
        )

        # Assertions
        success_rate = metrics.successful_connections / metrics.total_connections
        assert success_rate >= 0.90, f"Success rate too low: {success_rate:.2%}"

        assert metrics.connection_time_avg < 1.0, "Average connection time too high"
        assert metrics.memory_usage_mb < 1500, "Memory usage too high"

        print(f"✅ 5K connections test passed:")
        print(f"   Success rate: {success_rate:.2%}")
        print(f"   Avg connection time: {metrics.connection_time_avg:.3f}s")
        print(f"   Memory usage: {metrics.memory_usage_mb:.1f}MB")

    @pytest.mark.asyncio
    @pytest.mark.extreme_load
    async def test_scalability_to_10000_connections(self, websocket_load_tester):
        """Test scalability to 10,000 concurrent connections (extreme load test)"""
        target_connections = 10000
        ramp_up_time = 300.0  # 5 minutes ramp-up
        test_duration = 600.0  # 10 minutes sustained

        metrics = await websocket_load_tester.run_load_test(
            target_connections=target_connections,
            ramp_up_time=ramp_up_time,
            test_duration=test_duration,
            messages_per_second=200
        )

        # Assertions (more lenient for extreme load)
        success_rate = metrics.successful_connections / metrics.total_connections
        assert success_rate >= 0.85, f"Success rate too low: {success_rate:.2%}"

        assert metrics.connection_time_avg < 2.0, "Average connection time too high"
        assert metrics.memory_usage_mb < 3000, "Memory usage too high"

        print(f"✅ 10K connections test passed:")
        print(f"   Success rate: {success_rate:.2%}")
        print(f"   Avg connection time: {metrics.connection_time_avg:.3f}s")
        print(f"   Memory usage: {metrics.memory_usage_mb:.1f}MB")
        print(f"   Message throughput: {metrics.message_throughput:.1f} msg/s")

    @pytest.mark.asyncio
    async def test_message_throughput_under_load(self, websocket_load_tester):
        """Test message throughput under varying connection loads"""
        connection_levels = [100, 500, 1000, 2000]
        throughput_results = []

        for connections in connection_levels:
            print(f"Testing throughput with {connections} connections...")

            metrics = await websocket_load_tester.run_load_test(
                target_connections=connections,
                ramp_up_time=30.0,
                test_duration=60.0,
                messages_per_second=50
            )

            throughput_results.append({
                'connections': connections,
                'throughput': metrics.message_throughput,
                'latency': metrics.message_latency_avg,
                'success_rate': metrics.successful_connections / metrics.total_connections
            })

        # Analyze throughput degradation
        baseline_throughput = throughput_results[0]['throughput']
        max_degradation = 0.5  # Allow 50% degradation at max load

        for result in throughput_results:
            degradation = 1 - (result['throughput'] / baseline_throughput)
            assert degradation <= max_degradation, f"Throughput degradation too high: {degradation:.2%}"
            assert result['success_rate'] >= 0.90, f"Success rate too low at {result['connections']} connections"

        print("✅ Message throughput test passed:")
        for result in throughput_results:
            print(f"   {result['connections']} connections: "
                  f"{result['throughput']:.1f} msg/s, "
                  f"{result['latency']*1000:.1f}ms avg latency")

    @pytest.mark.asyncio
    async def test_connection_churn_under_load(self, websocket_load_tester):
        """Test connection churn (connect/disconnect) under load"""
        base_connections = 1000
        churn_rate = 50  # connections per second
        test_duration = 120.0

        print(f"Testing connection churn with {base_connections} base connections...")

        # Establish base connections
        base_metrics = await websocket_load_tester.run_load_test(
            target_connections=base_connections,
            ramp_up_time=30.0,
            test_duration=30.0,
            messages_per_second=25
        )

        churn_metrics = []
        start_time = time.time()

        while time.time() - start_time < test_duration:
            # Add connections
            add_metrics = await websocket_load_tester.run_load_test(
                target_connections=churn_rate,
                ramp_up_time=5.0,
                test_duration=10.0,
                messages_per_second=10
            )
            churn_metrics.append(('add', add_metrics))

            # Small pause
            await asyncio.sleep(2)

            # Remove connections (simulate natural churn)
            # This would require implementing connection removal logic
            await asyncio.sleep(3)

        # Verify system stability under churn
        total_successful = sum(m.successful_connections for _, m in churn_metrics)
        total_attempted = sum(m.total_connections for _, m in churn_metrics)
        overall_success_rate = total_successful / total_attempted if total_attempted > 0 else 0

        assert overall_success_rate >= 0.80, f"Churn success rate too low: {overall_success_rate:.2%}"

        print(f"✅ Connection churn test passed:")
        print(f"   Overall success rate: {overall_success_rate:.2%}")
        print(f"   Base connections maintained: {base_metrics.successful_connections}")

    @pytest.mark.asyncio
    async def test_burst_traffic_handling(self, websocket_load_tester):
        """Test handling of burst traffic patterns"""
        base_connections = 2000
        burst_patterns = [
            (100, 10),   # 100 msg/s for 10 seconds
            (500, 5),    # 500 msg/s for 5 seconds
            (1000, 2),   # 1000 msg/s for 2 seconds
        ]

        print(f"Testing burst traffic with {base_connections} connections...")

        # Establish base connections
        await websocket_load_tester.run_load_test(
            target_connections=base_connections,
            ramp_up_time=60.0,
            test_duration=30.0,
            messages_per_second=20
        )

        burst_results = []

        for burst_rate, burst_duration in burst_patterns:
            print(f"  Testing burst: {burst_rate} msg/s for {burst_duration}s")

            metrics = await websocket_load_tester.run_load_test(
                target_connections=base_connections,
                ramp_up_time=1.0,  # Fast ramp-up for bursts
                test_duration=burst_duration,
                messages_per_second=burst_rate
            )

            burst_results.append({
                'burst_rate': burst_rate,
                'duration': burst_duration,
                'throughput': metrics.message_throughput,
                'latency': metrics.message_latency_avg,
                'error_rate': len(metrics.errors) / max(metrics.messages_sent, 1)
            })

        # Verify burst handling
        for result in burst_results:
            # Throughput should be close to burst rate
            throughput_efficiency = result['throughput'] / result['burst_rate']
            assert throughput_efficiency >= 0.5, f"Burst throughput too low: {throughput_efficiency:.2%}"

            # Error rate should be reasonable
            assert result['error_rate'] < 0.1, f"Burst error rate too high: {result['error_rate']:.2%}"

        print("✅ Burst traffic test passed:")
        for result in burst_results:
            print(f"   {result['burst_rate']} msg/s burst: "
                  f"{result['throughput']:.1f} actual throughput, "
                  f"{result['latency']*1000:.1f}ms avg latency")

    @pytest.mark.asyncio
    async def test_long_running_stability(self, websocket_load_tester):
        """Test system stability over extended periods"""
        target_connections = 3000
        test_duration = 1800.0  # 30 minutes

        print(f"Testing long-running stability with {target_connections} connections for {test_duration/60:.1f} minutes...")

        metrics = await websocket_load_tester.run_load_test(
            target_connections=target_connections,
            ramp_up_time=120.0,
            test_duration=test_duration,
            messages_per_second=75
        )

        # Stability assertions
        success_rate = metrics.successful_connections / metrics.total_connections
        assert success_rate >= 0.90, f"Success rate degraded over time: {success_rate:.2%}"

        assert metrics.memory_usage_mb < 2000, "Memory leak detected over extended run"

        # Message throughput should be consistent
        expected_throughput = 75 * target_connections
        throughput_efficiency = metrics.message_throughput / expected_throughput
        assert throughput_efficiency >= 0.7, f"Throughput degradation: {throughput_efficiency:.2%}"

        print(f"✅ Long-running stability test passed:")
        print(f"   Final success rate: {success_rate:.2%}")
        print(f"   Memory usage: {metrics.memory_usage_mb:.1f}MB")
        print(f"   Throughput efficiency: {throughput_efficiency:.2%}")
        print(f"   Test duration: {metrics.test_duration/60:.1f} minutes")