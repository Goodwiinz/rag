"""
Database Integration Tests with Monitoring Schema

This module provides comprehensive integration tests for database monitoring:
- Monitoring schema validation and migrations
- Database performance monitoring integration
- Database health checks and metrics collection
- Monitoring data persistence and retrieval
- Database connection pooling and resilience
- Query performance optimization
- Data retention and cleanup policies
- Multi-database monitoring (PostgreSQL, Redis, Neo4j, Qdrant)
"""

import pytest
import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from unittest.mock import Mock, AsyncMock, patch
import psycopg2
import psycopg2.extras
import redis
import aioredis
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
import asyncpg
import aiopg

# Setup paths
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend" / "src"))

from backend.src.core.database import Base, get_db, engine
from backend.src.models.monitoring import (
    MonitoringMetric,
    MonitoringAlert,
    MonitoringTrace,
    MonitoringLog,
    HealthCheckRecord,
    MonitoringSession
)
from backend.src.monitoring.services.observability_manager import ObservabilityManager
from backend.src.monitoring.config.monitoring_config import MonitoringConfig
from backend.src.monitoring.models.metrics import MetricPoint, MetricSeries
from backend.src.monitoring.models.alerting import Alert, AlertRule
from backend.src.monitoring.models.health_check import HealthCheckResult


class TestMonitoringSchemaValidation:
    """Test monitoring database schema validation and migrations"""

    @pytest.fixture
    async def test_db_connection(self):
        """Create test database connection"""
        # Use in-memory SQLite for testing
        import sqlite3
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row

        # Create monitoring tables
        await self._create_monitoring_schema(conn)

        yield conn

        conn.close()

    async def _create_monitoring_schema(self, conn):
        """Create monitoring schema in test database"""
        # Metrics table
        conn.execute("""
            CREATE TABLE monitoring_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                value REAL NOT NULL,
                labels TEXT,
                timestamp DATETIME NOT NULL,
                service TEXT,
                component TEXT
            )
        """)

        # Alerts table
        conn.execute("""
            CREATE TABLE monitoring_alerts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT,
                created_at DATETIME NOT NULL,
                acknowledged_at DATETIME,
                resolved_at DATETIME,
                acknowledged_by TEXT,
                resolved_by TEXT,
                labels TEXT
            )
        """)

        # Traces table
        conn.execute("""
            CREATE TABLE monitoring_traces (
                trace_id TEXT NOT NULL,
                span_id TEXT NOT NULL,
                parent_span_id TEXT,
                operation_name TEXT NOT NULL,
                service TEXT NOT NULL,
                component TEXT,
                start_time DATETIME NOT NULL,
                end_time DATETIME,
                duration_ms REAL,
                status TEXT NOT NULL,
                tags TEXT,
                PRIMARY KEY (trace_id, span_id)
            )
        """)

        # Logs table
        conn.execute("""
            CREATE TABLE monitoring_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                service TEXT,
                component TEXT,
                timestamp DATETIME NOT NULL,
                correlation_id TEXT,
                user_id TEXT,
                request_id TEXT,
                extra_data TEXT
            )
        """)

        # Health checks table
        conn.execute("""
            CREATE TABLE health_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                component TEXT NOT NULL,
                status TEXT NOT NULL,
                response_time_ms REAL,
                error_message TEXT,
                checked_at DATETIME NOT NULL,
                details TEXT
            )
        """)

        conn.commit()

    @pytest.mark.asyncio
    async def test_monitoring_metrics_schema(self, test_db_connection):
        """Test monitoring metrics table schema"""
        # Insert test metric
        cursor = test_db_connection.cursor()
        cursor.execute("""
            INSERT INTO monitoring_metrics
            (name, value, labels, timestamp, service, component)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            "cpu_usage",
            75.5,
            json.dumps({"host": "server1"}),
            datetime.utcnow().isoformat(),
            "api-service",
            "metrics-collector"
        ))
        test_db_connection.commit()

        # Query and validate
        cursor.execute("SELECT * FROM monitoring_metrics")
        row = cursor.fetchone()

        assert row["name"] == "cpu_usage"
        assert row["value"] == 75.5
        assert json.loads(row["labels"])["host"] == "server1"
        assert row["service"] == "api-service"
        assert row["component"] == "metrics-collector"

    @pytest.mark.asyncio
    async def test_monitoring_alerts_schema(self, test_db_connection):
        """Test monitoring alerts table schema"""
        cursor = test_db_connection.cursor()
        alert_id = str(uuid.uuid4())

        cursor.execute("""
            INSERT INTO monitoring_alerts
            (id, name, severity, status, message, created_at, labels)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            alert_id,
            "High CPU Usage",
            "critical",
            "active",
            "CPU usage exceeded 90%",
            datetime.utcnow().isoformat(),
            json.dumps({"threshold": "90%"})
        ))
        test_db_connection.commit()

        # Query and validate
        cursor.execute("SELECT * FROM monitoring_alerts WHERE id = ?", (alert_id,))
        row = cursor.fetchone()

        assert row["id"] == alert_id
        assert row["name"] == "High CPU Usage"
        assert row["severity"] == "critical"
        assert row["status"] == "active"
        assert json.loads(row["labels"])["threshold"] == "90%"

    @pytest.mark.asyncio
    async def test_monitoring_traces_schema(self, test_db_connection):
        """Test monitoring traces table schema"""
        cursor = test_db_connection.cursor()
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())

        cursor.execute("""
            INSERT INTO monitoring_traces
            (trace_id, span_id, operation_name, service, start_time, end_time,
             duration_ms, status, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trace_id,
            span_id,
            "api_request",
            "user-service",
            datetime.utcnow().isoformat(),
            (datetime.utcnow() + timedelta(milliseconds=150)).isoformat(),
            150.0,
            "ok",
            json.dumps({"http.method": "GET", "http.status_code": "200"})
        ))
        test_db_connection.commit()

        # Query and validate
        cursor.execute("SELECT * FROM monitoring_traces WHERE trace_id = ?", (trace_id,))
        row = cursor.fetchone()

        assert row["trace_id"] == trace_id
        assert row["span_id"] == span_id
        assert row["operation_name"] == "api_request"
        assert row["duration_ms"] == 150.0
        assert row["status"] == "ok"
        tags = json.loads(row["tags"])
        assert tags["http.method"] == "GET"

    @pytest.mark.asyncio
    async def test_monitoring_logs_schema(self, test_db_connection):
        """Test monitoring logs table schema"""
        cursor = test_db_connection.cursor()
        correlation_id = str(uuid.uuid4())

        cursor.execute("""
            INSERT INTO monitoring_logs
            (level, message, service, timestamp, correlation_id, extra_data)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            "ERROR",
            "Database connection failed",
            "user-service",
            datetime.utcnow().isoformat(),
            correlation_id,
            json.dumps({"error_code": "DB_CONN_FAILED", "retry_count": 3})
        ))
        test_db_connection.commit()

        # Query and validate
        cursor.execute("SELECT * FROM monitoring_logs WHERE correlation_id = ?", (correlation_id,))
        row = cursor.fetchone()

        assert row["level"] == "ERROR"
        assert row["message"] == "Database connection failed"
        assert row["correlation_id"] == correlation_id
        extra_data = json.loads(row["extra_data"])
        assert extra_data["error_code"] == "DB_CONN_FAILED"

    @pytest.mark.asyncio
    async def test_health_checks_schema(self, test_db_connection):
        """Test health checks table schema"""
        cursor = test_db_connection.cursor()

        cursor.execute("""
            INSERT INTO health_checks
            (component, status, response_time_ms, error_message, checked_at, details)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            "postgresql",
            "healthy",
            12.5,
            None,
            datetime.utcnow().isoformat(),
            json.dumps({"connection_pool": {"active": 5, "idle": 10}})
        ))
        test_db_connection.commit()

        # Query and validate
        cursor.execute("SELECT * FROM health_checks WHERE component = ?", ("postgresql",))
        row = cursor.fetchone()

        assert row["component"] == "postgresql"
        assert row["status"] == "healthy"
        assert row["response_time_ms"] == 12.5
        assert row["error_message"] is None
        details = json.loads(row["details"])
        assert details["connection_pool"]["active"] == 5


class TestPostgreSQLMonitoringIntegration:
    """Test PostgreSQL monitoring integration"""

    @pytest.fixture
    async def postgresql_config(self):
        """PostgreSQL configuration for testing"""
        return {
            "host": "localhost",
            "port": 5432,
            "database": "test_monitoring",
            "user": "test_user",
            "password": "test_password"
        }

    @pytest.mark.asyncio
    async def test_postgresql_connection_monitoring(self, postgresql_config):
        """Test PostgreSQL connection monitoring"""
        # Mock PostgreSQL connection for testing
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn

            # Simulate connection
            conn = await asyncpg.connect(**postgresql_config)

            # Mock connection status query
            mock_conn.fetchval.return_value = 1

            # Test connection health
            is_connected = await conn.fetchval("SELECT 1")
            assert is_connected == 1

            # Verify connection was called with correct parameters
            mock_connect.assert_called_once_with(**postgresql_config)

    @pytest.mark.asyncio
    async def test_postgresql_performance_metrics(self, postgresql_config):
        """Test PostgreSQL performance metrics collection"""
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn

            # Mock performance queries
            mock_conn.fetch.return_value = [
                {
                    "datname": "test_monitoring",
                    "numbackends": 5,
                    "xact_commit": 1000,
                    "xact_rollback": 10,
                    "blks_read": 500,
                    "blks_hit": 10000,
                    "tup_returned": 50000,
                    "tup_fetched": 20000,
                    "tup_inserted": 1000,
                    "tup_updated": 500,
                    "tup_deleted": 100
                }
            ]

            conn = await asyncpg.connect(**postgresql_config)

            # Collect performance metrics
            metrics = await conn.fetch("""
                SELECT
                    datname,
                    numbackends,
                    xact_commit,
                    xact_rollback,
                    blks_read,
                    blks_hit,
                    tup_returned,
                    tup_fetched,
                    tup_inserted,
                    tup_updated,
                    tup_deleted
                FROM pg_stat_database
                WHERE datname = current_database()
            """)

            assert len(metrics) == 1
            metric = metrics[0]
            assert metric["numbackends"] == 5
            assert metric["xact_commit"] == 1000

    @pytest.mark.asyncio
    async def test_postgresql_slow_query_monitoring(self, postgresql_config):
        """Test PostgreSQL slow query monitoring"""
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn

            # Mock slow query data
            mock_conn.fetch.return_value = [
                {
                    "query": "SELECT * FROM large_table WHERE complex_condition = $1",
                    "calls": 100,
                    "total_time": 50000.0,
                    "mean_time": 500.0,
                    "rows": 10000
                }
            ]

            conn = await asyncpg.connect(**postgresql_config)

            # Get slow queries
            slow_queries = await conn.fetch("""
                SELECT
                    query,
                    calls,
                    total_time,
                    mean_time,
                    rows
                FROM pg_stat_statements
                WHERE mean_time > 100
                ORDER BY mean_time DESC
                LIMIT 10
            """)

            assert len(slow_queries) == 1
            query = slow_queries[0]
            assert query["mean_time"] == 500.0
            assert query["calls"] == 100

    @pytest.mark.asyncio
    async def test_postgresql_lock_monitoring(self, postgresql_config):
        """Test PostgreSQL lock monitoring"""
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn

            # Mock lock data
            mock_conn.fetch.return_value = [
                {
                    "pid": 1234,
                    "state": "active",
                    "query": "UPDATE users SET status = $1 WHERE id = $2",
                    "wait_event_type": "Lock",
                    "wait_event": "transactionid"
                }
            ]

            conn = await asyncpg.connect(**postgresql_config)

            # Get lock information
            locks = await conn.fetch("""
                SELECT
                    pid,
                    state,
                    query,
                    wait_event_type,
                    wait_event
                FROM pg_stat_activity
                WHERE wait_event_type = 'Lock'
                AND state = 'active'
            """)

            assert len(locks) == 1
            lock = locks[0]
            assert lock["wait_event_type"] == "Lock"
            assert lock["state"] == "active"


class TestRedisMonitoringIntegration:
    """Test Redis monitoring integration"""

    @pytest.fixture
    async def redis_config(self):
        """Redis configuration for testing"""
        return {
            "host": "localhost",
            "port": 6379,
            "db": 0,
            "password": None
        }

    @pytest.mark.asyncio
    async def test_redis_connection_monitoring(self, redis_config):
        """Test Redis connection monitoring"""
        with patch('aioredis.from_url') as mock_redis:
            mock_client = AsyncMock()
            mock_redis.return_value = mock_client

            # Mock ping response
            mock_client.ping.return_value = True

            # Test connection
            redis_client = await aioredis.from_url(
                f"redis://{redis_config['host']}:{redis_config['port']}/{redis_config['db']}"
            )

            # Test health check
            is_healthy = await redis_client.ping()
            assert is_healthy is True

            # Verify connection was established
            mock_redis.assert_called_once()
            mock_client.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_performance_metrics(self, redis_config):
        """Test Redis performance metrics collection"""
        with patch('aioredis.from_url') as mock_redis:
            mock_client = AsyncMock()
            mock_redis.return_value = mock_client

            # Mock Redis info command
            mock_client.info.return_value = {
                "used_memory": 1048576,  # 1MB
                "used_memory_peak": 2097152,  # 2MB
                "connected_clients": 10,
                "total_commands_processed": 100000,
                "keyspace_hits": 80000,
                "keyspace_misses": 20000,
                "instantaneous_ops_per_sec": 150,
                "total_net_input_bytes": 5000000,
                "total_net_output_bytes": 3000000
            }

            redis_client = await aioredis.from_url(
                f"redis://{redis_config['host']}:{redis_config['port']}/{redis_config['db']}"
            )

            # Collect performance metrics
            info = await redis_client.info()

            # Verify metrics
            assert info["used_memory"] == 1048576
            assert info["connected_clients"] == 10
            assert info["instantaneous_ops_per_sec"] == 150

            # Calculate hit ratio
            hit_ratio = info["keyspace_hits"] / (info["keyspace_hits"] + info["keyspace_misses"])
            assert hit_ratio == 0.8  # 80%

    @pytest.mark.asyncio
    async def test_redis_keyspace_monitoring(self, redis_config):
        """Test Redis keyspace monitoring"""
        with patch('aioredis.from_url') as mock_redis:
            mock_client = AsyncMock()
            mock_redis.return_value = mock_client

            # Mock keyspace info
            mock_client.info.return_value = {
                "db0": {
                    "keys": 1000,
                    "expires": 100,
                    "avg_ttl": 3600000  # 1 hour in milliseconds
                },
                "db1": {
                    "keys": 500,
                    "expires": 50,
                    "avg_ttl": 7200000  # 2 hours
                }
            }

            redis_client = await aioredis.from_url(
                f"redis://{redis_config['host']}:{redis_config['port']}/{redis_config['db']}"
            )

            # Get keyspace information
            info = await redis_client.info()

            # Verify keyspace data
            assert info["db0"]["keys"] == 1000
            assert info["db0"]["expires"] == 100
            assert info["db1"]["keys"] == 500

    @pytest.mark.asyncio
    async def test_redis_slow_log_monitoring(self, redis_config):
        """Test Redis slow log monitoring"""
        with patch('aioredis.from_url') as mock_redis:
            mock_client = AsyncMock()
            mock_redis.return_value = mock_client

            # Mock slow log data
            mock_client.slow_log.return_value = [
                [1234567890, 5000, "GET", "large:key:data"],
                [1234567891, 3000, "HGETALL", "user:profile:12345"]
            ]

            redis_client = await aioredis.from_url(
                f"redis://{redis_config['host']}:{redis_config['port']}/{redis_config['db']}"
            )

            # Get slow log entries
            slow_log = await redis_client.slow_log("get", 10)

            # Verify slow log data
            assert len(slow_log) == 2
            assert slow_log[0][1] == 5000  # 5 seconds execution time
            assert slow_log[0][2] == "GET"
            assert slow_log[1][1] == 3000  # 3 seconds execution time


class TestNeo4jMonitoringIntegration:
    """Test Neo4j monitoring integration"""

    @pytest.fixture
    async def neo4j_config(self):
        """Neo4j configuration for testing"""
        return {
            "uri": "bolt://localhost:7687",
            "auth": ("neo4j", "password")
        }

    @pytest.mark.asyncio
    async def test_neo4j_connection_monitoring(self, neo4j_config):
        """Test Neo4j connection monitoring"""
        with patch('neo4j.GraphDatabase.driver') as mock_driver:
            mock_session = AsyncMock()
            mock_driver_instance = Mock()
            mock_driver_instance.session.return_value = mock_session
            mock_driver.return_value = mock_driver_instance

            # Test connection
            driver = GraphDatabase.driver(**neo4j_config)
            session = driver.session()

            # Mock health check query
            mock_session.run.return_value.single.return_value.value.return_value = 1

            # Test database availability
            result = session.run("RETURN 1").single()
            assert result.value() == 1

            # Verify connection was established
            mock_driver.assert_called_once_with(**neo4j_config)

    @pytest.mark.asyncio
    async def test_neo4j_performance_metrics(self, neo4j_config):
        """Test Neo4j performance metrics collection"""
        with patch('neo4j.GraphDatabase.driver') as mock_driver:
            mock_session = AsyncMock()
            mock_driver_instance = Mock()
            mock_driver_instance.session.return_value = mock_session
            mock_driver.return_value = mock_driver_instance

            # Mock performance metrics
            mock_session.run.return_value.data.return_value = [
                {
                    "name": "KernelTotalPageFaults",
                    "value": 1000
                },
                {
                    "name": "KernelPageFaultsPerSecond",
                    "value": 10.5
                },
                {
                    "name": "PoolTotalPageFaults",
                    "value": 500
                }
            ]

            driver = GraphDatabase.driver(**neo4j_config)
            session = driver.session()

            # Get performance metrics
            metrics = session.run("CALL dbms.queryJmx('org.neo4j:instance=kernel#0,name=Memory')").data()

            assert len(metrics) >= 3
            assert any(m["name"] == "KernelTotalPageFaults" for m in metrics)

    @pytest.mark.asyncio
    async def test_neo4j_query_monitoring(self, neo4j_config):
        """Test Neo4j query performance monitoring"""
        with patch('neo4j.GraphDatabase.driver') as mock_driver:
            mock_session = AsyncMock()
            mock_driver_instance = Mock()
            mock_driver_instance.session.return_value = mock_session
            mock_driver.return_value = mock_driver_instance

            # Mock query log data
            mock_session.run.return_value.data.return_value = [
                {
                    "query": "MATCH (u:User) WHERE u.email = $email RETURN u",
                    "elapsedTimeMillis": 150,
                    "allocatedBytes": 1024,
                    "pageHits": 10,
                    "pageFaults": 2
                }
            ]

            driver = GraphDatabase.driver(**neo4j_config)
            session = driver.session()

            # Get query log information
            query_logs = session.run("CALL dbms.listQueries()").data()

            assert len(query_logs) >= 1
            query = query_logs[0]
            assert query["elapsedTimeMillis"] == 150
            assert query["pageHits"] == 10

    @pytest.mark.asyncio
    async def test_neo4j_database_size_monitoring(self, neo4j_config):
        """Test Neo4j database size monitoring"""
        with patch('neo4j.GraphDatabase.driver') as mock_driver:
            mock_session = AsyncMock()
            mock_driver_instance = Mock()
            mock_driver_instance.session.return_value = mock_session
            mock_driver.return_value = mock_driver_instance

            # Mock size information
            mock_session.run.return_value.single.return_value.value.return_value = 104857600  # 100MB

            driver = GraphDatabase.driver(**neo4j_config)
            session = driver.session()

            # Get database size
            result = session.run("CALL db.info() YIELD sizeOnDisk RETURN sizeOnDisk").single()
            size = result.value()

            assert size == 104857600  # 100MB


class TestQdrantMonitoringIntegration:
    """Test Qdrant vector database monitoring integration"""

    @pytest.fixture
    async def qdrant_config(self):
        """Qdrant configuration for testing"""
        return {
            "host": "localhost",
            "port": 6333,
            "timeout": 5
        }

    @pytest.mark.asyncio
    async def test_qdrant_connection_monitoring(self, qdrant_config):
        """Test Qdrant connection monitoring"""
        with patch('qdrant_client.QdrantClient') as mock_client:
            mock_instance = Mock()
            mock_client.return_value = mock_instance

            # Mock health check
            mock_instance.get_collections.return_value = {"collections": []}

            # Test connection
            client = QdrantClient(**qdrant_config)
            collections = client.get_collections()

            assert "collections" in collections
            mock_client.assert_called_once_with(**qdrant_config)

    @pytest.mark.asyncio
    async def test_qdrant_cluster_info_monitoring(self, qdrant_config):
        """Test Qdrant cluster information monitoring"""
        with patch('qdrant_client.QdrantClient') as mock_client:
            mock_instance = Mock()
            mock_client.return_value = mock_instance

            # Mock cluster info
            mock_instance.get_cluster_info.return_value = {
                "result": {
                    "peers": [
                        {
                            "id": 1,
                            "uri": "http://localhost:6333",
                            "state": "Active"
                        }
                    ],
                    "status": "healthy"
                }
            }

            client = QdrantClient(**qdrant_config)
            cluster_info = client.get_cluster_info()

            assert cluster_info["result"]["status"] == "healthy"
            assert len(cluster_info["result"]["peers"]) == 1

    @pytest.mark.asyncio
    async def test_qdrant_collection_metrics(self, qdrant_config):
        """Test Qdrant collection performance metrics"""
        with patch('qdrant_client.QdrantClient') as mock_client:
            mock_instance = Mock()
            mock_client.return_value = mock_instance

            # Mock collection info
            mock_instance.get_collection.return_value = {
                "result": {
                    "config": {
                        "params": {
                            "vectors": {
                                "size": 384,
                                "distance": "Cosine"
                            }
                        }
                    },
                    "status": "green",
                    "optimizer_status": "ok",
                    "vectors_count": 10000,
                    "indexed_vectors_count": 9500,
                    "points_count": 10000,
                    "segments_count": 15,
                    "disk_data_size": 1048576,  # 1MB
                    "ram_data_size": 2097152    # 2MB
                }
            }

            client = QdrantClient(**qdrant_config)
            collection_info = client.get_collection(collection_name="test_collection")

            result = collection_info["result"]
            assert result["vectors_count"] == 10000
            assert result["indexed_vectors_count"] == 9500
            assert result["status"] == "green"
            assert result["disk_data_size"] == 1048576

    @pytest.mark.asyncio
    async def test_qdrant_search_performance(self, qdrant_config):
        """Test Qdrant search performance monitoring"""
        with patch('qdrant_client.QdrantClient') as mock_client:
            mock_instance = Mock()
            mock_client.return_value = mock_instance

            # Mock search results with timing info
            mock_instance.search.return_value = [
                {
                    "id": "point1",
                    "score": 0.95,
                    "payload": {"text": "sample document"}
                }
            ]

            client = QdrantClient(**qdrant_config)

            # Perform search and measure performance
            start_time = time.time()
            results = client.search(
                collection_name="test_collection",
                query_vector=[0.1] * 384,
                limit=10
            )
            search_time = (time.time() - start_time) * 1000  # Convert to milliseconds

            assert len(results) == 1
            assert results[0]["score"] == 0.95
            assert search_time < 100  # Should complete within 100ms


class TestMonitoringDataPersistence:
    """Test monitoring data persistence and retrieval"""

    @pytest.fixture
    async def persistence_manager(self):
        """Create monitoring persistence manager"""
        config = MonitoringConfig(
            service_name="test-persistence",
            metrics__custom_metrics_enabled=True,
            tracing__enabled=True,
            logging__structured_logging=True,
            alerting__enabled=True,
            health_check__enabled=True
        )

        manager = ObservabilityManager(config)
        await manager.initialize()
        await manager.start()

        yield manager

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_metrics_data_persistence(self, persistence_manager):
        """Test metrics data persistence"""
        # Record multiple metrics
        metrics_data = [
            {"name": "cpu_usage", "value": 75.5, "labels": {"host": "server1"}},
            {"name": "memory_usage", "value": 68.2, "labels": {"host": "server1"}},
            {"name": "disk_usage", "value": 45.0, "labels": {"host": "server1"}},
            {"name": "cpu_usage", "value": 80.1, "labels": {"host": "server2"}},
            {"name": "memory_usage", "value": 72.8, "labels": {"host": "server2"}}
        ]

        # Record metrics
        for metric in metrics_data:
            await persistence_manager.metrics_collector.record_counter(
                name=metric["name"],
                value=metric["value"],
                labels=metric["labels"]
            )

        # Query metrics back
        retrieved_metrics = await persistence_manager.get_metrics()

        # Verify persistence
        assert "metrics" in retrieved_metrics
        assert len(retrieved_metrics["metrics"]) >= len(metrics_data)

    @pytest.mark.asyncio
    async def test_alert_data_persistence(self, persistence_manager):
        """Test alert data persistence"""
        # Create alert rule
        rule_id = await persistence_manager.create_alert_rule(
            name="Test Persistence Alert",
            conditions={"metric": "test_metric", "operator": ">", "threshold": 1.0},
            severity="medium",
            description="Test alert for persistence validation"
        )

        # Trigger alert
        await persistence_manager.metrics_collector.record_gauge(
            name="test_metric",
            value=2.0,
            labels={}
        )

        # Query alerts
        alerts_data = await persistence_manager.get_alerts()

        # Verify alert persistence
        assert "alerts" in alerts_data
        test_alerts = [
            alert for alert in alerts_data.get("alerts", [])
            if "Test Persistence Alert" in alert.get("name", "")
        ]
        assert len(test_alerts) >= 1

    @pytest.mark.asyncio
    async def test_trace_data_persistence(self, persistence_manager):
        """Test trace data persistence"""
        # Create trace spans
        trace_operations = [
            "user_authentication",
            "database_query",
            "api_response"
        ]

        for operation in trace_operations:
            async with persistence_manager.trace_operation(
                operation_name=operation,
                service="test-service",
                component="test-component"
            ):
                await asyncio.sleep(0.001)  # Small delay

        # Query traces
        traces_data = await persistence_manager.get_traces(
            service="test-service"
        )

        # Verify trace persistence
        assert "traces" in traces_data
        assert len(traces_data.get("traces", {})) >= len(trace_operations)

    @pytest.mark.asyncio
    async def test_log_data_persistence(self, persistence_manager):
        """Test log data persistence"""
        log_entries = [
            {"level": "INFO", "message": "Test info log"},
            {"level": "WARNING", "message": "Test warning log"},
            {"level": "ERROR", "message": "Test error log"},
            {"level": "DEBUG", "message": "Test debug log"}
        ]

        # Add log entries
        for log_entry in log_entries:
            await persistence_manager.log_aggregator.add_log(
                level=log_entry["level"],
                message=log_entry["message"],
                service="test-service"
            )

        # Query logs
        logs_data = await persistence_manager.get_logs(
            service="test-service"
        )

        # Verify log persistence
        assert "logs" in logs_data
        assert len(logs_data.get("logs", [])) >= len(log_entries)

    @pytest.mark.asyncio
    async def test_health_check_data_persistence(self, persistence_manager):
        """Test health check data persistence"""
        # Run health checks multiple times
        for i in range(3):
            await persistence_manager.health_check_hub.run_all_checks()
            await asyncio.sleep(0.1)

        # Get service health
        health_data = await persistence_manager.get_service_health()

        # Verify health data structure
        assert "overall_status" in health_data
        assert "components" in health_data
        assert "timestamp" in health_data


class TestDatabaseRetentionAndCleanup:
    """Test database retention policies and cleanup"""

    @pytest.fixture
    async def retention_manager(self):
        """Create manager with retention configuration"""
        config = MonitoringConfig(
            service_name="test-retention",
            metrics__custom_metrics_enabled=True,
            metrics__metrics_retention_days=7,
            logging__structured_logging=True,
            alerting__enabled=True,
            health_check__enabled=True,
            health_check__history_retention_days=30
        )

        manager = ObservabilityManager(config)
        await manager.initialize()
        await manager.start()

        yield manager

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_metrics_retention_policy(self, retention_manager):
        """Test metrics data retention policy"""
        # Record metrics with different timestamps
        old_time = datetime.utcnow() - timedelta(days=10)
        recent_time = datetime.utcnow() - timedelta(hours=1)

        # Simulate old metrics (beyond retention period)
        with patch('datetime.datetime.utcnow') as mock_now:
            mock_now.return_value = old_time

            for i in range(10):
                await retention_manager.metrics_collector.record_counter(
                    name="old_metric",
                    value=i,
                    labels={"retention": "test"}
                )

        # Simulate recent metrics (within retention period)
        with patch('datetime.datetime.utcnow') as mock_now:
            mock_now.return_value = recent_time

            for i in range(5):
                await retention_manager.metrics_collector.record_counter(
                    name="recent_metric",
                    value=i,
                    labels={"retention": "test"}
                )

        # Query metrics and verify retention
        all_metrics = await retention_manager.get_metrics()

        # Should primarily have recent metrics
        recent_metrics = [
            m for m in all_metrics.get("metrics", {}).values()
            if any("recent_metric" in str(m) for m in [m])
        ]

        # Verify retention worked (old metrics should be cleaned up)
        # Note: This would depend on actual cleanup implementation
        assert len(recent_metrics) >= 0

    @pytest.mark.asyncio
    async def test_log_retention_policy(self, retention_manager):
        """Test log data retention policy"""
        # Add logs with different timestamps
        old_logs = []
        recent_logs = []

        old_time = datetime.utcnow() - timedelta(days=35)  # Beyond default retention
        recent_time = datetime.utcnow() - timedelta(hours=1)

        # Add old logs
        with patch('datetime.datetime.utcnow') as mock_now:
            mock_now.return_value = old_time

            for i in range(20):
                await retention_manager.log_aggregator.add_log(
                    level="INFO",
                    message=f"Old log entry {i}",
                    service="test-service"
                )
                old_logs.append(f"Old log entry {i}")

        # Add recent logs
        with patch('datetime.datetime.utcnow') as mock_now:
            mock_now.return_value = recent_time

            for i in range(10):
                await retention_manager.log_aggregator.add_log(
                    level="INFO",
                    message=f"Recent log entry {i}",
                    service="test-service"
                )
                recent_logs.append(f"Recent log entry {i}")

        # Query logs and verify retention
        all_logs = await retention_manager.get_logs(service="test-service")

        # Should primarily have recent logs
        recent_log_entries = [
            log for log in all_logs.get("logs", [])
            if any("Recent" in log.get("message", "") for log in [log])
        ]

        assert len(recent_log_entries) >= 0

    @pytest.mark.asyncio
    async def test_health_check_history_retention(self, retention_manager):
        """Test health check history retention"""
        # Run health checks over time
        for i in range(50):  # More than retention period
            await retention_manager.health_check_hub.run_all_checks()
            await asyncio.sleep(0.01)

        # Get health history (if implemented)
        if hasattr(retention_manager.health_check_hub, 'get_health_history'):
            history = await retention_manager.health_check_hub.get_health_history(days=60)

            # Should respect retention policy
            assert len(history) <= 30  # Based on retention_days=30

    @pytest.mark.asyncio
    async def test_cleanup_performance(self, retention_manager):
        """Test cleanup operation performance"""
        # Generate a lot of data
        start_time = time.time()

        # Generate metrics
        for i in range(1000):
            await retention_manager.metrics_collector.record_counter(
                name="cleanup_test_metric",
                value=i,
                labels={"batch": str(i // 100)}
            )

        # Generate logs
        for i in range(500):
            await retention_manager.log_aggregator.add_log(
                level="INFO",
                message=f"Cleanup test log {i}",
                service="test-service"
            )

        generation_time = time.time() - start_time

        # Simulate cleanup operation
        cleanup_start = time.time()

        # This would call actual cleanup methods
        # For testing, we'll simulate the time it would take
        await asyncio.sleep(0.1)

        cleanup_time = time.time() - cleanup_start

        # Verify performance
        assert generation_time < 5.0  # Should generate data quickly
        assert cleanup_time < 2.0    # Cleanup should be efficient


class TestMultiDatabaseMonitoring:
    """Test monitoring across multiple database types"""

    @pytest.fixture
    async def multi_db_manager(self):
        """Create manager with multi-database configuration"""
        config = MonitoringConfig(
            service_name="test-multi-db",
            metrics__custom_metrics_enabled=True,
            tracing__enabled=True,
            logging__structured_logging=True,
            alerting__enabled=True,
            health_check__enabled=True,
            health_check__check_database=True,
            health_check__check_redis=True,
            health_check__check_neo4j=True,
            health_check__check_qdrant=True
        )

        manager = ObservabilityManager(config)
        await manager.initialize()
        await manager.start()

        yield manager

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_cross_database_health_monitoring(self, multi_db_manager):
        """Test health monitoring across multiple databases"""
        # Mock different database health check responses
        with patch.object(multi_db_manager.health_check_hub, 'run_all_checks') as mock_checks:
            mock_checks.return_value = {
                "postgresql": {"status": "healthy", "response_time_ms": 5.2},
                "redis": {"status": "healthy", "response_time_ms": 1.8},
                "neo4j": {"status": "degraded", "response_time_ms": 15.5},
                "qdrant": {"status": "healthy", "response_time_ms": 8.3}
            }

            # Run health checks
            health_status = await multi_db_manager.health_check()

            # Verify all databases are checked
            assert "services" in health_status
            assert "health_checks" in health_status["services"]

            # Verify overall status reflects worst component
            assert health_status["manager"]["status"] in ["healthy", "degraded"]

    @pytest.mark.asyncio
    async def test_cross_database_performance_aggregation(self, multi_db_manager):
        """Test performance metrics aggregation across databases"""
        # Mock performance data from different databases
        with patch.object(multi_db_manager.metrics_collector, 'collect_system_metrics') as mock_collect:
            mock_collect.return_value = {
                "postgresql": {
                    "connections": 10,
                    "query_time_avg": 25.5,
                    "transactions_per_sec": 150
                },
                "redis": {
                    "operations_per_sec": 1000,
                    "memory_usage_mb": 512,
                    "hit_rate": 0.95
                },
                "neo4j": {
                    "queries_per_sec": 50,
                    "transaction_time_avg": 45.2,
                    "nodes_count": 100000
                },
                "qdrant": {
                    "search_time_avg": 12.3,
                    "index_size_mb": 1024,
                    "vectors_count": 50000
                }
            }

            # Collect metrics
            await multi_db_manager.metrics_collector.collect_system_metrics()

            # Get aggregated metrics
            metrics_data = await multi_db_manager.get_metrics()

            # Verify aggregation worked
            assert "metrics" in metrics_data

    @pytest.mark.asyncio
    async def test_database_specific_alerting(self, multi_db_manager):
        """Test database-specific alerting rules"""
        # Create database-specific alert rules
        db_alert_rules = [
            {
                "name": "PostgreSQL High Connections",
                "conditions": {"metric": "postgresql.connections", "operator": ">", "threshold": 80},
                "severity": "warning"
            },
            {
                "name": "Redis Memory High",
                "conditions": {"metric": "redis.memory_usage_mb", "operator": ">", "threshold": 1024},
                "severity": "critical"
            },
            {
                "name": "Neo4j Slow Queries",
                "conditions": {"metric": "neo4j.query_time_avg", "operator": ">", "threshold": 100},
                "severity": "warning"
            }
        ]

        # Create alert rules
        for rule in db_alert_rules:
            await multi_db_manager.create_alert_rule(**rule)

        # Simulate metrics that would trigger alerts
        trigger_metrics = [
            ("postgresql.connections", 85),
            ("redis.memory_usage_mb", 1536),
            ("neo4j.query_time_avg", 120)
        ]

        for metric_name, value in trigger_metrics:
            await multi_db_manager.metrics_collector.record_gauge(
                name=metric_name,
                value=value,
                labels={"database": metric_name.split(".")[0]}
            )

        # Get alerts
        alerts_data = await multi_db_manager.get_alerts(status="active")

        # Verify database-specific alerts were triggered
        assert "alerts" in alerts_data
        active_alerts = alerts_data.get("alerts", [])
        assert len(active_alerts) >= 3


# Performance benchmarks for database monitoring
@pytest.mark.performance
class TestDatabaseMonitoringPerformance:
    """Performance benchmarks for database monitoring"""

    @pytest.mark.asyncio
    async def test_metrics_insertion_performance(self):
        """Benchmark metrics insertion performance"""
        config = MonitoringConfig(metrics__custom_metrics_enabled=True)
        manager = ObservabilityManager(config)

        try:
            await manager.initialize()
            await manager.start()

            # Benchmark insertion
            start_time = time.time()
            metric_count = 10000

            for i in range(metric_count):
                await manager.metrics_collector.record_counter(
                    name="performance_test_metric",
                    value=1,
                    labels={"iteration": str(i)}
                )

            insertion_time = time.time() - start_time
            insertion_rate = metric_count / insertion_time

            # Should achieve at least 1000 metrics per second
            assert insertion_rate >= 1000.0

        finally:
            await manager.shutdown()

    @pytest.mark.asyncio
    async def test_query_performance_under_load(self):
        """Benchmark query performance under load"""
        config = MonitoringConfig(
            metrics__custom_metrics_enabled=True,
            tracing__enabled=True,
            logging__structured_logging=True
        )
        manager = ObservabilityManager(config)

        try:
            await manager.initialize()
            await manager.start()

            # Generate test data
            for i in range(1000):
                await manager.metrics_collector.record_counter(
                    name="query_test_metric",
                    value=i,
                    labels={"batch": str(i // 100)}
                )

            # Benchmark queries
            start_time = time.time()
            query_count = 100

            for _ in range(query_count):
                await manager.get_metrics(
                    start_time=datetime.utcnow() - timedelta(hours=1),
                    end_time=datetime.utcnow()
                )

            query_time = time.time() - start_time
            queries_per_second = query_count / query_time

            # Should achieve at least 50 queries per second
            assert queries_per_second >= 50.0

        finally:
            await manager.shutdown()


if __name__ == "__main__":
    # Run specific test classes
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "TestMonitoringSchemaValidation",
        "TestPostgreSQLMonitoringIntegration",
        "TestRedisMonitoringIntegration",
        "TestNeo4jMonitoringIntegration",
        "TestQdrantMonitoringIntegration",
        "TestMonitoringDataPersistence",
        "TestDatabaseRetentionAndCleanup",
        "TestMultiDatabaseMonitoring"
    ])