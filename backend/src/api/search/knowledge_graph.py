"""
Knowledge Graph API endpoints
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from neo4j.exceptions import ServiceUnavailable as Neo4jServiceUnavailable
from pydantic import BaseModel, Field

from src.core.circuit_breaker import ServiceUnavailableError as CircuitBreakerError
from src.core.database import get_db_sync
from src.core.dependencies import get_current_user
from src.models.document import Document
from src.models.graph import (
    BatchEntityRequest,
    BatchEntityResponse,
    CreateEntityRequest,
    CreateRelationshipRequest,
    Entity,
    EntityResponse,
    EntityType,
    ExtractionMethod,
    GraphAnalytics,
    GraphHealthStatus,
    GraphPath,
    GraphSearchRequest,
    GraphSearchResponse,
    GraphVisualizationData,
    GraphVisualizationEdge,
    GraphVisualizationNode,
    PaginatedEntitiesResponse,
    Relationship,
    RelationshipResponse,
    RelationshipType,
    UpdateEntityRequest,
)
from src.models.user import User, UserRole
from src.models.processing import JobPriority, JobStatus, JobType, ProcessingJob
from src.services.knowledge_graph.knowledge_graph_service import knowledge_graph_service
from src.services.processing.entity_extraction_service import EntityExtractionService
from src.tasks.processing_tasks import kg_extract_entities_job, kg_merge_entities_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge-graph", tags=["knowledge-graph"])


def _is_neo4j_unavailable_error(error: Exception) -> bool:
    if isinstance(error, (CircuitBreakerError, Neo4jServiceUnavailable)):
        return True
    message = str(error).lower()
    return "circuit breaker is open" in message or "service unavailable" in message


class MergeJobEntityRef(BaseModel):
    id: str
    name: str


class MergeJobGroupRequest(BaseModel):
    entities: List[MergeJobEntityRef] = Field(default_factory=list)
    suggested_primary: str


class CreateMergeJobRequest(BaseModel):
    groups: List[MergeJobGroupRequest] = Field(default_factory=list)


class CreateExtractionJobRequest(BaseModel):
    document_ids: List[str] = Field(default_factory=list)


# Entity Management Endpoints
@router.post("/entities", response_model=EntityResponse)
async def create_entity(
    request: CreateEntityRequest, current_user: User = Depends(get_current_user)
):
    """Create a new entity in the knowledge graph"""
    try:
        entity = knowledge_graph_service.create_entity(request)
        return entity
    except Exception as e:
        logger.error(f"Error creating entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entities/{entity_id}", response_model=EntityResponse)
async def get_entity(entity_id: str, current_user: User = Depends(get_current_user)):
    """Get an entity by ID"""
    entity = knowledge_graph_service.get_entity(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.put("/entities/{entity_id}", response_model=EntityResponse)
async def update_entity(
    entity_id: str,
    request: UpdateEntityRequest,
    current_user: User = Depends(get_current_user),
):
    """Update an existing entity"""
    entity = knowledge_graph_service.update_entity(entity_id, request)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.delete("/entities/{entity_id}")
async def delete_entity(entity_id: str, current_user: User = Depends(get_current_user)):
    """Delete an entity and all its relationships"""
    success = knowledge_graph_service.delete_entity(entity_id)
    if not success:
        raise HTTPException(status_code=404, detail="Entity not found")
    return {"message": "Entity deleted successfully"}


@router.get("/entities", response_model=PaginatedEntitiesResponse)
async def get_all_entities(
    limit: int = Query(
        default=100, ge=1, le=1000, description="Maximum results to return"
    ),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
    entity_types: Optional[List[EntityType]] = Query(
        None, description="Filter by entity types"
    ),
    current_user: User = Depends(get_current_user),
):
    """Get all entities with pagination and optional filtering"""
    try:
        entities = knowledge_graph_service.get_all_entities(limit, offset, entity_types)
        total = knowledge_graph_service.count_entities(entity_types)
        return PaginatedEntitiesResponse(
            entities=entities,
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + len(entities)) < total,
        )
    except Exception as e:
        logger.error(f"Error getting entities: {e}")
        if _is_neo4j_unavailable_error(e):
            raise HTTPException(status_code=503, detail=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entities/search", response_model=List[EntityResponse])
async def search_entities(
    query: str = Query(..., description="Search query"),
    entity_types: Optional[List[EntityType]] = Query(
        None, description="Filter by entity types"
    ),
    limit: int = Query(default=50, ge=1, le=200, description="Maximum results"),
    current_user: User = Depends(get_current_user),
):
    """Search for entities by name or properties"""
    try:
        entities = knowledge_graph_service.search_entities(query, entity_types, limit)
        return entities
    except Exception as e:
        logger.error(f"Error searching entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/entities/{entity_id}/relationships", response_model=List[RelationshipResponse]
)
async def get_entity_relationships(
    entity_id: str,
    relationship_types: Optional[List[RelationshipType]] = Query(
        None, description="Filter by relationship types"
    ),
    current_user: User = Depends(get_current_user),
):
    """Get all relationships for an entity"""
    try:
        relationships = knowledge_graph_service.get_relationships(
            entity_id, relationship_types
        )
        return relationships
    except Exception as e:
        logger.error(f"Error getting relationships: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entities/{entity_id}/related", response_model=List[EntityResponse])
async def get_related_entities(
    entity_id: str,
    max_depth: int = Query(
        default=2, ge=1, le=5, description="Maximum traversal depth"
    ),
    min_strength: float = Query(
        default=0.1, ge=0.0, le=1.0, description="Minimum relationship strength"
    ),
    limit: int = Query(default=50, ge=1, le=200, description="Maximum results"),
    current_user: User = Depends(get_current_user),
):
    """Find entities related to a given entity"""
    try:
        entities = knowledge_graph_service.find_related_entities(
            entity_id, max_depth, min_strength, limit
        )
        return entities
    except Exception as e:
        logger.error(f"Error finding related entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entities/{entity_id}/neighborhood")
async def get_entity_neighborhood(
    entity_id: str,
    max_depth: int = Query(
        default=2, ge=1, le=5, description="Maximum traversal depth"
    ),
    min_strength: float = Query(
        default=0.1, ge=0.0, le=1.0, description="Minimum relationship strength"
    ),
    limit: int = Query(default=50, ge=1, le=200, description="Maximum results"),
    current_user: User = Depends(get_current_user),
):
    """Get neighborhood entities and relationships in a single call"""
    try:
        data = knowledge_graph_service.get_neighborhood(
            entity_id, max_depth, min_strength, limit
        )
        return data
    except Exception as e:
        logger.error(f"Error getting neighborhood: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Relationship Management Endpoints
@router.get("/relationships", response_model=List[RelationshipResponse])
async def get_all_relationships(
    limit: int = Query(
        default=500, ge=1, le=2000, description="Maximum results to return"
    ),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
    relationship_types: Optional[List[RelationshipType]] = Query(
        None, description="Filter by relationship types"
    ),
    current_user: User = Depends(get_current_user),
):
    """Get all relationships with pagination and optional filtering"""
    try:
        relationships = knowledge_graph_service.get_all_relationships(
            limit, offset, relationship_types
        )
        return relationships
    except Exception as e:
        logger.error(f"Error getting relationships: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/relationships", response_model=RelationshipResponse)
async def create_relationship(
    request: CreateRelationshipRequest, current_user: User = Depends(get_current_user)
):
    """Create a new relationship between entities"""
    try:
        relationship = knowledge_graph_service.create_relationship(request)
        return relationship
    except Exception as e:
        logger.error(f"Error creating relationship: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/relationships/{relationship_id}", response_model=RelationshipResponse)
async def get_relationship(
    relationship_id: str, current_user: User = Depends(get_current_user)
):
    """Get a relationship by ID"""
    try:
        relationship = knowledge_graph_service.get_relationship(relationship_id)
        if not relationship:
            raise HTTPException(
                status_code=404, detail=f"Relationship {relationship_id} not found"
            )
        return relationship
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting relationship {relationship_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve relationship: {str(e)}"
        )


@router.delete("/relationships/{relationship_id}")
async def delete_relationship(
    relationship_id: str, current_user: User = Depends(get_current_user)
):
    """Delete a relationship"""
    try:
        success = knowledge_graph_service.delete_relationship(relationship_id)
        if not success:
            raise HTTPException(status_code=404, detail="Relationship not found")
        return {"message": "Relationship deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting relationship: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Graph Search and Traversal Endpoints
@router.post("/search", response_model=GraphSearchResponse)
async def search_graph(
    request: GraphSearchRequest, current_user: User = Depends(get_current_user)
):
    """Perform a comprehensive graph search"""
    try:
        import time

        start_time = time.time()

        # Search entities
        entities = knowledge_graph_service.search_entities(
            request.query, request.entity_types, request.max_results
        )

        # Find relationships for found entities
        relationships = []
        for entity in entities:
            entity_relationships = knowledge_graph_service.get_relationships(
                entity.id, request.relationship_types
            )
            relationships.extend(entity_relationships)

        # Find paths between entities
        paths = []
        if len(entities) >= 2:
            for i in range(len(entities) - 1):
                for j in range(i + 1, min(len(entities), i + 5)):  # Limit path finding
                    entity_paths = knowledge_graph_service.find_paths(
                        entities[i].id,
                        entities[j].id,
                        request.max_depth,
                        request.min_strength,
                    )
                    paths.extend(entity_paths)

        search_time = time.time() - start_time

        return GraphSearchResponse(
            query=request.query,
            entities=entities,
            relationships=relationships,
            paths=paths,
            total_entities=len(entities),
            total_relationships=len(relationships),
            total_paths=len(paths),
            search_time=search_time,
        )
    except Exception as e:
        logger.error(f"Error performing graph search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/paths/{source_id}/{target_id}", response_model=List[GraphPath])
async def find_paths(
    source_id: str,
    target_id: str,
    max_depth: int = Query(default=3, ge=1, le=5, description="Maximum path length"),
    min_strength: float = Query(
        default=0.1, ge=0.0, le=1.0, description="Minimum relationship strength"
    ),
    current_user: User = Depends(get_current_user),
):
    """Find paths between two entities"""
    try:
        paths = knowledge_graph_service.find_paths(
            source_id, target_id, max_depth, min_strength
        )
        return paths
    except Exception as e:
        logger.error(f"Error finding paths: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Batch Operations Endpoints
@router.post("/batch", response_model=BatchEntityResponse)
async def batch_create_entities(
    request: BatchEntityRequest, current_user: User = Depends(get_current_user)
):
    """Create multiple entities and relationships in a batch"""
    try:
        result = knowledge_graph_service.create_entities_batch(request)
        return result
    except Exception as e:
        logger.error(f"Error in batch processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/merge-jobs", status_code=status.HTTP_202_ACCEPTED)
async def create_merge_job(
    request: CreateMergeJobRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db_sync),
):
    """Queue a background merge job for selected duplicate groups."""
    if not request.groups:
        raise HTTPException(status_code=400, detail="At least one merge group is required")

    # Validate that all entity IDs belong to documents in the caller's organization.
    entity_ids = set()
    for group in request.groups:
        if group.suggested_primary:
            entity_ids.add(group.suggested_primary)
        for entity in group.entities:
            if entity.id:
                entity_ids.add(entity.id)

    if not entity_ids:
        raise HTTPException(status_code=400, detail="At least one entity ID is required")

    entity_source_docs: Dict[str, str] = {}
    for entity_id in entity_ids:
        entity = knowledge_graph_service.get_entity(entity_id)
        if not entity:
            raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")

        source_document_id = getattr(entity, "source_document_id", None)
        if not source_document_id:
            raise HTTPException(
                status_code=422,
                detail=f"Entity {entity_id} has no source document and cannot be merged safely",
            )
        entity_source_docs[entity_id] = str(source_document_id)

    source_doc_ids = sorted(set(entity_source_docs.values()))
    docs = (
        db.query(Document)
        .filter(
            Document.id.in_(source_doc_ids),
            Document.organization_id == current_user.organization_id,
            Document.is_deleted == False,
        )
        .all()
    )
    found_doc_ids = {str(doc.id) for doc in docs}
    unauthorized_entities = [
        entity_id
        for entity_id, doc_id in entity_source_docs.items()
        if doc_id not in found_doc_ids
    ]
    if unauthorized_entities:
        raise HTTPException(
            status_code=403,
            detail=(
                "One or more entities are outside your organization: "
                f"{unauthorized_entities}"
            ),
        )

    job = ProcessingJob(
        job_type=JobType.BATCH_PROCESSING,
        status=JobStatus.PENDING,
        priority=JobPriority.NORMAL,
        organization_id=current_user.organization_id,
        created_by_user_id=current_user.id,
        parameters={
            "operation": "entity_merge",
            "groups": [group.dict() for group in request.groups],
        },
        total_steps=len(request.groups),
        queue_name="graph_processing",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    task = kg_merge_entities_job.apply_async(
        args=[str(job.id)],
        queue="graph_processing",
    )
    job.celery_task_id = task.id
    job.queue_job(queue_name="graph_processing")
    db.commit()

    return {"job_id": str(job.id), "status": job.status.value}


@router.post("/extraction-jobs", status_code=status.HTTP_202_ACCEPTED)
async def create_extraction_job(
    request: CreateExtractionJobRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db_sync),
):
    """Queue a background entity extraction job for one or more documents."""
    if not request.document_ids:
        raise HTTPException(status_code=400, detail="At least one document ID is required")

    # Ensure all requested documents belong to the current organization
    docs = (
        db.query(Document)
        .filter(
            Document.id.in_(request.document_ids),
            Document.organization_id == current_user.organization_id,
            Document.is_deleted == False,
        )
        .all()
    )
    found_ids = {str(doc.id) for doc in docs}
    missing = [doc_id for doc_id in request.document_ids if str(doc_id) not in found_ids]
    if missing:
        raise HTTPException(status_code=404, detail=f"Documents not found: {missing}")

    job = ProcessingJob(
        job_type=JobType.ENTITY_EXTRACTION,
        status=JobStatus.PENDING,
        priority=JobPriority.NORMAL,
        organization_id=current_user.organization_id,
        created_by_user_id=current_user.id,
        parameters={
            "operation": "document_entity_extraction",
            "document_ids": [str(doc_id) for doc_id in request.document_ids],
        },
        total_steps=len(request.document_ids),
        queue_name="entity_processing",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    task = kg_extract_entities_job.apply_async(
        args=[str(job.id)],
        queue="entity_processing",
    )
    job.celery_task_id = task.id
    job.queue_job(queue_name="entity_processing")
    db.commit()

    return {"job_id": str(job.id), "status": job.status.value}


# Document Integration Endpoints
@router.post("/documents/{document_id}/extract-entities", response_model=Dict[str, Any])
async def extract_entities_from_document(
    document_id: str, current_user: User = Depends(get_current_user), db=Depends(get_db_sync)
):
    """Extract entities from a document and add them to the knowledge graph"""
    try:
        # Get document from database
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        # Extract entities using entity extraction service
        entity_extractor = EntityExtractionService()
        entities_data = entity_extractor.extract_entities(document.content)

        # Convert extracted entities to CreateEntityRequest objects
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

        result = knowledge_graph_service.create_entities_batch(batch_request)

        return {
            "document_id": document_id,
            "entities_found": len(entities_data),
            "entities_created": len(result.created_entities),
            "errors": len(result.errors),
            "processing_time": result.processing_time,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extracting entities from document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{document_id}/entities", response_model=List[EntityResponse])
async def get_document_entities(
    document_id: str, current_user: User = Depends(get_current_user)
):
    """Get all entities extracted from a specific document"""
    try:
        entities = knowledge_graph_service.search_entities(
            query="",  # Empty query to find all
            limit=1000,
        )

        # Filter by source document
        document_entities = [
            entity for entity in entities if entity.source_document_id == document_id
        ]

        return document_entities
    except Exception as e:
        logger.error(f"Error getting document entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Analytics and Statistics Endpoints
@router.get("/analytics", response_model=GraphAnalytics)
async def get_graph_analytics(current_user: User = Depends(get_current_user)):
    """Get comprehensive graph analytics"""
    try:
        analytics = knowledge_graph_service.get_graph_analytics()
        return analytics
    except Exception as e:
        logger.error(f"Error getting graph analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=GraphHealthStatus)
async def get_graph_health(current_user: User = Depends(get_current_user)):
    """Get health status of the graph database"""
    try:
        health = knowledge_graph_service.get_health_status()
        return health
    except Exception as e:
        logger.error(f"Error getting graph health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Visualization Endpoints
@router.get("/visualization/{entity_id}", response_model=GraphVisualizationData)
async def get_entity_neighborhood(
    entity_id: str,
    depth: int = Query(default=2, ge=1, le=3, description="Neighborhood depth"),
    max_nodes: int = Query(
        default=50, ge=1, le=200, description="Maximum nodes to include"
    ),
    current_user: User = Depends(get_current_user),
):
    """Get graph data for visualizing an entity's neighborhood"""
    try:
        # Get the central entity
        central_entity = knowledge_graph_service.get_entity(entity_id)
        if not central_entity:
            raise HTTPException(status_code=404, detail="Entity not found")

        # Get related entities
        related_entities = knowledge_graph_service.find_related_entities(
            entity_id, max_depth=depth, limit=max_nodes - 1
        )

        # Get relationships
        all_entity_ids = [entity_id] + [e.id for e in related_entities]
        relationships = []
        for eid in all_entity_ids:
            rels = knowledge_graph_service.get_relationships(eid)
            relationships.extend(rels)

        # Filter relationships to only include entities in our set
        entity_id_set = set(all_entity_ids)
        filtered_relationships = [
            rel
            for rel in relationships
            if rel.source_entity_id in entity_id_set
            and rel.target_entity_id in entity_id_set
        ]

        # Convert to visualization format
        nodes = []
        edges = []

        # Add central node
        nodes.append(
            GraphVisualizationNode(
                id=central_entity.id,
                label=central_entity.name,
                type=central_entity.entity_type.value,
                properties=central_entity.dict(),
                size=20,
                color="#ff6b6b",  # Central node color
            )
        )

        # Add related nodes
        for entity in related_entities:
            # Choose color based on entity type
            type_colors = {
                "PERSON": "#4ecdc4",
                "ORGANIZATION": "#45b7d1",
                "LOCATION": "#96ceb4",
                "PRODUCT": "#ffeaa7",
                "EVENT": "#dfe6e9",
                "CONCEPT": "#a29bfe",
            }
            color = type_colors.get(entity.entity_type.value, "#74b9ff")

            nodes.append(
                GraphVisualizationNode(
                    id=entity.id,
                    label=entity.name,
                    type=entity.entity_type.value,
                    properties=entity.dict(),
                    size=10 + entity.confidence_score * 10,
                    color=color,
                )
            )

        # Add edges
        for rel in filtered_relationships:
            edges.append(
                GraphVisualizationEdge(
                    id=rel.id,
                    source=rel.source_entity_id,
                    target=rel.target_entity_id,
                    type=rel.relationship_type.value,
                    weight=rel.strength,
                    properties=rel.dict(),
                    width=rel.strength * 5,
                    color="#636e72",
                )
            )

        return GraphVisualizationData(
            nodes=nodes,
            edges=edges,
            layout="force",
            metadata={
                "central_entity_id": entity_id,
                "depth": depth,
                "total_nodes": len(nodes),
                "total_edges": len(edges),
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating visualization data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Entity Type and Relationship Management
@router.get("/entity-types", response_model=List[str])
async def get_entity_types(current_user: User = Depends(get_current_user)):
    """Get all available entity types"""
    return [t.value for t in EntityType]


@router.get("/relationship-types", response_model=List[str])
async def get_relationship_types(current_user: User = Depends(get_current_user)):
    """Get all available relationship types"""
    return [t.value for t in RelationshipType]


# Maintenance Endpoints
@router.post("/maintenance/fix-null-types")
async def fix_null_entity_types(
    current_user: User = Depends(get_current_user),
):
    """
    Fix all entities with NULL type by setting them to 'OTHER'.

    Requires admin privileges.
    """
    # Ensure only admins can perform maintenance operations
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        with knowledge_graph_service.get_session() as session:
            # Count entities with NULL type
            count_result = session.run(
                """
                MATCH (e:Entity)
                WHERE e.type IS NULL OR e.entity_type IS NULL
                RETURN count(e) as count
            """
            )
            count = count_result.single()["count"]

            if count == 0:
                return {"message": "No entities with NULL type found", "updated": 0}

            # Fix entities with NULL type or entity_type properties in one query
            # Using COALESCE to avoid double-counting entities with both NULL
            result = session.run(
                """
                MATCH (e:Entity)
                WHERE e.type IS NULL OR e.entity_type IS NULL
                SET e.type = COALESCE(e.type, 'OTHER'),
                    e.entity_type = COALESCE(e.entity_type, 'OTHER')
                RETURN count(e) as updated
            """
            )
            total_updated = result.single()["updated"]

            logger.info(f"Fixed {total_updated} entities with NULL type")

            return {
                "message": f"Successfully fixed {total_updated} entities with NULL type",
                "updated": total_updated,
            }
    except Exception as e:
        logger.error(f"Error fixing NULL entity types: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Schema Management
@router.post("/schema/reset")
async def reset_graph_schema(
    confirm: bool = Query(..., description="Confirmation to reset schema"),
    current_user: User = Depends(get_current_user),
):
    """Reset the entire graph schema (DESTRUCTIVE OPERATION)"""
    if not confirm:
        raise HTTPException(status_code=400, detail="Confirmation required")

    try:
        with knowledge_graph_service.get_session() as session:
            # Delete all nodes and relationships
            session.run("MATCH (n) DETACH DELETE n")

            # Recreate constraints and indexes
            knowledge_graph_service._ensure_schema()

        return {"message": "Graph schema reset successfully"}
    except Exception as e:
        logger.error(f"Error resetting graph schema: {e}")
        raise HTTPException(status_code=500, detail=str(e))
