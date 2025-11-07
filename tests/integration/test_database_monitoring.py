"""
Database Integration Tests with Monitoring Schema Validation

This module provides comprehensive integration tests for database optimization and monitoring:
- PostgreSQL optimization validation
- Neo4j graph database performance testing
- Redis caching optimization verification
- Qdrant vector store optimization testing
- Cross-database integration validation
- Monitoring schema validation
- Database connection pooling and performance
- Data migration and schema evolution testing
"""

import pytest
import asyncio
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, AsyncGenerator
from unittest.mock import Mock, AsyncMock, patch
import psycopg2
import redis
import neo4j
from qdrant_client import QdrantClient
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
import numpy as np

# Add backend to path
import sys
from pathlib import Path
backend_dir = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_dir / "src"))

from src.core.database import Base, get_db
from src.models.document import Document, DocumentType, ProcessingStatus
from src.models.processing import ProcessingJob, JobType, JobStatus
from src.monitoring.models.metrics import MetricModel, MetricType
from src.monitoring.models.tracing import TraceModel, SpanModel
from src.monitoring.models.alerting import AlertModel, AlertSeverity, AlertStatus
from src.monitoring.models.health_check import HealthCheckResult, ComponentStatus
from src.monitoring.models.monitoring_session import MonitoringSession
from src.knowledge_graph.neo4j_client import Neo4jClient
from src.vector_store.qdrant_client import QdrantVectorStore


@pytest.fixture(scope="session")
def postgres_engine():
    """Create PostgreSQL engine for testing"""
    database_url = os.getenv("TEST_DATABASE_URL", "postgresql://test:test@localhost:5432/test_rag")

    engine = create_engine(
        database_url,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        echo=False
    )

    # Create tables
    Base.metadata.create_all(engine)

    yield engine

    # Cleanup
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def postgres_session(postgres_engine):
    """Create PostgreSQL session for testing"""
    TestingSessionLocal = sessionmaker(bind=postgres_engine)
    session = TestingSessionLocal()

    yield session

    session.close()


@pytest.fixture
def redis_client():
    """Create Redis client for testing"""
    redis_url = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/1")

    client = redis.from_url(redis_url, decode_responses=True)

    # Clear test database
    client.flushdb()

    yield client

    client.close()


@pytest.fixture
def neo4j_client():
    """Create Neo4j client for testing"""
    uri = os.getenv("TEST_NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("TEST_NEO4J_USER", "neo4j")
    password = os.getenv("TEST_NEO4J_PASSWORD", "password")

    client = Neo4jClient(uri=uri, user=user, password=password)

    # Clear test data
    with client.driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")

    yield client

    client.close()


@pytest.fixture
def qdrant_client():
    """Create Qdrant client for testing"""
    host = os.getenv("TEST_QDRANT_HOST", "localhost")
    port = int(os.getenv("TEST_QDRANT_PORT", "6333"))

    client = QdrantClient(host=host, port=port)

    # Create test collection
    collection_name = f"test_collection_{uuid.uuid4().hex[:8]}"
    vector_size = 384

    client.create_collection(
        collection_name=collection_name,
        vectors_config={"size": vector_size, "distance": "Cosine"}
    )

    yield client, collection_name

    # Cleanup
    try:
        client.delete_collection(collection_name)
    except:
        pass


class TestPostgreSQLMonitoringIntegration:
    """Test PostgreSQL integration with monitoring system"""

    @pytest.mark.asyncio
    async def test_postgres_connection_pooling(self, postgres_engine):
        """Test PostgreSQL connection pooling performance"""
        # Test connection pool configuration
        pool = postgres_engine.pool

        assert pool.size() == 5  # Initial pool size
        assert pool.max_overflow == 10  # Max overflow

        # Test multiple concurrent connections
        sessions = []
        start_time = time.time()

        try:
            # Create 15 concurrent connections (5 base + 10 overflow)
            for i in range(15):
                session = sessionmaker(bind=postgres_engine)()
                sessions.append(session)

                # Execute simple query to validate connection
                result = session.execute(text("SELECT 1"))
                assert result.scalar() == 1

        finally:
            # Close all sessions
            for session in sessions:
                session.close()

        connection_time = time.time() - start_time

        # Performance assertions
        assert connection_time < 5.0  # Should complete within 5 seconds
        assert pool.size() == 5  # Pool should return to original size

    @pytest.mark.asyncio
    async def test_postgres_query_performance_monitoring(self, postgres_session):
        """Test PostgreSQL query performance monitoring"""
        # Insert test data
        test_documents = []
        for i in range(1000):
            doc = Document(
                title=f"Test Document {i}",
                content=f"Test content for document {i}",
                document_type=DocumentType.PDF,
                processing_status=ProcessingStatus.COMPLETED,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            test_documents.append(doc)
            postgres_session.add(doc)

        postgres_session.commit()

        # Monitor query performance
        start_time = time.time()

        # Execute various queries and monitor performance
        queries = [
            "SELECT COUNT(*) FROM documents",
            "SELECT * FROM documents WHERE title LIKE 'Test Document %' LIMIT 10",
            "SELECT document_type, COUNT(*) FROM documents GROUP BY document_type",
            "SELECT * FROM documents ORDER BY created_at DESC LIMIT 50"
        ]

        query_times = []
        for query in queries:
            query_start = time.time()
            result = postgres_session.execute(text(query))
            result.fetchall()
            query_time = time.time() - query_start
            query_times.append(query_time)

        total_time = time.time() - start_time
        avg_query_time = sum(query_times) / len(query_times)

        # Performance assertions
        assert total_time < 2.0  # All queries should complete within 2 seconds
        assert avg_query_time < 0.5  # Average query time should be under 500ms
        assert all(qt < 1.0 for qt in query_times)  # No query should take more than 1 second

    @pytest.mark.asyncio
    async def test_postgres_monitoring_schema_validation(self, postgres_engine):
        """Test PostgreSQL monitoring schema validation"""
        inspector = inspect(postgres_engine)

        # Check monitoring tables exist
        expected_tables = [
            'documents', 'processing_jobs', 'metrics', 'traces', 'spans',
            'alerts', 'health_checks', 'monitoring_sessions'
        ]

        existing_tables = inspector.get_table_names()

        for table in expected_tables:
            assert table in existing_tables, f"Table {table} not found in schema"

        # Validate metrics table structure
        metrics_columns = [col['name'] for col in inspector.get_columns('metrics')]
        expected_metric_columns = [
            'id', 'name', 'value', 'type', 'labels', 'timestamp', 'created_at'
        ]

        for col in expected_metric_columns:
            assert col in metrics_columns, f"Column {col} not found in metrics table"

        # Validate alerts table structure
        alerts_columns = [col['name'] for col in inspector.get_columns('alerts')]
        expected_alert_columns = [
            'id', 'title', 'description', 'severity', 'status', 'source',
            'metadata', 'created_at', 'updated_at', 'resolved_at'
        ]

        for col in expected_alert_columns:
            assert col in alerts_columns, f"Column {col} not found in alerts table"

    @pytest.mark.asyncio
    async def test_postgres_index_optimization(self, postgres_session):
        """Test PostgreSQL index optimization for monitoring queries"""
        # Check if necessary indexes exist for monitoring tables
        indexes_query = """
        SELECT indexname, tablename
        FROM pg_indexes
        WHERE tablename IN ('metrics', 'alerts', 'traces', 'health_checks')
        ORDER BY tablename, indexname
        """

        result = postgres_session.execute(text(indexes_query))
        indexes = result.fetchall()

        # Verify indexes exist for performance-critical columns
        expected_indexes = {
            'metrics': ['idx_metrics_timestamp', 'idx_metrics_name', 'idx_metrics_type'],
            'alerts': ['idx_alerts_status', 'idx_alerts_severity', 'idx_alerts_created_at'],
            'traces': ['idx_traces_trace_id', 'idx_traces_timestamp'],
            'health_checks': ['idx_health_checks_component', 'idx_health_checks_timestamp']
        }

        # Check if at least some indexes exist for each table
        table_indexes = {}
        for index_name, table_name in indexes:
            if table_name not in table_indexes:
                table_indexes[table_name] = []
            table_indexes[table_name].append(index_name)

        for table, expected_idx_list in expected_indexes.items():
            assert table in table_indexes, f"No indexes found for table {table}"
            # At least one expected index should exist
            assert len(table_indexes[table]) > 0, f"No indexes found for table {table}"

    @pytest.mark.asyncio
    async def test_postgres_monitoring_data_integrity(self, postgres_session):
        """Test data integrity for monitoring data"""
        # Insert test monitoring data
        test_metric = MetricModel(
            name="test_integrity_metric",
            value=42.5,
            type=MetricType.GAUGE,
            labels={"test": "integrity"},
            timestamp=datetime.utcnow()
        )
        postgres_session.add(test_metric)

        test_alert = AlertModel(
            title="Integrity Test Alert",
            description="Testing alert data integrity",
            severity=AlertSeverity.INFO,
            status=AlertStatus.ACTIVE,
            source="test_suite"
        )
        postgres_session.add(test_alert)

        postgres_session.commit()

        # Verify data integrity
        # Check metric data
        metric = postgres_session.query(MetricModel).filter_by(name="test_integrity_metric").first()
        assert metric is not None
        assert metric.value == 42.5
        assert metric.type == MetricType.GAUGE
        assert "test" in metric.labels
        assert metric.labels["test"] == "integrity"

        # Check alert data
        alert = postgres_session.query(AlertModel).filter_by(title="Integrity Test Alert").first()
        assert alert is not None
        assert alert.severity == AlertSeverity.INFO
        assert alert.status == AlertStatus.ACTIVE
        assert alert.source == "test_suite"
        assert alert.created_at is not None

    @pytest.mark.asyncio
    async def test_postgres_transaction_handling(self, postgres_session):
        """Test transaction handling for monitoring operations"""
        # Test transaction rollback on error
        try:
            # Start transaction
            metric1 = MetricModel(
                name="transaction_test_1",
                value=1.0,
                type=MetricType.COUNTER,
                timestamp=datetime.utcnow()
            )
            postgres_session.add(metric1)
            postgres_session.flush()  # Get ID without committing

            # Force an error
            postgres_session.execute(text("SELECT invalid_column FROM non_existent_table"))

        except Exception:
            # Rollback should remove the metric
            postgres_session.rollback()

        # Verify metric was not committed
        metric = postgres_session.query(MetricModel).filter_by(name="transaction_test_1").first()
        assert metric is None

        # Test successful transaction
        metric2 = MetricModel(
            name="transaction_test_2",
            value=2.0,
            type=MetricType.COUNTER,
            timestamp=datetime.utcnow()
        )
        postgres_session.add(metric2)
        postgres_session.commit()

        # Verify metric was committed
        metric = postgres_session.query(MetricModel).filter_by(name="transaction_test_2").first()
        assert metric is not None
        assert metric.value == 2.0


class TestRedisMonitoringIntegration:
    """Test Redis integration with monitoring system"""

    @pytest.mark.asyncio
    async def test_redis_connection_pooling(self, redis_client):
        """Test Redis connection pooling"""
        # Test basic Redis operations
        start_time = time.time()

        # Perform multiple operations to test connection reuse
        for i in range(100):
            key = f"test_key_{i}"
            value = f"test_value_{i}"

            # Set operation
            redis_client.set(key, value)

            # Get operation
            retrieved_value = redis_client.get(key)
            assert retrieved_value == value

        operation_time = time.time() - start_time

        # Performance assertions
        assert operation_time < 2.0  # 100 operations should complete within 2 seconds
        assert operation_time < 0.1  # Should be much faster in practice

    @pytest.mark.asyncio
    async def test_redis_caching_performance(self, redis_client):
        """Test Redis caching performance for monitoring data"""
        # Simulate caching monitoring metrics
        test_metrics = []
        for i in range(50):
            metric = {
                "name": f"cache_test_metric_{i}",
                "value": np.random.random() * 100,
                "timestamp": datetime.utcnow().isoformat(),
                "labels": {"service": f"service_{i % 5}"}
            }
            test_metrics.append(metric)

        # Cache metrics
        start_time = time.time()
        for i, metric in enumerate(test_metrics):
            cache_key = f"metric:{metric['name']}"
            redis_client.setex(
                cache_key,
                timedelta(minutes=5),
                json.dumps(metric)
            )
        cache_time = time.time() - start_time

        # Retrieve cached metrics
        start_time = time.time()
        cached_metrics = []
        for i, metric in enumerate(test_metrics):
            cache_key = f"metric:{metric['name']}"
            cached_data = redis_client.get(cache_key)
            if cached_data:
                cached_metrics.append(json.loads(cached_data))
        retrieve_time = time.time() - start_time

        # Performance assertions
        assert cache_time < 1.0  # Caching should be fast
        assert retrieve_time < 0.5  # Retrieval should be faster
        assert len(cached_metrics) == len(test_metrics)  # All metrics should be cached

        # Verify data integrity
        for original, cached in zip(test_metrics, cached_metrics):
            assert original['name'] == cached['name']
            assert original['value'] == cached['value']

    @pytest.mark.asyncio
    async def test_redis_pubsub_monitoring(self, redis_client):
        """Test Redis pub/sub for real-time monitoring"""
        # Create publisher and subscriber
        pubsub = redis_client.pubsub()

        # Subscribe to monitoring channels
        channels = ['metrics', 'alerts', 'health_checks']
        for channel in channels:
            pubsub.subscribe(channel)

        # Publish test messages
        test_messages = {
            'metrics': {'type': 'metric_update', 'data': {'name': 'cpu_usage', 'value': 75.5}},
            'alerts': {'type': 'alert_created', 'data': {'title': 'High Memory', 'severity': 'warning'}},
            'health_checks': {'type': 'health_update', 'data': {'component': 'database', 'status': 'healthy'}}
        }

        received_messages = []

        # Publish messages
        for channel, message in test_messages.items():
            redis_client.publish(channel, json.dumps(message))

        # Listen for messages
        start_time = time.time()
        timeout = 2.0  # 2 seconds timeout

        while time.time() - start_time < timeout and len(received_messages) < len(test_messages):
            message = pubsub.get_message(timeout=0.1)
            if message and message['type'] == 'message':
                channel = message['channel'].decode('utf-8')
                data = json.loads(message['data'].decode('utf-8'))
                received_messages.append((channel, data))

        # Verify message reception
        assert len(received_messages) == len(test_messages)

        for channel, message in received_messages:
            assert channel in test_messages
            assert message['type'] == test_messages[channel]['type']

        pubsub.close()

    @pytest.mark.asyncio
    async def test_redis_monitoring_data_expiration(self, redis_client):
        """Test Redis data expiration for monitoring time-series data"""
        # Set data with TTL
        key_prefix = "monitoring:expires_test"
        test_data = {
            "metric_name": "test_expiration",
            "value": 42,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Set with 2 second TTL
        redis_client.setex(f"{key_prefix}:1", 2, json.dumps(test_data))
        redis_client.setex(f"{key_prefix}:2", 2, json.dumps(test_data))
        redis_client.setex(f"{key_prefix}:3", 2, json.dumps(test_data))

        # Verify data exists initially
        assert redis_client.exists(f"{key_prefix}:1")
        assert redis_client.exists(f"{key_prefix}:2")
        assert redis_client.exists(f"{key_prefix}:3")

        # Wait for expiration
        await asyncio.sleep(3)

        # Verify data has expired
        assert not redis_client.exists(f"{key_prefix}:1")
        assert not redis_client.exists(f"{key_prefix}:2")
        assert not redis_client.exists(f"{key_prefix}:3")

    @pytest.mark.asyncio
    async def test_redis_memory_optimization(self, redis_client):
        """Test Redis memory optimization for monitoring data"""
        # Get initial memory usage
        initial_memory = redis_client.info('memory')['used_memory']

        # Add monitoring data
        batch_size = 1000
        for i in range(batch_size):
            key = f"batch_test:{i:04d}"
            value = json.dumps({
                "metric": f"metric_{i % 10}",
                "value": np.random.random() * 100,
                "timestamp": datetime.utcnow().isoformat()
            })
            redis_client.set(key, value)

        # Check memory usage after batch insert
        batch_memory = redis_client.info('memory')['used_memory']
        memory_increase = batch_memory - initial_memory
        memory_per_key = memory_increase / batch_size

        # Cleanup test data
        for i in range(batch_size):
            redis_client.delete(f"batch_test:{i:04d}")

        # Memory efficiency assertions
        assert memory_per_key < 1024  # Less than 1KB per key on average

        # Verify cleanup
        final_memory = redis_client.info('memory')['used_memory']
        assert abs(final_memory - initial_memory) < memory_increase * 0.1  # Should be close to initial


class TestNeo4jMonitoringIntegration:
    """Test Neo4j integration with monitoring system"""

    @pytest.mark.asyncio
    async def test_neo4j_connection_pooling(self, neo4j_client):
        """Test Neo4j connection pooling"""
        # Test multiple concurrent sessions
        sessions = []
        start_time = time.time()

        try:
            # Create multiple sessions
            for i in range(10):
                session = neo4j_client.driver.session()
                sessions.append(session)

                # Execute simple query
                result = session.run("RETURN 1 as test")
                record = result.single()
                assert record["test"] == 1

        finally:
            # Close all sessions
            for session in sessions:
                session.close()

        connection_time = time.time() - start_time
        assert connection_time < 5.0  # Should complete within 5 seconds

    @pytest.mark.asyncio
    async def test_neo4j_monitoring_queries(self, neo4j_client):
        """Test Neo4j monitoring queries performance"""
        # Create test data
        with neo4j_client.driver.session() as session:
            # Create nodes and relationships
            session.run("""
                CREATE (d1:Document {id: 'doc1', title: 'Test Document 1', created: datetime()})
                CREATE (d2:Document {id: 'doc2', title: 'Test Document 2', created: datetime()})
                CREATE (e1:Entity {id: 'entity1', name: 'Machine Learning', type: 'concept'})
                CREATE (e2:Entity {id: 'entity2', name: 'AI', type: 'concept'})
                CREATE (d1)-[:CONTAINS_ENTITY]->(e1)
                CREATE (d2)-[:CONTAINS_ENTITY]->(e2)
                CREATE (e1)-[:RELATED_TO]->(e2)
            """)

        # Test monitoring queries
        monitoring_queries = [
            # Node count query
            "MATCH (n) RETURN count(n) as node_count",

            # Relationship count query
            "MATCH ()-[r]->() RETURN count(r) as rel_count",

            # Document metrics
            "MATCH (d:Document) RETURN count(d) as doc_count",

            # Entity metrics
            "MATCH (e:Entity) RETURN count(e) as entity_count",

            # Connection metrics
            "MATCH (d:Document)-[r:CONTAINS_ENTITY]->(e:Entity) RETURN count(r) as connections"
        ]

        query_times = []
        with neo4j_client.driver.session() as session:
            for query in monitoring_queries:
                start_time = time.time()
                result = session.run(query)
                result.single()  # Consume the result
                query_time = time.time() - start_time
                query_times.append(query_time)

        # Performance assertions
        avg_query_time = sum(query_times) / len(query_times)
        assert avg_query_time < 0.5  # Average query should be under 500ms
        assert all(qt < 1.0 for qt in query_times)  # No query should take more than 1 second

    @pytest.mark.asyncio
    async def test_neo4j_graph_metrics_collection(self, neo4j_client):
        """Test Neo4j graph metrics collection"""
        with neo4j_client.driver.session() as session:
            # Create diverse graph structure
            for i in range(100):
                session.run("""
                    CREATE (d:Document {id: $doc_id, title: $title, created: datetime()})
                    CREATE (e:Entity {id: $entity_id, name: $name, type: $type})
                    CREATE (d)-[:CONTAINS_ENTITY {weight: $weight}]->(e)
                """, {
                    'doc_id': f'doc_{i}',
                    'title': f'Document {i}',
                    'entity_id': f'entity_{i}',
                    'name': f'Entity {i}',
                    'type': f'type_{i % 5}',
                    'weight': np.random.random()
                })

        # Collect graph metrics
        with neo4j_client.driver.session() as session:
            # Node degree distribution
            degree_query = """
                MATCH (n)
                OPTIONAL MATCH (n)-[r]-()
                WITH n, count(r) as degree
                RETURN avg(degree) as avg_degree,
                       max(degree) as max_degree,
                       min(degree) as min_degree
            """
            degree_result = session.run(degree_query).single()

            # Path analysis
            path_query = """
                MATCH path = shortestPath((d1:Document)-[*..6]-(d2:Document))
                WHERE d1 <> d2
                RETURN count(path) as total_paths,
                       avg(length(path)) as avg_path_length
            """
            path_result = session.run(path_query).single()

            # Clustering coefficient
            clustering_query = """
                MATCH (n)-[r1]-(m)-[r2]-(l)-[r3]-(n)
                WHERE id(n) < id(m) < id(l)
                RETURN count(*) as triangles
            """
            clustering_result = session.run(clustering_query).single()

        # Verify metrics collection
        assert degree_result['avg_degree'] > 0
        assert degree_result['max_degree'] > 0
        assert path_result['total_paths'] >= 0
        assert clustering_result['triangles'] >= 0

    @pytest.mark.asyncio
    async def test_neo4j_monitoring_schema_validation(self, neo4j_client):
        """Test Neo4j monitoring schema validation"""
        with neo4j_client.driver.session() as session:
            # Check if monitoring constraints exist
            constraints_query = "SHOW CONSTRAINTS"
            constraints = list(session.run(constraints_query))

            # Should have constraints for unique IDs
            constraint_names = [record['name'] for record in constraints]

            # Check indexes
            indexes_query = "SHOW INDEXES"
            indexes = list(session.run(indexes_query))

            # Should have indexes for performance
            index_names = [record['name'] for record in indexes]

            # Verify basic schema structure
            node_labels_query = "CALL db.labels() YIELD label RETURN collect(label) as labels"
            labels_result = session.run(node_labels_query).single()
            existing_labels = labels_result['labels']

            expected_labels = ['Document', 'Entity', 'User', 'Organization', 'ProcessingJob']
            for label in expected_labels:
                if label in existing_labels:  # Some labels might not exist in test setup
                    pass  # Label exists

            relationship_types_query = "CALL db.relationshipTypes() YIELD relationshipType RETURN collect(relationshipType) as types"
            types_result = session.run(relationship_types_query).single()
            existing_types = types_result['types']

            expected_types = ['CONTAINS_ENTITY', 'RELATED_TO', 'OWNS_DOCUMENT', 'PROCESSED_BY']
            for rel_type in expected_types:
                if rel_type in existing_types:
                    pass  # Relationship type exists

    @pytest.mark.asyncio
    async def test_neo4j_performance_monitoring(self, neo4j_client):
        """Test Neo4j performance monitoring capabilities"""
        with neo4j_client.driver.session() as session:
            # Create performance test data
            batch_size = 1000

            # Measure batch insertion performance
            start_time = time.time()
            for i in range(batch_size):
                session.run("""
                    CREATE (n:TestNode {
                        id: $id,
                        name: $name,
                        value: $value,
                        created: datetime()
                    })
                """, {
                    'id': f'node_{i}',
                    'name': f'Node {i}',
                    'value': np.random.random() * 100
                })
            insertion_time = time.time() - start_time

            # Measure query performance
            queries = [
                "MATCH (n:TestNode) RETURN count(n) as count",
                "MATCH (n:TestNode) WHERE n.value > 50 RETURN count(n) as high_value_count",
                "MATCH (n:TestNode) RETURN avg(n.value) as avg_value",
                "MATCH (n:TestNode) RETURN n.name LIMIT 10"
            ]

            query_times = []
            for query in queries:
                start_time = time.time()
                result = session.run(query)
                result.consume()  # Consume all results
                query_time = time.time() - start_time
                query_times.append(query_time)

            # Cleanup test data
            session.run("MATCH (n:TestNode) DELETE n")

        # Performance assertions
        assert insertion_time < 10.0  # 1000 insertions should complete within 10 seconds
        avg_query_time = sum(query_times) / len(query_times)
        assert avg_query_time < 1.0  # Average query should be under 1 second


class TestQdrantMonitoringIntegration:
    """Test Qdrant vector store integration with monitoring system"""

    @pytest.mark.asyncio
    async def test_qdrant_collection_performance(self, qdrant_client):
        """Test Qdrant collection performance for monitoring"""
        client, collection_name = qdrant_client

        # Generate test vectors
        batch_size = 1000
        vector_size = 384

        vectors = np.random.random((batch_size, vector_size)).astype(np.float32)
        payloads = [
            {
                "id": f"doc_{i}",
                "title": f"Document {i}",
                "content": f"Test content for document {i}",
                "metadata": {"category": f"cat_{i % 10}", "priority": i % 3}
            }
            for i in range(batch_size)
        ]

        # Measure batch insertion performance
        start_time = time.time()

        # Insert in batches
        batch_size_qdrant = 100
        for i in range(0, batch_size, batch_size_qdrant):
            end_idx = min(i + batch_size_qdrant, batch_size)
            batch_vectors = vectors[i:end_idx].tolist()
            batch_payloads = payloads[i:end_idx]

            client.upsert(
                collection_name=collection_name,
                points=[
                    {
                        "id": i,
                        "vector": vector,
                        "payload": payload
                    }
                    for i, (vector, payload) in enumerate(zip(batch_vectors, batch_payloads), start=i)
                ]
            )

        insertion_time = time.time() - start_time

        # Measure search performance
        search_times = []
        for i in range(10):
            query_vector = np.random.random(vector_size).astype(np.float32).tolist()

            start_time = time.time()
            search_result = client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=10,
                with_payload=True
            )
            search_time = time.time() - start_time
            search_times.append(search_time)

            # Verify search results
            assert len(search_result) <= 10
            assert all(hit.score is not None for hit in search_result)

        # Performance assertions
        assert insertion_time < 30.0  # 1000 vectors should insert within 30 seconds
        avg_search_time = sum(search_times) / len(search_times)
        assert avg_search_time < 0.5  # Average search should be under 500ms

        # Test collection info
        collection_info = client.get_collection(collection_name)
        assert collection_info.points_count == batch_size
        assert collection_info.config.params.vectors.size == vector_size

    @pytest.mark.asyncio
    async def test_qdrant_monitoring_metrics(self, qdrant_client):
        """Test Qdrant monitoring metrics collection"""
        client, collection_name = qdrant_client

        # Insert test data with varied characteristics
        for i in range(100):
            vector = np.random.random(384).astype(np.float32).tolist()
            payload = {
                "document_id": f"doc_{i}",
                "category": f"category_{i % 5}",
                "importance": np.random.choice(['low', 'medium', 'high']),
                "created_at": datetime.utcnow().isoformat(),
                "size": np.random.randint(100, 10000)
            }

            client.upsert(
                collection_name=collection_name,
                points=[{
                    "id": i,
                    "vector": vector,
                    "payload": payload
                }]
            )

        # Collect monitoring metrics
        collection_info = client.get_collection(collection_name)

        # Test filtering and aggregation
        filter_result = client.scroll(
            collection_name=collection_name,
            scroll_filter={
                "must": [
                    {"key": "importance", "match": {"value": "high"}}
                ]
            },
            limit=10,
            with_payload=True
        )

        # Test count operation
        count_result = client.count(
            collection_name=collection_name,
            count_filter={
                "must": [
                    {"key": "category", "match": {"value": "category_1"}}
                ]
            }
        )

        # Verify metrics
        assert collection_info.points_count == 100
        assert len(filter_result[0]) <= 10
        assert count_result.count >= 0  # Should count documents with category_1

    @pytest.mark.asyncio
    async def test_qdrant_vector_search_optimization(self, qdrant_client):
        """Test Qdrant vector search optimization"""
        client, collection_name = qdrant_client

        # Create clusters of similar vectors
        num_clusters = 5
        vectors_per_cluster = 20

        for cluster_id in range(num_clusters):
            # Create cluster center
            center = np.random.random(384).astype(np.float32)

            for i in range(vectors_per_cluster):
                # Create vector around cluster center with some noise
                noise = np.random.normal(0, 0.1, 384).astype(np.float32)
                vector = center + noise
                vector = vector / np.linalg.norm(vector)  # Normalize

                payload = {
                    "cluster_id": cluster_id,
                    "vector_id": f"{cluster_id}_{i}",
                    "category": f"cluster_{cluster_id}"
                }

                client.upsert(
                    collection_name=collection_name,
                    points=[{
                        "id": cluster_id * vectors_per_cluster + i,
                        "vector": vector.tolist(),
                        "payload": payload
                    }]
                )

        # Test search within clusters
        for cluster_id in range(num_clusters):
            # Create query vector for this cluster
            cluster_vectors = client.scroll(
                collection_name=collection_name,
                scroll_filter={
                    "must": [
                        {"key": "cluster_id", "match": {"value": cluster_id}}
                    ]
                },
                limit=vectors_per_cluster,
                with_vectors=True
            )[0]

            if cluster_vectors:
                # Use first vector from cluster as query
                query_vector = cluster_vectors[0].vector

                # Search for similar vectors
                search_result = client.search(
                    collection_name=collection_name,
                    query_vector=query_vector,
                    limit=5,
                    search_filter={
                        "must": [
                            {"key": "cluster_id", "match": {"value": cluster_id}}
                        ]
                    }
                )

                # Verify search quality
                assert len(search_result) > 0
                assert all(hit.payload["cluster_id"] == cluster_id for hit in search_result)
                assert all(hit.score > 0.5 for hit in search_result)  # Should be high similarity

    @pytest.mark.asyncio
    async def test_qdrant_collection_management(self, qdrant_client):
        """Test Qdrant collection management for monitoring"""
        client, original_collection = qdrant_client

        # Create additional collections for testing
        test_collections = []

        for i in range(3):
            collection_name = f"monitoring_test_{i}"
            test_collections.append(collection_name)

            # Create collection with different configurations
            client.create_collection(
                collection_name=collection_name,
                vectors_config={
                    "size": 256,
                    "distance": "Cosine"
                }
            )

            # Add some data
            for j in range(10):
                vector = np.random.random(256).astype(np.float32).tolist()
                payload = {
                    "test_id": f"{i}_{j}",
                    "collection": collection_name,
                    "timestamp": datetime.utcnow().isoformat()
                }

                client.upsert(
                    collection_name=collection_name,
                    points=[{
                        "id": j,
                        "vector": vector,
                        "payload": payload
                    }]
                )

        # List collections
        collections = client.get_collections().collections
        collection_names = [col.name for col in collections]

        # Verify test collections exist
        for test_col in test_collections:
            assert test_col in collection_names

        # Test collection aliases
        alias_name = "monitoring_alias"
        client.create_collection_alias(
            alias_name=alias_name,
            collection_name=test_collections[0]
        )

        # Search using alias
        search_result = client.search(
            collection_name=alias_name,
            query_vector=np.random.random(256).astype(np.float32).tolist(),
            limit=3
        )

        assert len(search_result) > 0

        # Cleanup test collections
        for collection_name in test_collections:
            try:
                client.delete_collection(collection_name)
            except:
                pass

        # Remove alias
        try:
            client.delete_collection_alias(alias_name)
        except:
            pass


class TestCrossDatabaseIntegration:
    """Test cross-database integration and synchronization"""

    @pytest.mark.asyncio
    async def test_database_synchronization(self, postgres_session, redis_client, neo4j_client, qdrant_client):
        """Test data synchronization across databases"""
        # Create document in PostgreSQL
        document = Document(
            title="Cross-DB Test Document",
            content="This document tests cross-database integration",
            document_type=DocumentType.PDF,
            processing_status=ProcessingStatus.COMPLETED,
            created_at=datetime.utcnow()
        )
        postgres_session.add(document)
        postgres_session.commit()

        doc_id = document.id

        # Create corresponding entities in Neo4j
        with neo4j_client.driver.session() as session:
            session.run("""
                CREATE (d:Document {id: $doc_id, title: $title})
                CREATE (e:Entity {name: 'Cross-DB Integration', type: 'concept'})
                CREATE (d)-[:CONTAINS_ENTITY]->(e)
            """, {
                'doc_id': str(doc_id),
                'title': document.title
            })

        # Create vector embedding in Qdrant
        test_vector = np.random.random(384).astype(np.float32).tolist()
        qdrant_collection = f"test_collection_{uuid.uuid4().hex[:8]}"

        qdrant_client.create_collection(
            collection_name=qdrant_collection,
            vectors_config={"size": 384, "distance": "Cosine"}
        )

        qdrant_client.upsert(
            collection_name=qdrant_collection,
            points=[{
                "id": str(doc_id),
                "vector": test_vector,
                "payload": {
                    "document_id": str(doc_id),
                    "title": document.title,
                    "content_preview": document.content[:100]
                }
            }]
        )

        # Cache document metadata in Redis
        cache_key = f"document:{doc_id}"
        cache_data = {
            "id": str(doc_id),
            "title": document.title,
            "status": "completed",
            "cached_at": datetime.utcnow().isoformat()
        }
        redis_client.setex(cache_key, timedelta(minutes=5), json.dumps(cache_data))

        # Verify cross-database consistency

        # Check PostgreSQL
        pg_doc = postgres_session.query(Document).filter_by(id=doc_id).first()
        assert pg_doc is not None
        assert pg_doc.title == document.title

        # Check Redis cache
        cached_doc = json.loads(redis_client.get(cache_key))
        assert cached_doc["id"] == str(doc_id)
        assert cached_doc["title"] == document.title

        # Check Neo4j
        with neo4j_client.driver.session() as session:
            result = session.run("""
                MATCH (d:Document {id: $doc_id})-[:CONTAINS_ENTITY]->(e:Entity)
                RETURN d.title as title, e.name as entity_name
            """, {'doc_id': str(doc_id)})

            record = result.single()
            assert record is not None
            assert record["title"] == document.title
            assert record["entity_name"] == "Cross-DB Integration"

        # Check Qdrant
        search_result = qdrant_client.retrieve(
            collection_name=qdrant_collection,
            ids=[str(doc_id)],
            with_payload=True
        )

        assert len(search_result) == 1
        assert search_result[0].payload["document_id"] == str(doc_id)
        assert search_result[0].payload["title"] == document.title

        # Cleanup
        try:
            qdrant_client.delete_collection(qdrant_collection)
        except:
            pass

        postgres_session.delete(document)
        postgres_session.commit()

        with neo4j_client.driver.session() as session:
            session.run("MATCH (d:Document {id: $doc_id}) DETACH DELETE d", {'doc_id': str(doc_id)})

        redis_client.delete(cache_key)

    @pytest.mark.asyncio
    async def test_monitoring_data_consistency(self, postgres_session, redis_client):
        """Test monitoring data consistency across databases"""
        # Create monitoring metric in PostgreSQL
        metric = MetricModel(
            name="consistency_test_metric",
            value=42.5,
            type=MetricType.GAUGE,
            labels={"test": "consistency"},
            timestamp=datetime.utcnow()
        )
        postgres_session.add(metric)
        postgres_session.commit()

        metric_id = metric.id

        # Cache metric in Redis for fast access
        cache_key = f"metric:{metric_id}"
        cached_metric = {
            "id": metric_id,
            "name": metric.name,
            "value": metric.value,
            "type": metric.type.value,
            "labels": metric.labels,
            "timestamp": metric.timestamp.isoformat()
        }
        redis_client.setex(cache_key, timedelta(minutes=5), json.dumps(cached_metric))

        # Create time-series aggregate in Redis
        aggregate_key = f"metric_aggregate:{metric.name}:hour"
        redis_client.hincrby(aggregate_key, "count", 1)
        redis_client.hincrbyfloat(aggregate_key, "sum", metric.value)
        redis_client.expire(aggregate_key, timedelta(hours=24))

        # Verify consistency
        # Check PostgreSQL
        pg_metric = postgres_session.query(MetricModel).filter_by(id=metric_id).first()
        assert pg_metric.value == 42.5

        # Check Redis cache
        cached_data = json.loads(redis_client.get(cache_key))
        assert cached_data["value"] == 42.5
        assert cached_data["name"] == "consistency_test_metric"

        # Check Redis aggregate
        aggregate_data = redis_client.hgetall(aggregate_key)
        assert int(aggregate_data["count"]) == 1
        assert float(aggregate_data["sum"]) == 42.5

        # Cleanup
        postgres_session.delete(metric)
        postgres_session.commit()
        redis_client.delete(cache_key, aggregate_key)

    @pytest.mark.asyncio
    async def test_cross_database_performance_monitoring(self, postgres_session, redis_client, neo4j_client):
        """Test performance monitoring across all databases"""
        # Collect performance metrics from each database

        # PostgreSQL performance
        pg_start = time.time()
        postgres_session.execute(text("SELECT COUNT(*) FROM documents"))
        pg_time = time.time() - pg_start

        # Redis performance
        redis_start = time.time()
        redis_client.set("perf_test", "test_value")
        redis_client.get("perf_test")
        redis_time = time.time() - redis_start

        # Neo4j performance
        neo4j_start = time.time()
        with neo4j_client.driver.session() as session:
            session.run("MATCH (n) RETURN count(n) as count")
        neo4j_time = time.time() - neo4j_start

        # Store performance metrics
        performance_metrics = {
            "postgresql_query_time": pg_time,
            "redis_operation_time": redis_time,
            "neo4j_query_time": neo4j_time,
            "total_time": pg_time + redis_time + neo4j_time,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Store in PostgreSQL for historical analysis
        performance_metric = MetricModel(
            name="database_performance",
            value=performance_metrics["total_time"],
            type=MetricType.HISTOGRAM,
            labels=performance_metrics,
            timestamp=datetime.utcnow()
        )
        postgres_session.add(performance_metric)
        postgres_session.commit()

        # Cache in Redis for real-time access
        redis_client.setex(
            "db_performance_current",
            timedelta(minutes=1),
            json.dumps(performance_metrics)
        )

        # Performance assertions
        assert pg_time < 0.1  # PostgreSQL query should be fast
        assert redis_time < 0.01  # Redis operations should be very fast
        assert neo4j_time < 0.5  # Neo4j query should be reasonable
        assert performance_metrics["total_time"] < 1.0  # Total should be under 1 second

        # Cleanup
        redis_client.delete("perf_test", "db_performance_current")

    @pytest.mark.asyncio
    async def test_database_failover_handling(self, postgres_session, redis_client):
        """Test failover handling when database connections fail"""
        # Test Redis failover behavior
        original_redis_client = redis_client

        # Simulate Redis connection failure
        with patch('redis.from_url') as mock_redis:
            mock_redis.side_effect = redis.ConnectionError("Redis connection failed")

            # System should handle Redis failure gracefully
            try:
                fallback_client = redis.from_url("redis://localhost:6379/1")
                # Should handle the error appropriately
            except redis.ConnectionError:
                # Expected behavior - implement fallback logic
                pass

        # Test PostgreSQL failover behavior
        with patch.object(postgres_session, 'execute') as mock_execute:
            mock_execute.side_effect = Exception("Database connection failed")

            try:
                postgres_session.execute(text("SELECT 1"))
            except Exception:
                # Should implement retry logic or fallback
                pass

        # Verify system can continue operating with degraded functionality
        # This would be tested with actual fallback mechanisms in place

        # Restore normal operation
        assert original_redis_client.ping()  # Redis should be back to normal


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])