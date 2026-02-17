"""
Vector database API endpoints
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from src.core.database import get_db
from src.core.dependencies import get_current_user
from src.models.user import User
from src.models.vector import (
    BatchEmbeddingRequest,
    BatchEmbeddingResponse,
    CollectionConfig,
    EmbeddingRequest,
    EmbeddingResponse,
    VectorCollectionType,
    VectorHealthStatus,
    VectorOperationResult,
    VectorSearchRequest,
    VectorSearchResponse,
)
from src.services.embedding.embedding_service import embedding_service
from src.services.search.vector_search_service import vector_search_service
from src.services.search.vector_service import vector_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vectors", tags=["vectors"])


@router.post("/embeddings", response_model=EmbeddingResponse)
async def create_embedding(
    request: EmbeddingRequest, current_user: User = Depends(get_current_user)
):
    """Generate embedding for a single text"""
    try:
        result = embedding_service.generate_embedding(request)
        return result
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/embeddings/batch", response_model=BatchEmbeddingResponse)
async def create_batch_embeddings(
    request: BatchEmbeddingRequest, current_user: User = Depends(get_current_user)
):
    """Generate embeddings for multiple texts"""
    try:
        result = embedding_service.generate_batch_embeddings(request)
        return result
    except Exception as e:
        logger.error(f"Error generating batch embeddings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search/documents", response_model=VectorSearchResponse)
async def search_documents(
    query: str,
    organization_id: str,
    limit: int = Query(default=10, ge=1, le=100),
    score_threshold: float = Query(default=0.7, ge=0.0, le=1.0),
    filters: Optional[Dict[str, Any]] = None,
    current_user: User = Depends(get_current_user),
):
    """Search for similar documents"""
    try:
        result = vector_search_service.search_documents(
            query=query,
            organization_id=organization_id,
            limit=limit,
            score_threshold=score_threshold,
            filters=filters,
        )
        return result
    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search/entities", response_model=VectorSearchResponse)
async def search_entities(
    query: str,
    organization_id: str,
    entity_type: Optional[str] = None,
    limit: int = Query(default=10, ge=1, le=100),
    score_threshold: float = Query(default=0.7, ge=0.0, le=1.0),
    current_user: User = Depends(get_current_user),
):
    """Search for similar entities"""
    try:
        result = vector_search_service.search_entities(
            query=query,
            organization_id=organization_id,
            entity_type=entity_type,
            limit=limit,
            score_threshold=score_threshold,
        )
        return result
    except Exception as e:
        logger.error(f"Error searching entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections", response_model=List[Dict[str, Any]])
async def list_collections(current_user: User = Depends(get_current_user)):
    """List all vector collections"""
    try:
        collections = vector_service.client.get_collections()
        return [
            {
                "name": coll.name,
                "vectors_count": vector_service.get_collection_stats(
                    VectorCollectionType(coll.name)
                ).vectors_count
                if vector_service.get_collection_stats(VectorCollectionType(coll.name))
                else 0,
            }
            for coll in collections.collections
        ]
    except Exception as e:
        logger.error(f"Error listing collections: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/collections", response_model=VectorOperationResult)
async def create_collection(
    config: CollectionConfig, current_user: User = Depends(get_current_user)
):
    """Create a new vector collection"""
    try:
        # Only admins can create collections
        if current_user.role.value != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")

        result = vector_service.create_collection(config)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating collection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections/{collection_name}/stats")
async def get_collection_stats(
    collection_name: str, current_user: User = Depends(get_current_user)
):
    """Get statistics for a collection"""
    try:
        # Validate collection type
        try:
            collection_type = VectorCollectionType(collection_name)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid collection name")

        stats = vector_service.get_collection_stats(collection_type)
        if not stats:
            raise HTTPException(status_code=404, detail="Collection not found")

        return stats.dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting collection stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/collections/{collection_name}", response_model=VectorOperationResult)
async def delete_collection(
    collection_name: str, current_user: User = Depends(get_current_user)
):
    """Delete a collection"""
    try:
        # Only admins can delete collections
        if current_user.role.value != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")

        # Validate collection type
        try:
            collection_type = VectorCollectionType(collection_name)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid collection name")

        result = vector_service.delete_collection(collection_type)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting collection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/collections/{collection_name}/clear", response_model=VectorOperationResult
)
async def clear_collection(
    collection_name: str, current_user: User = Depends(get_current_user)
):
    """Clear all vectors from a collection"""
    try:
        # Only admins can clear collections
        if current_user.role.value != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")

        # Validate collection type
        try:
            collection_type = VectorCollectionType(collection_name)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid collection name")

        result = vector_service.clear_collection(collection_type)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing collection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=VectorHealthStatus)
async def get_vector_health(current_user: User = Depends(get_current_user)):
    """Get vector database health status"""
    try:
        health_status = vector_service.get_health_status()
        return health_status
    except Exception as e:
        logger.error(f"Error getting vector health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model/info")
async def get_embedding_model_info(current_user: User = Depends(get_current_user)):
    """Get information about the embedding model"""
    try:
        info = vector_search_service.get_embedding_model_info()
        return info
    except Exception as e:
        logger.error(f"Error getting model info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/model/test-quality")
async def test_embedding_quality(
    test_texts: List[str], current_user: User = Depends(get_current_user)
):
    """Test embedding quality with sample texts"""
    try:
        if not test_texts:
            raise HTTPException(status_code=400, detail="No test texts provided")

        if len(test_texts) > 10:
            raise HTTPException(status_code=400, detail="Maximum 10 test texts allowed")

        result = embedding_service.test_embedding_quality(test_texts)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing embedding quality: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/index/document", response_model=VectorOperationResult)
async def index_document(
    document_id: str,
    text: str,
    organization_id: str,
    content_type: str = "text",
    source_type: str = "document",
    chunk_size: int = Query(default=500, ge=100, le=2000),
    overlap: int = Query(default=50, ge=0, le=200),
    current_user: User = Depends(get_current_user),
):
    """Index a document in the vector database"""
    try:
        # Validate user has access to the organization
        if (
            current_user.organization_id != organization_id
            and current_user.role.value != "admin"
        ):
            raise HTTPException(status_code=403, detail="Access denied")

        result = vector_search_service.index_document(
            document_id=document_id,
            text=text,
            organization_id=organization_id,
            content_type=content_type,
            source_type=source_type,
            chunk_size=chunk_size,
            overlap=overlap,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error indexing document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/index/entity", response_model=VectorOperationResult)
async def index_entity(
    entity_id: str,
    entity_text: str,
    entity_type: str,
    confidence_score: float,
    organization_id: str,
    document_id: Optional[str] = None,
    additional_data: Optional[Dict[str, Any]] = None,
    current_user: User = Depends(get_current_user),
):
    """Index an entity in the vector database"""
    try:
        # Validate user has access to the organization
        if (
            current_user.organization_id != organization_id
            and current_user.role.value != "admin"
        ):
            raise HTTPException(status_code=403, detail="Access denied")

        # Validate confidence score
        if not 0.0 <= confidence_score <= 1.0:
            raise HTTPException(
                status_code=400, detail="Confidence score must be between 0.0 and 1.0"
            )

        result = vector_search_service.index_entity(
            entity_id=entity_id,
            entity_text=entity_text,
            entity_type=entity_type,
            confidence_score=confidence_score,
            organization_id=organization_id,
            document_id=document_id,
            additional_data=additional_data,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error indexing entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{document_id}/vectors", response_model=VectorOperationResult)
async def delete_document_vectors(
    document_id: str, current_user: User = Depends(get_current_user)
):
    """Delete all vectors associated with a document"""
    try:
        result = vector_search_service.delete_document_vectors(document_id)
        return result
    except Exception as e:
        logger.error(f"Error deleting document vectors: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/entities/{entity_id}/vectors", response_model=VectorOperationResult)
async def delete_entity_vectors(
    entity_id: str, current_user: User = Depends(get_current_user)
):
    """Delete entity vectors"""
    try:
        result = vector_search_service.delete_entity_vectors(entity_id)
        return result
    except Exception as e:
        logger.error(f"Error deleting entity vectors: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reindex/organization/{organization_id}")
async def reindex_organization_content(
    organization_id: str,
    batch_size: int = Query(default=100, ge=10, le=1000),
    arxiv_only: bool = Query(default=False),
    dry_run: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
):
    """Reindex all content for an organization"""
    try:
        # Only admins can reindex organizations
        if current_user.role.value != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")

        result = vector_search_service.reindex_all_content(
            organization_id=organization_id,
            batch_size=batch_size,
            arxiv_only=arxiv_only,
            dry_run=dry_run,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reindexing organization content: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/documents/{document_id}/reindex", response_model=VectorOperationResult)
async def update_document_index(
    document_id: str,
    text: str,
    organization_id: str,
    content_type: str = "text",
    current_user: User = Depends(get_current_user),
):
    """Update document index by deleting old vectors and re-indexing"""
    try:
        # Validate user has access to the organization
        if (
            current_user.organization_id != organization_id
            and current_user.role.value != "admin"
        ):
            raise HTTPException(status_code=403, detail="Access denied")

        result = vector_search_service.update_document_index(
            document_id=document_id,
            text=text,
            organization_id=organization_id,
            content_type=content_type,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating document index: {e}")
        raise HTTPException(status_code=500, detail=str(e))
