"""
Knowledge Graph Service for managing Neo4j graph database operations
"""

import json
import logging
import time
import uuid
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime
from neo4j import GraphDatabase, Driver, Session
from contextlib import contextmanager

from ..core.config import settings
from ..models.graph import (
    Entity, EntityResponse, CreateEntityRequest, UpdateEntityRequest,
    Relationship, RelationshipResponse, CreateRelationshipRequest,
    EntityType, RelationshipType, ExtractionMethod,
    GraphSearchRequest, GraphSearchResponse, GraphPath,
    BatchEntityRequest, BatchEntityResponse,
    GraphAnalytics, GraphHealthStatus,
    GraphVisualizationData, GraphVisualizationNode, GraphVisualizationEdge
)

logger = logging.getLogger(__name__)


def _parse_metadata(metadata_str: str) -> Dict[str, Any]:
    """Parse metadata string back to dictionary"""
    if not metadata_str or metadata_str == "{}":
        return {}
    try:
        import ast
        return ast.literal_eval(metadata_str)
    except (ValueError, SyntaxError):
        return {}


def _convert_datetime(dt) -> datetime:
    """Convert Neo4j datetime to Python datetime"""
    if hasattr(dt, 'to_native'):
        return dt.to_native()
    return datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)


class KnowledgeGraphService:
    """Service for managing knowledge graph operations using Neo4j"""

    _driver_instance: Optional[Driver] = None

    def __init__(self):
        self.driver: Optional[Driver] = None
        self.uri = settings.NEO4J_URI
        self.user = settings.NEO4J_USER
        self.password = settings.NEO4J_PASSWORD
        # Do not connect immediately to avoid import-time side effects
        # self._connect() 

    async def __aenter__(self):
        self._connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # We don't close the shared driver here anymore
        pass

    @classmethod
    def close_driver(cls):
        """Close the shared driver instance"""
        if cls._driver_instance:
            cls._driver_instance.close()
            cls._driver_instance = None
            logger.info("Closed shared Neo4j driver")

    def _connect(self):
        """Establish connection to Neo4j database (using shared driver)"""
        if KnowledgeGraphService._driver_instance:
            self.driver = KnowledgeGraphService._driver_instance
            return

        try:
            KnowledgeGraphService._driver_instance = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
                max_connection_lifetime=3600,
                max_connection_pool_size=50
            )
            self.driver = KnowledgeGraphService._driver_instance
            
            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            logger.info(f"Connected to Neo4j at {self.uri}")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            # Don't raise here, let the caller handle it or retry later
            self.driver = None
            KnowledgeGraphService._driver_instance = None

    @contextmanager
    def get_session(self, database: str = "neo4j") -> Session:
        """Context manager for database sessions"""
        if not self.driver:
            self._connect()
        
        if not self.driver:
            raise RuntimeError("Neo4j driver not initialized")
            
        session = self.driver.session(database=database)
        try:
            yield session
        finally:
            session.close()

    def _ensure_schema(self):
        """Ensure database schema constraints and indexes exist"""
        if not self.driver:
            self._connect()
            
        if not self.driver:
            logger.warning("Skipping schema initialization - no connection to Neo4j")
            return

        try:
            with self.get_session() as session:

                # Create constraints
                constraints = [
                    "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
                    "CREATE CONSTRAINT document_id_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
                    "CREATE INDEX entity_name_index IF NOT EXISTS FOR (e:Entity) ON (e.name)",
                    "CREATE INDEX entity_type_index IF NOT EXISTS FOR (e:Entity) ON (e.type)",
                    "CREATE INDEX document_title_index IF NOT EXISTS FOR (d:Document) ON (d.title)",
                    "CREATE INDEX relationship_strength_index IF NOT EXISTS FOR ()-[r:RELATED_TO]-() ON (r.strength)"
                ]

                for constraint in constraints:
                    try:
                        session.run(constraint)
                        logger.debug(f"Applied schema: {constraint}")
                    except Exception as e:
                        if "already exists" not in str(e).lower():
                            logger.warning(f"Failed to apply constraint: {e}")

                logger.info("Database schema ensured")
        except Exception as e:
            logger.error(f"Failed to ensure database schema: {e}")
            raise

    def close(self):
        """
        Close Neo4j driver connection.
        
        NOTE: With Singleton pattern, we DO NOT close the shared driver here.
        The driver should remain open for the application lifetime.
        Use close_driver() class method for explicit shutdown.
        """
        # if self.driver:
        #     self.driver.close()
        #     logger.info("Neo4j connection closed")
        pass

    # Entity Management
    def create_entity(self, request: CreateEntityRequest) -> EntityResponse:
        """Create a new entity in the knowledge graph"""
        start_time = time.time()
        entity_id = str(uuid.uuid4())

        try:
            with self.get_session() as session:
                query = f"""
                CREATE (e:Entity:{request.entity_type.value} {{
                    id: $id,
                    name: $name,
                    type: $entity_type,
                    confidence_score: $confidence_score,
                    extraction_method: $extraction_method,
                    position: $position,
                    context: $context,
                    metadata: $metadata,
                    source_document_id: $source_document_id,
                    created_at: datetime(),
                    updated_at: datetime()
                }})
                RETURN e
                """

                result = session.run(query, {
                    "id": entity_id,
                    "name": request.name,
                    "entity_type": request.entity_type.value,
                    "entity_type": request.entity_type.value,
                    "confidence_score": request.confidence_score,
                    "extraction_method": request.extraction_method.value,
                    "position": request.position,
                    "context": request.context,
                    "metadata": str(request.metadata) if request.metadata else "{}",
                    "source_document_id": request.source_document_id
                })

                node = result.single()
                if not node:
                    raise RuntimeError("Failed to create entity")

                processing_time = time.time() - start_time
                logger.info(f"Created entity: {request.name} ({entity_id}) in {processing_time:.3f}s")

                return EntityResponse(
                    id=entity_id,
                    name=request.name,
                    entity_type=request.entity_type,
                    confidence_score=request.confidence_score,
                    extraction_method=request.extraction_method,
                    position=request.position,
                    context=request.context,
                    metadata=request.metadata,
                    source_document_id=request.source_document_id,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )

        except Exception as e:
            logger.error(f"Error creating entity {request.name}: {e}")
            raise

    def get_entity(self, entity_id: str) -> Optional[EntityResponse]:
        """Retrieve an entity by ID"""
        try:
            with self.get_session() as session:
                query = """
                MATCH (e:Entity {id: $entity_id})
                RETURN e
                """

                result = session.run(query, {"entity_id": entity_id})
                node = result.single()

                if not node:
                    return None

                e = node["e"]
                return EntityResponse(
                    id=e["id"],
                    name=e["name"],
                    entity_type=EntityType(e["type"]),
                    confidence_score=e["confidence_score"],
                    extraction_method=ExtractionMethod(e["extraction_method"]),
                    position=e.get("position"),
                    context=e.get("context"),
                    metadata=_parse_metadata(e.get("metadata", "{}")),
                    source_document_id=e.get("source_document_id"),
                    created_at=_convert_datetime(e["created_at"]),
                    updated_at=_convert_datetime(e["updated_at"]) if e.get("updated_at") else None
                )
        except Exception as e:
            logger.error(f"Error retrieving entity {entity_id}: {e}")
            return None

    def update_entity(self, entity_id: str, request: UpdateEntityRequest) -> Optional[EntityResponse]:
        """Update an existing entity"""
        try:
            with self.get_session() as session:
                # Build update parameters dynamically
                update_fields = []
                params = {"entity_id": entity_id, "updated_at": datetime.utcnow()}

                if request.name is not None:
                    update_fields.append("e.name = $name")
                    params["name"] = request.name

                if request.confidence_score is not None:
                    update_fields.append("e.confidence_score = $confidence_score")
                    params["confidence_score"] = request.confidence_score

                if request.metadata is not None:
                    update_fields.append("e.metadata = $metadata")
                    params["metadata"] = str(request.metadata) if request.metadata else "{}"

                if not update_fields:
                    return self.get_entity(entity_id)

                update_fields.append("e.updated_at = $updated_at")
                set_clause = ", ".join(update_fields)

                query = f"""
                MATCH (e:Entity {{id: $entity_id}})
                SET {set_clause}
                RETURN e
                """

                result = session.run(query, params)
                node = result.single()

                if not node:
                    return None

                e = node["e"]
                return EntityResponse(
                    id=e["id"],
                    name=e["name"],
                    entity_type=EntityType(e["type"]),
                    confidence_score=e["confidence_score"],
                    extraction_method=ExtractionMethod(e["extraction_method"]),
                    position=e.get("position"),
                    context=e.get("context"),
                    metadata=_parse_metadata(e.get("metadata", "{}")),
                    source_document_id=e.get("source_document_id"),
                    created_at=_convert_datetime(e["created_at"]),
                    updated_at=_convert_datetime(e["updated_at"]) if e.get("updated_at") else None
                )
        except Exception as e:
            logger.error(f"Error updating entity {entity_id}: {e}")
            return None

    def delete_entity(self, entity_id: str) -> bool:
        """Delete an entity and all its relationships"""
        try:
            with self.get_session() as session:
                query = """
                MATCH (e:Entity {id: $entity_id})
                DETACH DELETE e
                RETURN count(e) as deleted_count
                """

                result = session.run(query, {"entity_id": entity_id})
                deleted_count = result.single()["deleted_count"]

                if deleted_count > 0:
                    logger.info(f"Deleted entity {entity_id}")
                    return True
                else:
                    logger.warning(f"Entity {entity_id} not found for deletion")
                    return False
        except Exception as e:
            logger.error(f"Error deleting entity {entity_id}: {e}")
            return False

    def search_entities(self, query: str, entity_types: Optional[List[EntityType]] = None,
                       limit: int = 50) -> List[EntityResponse]:
        """Search for entities by name or properties"""
        try:
            with self.get_session() as session:
                # Build query conditions
                conditions = ["e.name CONTAINS $query"]
                params = {"query": query, "limit": limit}

                if entity_types:
                    type_condition = " OR ".join([f"e.type = '{t.value}'" for t in entity_types])
                    conditions.append(f"({type_condition})")

                where_clause = " AND ".join(conditions)

                search_query = f"""
                MATCH (e:Entity)
                WHERE {where_clause}
                RETURN e
                ORDER BY e.confidence_score DESC
                LIMIT $limit
                """

                result = session.run(search_query, params)
                entities = []

                for node in result:
                    e = node["e"]
                    entities.append(EntityResponse(
                        id=e["id"],
                        name=e["name"],
                        entity_type=EntityType(e["type"]),
                        confidence_score=e["confidence_score"],
                        extraction_method=ExtractionMethod(e["extraction_method"]),
                        position=e.get("position"),
                        context=e.get("context"),
                        metadata=_parse_metadata(e.get("metadata", "{}")),
                        source_document_id=e.get("source_document_id"),
                        created_at=_convert_datetime(e["created_at"]),
                        updated_at=_convert_datetime(e["updated_at"]) if e.get("updated_at") else None
                    ))

                return entities
        except Exception as e:
            logger.error(f"Error searching entities: {e}")
            return []

    def get_all_entities(self, limit: int = 100, offset: int = 0,
                          entity_types: Optional[List[EntityType]] = None) -> List[EntityResponse]:
        """Get all entities with pagination and optional filtering"""
        try:
            with self.get_session() as session:
                # Build query conditions
                conditions = []
                params = {"limit": limit, "offset": offset}

                if entity_types:
                    # Match specific entity type labels
                    type_labels = [f"e:{t.value}" for t in entity_types]
                    match_clause = f"MATCH ({'|'.join(type_labels)})"
                    conditions.append("true")  # Dummy condition for structure
                else:
                    # Match all possible entity type labels
                    match_clause = "MATCH (e) WHERE any(label IN labels(e) WHERE label IN ['Person', 'Organization', 'Location', 'Concept', 'Event', 'Product', 'Date', 'Technology', 'Document'])"

                where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

                # Use the appropriate MATCH clause
                query = f"""
                {match_clause}
                {where_clause}
                RETURN e
                ORDER BY e.created_at DESC
                SKIP $offset
                LIMIT $limit
                """

                result = session.run(query, params)
                entities = []

                for node in result:
                    e = node["e"]
                    # Handle legacy nodes that might not have all properties
                    labels = e.labels if hasattr(e, 'labels') else []
                    entity_type = EntityType.PERSON  # Default

                    # Determine entity type from labels or properties
                    if "type" in e:
                        entity_type = EntityType(e["type"])
                    elif labels:
                        # Map label to entity type
                        label_map = {
                            'Person': EntityType.PERSON,
                            'Organization': EntityType.ORGANIZATION,
                            'Location': EntityType.LOCATION,
                            'Concept': EntityType.CONCEPT,
                            'Event': EntityType.EVENT,
                            'Product': EntityType.PRODUCT,
                            'Date': EntityType.DATE,
                            'Technology': EntityType.TECHNOLOGY,
                            'Document': EntityType.DOCUMENT
                        }
                        for label in labels:
                            if label in label_map:
                                entity_type = label_map[label]
                                break

                    entities.append(EntityResponse(
                        id=e.get("id", str(uuid.uuid4())),
                        name=e.get("name", "Unknown"),
                        entity_type=entity_type,
                        confidence_score=e.get("confidence_score", 0.8),
                        extraction_method=ExtractionMethod(e.get("extraction_method", "manual")),
                        position=e.get("position"),
                        context=e.get("context"),
                        metadata=_parse_metadata(e.get("metadata", "{}")),
                        source_document_id=e.get("source_document_id"),
                        created_at=_convert_datetime(e.get("created_at", datetime.utcnow())),
                        updated_at=_convert_datetime(e["updated_at"]) if e.get("updated_at") else None
                    ))

                return entities
        except Exception as e:
            logger.error(f"Error getting all entities: {e}")
            return []

    # Relationship Management
    def create_relationship(self, request: CreateRelationshipRequest) -> RelationshipResponse:
        """Create a new relationship between entities"""
        start_time = time.time()
        relationship_id = str(uuid.uuid4())

        try:
            with self.get_session() as session:
                query = """
                MATCH (source:Entity {id: $source_entity_id})
                MATCH (target:Entity {id: $target_entity_id})
                CREATE (source)-[r:RELATED_TO {
                    id: $id,
                    type: $relationship_type,
                    strength: $strength,
                    confidence_score: $confidence_score,
                    context: $context,
                    evidence: $evidence,
                    metadata: $metadata,
                    source_document_id: $source_document_id,
                    created_at: datetime(),
                    updated_at: datetime()
                }]->(target)
                RETURN r, source, target
                """

                # Serialize evidence and metadata to JSON strings (Neo4j only accepts primitives)
                evidence_str = json.dumps(request.evidence) if request.evidence else "[]"
                metadata_str = json.dumps(request.metadata) if request.metadata else "{}"
                
                result = session.run(query, {
                    "id": relationship_id,
                    "source_entity_id": request.source_entity_id,
                    "target_entity_id": request.target_entity_id,
                    "relationship_type": request.relationship_type.value,
                    "strength": request.strength,
                    "confidence_score": request.confidence_score,
                    "context": request.context,
                    "evidence": evidence_str,
                    "metadata": metadata_str,
                    "source_document_id": request.source_document_id
                })

                record = result.single()
                if not record:
                    raise RuntimeError("Failed to create relationship")

                processing_time = time.time() - start_time
                logger.info(f"Created relationship: {request.source_entity_id} -> {request.target_entity_id} ({relationship_id}) in {processing_time:.3f}s")

                return RelationshipResponse(
                    id=relationship_id,
                    source_entity_id=request.source_entity_id,
                    target_entity_id=request.target_entity_id,
                    relationship_type=request.relationship_type,
                    strength=request.strength,
                    confidence_score=request.confidence_score,
                    context=request.context,
                    evidence=request.evidence,
                    metadata=request.metadata,
                    source_document_id=request.source_document_id,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
        except Exception as e:
            logger.error(f"Error creating relationship: {e}")
            raise

    def get_relationships(self, entity_id: str, relationship_types: Optional[List[RelationshipType]] = None) -> List[RelationshipResponse]:
        """Get all relationships for an entity"""
        try:
            with self.get_session() as session:
                conditions = ["source.id = $entity_id OR target.id = $entity_id"]
                params = {"entity_id": entity_id}

                if relationship_types:
                    type_condition = " OR ".join([f"r.type = '{t.value}'" for t in relationship_types])
                    conditions.append(f"({type_condition})")

                where_clause = " AND ".join(conditions)

                query = f"""
                MATCH (source:Entity)-[r:RELATED_TO]-(target:Entity)
                WHERE {where_clause}
                RETURN r, source.id AS source_id, target.id AS target_id
                """

                result = session.run(query, params)
                relationships = []

                for record in result:
                    r = record["r"]
                    relationships.append(RelationshipResponse(
                        id=r["id"],
                        source_entity_id=record["source_id"],
                        target_entity_id=record["target_id"],
                        relationship_type=RelationshipType(r["type"]),
                        strength=r["strength"],
                        confidence_score=r["confidence_score"],
                        context=r.get("context"),
                        evidence=r.get("evidence", []),
                        metadata=r.get("metadata", {}),
                        source_document_id=r.get("source_document_id"),
                        created_at=r["created_at"],
                        updated_at=r.get("updated_at")
                    ))

                return relationships
        except Exception as e:
            logger.error(f"Error retrieving relationships for {entity_id}: {e}")
            return []

    def delete_relationship(self, relationship_id: str) -> bool:
        """Delete a relationship by ID"""
        try:
            with self.get_session() as session:
                query = """
                MATCH (source)-[r:RELATED_TO {id: $relationship_id}]-(target)
                DELETE r
                RETURN count(r) as deleted_count
                """

                result = session.run(query, {"relationship_id": relationship_id})
                deleted_count = result.single()["deleted_count"]

                if deleted_count > 0:
                    logger.info(f"Deleted relationship {relationship_id}")
                    return True
                else:
                    logger.warning(f"Relationship {relationship_id} not found for deletion")
                    return False
        except Exception as e:
            logger.error(f"Error deleting relationship {relationship_id}: {e}")
            return False

    # Graph Search and Traversal
    def find_related_entities(self, entity_id: str, max_depth: int = 2,
                            min_strength: float = 0.1, limit: int = 50) -> List[EntityResponse]:
        """Find entities related to a given entity"""
        try:
            with self.get_session() as session:
                query = """
                MATCH (start:Entity {id: $entity_id})
                MATCH (start)-[r:RELATED_TO*1..$max_depth]-(related:Entity)
                WHERE all(rel in r WHERE rel.strength >= $min_strength)
                RETURN DISTINCT related
                LIMIT $limit
                """

                result = session.run(query, {
                    "entity_id": entity_id,
                    "max_depth": max_depth,
                    "min_strength": min_strength,
                    "limit": limit
                })

                entities = []
                for node in result:
                    e = node["related"]
                    if e["id"] != entity_id:  # Exclude the start entity
                        entities.append(EntityResponse(
                            id=e["id"],
                            name=e["name"],
                            entity_type=EntityType(e["type"]),
                            confidence_score=e["confidence_score"],
                            extraction_method=ExtractionMethod(e["extraction_method"]),
                            position=e.get("position"),
                            context=e.get("context"),
                            metadata=_parse_metadata(e.get("metadata", "{}")),
                            source_document_id=e.get("source_document_id"),
                            created_at=_convert_datetime(e["created_at"]),
                            updated_at=_convert_datetime(e["updated_at"]) if e.get("updated_at") else None
                        ))

                return entities
        except Exception as e:
            logger.error(f"Error finding related entities for {entity_id}: {e}")
            return []

    def find_paths(self, source_id: str, target_id: str, max_depth: int = 3,
                  min_strength: float = 0.1) -> List[GraphPath]:
        """Find paths between two entities"""
        try:
            with self.get_session() as session:
                query = """
                MATCH path = (start:Entity {id: $source_id})-[:RELATED_TO*1..$max_depth]-(end:Entity {id: $target_id})
                WHERE all(rel in relationships(path) WHERE rel.strength >= $min_strength)
                RETURN path, length(path) as path_length
                ORDER BY path_length, reduce(strength = 1.0, rel in relationships(path) | strength * rel.strength) DESC
                LIMIT 10
                """

                result = session.run(query, {
                    "source_id": source_id,
                    "target_id": target_id,
                    "max_depth": max_depth,
                    "min_strength": min_strength
                })

                paths = []
                for record in result:
                    path_obj = record["path"]
                    path_length = record["path_length"]

                    # Extract entities and relationships from path
                    entities = []
                    relationships = []
                    total_strength = 1.0

                    for node in path_obj.nodes:
                        e = node
                        entities.append(EntityResponse(
                            id=e["id"],
                            name=e["name"],
                            entity_type=EntityType(e["type"]),
                            confidence_score=e["confidence_score"],
                            extraction_method=ExtractionMethod(e["extraction_method"]),
                            position=e.get("position"),
                            context=e.get("context"),
                            metadata=_parse_metadata(e.get("metadata", "{}")),
                            source_document_id=e.get("source_document_id"),
                            created_at=_convert_datetime(e["created_at"]),
                            updated_at=_convert_datetime(e["updated_at"]) if e.get("updated_at") else None
                        ))

                    for rel in path_obj.relationships:
                        r = rel
                        total_strength *= r["strength"]
                        relationships.append(RelationshipResponse(
                            id=r["id"],
                            source_entity_id=r["source_entity_id"],
                            target_entity_id=r["target_entity_id"],
                            relationship_type=RelationshipType(r["type"]),
                            strength=r["strength"],
                            confidence_score=r["confidence_score"],
                            context=r.get("context"),
                            evidence=r.get("evidence", []),
                            metadata=r.get("metadata", {}),
                            source_document_id=r.get("source_document_id"),
                            created_at=r["created_at"],
                            updated_at=r.get("updated_at")
                        ))

                    paths.append(GraphPath(
                        entities=entities,
                        relationships=relationships,
                        total_strength=total_strength,
                        path_length=path_length,
                        confidence_score=min([rel.confidence_score for rel in relationships])
                    ))

                return paths
        except Exception as e:
            logger.error(f"Error finding paths between {source_id} and {target_id}: {e}")
            return []

    # Batch Operations
    def create_entities_batch(self, request: BatchEntityRequest) -> BatchEntityResponse:
        """Create multiple entities and relationships in a batch"""
        start_time = time.time()
        response = BatchEntityResponse()

        try:
            with self.get_session() as session:
                with session.begin_transaction() as tx:
                    # Create entities
                    for entity_req in request.entities:
                        try:
                            entity = self._create_entity_in_transaction(tx, entity_req)
                            if entity:
                                response.created_entities.append(entity)
                        except Exception as e:
                            response.errors.append({
                                "type": "entity_creation_error",
                                "data": entity_req.dict(),
                                "error": str(e)
                            })

                    # Create relationships
                    for rel_req in request.relationships:
                        try:
                            relationship = self._create_relationship_in_transaction(tx, rel_req)
                            if relationship:
                                response.created_relationships.append(relationship)
                        except Exception as e:
                            response.errors.append({
                                "type": "relationship_creation_error",
                                "data": rel_req.dict(),
                                "error": str(e)
                            })

            response.processing_time = time.time() - start_time
            logger.info(f"Batch processing completed: {len(response.created_entities)} entities, {len(response.created_relationships)} relationships in {response.processing_time:.3f}s")

            return response
        except Exception as e:
            logger.error(f"Error in batch processing: {e}")
            response.processing_time = time.time() - start_time
            response.errors.append({
                "type": "batch_processing_error",
                "error": str(e)
            })
            return response

    def _create_entity_in_transaction(self, tx, request: CreateEntityRequest) -> Optional[EntityResponse]:
        """Helper to create entity within a transaction"""
        entity_id = str(uuid.uuid4())
        query = f"""
        CREATE (e:Entity:{request.entity_type.value} {{
            id: $id,
            name: $name,
            type: $entity_type,
            confidence_score: $confidence_score,
            extraction_method: $extraction_method,
            position: $position,
            context: $context,
            metadata: $metadata,
            source_document_id: $source_document_id,
            created_at: datetime(),
            updated_at: datetime()
        }})
        RETURN e
        """

        result = tx.run(query, {
            "id": entity_id,
            "name": request.name,
            "entity_type": request.entity_type.value,
            "entity_type": request.entity_type.value,
            "confidence_score": request.confidence_score,
            "extraction_method": request.extraction_method.value,
            "position": request.position,
            "context": request.context,
            "metadata": str(request.metadata) if request.metadata else "{}",
            "source_document_id": request.source_document_id
        })

        node = result.single()
        if not node:
            return None

        return EntityResponse(
            id=entity_id,
            name=request.name,
            entity_type=request.entity_type,
            confidence_score=request.confidence_score,
            extraction_method=request.extraction_method,
            position=request.position,
            context=request.context,
            metadata=request.metadata,
            source_document_id=request.source_document_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

    def _create_relationship_in_transaction(self, tx, request: CreateRelationshipRequest) -> Optional[RelationshipResponse]:
        """Helper to create relationship within a transaction"""
        relationship_id = str(uuid.uuid4())
        query = """
        MATCH (source:Entity {id: $source_entity_id})
        MATCH (target:Entity {id: $target_entity_id})
        CREATE (source)-[r:RELATED_TO {
            id: $id,
            type: $relationship_type,
            strength: $strength,
            confidence_score: $confidence_score,
            context: $context,
            evidence: $evidence,
            metadata: $metadata,
            source_document_id: $source_document_id,
            created_at: datetime(),
            updated_at: datetime()
        }]->(target)
        RETURN r
        """

        # Serialize evidence and metadata to JSON strings (Neo4j only accepts primitives)
        evidence_str = json.dumps(request.evidence) if request.evidence else "[]"
        metadata_str = json.dumps(request.metadata) if request.metadata else "{}"
        
        result = tx.run(query, {
            "id": relationship_id,
            "source_entity_id": request.source_entity_id,
            "target_entity_id": request.target_entity_id,
            "relationship_type": request.relationship_type.value,
            "strength": request.strength,
            "confidence_score": request.confidence_score,
            "context": request.context,
            "evidence": evidence_str,
            "metadata": metadata_str,
            "source_document_id": request.source_document_id
        })

        rel = result.single()
        if not rel:
            return None

        return RelationshipResponse(
            id=relationship_id,
            source_entity_id=request.source_entity_id,
            target_entity_id=request.target_entity_id,
            relationship_type=request.relationship_type,
            strength=request.strength,
            confidence_score=request.confidence_score,
            context=request.context,
            evidence=request.evidence,
            metadata=request.metadata,
            source_document_id=request.source_document_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

    # Analytics and Statistics
    def get_graph_analytics(self) -> GraphAnalytics:
        """Get comprehensive graph analytics"""
        try:
            with self.get_session() as session:
                # Get basic counts
                node_count_result = session.run("MATCH (n) RETURN count(n) as count").single()
                relationship_count_result = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()

                total_entities = node_count_result["count"]
                total_relationships = relationship_count_result["count"]

                # Get entity type distribution
                entity_types_result = session.run("MATCH (e:Entity) RETURN e.type as type, count(e) as count")
                entity_type_counts = {record["type"]: record["count"] for record in entity_types_result}

                # Get relationship type distribution
                rel_types_result = session.run("MATCH ()-[r:RELATED_TO]->() RETURN r.type as type, count(r) as count")
                relationship_type_counts = {record["type"]: record["count"] for record in rel_types_result}

                # Calculate average degree
                if total_entities > 0:
                    avg_degree = (2 * total_relationships) / total_entities
                else:
                    avg_degree = 0.0

                # Get connected components
                components_result = session.run("""
                CALL gds.graph.project('tempGraph', 'Entity', 'RELATED_TO')
                YIELD graphName
                CALL gds.connectedComponents.stream('tempGraph')
                YIELD nodeId, componentId
                WITH componentId, count(*) as size
                RETURN count(DISTINCT componentId) as components, max(size) as largest_size
                """).single()

                connected_components = components_result["components"] if components_result else 0
                largest_component_size = components_result["largest_size"] if components_result else 0

                return GraphAnalytics(
                    total_entities=total_entities,
                    total_relationships=total_relationships,
                    entity_type_counts=entity_type_counts,
                    relationship_type_counts=relationship_type_counts,
                    average_degree=avg_degree,
                    connected_components=connected_components,
                    largest_component_size=largest_component_size,
                    clustering_coefficient=0.0  # TODO: Implement clustering coefficient calculation
                )
        except Exception as e:
            logger.error(f"Error getting graph analytics: {e}")
            return GraphAnalytics()

    def get_health_status(self) -> GraphHealthStatus:
        """Get health status of the graph database"""
        start_time = time.time()
        try:
            with self.get_session() as session:
                # Test basic connectivity
                start_time = time.time()
                session.run("RETURN 1")
                response_time_ms = (time.time() - start_time) * 1000

                # Get database info
                version_result = session.run("CALL dbms.components() YIELD name, versions RETURN versions[0] as version").single()
                node_count_result = session.run("MATCH (n) RETURN count(n) as count").single()
                rel_count_result = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()

                # Get indexes and constraints
                index_result = session.run("SHOW INDEXES YIELD type RETURN count(*) as count").single()
                constraint_result = session.run("SHOW CONSTRAINTS YIELD type RETURN count(*) as count").single()

                return GraphHealthStatus(
                    status="healthy",
                    neo4j_version=version_result["version"] if version_result else "unknown",
                    database_size=None,  # TODO: Implement size calculation
                    node_count=node_count_result["count"] if node_count_result else 0,
                    relationship_count=rel_count_result["count"] if rel_count_result else 0,
                    index_count=index_result["count"] if index_result else 0,
                    constraint_count=constraint_result["count"] if constraint_result else 0,
                    uptime=None,  # TODO: Implement uptime calculation
                    last_error=None,
                    response_time_ms=response_time_ms
                )
        except Exception as e:
            logger.error(f"Error getting health status: {e}")
            return GraphHealthStatus(
                status="unhealthy",
                neo4j_version="unknown",
                node_count=0,
                relationship_count=0,
                index_count=0,
                constraint_count=0,
                response_time_ms=(time.time() - start_time) * 1000,
                last_error=str(e)
            )


# Global instance
knowledge_graph_service = KnowledgeGraphService()