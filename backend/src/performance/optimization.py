"""
Performance optimization utilities and strategies for the RAG system
"""

import asyncio
import time
import functools
import hashlib
import json
from typing import Dict, List, Optional, Any, Callable, Union, AsyncGenerator
from collections import defaultdict
from dataclasses import dataclass
from contextlib import asynccontextmanager
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import logging
import psutil
import gc
import gzip
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from fastapi import HTTPException
import aioredis

logger = logging.getLogger(__name__)

@dataclass
class CacheConfig:
    """Cache configuration settings"""
    ttl: int = 300  # 5 minutes default
    max_size: int = 1000
    compression: bool = True
    serializer: str = 'json'  # 'json' only for security
    key_prefix: str = 'rag_cache'

class SmartCache:
    """Intelligent multi-level caching system"""

    def __init__(self, redis_client: redis.Redis, config: CacheConfig = None):
        self.redis_client = redis_client
        self.config = config or CacheConfig()
        self.local_cache: Dict[str, Dict] = {}
        self.cache_stats = defaultdict(lambda: {'hits': 0, 'misses': 0, 'sets': 0})
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._last_cleanup = time.time()
        self._cleanup_interval = 60  # Cleanup every minute

    def _generate_key(self, key_parts: List[Any]) -> str:
        """Generate consistent cache key from key parts"""
        key_str = ':'.join(str(part) for part in key_parts)
        key_hash = hashlib.md5(key_str.encode()).hexdigest()
        return f"{self.config.key_prefix}:{key_hash}"

    def _serialize_value(self, value: Any) -> bytes:
        """Serialize value for storage using secure JSON"""
        data = json.dumps(value, default=str, ensure_ascii=False).encode('utf-8')

        if self.config.compression:
            data = gzip.compress(data)

        return data

    def _deserialize_value(self, data: bytes) -> Any:
        """Deserialize value from storage using secure JSON"""
        try:
            if self.config.compression:
                data = gzip.decompress(data)

            return json.loads(data.decode('utf-8'))

        except Exception as e:
            logger.error(f"Cache deserialization error: {e}")
            return None

    async def get(self, key_parts: List[Any]) -> Optional[Any]:
        """Get value from cache (local first, then Redis)"""
        key = self._generate_key(key_parts)

        # Check local cache first
        if key in self.local_cache:
            entry = self.local_cache[key]
            if time.time() < entry['expires']:
                self.cache_stats[key]['hits'] += 1
                return entry['value']
            else:
                del self.local_cache[key]

        # Check Redis cache
        try:
            data = await self.redis_client.get(key)
            if data:
                value = self._deserialize_value(data)
                if value is not None:
                    # Store in local cache
                    self.local_cache[key] = {
                        'value': value,
                        'expires': time.time() + self.config.ttl
                    }
                    self.cache_stats[key]['hits'] += 1
                    return value
        except Exception as e:
            logger.error(f"Redis cache get error: {e}")

        self.cache_stats[key]['misses'] += 1
        return None

    async def set(self, key_parts: List[Any], value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache (both local and Redis)"""
        key = self._generate_key(key_parts)
        ttl = ttl or self.config.ttl

        # Set in local cache
        self.local_cache[key] = {
            'value': value,
            'expires': time.time() + ttl
        }

        # Set in Redis
        try:
            data = self._serialize_value(value)
            await self.redis_client.setex(key, ttl, data)
            self.cache_stats[key]['sets'] += 1
            return True
        except Exception as e:
            logger.error(f"Redis cache set error: {e}")
            return False

    async def delete(self, key_parts: List[Any]) -> bool:
        """Delete value from cache"""
        key = self._generate_key(key_parts)

        # Delete from local cache
        if key in self.local_cache:
            del self.local_cache[key]

        # Delete from Redis
        try:
            await self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis cache delete error: {e}")
            return False

    async def clear_pattern(self, pattern: str) -> int:
        """Clear cache entries matching pattern"""
        try:
            # Clear from Redis
            keys = await self.redis_client.keys(f"{self.config.key_prefix}:*{pattern}*")
            if keys:
                deleted = await self.redis_client.delete(*keys)
            else:
                deleted = 0

            # Clear from local cache
            keys_to_delete = [
                k for k in self.local_cache.keys()
                if pattern in k
            ]
            for k in keys_to_delete:
                del self.local_cache[k]

            return deleted
        except Exception as e:
            logger.error(f"Cache clear pattern error: {e}")
            return 0

    async def cleanup_expired(self):
        """Clean up expired local cache entries"""
        current_time = time.time()
        if current_time - self._last_cleanup < self._cleanup_interval:
            return

        expired_keys = [
            k for k, v in self.local_cache.items()
            if current_time >= v['expires']
        ]

        for k in expired_keys:
            del self.local_cache[k]

        self._last_cleanup = current_time

    def get_stats(self) -> Dict[str, Dict]:
        """Get cache statistics"""
        return dict(self.cache_stats)

def smart_cache(
    cache: SmartCache,
    key_parts: List[Any],
    ttl: Optional[int] = None,
    cache_on_success: bool = True
):
    """Decorator for smart caching function results"""
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = key_parts + [str(arg) for arg in args] + [f"{k}:{v}" for k, v in sorted(kwargs.items())]

            # Try to get from cache
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Execute function
            try:
                result = await func(*args, **kwargs)

                # Cache successful result
                if cache_on_success:
                    await cache.set(cache_key, result, ttl)

                return result
            except Exception as e:
                logger.error(f"Function execution error in cached wrapper: {e}")
                raise

        return wrapper
    return decorator

class DatabaseOptimizer:
    """Database query optimization utilities"""

    def __init__(self, db_session: AsyncSession, cache: SmartCache):
        self.db_session = db_session
        self.cache = cache
        self.query_stats = defaultdict(lambda: {
            'count': 0,
            'total_time': 0,
            'avg_time': 0,
            'slow_queries': 0
        })

    @asynccontextmanager
    async def optimized_query(self, query_name: str, cache_key: Optional[List[Any]] = None, cache_ttl: int = 300):
        """Execute optimized database query with caching"""
        start_time = time.time()

        # Try cache first if cache_key provided
        if cache_key:
            cached_result = await self.cache.get(['query'] + cache_key)
            if cached_result is not None:
                yield cached_result
                return

        # Execute query
        try:
            yield
        finally:
            # Record query statistics
            duration = time.time() - start_time
            stats = self.query_stats[query_name]
            stats['count'] += 1
            stats['total_time'] += duration
            stats['avg_time'] = stats['total_time'] / stats['count']

            if duration > 1.0:  # Consider queries over 1s as slow
                stats['slow_queries'] += 1
                logger.warning(f"Slow query detected: {query_name} took {duration:.2f}s")

    async def execute_cached_query(
        self,
        query: str,
        params: Dict = None,
        cache_key_parts: Optional[List[Any]] = None,
        cache_ttl: int = 300
    ) -> List[Dict]:
        """Execute query with result caching"""
        cache_key_parts = cache_key_parts or [query, str(params or {})]
        cache_key = ['db_query'] + cache_key_parts

        # Try cache
        cached_result = await self.cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        # Execute query
        start_time = time.time()
        try:
            result = await self.db_session.execute(text(query), params or {})
            rows = result.fetchall()
            result_dicts = [dict(row) for row in rows]

            # Cache result
            await self.cache.set(cache_key, result_dicts, cache_ttl)

            logger.debug(f"Query executed in {time.time() - start_time:.3f}s: {query[:100]}...")
            return result_dicts

        except Exception as e:
            logger.error(f"Query execution error: {e}")
            raise

    def get_query_stats(self) -> Dict[str, Dict]:
        """Get query performance statistics"""
        return dict(self.query_stats)

class AsyncOptimizer:
    """Async processing optimization utilities"""

    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.semaphore = asyncio.Semaphore(max_workers * 2)

    async def run_in_background(self, func: Callable, *args, **kwargs) -> Any:
        """Run CPU-intensive function in background thread"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, func, *args, **kwargs)

    async def batch_process(
        self,
        items: List[Any],
        processor: Callable,
        batch_size: int = 10,
        max_concurrent: int = 5
    ) -> List[Any]:
        """Process items in batches with concurrency control"""
        results = []
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_batch(batch):
            async with semaphore:
                if asyncio.iscoroutinefunction(processor):
                    return await processor(batch)
                else:
                    return await self.run_in_background(processor, batch)

        # Create batches
        batches = [items[i:i + batch_size] for i in range(0, len(items), batch_size)]

        # Process batches concurrently
        tasks = [process_batch(batch) for batch in batches]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten results
        for batch_result in batch_results:
            if isinstance(batch_result, Exception):
                logger.error(f"Batch processing error: {batch_result}")
            else:
                results.extend(batch_result if isinstance(batch_result, list) else [batch_result])

        return results

    async def parallel_map(
        self,
        func: Callable,
        items: List[Any],
        max_concurrent: int = 10
    ) -> List[Any]:
        """Map function over items in parallel"""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_item(item):
            async with semaphore:
                if asyncio.iscoroutinefunction(func):
                    return await func(item)
                else:
                    return await self.run_in_background(func, item)

        tasks = [process_item(item) for item in items]
        return await asyncio.gather(*tasks, return_exceptions=True)

class MemoryOptimizer:
    """Memory usage optimization utilities"""

    @staticmethod
    def optimize_gc():
        """Optimize garbage collection"""
        # Run garbage collection
        collected = gc.collect()
        logger.debug(f"Garbage collection collected {collected} objects")

        # Get memory stats
        memory_info = psutil.virtual_memory()
        process = psutil.Process()
        process_memory = process.memory_info()

        return {
            'collected_objects': collected,
            'system_memory_percent': memory_info.percent,
            'process_memory_mb': process_memory.rss / 1024 / 1024,
            'process_memory_percent': process_memory.percent
        }

    @staticmethod
    def get_memory_usage() -> Dict[str, float]:
        """Get detailed memory usage information"""
        process = psutil.Process()
        memory_info = process.memory_info()
        memory_percent = process.memory_percent()

        return {
            'rss_mb': memory_info.rss / 1024 / 1024,
            'vms_mb': memory_info.vms / 1024 / 1024,
            'percent': memory_percent,
            'available_mb': psutil.virtual_memory().available / 1024 / 1024
        }

    @staticmethod
    async def memory_monitor(threshold_mb: float = 1000, check_interval: int = 30):
        """Monitor memory usage and optimize when threshold exceeded"""
        while True:
            try:
                memory_usage = MemoryOptimizer.get_memory_usage()

                if memory_usage['rss_mb'] > threshold_mb:
                    logger.warning(f"Memory usage high: {memory_usage['rss_mb']:.2f}MB")

                    # Run garbage collection
                    gc_stats = MemoryOptimizer.optimize_gc()
                    logger.info(f"Memory optimization: {gc_stats}")

                await asyncio.sleep(check_interval)
            except Exception as e:
                logger.error(f"Memory monitoring error: {e}")
                await asyncio.sleep(check_interval)

class VectorOptimizer:
    """Vector operations optimization utilities"""

    @staticmethod
    def batch_normalize(vectors: List[np.ndarray], batch_size: int = 1000) -> List[np.ndarray]:
        """Normalize vectors in batches for better performance"""
        normalized = []

        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]
            batch_array = np.array(batch)

            # Normalize batch
            norms = np.linalg.norm(batch_array, axis=1, keepdims=True)
            normalized_batch = batch_array / (norms + 1e-8)

            normalized.extend(normalized_batch)

        return normalized

    @staticmethod
    async def similarity_search_optimized(
        query_vector: np.ndarray,
        vectors: np.ndarray,
        top_k: int = 10,
        batch_size: int = 1000
    ) -> List[tuple]:
        """Optimized similarity search with batching"""
        similarities = []

        # Calculate similarities in batches
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]

            # Calculate cosine similarity
            query_norm = query_vector / (np.linalg.norm(query_vector) + 1e-8)
            batch_norms = batch / (np.linalg.norm(batch, axis=1, keepdims=True) + 1e-8)
            batch_similarities = np.dot(batch_norms, query_norm)

            # Store results with indices
            for j, similarity in enumerate(batch_similarities):
                similarities.append((i + j, float(similarity)))

        # Sort and return top_k
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]

# Global optimization instances
def create_optimization_instances(redis_client: redis.Redis) -> Dict[str, Any]:
    """Create global optimization instances"""
    cache_config = CacheConfig(
        ttl=300,
        max_size=10000,
        compression=True,
        serializer='json'
    )

    smart_cache = SmartCache(redis_client, cache_config)
    async_optimizer = AsyncOptimizer(max_workers=4)

    return {
        'cache': smart_cache,
        'async_optimizer': async_optimizer,
        'memory_optimizer': MemoryOptimizer(),
        'vector_optimizer': VectorOptimizer()
    }