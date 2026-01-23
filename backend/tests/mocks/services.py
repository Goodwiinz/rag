"""
Service Mock Implementations for Unit Testing

Provides reusable mock implementations for core external services:
- MockAsyncSession: SQLAlchemy async session mock
- MockNeo4jDriver: Neo4j driver with mock session/transactions
- MockRedisClient: Redis async client mock
- MockCohereClient: Cohere reranking API mock
- MockSentenceTransformer: Embedding model mock

Usage:
    from tests.mocks.services import MockAsyncSession, MockNeo4jDriver

    async def test_my_service():
        db = MockAsyncSession()
        db.set_query_result([mock_user])

        service = MyService(db)
        result = await service.get_user("123")
        assert result == mock_user
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Union, TypeVar, Generic
from unittest.mock import Mock, MagicMock, AsyncMock
from uuid import uuid4
from datetime import datetime
import numpy as np


T = TypeVar('T')


# ============================================================================
# Mock Async Session (SQLAlchemy)
# ============================================================================

class MockAsyncSession:
    """
    Mock SQLAlchemy AsyncSession for unit testing.

    Supports:
    - Configurable query results
    - Execute/scalar/scalars result mocking
    - Transaction simulation
    - Call recording for assertions

    Example:
        db = MockAsyncSession()
        db.set_query_result([user1, user2])

        result = await db.execute(select(User))
        users = result.scalars().all()
        assert users == [user1, user2]
    """

    def __init__(self):
        self._query_results: List[Any] = []
        self._scalar_result: Any = None
        self._scalars_result: List[Any] = []
        self._execute_side_effect: Optional[Exception] = None
        self._commit_side_effect: Optional[Exception] = None
        self._added_items: List[Any] = []
        self._deleted_items: List[Any] = []
        self._flushed: bool = False
        self._committed: bool = False
        self._rolled_back: bool = False
        self._closed: bool = False
        self.execute_calls: List[Any] = []

    def set_query_result(self, results: List[Any]) -> "MockAsyncSession":
        """Set results for query execution."""
        self._query_results = results
        self._scalars_result = results
        self._scalar_result = results[0] if results else None
        return self

    def set_scalar_result(self, result: Any) -> "MockAsyncSession":
        """Set result for scalar() calls."""
        self._scalar_result = result
        return self

    def set_scalars_result(self, results: List[Any]) -> "MockAsyncSession":
        """Set result for scalars().all() calls."""
        self._scalars_result = results
        return self

    def set_execute_side_effect(self, exception: Exception) -> "MockAsyncSession":
        """Set exception to raise on execute()."""
        self._execute_side_effect = exception
        return self

    def set_commit_side_effect(self, exception: Exception) -> "MockAsyncSession":
        """Set exception to raise on commit()."""
        self._commit_side_effect = exception
        return self

    async def execute(self, statement: Any, *args, **kwargs) -> "MockResult":
        """Execute a statement and return mock result."""
        self.execute_calls.append((statement, args, kwargs))

        if self._execute_side_effect:
            raise self._execute_side_effect

        return MockResult(
            scalar_result=self._scalar_result,
            scalars_result=self._scalars_result,
            all_result=self._query_results
        )

    async def scalar(self, statement: Any, *args, **kwargs) -> Any:
        """Execute and return single scalar result."""
        self.execute_calls.append((statement, args, kwargs))

        if self._execute_side_effect:
            raise self._execute_side_effect

        return self._scalar_result

    async def scalars(self, statement: Any, *args, **kwargs) -> "MockScalarsResult":
        """Execute and return scalars result."""
        self.execute_calls.append((statement, args, kwargs))

        if self._execute_side_effect:
            raise self._execute_side_effect

        return MockScalarsResult(self._scalars_result)

    def add(self, instance: Any) -> None:
        """Add an instance to the session."""
        self._added_items.append(instance)

    def add_all(self, instances: List[Any]) -> None:
        """Add multiple instances to the session."""
        self._added_items.extend(instances)

    async def delete(self, instance: Any) -> None:
        """Delete an instance from the session."""
        self._deleted_items.append(instance)

    async def flush(self) -> None:
        """Flush pending changes."""
        self._flushed = True

    async def commit(self) -> None:
        """Commit the transaction."""
        if self._commit_side_effect:
            raise self._commit_side_effect
        self._committed = True

    async def rollback(self) -> None:
        """Rollback the transaction."""
        self._rolled_back = True

    async def refresh(self, instance: Any) -> None:
        """Refresh an instance from the database."""
        pass

    async def close(self) -> None:
        """Close the session."""
        self._closed = True

    async def __aenter__(self) -> "MockAsyncSession":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    def begin(self) -> "MockTransactionContext":
        """Begin a transaction."""
        return MockTransactionContext(self)

    def begin_nested(self) -> "MockTransactionContext":
        """Begin a nested transaction (savepoint)."""
        return MockTransactionContext(self)

    # Assertions
    def assert_added(self, count: Optional[int] = None) -> None:
        """Assert items were added."""
        if count is not None:
            assert len(self._added_items) == count, \
                f"Expected {count} items added, got {len(self._added_items)}"
        else:
            assert len(self._added_items) > 0, "Expected items to be added"

    def assert_committed(self) -> None:
        """Assert transaction was committed."""
        assert self._committed, "Expected commit() to be called"

    def assert_rolled_back(self) -> None:
        """Assert transaction was rolled back."""
        assert self._rolled_back, "Expected rollback() to be called"

    def reset(self) -> "MockAsyncSession":
        """Reset state for reuse."""
        self._added_items = []
        self._deleted_items = []
        self._flushed = False
        self._committed = False
        self._rolled_back = False
        self.execute_calls = []
        return self


class MockResult:
    """Mock result from session.execute()."""

    def __init__(
        self,
        scalar_result: Any = None,
        scalars_result: List[Any] = None,
        all_result: List[Any] = None
    ):
        self._scalar_result = scalar_result
        self._scalars_result = scalars_result or []
        self._all_result = all_result or []

    def scalar(self) -> Any:
        """Return single scalar result."""
        return self._scalar_result

    def scalar_one(self) -> Any:
        """Return single scalar result or raise."""
        if self._scalar_result is None:
            raise Exception("No result found")
        return self._scalar_result

    def scalar_one_or_none(self) -> Optional[Any]:
        """Return single scalar result or None."""
        return self._scalar_result

    def scalars(self) -> "MockScalarsResult":
        """Return scalars accessor."""
        return MockScalarsResult(self._scalars_result)

    def all(self) -> List[Any]:
        """Return all results."""
        return self._all_result

    def first(self) -> Optional[Any]:
        """Return first result or None."""
        return self._all_result[0] if self._all_result else None

    def one(self) -> Any:
        """Return exactly one result or raise."""
        if not self._all_result or len(self._all_result) != 1:
            raise Exception("Expected exactly one result")
        return self._all_result[0]

    def one_or_none(self) -> Optional[Any]:
        """Return one result or None."""
        if not self._all_result:
            return None
        if len(self._all_result) > 1:
            raise Exception("Multiple results found")
        return self._all_result[0]


class MockScalarsResult:
    """Mock scalars result."""

    def __init__(self, results: List[Any]):
        self._results = results

    def all(self) -> List[Any]:
        """Return all scalar results."""
        return self._results

    def first(self) -> Optional[Any]:
        """Return first result or None."""
        return self._results[0] if self._results else None

    def one(self) -> Any:
        """Return exactly one result or raise."""
        if not self._results or len(self._results) != 1:
            raise Exception("Expected exactly one result")
        return self._results[0]

    def one_or_none(self) -> Optional[Any]:
        """Return one result or None."""
        if not self._results:
            return None
        if len(self._results) > 1:
            raise Exception("Multiple results found")
        return self._results[0]

    def __iter__(self):
        return iter(self._results)


class MockTransactionContext:
    """Mock transaction context manager."""

    def __init__(self, session: MockAsyncSession):
        self.session = session

    async def __aenter__(self) -> "MockTransactionContext":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            await self.session.rollback()
        else:
            await self.session.commit()


# ============================================================================
# Mock Neo4j Driver
# ============================================================================

@dataclass
class MockNeo4jRecord:
    """Mock Neo4j record."""
    _data: Dict[str, Any] = field(default_factory=dict)

    def data(self) -> Dict[str, Any]:
        """Return record data."""
        return self._data

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)


class MockNeo4jResult:
    """Mock Neo4j query result."""

    def __init__(self, records: List[Dict[str, Any]] = None):
        self._records = [MockNeo4jRecord(_data=r) for r in (records or [])]
        self._index = 0

    def single(self) -> Optional[MockNeo4jRecord]:
        """Return single record or None."""
        return self._records[0] if self._records else None

    def data(self) -> List[Dict[str, Any]]:
        """Return all records as dicts."""
        return [r.data() for r in self._records]

    def __iter__(self):
        return iter(self._records)

    def __next__(self) -> MockNeo4jRecord:
        if self._index >= len(self._records):
            raise StopIteration
        record = self._records[self._index]
        self._index += 1
        return record


class MockNeo4jSession:
    """Mock Neo4j session."""

    def __init__(self, driver: "MockNeo4jDriver"):
        self._driver = driver
        self._closed = False
        self.run_calls: List[tuple] = []

    async def run(self, query: str, parameters: Dict[str, Any] = None, **kwargs) -> MockNeo4jResult:
        """Execute a Cypher query."""
        self.run_calls.append((query, parameters, kwargs))

        if self._driver._run_side_effect:
            raise self._driver._run_side_effect

        return MockNeo4jResult(self._driver._query_results)

    async def close(self) -> None:
        """Close the session."""
        self._closed = True

    async def __aenter__(self) -> "MockNeo4jSession":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()


class MockNeo4jTransaction:
    """Mock Neo4j transaction."""

    def __init__(self, session: MockNeo4jSession):
        self._session = session
        self._committed = False
        self._rolled_back = False

    async def run(self, query: str, parameters: Dict[str, Any] = None, **kwargs) -> MockNeo4jResult:
        """Execute a query within the transaction."""
        return await self._session.run(query, parameters, **kwargs)

    async def commit(self) -> None:
        """Commit the transaction."""
        self._committed = True

    async def rollback(self) -> None:
        """Rollback the transaction."""
        self._rolled_back = True


class MockNeo4jDriver:
    """
    Mock Neo4j driver for unit testing.

    Example:
        driver = MockNeo4jDriver()
        driver.set_query_results([{"name": "Entity1", "type": "Person"}])

        async with driver.session() as session:
            result = await session.run("MATCH (n) RETURN n")
            records = result.data()
    """

    def __init__(self):
        self._query_results: List[Dict[str, Any]] = []
        self._run_side_effect: Optional[Exception] = None
        self._connected = True
        self._closed = False

    def set_query_results(self, results: List[Dict[str, Any]]) -> "MockNeo4jDriver":
        """Set results for query execution."""
        self._query_results = results
        return self

    def set_run_side_effect(self, exception: Exception) -> "MockNeo4jDriver":
        """Set exception to raise on run()."""
        self._run_side_effect = exception
        return self

    def set_connected(self, connected: bool) -> "MockNeo4jDriver":
        """Set connection status."""
        self._connected = connected
        return self

    def session(self, **kwargs) -> MockNeo4jSession:
        """Create a session."""
        if not self._connected:
            raise ConnectionError("Driver not connected")
        return MockNeo4jSession(self)

    async def verify_connectivity(self) -> None:
        """Verify driver connectivity."""
        if not self._connected:
            raise ConnectionError("Unable to connect to Neo4j")

    async def close(self) -> None:
        """Close the driver."""
        self._closed = True

    def reset(self) -> "MockNeo4jDriver":
        """Reset state for reuse."""
        self._query_results = []
        self._run_side_effect = None
        self._connected = True
        self._closed = False
        return self


# ============================================================================
# Mock Redis Client
# ============================================================================

class MockRedisClient:
    """
    Mock Redis async client for unit testing.

    Example:
        redis = MockRedisClient()
        redis.set_value("user:123", '{"name": "John"}')

        value = await redis.get("user:123")
        assert value == '{"name": "John"}'
    """

    def __init__(self):
        self._cache: Dict[str, str] = {}
        self._expiry: Dict[str, int] = {}
        self._connected = True
        self._side_effect: Optional[Exception] = None
        self.get_calls: List[str] = []
        self.set_calls: List[tuple] = []
        self.delete_calls: List[str] = []

    def set_value(self, key: str, value: str, ex: int = None) -> "MockRedisClient":
        """Set a cache value."""
        self._cache[key] = value
        if ex:
            self._expiry[key] = ex
        return self

    def set_values(self, values: Dict[str, str]) -> "MockRedisClient":
        """Set multiple cache values."""
        self._cache.update(values)
        return self

    def set_side_effect(self, exception: Exception) -> "MockRedisClient":
        """Set exception to raise on operations."""
        self._side_effect = exception
        return self

    def set_connected(self, connected: bool) -> "MockRedisClient":
        """Set connection status."""
        self._connected = connected
        return self

    async def get(self, key: str) -> Optional[str]:
        """Get a value from cache."""
        self.get_calls.append(key)

        if self._side_effect:
            raise self._side_effect

        if not self._connected:
            raise ConnectionError("Redis not connected")

        return self._cache.get(key)

    async def set(
        self,
        key: str,
        value: str,
        ex: int = None,
        px: int = None,
        nx: bool = False,
        xx: bool = False
    ) -> bool:
        """Set a value in cache."""
        self.set_calls.append((key, value, ex))

        if self._side_effect:
            raise self._side_effect

        if not self._connected:
            raise ConnectionError("Redis not connected")

        if nx and key in self._cache:
            return False
        if xx and key not in self._cache:
            return False

        self._cache[key] = value
        if ex:
            self._expiry[key] = ex
        return True

    async def setex(self, key: str, seconds: int, value: str) -> bool:
        """Set a value with expiry."""
        return await self.set(key, value, ex=seconds)

    async def delete(self, *keys: str) -> int:
        """Delete keys from cache."""
        deleted = 0
        for key in keys:
            self.delete_calls.append(key)
            if key in self._cache:
                del self._cache[key]
                self._expiry.pop(key, None)
                deleted += 1
        return deleted

    async def exists(self, *keys: str) -> int:
        """Check if keys exist."""
        if self._side_effect:
            raise self._side_effect
        return sum(1 for key in keys if key in self._cache)

    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiry on a key."""
        if key in self._cache:
            self._expiry[key] = seconds
            return True
        return False

    async def ttl(self, key: str) -> int:
        """Get TTL of a key."""
        return self._expiry.get(key, -2 if key not in self._cache else -1)

    async def incr(self, key: str) -> int:
        """Increment a key."""
        current = int(self._cache.get(key, "0"))
        new_value = current + 1
        self._cache[key] = str(new_value)
        return new_value

    async def decr(self, key: str) -> int:
        """Decrement a key."""
        current = int(self._cache.get(key, "0"))
        new_value = current - 1
        self._cache[key] = str(new_value)
        return new_value

    async def ping(self) -> bool:
        """Ping the server."""
        if not self._connected:
            raise ConnectionError("Redis not connected")
        return True

    async def close(self) -> None:
        """Close the connection."""
        self._connected = False

    async def __aenter__(self) -> "MockRedisClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    def reset(self) -> "MockRedisClient":
        """Reset state for reuse."""
        self._cache = {}
        self._expiry = {}
        self._connected = True
        self._side_effect = None
        self.get_calls = []
        self.set_calls = []
        self.delete_calls = []
        return self


# ============================================================================
# Mock Cohere Client
# ============================================================================

@dataclass
class MockRerankResult:
    """Mock Cohere rerank result."""
    index: int
    relevance_score: float
    document: Dict[str, str] = field(default_factory=dict)


class MockCohereClient:
    """
    Mock Cohere client for reranking tests.

    Example:
        cohere = MockCohereClient()
        cohere.set_rerank_scores([0.9, 0.7, 0.5])

        results = await cohere.rerank(query="test", documents=docs)
        assert results[0].relevance_score == 0.9
    """

    def __init__(self):
        self._rerank_scores: List[float] = []
        self._side_effect: Optional[Exception] = None
        self._enabled = True
        self.rerank_calls: List[tuple] = []

    def set_rerank_scores(self, scores: List[float]) -> "MockCohereClient":
        """Set scores to return for reranking."""
        self._rerank_scores = scores
        return self

    def set_side_effect(self, exception: Exception) -> "MockCohereClient":
        """Set exception to raise on rerank."""
        self._side_effect = exception
        return self

    def set_enabled(self, enabled: bool) -> "MockCohereClient":
        """Set whether reranking is enabled."""
        self._enabled = enabled
        return self

    @property
    def is_enabled(self) -> bool:
        """Check if reranking is enabled."""
        return self._enabled

    async def rerank(
        self,
        query: str,
        documents: List[Union[str, Dict[str, str]]],
        top_n: int = None,
        model: str = "rerank-english-v2.0"
    ) -> List[MockRerankResult]:
        """Rerank documents by relevance to query."""
        self.rerank_calls.append((query, documents, top_n, model))

        if self._side_effect:
            raise self._side_effect

        if not self._enabled:
            return []

        # Generate results based on scores
        results = []
        for i, doc in enumerate(documents):
            score = self._rerank_scores[i] if i < len(self._rerank_scores) else 0.5
            doc_dict = {"text": doc} if isinstance(doc, str) else doc
            results.append(MockRerankResult(
                index=i,
                relevance_score=score,
                document=doc_dict
            ))

        # Sort by score descending
        results.sort(key=lambda x: x.relevance_score, reverse=True)

        # Apply top_n limit
        if top_n:
            results = results[:top_n]

        return results

    def reset(self) -> "MockCohereClient":
        """Reset state for reuse."""
        self._rerank_scores = []
        self._side_effect = None
        self._enabled = True
        self.rerank_calls = []
        return self


# ============================================================================
# Mock Sentence Transformer
# ============================================================================

class MockSentenceTransformer:
    """
    Mock sentence transformer for embedding tests.

    Generates deterministic embeddings based on text hash.

    Example:
        model = MockSentenceTransformer(dimension=384)
        embeddings = model.encode(["Hello world", "Test sentence"])
        assert len(embeddings[0]) == 384
    """

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self._side_effect: Optional[Exception] = None
        self.encode_calls: List[List[str]] = []

    def set_side_effect(self, exception: Exception) -> "MockSentenceTransformer":
        """Set exception to raise on encode."""
        self._side_effect = exception
        return self

    def _generate_embedding(self, text: str) -> np.ndarray:
        """Generate deterministic embedding from text."""
        np.random.seed(hash(text) % 2**32)
        embedding = np.random.rand(self.dimension).astype(np.float32)
        # Normalize to unit length
        embedding = embedding / np.linalg.norm(embedding)
        return embedding

    def encode(
        self,
        sentences: Union[str, List[str]],
        batch_size: int = 32,
        show_progress_bar: bool = False,
        convert_to_numpy: bool = True,
        normalize_embeddings: bool = False
    ) -> np.ndarray:
        """Encode sentences to embeddings."""
        if self._side_effect:
            raise self._side_effect

        if isinstance(sentences, str):
            sentences = [sentences]

        self.encode_calls.append(sentences)

        embeddings = np.array([self._generate_embedding(text) for text in sentences])

        if normalize_embeddings:
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            embeddings = embeddings / norms

        return embeddings

    async def encode_async(
        self,
        sentences: Union[str, List[str]],
        **kwargs
    ) -> np.ndarray:
        """Async encode wrapper."""
        return self.encode(sentences, **kwargs)

    def reset(self) -> "MockSentenceTransformer":
        """Reset state for reuse."""
        self._side_effect = None
        self.encode_calls = []
        return self


# ============================================================================
# Mock Search Services
# ============================================================================

@dataclass
class MockSearchResult:
    """Mock search result."""
    id: str
    document_id: str
    content: str
    score: float
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class MockFulltextSearchService:
    """Mock fulltext search service."""

    def __init__(self):
        self._results: List[MockSearchResult] = []
        self._side_effect: Optional[Exception] = None

    def set_results(self, results: List[MockSearchResult]) -> "MockFulltextSearchService":
        """Set search results."""
        self._results = results
        return self

    def set_side_effect(self, exception: Exception) -> "MockFulltextSearchService":
        """Set exception to raise on search."""
        self._side_effect = exception
        return self

    async def search(self, query: str, **kwargs) -> List[MockSearchResult]:
        """Perform fulltext search."""
        if self._side_effect:
            raise self._side_effect
        return self._results


class MockVectorSearchService:
    """Mock vector search service."""

    def __init__(self):
        self._results: List[MockSearchResult] = []
        self._side_effect: Optional[Exception] = None

    def set_results(self, results: List[MockSearchResult]) -> "MockVectorSearchService":
        """Set search results."""
        self._results = results
        return self

    def set_side_effect(self, exception: Exception) -> "MockVectorSearchService":
        """Set exception to raise on search."""
        self._side_effect = exception
        return self

    async def search(self, query: str, embedding: List[float] = None, **kwargs) -> List[MockSearchResult]:
        """Perform vector search."""
        if self._side_effect:
            raise self._side_effect
        return self._results


class MockGraphSearchService:
    """Mock graph search service."""

    def __init__(self):
        self._results: List[MockSearchResult] = []
        self._side_effect: Optional[Exception] = None

    def set_results(self, results: List[MockSearchResult]) -> "MockGraphSearchService":
        """Set search results."""
        self._results = results
        return self

    def set_side_effect(self, exception: Exception) -> "MockGraphSearchService":
        """Set exception to raise on search."""
        self._side_effect = exception
        return self

    async def search(self, query: str, **kwargs) -> List[MockSearchResult]:
        """Perform graph search."""
        if self._side_effect:
            raise self._side_effect
        return self._results
