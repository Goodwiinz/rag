"""
Redis caching layer for Evidence Agreement Meter

Caches stance classifications and evidence meters for fast retrieval
"""

import json
import logging
from typing import Dict, List, Optional
from uuid import UUID

import redis

from ...core.config import settings

logger = logging.getLogger(__name__)


class EvidenceCacheService:
    """Redis caching service for evidence meter data"""
    
    def __init__(self):
        self.redis_client = None
        self._connect()
    
    def _connect(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = redis.Redis.from_url(
                settings.REDIS_URL or "redis://localhost:6379/0",
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                health_check_interval=30,
            )
            # Test connection
            self.redis_client.ping()
            logger.info("Connected to Redis for evidence caching")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None
    
    def _ensure_connected(self) -> bool:
        """Ensure Redis connection is active"""
        if not self.redis_client:
            self._connect()
        
        if self.redis_client:
            try:
                self.redis_client.ping()
                return True
            except Exception as e:
                logger.warning(f"Redis connection lost, reconnecting: {e}")
                self._connect()
                return self.redis_client is not None
        
        return False
    
    def _serialize_data(self, data: dict) -> str:
        """Serialize data for Redis storage"""
        return json.dumps(data, default=str, ensure_ascii=False)
    
    def _deserialize_data(self, data: str) -> dict:
        """Deserialize data from Redis storage"""
        return json.loads(data)
    
    # Stance classification caching
    
    async def get_stance_classification(self, cache_key: str) -> Optional[Dict]:
        """Get cached stance classification"""
        if not self._ensure_connected():
            return None
        
        try:
            data = self.redis_client.get(cache_key)
            if data:
                result = self._deserialize_data(data)
                logger.debug(f"Cache hit for stance classification: {cache_key}")
                return result
            return None
        except Exception as e:
            logger.error(f"Failed to get stance classification from cache: {e}")
            return None
    
    async def set_stance_classification(
        self, cache_key: str, classification: Dict, ttl: int = 86400
    ) -> bool:
        """Set stance classification in cache"""
        if not self._ensure_connected():
            return False
        
        try:
            data = self._serialize_data(classification)
            result = self.redis_client.setex(cache_key, ttl, data)
            logger.debug(f"Cached stance classification: {cache_key} (TTL: {ttl}s)")
            return bool(result)
        except Exception as e:
            logger.error(f"Failed to cache stance classification: {e}")
            return False
    
    # Evidence meter caching
    
    def _generate_meter_cache_key(
        self, claim_hash: str, source_ids: List[str], model_version: str
    ) -> str:
        """Generate cache key for evidence meter"""
        # Sort source IDs for consistent caching
        sorted_sources = sorted(source_ids)
        sources_hash = str(hash("|".join(sorted_sources)))[:16]
        return f"meter:{claim_hash}:{sources_hash}:{model_version}"
    
    async def get_evidence_meter(
        self, claim_hash: str, source_ids: List[str], model_version: str
    ) -> Optional[Dict]:
        """Get cached evidence meter"""
        if not self._ensure_connected():
            return None
        
        cache_key = self._generate_meter_cache_key(claim_hash, source_ids, model_version)
        
        try:
            data = self.redis_client.get(cache_key)
            if data:
                result = self._deserialize_data(data)
                logger.debug(f"Cache hit for evidence meter: {cache_key}")
                return result
            return None
        except Exception as e:
            logger.error(f"Failed to get evidence meter from cache: {e}")
            return None
    
    async def set_evidence_meter(
        self, claim_hash: str, source_ids: List[str], model_version: str, 
        meter_data: Dict, ttl: int = 86400
    ) -> bool:
        """Set evidence meter in cache"""
        if not self._ensure_connected():
            return False
        
        cache_key = self._generate_meter_cache_key(claim_hash, source_ids, model_version)
        
        try:
            data = self._serialize_data(meter_data)
            result = self.redis_client.setex(cache_key, ttl, data)
            logger.debug(f"Cached evidence meter: {cache_key} (TTL: {ttl}s)")
            return bool(result)
        except Exception as e:
            logger.error(f"Failed to cache evidence meter: {e}")
            return False
    
    # Batch operations
    
    async def get_stance_classifications_batch(
        self, cache_keys: List[str]
    ) -> Dict[str, Optional[Dict]]:
        """Get multiple stance classifications from cache"""
        if not self._ensure_connected() or not cache_keys:
            return {key: None for key in cache_keys}
        
        try:
            # Use mget for efficient batch retrieval
            results = self.redis_client.mget(cache_keys)
            
            cache_results = {}
            for i, key in enumerate(cache_keys):
                if results[i]:
                    try:
                        cache_results[key] = self._deserialize_data(results[i])
                    except Exception as e:
                        logger.warning(f"Failed to deserialize cached data for {key}: {e}")
                        cache_results[key] = None
                else:
                    cache_results[key] = None
            
            hit_count = sum(1 for v in cache_results.values() if v is not None)
            logger.debug(f"Batch cache lookup: {hit_count}/{len(cache_keys)} hits")
            
            return cache_results
            
        except Exception as e:
            logger.error(f"Failed to get stance classifications batch: {e}")
            return {key: None for key in cache_keys}
    
    async def set_stance_classifications_batch(
        self, classifications: Dict[str, Dict], ttl: int = 86400
    ) -> bool:
        """Set multiple stance classifications in cache"""
        if not self._ensure_connected() or not classifications:
            return False
        
        try:
            pipe = self.redis_client.pipeline()
            
            for cache_key, classification in classifications.items():
                data = self._serialize_data(classification)
                pipe.setex(cache_key, ttl, data)
            
            results = pipe.execute()
            success_count = sum(1 for r in results if r)
            
            logger.debug(f"Batch cache set: {success_count}/{len(classifications)} successful")
            return success_count == len(classifications)
            
        except Exception as e:
            logger.error(f"Failed to set stance classifications batch: {e}")
            return False
    
    # Cache management
    
    async def invalidate_claim_cache(self, claim_hash: str) -> int:
        """Invalidate all cache entries for a claim"""
        if not self._ensure_connected():
            return 0
        
        try:
            # Find all keys for this claim
            patterns = [
                f"stance:{claim_hash}:*",
                f"meter:{claim_hash}:*",
            ]
            
            deleted_count = 0
            for pattern in patterns:
                keys = self.redis_client.keys(pattern)
                if keys:
                    deleted = self.redis_client.delete(*keys)
                    deleted_count += deleted
            
            logger.info(f"Invalidated {deleted_count} cache entries for claim {claim_hash}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to invalidate claim cache: {e}")
            return 0
    
    async def invalidate_source_cache(self, source_id: str) -> int:
        """Invalidate all cache entries for a source"""
        if not self._ensure_connected():
            return 0
        
        try:
            # Find stance classifications for this source
            pattern = f"stance:*:{source_id}:*"
            keys = self.redis_client.keys(pattern)
            
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(f"Invalidated {deleted} cache entries for source {source_id}")
                return deleted
            
            return 0
            
        except Exception as e:
            logger.error(f"Failed to invalidate source cache: {e}")
            return 0
    
    async def cleanup_old_model_versions(self, current_model_version: str) -> int:
        """Clean up cache entries from old model versions"""
        if not self._ensure_connected():
            return 0
        
        try:
            # Find all stance and meter keys
            all_keys = []
            for pattern in ["stance:*", "meter:*"]:
                keys = self.redis_client.keys(pattern)
                all_keys.extend(keys)
            
            # Filter for old model versions
            old_keys = []
            for key in all_keys:
                if key.endswith(f":{current_model_version}"):
                    continue  # Keep current version
                if any(key.endswith(f":{v}") for v in ["gpt-4o-mini", "gpt-4o", "gpt-3.5"]):
                    old_keys.append(key)  # Mark old versions for deletion
            
            if old_keys:
                deleted = self.redis_client.delete(*old_keys)
                logger.info(f"Cleaned up {deleted} cache entries from old model versions")
                return deleted
            
            return 0
            
        except Exception as e:
            logger.error(f"Failed to cleanup old model versions: {e}")
            return 0
    
    # Cache statistics
    
    async def get_cache_stats(self) -> Dict:
        """Get cache usage statistics"""
        if not self._ensure_connected():
            return {"error": "Redis not connected"}
        
        try:
            info = self.redis_client.info()
            
            # Count different key types
            stance_keys = len(self.redis_client.keys("stance:*"))
            meter_keys = len(self.redis_client.keys("meter:*"))
            
            return {
                "connected": True,
                "total_keys": info.get("db0", {}).get("keys", 0) if "db0" in info else 0,
                "stance_classifications": stance_keys,
                "evidence_meters": meter_keys,
                "memory_usage": info.get("used_memory_human", "unknown"),
                "hit_rate": info.get("keyspace_hits", 0) / max(
                    info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0), 1
                ),
            }
            
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {"error": str(e)}