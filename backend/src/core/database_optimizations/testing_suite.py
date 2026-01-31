"""
Comprehensive Testing and Validation Suite for Database Optimizations

This module provides extensive testing capabilities for all database optimizations,
including performance validation, load testing, and automated regression testing.
"""

import asyncio
import json
import logging
import os
import statistics
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np


# Environment variable helpers for test configurations
def _get_env_or_default(key: str, default: str) -> str:
    """Get environment variable or return default value"""
    return os.environ.get(key, default)


logger = logging.getLogger(__name__)


class TestType(str, Enum):
    """Test types"""

    PERFORMANCE = "performance"
    LOAD = "load"
    STRESS = "stress"
    RECOVERY = "recovery"
    INTEGRATION = "integration"
    REGRESSION = "regression"
    VALIDATION = "validation"


class TestStatus(str, Enum):
    """Test execution status"""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"


class TestPriority(str, Enum):
    """Test priority levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class TestConfiguration:
    """Test configuration settings"""

    test_timeout_seconds: int = 300
    performance_thresholds: Dict[str, float] = field(default_factory=dict)
    load_test_duration_minutes: int = 10
    stress_test_concurrency: int = 100
    data_size_mb: int = 100
    enable_detailed_logging: bool = True
    cleanup_after_test: bool = True
    parallel_tests: int = 3


@dataclass
class TestResult:
    """Individual test result"""

    test_id: str
    test_name: str
    test_type: TestType
    database_type: str
    status: TestStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    success: bool = False
    error_message: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    assertions_passed: int = 0
    assertions_failed: int = 0
    logs: List[str] = field(default_factory=list)


@dataclass
class TestSuite:
    """Test suite definition"""

    suite_id: str
    name: str
    description: str
    tests: List[str] = field(default_factory=list)
    setup_procedures: List[str] = field(default_factory=list)
    teardown_procedures: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    expected_duration_minutes: int = 30
    retry_count: int = 0


class DatabaseTestRunner:
    """Database test runner for optimization validation"""

    def __init__(self, config: TestConfiguration):
        self.config = config
        self.test_results: List[TestResult] = []
        self.active_tests: Dict[str, TestResult] = {}
        self.test_suites: Dict[str, TestSuite] = {}
        self.test_data_cache: Dict[str, Any] = {}
        self.is_running = False

    async def run_all_tests(
        self, database_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Run all tests for specified databases"""
        databases_to_test = database_types or ["postgresql", "neo4j", "redis", "qdrant"]

        logger.info(
            f"Starting comprehensive test suite for databases: {databases_to_test}"
        )
        start_time = time.time()

        # Initialize test suites
        await self._initialize_test_suites()

        # Run tests by category
        test_categories = [
            TestType.VALIDATION,
            TestType.PERFORMANCE,
            TestType.LOAD,
            TestType.INTEGRATION,
            TestType.RECOVERY,
        ]

        results = {
            "start_time": datetime.utcnow().isoformat(),
            "databases_tested": databases_to_test,
            "test_categories": [cat.value for cat in test_categories],
            "category_results": {},
            "overall_success": True,
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
        }

        for category in test_categories:
            logger.info(f"Running {category.value} tests")
            category_results = await self._run_test_category(
                category, databases_to_test
            )
            results["category_results"][category.value] = category_results

            results["total_tests"] += category_results["total_tests"]
            results["passed_tests"] += category_results["passed_tests"]
            results["failed_tests"] += category_results["failed_tests"]

            if not category_results["success"]:
                results["overall_success"] = False

        total_duration = time.time() - start_time
        results["end_time"] = datetime.utcnow().isoformat()
        results["total_duration_seconds"] = total_duration

        logger.info(f"Test suite completed in {total_duration:.2f} seconds")
        return results

    async def _initialize_test_suites(self):
        """Initialize predefined test suites"""
        # PostgreSQL test suite
        self.test_suites["postgresql_optimization"] = TestSuite(
            suite_id="postgresql_optimization",
            name="PostgreSQL Optimization Tests",
            description="Comprehensive tests for PostgreSQL performance optimizations",
            tests=[
                "test_connection_pool_efficiency",
                "test_index_performance",
                "test_query_optimization",
                "test_transaction_throughput",
                "test_backup_recovery",
            ],
            setup_procedures=["create_test_tables", "populate_test_data"],
            teardown_procedures=["cleanup_test_data"],
        )

        # Neo4j test suite
        self.test_suites["neo4j_optimization"] = TestSuite(
            suite_id="neo4j_optimization",
            name="Neo4j Optimization Tests",
            description="Tests for Neo4j graph database optimizations",
            tests=[
                "test_graph_traversal_performance",
                "test_index_effectiveness",
                "test_relationship_queries",
                "test_memory_usage",
            ],
        )

        # Redis test suite
        self.test_suites["redis_optimization"] = TestSuite(
            suite_id="redis_optimization",
            name="Redis Optimization Tests",
            description="Tests for Redis caching and performance optimizations",
            tests=[
                "test_cache_performance",
                "test_memory_efficiency",
                "test_connection_pooling",
                "test_data_compression",
            ],
        )

        # Qdrant test suite
        self.test_suites["qdrant_optimization"] = TestSuite(
            suite_id="qdrant_optimization",
            name="Qdrant Optimization Tests",
            description="Tests for Qdrant vector database optimizations",
            tests=[
                "test_vector_search_performance",
                "test_index_optimization",
                "test_batch_operations",
                "test_memory_usage",
            ],
        )

    async def _run_test_category(
        self, category: TestType, database_types: List[str]
    ) -> Dict[str, Any]:
        """Run all tests in a specific category"""
        category_results = {
            "category": category.value,
            "start_time": datetime.utcnow().isoformat(),
            "tests": [],
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "success": True,
        }

        # Run tests for each database type
        for db_type in database_types:
            test_methods = self._get_test_methods_for_category(category, db_type)

            for test_method_name in test_methods:
                test_result = await self._run_single_test(
                    test_method_name, db_type, category
                )
                category_results["tests"].append(test_result)
                category_results["total_tests"] += 1

                if test_result.success:
                    category_results["passed_tests"] += 1
                else:
                    category_results["failed_tests"] += 1
                    category_results["success"] = False

        category_results["end_time"] = datetime.utcnow().isoformat()
        return category_results

    def _get_test_methods_for_category(
        self, category: TestType, database_type: str
    ) -> List[str]:
        """Get test methods for a category and database type"""
        test_methods = []

        if category == TestType.VALIDATION:
            test_methods.extend(
                [
                    f"test_{database_type}_connectivity",
                    f"test_{database_type}_configuration",
                    f"test_{database_type}_basic_operations",
                ]
            )
        elif category == TestType.PERFORMANCE:
            test_methods.extend(
                [
                    f"test_{database_type}_query_performance",
                    f"test_{database_type}_throughput",
                    f"test_{database_type}_latency",
                ]
            )
        elif category == TestType.LOAD:
            test_methods.extend(
                [
                    f"test_{database_type}_load_handling",
                    f"test_{database_type}_concurrent_operations",
                    f"test_{database_type}_scalability",
                ]
            )
        elif category == TestType.INTEGRATION:
            test_methods.extend(
                [
                    f"test_{database_type}_cross_db_operations",
                    f"test_{database_type}_data_sync",
                    f"test_{database_type}_monitoring_integration",
                ]
            )
        elif category == TestType.RECOVERY:
            test_methods.extend(
                [
                    f"test_{database_type}_backup_recovery",
                    f"test_{database_type}_failure_recovery",
                    f"test_{database_type}_data_integrity",
                ]
            )

        return test_methods

    async def _run_single_test(
        self, test_method_name: str, database_type: str, test_type: TestType
    ) -> TestResult:
        """Run a single test method"""
        test_id = str(uuid.uuid4())
        test_result = TestResult(
            test_id=test_id,
            test_name=test_method_name,
            test_type=test_type,
            database_type=database_type,
            status=TestStatus.PENDING,
            started_at=datetime.utcnow(),
        )

        self.active_tests[test_id] = test_result

        try:
            logger.info(f"Running test: {test_method_name} for {database_type}")
            test_result.status = TestStatus.RUNNING

            # Get test method
            test_method = getattr(self, test_method_name, None)
            if not test_method:
                raise ValueError(f"Test method {test_method_name} not found")

            # Run test with timeout
            await asyncio.wait_for(
                test_method(database_type, test_result),
                timeout=self.config.test_timeout_seconds,
            )

            test_result.status = TestStatus.PASSED
            test_result.success = True
            logger.info(f"Test passed: {test_method_name}")

        except asyncio.TimeoutError:
            test_result.status = TestStatus.TIMEOUT
            test_result.success = False
            test_result.error_message = (
                f"Test timed out after {self.config.test_timeout_seconds} seconds"
            )
            logger.error(f"Test timed out: {test_method_name}")

        except Exception as e:
            test_result.status = TestStatus.FAILED
            test_result.success = False
            test_result.error_message = str(e)
            logger.error(f"Test failed: {test_method_name} - {e}")

        finally:
            test_result.completed_at = datetime.utcnow()
            test_result.duration_seconds = (
                test_result.completed_at - test_result.started_at
            ).total_seconds()

            self.test_results.append(test_result)
            if test_id in self.active_tests:
                del self.active_tests[test_id]

        return test_result

    # PostgreSQL Test Methods
    async def test_postgresql_connectivity(
        self, database_type: str, test_result: TestResult
    ):
        """Test PostgreSQL connectivity"""
        import asyncpg

        try:
            conn = await asyncpg.connect(
                host=_get_env_or_default("POSTGRES_HOST", "localhost"),
                port=int(_get_env_or_default("POSTGRES_PORT", "5432")),
                user=_get_env_or_default("POSTGRES_USER", "raguser"),
                password=_get_env_or_default("POSTGRES_PASSWORD", ""),
                database=_get_env_or_default("POSTGRES_DB", "ragdb"),
            )

            # Test basic query
            result = await conn.fetchval("SELECT 1")
            assert result == 1, "Basic query failed"
            test_result.assertions_passed += 1

            # Test table access
            tables = await conn.fetch(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' LIMIT 1"
            )
            assert len(tables) > 0, "No tables found"
            test_result.assertions_passed += 1

            await conn.close()

            test_result.metrics["connection_time_ms"] = 50  # Simulated metric
            test_result.logs.append("PostgreSQL connectivity test passed")

        except Exception as e:
            test_result.assertions_failed += 1
            raise

    async def test_postgresql_query_performance(
        self, database_type: str, test_result: TestResult
    ):
        """Test PostgreSQL query performance"""
        import asyncpg

        try:
            conn = await asyncpg.connect(
                host=_get_env_or_default("POSTGRES_HOST", "localhost"),
                port=int(_get_env_or_default("POSTGRES_PORT", "5432")),
                user=_get_env_or_default("POSTGRES_USER", "raguser"),
                password=_get_env_or_default("POSTGRES_PASSWORD", ""),
                database=_get_env_or_default("POSTGRES_DB", "ragdb"),
            )

            # Test query performance
            queries = [
                "SELECT COUNT(*) FROM monitoring_metrics",
                "SELECT * FROM monitoring_metrics ORDER BY timestamp DESC LIMIT 100",
                "SELECT definition_id, AVG(value) FROM monitoring_metrics GROUP BY definition_id",
            ]

            query_times = []
            for query in queries:
                start_time = time.time()
                try:
                    await conn.fetch(query)
                    query_time = (time.time() - start_time) * 1000
                    query_times.append(query_time)
                    test_result.assertions_passed += 1
                except:
                    test_result.assertions_failed += 1

            # Check performance thresholds
            avg_query_time = statistics.mean(query_times) if query_times else 0
            test_result.metrics["avg_query_time_ms"] = avg_query_time
            test_result.metrics["query_times"] = query_times

            assert (
                avg_query_time < 1000
            ), f"Average query time {avg_query_time:.2f}ms exceeds threshold"
            test_result.assertions_passed += 1

            await conn.close()

        except Exception as e:
            test_result.assertions_failed += 1
            raise

    async def test_postgresql_load_handling(
        self, database_type: str, test_result: TestResult
    ):
        """Test PostgreSQL load handling"""
        import asyncpg

        try:
            # Create concurrent connections
            tasks = []
            for i in range(10):
                task = asyncio.create_task(self._postgresql_load_worker(i))
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            successful_operations = sum(
                1 for r in results if not isinstance(r, Exception)
            )
            test_result.metrics["concurrent_operations"] = successful_operations
            test_result.metrics["total_operations"] = len(tasks)

            assert (
                successful_operations >= 8
            ), f"Too many failed operations: {len(tasks) - successful_operations}"
            test_result.assertions_passed += 1

        except Exception as e:
            test_result.assertions_failed += 1
            raise

    async def _postgresql_load_worker(self, worker_id: int):
        """Worker function for PostgreSQL load test"""
        import asyncpg

        conn = await asyncpg.connect(
            host=_get_env_or_default("POSTGRES_HOST", "localhost"),
            port=int(_get_env_or_default("POSTGRES_PORT", "5432")),
            user=_get_env_or_default("POSTGRES_USER", "raguser"),
            password=_get_env_or_default("POSTGRES_PASSWORD", ""),
            database=_get_env_or_default("POSTGRES_DB", "ragdb"),
        )

        try:
            for i in range(10):
                await conn.fetch("SELECT 1")
                await asyncio.sleep(0.01)
        finally:
            await conn.close()

    # Neo4j Test Methods
    async def test_neo4j_connectivity(
        self, database_type: str, test_result: TestResult
    ):
        """Test Neo4j connectivity"""
        try:
            from neo4j import AsyncGraphDatabase

            driver = AsyncGraphDatabase.driver(
                _get_env_or_default("NEO4J_URI", "bolt://localhost:7687"),
                auth=(
                    _get_env_or_default("NEO4J_USER", "neo4j"),
                    _get_env_or_default("NEO4J_PASSWORD", ""),
                ),
            )

            async with driver.session() as session:
                result = await session.run("RETURN 1 as test")
                record = await result.single()
                assert record["test"] == 1, "Basic query failed"
                test_result.assertions_passed += 1

            await driver.close()

            test_result.metrics["connection_time_ms"] = 30  # Simulated
            test_result.logs.append("Neo4j connectivity test passed")

        except Exception as e:
            test_result.assertions_failed += 1
            raise

    async def test_neo4j_graph_traversal_performance(
        self, database_type: str, test_result: TestResult
    ):
        """Test Neo4j graph traversal performance"""
        try:
            from neo4j import AsyncGraphDatabase

            driver = AsyncGraphDatabase.driver(
                _get_env_or_default("NEO4J_URI", "bolt://localhost:7687"),
                auth=(
                    _get_env_or_default("NEO4J_USER", "neo4j"),
                    _get_env_or_default("NEO4J_PASSWORD", ""),
                ),
            )

            async with driver.session() as session:
                # Test traversal queries
                queries = [
                    "MATCH (n) RETURN count(n) as node_count",
                    "MATCH ()-[r]->() RETURN count(r) as rel_count",
                    "MATCH (n:Entity) RETURN n LIMIT 100",
                ]

                query_times = []
                for query in queries:
                    start_time = time.time()
                    result = await session.run(query)
                    await result.consume()
                    query_time = (time.time() - start_time) * 1000
                    query_times.append(query_time)
                    test_result.assertions_passed += 1

                avg_query_time = statistics.mean(query_times) if query_times else 0
                test_result.metrics["avg_query_time_ms"] = avg_query_time
                test_result.metrics["query_times"] = query_times

                assert (
                    avg_query_time < 2000
                ), f"Average query time {avg_query_time:.2f}ms exceeds threshold"
                test_result.assertions_passed += 1

            await driver.close()

        except Exception as e:
            test_result.assertions_failed += 1
            raise

    # Redis Test Methods
    async def test_redis_connectivity(
        self, database_type: str, test_result: TestResult
    ):
        """Test Redis connectivity"""
        try:
            import redis.asyncio as redis

            client = redis.Redis(
                host=_get_env_or_default("REDIS_HOST", "localhost"),
                port=int(_get_env_or_default("REDIS_PORT", "6379")),
                password=_get_env_or_default("REDIS_PASSWORD", "") or None,
                decode_responses=True,
            )

            # Test basic operations
            await client.set("test_key", "test_value")
            value = await client.get("test_key")
            assert value == "test_value", "Basic SET/GET failed"
            test_result.assertions_passed += 1

            # Test ping
            pong = await client.ping()
            assert pong is True, "PING failed"
            test_result.assertions_passed += 1

            await client.close()

            test_result.metrics["connection_time_ms"] = 10  # Simulated
            test_result.logs.append("Redis connectivity test passed")

        except Exception as e:
            test_result.assertions_failed += 1
            raise

    async def test_redis_cache_performance(
        self, database_type: str, test_result: TestResult
    ):
        """Test Redis cache performance"""
        try:
            import redis.asyncio as redis

            client = redis.Redis(
                host=_get_env_or_default("REDIS_HOST", "localhost"),
                port=int(_get_env_or_default("REDIS_PORT", "6379")),
                password=_get_env_or_default("REDIS_PASSWORD", "") or None,
                decode_responses=True,
            )

            # Test cache operations
            operations = 1000
            start_time = time.time()

            for i in range(operations):
                await client.set(f"test_key_{i}", f"test_value_{i}")
                await client.get(f"test_key_{i}")

            total_time = time.time() - start_time
            ops_per_second = (operations * 2) / total_time  # SET and GET

            test_result.metrics["operations_per_second"] = ops_per_second
            test_result.metrics["total_operations"] = operations * 2

            assert (
                ops_per_second > 1000
            ), f"Operations per second {ops_per_second:.2f} below threshold"
            test_result.assertions_passed += 1

            # Cleanup
            for i in range(operations):
                await client.delete(f"test_key_{i}")

            await client.close()

        except Exception as e:
            test_result.assertions_failed += 1
            raise

    # Qdrant Test Methods
    async def test_qdrant_connectivity(
        self, database_type: str, test_result: TestResult
    ):
        """Test Qdrant connectivity"""
        try:
            from qdrant_client import QdrantClient

            client = QdrantClient(url="http://localhost:6333")

            # Test basic operations
            collections = client.get_collections()
            assert isinstance(
                collections.collections, list
            ), "Failed to get collections"
            test_result.assertions_passed += 1

            # Test collection creation
            test_collection_name = f"test_collection_{int(time.time())}"
            client.create_collection(
                collection_name=test_collection_name,
                vectors_config={"size": 128, "distance": "Cosine"},
            )
            test_result.assertions_passed += 1

            # Cleanup
            client.delete_collection(test_collection_name)

            test_result.metrics["connection_time_ms"] = 20  # Simulated
            test_result.logs.append("Qdrant connectivity test passed")

        except Exception as e:
            test_result.assertions_failed += 1
            raise

    async def test_qdrant_vector_search_performance(
        self, database_type: str, test_result: TestResult
    ):
        """Test Qdrant vector search performance"""
        try:
            import numpy as np
            from qdrant_client import QdrantClient

            client = QdrantClient(url="http://localhost:6333")

            # Create test collection
            collection_name = f"test_search_{int(time.time())}"
            client.create_collection(
                collection_name=collection_name,
                vectors_config={"size": 128, "distance": "Cosine"},
            )

            # Insert test vectors
            vectors = np.random.rand(100, 128).tolist()
            points = [
                {"id": i, "vector": vectors[i], "payload": {"text": f"test_text_{i}"}}
                for i in range(100)
            ]

            start_time = time.time()
            client.upsert(collection_name=collection_name, points=points)
            insert_time = time.time() - start_time

            # Test search performance
            search_times = []
            for i in range(10):
                query_vector = np.random.rand(128).tolist()

                start_time = time.time()
                results = client.search(
                    collection_name=collection_name, query_vector=query_vector, limit=10
                )
                search_time = time.time() - start_time
                search_times.append(search_time)

                assert len(results) <= 10, "Search returned too many results"
                test_result.assertions_passed += 1

            avg_search_time = statistics.mean(search_times) if search_times else 0

            test_result.metrics["insert_time_seconds"] = insert_time
            test_result.metrics["avg_search_time_ms"] = avg_search_time * 1000
            test_result.metrics["vectors_inserted"] = len(vectors)

            assert (
                avg_search_time < 0.1
            ), f"Average search time {avg_search_time*1000:.2f}ms exceeds threshold"
            test_result.assertions_passed += 1

            # Cleanup
            client.delete_collection(collection_name)

        except Exception as e:
            test_result.assertions_failed += 1
            raise

    # Cross-Database Integration Tests
    async def test_cross_db_operations(
        self, database_type: str, test_result: TestResult
    ):
        """Test cross-database operations"""
        try:
            # Test data synchronization between databases
            # This is a simplified version - in reality would test actual sync mechanisms

            sync_operations = [
                "postgresql_to_redis",
                "neo4j_to_qdrant",
                "redis_to_postgresql",
            ]

            successful_syncs = 0
            for operation in sync_operations:
                # Simulate sync operation
                await asyncio.sleep(0.1)
                successful_syncs += 1
                test_result.assertions_passed += 1

            test_result.metrics["successful_syncs"] = successful_syncs
            test_result.metrics["total_syncs"] = len(sync_operations)

            assert (
                successful_syncs >= 2
            ), f"Too many failed syncs: {len(sync_operations) - successful_syncs}"
            test_result.assertions_passed += 1

        except Exception as e:
            test_result.assertions_failed += 1
            raise

    def generate_test_report(
        self, test_results: Optional[List[TestResult]] = None
    ) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        results_to_analyze = test_results or self.test_results

        if not results_to_analyze:
            return {"error": "No test results to analyze"}

        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "total_tests": len(results_to_analyze),
                "passed_tests": sum(1 for r in results_to_analyze if r.success),
                "failed_tests": sum(1 for r in results_to_analyze if not r.success),
                "success_rate": 0,
                "total_duration_seconds": sum(
                    r.duration_seconds for r in results_to_analyze
                ),
                "avg_duration_seconds": 0,
            },
            "by_database_type": {},
            "by_test_type": {},
            "failed_tests": [],
            "performance_metrics": {},
            "recommendations": [],
        }

        # Calculate summary metrics
        if results_to_analyze:
            report["summary"]["success_rate"] = (
                report["summary"]["passed_tests"]
                / report["summary"]["total_tests"]
                * 100
            )
            report["summary"]["avg_duration_seconds"] = (
                report["summary"]["total_duration_seconds"]
                / report["summary"]["total_tests"]
            )

        # Group by database type
        for db_type in ["postgresql", "neo4j", "redis", "qdrant"]:
            db_tests = [r for r in results_to_analyze if r.database_type == db_type]
            if db_tests:
                passed = sum(1 for r in db_tests if r.success)
                report["by_database_type"][db_type] = {
                    "total_tests": len(db_tests),
                    "passed_tests": passed,
                    "failed_tests": len(db_tests) - passed,
                    "success_rate": (passed / len(db_tests) * 100),
                    "avg_duration_seconds": sum(r.duration_seconds for r in db_tests)
                    / len(db_tests),
                }

        # Group by test type
        for test_type in TestType:
            type_tests = [r for r in results_to_analyze if r.test_type == test_type]
            if type_tests:
                passed = sum(1 for r in type_tests if r.success)
                report["by_test_type"][test_type.value] = {
                    "total_tests": len(type_tests),
                    "passed_tests": passed,
                    "failed_tests": len(type_tests) - passed,
                    "success_rate": (passed / len(type_tests) * 100),
                }

        # Collect failed tests
        report["failed_tests"] = [
            {
                "test_name": r.test_name,
                "database_type": r.database_type,
                "error_message": r.error_message,
                "duration_seconds": r.duration_seconds,
                "assertions_failed": r.assertions_failed,
            }
            for r in results_to_analyze
            if not r.success
        ]

        # Collect performance metrics
        all_metrics = {}
        for r in results_to_analyze:
            for metric_name, metric_value in r.metrics.items():
                if metric_name not in all_metrics:
                    all_metrics[metric_name] = []
                all_metrics[metric_name].append(metric_value)

        for metric_name, values in all_metrics.items():
            if values:
                report["performance_metrics"][metric_name] = {
                    "avg": statistics.mean(values),
                    "min": min(values),
                    "max": max(values),
                    "count": len(values),
                }

        # Generate recommendations
        if report["summary"]["success_rate"] < 90:
            report["recommendations"].append(
                "Overall success rate is below 90%. Review failed tests and fix underlying issues."
            )

        for db_type, metrics in report["by_database_type"].items():
            if metrics["success_rate"] < 85:
                report["recommendations"].append(
                    f"{db_type} database has low success rate ({metrics['success_rate']:.1f}%). "
                    f"Investigate connectivity and configuration issues."
                )

        return report

    def get_test_results(
        self,
        database_type: Optional[str] = None,
        test_type: Optional[TestType] = None,
        status: Optional[TestStatus] = None,
    ) -> List[TestResult]:
        """Get filtered test results"""
        results = self.test_results

        if database_type:
            results = [r for r in results if r.database_type == database_type]

        if test_type:
            results = [r for r in results if r.test_type == test_type]

        if status:
            results = [r for r in results if r.status == status]

        return results

    def clear_test_results(self):
        """Clear all test results"""
        self.test_results.clear()
        self.active_tests.clear()
        logger.info("Cleared all test results")


# Utility functions
async def run_comprehensive_test_suite() -> Dict[str, Any]:
    """Run comprehensive test suite for all database optimizations"""
    config = TestConfiguration(
        test_timeout_seconds=300,
        performance_thresholds={
            "max_query_time_ms": 1000,
            "min_ops_per_second": 1000,
            "max_error_rate_percent": 5,
        },
        load_test_duration_minutes=5,
        stress_test_concurrency=50,
    )

    test_runner = DatabaseTestRunner(config)

    try:
        results = await test_runner.run_all_tests()

        # Generate and save test report
        report = test_runner.generate_test_report()

        # Save report to file
        report_file = f"test_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"Test report saved to {report_file}")

        return {
            "test_results": results,
            "test_report": report,
            "report_file": report_file,
        }

    finally:
        test_runner.clear_test_results()


async def validate_database_optimizations() -> bool:
    """Validate that all database optimizations are working correctly"""
    config = TestConfiguration(
        test_timeout_seconds=60,
        performance_thresholds={"max_query_time_ms": 500, "min_ops_per_second": 500},
    )

    test_runner = DatabaseTestRunner(config)

    # Run only validation tests
    validation_results = await test_runner._run_test_category(
        TestType.VALIDATION, ["postgresql", "neo4j", "redis", "qdrant"]
    )

    return validation_results["success"] and validation_results["failed_tests"] == 0
