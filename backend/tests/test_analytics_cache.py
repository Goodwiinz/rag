"""
Comprehensive tests for analytics caching system
"""

import pytest
import json
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

from src.cache.analytics_cache import (
    AnalyticsCache, CacheKey, CacheTTL,
    get_analytics_cache, cached_analytics, invalidate_analytics_cache
)
from src.cache.cache_keys import CacheKeyBuilder, CacheKeyPattern, CacheKeyValidator
from src.exceptions.analytics_exceptions import CacheError


class TestCacheKey:
    """Test cache key generation and management"""

    def test_cache_key_generation(self):
        """Test cache key generation"""
        key = CacheKey(
            prefix="analytics",
            organization_id="org123",
            data_type="quality_metrics",
            filters={"date_range": "30d", "document_type": "pdf"}
        )

        generated_key = key.generate_key()

        assert generated_key.startswith("analytics:analytics:quality_metrics:org123:")
        assert "org123" in generated_key
        assert "quality_metrics" in generated_key

    def test_cache_key_consistency(self):
        """Test that same parameters generate same keys"""
        key1 = CacheKey(
            prefix="analytics",
            organization_id="org123",
            data_type="quality_metrics",
            filters={"date_range": "30d", "document_type": "pdf"}
        )

        key2 = CacheKey(
            prefix="analytics",
            organization_id="org123",
            data_type="quality_metrics",
            filters={"document_type": "pdf", "date_range": "30d"}  # Different order
        )

        assert key1.generate_key() == key2.generate_key()

    def test_cache_key_with_time_range(self):
        """Test cache key generation with time range"""
        time_range = ("2024-01-01", "2024-01-31")
        key = CacheKey(
            prefix="analytics",
            organization_id="org123",
            data_type="quality_metrics",
            filters={},
            time_range=time_range
        )

        generated_key = key.generate_key()
        assert generated_key.startswith("analytics:analytics:quality_metrics:org123:")


class TestCacheKeyBuilder:
    """Test cache key builder utilities"""

    def test_build_quality_metrics_key(self):
        """Test building quality metrics cache key"""
        key = CacheKeyBuilder.build_quality_metrics_key(
            organization_id="org123",
            document_id="doc456",
            filters={"type": "pdf"}
        )

        assert key.startswith("analytics:quality:document:org123:")
        assert "doc456" in key

    def test_build_user_behavior_key(self):
        """Test building user behavior cache key"""
        key = CacheKeyBuilder.build_user_behavior_key(
            organization_id="org123",
            user_id="user789",
            entity_type="session"
        )

        assert key.startswith("analytics:behavior:session:org123:")
        assert "user789" in key

    def test_build_performance_metrics_key(self):
        """Test building performance metrics cache key"""
        key = CacheKeyBuilder.build_performance_metrics_key(
            organization_id="org123",
            component="api"
        )

        assert key.startswith("analytics:perf:system:org123:")
        assert "api" in key

    def test_build_dashboard_key(self):
        """Test building dashboard cache key"""
        key = CacheKeyBuilder.build_dashboard_key(
            organization_id="org123",
            dashboard_type="quality",
            filters={"time_range": "30d"}
        )

        assert key.startswith("analytics:dashboard:quality:org123:")

    def test_normalize_filters(self):
        """Test filter normalization"""
        filters1 = {"date_range": "30d", "type": ["pdf", "docx"]}
        filters2 = {"type": ["docx", "pdf"], "date_range": "30d"}  # Different order

        key1 = CacheKeyBuilder.build_quality_metrics_key(
            organization_id="org123",
            filters=filters1
        )

        key2 = CacheKeyBuilder.build_quality_metrics_key(
            organization_id="org123",
            filters=filters2
        )

        assert key1 == key2

    def test_normalize_time_range(self):
        """Test time range normalization"""
        time_range_str = ("2024-01-01", "2024-01-31")
        time_range_dt = (
            datetime(2024, 1, 1),
            datetime(2024, 1, 31)
        )

        key1 = CacheKeyBuilder.build_quality_metrics_key(
            organization_id="org123",
            time_range=time_range_str
        )

        key2 = CacheKeyBuilder.build_quality_metrics_key(
            organization_id="org123",
            time_range=time_range_dt
        )

        assert key1 == key2


class TestCacheKeyPattern:
    """Test cache key patterns"""

    def test_organization_pattern(self):
        """Test organization pattern generation"""
        pattern = CacheKeyPattern.organization_pattern("org123")
        assert "*:org123:*" in pattern

    def test_quality_metrics_pattern(self):
        """Test quality metrics pattern"""
        pattern = CacheKeyPattern.quality_metrics_pattern()
        assert "quality" in pattern
        assert "*" in pattern

    def test_user_behavior_pattern(self):
        """Test user behavior pattern"""
        pattern = CacheKeyPattern.user_behavior_pattern("org123")
        assert "behavior" in pattern
        assert "org123" in pattern


class TestCacheKeyValidator:
    """Test cache key validation"""

    def test_valid_key_validation(self):
        """Test valid key validation"""
        valid_key = "analytics:quality:document:org123:hash"
        assert CacheKeyValidator.is_valid_key(valid_key) is True

    def test_invalid_key_validation(self):
        """Test invalid key validation"""
        invalid_keys = [
            "",
            "invalid",
            "invalid:format",
            "otherprefix:quality:document:org123:hash"
        ]

        for key in invalid_keys:
            assert CacheKeyValidator.is_valid_key(key) is False

    def test_extract_organization_id(self):
        """Test organization ID extraction"""
        key = "analytics:quality:document:org123:hash"
        org_id = CacheKeyValidator.extract_organization_id(key)
        assert org_id == "org123"

    def test_extract_service(self):
        """Test service extraction"""
        key = "analytics:quality:document:org123:hash"
        service = CacheKeyValidator.extract_service(key)
        assert service == "quality"

    def test_extract_entity_type(self):
        """Test entity type extraction"""
        key = "analytics:quality:document:org123:hash"
        entity_type = CacheKeyValidator.extract_entity_type(key)
        assert entity_type == "document"

    def test_group_keys_by_organization(self):
        """Test grouping keys by organization"""
        keys = [
            "analytics:quality:document:org123:hash1",
            "analytics:behavior:session:org123:hash2",
            "analytics:perf:system:org456:hash3",
            "analytics:quality:document:org123:hash4"
        ]

        grouped = CacheKeyValidator.group_keys_by_organization(keys)

        assert "org123" in grouped
        assert "org456" in grouped
        assert len(grouped["org123"]) == 3
        assert len(grouped["org456"]) == 1


class TestAnalyticsCache:
    """Test analytics cache functionality"""

    @pytest.fixture
    def mock_config(self):
        """Mock analytics configuration"""
        config = Mock()
        config.redis_analytics_url = None  # Force fallback cache
        return config

    @pytest.fixture
    def cache(self, mock_config):
        """Create cache instance"""
        with patch('src.cache.analytics_cache.get_analytics_config', return_value=mock_config):
            return AnalyticsCache()

    @pytest.mark.asyncio
    async def test_cache_set_and_get(self, cache):
        """Test basic cache set and get operations"""
        key = "test:key"
        value = {"data": "test_value", "timestamp": datetime.utcnow().isoformat()}

        # Set value
        result = await cache.set(key, value, ttl=60)
        assert result is True

        # Get value
        retrieved = await cache.get(key)
        assert retrieved == value

    @pytest.mark.asyncio
    async def test_cache_miss(self, cache):
        """Test cache miss scenario"""
        key = "nonexistent:key"

        result = await cache.get(key)
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_delete(self, cache):
        """Test cache delete operation"""
        key = "test:delete:key"
        value = {"data": "test"}

        # Set value
        await cache.set(key, value, ttl=60)
        assert await cache.get(key) == value

        # Delete value
        result = await cache.delete(key)
        assert result is True

        # Verify deletion
        assert await cache.get(key) is None

    @pytest.mark.asyncio
    async def test_cache_expiry(self, cache):
        """Test cache expiration"""
        key = "test:expiry:key"
        value = {"data": "test"}

        # Set value with short TTL
        await cache.set(key, value, ttl=1)
        assert await cache.get(key) == value

        # Wait for expiry
        await asyncio.sleep(2)

        # Value should be expired
        assert await cache.get(key) is None

    @pytest.mark.asyncio
    async def test_analytics_data_caching(self, cache):
        """Test analytics data caching functionality"""
        organization_id = "org123"
        data_type = "quality_metrics"
        filters = {"date_range": "30d", "document_type": "pdf"}
        data = {"metrics": [{"score": 0.85}, {"score": 0.90}]}

        # Set analytics data
        result = await cache.set_analytics_data(
            organization_id=organization_id,
            data_type=data_type,
            data=data,
            filters=filters
        )
        assert result is True

        # Get analytics data
        retrieved = await cache.get_analytics_data(
            organization_id=organization_id,
            data_type=data_type,
            filters=filters
        )
        assert retrieved == data

    @pytest.mark.asyncio
    async def test_invalidate_organization_data(self, cache):
        """Test organization data invalidation"""
        org_id = "org123"

        # Set multiple cache entries for organization
        await cache.set_analytics_data(org_id, "quality_metrics", {"data": 1}, {})
        await cache.set_analytics_data(org_id, "user_behavior", {"data": 2}, {})
        await cache.set_analytics_data("org456", "quality_metrics", {"data": 3}, {})

        # Invalidate organization data
        invalidated_count = await cache.invalidate_organization_data(org_id)
        assert invalidated_count >= 0

        # Verify organization data is gone
        assert await cache.get_analytics_data(org_id, "quality_metrics", {}) is None
        assert await cache.get_analytics_data(org_id, "user_behavior", {}) is None

        # Verify other organization data remains
        assert await cache.get_analytics_data("org456", "quality_metrics", {}) is not None

    @pytest.mark.asyncio
    async def test_invalidate_data_type(self, cache):
        """Test data type invalidation"""
        # Set multiple cache entries
        await cache.set_analytics_data("org123", "quality_metrics", {"data": 1}, {})
        await cache.set_analytics_data("org456", "quality_metrics", {"data": 2}, {})
        await cache.set_analytics_data("org123", "user_behavior", {"data": 3}, {})

        # Invalidate data type
        invalidated_count = await cache.invalidate_data_type("quality_metrics")
        assert invalidated_count >= 0

        # Verify quality metrics are gone
        assert await cache.get_analytics_data("org123", "quality_metrics", {}) is None
        assert await cache.get_analytics_data("org456", "quality_metrics", {}) is None

        # Verify other data type remains
        assert await cache.get_analytics_data("org123", "user_behavior", {}) is not None

    @pytest.mark.asyncio
    async def test_get_cache_stats(self, cache):
        """Test cache statistics"""
        # Set some cache data
        await cache.set("test:stats:1", {"data": 1}, ttl=60)
        await cache.set("test:stats:2", {"data": 2}, ttl=60)

        stats = await cache.get_cache_stats()

        assert "redis_connected" in stats
        assert "fallback_cache_size" in stats
        assert stats["fallback_cache_size"] >= 2

    @pytest.mark.asyncio
    async def test_health_check(self, cache):
        """Test cache health check"""
        health = await cache.health_check()

        assert "status" in health
        assert "redis_connected" in health
        assert "fallback_available" in health
        assert health["status"] in ["healthy", "degraded", "unhealthy"]

    def test_get_default_ttl(self, cache):
        """Test default TTL retrieval"""
        quality_ttl = cache._get_default_ttl("quality_scores")
        assert quality_ttl == CacheTTL.QUALITY_SCORES

        dashboard_ttl = cache._get_default_ttl("dashboard_data")
        assert dashboard_ttl == CacheTTL.DASHBOARD_DATA

        unknown_ttl = cache._get_default_ttl("unknown_type")
        assert unknown_ttl == CacheTTL.AGGREGATED_METRICS


class TestCacheDecorator:
    """Test cache decorator functionality"""

    @pytest.mark.asyncio
    async def test_cached_analytics_decorator(self):
        """Test cached analytics decorator"""
        call_count = 0

        @cached_analytics("test_data_type", ttl=60)
        async def test_function(organization_id, filters=None):
            nonlocal call_count
            call_count += 1
            return {"data": "test_result", "call_count": call_count}

        # First call should execute function
        result1 = await test_function("org123", {"type": "pdf"})
        assert result1["call_count"] == 1

        # Second call should use cache
        result2 = await test_function("org123", {"type": "pdf"})
        assert result2["call_count"] == 1  # Same call count
        assert result2["data"] == "test_result"

        # Different filters should execute function
        result3 = await test_function("org123", {"type": "docx"})
        assert result3["call_count"] == 2  # New call

    @pytest.mark.asyncio
    async def test_cached_analytics_decorator_no_organization(self):
        """Test cached decorator with no organization_id"""
        call_count = 0

        @cached_analytics("test_data_type", ttl=60)
        async def test_function(data=None):
            nonlocal call_count
            call_count += 1
            return {"data": data, "call_count": call_count}

        # Calls without organization_id should not be cached
        result1 = await test_function("test1")
        assert result1["call_count"] == 1

        result2 = await test_function("test2")
        assert result2["call_count"] == 2  # Should execute again


class TestCacheIntegration:
    """Test cache integration with mock Redis"""

    @pytest.mark.asyncio
    @patch('src.cache.analytics_cache.REDIS_AVAILABLE', True)
    @patch('src.cache.analytics_cache.redis')
    async def test_redis_integration(self, mock_redis):
        """Test Redis integration"""
        # Setup mock Redis client
        mock_client = AsyncMock()
        mock_redis.from_url.return_value = mock_client
        mock_client.ping.return_value = True

        # Create cache with Redis
        with patch('src.cache.analytics_cache.get_analytics_config') as mock_config:
            mock_config.return_value.redis_analytics_url = "redis://localhost:6379"
            cache = AnalyticsCache()
            await cache._init_redis()

        assert cache._connected is True
        assert cache.redis_client == mock_client

        # Test Redis operations
        test_value = {"data": "test"}
        serialized = b'{"data": "test"}'  # Mock serialized value

        mock_client.get.return_value = serialized
        mock_client.setex.return_value = True

        # Test get
        with patch('pickle.loads', return_value=test_value):
            result = await cache.get("test:key")
            assert result == test_value
            mock_client.get.assert_called_once_with("test:key")

        # Test set
        with patch('pickle.dumps', return_value=serialized):
            result = await cache.set("test:key", test_value, ttl=60)
            assert result is True
            mock_client.setex.assert_called_once_with("test:key", 60, serialized)

    @pytest.mark.asyncio
    async def test_cache_warming(self):
        """Test cache warming functionality"""
        cache = AnalyticsCache()

        # Mock the cache warming function
        with patch.object(cache, 'set', new_callable=AsyncMock) as mock_set:
            mock_set.return_value = True

            from src.cache.analytics_cache import warm_organization_cache
            warmed_count = await warm_organization_cache("org123", days=7)

            assert warmed_count > 0
            assert mock_set.call_count > 0

    @pytest.mark.asyncio
    async def test_cache_invalidation_functions(self):
        """Test cache invalidation utility functions"""
        cache = AnalyticsCache()

        with patch.object(cache, 'invalidate_organization_data', new_callable=AsyncMock) as mock_invalidate:
            mock_invalidate.return_value = 5

            from src.cache.analytics_cache import invalidate_analytics_cache

            # Test organization-specific invalidation
            await invalidate_analytics_cache(organization_id="org123")
            mock_invalidate.assert_called_once_with("org123")

            # Test full invalidation
            mock_invalidate.reset_mock()
            with patch.object(cache, 'invalidate_pattern', new_callable=AsyncMock) as mock_pattern:
                mock_pattern.return_value = 10

                await invalidate_analytics_cache()
                mock_pattern.assert_called_once_with("analytics:*")


class TestCacheErrorHandling:
    """Test cache error handling"""

    @pytest.mark.asyncio
    async def test_redis_connection_failure(self):
        """Test handling of Redis connection failures"""
        with patch('src.cache.analytics_cache.REDIS_AVAILABLE', True):
            with patch('src.cache.analytics_cache.redis.from_url', side_effect=Exception("Connection failed")):
                with patch('src.cache.analytics_cache.get_analytics_config') as mock_config:
                    mock_config.return_value.redis_analytics_url = "redis://localhost:6379"
                    cache = AnalyticsCache()

                assert cache._connected is False
                assert cache.redis_client is None

    @pytest.mark.asyncio
    async def test_cache_operation_errors(self):
        """Test handling of cache operation errors"""
        cache = AnalyticsCache()

        # Mock fallback cache to raise an exception
        with patch.object(cache, '_get_fallback_key', side_effect=Exception("Cache error")):
            # Operations should not raise exceptions
            result = await cache.get("test:key")
            assert result is None

            result = await cache.set("test:key", "value", ttl=60)
            assert result is False

            result = await cache.delete("test:key")
            assert result is False

    @pytest.mark.asyncio
    async def test_deserialization_errors(self):
        """Test handling of deserialization errors"""
        cache = AnalyticsCache()

        # Set valid data
        await cache.set("test:key", {"valid": "data"}, ttl=60)

        # Mock deserialization to raise an exception
        with patch('pickle.loads', side_effect=Exception("Deserialization failed")):
            # Should return None and log error
            result = await cache.get("test:key")
            assert result is None


if __name__ == "__main__":
    pytest.main([__file__])