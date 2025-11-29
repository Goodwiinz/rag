"""
WebSocket Load Testing Framework

Comprehensive load testing for WebSocket connections to validate:
- Connection scalability and performance
- Message throughput under load
- Resource usage optimization
- Connection stability under stress
- Concurrent operation handling

Load Test Scenarios:
- Connection burst testing
- Sustained load testing
- Message throughput testing
- Connection lifecycle testing
- Resource exhaustion testing
"""

import asyncio
import time
import json
import logging
import psutil
import statistics
from typing import List, Dict, Any, Optional, AsyncGenerator
from datetime import datetime, timezone as dt_timezone
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
from unittest.mock import patch

import pytest
import websockets
from websockets.client import WebSocketClientProtocol
from websockets.exceptions import ConnectionClosed, InvalidHandshake

# Import test utilities
from .test_websocket_integration import (
    WebSocketTestConfig,
    WebSocketTestHelper,
    MockUserManager
)

logger = logging.getLogger(__name__)


@dataclass
class ConnectionMetrics:
    """Metrics collected for each WebSocket connection"""

    connection_id: str
    connect_time: float
    connect_timestamp: datetime
    first_message_time: Optional[float] = None
    last_heartbeat_time: Optional[float] = None
    messages_sent: int = 0
    messages_received: int = 0
    connection_errors: int = 0
    reconnection_attempts: int = 0
    is_connected: bool = True
    total_bytes_received: int = 0
    total_bytes_sent: int = 0
    latency_samples: List[float] = None

    def __post_init__(self):
        if self.latency_samples is None:
            self.latency_samples = []


@dataclass
class LoadTestResults:
    """Aggregated load test results"""

    test_name: str
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    total_connections: int
    successful_connections: int
    failed_connections: int
    connection_metrics: List[ConnectionMetrics]

    # Performance metrics
    avg_connection_time: float = 0.0
    min_connection_time: float = 0.0
    max_connection_time: float = 0.0
    p95_connection_time: float = 0.0

    # Message metrics
    total_messages_sent: int = 0
    total_messages_received: int = 0
    avg_messages_per_connection: float = 0.0
    message_success_rate: float = 0.0

    # Latency metrics
    avg_latency: float = 0.0
    min_latency: float = 0.0
    max_latency: float = 0.0
    p95_latency: float = 0.0

    # Resource metrics
    peak_memory_usage_mb: float = 0.0
    peak_cpu_usage_percent: float = 0.0
    avg_memory_usage_mb: float = 0.0
    avg_cpu_usage_percent: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert results to dictionary for serialization"""
        return asdict(self)

    def calculate_derived_metrics(self):
        """Calculate derived metrics from raw data"""

        # Connection time metrics
        if self.connection_metrics:
            connection_times = [
                m.connect_time for m in self.connection_metrics
                if m.connect_time > 0
            ]

            if connection_times:
                self.avg_connection_time = statistics.mean(connection_times)
                self.min_connection_time = min(connection_times)
                self.max_connection_time = max(connection_times)
                self.p95_connection_time = statistics.quantiles(connection_times, n=20)[18]  # 95th percentile

            # Message metrics
            self.total_messages_sent = sum(m.messages_sent for m in self.connection_metrics)
            self.total_messages_received = sum(m.messages_received for m in self.connection_metrics)
            self.avg_messages_per_connection = self.total_messages_received / len(self.connection_metrics) if self.connection_metrics else 0

            if self.total_messages_sent > 0:
                self.message_success_rate = (self.total_messages_received / self.total_messages_sent) * 100

            # Latency metrics
            all_latencies = []
            for m in self.connection_metrics:
                all_latencies.extend(m.latency_samples)

            if all_latencies:
                self.avg_latency = statistics.mean(all_latencies)
                self.min_latency = min(all_latencies)
                self.max_latency = max(all_latencies)
                self.p95_latency = statistics.quantiles(all_latencies, n=20)[18]  # 95th percentile


class ResourceMonitor:
    """Monitor system resources during load testing"""

    def __init__(self):
        self.monitoring = False
        self.monitor_task = None
        self.samples: List[Dict[str, float]] = []

    async def start_monitoring(self, interval: float = 1.0):
        """Start resource monitoring"""
        self.monitoring = True
        self.samples.clear()
        self.monitor_task = asyncio.create_task(self._monitor_loop(interval))

    async def stop_monitoring(self):
        """Stop resource monitoring"""
        self.monitoring = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

    def get_metrics(self) -> Dict[str, float]:
        """Get aggregated resource metrics"""
        if not self.samples:
            return {
                "peak_memory_mb": 0.0,
                "avg_memory_mb": 0.0,
                "peak_cpu_percent": 0.0,
                "avg_cpu_percent": 0.0
            }

        memory_samples = [s["memory_mb"] for s in self.samples]
        cpu_samples = [s["cpu_percent"] for s in self.samples]

        return {
            "peak_memory_mb": max(memory_samples),
            "avg_memory_mb": statistics.mean(memory_samples),
            "peak_cpu_percent": max(cpu_samples),
            "avg_cpu_percent": statistics.mean(cpu_samples)
        }

    async def _monitor_loop(self, interval: float):
        """Internal monitoring loop"""
        process = psutil.Process()

        while self.monitoring:
            try:
                # Get memory usage (in MB)
                memory_info = process.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024

                # Get CPU usage
                cpu_percent = process.cpu_percent()

                sample = {
                    "timestamp": time.time(),
                    "memory_mb": memory_mb,
                    "cpu_percent": cpu_percent
                }

                self.samples.append(sample)

                await asyncio.sleep(interval)

            except Exception as e:
                logger.warning(f"Error in resource monitoring: {e}")
                await asyncio.sleep(interval)


class WebSocketLoadTester:
    """Main WebSocket load testing framework"""

    def __init__(self):
        self.resource_monitor = ResourceMonitor()
        self.connection_metrics: List[ConnectionMetrics] = []

    async def run_connection_burst_test(
        self,
        num_connections: int = 100,
        connection_rate: float = 10.0,  # connections per second
        websocket_url: str = None,
        test_duration: float = 30.0
    ) -> LoadTestResults:
        """
        Run connection burst test

        Args:
            num_connections: Number of concurrent connections to create
            connection_rate: Rate at which to create connections (per second)
            websocket_url: WebSocket URL to test
            test_duration: Duration to maintain connections (seconds)
        """

        test_name = "connection_burst_test"
        websocket_url = websocket_url or WebSocketTestConfig.WS_V1_URL

        logger.info(f"Starting {test_name}: {num_connections} connections at {connection_rate}/s")

        start_time = datetime.now(dt_timezone.utc)

        # Start resource monitoring
        await self.resource_monitor.start_monitoring()

        # Calculate delay between connections
        connection_delay = 1.0 / connection_rate if connection_rate > 0 else 0

        # Create connection tasks
        connection_tasks = []
        for i in range(num_connections):
            task = asyncio.create_task(
                self._create_and_maintain_connection(
                    websocket_url,
                    f"burst_conn_{i}",
                    test_duration
                )
            )
            connection_tasks.append(task)

            # Add delay to control connection rate
            if connection_delay > 0:
                await asyncio.sleep(connection_delay)

        # Wait for all connections to complete
        results = await asyncio.gather(*connection_tasks, return_exceptions=True)

        # Stop resource monitoring
        await self.resource_monitor.stop_monitoring()

        # Process results
        end_time = datetime.now(dt_timezone.utc)
        duration = (end_time - start_time).total_seconds()

        successful_connections = []
        failed_connections = []

        for result in results:
            if isinstance(result, Exception):
                failed_connections.append(result)
                logger.error(f"Connection failed: {result}")
            else:
                successful_connections.append(result)

        # Create load test results
        load_results = LoadTestResults(
            test_name=test_name,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            total_connections=num_connections,
            successful_connections=len(successful_connections),
            failed_connections=len(failed_connections),
            connection_metrics=successful_connections
        )

        # Add resource metrics
        resource_metrics = self.resource_monitor.get_metrics()
        load_results.peak_memory_usage_mb = resource_metrics["peak_memory_mb"]
        load_results.avg_memory_usage_mb = resource_metrics["avg_memory_mb"]
        load_results.peak_cpu_usage_percent = resource_metrics["peak_cpu_percent"]
        load_results.avg_cpu_usage_percent = resource_metrics["avg_cpu_percent"]

        # Calculate derived metrics
        load_results.calculate_derived_metrics()

        logger.info(f"Completed {test_name}: {len(successful_connections)}/{num_connections} successful")

        return load_results

    async def run_sustained_load_test(
        self,
        num_connections: int = 50,
        test_duration: float = 300.0,  # 5 minutes
        message_frequency: float = 1.0,  # messages per second per connection
        websocket_url: str = None
    ) -> LoadTestResults:
        """
        Run sustained load test with continuous messaging

        Args:
            num_connections: Number of concurrent connections
            test_duration: Duration of the test (seconds)
            message_frequency: Messages per second per connection
            websocket_url: WebSocket URL to test
        """

        test_name = "sustained_load_test"
        websocket_url = websocket_url or WebSocketTestConfig.WS_V1_URL

        logger.info(f"Starting {test_name}: {num_connections} connections for {test_duration}s")

        start_time = datetime.now(dt_timezone.utc)

        # Start resource monitoring
        await self.resource_monitor.start_monitoring()

        # Create sustained connection tasks
        connection_tasks = []
        for i in range(num_connections):
            task = asyncio.create_task(
                self._create_sustained_connection(
                    websocket_url,
                    f"sustained_conn_{i}",
                    test_duration,
                    message_frequency
                )
            )
            connection_tasks.append(task)

        # Wait for all connections to complete
        results = await asyncio.gather(*connection_tasks, return_exceptions=True)

        # Stop resource monitoring
        await self.resource_monitor.stop_monitoring()

        # Process results
        end_time = datetime.now(dt_timezone.utc)
        duration = (end_time - start_time).total_seconds()

        successful_connections = []
        failed_connections = []

        for result in results:
            if isinstance(result, Exception):
                failed_connections.append(result)
            else:
                successful_connections.append(result)

        # Create load test results
        load_results = LoadTestResults(
            test_name=test_name,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            total_connections=num_connections,
            successful_connections=len(successful_connections),
            failed_connections=len(failed_connections),
            connection_metrics=successful_connections
        )

        # Add resource metrics
        resource_metrics = self.resource_monitor.get_metrics()
        load_results.peak_memory_usage_mb = resource_metrics["peak_memory_mb"]
        load_results.avg_memory_usage_mb = resource_metrics["avg_memory_mb"]
        load_results.peak_cpu_usage_percent = resource_metrics["peak_cpu_percent"]
        load_results.avg_cpu_usage_percent = resource_metrics["avg_cpu_percent"]

        # Calculate derived metrics
        load_results.calculate_derived_metrics()

        logger.info(f"Completed {test_name}: {len(successful_connections)}/{num_connections} successful")

        return load_results

    async def run_message_throughput_test(
        self,
        num_connections: int = 10,
        messages_per_connection: int = 1000,
        message_size: int = 1024,  # bytes
        websocket_url: str = None
    ) -> LoadTestResults:
        """
        Run message throughput test

        Args:
            num_connections: Number of concurrent connections
            messages_per_connection: Number of messages to send per connection
            message_size: Size of each message in bytes
            websocket_url: WebSocket URL to test
        """

        test_name = "message_throughput_test"
        websocket_url = websocket_url or WebSocketTestConfig.WS_V1_URL

        logger.info(f"Starting {test_name}: {num_connections} connections, {messages_per_connection} messages each")

        start_time = datetime.now(dt_timezone.utc)

        # Start resource monitoring
        await self.resource_monitor.start_monitoring()

        # Create throughput test tasks
        connection_tasks = []
        for i in range(num_connections):
            task = asyncio.create_task(
                self._create_throughput_connection(
                    websocket_url,
                    f"throughput_conn_{i}",
                    messages_per_connection,
                    message_size
                )
            )
            connection_tasks.append(task)

        # Wait for all connections to complete
        results = await asyncio.gather(*connection_tasks, return_exceptions=True)

        # Stop resource monitoring
        await self.resource_monitor.stop_monitoring()

        # Process results
        end_time = datetime.now(dt_timezone.utc)
        duration = (end_time - start_time).total_seconds()

        successful_connections = []
        failed_connections = []

        for result in results:
            if isinstance(result, Exception):
                failed_connections.append(result)
            else:
                successful_connections.append(result)

        # Create load test results
        load_results = LoadTestResults(
            test_name=test_name,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            total_connections=num_connections,
            successful_connections=len(successful_connections),
            failed_connections=len(failed_connections),
            connection_metrics=successful_connections
        )

        # Add resource metrics
        resource_metrics = self.resource_monitor.get_metrics()
        load_results.peak_memory_usage_mb = resource_metrics["peak_memory_mb"]
        load_results.avg_memory_usage_mb = resource_metrics["avg_memory_mb"]
        load_results.peak_cpu_usage_percent = resource_metrics["peak_cpu_percent"]
        load_results.avg_cpu_usage_percent = resource_metrics["avg_cpu_percent"]

        # Calculate derived metrics
        load_results.calculate_derived_metrics()

        # Calculate throughput
        total_messages = load_results.total_messages_received
        throughput = total_messages / duration if duration > 0 else 0
        logger.info(f"Message throughput: {throughput:.2f} messages/second")

        return load_results

    async def _create_and_maintain_connection(
        self,
        websocket_url: str,
        connection_id: str,
        duration: float
    ) -> ConnectionMetrics:
        """Create and maintain a WebSocket connection for specified duration"""

        token = WebSocketTestHelper.generate_test_token()
        metrics = ConnectionMetrics(
            connection_id=connection_id,
            connect_time=0.0,
            connect_timestamp=datetime.now(dt_timezone.utc)
        )

        try:
            # Measure connection time
            connect_start = time.time()

            websocket = await WebSocketTestHelper.create_websocket_connection(
                websocket_url,
                token=token,
                timeout=WebSocketTestConfig.CONNECTION_TIMEOUT
            )

            connect_end = time.time()
            metrics.connect_time = connect_end - connect_start
            metrics.first_message_time = connect_end

            # Wait for welcome message
            await WebSocketTestHelper.authenticate_websocket_v1(websocket)
            metrics.messages_received += 1

            # Maintain connection for specified duration
            end_time = time.time() + duration

            while time.time() < end_time:
                try:
                    # Send periodic ping
                    ping_start = time.time()
                    pong_response = await WebSocketTestHelper.send_message_and_wait_for_response(
                        websocket,
                        WebSocketTestConfig.PING_MESSAGE,
                        expected_type="pong",
                        timeout=WebSocketTestConfig.PING_TIMEOUT
                    )
                    ping_end = time.time()

                    # Record latency
                    latency = ping_end - ping_start
                    metrics.latency_samples.append(latency)

                    metrics.messages_sent += 1
                    metrics.messages_received += 1
                    metrics.last_heartbeat_time = ping_end

                    # Wait before next ping
                    await asyncio.sleep(5.0)

                except asyncio.TimeoutError:
                    metrics.connection_errors += 1
                    logger.warning(f"Ping timeout for connection {connection_id}")
                    break

            await websocket.close()
            metrics.is_connected = False

        except Exception as e:
            metrics.connection_errors += 1
            metrics.is_connected = False
            logger.error(f"Connection {connection_id} failed: {e}")

        return metrics

    async def _create_sustained_connection(
        self,
        websocket_url: str,
        connection_id: str,
        duration: float,
        message_frequency: float
    ) -> ConnectionMetrics:
        """Create a sustained connection with continuous messaging"""

        token = WebSocketTestHelper.generate_test_token()
        metrics = ConnectionMetrics(
            connection_id=connection_id,
            connect_time=0.0,
            connect_timestamp=datetime.now(dt_timezone.utc)
        )

        try:
            # Connect
            connect_start = time.time()

            websocket = await WebSocketTestHelper.create_websocket_connection(
                websocket_url,
                token=token,
                timeout=WebSocketTestConfig.CONNECTION_TIMEOUT
            )

            connect_end = time.time()
            metrics.connect_time = connect_end - connect_start

            # Authenticate
            await WebSocketTestHelper.authenticate_websocket_v1(websocket)
            metrics.messages_received += 1

            # Continuous messaging
            end_time = time.time() + duration
            message_interval = 1.0 / message_frequency if message_frequency > 0 else 1.0

            while time.time() < end_time:
                try:
                    message_start = time.time()

                    # Send test message
                    test_message = {
                        "type": "test_message",
                        "data": f"Sustained load test message from {connection_id}",
                        "timestamp": datetime.now(dt_timezone.utc).isoformat(),
                        "sequence": metrics.messages_sent
                    }

                    await websocket.send(json.dumps(test_message))
                    metrics.messages_sent += 1

                    # Wait for response (if any)
                    try:
                        response = await asyncio.wait_for(
                            websocket.recv(),
                            timeout=1.0
                        )
                        response_data = json.loads(response)
                        metrics.messages_received += 1

                        # Record latency
                        message_end = time.time()
                        latency = message_end - message_start
                        metrics.latency_samples.append(latency)

                    except asyncio.TimeoutError:
                        # No response expected for test messages
                        pass

                    # Wait before next message
                    await asyncio.sleep(message_interval)

                except Exception as e:
                    metrics.connection_errors += 1
                    logger.warning(f"Message error in connection {connection_id}: {e}")
                    break

            await websocket.close()
            metrics.is_connected = False

        except Exception as e:
            metrics.connection_errors += 1
            metrics.is_connected = False
            logger.error(f"Sustained connection {connection_id} failed: {e}")

        return metrics

    async def _create_throughput_connection(
        self,
        websocket_url: str,
        connection_id: str,
        messages_to_send: int,
        message_size: int
    ) -> ConnectionMetrics:
        """Create connection for throughput testing"""

        token = WebSocketTestHelper.generate_test_token()
        metrics = ConnectionMetrics(
            connection_id=connection_id,
            connect_time=0.0,
            connect_timestamp=datetime.now(dt_timezone.utc)
        )

        # Prepare test message data
        test_data = "x" * message_size
        test_message = {
            "type": "throughput_test",
            "data": test_data,
            "size": message_size
        }

        try:
            # Connect
            connect_start = time.time()

            websocket = await WebSocketTestHelper.create_websocket_connection(
                websocket_url,
                token=token,
                timeout=WebSocketTestConfig.CONNECTION_TIMEOUT
            )

            connect_end = time.time()
            metrics.connect_time = connect_end - connect_start

            # Authenticate
            await WebSocketTestHelper.authenticate_websocket_v1(websocket)
            metrics.messages_received += 1

            # Send throughput test messages
            for i in range(messages_to_send):
                try:
                    message_start = time.time()

                    test_message["sequence"] = i
                    test_message["timestamp"] = datetime.now(dt_timezone.utc).isoformat()

                    await websocket.send(json.dumps(test_message))
                    metrics.messages_sent += 1

                    # Optionally wait for response (every 10th message)
                    if i % 10 == 0:
                        try:
                            response = await asyncio.wait_for(
                                websocket.recv(),
                                timeout=1.0
                            )
                            response_data = json.loads(response)
                            metrics.messages_received += 1

                            # Record latency
                            message_end = time.time()
                            latency = message_end - message_start
                            metrics.latency_samples.append(latency)

                        except asyncio.TimeoutError:
                            pass

                except Exception as e:
                    metrics.connection_errors += 1
                    logger.warning(f"Throughput message error in connection {connection_id}: {e}")
                    break

            await websocket.close()
            metrics.is_connected = False

        except Exception as e:
            metrics.connection_errors += 1
            metrics.is_connected = False
            logger.error(f"Throughput connection {connection_id} failed: {e}")

        return metrics


# ============================================================================
# Pytest Integration
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.websocket
@pytest.mark.load_test
@pytest.mark.slow
class TestWebSocketLoadTests:
    """WebSocket load test suite"""

    @pytest.fixture
    async def load_tester(self):
        """Load tester fixture"""
        return WebSocketLoadTester()

    async def test_small_connection_burst(self, load_tester):
        """Test small connection burst (quick test)"""

        results = await load_tester.run_connection_burst_test(
            num_connections=10,
            connection_rate=5.0,
            test_duration=10.0
        )

        # Validate results
        assert results.successful_connections >= 8  # Allow for some failures
        assert results.avg_connection_time < 2.0
        assert results.message_success_rate > 80.0
        assert results.peak_memory_usage_mb < 500  # Reasonable memory limit

        logger.info(f"Connection burst test completed: {results.successful_connections}/10 successful")

    async def test_sustained_load_small(self, load_tester):
        """Test small sustained load"""

        results = await load_tester.run_sustained_load_test(
            num_connections=5,
            test_duration=30.0,
            message_frequency=0.5  # 1 message every 2 seconds
        )

        # Validate results
        assert results.successful_connections >= 4
        assert results.avg_messages_per_connection > 10  # Should receive multiple messages
        assert results.message_success_rate > 70.0

        logger.info(f"Sustained load test completed: {results.avg_messages_per_connection:.1f} avg messages")

    async def test_message_throughput_small(self, load_tester):
        """Test message throughput with small load"""

        results = await load_tester.run_message_throughput_test(
            num_connections=3,
            messages_per_connection=50,
            message_size=512
        )

        # Validate results
        assert results.successful_connections >= 2
        assert results.total_messages_sent >= 150
        assert results.avg_latency < 1.0  # Latency should be reasonable

        throughput = results.total_messages_received / results.duration_seconds
        logger.info(f"Throughput: {throughput:.2f} messages/second")

    @pytest.mark.parametrize("connection_rate", [1.0, 5.0, 10.0])
    async def test_connection_rate_scaling(self, load_tester, connection_rate):
        """Test scaling with different connection rates"""

        results = await load_tester.run_connection_burst_test(
            num_connections=20,
            connection_rate=connection_rate,
            test_duration=15.0
        )

        # Success rate should be reasonable regardless of connection rate
        success_rate = (results.successful_connections / results.total_connections) * 100
        assert success_rate > 70.0

        logger.info(f"Connection rate {connection_rate}/s: {success_rate:.1f}% success rate")


# ============================================================================
# Benchmark Runner
# ============================================================================

async def run_comprehensive_websocket_benchmarks():
    """Run comprehensive WebSocket benchmarks"""

    tester = WebSocketLoadTester()
    results = []

    logger.info("Starting comprehensive WebSocket benchmark suite...")

    # Test 1: Connection scalability
    logger.info("Running connection scalability test...")
    result1 = await tester.run_connection_burst_test(
        num_connections=50,
        connection_rate=10.0,
        test_duration=60.0
    )
    results.append(result1)

    # Test 2: Sustained load
    logger.info("Running sustained load test...")
    result2 = await tester.run_sustained_load_test(
        num_connections=25,
        test_duration=180.0,  # 3 minutes
        message_frequency=1.0
    )
    results.append(result2)

    # Test 3: Message throughput
    logger.info("Running message throughput test...")
    result3 = await tester.run_message_throughput_test(
        num_connections=10,
        messages_per_connection=500,
        message_size=1024
    )
    results.append(result3)

    # Generate summary report
    logger.info("\n" + "="*50)
    logger.info("WEBSOCKET BENCHMARK SUMMARY")
    logger.info("="*50)

    for result in results:
        logger.info(f"\n{result.test_name}:")
        logger.info(f"  Connections: {result.successful_connections}/{result.total_connections} successful")
        logger.info(f"  Success Rate: {(result.successful_connections/result.total_connections)*100:.1f}%")
        logger.info(f"  Avg Connection Time: {result.avg_connection_time:.3f}s")
        logger.info(f"  Avg Latency: {result.avg_latency:.3f}s")
        logger.info(f"  Messages Received: {result.total_messages_received}")
        logger.info(f"  Peak Memory: {result.peak_memory_usage_mb:.1f} MB")
        logger.info(f"  Peak CPU: {result.peak_cpu_usage_percent:.1f}%")

    # Save results to file
    import json

    timestamp = datetime.now(dt_timezone.utc).strftime("%Y%m%d_%H%M%S")
    results_file = f"/tmp/websocket_benchmark_results_{timestamp}.json"

    with open(results_file, 'w') as f:
        json.dump([r.to_dict() for r in results], f, indent=2, default=str)

    logger.info(f"\nDetailed results saved to: {results_file}")

    return results


if __name__ == "__main__":
    # Run benchmarks when executed directly
    asyncio.run(run_comprehensive_websocket_benchmarks())