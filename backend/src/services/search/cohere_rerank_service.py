"""
Cohere Reranking Service

Uses Azure AI Cohere rerank API to improve precision@K scores by reranking
search results based on query-document relevance.
"""

import logging
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

import httpx

from src.core.config import settings
from src.core.circuit_breaker import get_circuit_breaker, ServiceUnavailableError

logger = logging.getLogger(__name__)


@dataclass
class RerankResult:
    """Result from reranking operation"""
    document_id: str
    index: int
    relevance_score: float
    original_score: float


class CohereRerankService:
    """
    Service for reranking search results using Azure AI Cohere rerank API.
    
    This improves Precision@K by using a cross-encoder model to score
    query-document pairs more accurately than initial retrieval.
    """
    
    def __init__(self):
        self.endpoint = settings.COHERE_RERANK_ENDPOINT
        self.api_key = settings.COHERE_RERANK_API_KEY
        self.model = settings.COHERE_RERANK_MODEL
        self.default_top_n = settings.COHERE_RERANK_TOP_N
        self._enabled = bool(self.endpoint and self.api_key)
        
        if self._enabled:
            logger.info(f"Cohere reranking enabled with model: {self.model}")
        else:
            logger.warning("Cohere reranking disabled - missing endpoint or API key")
    
    @property
    def is_enabled(self) -> bool:
        """Check if reranking is enabled"""
        return self._enabled
    
    async def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_n: Optional[int] = None,
        return_documents: bool = False
    ) -> List[RerankResult]:
        """
        Rerank documents based on query relevance using Cohere API.

        Args:
            query: The search query
            documents: List of documents with 'content' and 'id' fields
            top_n: Number of top results to return (default: settings.COHERE_RERANK_TOP_N)
            return_documents: Whether to include document text in response

        Returns:
            List of RerankResult sorted by relevance score (highest first)
        """
        if not self._enabled:
            logger.debug("Reranking disabled, returning original order")
            return self._fallback_rerank(documents, top_n)

        if not documents:
            return []

        # Check circuit breaker before making Cohere API call
        breaker = get_circuit_breaker("cohere")
        if breaker and not breaker.can_execute():
            logger.warning("Cohere circuit breaker is open - using fallback reranking")
            return self._fallback_rerank(documents, top_n)

        top_n = top_n or self.default_top_n
        top_n = min(top_n, len(documents))

        start_time = time.time()

        try:
            # Prepare documents for Cohere API
            doc_texts = []
            doc_ids = []
            original_scores = []
            
            for doc in documents:
                # Extract text content - try multiple fields
                content = (
                    doc.get('content') or 
                    doc.get('content_snippet') or 
                    doc.get('text') or 
                    doc.get('title', '')
                )
                doc_texts.append(content[:4096])  # Cohere has token limits
                doc_ids.append(str(doc.get('id') or doc.get('document_id', '')))
                original_scores.append(doc.get('relevance_score', doc.get('score', 0.0)))
            
            # Call Cohere rerank API
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.endpoint,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "query": query,
                        "documents": doc_texts,
                        "top_n": top_n,
                        "return_documents": return_documents
                    }
                )
                response.raise_for_status()
                result = response.json()
            
            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(f"Cohere rerank completed in {elapsed_ms:.0f}ms for {len(documents)} docs")
            
            # Parse results
            rerank_results = []
            for item in result.get('results', []):
                idx = item['index']
                rerank_results.append(RerankResult(
                    document_id=doc_ids[idx],
                    index=idx,
                    relevance_score=item['relevance_score'],
                    original_score=original_scores[idx]
                ))
            
            # Sort by relevance score (highest first)
            rerank_results.sort(key=lambda x: x.relevance_score, reverse=True)

            # Record circuit breaker success
            if breaker:
                breaker.record_success()

            return rerank_results

        except httpx.HTTPStatusError as e:
            logger.error(f"Cohere API error: {e.response.status_code} - {e.response.text}")
            # Record circuit breaker failure
            if breaker:
                breaker.record_failure(e)
            return self._fallback_rerank(documents, top_n)

        except Exception as e:
            logger.error(f"Cohere rerank failed: {e}")
            # Record circuit breaker failure
            if breaker:
                breaker.record_failure(e)
            return self._fallback_rerank(documents, top_n)
    
    def _fallback_rerank(
        self,
        documents: List[Dict[str, Any]],
        top_n: Optional[int] = None
    ) -> List[RerankResult]:
        """Fallback when API is unavailable - return original order"""
        top_n = top_n or self.default_top_n
        top_n = min(top_n, len(documents))
        
        results = []
        for i, doc in enumerate(documents[:top_n]):
            score = doc.get('relevance_score', doc.get('score', 1.0 - (i * 0.1)))
            results.append(RerankResult(
                document_id=str(doc.get('id') or doc.get('document_id', '')),
                index=i,
                relevance_score=score,
                original_score=score
            ))
        
        return results
    
    def rerank_sync(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_n: Optional[int] = None,
        return_documents: bool = False
    ) -> List[RerankResult]:
        """
        Synchronous version of rerank for use in non-async contexts.

        Args:
            query: The search query
            documents: List of documents with 'content' and 'id' fields
            top_n: Number of top results to return
            return_documents: Whether to include document text in response

        Returns:
            List of RerankResult sorted by relevance score (highest first)
        """
        if not self._enabled:
            logger.debug("Reranking disabled, returning original order")
            return self._fallback_rerank(documents, top_n)

        if not documents:
            return []

        # Check circuit breaker before making Cohere API call
        breaker = get_circuit_breaker("cohere")
        if breaker and not breaker.can_execute():
            logger.warning("Cohere circuit breaker is open - using fallback reranking")
            return self._fallback_rerank(documents, top_n)

        top_n = top_n or self.default_top_n
        top_n = min(top_n, len(documents))

        start_time = time.time()

        try:
            # Prepare documents for Cohere API
            doc_texts = []
            doc_ids = []
            original_scores = []
            
            for doc in documents:
                content = (
                    doc.get('content') or 
                    doc.get('content_snippet') or 
                    doc.get('text') or 
                    doc.get('title', '')
                )
                doc_texts.append(content[:4096])
                doc_ids.append(str(doc.get('id') or doc.get('document_id', '')))
                original_scores.append(doc.get('relevance_score', doc.get('score', 0.0)))
            
            # Call Cohere rerank API using sync client
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    self.endpoint,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "query": query,
                        "documents": doc_texts,
                        "top_n": top_n,
                        "return_documents": return_documents
                    }
                )
                response.raise_for_status()
                result = response.json()
            
            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(f"Cohere rerank (sync) completed in {elapsed_ms:.0f}ms for {len(documents)} docs")
            
            # Parse results
            rerank_results = []
            for item in result.get('results', []):
                idx = item['index']
                rerank_results.append(RerankResult(
                    document_id=doc_ids[idx],
                    index=idx,
                    relevance_score=item['relevance_score'],
                    original_score=original_scores[idx]
                ))
            
            rerank_results.sort(key=lambda x: x.relevance_score, reverse=True)

            # Record circuit breaker success
            if breaker:
                breaker.record_success()

            return rerank_results

        except httpx.HTTPStatusError as e:
            logger.error(f"Cohere API error: {e.response.status_code} - {e.response.text}")
            # Record circuit breaker failure
            if breaker:
                breaker.record_failure(e)
            return self._fallback_rerank(documents, top_n)

        except Exception as e:
            logger.error(f"Cohere rerank (sync) failed: {e}")
            # Record circuit breaker failure
            if breaker:
                breaker.record_failure(e)
            return self._fallback_rerank(documents, top_n)

    async def rerank_search_results(
        self,
        query: str,
        results: List[Any],
        top_n: Optional[int] = None,
        content_field: str = 'content_snippet'
    ) -> List[Any]:
        """
        Convenience method to rerank SearchResult objects directly.
        
        Args:
            query: The search query
            results: List of SearchResult objects (or dicts with similar structure)
            top_n: Number of results to return
            content_field: Field name containing the text content
            
        Returns:
            Reranked list of results with updated scores
        """
        if not results:
            return []
        
        # Convert SearchResult objects to dicts for reranking
        documents = []
        for r in results:
            if hasattr(r, 'dict'):
                doc = r.dict() if callable(r.dict) else dict(r)
            elif hasattr(r, '__dict__'):
                doc = vars(r)
            else:
                doc = dict(r)
            
            # Ensure we have content
            doc['content'] = (
                doc.get(content_field) or 
                doc.get('content_snippet') or 
                doc.get('content') or 
                doc.get('title', '')
            )
            documents.append(doc)
        
        # Perform reranking
        rerank_results = await self.rerank(query, documents, top_n)
        
        # Create index map for fast lookup
        rerank_map = {r.index: r for r in rerank_results}
        
        # Build reordered results with updated scores
        reranked = []
        for rr in rerank_results:
            original_result = results[rr.index]
            
            # Update score if the result has this attribute
            if hasattr(original_result, 'relevance_score'):
                original_result.relevance_score = rr.relevance_score
            elif isinstance(original_result, dict):
                original_result['relevance_score'] = rr.relevance_score
            
            reranked.append(original_result)
        
        return reranked


# Global service instance
cohere_rerank_service = CohereRerankService()
