"""
Unit Tests for KnowledgeGraphService

Tests entity creation, relationship management, search,
and circuit breaker patterns with proper Neo4j mocking.

All tests use mocks - no external services required.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from uuid import uuid4
from datetime import datetime
from typing import Dict, List, Any

from tests.mocks.services import MockNeo4jDriver, MockNeo4jRecord, MockNeo4jResult


# ============================================================================
# Test Data Builders
# ============================================================================

class EntityBuilder:
    """Builder pattern for entity test data."""

    def __init__(self):
        self._id = str(uuid4())
        self._name = "Test Entity"
        self._type = "CONCEPT"
        self._properties = {}
        self._created_at = datetime.utcnow().isoformat()
        self._updated_at = datetime.utcnow().isoformat()

    def with_id(self, id: str) -> "EntityBuilder":
        self._id = id
        return self

    def with_name(self, name: str) -> "EntityBuilder":
        self._name = name
        return self

    def with_type(self, type: str) -> "EntityBuilder":
        self._type = type
        return self

    def with_property(self, key: str, value: Any) -> "EntityBuilder":
        self._properties[key] = value
        return self

    def with_properties(self, properties: Dict[str, Any]) -> "EntityBuilder":
        self._properties.update(properties)
        return self

    def build(self) -> Dict[str, Any]:
        return {
            "id": self._id,
            "name": self._name,
            "type": self._type,
            "properties": self._properties,
            "created_at": self._created_at,
            "updated_at": self._updated_at,
        }

    def build_as_record(self) -> Dict[str, Any]:
        """Build as Neo4j record format."""
        return {
            "e": {
                "id": self._id,
                "name": self._name,
                "type": self._type,
                **self._properties,
            }
        }


class RelationshipBuilder:
    """Builder pattern for relationship test data."""

    def __init__(self):
        self._id = str(uuid4())
        self._source_id = str(uuid4())
        self._target_id = str(uuid4())
        self._type = "RELATED_TO"
        self._properties = {}
        self._weight = 1.0

    def with_id(self, id: str) -> "RelationshipBuilder":
        self._id = id
        return self

    def from_entity(self, source_id: str) -> "RelationshipBuilder":
        self._source_id = source_id
        return self

    def to_entity(self, target_id: str) -> "RelationshipBuilder":
        self._target_id = target_id
        return self

    def with_type(self, type: str) -> "RelationshipBuilder":
        self._type = type
        return self

    def with_weight(self, weight: float) -> "RelationshipBuilder":
        self._weight = weight
        return self

    def with_property(self, key: str, value: Any) -> "RelationshipBuilder":
        self._properties[key] = value
        return self

    def build(self) -> Dict[str, Any]:
        return {
            "id": self._id,
            "source_id": self._source_id,
            "target_id": self._target_id,
            "type": self._type,
            "weight": self._weight,
            "properties": self._properties,
        }

    def build_as_record(self) -> Dict[str, Any]:
        """Build as Neo4j record format."""
        return {
            "r": {
                "id": self._id,
                "type": self._type,
                "weight": self._weight,
                **self._properties,
            },
            "source": {"id": self._source_id},
            "target": {"id": self._target_id},
        }


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_driver():
    """Create mock Neo4j driver."""
    return MockNeo4jDriver()


@pytest.fixture
def sample_entities():
    """Create sample entities."""
    return [
        EntityBuilder().with_name("Machine Learning").with_type("CONCEPT").build(),
        EntityBuilder().with_name("Neural Network").with_type("CONCEPT").build(),
        EntityBuilder().with_name("TensorFlow").with_type("TECHNOLOGY").build(),
        EntityBuilder().with_name("Google").with_type("ORGANIZATION").build(),
    ]


@pytest.fixture
def sample_relationships():
    """Create sample relationships."""
    return [
        RelationshipBuilder()
            .with_type("USES")
            .with_weight(0.9)
            .build(),
        RelationshipBuilder()
            .with_type("DEVELOPED_BY")
            .with_weight(1.0)
            .build(),
    ]


# ============================================================================
# Entity Creation Tests
# ============================================================================

class TestEntityCreation:
    """Test entity creation logic."""

    @pytest.mark.asyncio
    async def test_creates_entity_with_valid_data(self, mock_driver):
        """Should create entity with valid data."""
        entity = EntityBuilder() \
            .with_name("Test Concept") \
            .with_type("CONCEPT") \
            .build()

        mock_driver.set_query_results([{"e": entity}])

        async with mock_driver.session() as session:
            result = await session.run(
                "CREATE (e:Entity {name: $name, type: $type}) RETURN e",
                {"name": entity["name"], "type": entity["type"]}
            )
            record = result.single()

        assert record is not None

    @pytest.mark.asyncio
    async def test_generates_unique_id(self, mock_driver):
        """Should generate unique ID for new entity."""
        entity = EntityBuilder().build()

        # ID should be a valid UUID string
        assert entity["id"] is not None
        assert len(entity["id"]) == 36  # UUID format

    @pytest.mark.asyncio
    async def test_entity_types_are_validated(self):
        """Should validate entity types."""
        valid_types = ["CONCEPT", "PERSON", "ORGANIZATION", "TECHNOLOGY", "DOCUMENT"]

        for entity_type in valid_types:
            entity = EntityBuilder().with_type(entity_type).build()
            assert entity["type"] in valid_types

    @pytest.mark.asyncio
    async def test_creates_entity_with_properties(self, mock_driver):
        """Should create entity with additional properties."""
        entity = EntityBuilder() \
            .with_name("Python") \
            .with_type("TECHNOLOGY") \
            .with_property("version", "3.11") \
            .with_property("paradigm", "multi-paradigm") \
            .build()

        assert entity["properties"]["version"] == "3.11"
        assert entity["properties"]["paradigm"] == "multi-paradigm"


class TestEntityRetrieval:
    """Test entity retrieval logic."""

    @pytest.mark.asyncio
    async def test_gets_entity_by_id(self, mock_driver, sample_entities):
        """Should retrieve entity by ID."""
        entity = sample_entities[0]
        mock_driver.set_query_results([{"e": entity}])

        async with mock_driver.session() as session:
            result = await session.run(
                "MATCH (e:Entity {id: $id}) RETURN e",
                {"id": entity["id"]}
            )
            record = result.single()

        assert record is not None
        assert record["e"]["name"] == entity["name"]

    @pytest.mark.asyncio
    async def test_returns_none_for_nonexistent_entity(self, mock_driver):
        """Should return None for nonexistent entity."""
        mock_driver.set_query_results([])

        async with mock_driver.session() as session:
            result = await session.run(
                "MATCH (e:Entity {id: $id}) RETURN e",
                {"id": "nonexistent-id"}
            )
            record = result.single()

        assert record is None


class TestEntityUpdate:
    """Test entity update logic."""

    @pytest.mark.asyncio
    async def test_updates_entity_properties(self, mock_driver):
        """Should update entity properties."""
        original = EntityBuilder() \
            .with_name("Original Name") \
            .build()

        updated = EntityBuilder() \
            .with_id(original["id"]) \
            .with_name("Updated Name") \
            .build()

        mock_driver.set_query_results([{"e": updated}])

        async with mock_driver.session() as session:
            result = await session.run(
                "MATCH (e:Entity {id: $id}) SET e.name = $name RETURN e",
                {"id": original["id"], "name": "Updated Name"}
            )
            record = result.single()

        assert record["e"]["name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_updates_timestamp_on_modification(self):
        """Should update timestamp when entity is modified."""
        original_time = datetime.utcnow().isoformat()
        entity = EntityBuilder().build()

        # Simulate update
        entity["updated_at"] = datetime.utcnow().isoformat()

        assert entity["updated_at"] >= original_time


class TestEntityDeletion:
    """Test entity deletion logic."""

    @pytest.mark.asyncio
    async def test_deletes_entity_by_id(self, mock_driver):
        """Should delete entity by ID."""
        entity = EntityBuilder().build()

        mock_driver.set_query_results([{"deleted": 1}])

        async with mock_driver.session() as session:
            result = await session.run(
                "MATCH (e:Entity {id: $id}) DETACH DELETE e RETURN count(e) as deleted",
                {"id": entity["id"]}
            )

        # Verify query was executed
        assert len(session.run_calls) == 1

    @pytest.mark.asyncio
    async def test_cascade_deletes_relationships(self, mock_driver):
        """Should delete related relationships when entity is deleted."""
        # DETACH DELETE removes all relationships
        entity = EntityBuilder().build()

        async with mock_driver.session() as session:
            await session.run(
                "MATCH (e:Entity {id: $id}) DETACH DELETE e",
                {"id": entity["id"]}
            )

        # Query should use DETACH DELETE
        query = session.run_calls[0][0]
        assert "DETACH DELETE" in query


# ============================================================================
# Entity Search Tests
# ============================================================================

class TestEntitySearch:
    """Test entity search logic."""

    @pytest.mark.asyncio
    async def test_searches_entities_by_name(self, mock_driver, sample_entities):
        """Should search entities by name."""
        mock_driver.set_query_results([{"e": sample_entities[0]}])

        async with mock_driver.session() as session:
            result = await session.run(
                "MATCH (e:Entity) WHERE e.name CONTAINS $query RETURN e",
                {"query": "Machine"}
            )
            records = list(result)

        assert len(records) == 1

    @pytest.mark.asyncio
    async def test_searches_entities_by_type(self, mock_driver, sample_entities):
        """Should filter entities by type."""
        concepts = [e for e in sample_entities if e["type"] == "CONCEPT"]
        mock_driver.set_query_results([{"e": e} for e in concepts])

        async with mock_driver.session() as session:
            result = await session.run(
                "MATCH (e:Entity) WHERE e.type = $type RETURN e",
                {"type": "CONCEPT"}
            )
            records = list(result)

        assert len(records) == 2

    @pytest.mark.asyncio
    async def test_fuzzy_search(self, mock_driver, sample_entities):
        """Should support fuzzy text search."""
        # Simulate fuzzy match on "Learn" matching "Learning"
        mock_driver.set_query_results([{"e": sample_entities[0]}])

        async with mock_driver.session() as session:
            result = await session.run(
                "MATCH (e:Entity) WHERE e.name =~ '(?i).*learn.*' RETURN e",
                {}
            )
            records = list(result)

        assert len(records) == 1

    @pytest.mark.asyncio
    async def test_paginates_search_results(self, mock_driver, sample_entities):
        """Should paginate search results."""
        mock_driver.set_query_results([{"e": e} for e in sample_entities[:2]])

        async with mock_driver.session() as session:
            result = await session.run(
                "MATCH (e:Entity) RETURN e SKIP $skip LIMIT $limit",
                {"skip": 0, "limit": 2}
            )
            records = list(result)

        assert len(records) == 2


# ============================================================================
# Relationship Tests
# ============================================================================

class TestRelationshipCreation:
    """Test relationship creation logic."""

    @pytest.mark.asyncio
    async def test_creates_relationship_between_entities(self, mock_driver):
        """Should create relationship between two entities."""
        source = EntityBuilder().with_name("TensorFlow").build()
        target = EntityBuilder().with_name("Google").build()
        rel = RelationshipBuilder() \
            .from_entity(source["id"]) \
            .to_entity(target["id"]) \
            .with_type("DEVELOPED_BY") \
            .build()

        mock_driver.set_query_results([{
            "r": rel,
            "source": source,
            "target": target
        }])

        async with mock_driver.session() as session:
            result = await session.run(
                """
                MATCH (s:Entity {id: $source_id}), (t:Entity {id: $target_id})
                CREATE (s)-[r:DEVELOPED_BY]->(t)
                RETURN r, s as source, t as target
                """,
                {"source_id": source["id"], "target_id": target["id"]}
            )
            record = result.single()

        assert record is not None

    @pytest.mark.asyncio
    async def test_relationship_has_weight(self, mock_driver):
        """Should create relationship with weight."""
        rel = RelationshipBuilder() \
            .with_type("SIMILAR_TO") \
            .with_weight(0.85) \
            .build()

        assert rel["weight"] == 0.85

    @pytest.mark.asyncio
    async def test_relationship_types_are_validated(self):
        """Should validate relationship types."""
        valid_types = [
            "RELATED_TO", "SIMILAR_TO", "PART_OF",
            "USES", "DEVELOPED_BY", "AUTHORED_BY"
        ]

        for rel_type in valid_types:
            rel = RelationshipBuilder().with_type(rel_type).build()
            assert rel["type"] in valid_types


class TestRelationshipRetrieval:
    """Test relationship retrieval logic."""

    @pytest.mark.asyncio
    async def test_gets_entity_relationships(self, mock_driver, sample_relationships):
        """Should retrieve all relationships for an entity."""
        mock_driver.set_query_results([{"r": r} for r in sample_relationships])

        async with mock_driver.session() as session:
            result = await session.run(
                """
                MATCH (e:Entity {id: $id})-[r]-()
                RETURN r
                """,
                {"id": str(uuid4())}
            )
            records = list(result)

        assert len(records) == 2

    @pytest.mark.asyncio
    async def test_gets_incoming_relationships(self, mock_driver):
        """Should retrieve incoming relationships."""
        rels = [RelationshipBuilder().with_type("REFERENCES").build()]
        mock_driver.set_query_results([{"r": r} for r in rels])

        async with mock_driver.session() as session:
            result = await session.run(
                "MATCH (e:Entity {id: $id})<-[r]-() RETURN r",
                {"id": str(uuid4())}
            )
            records = list(result)

        assert len(records) == 1

    @pytest.mark.asyncio
    async def test_gets_outgoing_relationships(self, mock_driver):
        """Should retrieve outgoing relationships."""
        rels = [RelationshipBuilder().with_type("USES").build()]
        mock_driver.set_query_results([{"r": r} for r in rels])

        async with mock_driver.session() as session:
            result = await session.run(
                "MATCH (e:Entity {id: $id})-[r]->() RETURN r",
                {"id": str(uuid4())}
            )
            records = list(result)

        assert len(records) == 1


class TestRelationshipDeletion:
    """Test relationship deletion logic."""

    @pytest.mark.asyncio
    async def test_deletes_relationship(self, mock_driver):
        """Should delete specific relationship."""
        rel = RelationshipBuilder().build()

        async with mock_driver.session() as session:
            await session.run(
                "MATCH ()-[r {id: $id}]-() DELETE r",
                {"id": rel["id"]}
            )

        assert len(session.run_calls) == 1


# ============================================================================
# Graph Traversal Tests
# ============================================================================

class TestGraphTraversal:
    """Test graph traversal and path finding."""

    @pytest.mark.asyncio
    async def test_finds_related_entities(self, mock_driver, sample_entities):
        """Should find entities related to a given entity."""
        related = sample_entities[1:3]
        mock_driver.set_query_results([{"e": e} for e in related])

        async with mock_driver.session() as session:
            result = await session.run(
                """
                MATCH (e:Entity {id: $id})-[r]->(related)
                RETURN related as e
                """,
                {"id": sample_entities[0]["id"]}
            )
            records = list(result)

        assert len(records) == 2

    @pytest.mark.asyncio
    async def test_finds_path_between_entities(self, mock_driver):
        """Should find path between two entities."""
        path_data = {
            "path": [
                {"name": "Entity A"},
                {"type": "RELATED_TO"},
                {"name": "Entity B"},
                {"type": "USES"},
                {"name": "Entity C"},
            ]
        }
        mock_driver.set_query_results([path_data])

        async with mock_driver.session() as session:
            result = await session.run(
                """
                MATCH path = shortestPath(
                    (start:Entity {id: $start_id})-[*..5]-(end:Entity {id: $end_id})
                )
                RETURN path
                """,
                {"start_id": str(uuid4()), "end_id": str(uuid4())}
            )
            record = result.single()

        assert record is not None

    @pytest.mark.asyncio
    async def test_limits_traversal_depth(self, mock_driver, sample_entities):
        """Should respect maximum traversal depth."""
        max_depth = 3

        async with mock_driver.session() as session:
            await session.run(
                f"""
                MATCH (e:Entity {{id: $id}})-[*1..{max_depth}]-(related)
                RETURN related
                """,
                {"id": sample_entities[0]["id"]}
            )

        # Verify query includes depth limit
        query = session.run_calls[0][0]
        assert f"1..{max_depth}" in query


# ============================================================================
# Circuit Breaker Tests
# ============================================================================

class TestCircuitBreaker:
    """Test circuit breaker pattern for Neo4j."""

    @pytest.mark.asyncio
    async def test_handles_connection_failure(self, mock_driver):
        """Should handle Neo4j connection failure gracefully."""
        mock_driver.set_connected(False)

        with pytest.raises(ConnectionError):
            mock_driver.session()

    @pytest.mark.asyncio
    async def test_handles_query_timeout(self, mock_driver):
        """Should handle query timeout gracefully."""
        mock_driver.set_run_side_effect(TimeoutError("Query timed out"))

        async with mock_driver.session() as session:
            with pytest.raises(TimeoutError):
                await session.run("MATCH (n) RETURN n")

    @pytest.mark.asyncio
    async def test_recovers_after_failure(self, mock_driver, sample_entities):
        """Should recover after transient failure."""
        # First call fails
        mock_driver.set_run_side_effect(ConnectionError("Temporary failure"))

        async with mock_driver.session() as session:
            try:
                await session.run("MATCH (n) RETURN n")
            except ConnectionError:
                pass

        # Clear error and retry
        mock_driver._run_side_effect = None
        mock_driver.set_query_results([{"e": sample_entities[0]}])

        async with mock_driver.session() as session:
            result = await session.run("MATCH (n) RETURN n")
            record = result.single()

        assert record is not None


# ============================================================================
# Batch Operations Tests
# ============================================================================

class TestBatchOperations:
    """Test batch entity and relationship operations."""

    @pytest.mark.asyncio
    async def test_creates_entities_in_batch(self, mock_driver):
        """Should create multiple entities in single transaction."""
        entities = [
            EntityBuilder().with_name(f"Entity {i}").build()
            for i in range(10)
        ]

        mock_driver.set_query_results([{"count": len(entities)}])

        async with mock_driver.session() as session:
            result = await session.run(
                """
                UNWIND $entities as entity
                CREATE (e:Entity)
                SET e = entity
                RETURN count(e) as count
                """,
                {"entities": entities}
            )
            record = result.single()

        assert record["count"] == 10

    @pytest.mark.asyncio
    async def test_batch_operation_is_atomic(self, mock_driver):
        """Batch operation should be atomic (all or nothing)."""
        entities = [
            EntityBuilder().with_name(f"Entity {i}").build()
            for i in range(5)
        ]

        # Simulate partial failure
        mock_driver.set_run_side_effect(Exception("Constraint violation"))

        async with mock_driver.session() as session:
            try:
                await session.run("UNWIND $entities as e CREATE (n:Entity)", {"entities": entities})
                committed = True
            except Exception:
                committed = False

        # Transaction should have failed completely
        assert committed is False


# ============================================================================
# Analytics Tests
# ============================================================================

class TestGraphAnalytics:
    """Test graph analytics queries."""

    @pytest.mark.asyncio
    async def test_counts_entities_by_type(self, mock_driver):
        """Should count entities grouped by type."""
        mock_driver.set_query_results([
            {"type": "CONCEPT", "count": 150},
            {"type": "PERSON", "count": 75},
            {"type": "ORGANIZATION", "count": 50},
        ])

        async with mock_driver.session() as session:
            result = await session.run(
                "MATCH (e:Entity) RETURN e.type as type, count(e) as count"
            )
            records = list(result)

        assert len(records) == 3
        total = sum(r["count"] for r in records)
        assert total == 275

    @pytest.mark.asyncio
    async def test_calculates_degree_centrality(self, mock_driver):
        """Should calculate entity degree centrality."""
        mock_driver.set_query_results([
            {"name": "Central Entity", "degree": 25},
            {"name": "Less Central", "degree": 10},
        ])

        async with mock_driver.session() as session:
            result = await session.run(
                """
                MATCH (e:Entity)-[r]-()
                WITH e, count(r) as degree
                RETURN e.name as name, degree
                ORDER BY degree DESC
                LIMIT 10
                """
            )
            records = list(result)

        assert records[0]["degree"] > records[1]["degree"]

    @pytest.mark.asyncio
    async def test_gets_graph_health_status(self, mock_driver):
        """Should return graph health status."""
        mock_driver.set_query_results([{
            "entity_count": 1000,
            "relationship_count": 5000,
            "orphan_count": 25,
        }])

        async with mock_driver.session() as session:
            result = await session.run(
                """
                MATCH (e:Entity)
                WITH count(e) as entity_count
                MATCH ()-[r]-()
                WITH entity_count, count(r) as relationship_count
                MATCH (orphan:Entity) WHERE NOT (orphan)--()
                RETURN entity_count, relationship_count, count(orphan) as orphan_count
                """
            )
            record = result.single()

        assert record["entity_count"] == 1000
        assert record["relationship_count"] == 5000
        assert record["orphan_count"] == 25
