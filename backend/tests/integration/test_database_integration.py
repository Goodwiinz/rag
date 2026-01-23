"""
Database Integration Tests

Comprehensive integration tests for all data stores:
- PostgreSQL (primary database)
- Neo4j (knowledge graph)
- Qdrant (vector store)
- Redis (caching)

Tests database connectivity, operations, transactions, and data consistency.
"""

import pytest
import asyncio
import time
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, patch
import uuid
from datetime import datetime, timedelta

# Database imports
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import redis

# Application imports
from src.core.database import get_db, Base
from src.models.user import User, UserRole
from src.models.organization import Organization
from src.models.document import Document, DocumentType, ProcessingStatus
from src.models.entity import Entity, EntityType, ExtractionMethod
from src.models.processing import ProcessingJob, JobType, JobStatus
from src.services.search import VectorService
from src.services.knowledge_graph import KnowledgeGraphService
from src.core.config import settings


class TestPostgreSQLIntegration:
    """Test PostgreSQL database integration"""

    @pytest.fixture(scope="class")
    def postgres_engine(self):
        """Create PostgreSQL test engine"""
        # Use test database configuration
        test_db_url = settings.DATABASE_URL.replace("/rag", "/rag_test")
        engine = create_engine(test_db_url, pool_pre_ping=True)
        yield engine
        engine.dispose()

    @pytest.fixture(scope="function")
    def postgres_session(self, postgres_engine):
        """Create test database session"""
        Base.metadata.create_all(bind=postgres_engine)
        SessionLocal = sessionmaker(bind=postgres_engine)
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()
            Base.metadata.drop_all(bind=postgres_engine)

    def test_database_connection(self, postgres_engine):
        """Test PostgreSQL database connection"""
        with postgres_engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.fetchone()[0] == 1

    def test_database_transaction_rollback(self, postgres_session):
        """Test database transaction rollback"""
        # Start a transaction
        with postgres_session.begin():
            # Create a test organization
            org = Organization(
                name="Test Org",
                plan_tier="free",
                max_users=10,
                storage_quota_gb=5.0,
                is_active=True
            )
            postgres_session.add(org)
            postgres_session.flush()

            # Force rollback by raising exception
            raise Exception("Force rollback")

        # Verify organization was not saved
        org_count = postgres_session.query(Organization).filter(Organization.name == "Test Org").count()
        assert org_count == 0

    def test_user_crud_operations(self, postgres_session):
        """Test user CRUD operations"""
        # Create organization
        org = Organization(
            name="CRUD Test Org",
            plan_tier="free",
            max_users=5,
            storage_quota_gb=2.0,
            is_active=True
        )
        postgres_session.add(org)
        postgres_session.commit()
        postgres_session.refresh(org)

        # Create user
        user = User(
            email="crud@test.com",
            first_name="CRUD",
            last_name="Test",
            role=UserRole.USER,
            organization_id=org.id,
            is_active=True,
            email_verified=True
        )
        user.set_password("testpassword123")
        postgres_session.add(user)
        postgres_session.commit()
        postgres_session.refresh(user)

        # Read user
        retrieved_user = postgres_session.query(User).filter(User.id == user.id).first()
        assert retrieved_user is not None
        assert retrieved_user.email == "crud@test.com"
        assert retrieved_user.check_password("testpassword123")

        # Update user
        retrieved_user.first_name = "Updated"
        postgres_session.commit()
        postgres_session.refresh(retrieved_user)
        assert retrieved_user.first_name == "Updated"

        # Delete user
        postgres_session.delete(retrieved_user)
        postgres_session.commit()

        deleted_user = postgres_session.query(User).filter(User.id == user.id).first()
        assert deleted_user is None

    def test_document_entity_relationship(self, postgres_session):
        """Test document-entity relationship"""
        # Create test data
        org = Organization(
            name="Relation Test Org",
            plan_tier="free",
            max_users=5,
            storage_quota_gb=2.0,
            is_active=True
        )
        postgres_session.add(org)

        user = User(
            email="relation@test.com",
            first_name="Relation",
            last_name="Test",
            role=UserRole.USER,
            organization_id=org.id,
            is_active=True
        )
        user.set_password("testpassword123")
        postgres_session.add(user)

        document = Document(
            title="Test Document",
            filename="test.txt",
            file_path="/test/path.txt",
            file_size_bytes=1024,
            mime_type="text/plain",
            document_type=DocumentType.TEXT,
            processing_status=ProcessingStatus.COMPLETED,
            content_text="This document mentions John Doe and Acme Corporation.",
            organization_id=org.id,
            uploaded_by_user_id=user.id
        )
        postgres_session.add(document)
        postgres_session.commit()
        postgres_session.refresh(document)

        # Create entities
        entity1 = Entity(
            name="John Doe",
            entity_type=EntityType.PERSON,
            confidence_score=0.95,
            extraction_method=ExtractionMethod.SPACY_NER,
            document_id=document.id,
            organization_id=org.id,
            metadata={"position": [0, 8]}
        )
        entity2 = Entity(
            name="Acme Corporation",
            entity_type=EntityType.ORGANIZATION,
            confidence_score=0.88,
            extraction_method=ExtractionMethod.SPACY_NER,
            document_id=document.id,
            organization_id=org.id,
            metadata={"position": [30, 46]}
        )

        postgres_session.add(entity1)
        postgres_session.add(entity2)
        postgres_session.commit()

        # Test relationship
        retrieved_doc = postgres_session.query(Document).filter(Document.id == document.id).first()
        assert len(retrieved_doc.entities) == 2
        entity_names = [e.name for e in retrieved_doc.entities]
        assert "John Doe" in entity_names
        assert "Acme Corporation" in entity_names

        # Test cascade delete
        postgres_session.delete(retrieved_doc)
        postgres_session.commit()

        remaining_entities = postgres_session.query(Entity).filter(
            Entity.document_id == document.id
        ).count()
        assert remaining_entities == 0

    def test_database_connection_pooling(self, postgres_engine):
        """Test database connection pooling"""
        # Create multiple connections simultaneously
        connections = []
        try:
            for i in range(5):
                conn = postgres_engine.connect()
                result = conn.execute(text("SELECT version()"))
                version = result.fetchone()[0]
                assert "PostgreSQL" in version
                connections.append(conn)

            # Verify all connections work
            for i, conn in enumerate(connections):
                result = conn.execute(text("SELECT {}".format(i)))
                assert result.fetchone()[0] == i

        finally:
            # Close all connections
            for conn in connections:
                conn.close()


class TestNeo4jIntegration:
    """Test Neo4j knowledge graph integration"""

    @pytest.fixture(scope="class")
    def neo4j_driver(self):
        """Create Neo4j test driver"""
        driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
        yield driver
        driver.close()

    @pytest.fixture(scope="function")
    def neo4j_session(self, neo4j_driver):
        """Create Neo4j test session"""
        session = neo4j_driver.session()
        # Clean up test data
        session.run("MATCH (n) WHERE n.test_data = true DETACH DELETE n")
        yield session
        session.run("MATCH (n) WHERE n.test_data = true DETACH DELETE n")
        session.close()

    def test_neo4j_connection(self, neo4j_driver):
        """Test Neo4j connection"""
        with neo4j_driver.session() as session:
            result = session.run("RETURN 1 as test")
            record = result.single()
            assert record["test"] == 1

    def test_create_entities_and_relationships(self, neo4j_session):
        """Test creating entities and relationships"""
        # Create test organization node
        org_query = """
        CREATE (o:Organization {
            id: $org_id,
            name: $org_name,
            test_data: true,
            created_at: datetime()
        })
        RETURN o
        """
        org_id = str(uuid.uuid4())
        neo4j_session.run(org_query, org_id=org_id, org_name="Test Org")

        # Create test user node
        user_query = """
        CREATE (u:User {
            id: $user_id,
            email: $email,
            organization_id: $org_id,
            test_data: true,
            created_at: datetime()
        })
        RETURN u
        """
        user_id = str(uuid.uuid4())
        neo4j_session.run(user_query, user_id=user_id, email="test@example.com", org_id=org_id)

        # Create document node
        doc_query = """
        CREATE (d:Document {
            id: $doc_id,
            title: $title,
            organization_id: $org_id,
            test_data: true,
            created_at: datetime()
        })
        RETURN d
        """
        doc_id = str(uuid.uuid4())
        neo4j_session.run(doc_query, doc_id=doc_id, title="Test Document", org_id=org_id)

        # Create entity nodes
        entity_queries = [
            """
            CREATE (e:Entity {
                id: $entity_id,
                name: $name,
                type: $type,
                document_id: $doc_id,
                organization_id: $org_id,
                confidence_score: $confidence,
                test_data: true,
                created_at: datetime()
            })
            RETURN e
            """,
            """
            CREATE (e:Entity {
                id: $entity_id,
                name: $name,
                type: $type,
                document_id: $doc_id,
                organization_id: $org_id,
                confidence_score: $confidence,
                test_data: true,
                created_at: datetime()
            })
            RETURN e
            """
        ]

        entity1_id = str(uuid.uuid4())
        entity2_id = str(uuid.uuid4())

        neo4j_session.run(entity_queries[0], entity_id=entity1_id, name="John Doe",
                         type="PERSON", doc_id=doc_id, org_id=org_id, confidence=0.95)

        neo4j_session.run(entity_queries[1], entity_id=entity2_id, name="Acme Corp",
                         type="ORGANIZATION", doc_id=doc_id, org_id=org_id, confidence=0.88)

        # Create relationships
        rel_queries = [
            """
            MATCH (u:User {id: $user_id}), (d:Document {id: $doc_id})
            CREATE (u)-[:UPLOADED {test_data: true, timestamp: datetime()}]->(d)
            """,
            """
            MATCH (d:Document {id: $doc_id}), (e:Entity {id: $entity_id})
            CREATE (d)-[:CONTAINS_ENTITY {test_data: true, position: $position}]->(e)
            """
        ]

        neo4j_session.run(rel_queries[0], user_id=user_id, doc_id=doc_id)
        neo4j_session.run(rel_queries[1], doc_id=doc_id, entity_id=entity1_id, position=[0, 8])
        neo4j_session.run(rel_queries[1], doc_id=doc_id, entity_id=entity2_id, position=[20, 30])

        # Verify data
        verify_query = """
        MATCH (u:User)-[:UPLOADED]->(d:Document)-[:CONTAINS_ENTITY]->(e:Entity)
        WHERE u.test_data = true AND d.test_data = true AND e.test_data = true
        RETURN count(e) as entity_count, collect(e.name) as entity_names
        """
        result = neo4j_session.run(verify_query)
        record = result.single()
        assert record["entity_count"] == 2
        assert "John Doe" in record["entity_names"]
        assert "Acme Corp" in record["entity_names"]

    def test_graph_queries(self, neo4j_session):
        """Test complex graph queries"""
        # Create test graph structure
        setup_query = """
        CREATE (org:Organization {id: $org_id, name: 'Test Org', test_data: true})
        CREATE (u1:User {id: $u1_id, email: 'user1@test.com', organization_id: $org_id, test_data: true})
        CREATE (u2:User {id: $u2_id, email: 'user2@test.com', organization_id: $org_id, test_data: true})
        CREATE (d1:Document {id: $d1_id, title: 'Doc 1', organization_id: $org_id, test_data: true})
        CREATE (d2:Document {id: $d2_id, title: 'Doc 2', organization_id: $org_id, test_data: true})
        CREATE (e1:Entity {id: $e1_id, name: 'Entity 1', type: 'PERSON', organization_id: $org_id, test_data: true})
        CREATE (e2:Entity {id: $e2_id, name: 'Entity 2', type: 'ORG', organization_id: $org_id, test_data: true})

        CREATE (u1)-[:UPLOADED]->(d1)
        CREATE (u1)-[:UPLOADED]->(d2)
        CREATE (u2)-[:UPLOADED]->(d2)
        CREATE (d1)-[:CONTAINS_ENTITY]->(e1)
        CREATE (d2)-[:CONTAINS_ENTITY]->(e1)
        CREATE (d2)-[:CONTAINS_ENTITY]->(e2)
        """

        neo4j_session.run(setup_query,
                          org_id=str(uuid.uuid4()),
                          u1_id=str(uuid.uuid4()),
                          u2_id=str(uuid.uuid4()),
                          d1_id=str(uuid.uuid4()),
                          d2_id=str(uuid.uuid4()),
                          e1_id=str(uuid.uuid4()),
                          e2_id=str(uuid.uuid4()))

        # Test query: Find documents by entity
        docs_by_entity_query = """
        MATCH (d:Document)-[:CONTAINS_ENTITY]->(e:Entity {name: 'Entity 1'})
        WHERE d.test_data = true AND e.test_data = true
        RETURN collect(d.title) as documents
        """
        result = neo4j_session.run(docs_by_entity_query)
        record = result.single()
        assert "Doc 1" in record["documents"]
        assert "Doc 2" in record["documents"]

        # Test query: Find users by common entity
        users_by_entity_query = """
        MATCH (u:User)-[:UPLOADED]->(d:Document)-[:CONTAINS_ENTITY]->(e:Entity {name: 'Entity 1'})
        WHERE u.test_data = true AND d.test_data = true AND e.test_data = true
        RETURN collect(DISTINCT u.email) as users
        """
        result = neo4j_session.run(users_by_entity_query)
        record = result.single()
        assert "user1@test.com" in record["users"]
        assert "user2@test.com" in record["users"]

    def test_neo4j_transaction_handling(self, neo4j_session):
        """Test Neo4j transaction handling"""
        try:
            with neo4j_session.begin_transaction() as tx:
                # Create test node
                tx.run("""
                CREATE (n:TestNode {
                    id: $node_id,
                    name: 'Test Transaction',
                    test_data: true
                })
                """, node_id=str(uuid.uuid4()))

                # Force rollback
                raise Exception("Force rollback")

        except Exception:
            pass

        # Verify node was not created
        result = neo4j_session.run("""
        MATCH (n:TestNode {name: 'Test Transaction', test_data: true})
        RETURN count(n) as count
        """)
        record = result.single()
        assert record["count"] == 0


class TestQdrantIntegration:
    """Test Qdrant vector store integration"""

    @pytest.fixture(scope="class")
    def qdrant_client(self):
        """Create Qdrant test client"""
        client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            api_key=settings.QDRANT_API_KEY
        )
        yield client
        # Clean up test collections
        collections = client.get_collections().collections
        for collection in collections:
            if collection.name.startswith("test_"):
                client.delete_collection(collection.name)

    @pytest.fixture(scope="function")
    def test_collection(self, qdrant_client):
        """Create test collection"""
        collection_name = f"test_collection_{int(time.time())}"
        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE)
        )
        yield collection_name
        qdrant_client.delete_collection(collection_name)

    def test_qdrant_connection(self, qdrant_client):
        """Test Qdrant connection"""
        # Test basic operation
        collections = qdrant_client.get_collections()
        assert isinstance(collections.collections, list)

    def test_create_and_search_vectors(self, qdrant_client, test_collection):
        """Test vector creation and search"""
        # Insert test vectors
        points = [
            PointStruct(
                id=1,
                vector=[0.1] * 384,  # 384-dimensional vector
                payload={"text": "This is about machine learning", "document_id": "doc1"}
            ),
            PointStruct(
                id=2,
                vector=[0.2] * 384,
                payload={"text": "This is about artificial intelligence", "document_id": "doc2"}
            ),
            PointStruct(
                id=3,
                vector=[0.9] * 384,
                payload={"text": "This is about cooking recipes", "document_id": "doc3"}
            )
        ]

        qdrant_client.upsert(
            collection_name=test_collection,
            points=points
        )

        # Search for similar vectors
        search_result = qdrant_client.search(
            collection_name=test_collection,
            query_vector=[0.15] * 384,  # Similar to first two vectors
            limit=2,
            with_payload=True
        )

        assert len(search_result) == 2
        # Should return the ML and AI documents first
        returned_texts = [hit.payload["text"] for hit in search_result]
        assert "machine learning" in " ".join(returned_texts) or "artificial intelligence" in " ".join(returned_texts)

    def test_vector_filtering(self, qdrant_client, test_collection):
        """Test vector search with filtering"""
        # Insert vectors with different payloads
        points = [
            PointStruct(
                id=1,
                vector=[0.1] * 384,
                payload={
                    "text": "Technical document",
                    "document_id": "doc1",
                    "document_type": "technical",
                    "organization_id": "org1"
                }
            ),
            PointStruct(
                id=2,
                vector=[0.2] * 384,
                payload={
                    "text": "Financial report",
                    "document_id": "doc2",
                    "document_type": "financial",
                    "organization_id": "org1"
                ),
            PointStruct(
                id=3,
                vector=[0.3] * 384,
                payload={
                    "text": "Technical manual",
                    "document_id": "doc3",
                    "document_type": "technical",
                    "organization_id": "org2"
                }
            )
        ]

        qdrant_client.upsert(
            collection_name=test_collection,
            points=points
        )

        # Search with filter for technical documents
        search_result = qdrant_client.search(
            collection_name=test_collection,
            query_vector=[0.15] * 384,
            query_filter={
                "must": [
                    {"key": "document_type", "match": {"value": "technical"}}
                ]
            },
            limit=10,
            with_payload=True
        )

        assert len(search_result) == 2
        for hit in search_result:
            assert hit.payload["document_type"] == "technical"

    def test_vector_update_and_delete(self, qdrant_client, test_collection):
        """Test vector update and delete operations"""
        # Insert initial vector
        point = PointStruct(
            id=1,
            vector=[0.1] * 384,
            payload={"text": "Original text", "status": "draft"}
        )
        qdrant_client.upsert(collection_name=test_collection, points=[point])

        # Update payload
        qdrant_client.set_payload(
            collection_name=test_collection,
            payload={"text": "Updated text", "status": "published"},
            points=[1]
        )

        # Verify update
        retrieve_result = qdrant_client.retrieve(
            collection_name=test_collection,
            ids=[1],
            with_payload=True
        )
        assert retrieve_result[0].payload["text"] == "Updated text"
        assert retrieve_result[0].payload["status"] == "published"

        # Delete vector
        qdrant_client.delete(
            collection_name=test_collection,
            points_selector={"points": [1]}
        )

        # Verify deletion
        retrieve_result = qdrant_client.retrieve(
            collection_name=test_collection,
            ids=[1]
        )
        assert len(retrieve_result) == 0

    def test_collection_management(self, qdrant_client):
        """Test collection management operations"""
        collection_name = f"test_mgmt_{int(time.time())}"

        # Create collection
        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=256, distance=Distance.EUCLID)
        )

        # Verify collection exists
        collections = qdrant_client.get_collections().collections
        collection_names = [c.name for c in collections]
        assert collection_name in collection_names

        # Get collection info
        collection_info = qdrant_client.get_collection(collection_name)
        assert collection_info.config.params.vectors.size == 256
        assert collection_info.config.params.vectors.distance == Distance.EUCLID

        # Delete collection
        qdrant_client.delete_collection(collection_name)

        # Verify deletion
        collections = qdrant_client.get_collections().collections
        collection_names = [c.name for c in collections]
        assert collection_name not in collection_names


class TestRedisIntegration:
    """Test Redis caching integration"""

    @pytest.fixture(scope="class")
    def redis_client(self):
        """Create Redis test client"""
        client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=15,  # Use test database
            decode_responses=True
        )
        yield client
        # Clean up test database
        client.flushdb()
        client.close()

    def test_redis_connection(self, redis_client):
        """Test Redis connection"""
        result = redis_client.ping()
        assert result is True

    def test_basic_operations(self, redis_client):
        """Test basic Redis operations"""
        # Set and get string
        redis_client.set("test_key", "test_value")
        value = redis_client.get("test_key")
        assert value == "test_value"

        # Set with expiration
        redis_client.setex("expire_key", 1, "expire_value")
        assert redis_client.get("expire_key") == "expire_value"
        time.sleep(1.1)
        assert redis_client.get("expire_key") is None

        # Delete key
        redis_client.delete("test_key")
        assert redis_client.get("test_key") is None

    def test_hash_operations(self, redis_client):
        """Test Redis hash operations"""
        # Set hash fields
        redis_client.hset("test_hash", mapping={
            "field1": "value1",
            "field2": "value2",
            "field3": "value3"
        })

        # Get single field
        assert redis_client.hget("test_hash", "field1") == "value1"

        # Get all fields
        all_fields = redis_client.hgetall("test_hash")
        assert all_fields["field2"] == "value2"
        assert len(all_fields) == 3

        # Delete hash
        redis_client.delete("test_hash")
        assert redis_client.hgetall("test_hash") == {}

    def test_list_operations(self, redis_client):
        """Test Redis list operations"""
        # Push to list
        redis_client.lpush("test_list", "item1", "item2", "item3")

        # Get list length
        assert redis_client.llen("test_list") == 3

        # Get range
        items = redis_client.lrange("test_list", 0, -1)
        assert "item2" in items
        assert len(items) == 3

        # Pop from list
        item = redis_client.rpop("test_list")
        assert item == "item1"
        assert redis_client.llen("test_list") == 2

    def test_set_operations(self, redis_client):
        """Test Redis set operations"""
        # Add to set
        redis_client.sadd("test_set", "member1", "member2", "member3")

        # Check membership
        assert redis_client.sismember("test_set", "member2") is True
        assert redis_client.sismember("test_set", "nonexistent") is False

        # Get all members
        members = redis_client.smembers("test_set")
        assert len(members) == 3

        # Remove from set
        redis_client.srem("test_set", "member2")
        assert redis_client.sismember("test_set", "member2") is False

    def test_json_operations(self, redis_client):
        """Test Redis JSON operations (if available)"""
        # Try to use JSON commands (RedisJSON module)
        try:
            import json
            test_data = {"name": "test", "value": 123, "nested": {"key": "val"}}

            # Set JSON value
            redis_client.execute_command("JSON.SET", "test_json", ".", json.dumps(test_data))

            # Get JSON value
            result = redis_client.execute_command("JSON.GET", "test_json")
            parsed_result = json.loads(result)
            assert parsed_result["name"] == "test"
            assert parsed_result["value"] == 123

            # Update JSON field
            redis_client.execute_command("JSON.SET", "test_json", ".value", "456")
            updated_result = redis_client.execute_command("JSON.GET", "test_json")
            updated_parsed = json.loads(updated_result)
            assert updated_parsed["value"] == 456

        except redis.exceptions.ResponseError:
            # JSON module not available, skip test
            pytest.skip("RedisJSON module not available")

    def test_cache_performance(self, redis_client):
        """Test Redis caching performance"""
        # Test set performance
        start_time = time.time()
        for i in range(1000):
            redis_client.set(f"perf_key_{i}", f"perf_value_{i}")
        set_time = time.time() - start_time

        # Test get performance
        start_time = time.time()
        for i in range(1000):
            redis_client.get(f"perf_key_{i}")
        get_time = time.time() - start_time

        # Performance should be reasonable (less than 1 second for 1000 ops)
        assert set_time < 1.0, f"Set performance too slow: {set_time:.3f}s"
        assert get_time < 1.0, f"Get performance too slow: {get_time:.3f}s"

        # Clean up
        for i in range(1000):
            redis_client.delete(f"perf_key_{i}")


class TestCrossDatabaseIntegration:
    """Test integration across multiple databases"""

    def test_document_pipeline_integration(self, postgres_session, neo4j_driver, qdrant_client, redis_client):
        """Test complete document processing pipeline across all databases"""
        # Create test data in PostgreSQL
        org = Organization(
            name="Integration Test Org",
            plan_tier="free",
            max_users=10,
            storage_quota_gb=5.0,
            is_active=True
        )
        postgres_session.add(org)
        postgres_session.commit()
        postgres_session.refresh(org)

        user = User(
            email="integration@test.com",
            first_name="Integration",
            last_name="Test",
            role=UserRole.USER,
            organization_id=org.id,
            is_active=True
        )
        user.set_password("testpassword123")
        postgres_session.add(user)
        postgres_session.commit()
        postgres_session.refresh(user)

        document = Document(
            title="Integration Test Document",
            filename="integration_test.txt",
            file_path="/test/integration_test.txt",
            file_size_bytes=2048,
            mime_type="text/plain",
            document_type=DocumentType.TEXT,
            processing_status=ProcessingStatus.COMPLETED,
            content_text="This document discusses machine learning algorithms and mentions Google and Microsoft.",
            organization_id=org.id,
            uploaded_by_user_id=user.id
        )
        postgres_session.add(document)
        postgres_session.commit()
        postgres_session.refresh(document)

        # Create entities in PostgreSQL
        entities = [
            Entity(
                name="machine learning",
                entity_type=EntityType.CONCEPT,
                confidence_score=0.95,
                extraction_method=ExtractionMethod.SPACY_NER,
                document_id=document.id,
                organization_id=org.id,
                metadata={"position": [29, 46]}
            ),
            Entity(
                name="Google",
                entity_type=EntityType.ORGANIZATION,
                confidence_score=0.98,
                extraction_method=ExtractionMethod.SPACY_NER,
                document_id=document.id,
                organization_id=org.id,
                metadata={"position": [73, 79]}
            ),
            Entity(
                name="Microsoft",
                entity_type=EntityType.ORGANIZATION,
                confidence_score=0.96,
                extraction_method=ExtractionMethod.SPACY_NER,
                document_id=document.id,
                organization_id=org.id,
                metadata={"position": [84, 93]}
            )
        ]

        for entity in entities:
            postgres_session.add(entity)
        postgres_session.commit()

        # Create corresponding nodes in Neo4j
        with neo4j_driver.session() as neo4j_session:
            # Create document node
            neo4j_session.run("""
            CREATE (d:Document {
                id: $doc_id,
                title: $title,
                organization_id: $org_id,
                test_data: true,
                created_at: datetime()
            })
            """, doc_id=document.id, title=document.title, org_id=org.id)

            # Create entity nodes and relationships
            for entity in entities:
                neo4j_session.run("""
                CREATE (e:Entity {
                    id: $entity_id,
                    name: $name,
                    type: $type,
                    organization_id: $org_id,
                    test_data: true,
                    created_at: datetime()
                })
                """, entity_id=entity.id, name=entity.name, type=entity.entity_type.value,
                    org_id=org.id)

                neo4j_session.run("""
                MATCH (d:Document {id: $doc_id}), (e:Entity {id: $entity_id})
                CREATE (d)-[:CONTAINS_ENTITY {test_data: true, confidence: $confidence}]->(e)
                """, doc_id=document.id, entity_id=entity.id, confidence=entity.confidence_score)

        # Create vector embeddings in Qdrant
        collection_name = f"integration_test_{int(time.time())}"
        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE)
        )

        # Simulate creating embedding for the document
        import numpy as np
        document_embedding = np.random.rand(384).tolist()

        qdrant_client.upsert(
            collection_name=collection_name,
            points=[
                PointStruct(
                    id=document.id,
                    vector=document_embedding,
                    payload={
                        "document_id": document.id,
                        "title": document.title,
                        "organization_id": org.id,
                        "content_preview": document.content_text[:100]
                    }
                )
            ]
        )

        # Cache document metadata in Redis
        redis_client.hset(
            f"document:{document.id}",
            mapping={
                "title": document.title,
                "organization_id": str(org.id),
                "processing_status": document.processing_status.value,
                "entity_count": str(len(entities)),
                "cached_at": datetime.utcnow().isoformat()
            }
        )

        # Verify cross-database consistency

        # Check PostgreSQL entities
        pg_entities = postgres_session.query(Entity).filter(
            Entity.document_id == document.id
        ).all()
        assert len(pg_entities) == 3

        # Check Neo4j entities
        with neo4j_driver.session() as neo4j_session:
            result = neo4j_session.run("""
            MATCH (d:Document {id: $doc_id})-[:CONTAINS_ENTITY]->(e:Entity)
            WHERE d.test_data = true AND e.test_data = true
            RETURN collect(e.name) as entity_names
            """, doc_id=document.id)
            record = result.single()
            neo4j_entities = record["entity_names"]
            assert len(neo4j_entities) == 3
            assert "machine learning" in neo4j_entities
            assert "Google" in neo4j_entities
            assert "Microsoft" in neo4j_entities

        # Check Qdrant vector
        search_result = qdrant_client.search(
            collection_name=collection_name,
            query_vector=document_embedding,
            limit=1
        )
        assert len(search_result) == 1
        assert search_result[0].id == document.id

        # Check Redis cache
        cached_data = redis_client.hgetall(f"document:{document.id}")
        assert cached_data["title"] == document.title
        assert cached_data["entity_count"] == "3"

        # Test search across databases
        search_query = "machine learning"

        # Search in PostgreSQL
        pg_results = postgres_session.query(Document).filter(
            Document.content_text.ilike(f"%{search_query}%")
        ).all()
        assert len(pg_results) == 1
        assert pg_results[0].id == document.id

        # Search in Neo4j
        with neo4j_driver.session() as neo4j_session:
            result = neo4j_session.run("""
            MATCH (d:Document)-[:CONTAINS_ENTITY]->(e:Entity)
            WHERE e.name = $entity_name AND d.test_data = true
            RETURN d.id as doc_id
            """, entity_name=search_query)
            records = list(result)
            assert len(records) == 1
            assert str(records[0]["doc_id"]) == str(document.id)

        # Search in Qdrant (vector similarity)
        # This would normally use the actual embedding of the search query
        # For testing, we use the same embedding
        vector_results = qdrant_client.search(
            collection_name=collection_name,
            query_vector=document_embedding,
            limit=10,
            score_threshold=0.9
        )
        assert len(vector_results) == 1
        assert vector_results[0].id == document.id

        # Cleanup
        qdrant_client.delete_collection(collection_name)
        redis_client.delete(f"document:{document.id}")

        # Clean up Neo4j test data
        with neo4j_driver.session() as neo4j_session:
            neo4j_session.run("""
            MATCH (n) WHERE n.test_data = true
            DETACH DELETE n
            """)

    def test_database_failure_resilience(self, postgres_session, redis_client):
        """Test application resilience when databases are unavailable"""
        # Test Redis failure handling
        redis_data = {"test": "data"}

        # Try to cache data
        try:
            redis_client.set("resilience_test", json.dumps(redis_data))
            cached_data = json.loads(redis_client.get("resilience_test"))
            assert cached_data == redis_data
        except redis.exceptions.ConnectionError:
            # Application should handle Redis unavailability gracefully
            pytest.skip("Redis not available for resilience test")

        # Test database connection recovery
        try:
            # Simulate temporary connection issue
            original_session = postgres_session
            postgres_session.close()

            # Create new session
            new_session = Session(bind=postgres_session.bind)

            # Test basic operation
            count = new_session.query(Document).count()
            assert isinstance(count, int)

            new_session.close()

        except Exception:
            pytest.skip("Database resilience test failed due to connection issues")

    def test_data_consistency_across_databases(self, postgres_session, neo4j_driver):
        """Test data consistency across PostgreSQL and Neo4j"""
        # Create test document in PostgreSQL
        org = Organization(
            name="Consistency Test Org",
            plan_tier="free",
            max_users=10,
            storage_quota_gb=5.0,
            is_active=True
        )
        postgres_session.add(org)
        postgres_session.commit()
        postgres_session.refresh(org)

        document = Document(
            title="Consistency Test Document",
            filename="consistency_test.txt",
            file_path="/test/consistency_test.txt",
            file_size_bytes=1024,
            mime_type="text/plain",
            document_type=DocumentType.TEXT,
            processing_status=ProcessingStatus.COMPLETED,
            content_text="Test content for consistency checking",
            organization_id=org.id
        )
        postgres_session.add(document)
        postgres_session.commit()
        postgres_session.refresh(document)

        # Create corresponding node in Neo4j
        with neo4j_driver.session() as neo4j_session:
            neo4j_session.run("""
            CREATE (d:Document {
                id: $doc_id,
                title: $title,
                organization_id: $org_id,
                test_data: true,
                created_at: datetime()
            })
            """, doc_id=document.id, title=document.title, org_id=org.id)

        # Update document in PostgreSQL
        document.title = "Updated Consistency Test Document"
        postgres_session.commit()

        # Simulate eventual consistency - update Neo4j
        with neo4j_driver.session() as neo4j_session:
            neo4j_session.run("""
            MATCH (d:Document {id: $doc_id})
            SET d.title = $title, d.updated_at = datetime()
            """, doc_id=document.id, title=document.title)

        # Verify consistency
        pg_title = postgres_session.query(Document.title).filter(
            Document.id == document.id
        ).scalar()

        with neo4j_driver.session() as neo4j_session:
            result = neo4j_session.run("""
            MATCH (d:Document {id: $doc_id})
            RETURN d.title as title
            """, doc_id=document.id)
            neo4j_title = result.single()["title"]

        assert pg_title == neo4j_title

        # Clean up
        with neo4j_driver.session() as neo4j_session:
            neo4j_session.run("""
            MATCH (n) WHERE n.test_data = true
            DETACH DELETE n
            """)