# Backend Improvements - Detailed Implementation Plan
**Priority:** HIGH
**Timeline:** Weeks 2-4
**Status:** Planning

---

## Overview

The backend analysis revealed several architectural and performance issues that need systematic resolution. This plan addresses them in order of impact.

---

## Phase 1: Performance Optimizations (Week 2)

### 1.1 Fix N+1 Query Problem in Document Listing

**Current Issue:**
**File:** `backend/src/api/documents.py:100-150`
- Documents listed without eager loading relationships
- Each document triggers separate queries for tags, metadata
- 100 documents = 100+ queries

**Implementation:**

#### Step 1: Add Eager Loading Options
**File:** `backend/src/api/documents.py`
```python
from sqlalchemy.orm import joinedload, selectinload

@router.get("", response_model=DocumentListResponse)
async def list_documents(
    db: Session = Depends(get_db),
    # ... params
):
    query = db.query(Document).filter(
        Document.is_deleted == False,
        Document.organization_id == current_user.organization_id
    ).options(
        # Eager load relationships
        selectinload(Document.tags),
        selectinload(Document.processing_jobs),
        joinedload(Document.uploaded_by),  # For user info
    )
    
    # Apply filters and pagination
    documents = query.offset(skip).limit(limit).all()
    
    return DocumentListResponse(
        documents=[DocumentResponse.from_orm(d) for d in documents],
        pagination=pagination
    )
```

#### Step 2: Create Query Performance Monitor
**File:** `backend/src/middleware/query_monitor.py`
```python
import time
import logging
from sqlalchemy import event
from sqlalchemy.engine import Engine

logger = logging.getLogger("query_monitor")

class QueryMonitor:
    """Monitor and log slow queries."""
    
    def __init__(self, slow_query_threshold_ms: float = 100):
        self.threshold = slow_query_threshold_ms / 1000
        self.query_count = 0
        self.slow_queries = []
    
    def start_request(self):
        self.query_count = 0
        self.slow_queries = []
    
    def end_request(self, request_path: str):
        if self.query_count > 10:
            logger.warning(
                f"High query count: {self.query_count} queries for {request_path}"
            )
        if self.slow_queries:
            logger.warning(
                f"Slow queries detected: {len(self.slow_queries)} for {request_path}"
            )

@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault("query_start_time", []).append(time.time())

@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total = time.time() - conn.info["query_start_time"].pop()
    if total > 0.1:  # 100ms threshold
        logger.warning(f"Slow query ({total:.3f}s): {statement[:200]}")
```

### 1.2 Increase Database Pool Recycle

**Current Issue:**
**File:** `backend/src/core/database.py:37`
```python
pool_recycle=300  # Too aggressive - causes connection churn
```

**Implementation:**
```python
# backend/src/core/database.py
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_pre_ping=True,           # Verify connections before use
    pool_recycle=3600,            # Recycle after 1 hour (was 300)
    pool_size=10,                 # Base pool size
    max_overflow=20,              # Allow up to 30 total connections
    pool_timeout=30,              # Wait 30s for available connection
    echo=settings.DEBUG_SQL,      # Configurable SQL logging
)

# Add connection event listeners
@event.listens_for(engine, "connect")
def on_connect(dbapi_connection, connection_record):
    logger.debug("New database connection established")

@event.listens_for(engine, "checkout")
def on_checkout(dbapi_connection, connection_record, connection_proxy):
    logger.debug("Connection checked out from pool")
```

### 1.3 Add Circuit Breaker for External Services

**Current Issue:**
- Neo4j, Qdrant, Cohere API calls have no failure protection
- Service failures cascade to all requests
- No graceful degradation

**Implementation:**

#### Step 1: Create Circuit Breaker Utility
**File:** `backend/src/core/circuit_breaker.py`
```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    CircuitBreaker
)
from functools import wraps
import asyncio
from typing import Callable, TypeVar, Any
from enum import Enum
import time

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery

class ServiceCircuitBreaker:
    """Circuit breaker for external service calls."""
    
    def __init__(
        self,
        service_name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3
    ):
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        self.half_open_calls = 0
    
    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
                return True
            return False
        
        # HALF_OPEN
        return self.half_open_calls < self.half_open_max_calls
    
    def record_success(self):
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_calls += 1
            if self.half_open_calls >= self.half_open_max_calls:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
    
    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker OPEN for {self.service_name}")

# Global circuit breakers
circuit_breakers = {
    "neo4j": ServiceCircuitBreaker("neo4j"),
    "qdrant": ServiceCircuitBreaker("qdrant"),
    "cohere": ServiceCircuitBreaker("cohere", failure_threshold=3),
}

def with_circuit_breaker(service_name: str):
    """Decorator to wrap function with circuit breaker."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            breaker = circuit_breakers.get(service_name)
            if not breaker:
                return await func(*args, **kwargs)
            
            if not breaker.can_execute():
                raise ServiceUnavailableError(
                    f"{service_name} circuit breaker is open"
                )
            
            try:
                result = await func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                raise
        
        return wrapper
    return decorator
```

#### Step 2: Apply to Neo4j Service
**File:** `backend/src/services/knowledge_graph_service.py`
```python
from ..core.circuit_breaker import with_circuit_breaker, retry_with_backoff

class KnowledgeGraphService:
    
    @with_circuit_breaker("neo4j")
    @retry_with_backoff(max_attempts=3)
    async def query_graph(self, cypher: str, params: dict = None):
        """Execute Cypher query with circuit breaker protection."""
        async with self.driver.session() as session:
            result = await session.run(cypher, params or {})
            return await result.data()
    
    @with_circuit_breaker("neo4j")
    async def get_entity_relationships(self, entity_id: str):
        """Get relationships for entity with fallback."""
        try:
            return await self.query_graph(
                "MATCH (e:Entity {id: $id})-[r]-(related) RETURN e, r, related",
                {"id": entity_id}
            )
        except ServiceUnavailableError:
            # Fallback to cached data or empty response
            logger.warning(f"Neo4j unavailable, returning cached data for {entity_id}")
            return self._get_cached_relationships(entity_id)
```

#### Step 3: Apply to Cohere Reranking
**File:** `backend/src/services/hybrid_search_service.py`
```python
@with_circuit_breaker("cohere")
@retry_with_backoff(max_attempts=2)
async def rerank_with_cohere(
    self,
    query: str,
    documents: list[str],
    top_n: int = 10
) -> list[dict]:
    """Rerank documents with Cohere, with timeout and circuit breaker."""
    try:
        async with asyncio.timeout(5.0):  # 5 second timeout
            response = await self.cohere_client.rerank(
                query=query,
                documents=documents,
                top_n=top_n,
                model="rerank-english-v2.0"
            )
            return response.results
    except asyncio.TimeoutError:
        logger.warning("Cohere reranking timed out, using fallback scoring")
        return self._fallback_rerank(query, documents, top_n)
```

---

## Phase 2: Architecture Refactoring (Week 3)

### 2.1 Split God Services

**Current Issue:**
`multi_agent_search_service_v2.py` is 1,637 lines doing:
- Agent orchestration
- Query processing
- Result fusion
- Metrics collection
- Caching

**Target Architecture:**
```
services/search/
├── __init__.py
├── orchestrator.py      # Agent coordination (~250 LoC)
├── query_processor.py   # Query analysis & expansion (~200 LoC)
├── executor.py          # Parallel search execution (~200 LoC)
├── fusion.py            # Result merging & dedup (~250 LoC)
├── reranker.py          # Cohere/custom reranking (~150 LoC)
├── metrics.py           # Search analytics (~150 LoC)
└── cache.py             # Result caching (~100 LoC)
```

#### Step 1: Create Base Search Interface
**File:** `backend/src/services/search/base.py`
```python
from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class SearchQuery:
    text: str
    filters: dict
    limit: int = 10
    offset: int = 0
    user_id: Optional[str] = None

@dataclass
class SearchResult:
    document_id: str
    score: float
    snippet: str
    metadata: dict
    source: str  # "vector", "graph", "keyword"

class SearchExecutor(ABC):
    """Base class for search executors."""
    
    @abstractmethod
    async def execute(self, query: SearchQuery) -> List[SearchResult]:
        pass
    
    @property
    @abstractmethod
    def source_name(self) -> str:
        pass
```

#### Step 2: Create Search Orchestrator
**File:** `backend/src/services/search/orchestrator.py`
```python
import asyncio
from typing import List
from .base import SearchQuery, SearchResult, SearchExecutor
from .fusion import ResultFusion
from .reranker import SearchReranker
from .metrics import SearchMetrics

class SearchOrchestrator:
    """Coordinates multi-source search execution."""
    
    def __init__(
        self,
        executors: List[SearchExecutor],
        fusion: ResultFusion,
        reranker: SearchReranker,
        metrics: SearchMetrics
    ):
        self.executors = executors
        self.fusion = fusion
        self.reranker = reranker
        self.metrics = metrics
    
    async def search(self, query: SearchQuery) -> List[SearchResult]:
        """Execute search across all sources and return unified results."""
        start_time = time.time()
        
        # Execute all searches in parallel
        tasks = [
            executor.execute(query) 
            for executor in self.executors
        ]
        results_per_source = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle failures gracefully
        valid_results = []
        for executor, results in zip(self.executors, results_per_source):
            if isinstance(results, Exception):
                self.metrics.record_source_failure(executor.source_name, results)
            else:
                valid_results.extend(results)
        
        # Fuse results from multiple sources
        fused = self.fusion.fuse(valid_results)
        
        # Rerank if we have enough results
        if len(fused) >= 5:
            fused = await self.reranker.rerank(query.text, fused)
        
        # Record metrics
        self.metrics.record_search(
            query=query,
            results_count=len(fused),
            duration_ms=(time.time() - start_time) * 1000,
            sources_used=[e.source_name for e in self.executors]
        )
        
        return fused[:query.limit]
```

#### Step 3: Create Result Fusion Service
**File:** `backend/src/services/search/fusion.py`
```python
from typing import List, Dict
from collections import defaultdict
from .base import SearchResult

class ResultFusion:
    """Fuses results from multiple search sources."""
    
    def __init__(self, source_weights: Dict[str, float] = None):
        self.source_weights = source_weights or {
            "vector": 0.4,
            "graph": 0.35,
            "keyword": 0.25
        }
    
    def fuse(self, results: List[SearchResult]) -> List[SearchResult]:
        """
        Fuse results using Reciprocal Rank Fusion (RRF).
        
        RRF score = sum(1 / (k + rank_i)) for each source
        """
        k = 60  # RRF constant
        
        # Group by document_id
        doc_scores: Dict[str, Dict] = defaultdict(lambda: {
            "rrf_score": 0.0,
            "result": None,
            "sources": []
        })
        
        # Calculate RRF scores
        results_by_source = defaultdict(list)
        for r in results:
            results_by_source[r.source].append(r)
        
        for source, source_results in results_by_source.items():
            weight = self.source_weights.get(source, 0.3)
            for rank, result in enumerate(source_results, 1):
                doc_id = result.document_id
                rrf_contribution = weight * (1 / (k + rank))
                doc_scores[doc_id]["rrf_score"] += rrf_contribution
                doc_scores[doc_id]["sources"].append(source)
                if doc_scores[doc_id]["result"] is None:
                    doc_scores[doc_id]["result"] = result
        
        # Sort by RRF score and return
        sorted_docs = sorted(
            doc_scores.items(),
            key=lambda x: x[1]["rrf_score"],
            reverse=True
        )
        
        return [
            SearchResult(
                document_id=doc_id,
                score=data["rrf_score"],
                snippet=data["result"].snippet,
                metadata={
                    **data["result"].metadata,
                    "fusion_sources": data["sources"]
                },
                source="fused"
            )
            for doc_id, data in sorted_docs
        ]
```

### 2.2 Create Custom Exception Hierarchy

**Current Issue:**
- `/src/exceptions/__init__.py` is empty
- Bare `except Exception` everywhere
- Error details leaked to clients

**Implementation:**

**File:** `backend/src/exceptions/__init__.py`
```python
from typing import Optional, Dict, Any

class RAGException(Exception):
    """Base exception for RAG system."""
    
    error_code: str = "RAG_ERROR"
    status_code: int = 500
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.cause = cause
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details
        }

# Validation Errors (4xx)
class ValidationException(RAGException):
    error_code = "VALIDATION_ERROR"
    status_code = 400

class AuthenticationException(RAGException):
    error_code = "AUTH_ERROR"
    status_code = 401

class AuthorizationException(RAGException):
    error_code = "FORBIDDEN"
    status_code = 403

class NotFoundException(RAGException):
    error_code = "NOT_FOUND"
    status_code = 404

class ConflictException(RAGException):
    error_code = "CONFLICT"
    status_code = 409

class QuotaExceededException(RAGException):
    error_code = "QUOTA_EXCEEDED"
    status_code = 429

# Processing Errors (5xx)
class ProcessingException(RAGException):
    error_code = "PROCESSING_ERROR"
    status_code = 500

class ServiceUnavailableError(RAGException):
    error_code = "SERVICE_UNAVAILABLE"
    status_code = 503

# Integration Errors
class Neo4jException(RAGException):
    error_code = "NEO4J_ERROR"
    status_code = 503

class QdrantException(RAGException):
    error_code = "QDRANT_ERROR"
    status_code = 503

class ExternalAPIException(RAGException):
    error_code = "EXTERNAL_API_ERROR"
    status_code = 502
```

**File:** `backend/src/middleware/exception_handler.py`
```python
from fastapi import Request
from fastapi.responses import JSONResponse
from ..exceptions import RAGException
import logging

logger = logging.getLogger(__name__)

async def rag_exception_handler(request: Request, exc: RAGException):
    """Handle RAG exceptions with proper logging and response."""
    
    # Log with appropriate level
    if exc.status_code >= 500:
        logger.error(
            f"{exc.error_code}: {exc.message}",
            extra={"details": exc.details, "path": request.url.path},
            exc_info=exc.cause
        )
    else:
        logger.warning(
            f"{exc.error_code}: {exc.message}",
            extra={"details": exc.details, "path": request.url.path}
        )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )

async def generic_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions without leaking details."""
    
    logger.exception(
        f"Unexpected error: {type(exc).__name__}",
        extra={"path": request.url.path}
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "details": {}
        }
    )
```

---

## Phase 3: Testing & Documentation (Week 4)

### 3.1 Add Integration Tests

**File:** `backend/tests/integration/test_search_pipeline.py`
```python
import pytest
from httpx import AsyncClient

@pytest.mark.integration
class TestSearchPipeline:
    """Integration tests for the complete search pipeline."""
    
    async def test_search_returns_results_from_multiple_sources(
        self,
        client: AsyncClient,
        auth_headers: dict,
        seeded_documents: list
    ):
        """Verify search aggregates results from vector, graph, and keyword."""
        response = await client.post(
            "/api/v1/search",
            json={"query": "machine learning", "limit": 10},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have results
        assert len(data["results"]) > 0
        
        # Should indicate fusion sources
        sources = set()
        for result in data["results"]:
            sources.update(result["metadata"].get("fusion_sources", []))
        
        # At least 2 sources should contribute
        assert len(sources) >= 2
    
    async def test_search_handles_neo4j_failure(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_neo4j_failure
    ):
        """Verify graceful degradation when Neo4j is unavailable."""
        response = await client.post(
            "/api/v1/search",
            json={"query": "test query", "limit": 10},
            headers=auth_headers
        )
        
        # Should still succeed with partial results
        assert response.status_code == 200
        data = response.json()
        
        # Results should be from non-Neo4j sources
        for result in data["results"]:
            assert "graph" not in result["metadata"].get("fusion_sources", [])
```

### 3.2 Add API Documentation

**File:** `backend/src/api/documents.py` (update docstrings)
```python
@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List documents",
    description="""
    Retrieve a paginated list of documents for the current user's organization.
    
    ## Filtering
    - `status`: Filter by processing status (pending, processing, completed, failed)
    - `file_type`: Filter by document type (pdf, txt, jpg, mp3, mp4)
    - `search`: Full-text search in title and filename
    
    ## Sorting
    - `sort_by`: Field to sort by (created_at, updated_at, title, filename)
    - `sort_order`: Sort direction (asc, desc)
    
    ## Pagination
    - `page`: Page number (1-indexed)
    - `size`: Items per page (1-100, default 20)
    """,
    responses={
        200: {"description": "List of documents"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized to access organization"},
    }
)
async def list_documents(...):
```

---

## Summary Checklist

### Week 2: Performance
- [ ] Add eager loading to document queries
- [ ] Increase pool_recycle to 3600
- [ ] Implement circuit breaker for Neo4j
- [ ] Implement circuit breaker for Qdrant
- [ ] Implement circuit breaker for Cohere
- [ ] Add query monitoring middleware

### Week 3: Architecture
- [ ] Split multi_agent_search_service_v2.py
- [ ] Create SearchOrchestrator
- [ ] Create ResultFusion service
- [ ] Create SearchReranker service
- [ ] Create custom exception hierarchy
- [ ] Add exception handler middleware

### Week 4: Quality
- [ ] Add integration tests for search pipeline
- [ ] Add integration tests for circuit breakers
- [ ] Update API documentation
- [ ] Add OpenAPI examples
- [ ] Performance benchmark baseline
