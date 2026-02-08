"""
Vector database service using Qdrant
"""

import time
import logging
import json
from typing import List, Dict, Any, Optional, Union
from uuid import uuid4
from datetime import datetime
import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    SearchParams,
    OptimizersConfigDiff,
    CreateCollection,
    CollectionInfo,
    CollectionStatus,
    RecommendRequest,
    Range
)

from src.core.config import settings
from src.core.circuit_breaker import get_circuit_breaker, ServiceUnavailableError
from src.models.vector import (
    VectorCollectionType,
    VectorSearchRequest,
    VectorSearchResponse,
    VectorSearchResult,
    VectorEntry,
    VectorMetadata,
    CollectionConfig,
    CollectionStats,
    VectorOperationResult,
    VectorHealthStatus
)

logger = logging.getLogger(__name__)


class VectorService:
    """Service for vector database operations using Qdrant"""

    def __init__(self):
        self.client = None
        self.url = settings.QDRANT_URL
        self.api_key = settings.QDRANT_API_KEY
        self._connect()

    def _connect(self):
        """Connect to Qdrant database"""
        try:
            logger.info(f"Connecting to Qdrant at {self.url}")
            self.client = QdrantClient(
                url=self.url,
                api_key=self.api_key,
                timeout=30
            )

            # Test connection
            collections = self.client.get_collections()
            logger.info(f"Connected to Qdrant. Found {len(collections.collections)} collections")

        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {e}")
            raise

    def create_collection(self, config: CollectionConfig) -> VectorOperationResult:
        """Create a new vector collection"""
        start_time = time.time()

        try:
            # Check if collection already exists
            try:
                existing = self.client.get_collection(config.name)
                logger.info(f"Collection {config.name} already exists")
                return VectorOperationResult(
                    success=True,
                    message=f"Collection {config.name} already exists",
                    processing_time=time.time() - start_time
                )
            except (ValueError, KeyError, Exception) as e:
                # Collection doesn't exist, proceed with creation
                logger.debug(f"Collection {config.name} not found, creating: {e}")

            # Configure HNSW parameters for better performance
            hnsw_config = {
                "m": 32,  # Number of neighbors (increased from 16 for better recall)
                "ef_construct": 200,  # Size of dynamic candidate list (increased from 100)
                "full_scan_threshold": 20000,  # Increased for larger datasets
                "max_indexing_threads": 4,
                "on_disk": config.on_disk
            }

            # Merge with provided config
            if config.hnsw_config:
                hnsw_config.update(config.hnsw_config)

            # Create collection
            self.client.create_collection(
                collection_name=config.name,
                vectors_config=VectorParams(
                    size=config.vector_size,
                    distance=getattr(Distance, config.distance.upper()),
                    on_disk=config.on_disk,
                    hnsw_config=hnsw_config
                )
            )

            # Configure quantization if provided
            if config.quantization_config:
                self.client.update_collection(
                    collection_name=config.name,
                    optimizer_config=OptimizersConfigDiff(
                        default_indexing_algorithm="hnsw",
                        hnsw_config=hnsw_config,
                        quantization_config=config.quantization_config
                    )
                )

            processing_time = time.time() - start_time
            logger.info(f"Collection {config.name} created successfully")

            return VectorOperationResult(
                success=True,
                message=f"Collection {config.name} created successfully",
                processing_time=processing_time
            )

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error creating collection {config.name}: {e}")
            return VectorOperationResult(
                success=False,
                message=f"Failed to create collection {config.name}",
                error=str(e),
                processing_time=processing_time
            )

    def ensure_collection_exists(self, collection_type: VectorCollectionType, vector_size: int = 1536):
        """Ensure a collection exists, create if necessary"""
        collection_name = collection_type.value

        try:
            self.client.get_collection(collection_name)
            logger.debug(f"Collection {collection_name} already exists")
        except (ValueError, KeyError, Exception):
            # Create collection with improved config for better recall
            config = CollectionConfig(
                name=collection_name,
                vector_size=vector_size,
                distance="Cosine",
                on_disk=True,
                hnsw_config={
                    "m": 32,  # Increased from 16 for better recall
                    "ef_construct": 200,  # Increased from 100 for better index quality
                    "full_scan_threshold": 20000  # Increased for larger datasets
                }
            )
            result = self.create_collection(config)
            if not result.success:
                raise Exception(f"Failed to create collection: {result.error}")

    def insert_vectors(self, collection_type: VectorCollectionType, vectors: List[VectorEntry]) -> VectorOperationResult:
        """Insert vectors into collection"""
        start_time = time.time()

        try:
            # Ensure collection exists
            if vectors:
                self.ensure_collection_exists(collection_type, len(vectors[0].vector))

            # Prepare points for Qdrant
            points = []
            for vector_entry in vectors:
                point = PointStruct(
                    id=vector_entry.id,
                    vector=vector_entry.vector,
                    payload={
                        "text": vector_entry.text,
                        "metadata": json.loads(vector_entry.metadata.json()) if hasattr(vector_entry.metadata, 'json') else vector_entry.metadata.dict(),
                        "content_type": vector_entry.metadata.content_type,
                        "source_type": vector_entry.metadata.source_type,
                        "document_id": vector_entry.metadata.document_id,
                        "organization_id": vector_entry.metadata.organization_id,
                        "timestamp": vector_entry.metadata.timestamp.isoformat()
                    }
                )
                points.append(point)

            collection_name = collection_type.value

            # Insert in batches for better performance
            batch_size = 100
            total_batches = (len(points) + batch_size - 1) // batch_size

            for i in range(0, len(points), batch_size):
                batch = points[i:i + batch_size]
                self.client.upsert(
                    collection_name=collection_name,
                    points=batch
                )

            processing_time = time.time() - start_time
            logger.info(f"Inserted {len(vectors)} vectors into {collection_name}")

            return VectorOperationResult(
                success=True,
                message=f"Successfully inserted {len(vectors)} vectors",
                processing_time=processing_time
            )

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error inserting vectors into {collection_type.value}: {e}")
            return VectorOperationResult(
                success=False,
                message=f"Failed to insert vectors",
                error=str(e),
                processing_time=processing_time
            )

    def search_vectors(self, request: VectorSearchRequest, query_vector: List[float]) -> VectorSearchResponse:
        """Search for similar vectors with circuit breaker protection"""
        start_time = time.time()

        # Check circuit breaker before making Qdrant call
        breaker = get_circuit_breaker("qdrant")
        if breaker and not breaker.can_execute():
            logger.warning("Qdrant circuit breaker is open - returning empty results")
            return VectorSearchResponse(
                results=[],
                total_found=0,
                search_time=0.0,
                query=request.query,
                collection=request.collection
            )

        try:
            collection_name = request.collection.value

            # Build filter
            query_filter = None
            filter_conditions = []

            if request.organization_id:
                filter_conditions.append(
                    FieldCondition(
                        key="organization_id",
                        match=MatchValue(value=request.organization_id)
                    )
                )

            # Add custom filters
            if request.filters:
                for key, value in request.filters.items():
                    filter_conditions.append(
                        FieldCondition(
                            key=key,
                            match=MatchValue(value=value)
                        )
                )
            
            if filter_conditions:
                query_filter = Filter(must=filter_conditions)

            # Use requests directly to avoid client version mismatch (Client v1.16+ vs Server v1.7.0)
            url = f"{settings.QDRANT_URL}/collections/{collection_name}/points/search"
            headers = {"Content-Type": "application/json"}
            if settings.QDRANT_API_KEY:
                headers["api-key"] = settings.QDRANT_API_KEY
                
            payload = {
                "vector": query_vector,
                "limit": request.limit,
                "with_payload": True,
                "with_vector": False,
                "score_threshold": request.score_threshold
            }
            
            if filter_conditions:
                # Convert Filter model to dict
                # model_dump for Pydantic v2, dict for v1
                if hasattr(query_filter, 'model_dump'):
                    payload["filter"] = query_filter.model_dump()
                else:
                    payload["filter"] = query_filter.dict()
            
            # Use async httpx instead of blocking requests
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=10.0)
                response.raise_for_status()
                search_result_json = response.json()
            search_results = search_result_json.get("result", [])

            # Convert to internal VectorSearchResult objects
            vector_results = []
            for hit in search_results:
                payload_data = hit.get("payload", {})
                metadata = VectorMetadata(
                    document_id=payload_data.get("document_id"),
                    organization_id=payload_data.get("organization_id") or "",
                    content_type=payload_data.get("content_type", "text"),
                    source_type=payload_data.get("source_type", "document"),
                    chunk_index=payload_data.get("chunk_index"),
                    timestamp=payload_data.get("timestamp") or datetime.utcnow(),
                    additional_data=payload_data
                )
                
                result_entry = VectorSearchResult(
                    id=str(hit.get("id")),
                    score=hit.get("score"),
                    text=payload_data.get("text", ""),
                    metadata=metadata
                )
                vector_results.append(result_entry)

            processing_time = time.time() - start_time
            logger.info(f"Found {len(vector_results)} results in {collection_name}")

            # Record circuit breaker success
            if breaker:
                breaker.record_success()

            return VectorSearchResponse(
                results=vector_results,
                total_found=len(vector_results),
                search_time=processing_time,
                query=request.query,
                collection=request.collection
            )

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error searching in {request.collection.value}: {e}")

            # Record circuit breaker failure
            if breaker:
                breaker.record_failure(e)

            # Return empty result on error
            return VectorSearchResponse(
                results=[],
                total_found=0,
                search_time=processing_time,
                query=request.query,
                collection=request.collection
            )

    def delete_vectors(self, collection_type: VectorCollectionType, vector_ids: List[str]) -> VectorOperationResult:
        """Delete vectors from collection"""
        start_time = time.time()

        try:
            collection_name = collection_type.value

            # Delete vectors
            self.client.delete(
                collection_name=collection_name,
                points_selector=vector_ids
            )

            processing_time = time.time() - start_time
            logger.info(f"Deleted {len(vector_ids)} vectors from {collection_name}")

            return VectorOperationResult(
                success=True,
                message=f"Successfully deleted {len(vector_ids)} vectors",
                processing_time=processing_time
            )

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error deleting vectors from {collection_type.value}: {e}")
            return VectorOperationResult(
                success=False,
                message=f"Failed to delete vectors",
                error=str(e),
                processing_time=processing_time
            )

    def get_collection_stats(self, collection_type: VectorCollectionType) -> Optional[CollectionStats]:
        """Get statistics for a collection"""
        try:
            collection_name = collection_type.value
            collection_info = self.client.get_collection(collection_name)

            return CollectionStats(
                name=collection_name,
                vectors_count=collection_info.vectors_count,
                indexed_vectors_count=collection_info.indexed_vectors_count,
                points_count=collection_info.points_count,
                segments_count=collection_info.segments_count,
                disk_data_size=collection_info.config.params.vectors.on_disk or 0,
                ram_data_size=collection_info.points_count * 384,  # Approximate
                config=collection_info.config.dict()
            )

        except Exception as e:
            logger.error(f"Error getting stats for {collection_type.value}: {e}")
            return None

    def get_health_status(self) -> VectorHealthStatus:
        """Get overall health status of vector database"""
        try:
            # Test basic connection
            collections = self.client.get_collections()

            # Get stats for all collections
            total_vectors = 0
            disk_usage = 0
            ram_usage = 0

            for collection_info in collections.collections:
                stats = self.get_collection_stats(VectorCollectionType(collection_info.name))
                if stats:
                    total_vectors += stats.vectors_count
                    disk_usage += stats.disk_data_size
                    ram_usage += stats.ram_data_size

            return VectorHealthStatus(
                status="healthy",
                collections_count=len(collections.collections),
                total_vectors=total_vectors,
                disk_usage_mb=disk_usage / (1024 * 1024),
                ram_usage_mb=ram_usage / (1024 * 1024),
                uptime_seconds=0,  # Not available in Qdrant client
                version="1.7.0"  # From docker image
            )

        except Exception as e:
            logger.error(f"Error getting health status: {e}")
            return VectorHealthStatus(
                status="unhealthy",
                collections_count=0,
                total_vectors=0,
                disk_usage_mb=0,
                ram_usage_mb=0,
                uptime_seconds=0,
                version="unknown"
            )

    def clear_collection(self, collection_type: VectorCollectionType) -> VectorOperationResult:
        """Clear all vectors from a collection"""
        start_time = time.time()

        try:
            collection_name = collection_type.value

            # Delete and recreate collection
            try:
                collection_info = self.client.get_collection(collection_name)
                vector_size = collection_info.config.params.vectors.size

                # Delete collection
                self.client.delete_collection(collection_name)

                # Recreate with same config
                self.ensure_collection_exists(collection_type, vector_size)

            except Exception as e:
                logger.warning(f"Collection {collection_name} may not exist: {e}")

            processing_time = time.time() - start_time
            logger.info(f"Cleared collection {collection_name}")

            return VectorOperationResult(
                success=True,
                message=f"Successfully cleared collection {collection_name}",
                processing_time=processing_time
            )

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error clearing collection {collection_type.value}: {e}")
            return VectorOperationResult(
                success=False,
                message=f"Failed to clear collection",
                error=str(e),
                processing_time=processing_time
            )

    def delete_collection(self, collection_type: Union[VectorCollectionType, str]) -> VectorOperationResult:
        """Delete a collection entirely"""
        start_time = time.time()

        try:
            collection_name = collection_type.value if hasattr(collection_type, "value") else str(collection_type)

            # Delete collection
            self.client.delete_collection(collection_name)

            processing_time = time.time() - start_time
            logger.info(f"Deleted collection {collection_name}")

            return VectorOperationResult(
                success=True,
                message=f"Successfully deleted collection {collection_name}",
                processing_time=processing_time
            )

        except Exception as e:
            processing_time = time.time() - start_time
            collection_name_err = collection_type.value if hasattr(collection_type, "value") else str(collection_type)
            logger.error(f"Error deleting collection {collection_name_err}: {e}")
            return VectorOperationResult(
                success=False,
                message=f"Failed to delete collection",
                error=str(e),
                processing_time=processing_time
            )


# Singleton instance
vector_service = VectorService()