"""
LLM Response Cache Service

Provides semantic caching for LLM responses to reduce API costs
and improve latency for similar queries.
"""

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMCacheConfig:
    """Configuration for LLM response caching."""

    # Default TTL in seconds (1 hour for LLM responses)
    default_ttl: int = 3600

    # Maximum cache entries for in-memory cache
    max_entries: int = 5000

    # Whether to use Redis if available
    use_redis: bool = True

    # Redis key prefix
    redis_prefix: str = "llm_cache:"

    # Semantic similarity threshold (0.0-1.0)
    # Higher = stricter matching, lower = more cache hits
    similarity_threshold: float = 0.92

    # Whether to use semantic similarity (requires embeddings)
    use_semantic_cache: bool = True

    # Maximum embeddings to compare for semantic search
    max_semantic_comparisons: int = 100

    # Whether caching is enabled at all
    enabled: bool = True

    def __post_init__(self):
        """Validate configuration values after initialization."""
        if self.default_ttl < 0:
            raise ValueError(f"default_ttl must be non-negative, got {self.default_ttl}")
        if self.default_ttl > 86400 * 7:  # Max 7 days
            logger.warning(f"default_ttl of {self.default_ttl}s is very long, consider a shorter TTL")

        if self.max_entries < 1:
            raise ValueError(f"max_entries must be at least 1, got {self.max_entries}")
        if self.max_entries > 100000:
            logger.warning(f"max_entries of {self.max_entries} is very large, may cause memory issues")

        if not 0.0 <= self.similarity_threshold <= 1.0:
            raise ValueError(f"similarity_threshold must be between 0.0 and 1.0, got {self.similarity_threshold}")

        if self.max_semantic_comparisons < 1:
            raise ValueError(f"max_semantic_comparisons must be at least 1, got {self.max_semantic_comparisons}")

    @classmethod
    def from_settings(cls) -> "LLMCacheConfig":
        """Create config from application settings."""
        return cls(
            default_ttl=settings.LLM_CACHE_TTL_SECONDS,
            max_entries=settings.LLM_CACHE_MAX_ENTRIES,
            use_semantic_cache=settings.LLM_CACHE_SEMANTIC_ENABLED,
            similarity_threshold=settings.LLM_CACHE_SIMILARITY_THRESHOLD,
            enabled=settings.LLM_CACHE_ENABLED,
        )


@dataclass
class LLMCacheEntry:
    """A cached LLM response entry."""

    key: str
    query_hash: str
    query_text: str
    response_content: str
    model: str
    usage: Dict[str, int]
    embedding: Optional[List[float]] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ttl: int = 3600
    hit_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Store retrieved contexts for RAG responses to ensure consistency
    retrieved_contexts: Optional[List[Dict[str, Any]]] = None
    
    @property
    def is_expired(self) -> bool:
        """Check if the entry has expired."""
        expiry = self.created_at + timedelta(seconds=self.ttl)
        return datetime.now(timezone.utc) > expiry
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "key": self.key,
            "query_hash": self.query_hash,
            "query_text": self.query_text,
            "response_content": self.response_content,
            "model": self.model,
            "usage": self.usage,
            "embedding": self.embedding,
            "created_at": self.created_at.isoformat(),
            "ttl": self.ttl,
            "hit_count": self.hit_count,
            "metadata": self.metadata,
            "retrieved_contexts": self.retrieved_contexts,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LLMCacheEntry":
        """Deserialize from dictionary."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
            # Ensure timezone-aware (handle naive datetimes)
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
        elif created_at is None:
            created_at = datetime.now(timezone.utc)

        return cls(
            key=data["key"],
            query_hash=data["query_hash"],
            query_text=data["query_text"],
            response_content=data["response_content"],
            model=data["model"],
            usage=data.get("usage", {}),
            embedding=data.get("embedding"),
            created_at=created_at,
            ttl=data.get("ttl", 3600),
            hit_count=data.get("hit_count", 0),
            metadata=data.get("metadata", {}),
            retrieved_contexts=data.get("retrieved_contexts"),
        )


class LLMResponseCache:
    """
    Semantic cache for LLM responses.
    
    Supports:
    - Exact hash matching for identical queries
    - Semantic similarity matching using embeddings
    - Dual-tier storage (Redis + in-memory)
    """
    
    def __init__(self, config: Optional[LLMCacheConfig] = None):
        self.config = config or LLMCacheConfig()
        self._memory_cache: Dict[str, LLMCacheEntry] = {}
        self._embedding_index: Dict[str, List[float]] = {}  # hash -> embedding
        self._redis_client = None
        self._embedding_service = None
        self._lock = asyncio.Lock()  # Thread safety for shared mutable state
        self._stats = {
            "exact_hits": 0,
            "semantic_hits": 0,
            "misses": 0,
            "sets": 0,
            "errors": 0,
        }

    async def _increment_stat(self, key: str, amount: int = 1) -> None:
        """Thread-safe stat increment.
        
        Args:
            key: The stat key to increment (e.g., 'exact_hits', 'misses')
            amount: Amount to increment by (default 1)
        """
        async with self._lock:
            self._stats[key] += amount
        
    async def _get_redis(self):
        """Get or create Redis client."""
        if not self.config.use_redis:
            return None
            
        if self._redis_client is None:
            try:
                import redis.asyncio as redis
                self._redis_client = redis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True
                )
                # Test connection
                await self._redis_client.ping()
                logger.info("LLM cache connected to Redis")
            except Exception as e:
                logger.warning(f"Redis unavailable for LLM cache: {e}")
                self._redis_client = None
                
        return self._redis_client
    
    async def _get_embedding_service(self):
        """Get embedding service for semantic similarity."""
        if self._embedding_service is None:
            try:
                from .embedding_service import EmbeddingService
                self._embedding_service = EmbeddingService()
                logger.info("Embedding service initialized for semantic cache")
            except Exception as e:
                logger.warning(f"Embedding service unavailable: {e}")
                self._embedding_service = None
                
        return self._embedding_service
    
    def _generate_query_hash(self, query: str, model: str, temperature: float) -> str:
        """Generate a hash key for exact matching."""
        # Normalize query
        normalized = query.lower().strip()
        
        # Include model and temperature in hash for more precise matching
        components = {
            "query": normalized,
            "model": model,
            "temperature": round(temperature, 2),
        }
        
        hash_input = json.dumps(components, sort_keys=True)
        return hashlib.sha256(hash_input.encode()).hexdigest()[:32]
    
    def _generate_cache_key(self, query_hash: str) -> str:
        """Generate full cache key with prefix."""
        return f"{self.config.redis_prefix}{query_hash}"
    
    async def _compute_embedding(self, text: str) -> Optional[List[float]]:
        """Compute embedding for semantic similarity."""
        if not self.config.use_semantic_cache:
            return None
            
        embedding_service = await self._get_embedding_service()
        if embedding_service is None:
            return None
            
        try:
            # Use the embed method which returns numpy array
            embedding = embedding_service.embed(text)
            if isinstance(embedding, np.ndarray):
                return embedding.tolist()
            return embedding
        except Exception as e:
            logger.warning(f"Failed to compute embedding: {e}")
            return None
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        a_arr = np.array(a)
        b_arr = np.array(b)
        
        dot_product = np.dot(a_arr, b_arr)
        norm_a = np.linalg.norm(a_arr)
        norm_b = np.linalg.norm(b_arr)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
            
        return float(dot_product / (norm_a * norm_b))
    
    async def _find_semantic_match(
        self, 
        query_embedding: List[float]
    ) -> Optional[LLMCacheEntry]:
        """Find semantically similar cached response."""
        if not query_embedding:
            return None
            
        best_match: Optional[LLMCacheEntry] = None
        best_similarity = 0.0
        
        # Search in-memory cache
        comparisons = 0
        for query_hash, cached_embedding in list(self._embedding_index.items()):
            if comparisons >= self.config.max_semantic_comparisons:
                break
                
            similarity = self._cosine_similarity(query_embedding, cached_embedding)
            
            if similarity > best_similarity and similarity >= self.config.similarity_threshold:
                # Get the actual cache entry
                cache_key = self._generate_cache_key(query_hash)
                entry = self._memory_cache.get(cache_key)
                
                if entry and not entry.is_expired:
                    best_similarity = similarity
                    best_match = entry
                    
            comparisons += 1
        
        if best_match:
            logger.debug(f"Semantic cache hit with similarity {best_similarity:.3f}")
            
        return best_match
    
    async def get(
        self,
        query: str,
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        use_semantic: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached LLM response.
        
        Args:
            query: The user query text
            model: Model name/ID
            temperature: Sampling temperature
            use_semantic: Whether to use semantic similarity matching
            
        Returns:
            Cached response dict or None if not found
        """
        # Check if caching is enabled
        if not self.config.enabled:
            return None
            
        try:
            # Generate hash for exact matching
            query_hash = self._generate_query_hash(query, model, temperature)
            cache_key = self._generate_cache_key(query_hash)
            
            # Try exact match in memory first
            entry = self._memory_cache.get(cache_key)
            if entry and not entry.is_expired:
                # Use lock for thread-safe hit_count increment
                async with self._lock:
                    entry.hit_count += 1
                    self._stats["exact_hits"] += 1

                logger.info(f"LLM cache exact hit for query hash {query_hash[:8]}...")

                # Background sync hit_count to Redis (fire-and-forget)
                redis = await self._get_redis()
                if redis:
                    try:
                        remaining_ttl = await redis.ttl(cache_key)
                        if remaining_ttl > 0:
                            await redis.setex(
                                cache_key,
                                remaining_ttl,
                                json.dumps(entry.to_dict())
                            )
                    except Exception as e:
                        # Non-critical, don't fail the request
                        logger.debug(f"Redis memory-hit sync error (non-critical): {e}")

                return {
                    "content": entry.response_content,
                    "model": entry.model,
                    "usage": entry.usage,
                    "cached": True,
                    "cache_type": "exact",
                    "retrieved_contexts": entry.retrieved_contexts,
                }

            # Try Redis for exact match
            redis = await self._get_redis()
            if redis:
                try:
                    cached_data = await redis.get(cache_key)
                    if cached_data:
                        entry = LLMCacheEntry.from_dict(json.loads(cached_data))
                        if not entry.is_expired:
                            # Use lock for thread-safe updates
                            async with self._lock:
                                # Update memory cache
                                self._memory_cache[cache_key] = entry
                                if entry.embedding:
                                    self._embedding_index[query_hash] = entry.embedding
                                entry.hit_count += 1
                                self._stats["exact_hits"] += 1

                            # Persist updated hit_count back to Redis
                            # Calculate remaining TTL to preserve expiration
                            remaining_ttl = await redis.ttl(cache_key)
                            if remaining_ttl > 0:
                                try:
                                    await redis.setex(
                                        cache_key,
                                        remaining_ttl,
                                        json.dumps(entry.to_dict())
                                    )
                                except Exception as e:
                                    logger.warning(f"Redis hit_count update error: {e}")

                            logger.info(f"LLM cache Redis exact hit for {query_hash[:8]}...")
                            return {
                                "content": entry.response_content,
                                "model": entry.model,
                                "usage": entry.usage,
                                "cached": True,
                                "cache_type": "exact_redis",
                                "retrieved_contexts": entry.retrieved_contexts,
                            }
                except Exception as e:
                    logger.warning(f"Redis get error: {e}")

            # Try semantic similarity matching
            if use_semantic and self.config.use_semantic_cache:
                query_embedding = await self._compute_embedding(query)
                if query_embedding:
                    semantic_match = await self._find_semantic_match(query_embedding)
                    if semantic_match:
                        # Use lock for thread-safe hit_count increment
                        async with self._lock:
                            semantic_match.hit_count += 1
                            self._stats["semantic_hits"] += 1
                        logger.info(f"LLM cache semantic hit for query")
                        return {
                            "content": semantic_match.response_content,
                            "model": semantic_match.model,
                            "usage": semantic_match.usage,
                            "cached": True,
                            "cache_type": "semantic",
                            "retrieved_contexts": semantic_match.retrieved_contexts,
                        }
            
            await self._increment_stat("misses")
            return None
            
        except Exception as e:
            logger.error(f"LLM cache get error: {e}")
            await self._increment_stat("errors")
            return None
    
    async def set(
        self,
        query: str,
        response_content: str,
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        usage: Optional[Dict[str, int]] = None,
        ttl: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        retrieved_contexts: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """
        Cache an LLM response.

        Args:
            query: The user query text
            response_content: The LLM response content
            model: Model name/ID
            temperature: Sampling temperature
            usage: Token usage stats
            ttl: Time-to-live in seconds
            metadata: Additional metadata to store
            retrieved_contexts: RAG contexts used to generate the response (for consistency)

        Returns:
            True if cached successfully
        """
        # Check if caching is enabled
        if not self.config.enabled:
            return False

        try:
            query_hash = self._generate_query_hash(query, model, temperature)
            cache_key = self._generate_cache_key(query_hash)
            effective_ttl = ttl or self.config.default_ttl

            # Compute embedding for semantic search
            embedding = None
            if self.config.use_semantic_cache:
                embedding = await self._compute_embedding(query)

            entry = LLMCacheEntry(
                key=cache_key,
                query_hash=query_hash,
                query_text=query,
                response_content=response_content,
                model=model,
                usage=usage or {},
                embedding=embedding,
                ttl=effective_ttl,
                metadata=metadata or {},
                retrieved_contexts=retrieved_contexts,
            )
            
            # Use lock for thread-safe cache modifications
            async with self._lock:
                # Evict if at capacity
                if len(self._memory_cache) >= self.config.max_entries:
                    await self._evict_entries()

                # Store in memory
                self._memory_cache[cache_key] = entry
                if embedding:
                    self._embedding_index[query_hash] = embedding
            
            # Store in Redis
            redis = await self._get_redis()
            if redis:
                try:
                    await redis.setex(
                        cache_key,
                        effective_ttl,
                        json.dumps(entry.to_dict())
                    )
                except Exception as e:
                    logger.warning(f"Redis set error: {e}")
            
            await self._increment_stat("sets")
            logger.debug(f"LLM response cached with key {query_hash[:8]}...")
            return True
            
        except Exception as e:
            logger.error(f"LLM cache set error: {e}")
            await self._increment_stat("errors")
            return False
    
    async def _evict_entries(self):
        """Evict oldest/least-used entries when at capacity. Must be called with lock held."""
        if not self._memory_cache:
            return

        # Sort by hit count (ascending) and created_at (ascending)
        sorted_entries = sorted(
            self._memory_cache.items(),
            key=lambda x: (x[1].hit_count, x[1].created_at)
        )

        # Remove bottom 10%
        evict_count = max(1, len(sorted_entries) // 10)
        for i in range(evict_count):
            key = sorted_entries[i][0]
            entry = self._memory_cache.pop(key, None)
            if entry:
                self._embedding_index.pop(entry.query_hash, None)

        logger.debug(f"Evicted {evict_count} LLM cache entries")
    
    async def clear(self, timeout_seconds: int = 25) -> int:
        """
        Clear all cached entries with batch limiting and timeout protection.

        Args:
            timeout_seconds: Maximum time for the operation (default 25s to leave buffer for 30s API timeout)

        Returns:
            Number of entries cleared
        """
        # Clear in-memory cache with lock for thread safety
        async with self._lock:
            memory_count = len(self._memory_cache)
            self._memory_cache.clear()
            self._embedding_index.clear()

        redis_count = 0
        redis = await self._get_redis()
        if redis:
            try:
                pattern = f"{self.config.redis_prefix}*"
                cursor = 0
                batch_size = 100
                start_time = time.time()

                while True:
                    # Check timeout
                    elapsed = time.time() - start_time
                    if elapsed > timeout_seconds:
                        logger.warning(
                            f"Cache clear timeout after {redis_count} Redis entries. "
                            f"Remaining entries will expire via TTL."
                        )
                        break

                    # Scan for keys
                    cursor, keys = await redis.scan(cursor, match=pattern, count=batch_size)

                    if keys:
                        # Delete in batches to avoid blocking
                        for i in range(0, len(keys), batch_size):
                            batch = keys[i:i + batch_size]
                            deleted = await redis.delete(*batch)
                            redis_count += deleted

                        # Log progress every 500 deletions
                        if redis_count % 500 == 0 and redis_count > 0:
                            logger.info(f"Cache clear progress: {redis_count} Redis entries deleted")

                    if cursor == 0:
                        break

            except Exception as e:
                logger.warning(f"Redis clear error: {e}")

        total_cleared = memory_count + redis_count
        logger.info(
            f"Cleared {total_cleared} LLM cache entries "
            f"(memory: {memory_count}, redis: {redis_count})"
        )
        return total_cleared
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_hits = self._stats["exact_hits"] + self._stats["semantic_hits"]
        total_requests = total_hits + self._stats["misses"]
        hit_rate = (total_hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "enabled": self.config.enabled,
            "exact_hits": self._stats["exact_hits"],
            "semantic_hits": self._stats["semantic_hits"],
            "total_hits": total_hits,
            "misses": self._stats["misses"],
            "sets": self._stats["sets"],
            "errors": self._stats["errors"],
            "hit_rate_percent": round(hit_rate, 2),
            "memory_entries": len(self._memory_cache),
            "embedding_entries": len(self._embedding_index),
            "config": {
                "enabled": self.config.enabled,
                "similarity_threshold": self.config.similarity_threshold,
                "ttl_seconds": self.config.default_ttl,
                "semantic_enabled": self.config.use_semantic_cache,
                "max_entries": self.config.max_entries,
            }
        }


# Global instance with settings-based configuration
def _create_cache() -> LLMResponseCache:
    """Create cache instance with settings."""
    try:
        config = LLMCacheConfig.from_settings()
        return LLMResponseCache(config)
    except Exception as e:
        logger.warning(f"Failed to load LLM cache config from settings: {e}")
        return LLMResponseCache()

llm_response_cache = _create_cache()
