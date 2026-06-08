"""
Knowledge Graph Service (Port 8003)
Standalone microservice for entity extraction and relationship management
"""

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import redis.asyncio as redis
from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from neo4j import AsyncDriver, AsyncGraphDatabase, AsyncSession
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession as SQLAsyncSession

from .config.knowledge_graph_config import KnowledgeGraphConfig
from .core.auth import get_current_user, verify_websocket_token
from .core.cache import cache_delete, cache_get, cache_set
from .core.database import get_async_db
from .models.knowledge_graph_models import (
    BatchEntityRequest,
    BatchEntityResponse,
    CreateEntityRequest,
    CreateRelationshipRequest,
    Entity,
    EntityResponse,
    EntityType,
    ExtractionMethod,
    Relationship,
    RelationshipResponse,
    RelationshipType,
    UpdateEntityRequest,
)
from .models.postgres_models import EntitySQL, RelationshipSQL
from .services.services.entity_extraction_service import EntityExtractionService
from .services.tenant_service import TenantService
from .services.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)
config = KnowledgeGraphConfig()

# Global services
websocket_manager = WebSocketManager()
entity_extractor = EntityExtractionService()
tenant_service = TenantService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting Knowledge Graph Service on port 8003...")

    # Initialize Neo4j connection
    app.state.neo4j_driver = AsyncGraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USER, config.NEO4J_PASSWORD),
        max_connection_lifetime=3600,
        max_connection_pool_size=50,
    )

    # Initialize Redis
    app.state.redis_client = redis.from_url(config.REDIS_URL)

    # Test connections
    await test_connections(app)

    # Ensure schema
    await ensure_schema(app)

    logger.info("Knowledge Graph Service startup complete")

    yield

    # Shutdown
    logger.info("Shutting down Knowledge Graph Service...")
    await app.state.neo4j_driver.close()
    await app.state.redis_client.close()
    logger.info("Knowledge Graph Service shutdown complete")


async def test_connections(app):
    """Test database connections"""
    try:
        # Test Neo4j
        async with app.state.neo4j_driver.session() as session:
            await session.run("RETURN 1")
        logger.info("Neo4j connection successful")

        # Test Redis
        await app.state.redis_client.ping()
        logger.info("Redis connection successful")

    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        raise


async def ensure_schema(app):
    """Ensure Neo4j schema constraints and indexes"""
    try:
        async with app.state.neo4j_driver.session() as session:
            constraints = [
                "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
                "CREATE CONSTRAINT document_id_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
                "CREATE INDEX entity_name_index IF NOT EXISTS FOR (e:Entity) ON (e.name)",
                "CREATE INDEX entity_type_index IF NOT EXISTS FOR (e:Entity) ON (e.type)",
                "CREATE INDEX entity_tenant_index IF NOT EXISTS FOR (e:Entity) ON (e.tenant_id)",
                "CREATE INDEX relationship_strength_index IF NOT EXISTS FOR ()-[r:RELATED_TO]-() ON (r.strength)",
            ]

            for constraint in constraints:
                try:
                    await session.run(constraint)
                    logger.debug(f"Applied schema: {constraint}")
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        logger.warning(f"Failed to apply constraint: {e}")

            logger.info("Neo4j schema ensured")
    except Exception as e:
        logger.error(f"Failed to ensure schema: {e}")
        raise


app = FastAPI(
    title="Knowledge Graph Service",
    version="1.0.0",
    description="Entity extraction and relationship management service",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware — use centralized config or env var
try:
    from src.core.config import settings as _core_settings

    _cors_origins: list = _core_settings.cors_origins_list
except ImportError:
    import os as _os

    _raw_origins = _os.getenv("CORS_ORIGINS", "http://localhost:3000")
    _cors_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)


async def get_neo4j_session(app) -> AsyncSession:
    """Get Neo4j session"""
    return app.state.neo4j_driver.session()


async def get_redis_client(app):
    """Get Redis client"""
    return app.state.redis_client


def parse_metadata(metadata_str: str) -> Dict[str, Any]:
    """Parse metadata string safely using JSON"""
    if not metadata_str or metadata_str == "{}":
        return {}
    try:
        return json.loads(metadata_str)
    except (ValueError, json.JSONDecodeError):
        return {}


def safe_entity_type(value: Optional[str]) -> EntityType:
    """Safely convert string to EntityType, falling back to OTHER for unknown values"""
    if not value:
        return EntityType.OTHER
    try:
        return EntityType(value)
    except ValueError:
        logger.debug(f"Unknown EntityType '{value}', using OTHER")
        return EntityType.OTHER


def safe_extraction_method(value: Optional[str]) -> ExtractionMethod:
    """Safely convert string to ExtractionMethod, falling back to UNKNOWN for None/unknown values"""
    if not value:
        return ExtractionMethod.UNKNOWN
    try:
        return ExtractionMethod(value)
    except ValueError:
        logger.debug(f"Unknown ExtractionMethod '{value}', using UNKNOWN")
        return ExtractionMethod.UNKNOWN


# Entity Management Endpoints
@app.post("/entities", response_model=EntityResponse)
async def create_entity(
    request: CreateEntityRequest,
    current_user=Depends(get_current_user),
    db: SQLAsyncSession = Depends(get_async_db),
    neo4j_session=Depends(get_neo4j_session),
    redis_client=Depends(get_redis_client),
):
    """Create a new entity in the knowledge graph"""
    try:
        # Verify tenant access
        await tenant_service.verify_tenant_access(
            current_user.tenant_id, "entity:create"
        )

        entity_id = str(uuid.uuid4())

        # Create in Neo4j
        neo4j_query = f"""
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
            tenant_id: $tenant_id,
            created_at: datetime(),
            updated_at: datetime()
        }})
        RETURN e
        """

        await neo4j_session.run(
            neo4j_query,
            {
                "id": entity_id,
                "name": request.name,
                "entity_type": request.entity_type.value,
                "confidence_score": request.confidence_score,
                "extraction_method": request.extraction_method.value,
                "position": request.position,
                "context": request.context,
                "metadata": json.dumps(request.metadata) if request.metadata else "{}",
                "source_document_id": request.source_document_id,
                "tenant_id": current_user.tenant_id,
            },
        )

        # Create in PostgreSQL for additional metadata and search
        entity_sql = EntitySQL(
            id=entity_id,
            name=request.name,
            entity_type=request.entity_type.value,
            confidence_score=request.confidence_score,
            extraction_method=request.extraction_method.value,
            metadata=request.metadata,
            source_document_id=request.source_document_id,
            tenant_id=current_user.tenant_id,
        )
        db.add(entity_sql)
        await db.commit()

        # Cache the entity
        entity_response = EntityResponse(
            id=entity_id,
            name=request.name,
            entity_type=request.entity_type,
            confidence_score=request.confidence_score,
            extraction_method=request.extraction_method,
            position=request.position,
            context=request.context,
            metadata=request.metadata,
            source_document_id=request.source_document_id,
        )

        cache_key = f"entity:{entity_id}:tenant:{current_user.tenant_id}"
        await cache_set(redis_client, cache_key, entity_response.dict(), ttl=3600)

        # Notify WebSocket clients
        await websocket_manager.broadcast_to_tenant(
            current_user.tenant_id,
            {"type": "entity_created", "entity": entity_response.dict()},
        )

        logger.info(
            f"Created entity: {request.name} ({entity_id}) for tenant {current_user.tenant_id}"
        )
        return entity_response

    except Exception as e:
        logger.error(f"Error creating entity {request.name}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/entities/{entity_id}", response_model=EntityResponse)
async def get_entity(
    entity_id: str,
    current_user=Depends(get_current_user),
    redis_client=Depends(get_redis_client),
    neo4j_session=Depends(get_neo4j_session),
):
    """Get an entity by ID"""
    try:
        # Check cache first
        cache_key = f"entity:{entity_id}:tenant:{current_user.tenant_id}"
        cached_entity = await cache_get(redis_client, cache_key)
        if cached_entity:
            return EntityResponse(**cached_entity)

        # Query Neo4j
        query = """
        MATCH (e:Entity {id: $entity_id, tenant_id: $tenant_id})
        RETURN e
        """

        result = await neo4j_session.run(
            query, {"entity_id": entity_id, "tenant_id": current_user.tenant_id}
        )
        node = await result.single()

        if not node:
            raise HTTPException(status_code=404, detail="Entity not found")

        e = node["e"]
        entity_response = EntityResponse(
            id=e["id"],
            name=e["name"],
            entity_type=safe_entity_type(e["type"]),
            confidence_score=e["confidence_score"],
            extraction_method=safe_extraction_method(e["extraction_method"]),
            position=e.get("position"),
            context=e.get("context"),
            metadata=parse_metadata(e.get("metadata", "{}")),
            source_document_id=e.get("source_document_id"),
        )

        # Cache the result
        await cache_set(redis_client, cache_key, entity_response.dict(), ttl=3600)

        return entity_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving entity {entity_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.put("/entities/{entity_id}", response_model=EntityResponse)
async def update_entity(
    entity_id: str,
    request: UpdateEntityRequest,
    current_user=Depends(get_current_user),
    db: SQLAsyncSession = Depends(get_async_db),
    neo4j_session=Depends(get_neo4j_session),
    redis_client=Depends(get_redis_client),
):
    """Update an existing entity"""
    try:
        # Build update parameters dynamically
        update_fields = []
        params = {
            "entity_id": entity_id,
            "tenant_id": current_user.tenant_id,
        }

        if request.name is not None:
            update_fields.append("e.name = $name")
            params["name"] = request.name

        if request.confidence_score is not None:
            update_fields.append("e.confidence_score = $confidence_score")
            params["confidence_score"] = request.confidence_score

        if request.metadata is not None:
            update_fields.append("e.metadata = $metadata")
            params["metadata"] = (
                json.dumps(request.metadata) if request.metadata else "{}"
            )

        if not update_fields:
            return await get_entity(
                entity_id, current_user, redis_client, neo4j_session
            )

        # Inline datetime() — it's a Cypher function call, not a bind value.
        # Passing the string "datetime()" as $updated_at stored the literal
        # text and corrupted the timestamp on every update.
        update_fields.append("e.updated_at = datetime()")
        set_clause = ", ".join(update_fields)

        query = f"""
        MATCH (e:Entity {{id: $entity_id, tenant_id: $tenant_id}})
        SET {set_clause}
        RETURN e
        """

        result = await neo4j_session.run(query, params)
        node = await result.single()

        if not node:
            raise HTTPException(status_code=404, detail="Entity not found")

        e = node["e"]
        entity_response = EntityResponse(
            id=e["id"],
            name=e["name"],
            entity_type=safe_entity_type(e["type"]),
            confidence_score=e["confidence_score"],
            extraction_method=safe_extraction_method(e["extraction_method"]),
            position=e.get("position"),
            context=e.get("context"),
            metadata=parse_metadata(e.get("metadata", "{}")),
            source_document_id=e.get("source_document_id"),
        )

        # Update PostgreSQL record
        stmt = select(EntitySQL).where(EntitySQL.id == entity_id)
        result = await db.execute(stmt)
        entity_sql = result.scalar_one_or_none()

        if entity_sql:
            if request.name is not None:
                entity_sql.name = request.name
            if request.confidence_score is not None:
                entity_sql.confidence_score = request.confidence_score
            if request.metadata is not None:
                entity_sql.metadata = request.metadata
            await db.commit()

        # Update cache
        cache_key = f"entity:{entity_id}:tenant:{current_user.tenant_id}"
        await cache_set(redis_client, cache_key, entity_response.dict(), ttl=3600)

        # Notify WebSocket clients
        await websocket_manager.broadcast_to_tenant(
            current_user.tenant_id,
            {"type": "entity_updated", "entity": entity_response.dict()},
        )

        return entity_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating entity {entity_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.delete("/entities/{entity_id}")
async def delete_entity(
    entity_id: str,
    current_user=Depends(get_current_user),
    db: SQLAsyncSession = Depends(get_async_db),
    neo4j_session=Depends(get_neo4j_session),
    redis_client=Depends(get_redis_client),
):
    """Delete an entity and all its relationships"""
    try:
        # Delete from Neo4j
        query = """
        MATCH (e:Entity {id: $entity_id, tenant_id: $tenant_id})
        DETACH DELETE e
        RETURN count(e) as deleted_count
        """

        result = await neo4j_session.run(
            query, {"entity_id": entity_id, "tenant_id": current_user.tenant_id}
        )
        deleted_count = (await result.single())["deleted_count"]

        if deleted_count == 0:
            raise HTTPException(status_code=404, detail="Entity not found")

        # Delete from PostgreSQL
        stmt = select(EntitySQL).where(EntitySQL.id == entity_id)
        result = await db.execute(stmt)
        entity_sql = result.scalar_one_or_none()

        if entity_sql:
            await db.delete(entity_sql)
            await db.commit()

        # Clear cache
        cache_key = f"entity:{entity_id}:tenant:{current_user.tenant_id}"
        await cache_delete(redis_client, cache_key)

        # Notify WebSocket clients
        await websocket_manager.broadcast_to_tenant(
            current_user.tenant_id, {"type": "entity_deleted", "entity_id": entity_id}
        )

        logger.info(f"Deleted entity {entity_id} for tenant {current_user.tenant_id}")
        return {"message": "Entity deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting entity {entity_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/entities/batch", response_model=BatchEntityResponse)
async def batch_create_entities(
    request: BatchEntityRequest,
    current_user=Depends(get_current_user),
    db: SQLAsyncSession = Depends(get_async_db),
    neo4j_session=Depends(get_neo4j_session),
    redis_client=Depends(get_redis_client),
):
    """Create multiple entities and relationships in a batch"""
    try:
        response = BatchEntityResponse()

        async with neo4j_session.begin_transaction() as tx:
            # Create entities
            for entity_req in request.entities:
                try:
                    entity = await _create_entity_in_transaction(
                        tx, entity_req, current_user.tenant_id
                    )
                    if entity:
                        response.created_entities.append(entity)

                        # Create PostgreSQL record
                        entity_sql = EntitySQL(
                            id=entity.id,
                            name=entity.name,
                            entity_type=entity.entity_type.value,
                            confidence_score=entity.confidence_score,
                            extraction_method=entity.extraction_method.value,
                            metadata=entity.metadata,
                            source_document_id=entity.source_document_id,
                            tenant_id=current_user.tenant_id,
                        )
                        db.add(entity_sql)

                except Exception as e:
                    response.errors.append(
                        {
                            "type": "entity_creation_error",
                            "data": entity_req.dict(),
                            "error": str(e),
                        }
                    )

            # Create relationships
            for rel_req in request.relationships:
                try:
                    relationship = await _create_relationship_in_transaction(
                        tx, rel_req, current_user.tenant_id
                    )
                    if relationship:
                        response.created_relationships.append(relationship)

                        # Create PostgreSQL record
                        relationship_sql = RelationshipSQL(
                            id=relationship.id,
                            source_entity_id=relationship.source_entity_id,
                            target_entity_id=relationship.target_entity_id,
                            relationship_type=relationship.relationship_type.value,
                            strength=relationship.strength,
                            confidence_score=relationship.confidence_score,
                            metadata=relationship.metadata,
                            source_document_id=relationship.source_document_id,
                            tenant_id=current_user.tenant_id,
                        )
                        db.add(relationship_sql)

                except Exception as e:
                    response.errors.append(
                        {
                            "type": "relationship_creation_error",
                            "data": rel_req.dict(),
                            "error": str(e),
                        }
                    )

        await db.commit()

        # Notify WebSocket clients
        await websocket_manager.broadcast_to_tenant(
            current_user.tenant_id,
            {
                "type": "batch_operation_completed",
                "created_entities": len(response.created_entities),
                "created_relationships": len(response.created_relationships),
                "errors": len(response.errors),
            },
        )

        logger.info(
            f"Batch processing completed for tenant {current_user.tenant_id}: "
            f"{len(response.created_entities)} entities, {len(response.created_relationships)} relationships"
        )

        return response

    except Exception as e:
        logger.error(f"Error in batch processing: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def _create_entity_in_transaction(
    tx, request: CreateEntityRequest, tenant_id: str
) -> Optional[EntityResponse]:
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
        tenant_id: $tenant_id,
        created_at: datetime(),
        updated_at: datetime()
    }})
    RETURN e
    """

    result = await tx.run(
        query,
        {
            "id": entity_id,
            "name": request.name,
            "entity_type": request.entity_type.value,
            "confidence_score": request.confidence_score,
            "extraction_method": request.extraction_method.value,
            "position": request.position,
            "context": request.context,
            "metadata": json.dumps(request.metadata) if request.metadata else "{}",
            "source_document_id": request.source_document_id,
            "tenant_id": tenant_id,
        },
    )

    node = await result.single()
    if not node:
        return None

    e = node["e"]
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
    )


async def _create_relationship_in_transaction(
    tx, request: CreateRelationshipRequest, tenant_id: str
) -> Optional[RelationshipResponse]:
    """Helper to create relationship within a transaction"""
    relationship_id = str(uuid.uuid4())
    query = """
    MATCH (source:Entity {id: $source_entity_id, tenant_id: $tenant_id})
    MATCH (target:Entity {id: $target_entity_id, tenant_id: $tenant_id})
    CREATE (source)-[r:RELATED_TO {
        id: $id,
        type: $relationship_type,
        strength: $strength,
        confidence_score: $confidence_score,
        context: $context,
        evidence: $evidence,
        metadata: $metadata,
        source_document_id: $source_document_id,
        tenant_id: $tenant_id,
        created_at: datetime(),
        updated_at: datetime()
    }]->(target)
    RETURN r
    """

    result = await tx.run(
        query,
        {
            "id": relationship_id,
            "source_entity_id": request.source_entity_id,
            "target_entity_id": request.target_entity_id,
            "relationship_type": request.relationship_type.value,
            "strength": request.strength,
            "confidence_score": request.confidence_score,
            "context": request.context,
            "evidence": request.evidence,
            "metadata": json.dumps(request.metadata) if request.metadata else "{}",
            "source_document_id": request.source_document_id,
            "tenant_id": tenant_id,
        },
    )

    rel = await result.single()
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
    )


@app.post("/documents/{document_id}/extract-entities")
async def extract_entities_from_document(
    document_id: str,
    current_user=Depends(get_current_user),
    db: SQLAsyncSession = Depends(get_async_db),
    neo4j_session=Depends(get_neo4j_session),
):
    """Extract entities from a document and add them to the knowledge graph"""
    try:
        # Get document content (this would integrate with document service)
        # For now, assume we have document content
        document_content = await get_document_content(
            document_id, current_user.tenant_id
        )

        # Extract entities using AI service
        entities_data = await entity_extractor.extract_entities(document_content)

        # Convert to batch request
        create_requests = []
        for entity_data in entities_data:
            create_requests.append(
                CreateEntityRequest(
                    name=entity_data["name"],
                    entity_type=EntityType(entity_data["entity_type"]),
                    confidence_score=entity_data["confidence_score"],
                    extraction_method=ExtractionMethod(
                        entity_data["extraction_method"]
                    ),
                    position=entity_data.get("position"),
                    context=entity_data.get("context"),
                    metadata=entity_data.get("metadata", {}),
                    source_document_id=document_id,
                )
            )

        # Create entities in batch
        batch_request = BatchEntityRequest(
            entities=create_requests, upsert=True, document_id=document_id
        )

        result = await batch_create_entities(
            batch_request, current_user, db, neo4j_session, None
        )

        return {
            "document_id": document_id,
            "entities_found": len(entities_data),
            "entities_created": len(result.created_entities),
            "errors": len(result.errors),
            "processing_time": result.processing_time,
        }

    except Exception as e:
        logger.error(f"Error extracting entities from document {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def get_document_content(document_id: str, tenant_id: str) -> str:
    """Get document content from document service"""
    # This would integrate with document service via API call
    # For now, return placeholder
    return f"Sample document content for {document_id}"


# WebSocket endpoint for real-time updates
@app.websocket("/ws/{tenant_id}")
async def websocket_endpoint(websocket: WebSocket, tenant_id: str, token: str = None):
    """WebSocket endpoint for real-time graph updates"""
    if not token:
        await websocket.close(code=4001, reason="Authentication token required")
        return

    # Verify token
    user = await verify_websocket_token(token)
    if not user or user.tenant_id != tenant_id:
        await websocket.close(code=4003, reason="Invalid token or tenant mismatch")
        return

    await websocket_manager.connect(websocket, tenant_id)

    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming WebSocket messages if needed
            await websocket.send_text(f"Echo: {data}")

    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket, tenant_id)


# Health check endpoint
@app.get("/health")
async def health_check(request: Request):
    """Health check endpoint"""
    # Was `health_check(app)` — FastAPI treated `app` as a required query param,
    # so the probe 422'd. Take the app off the Request instead.
    app_state = request.app.state
    try:
        # Test Neo4j
        async with app_state.neo4j_driver.session() as session:
            await session.run("RETURN 1")

        # Test Redis
        await app_state.redis_client.ping()

        return {
            "status": "healthy",
            "service": "knowledge-graph",
            "port": 8003,
            "neo4j": "connected",
            "redis": "connected",
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "knowledge-graph",
            "port": 8003,
            "error": str(e),
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "knowledge_graph_main:app",
        host="0.0.0.0",
        port=8003,
        reload=config.DEBUG,
        log_level="info",
    )
