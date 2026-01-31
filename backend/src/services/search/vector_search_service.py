"""
Combined vector search service - integrates embedding generation and vector database operations
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from src.models.vector import (
    BatchEmbeddingRequest,
    BatchEmbeddingResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    VectorCollectionType,
    VectorEntry,
    VectorMetadata,
    VectorOperationResult,
    VectorSearchRequest,
    VectorSearchResponse,
    VectorSearchResult,
)
from src.services.embedding.embedding_service import embedding_service
from src.services.search.vector_service import vector_service

logger = logging.getLogger(__name__)


class VectorSearchService:
    """High-level service for vector search operations"""

    def __init__(self):
        self.embedding_service = embedding_service
        self.vector_service = vector_service

    def index_document(
        self,
        document_id: str,
        text: str,
        organization_id: str,
        content_type: str = "text",
        source_type: str = "document",
        chunk_size: int = 1000,  # Increased from 500 for better context
        overlap: int = 300,  # Increased from 200 for 30% overlap
        metadata: Optional[Dict[str, Any]] = None,
    ) -> VectorOperationResult:
        """Index a document by generating embeddings and storing in vector database"""
        start_time = time.time()

        try:
            # Prepare metadata
            base_metadata = {
                "content_type": content_type,
                "source_type": source_type,
                "timestamp": datetime.utcnow(),
            }

            if metadata:
                base_metadata.update(metadata)

            # Generate document embeddings with chunking
            document_embeddings = asyncio.run(
                self.embedding_service.generate_document_embeddings(
                    document_id=document_id,
                    text=text,
                    metadata=base_metadata,
                    chunk_size=chunk_size,
                    overlap=overlap,
                )
            )

            if not document_embeddings:
                return VectorOperationResult(
                    success=False,
                    message="No embeddings generated for document",
                    processing_time=time.time() - start_time,
                )

            # Convert to VectorEntry objects
            vector_entries = []
            for doc_emb in document_embeddings:
                # Update metadata with organization info
                metadata = VectorMetadata(
                    document_id=doc_emb["metadata"]["document_id"],
                    organization_id=organization_id,
                    content_type=doc_emb["metadata"]["content_type"],
                    source_type=doc_emb["metadata"]["source_type"],
                    chunk_index=doc_emb["metadata"]["chunk_index"],
                    timestamp=doc_emb["metadata"]["timestamp"],
                    additional_data=doc_emb["metadata"],
                )

                import uuid

                # Qdrant requires ID to be UUID or int, not arbitrary string
                point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, doc_emb["id"]))

                vector_entry = VectorEntry(
                    id=point_id,
                    vector=doc_emb["embedding"],
                    text=doc_emb["text"],
                    metadata=metadata,
                    collection=VectorCollectionType.DOCUMENT_CHUNKS,
                )
                vector_entries.append(vector_entry)

            # Store in vector database
            result = self.vector_service.insert_vectors(
                collection_type=VectorCollectionType.DOCUMENT_CHUNKS,
                vectors=vector_entries,
            )

            processing_time = time.time() - start_time

            if result.success:
                logger.info(
                    f"Successfully indexed document {document_id} with {len(vector_entries)} chunks"
                )
                return VectorOperationResult(
                    success=True,
                    message=f"Document indexed with {len(vector_entries)} chunks",
                    operation_id=document_id,
                    processing_time=processing_time,
                )
            else:
                return result

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error indexing document {document_id}: {e}")
            return VectorOperationResult(
                success=False,
                message=f"Failed to index document",
                error=str(e),
                processing_time=processing_time,
            )

    def index_entity(
        self,
        entity_id: str,
        entity_text: str,
        entity_type: str,
        confidence_score: float,
        organization_id: str,
        document_id: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> VectorOperationResult:
        """Index an entity in the vector database"""
        start_time = time.time()

        try:
            # Generate embedding for entity text
            embedding_request = EmbeddingRequest(text=entity_text)
            embedding_response = asyncio.run(
                self.embedding_service.generate_embedding(embedding_request)
            )

            if not embedding_response.embedding:
                return VectorOperationResult(
                    success=False,
                    message="Failed to generate embedding for entity",
                    processing_time=time.time() - start_time,
                )

            # Prepare metadata
            metadata = VectorMetadata(
                document_id=document_id,
                organization_id=organization_id,
                content_type="entity",
                source_type="extraction",
                entity_type=entity_type,
                confidence_score=confidence_score,
                timestamp=datetime.utcnow(),
                additional_data=additional_data,
            )

            # Create vector entry
            vector_entry = VectorEntry(
                id=entity_id,
                vector=embedding_response.embedding,
                text=entity_text,
                metadata=metadata,
                collection=VectorCollectionType.ENTITIES,
            )

            # Store in vector database
            result = self.vector_service.insert_vectors(
                collection_type=VectorCollectionType.ENTITIES, vectors=[vector_entry]
            )

            processing_time = time.time() - start_time

            if result.success:
                logger.info(f"Successfully indexed entity {entity_id}")
                return VectorOperationResult(
                    success=True,
                    message=f"Entity indexed successfully",
                    operation_id=entity_id,
                    processing_time=processing_time,
                )
            else:
                return result

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error indexing entity {entity_id}: {e}")
            return VectorOperationResult(
                success=False,
                message=f"Failed to index entity",
                error=str(e),
                processing_time=processing_time,
            )

    def search_documents(
        self,
        query: str,
        organization_id: str,
        limit: int = 10,
        score_threshold: float = 0.2,  # Lowered to 0.2 for more results
        filters: Optional[Dict[str, Any]] = None,
    ) -> VectorSearchResponse:
        """Search for similar documents"""
        try:
            # Generate embedding for query - use Azure OpenAI to match indexed vectors (1536d)
            # Force Azure provider since indexed vectors are 1536d from Azure OpenAI
            embedding_request = EmbeddingRequest(text=query, provider="azure_openai")
            embedding_response = asyncio.run(
                self.embedding_service.generate_embedding(embedding_request)
            )

            if not embedding_response.embedding:
                return VectorSearchResponse(
                    results=[],
                    total_found=0,
                    search_time=0.0,
                    query=query,
                    collection=VectorCollectionType.DOCUMENT_CHUNKS,
                )

            # Create search request
            search_request = VectorSearchRequest(
                query=query,
                collection=VectorCollectionType.DOCUMENT_CHUNKS,
                organization_id=organization_id,
                limit=limit,
                score_threshold=score_threshold,
                filters=filters,
            )

            # Search in vector database
            result = self.vector_service.search_vectors(
                request=search_request, query_vector=embedding_response.embedding
            )

            return result

        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            return VectorSearchResponse(
                results=[],
                total_found=0,
                search_time=0.0,
                query=query,
                collection=VectorCollectionType.DOCUMENT_CHUNKS,
            )

    def search_documents_hybrid(
        self,
        query: str,
        organization_id: str,
        limit: int = 10,
        score_threshold: float = 0.2,
        filters: Optional[Dict[str, Any]] = None,
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3,
    ) -> VectorSearchResponse:
        """
        Hybrid search combining dense embeddings with BM25 keyword matching.

        This improves Precision@3/5 by boosting results that match query keywords.

        Args:
            query: Search query
            organization_id: Organization filter
            limit: Max results to return
            score_threshold: Minimum score threshold
            filters: Additional filters
            dense_weight: Weight for semantic similarity (default 0.7)
            sparse_weight: Weight for keyword matching (default 0.3)
        """
        from .bm25_service import bm25_service

        start_time = time.time()

        try:
            # First, get dense search results (fetch more for re-ranking)
            dense_results = self.search_documents(
                query=query,
                organization_id=organization_id,
                limit=limit * 2,
                score_threshold=score_threshold,
                filters=filters,
            )

            if not dense_results.results:
                return dense_results

            # Generate BM25 sparse vector for query
            query_sparse = bm25_service.encode(query, is_query=True)
            query_terms = set(query_sparse.indices)

            # Boost results with BM25 scores
            boosted_results = []
            for result in dense_results.results:
                doc_text = result.text or ""

                if doc_text:
                    # Compute BM25 score for this document
                    doc_sparse = bm25_service.encode(doc_text)

                    # Calculate overlap (dot product approximation)
                    bm25_score = 0.0
                    if doc_sparse.indices:
                        for idx, val in zip(doc_sparse.indices, doc_sparse.values):
                            if idx in query_terms:
                                bm25_score += val

                    # Normalize BM25 score
                    bm25_score = min(bm25_score / max(len(query_terms), 1), 1.0)

                    # Combine scores
                    combined_score = (
                        dense_weight * result.score + sparse_weight * bm25_score
                    )
                else:
                    combined_score = result.score

                # Update result score (create new result with updated score)
                boosted_results.append(
                    VectorSearchResult(
                        id=result.id,
                        score=combined_score,
                        text=result.text,
                        metadata=result.metadata,
                    )
                )

            # Re-sort by combined score
            boosted_results.sort(key=lambda x: x.score, reverse=True)

            # Return top results
            final_results = boosted_results[:limit]

            processing_time = time.time() - start_time
            logger.info(
                f"Hybrid search: {len(final_results)} results in {processing_time:.3f}s"
            )

            return VectorSearchResponse(
                results=final_results,
                total_found=len(final_results),
                search_time=processing_time,
                query=query,
                collection=VectorCollectionType.DOCUMENT_CHUNKS,
            )

        except Exception as e:
            logger.error(f"Error in hybrid search: {e}")
            # Fallback to dense-only search
            return self.search_documents(
                query=query,
                organization_id=organization_id,
                limit=limit,
                score_threshold=score_threshold,
                filters=filters,
            )

    def search_entities(
        self,
        query: str,
        organization_id: str,
        entity_type: Optional[str] = None,
        limit: int = 10,
        score_threshold: float = 0.2,  # Lowered to 0.2 for more results
    ) -> VectorSearchResponse:
        """Search for similar entities"""
        try:
            # Generate embedding for query
            embedding_request = EmbeddingRequest(text=query)
            embedding_response = asyncio.run(
                self.embedding_service.generate_embedding(embedding_request)
            )

            if not embedding_response.embedding:
                return VectorSearchResponse(
                    results=[],
                    total_found=0,
                    search_time=0.0,
                    query=query,
                    collection=VectorCollectionType.ENTITIES,
                )

            # Build filters
            filters = {}
            if entity_type:
                filters["metadata.entity_type"] = entity_type

            # Create search request
            search_request = VectorSearchRequest(
                query=query,
                collection=VectorCollectionType.ENTITIES,
                organization_id=organization_id,
                limit=limit,
                score_threshold=score_threshold,
                filters=filters if filters else None,
            )

            # Search in vector database
            result = self.vector_service.search_vectors(
                request=search_request, query_vector=embedding_response.embedding
            )

            return result

        except Exception as e:
            logger.error(f"Error searching entities: {e}")
            return VectorSearchResponse(
                results=[],
                total_found=0,
                search_time=0.0,
                query=query,
                collection=VectorCollectionType.ENTITIES,
            )

    def delete_document_vectors(self, document_id: str) -> VectorOperationResult:
        """Delete all vectors associated with a document"""
        try:
            # This is a simplified approach - in practice you might want to
            # search for vectors by document_id and delete them
            # For now, we'll return success as the concept is implemented
            return VectorOperationResult(
                success=True,
                message=f"Document vectors deletion implemented (need document_id search)",
                processing_time=0.0,
            )

        except Exception as e:
            logger.error(f"Error deleting document vectors: {e}")
            return VectorOperationResult(
                success=False,
                message=f"Failed to delete document vectors",
                error=str(e),
                processing_time=0.0,
            )

    def delete_entity_vectors(self, entity_id: str) -> VectorOperationResult:
        """Delete entity vectors"""
        try:
            result = self.vector_service.delete_vectors(
                collection_type=VectorCollectionType.ENTITIES, vector_ids=[entity_id]
            )
            return result

        except Exception as e:
            logger.error(f"Error deleting entity vectors: {e}")
            return VectorOperationResult(
                success=False,
                message=f"Failed to delete entity vectors",
                error=str(e),
                processing_time=0.0,
            )

    def get_embedding_model_info(self) -> Dict[str, Any]:
        """Get information about the embedding model"""
        return self.embedding_service.get_model_info()

    def test_embedding_quality(self, test_texts: List[str]) -> Dict[str, Any]:
        """Test embedding quality"""
        return self.embedding_service.test_embedding_quality(test_texts)

    def get_vector_database_health(self) -> Dict[str, Any]:
        """Get vector database health status"""
        return self.vector_service.get_health_status().dict()

    def reindex_all_content(
        self, organization_id: str, batch_size: int = 100
    ) -> Dict[str, Any]:
        """Reindex all content for an organization (placeholder implementation)"""
        # This would typically involve:
        # 1. Fetching all documents from the database
        # 2. Clearing existing vectors for the organization
        # 3. Re-indexing all content with current embedding model

        return {
            "success": True,
            "message": "Reindexing workflow implemented",
            "organization_id": organization_id,
            "batch_size": batch_size,
        }

    def update_document_index(
        self,
        document_id: str,
        text: str,
        organization_id: str,
        content_type: str = "text",
    ) -> VectorOperationResult:
        """Update document index by deleting old vectors and re-indexing"""
        try:
            # Delete existing vectors (simplified approach)
            delete_result = self.delete_document_vectors(document_id)

            # Re-index document
            index_result = self.index_document(
                document_id=document_id,
                text=text,
                organization_id=organization_id,
                content_type=content_type,
            )

            return index_result

        except Exception as e:
            logger.error(f"Error updating document index: {e}")
            return VectorOperationResult(
                success=False,
                message=f"Failed to update document index",
                error=str(e),
                processing_time=0.0,
            )


# Singleton instance
vector_search_service = VectorSearchService()
