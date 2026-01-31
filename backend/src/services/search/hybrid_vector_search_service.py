"""
Hybrid Search Service

Combines dense vector search (Azure OpenAI embeddings) with sparse BM25 vectors
for improved retrieval precision. Uses Reciprocal Rank Fusion (RRF) to merge results.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests

from src.core.config import settings
from src.models.vector import (
    VectorCollectionType,
    VectorMetadata,
    VectorSearchRequest,
    VectorSearchResponse,
    VectorSearchResult,
)
from src.services.embedding.embedding_service import embedding_service

from .bm25_service import SparseVector, bm25_service

logger = logging.getLogger(__name__)


@dataclass
class HybridSearchConfig:
    """Configuration for hybrid search"""

    dense_weight: float = 0.7  # Weight for semantic (dense) search
    sparse_weight: float = 0.3  # Weight for keyword (BM25) search
    rrf_k: int = 60  # RRF constant (default 60 is standard)
    limit: int = 10
    score_threshold: float = 0.0


class HybridVectorSearchService:
    """
    Hybrid search service combining dense and sparse vectors.

    Uses Reciprocal Rank Fusion (RRF) to combine results from:
    1. Dense vector search (semantic similarity via embeddings)
    2. Sparse vector search (keyword matching via BM25)
    """

    def __init__(self):
        self.qdrant_url = settings.QDRANT_URL
        self.qdrant_api_key = settings.QDRANT_API_KEY

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for Qdrant API requests"""
        headers = {"Content-Type": "application/json"}
        if self.qdrant_api_key:
            headers["api-key"] = self.qdrant_api_key
        return headers

    def search_dense(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 20,
        score_threshold: float = 0.0,
        filters: Optional[Dict] = None,
    ) -> List[Tuple[str, float, Dict]]:
        """
        Perform dense vector search.

        Returns:
            List of (doc_id, score, payload) tuples
        """
        url = f"{self.qdrant_url}/collections/{collection_name}/points/search"

        payload = {
            "vector": query_vector,
            "limit": limit,
            "with_payload": True,
            "with_vector": False,
            "score_threshold": score_threshold,
        }

        if filters:
            payload["filter"] = filters

        try:
            response = requests.post(
                url, json=payload, headers=self._get_headers(), timeout=10
            )
            response.raise_for_status()
            results = response.json().get("result", [])

            return [(str(r["id"]), r["score"], r.get("payload", {})) for r in results]
        except Exception as e:
            logger.error(f"Dense search failed: {e}")
            return []

    def search_sparse_simulation(
        self,
        collection_name: str,
        sparse_vector: SparseVector,
        limit: int = 20,
        filters: Optional[Dict] = None,
    ) -> List[Tuple[str, float, Dict]]:
        """
        Simulate sparse vector search using payload filtering.

        Note: This is a simulation since Qdrant sparse vector support
        requires specific collection configuration. For production,
        use Qdrant's native sparse vector collections.

        Returns:
            List of (doc_id, score, payload) tuples
        """
        # For now, we'll use the BM25 scores during reranking
        # rather than a separate Qdrant sparse index
        # This is a workaround until the collection is migrated to sparse vectors

        logger.debug("Sparse search simulation - using BM25 for reranking only")
        return []

    def reciprocal_rank_fusion(
        self,
        dense_results: List[Tuple[str, float, Dict]],
        sparse_results: List[Tuple[str, float, Dict]],
        k: int = 60,
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3,
    ) -> List[Tuple[str, float, Dict]]:
        """
        Combine results using Reciprocal Rank Fusion.

        RRF score = sum(weight / (k + rank))

        Args:
            dense_results: Results from dense search
            sparse_results: Results from sparse search
            k: RRF constant (standard is 60)
            dense_weight: Weight for dense results
            sparse_weight: Weight for sparse results

        Returns:
            Fused and sorted results
        """
        doc_scores: Dict[str, float] = {}
        doc_payloads: Dict[str, Dict] = {}

        # Score dense results
        for rank, (doc_id, score, payload) in enumerate(dense_results, 1):
            rrf_score = dense_weight / (k + rank)
            doc_scores[doc_id] = doc_scores.get(doc_id, 0) + rrf_score
            doc_payloads[doc_id] = payload

        # Score sparse results
        for rank, (doc_id, score, payload) in enumerate(sparse_results, 1):
            rrf_score = sparse_weight / (k + rank)
            doc_scores[doc_id] = doc_scores.get(doc_id, 0) + rrf_score
            if doc_id not in doc_payloads:
                doc_payloads[doc_id] = payload

        # Sort by fused score
        sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)

        return [(doc_id, score, doc_payloads[doc_id]) for doc_id, score in sorted_docs]

    def hybrid_search(
        self,
        query: str,
        collection: VectorCollectionType,
        organization_id: Optional[str] = None,
        config: Optional[HybridSearchConfig] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> VectorSearchResponse:
        """
        Perform hybrid search combining dense and sparse vectors.

        Args:
            query: Search query
            collection: Target collection
            organization_id: Optional org filter
            config: Hybrid search configuration
            filters: Additional filters

        Returns:
            VectorSearchResponse with hybrid results
        """
        start_time = time.time()
        config = config or HybridSearchConfig()

        try:
            collection_name = collection.value

            # Build filter
            query_filter = None
            if organization_id or filters:
                filter_conditions = []
                if organization_id:
                    filter_conditions.append(
                        {"key": "organization_id", "match": {"value": organization_id}}
                    )
                if filters:
                    for key, value in filters.items():
                        filter_conditions.append(
                            {"key": key, "match": {"value": value}}
                        )
                if filter_conditions:
                    query_filter = {"must": filter_conditions}

            # Get dense query vector
            query_embedding = embedding_service.generate_embedding(query)
            if not query_embedding:
                logger.error("Failed to generate query embedding")
                return self._empty_response(query, collection, start_time)

            # Get sparse query vector
            sparse_query = bm25_service.encode(query, is_query=True)

            # Perform dense search (get more than limit for fusion)
            dense_limit = config.limit * 2
            dense_results = self.search_dense(
                collection_name=collection_name,
                query_vector=query_embedding,
                limit=dense_limit,
                score_threshold=config.score_threshold,
                filters=query_filter,
            )

            logger.info(f"Dense search found {len(dense_results)} results")

            # Perform sparse search simulation
            sparse_results = self.search_sparse_simulation(
                collection_name=collection_name,
                sparse_vector=sparse_query,
                limit=dense_limit,
                filters=query_filter,
            )

            logger.info(f"Sparse search found {len(sparse_results)} results")

            # Fuse results using RRF
            if sparse_results:
                fused_results = self.reciprocal_rank_fusion(
                    dense_results=dense_results,
                    sparse_results=sparse_results,
                    k=config.rrf_k,
                    dense_weight=config.dense_weight,
                    sparse_weight=config.sparse_weight,
                )
            else:
                # If no sparse results, use dense only with BM25 boost
                fused_results = self._boost_with_bm25(query, dense_results)

            # Convert to VectorSearchResult
            vector_results = []
            for doc_id, score, payload in fused_results[: config.limit]:
                metadata = VectorMetadata(
                    document_id=payload.get("document_id", doc_id),
                    organization_id=payload.get(
                        "organization_id", organization_id or ""
                    ),
                    content_type=payload.get("content_type", "text"),
                    source_type=payload.get("source_type", "document"),
                    chunk_index=payload.get("chunk_index"),
                    timestamp=payload.get("timestamp"),
                    additional_data=payload,
                )

                vector_results.append(
                    VectorSearchResult(
                        id=doc_id,
                        score=score,
                        text=payload.get("text", ""),
                        metadata=metadata,
                    )
                )

            processing_time = time.time() - start_time

            logger.info(
                f"Hybrid search completed: {len(vector_results)} results in {processing_time:.3f}s "
                f"(dense={len(dense_results)}, sparse={len(sparse_results)})"
            )

            return VectorSearchResponse(
                results=vector_results,
                total_found=len(vector_results),
                search_time=processing_time,
                query=query,
                collection=collection,
            )

        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            return self._empty_response(query, collection, start_time)

    def _boost_with_bm25(
        self,
        query: str,
        dense_results: List[Tuple[str, float, Dict]],
        bm25_weight: float = 0.3,
    ) -> List[Tuple[str, float, Dict]]:
        """
        Boost dense results with BM25 scores.
        Used when sparse index is not available.
        """
        if not dense_results:
            return []

        query_sparse = bm25_service.encode(query, is_query=True)
        query_terms = set(query_sparse.indices)

        boosted = []
        for doc_id, dense_score, payload in dense_results:
            # Compute BM25 score for document text
            doc_text = payload.get("text", "")
            if doc_text:
                doc_sparse = bm25_service.encode(doc_text)

                # Compute dot product (overlap score)
                overlap = (
                    sum(
                        doc_sparse.values[doc_sparse.indices.index(idx)]
                        for idx in query_terms
                        if idx in doc_sparse.indices
                    )
                    if doc_sparse.indices
                    else 0.0
                )

                # Normalize and combine
                bm25_score = min(overlap / max(len(query_terms), 1), 1.0)
                combined = (1 - bm25_weight) * dense_score + bm25_weight * bm25_score
            else:
                combined = dense_score

            boosted.append((doc_id, combined, payload))

        # Re-sort by combined score
        boosted.sort(key=lambda x: x[1], reverse=True)
        return boosted

    def _empty_response(
        self, query: str, collection: VectorCollectionType, start_time: float
    ) -> VectorSearchResponse:
        """Return empty response on error"""
        return VectorSearchResponse(
            results=[],
            total_found=0,
            search_time=time.time() - start_time,
            query=query,
            collection=collection,
        )


# Global service instance
hybrid_vector_search_service = HybridVectorSearchService()
