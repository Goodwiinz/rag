"""
Unit tests for User Behavior Service
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import json

from src.services.user_behavior_service import (
    UserBehaviorService,
    BehaviorPattern,
    MetricTimeRange,
    SearchEvent,
    UserSession,
    BehaviorAnalysis
)
from src.schemas.user_behavior import (
    SearchEventCreate,
    SessionCreate,
    BehaviorPatternType
)


class TestUserBehaviorService:
    """Test suite for UserBehaviorService"""

    @pytest.fixture
    def service(self):
        """Create a UserBehaviorService instance for testing."""
        return UserBehaviorService()

    @pytest.fixture
    def sample_search_event(self):
        """Sample search event data for testing."""
        return SearchEvent(
            id="event-123",
            session_id="session-123",
            user_id="user-123",
            query="test search query",
            search_type="hybrid",
            results_count=15,
            response_time=245.5,
            clicked_results=[1, 3, 5],
            filters_applied={"date_range": "last_30_days"},
            page_number=1,
            sort_order="relevance",
            user_agent="Mozilla/5.0...",
            ip_address="192.168.1.100",
            timestamp=datetime.utcnow()
        )

    @pytest.fixture
    def sample_user_session(self):
        """Sample user session data for testing."""
        return UserSession(
            id="session-123",
            user_id="user-123",
            organization_id="org-123",
            start_time=datetime.utcnow() - timedelta(minutes=30),
            end_time=datetime.utcnow(),
            duration_seconds=1800,
            events_count=5,
            queries_count=3,
            clicks_count=12,
            bounce_rate=0.0,
            user_agent="Mozilla/5.0...",
            ip_address="192.168.1.100",
            is_active=False
        )

    # Test Initialization
    @pytest.mark.asyncio
    async def test_service_initialization(self, service):
        """Test service initialization."""
        assert service.cache_ttl == 3600
        assert service.session_cache == {}
        assert service.behavior_cache == {}
        assert service.redis_client is None

    # Test Session Management
    @pytest.mark.asyncio
    async def test_create_session(self, service, sample_user_session):
        """Test creating a user session."""
        with patch.object(service, '_store_session') as mock_store:
            mock_store.return_value = sample_user_session

            result = await service.create_session(
                user_id="user-123",
                organization_id="org-123",
                user_agent="Mozilla/5.0...",
                ip_address="192.168.1.100"
            )

            assert result.user_id == "user-123"
            assert result.organization_id == "org-123"
            assert result.is_active is True
            mock_store.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_session(self, service, sample_user_session):
        """Test retrieving a session."""
        session_id = "session-123"

        with patch.object(service, '_get_session_from_db') as mock_get:
            mock_get.return_value = sample_user_session

            result = await service.get_session(session_id)

            assert result.id == session_id
            assert result.user_id == "user-123"
            mock_get.assert_called_once_with(session_id)

    @pytest.mark.asyncio
    async def test_update_session(self, service, sample_user_session):
        """Test updating a session."""
        with patch.object(service, '_update_session_in_db') as mock_update:
            mock_update.return_value = True

            result = await service.update_session(
                session_id=sample_user_session.id,
                events_count=10,
                queries_count=5,
                is_active=False,
                end_time=datetime.utcnow()
            )

            assert result is True
            mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_end_session(self, service, sample_user_session):
        """Test ending a session."""
        with patch.object(service, 'update_session') as mock_update:
            mock_update.return_value = True

            result = await service.end_session(sample_user_session.id)

            assert result is True
            mock_update.assert_called_once_with(
                session_id=sample_user_session.id,
                is_active=False,
                end_time=pytest.ANY
            )

    # Test Search Event Tracking
    @pytest.mark.asyncio
    async def test_track_search_event(self, service, sample_search_event):
        """Test tracking a search event."""
        with patch.object(service, '_store_search_event') as mock_store:
            mock_store.return_value = sample_search_event

            result = await service.track_search_event(
                session_id="session-123",
                query="test search query",
                search_type="hybrid",
                results_count=15,
                response_time=245.5,
                user_id="user-123",
                clicked_results=[1, 3, 5],
                filters_applied={"date_range": "last_30_days"}
            )

            assert result.query == "test search query"
            assert result.search_type == "hybrid"
            assert result.results_count == 15
            mock_store.assert_called_once()

    @pytest.mark.asyncio
    async def test_track_search_event_validation(self, service):
        """Test search event validation."""
        # Test empty query
        with pytest.raises(ValueError, match="Query cannot be empty"):
            await service.track_search_event(
                session_id="session-123",
                query="",
                search_type="hybrid",
                results_count=15,
                response_time=245.5
            )

        # Test negative response time
        with pytest.raises(ValueError, match="Response time cannot be negative"):
            await service.track_search_event(
                session_id="session-123",
                query="test query",
                search_type="hybrid",
                results_count=15,
                response_time=-100
            )

        # Test negative results count
        with pytest.raises(ValueError, match="Results count cannot be negative"):
            await service.track_search_event(
                session_id="session-123",
                query="test query",
                search_type="hybrid",
                results_count=-5,
                response_time=245.5
            )

    @pytest.mark.asyncio
    async def test_get_search_events(self, service):
        """Test retrieving search events."""
        user_id = "user-123"
        time_range = MetricTimeRange.LAST_24H

        with patch.object(service, '_query_search_events_from_db') as mock_query:
            mock_events = [Mock(), Mock(), Mock()]
            mock_query.return_value = mock_events

            result = await service.get_search_events(
                user_id=user_id,
                time_range=time_range,
                limit=50
            )

            assert len(result) == 3
            mock_query.assert_called_once_with(
                user_id=user_id,
                time_range=time_range,
                limit=50
            )

    # Test Behavior Pattern Analysis
    @pytest.mark.asyncio
    async def test_analyze_behavior_patterns(self, service):
        """Test analyzing user behavior patterns."""
        user_id = "user-123"

        with patch.object(service, '_get_user_events') as mock_get_events:
            mock_events = [
                Mock(query="python tutorial", results_count=15, clicked_results=[1, 2]),
                Mock(query="machine learning", results_count=20, clicked_results=[3, 5, 7]),
                Mock(query="data science", results_count=12, clicked_results=[1])
            ]
            mock_get_events.return_value = mock_events

            with patch.object(service, '_classify_behavior_pattern') as mock_classify:
                mock_classify.return_value = BehaviorPatternType.RESEARCHER

                result = await service.analyze_behavior_patterns(user_id)

                assert result.pattern_type == BehaviorPatternType.RESEARCHER
                assert "confidence" in result
                assert "characteristics" in result
                mock_classify.assert_called_once()

    @pytest.mark.asyncio
    async def test_classify_behavior_pattern_power_user(self, service):
        """Test classifying power user behavior."""
        events = [
            Mock(query="advanced topic 1", results_count=20, clicked_results=[1, 3, 5]),
            Mock(query="advanced topic 2", results_count=25, clicked_results=[2, 4]),
            Mock(query="advanced topic 3", results_count=30, clicked_results=[1, 6, 8]),
        ]

        result = await service._classify_behavior_pattern(events)

        assert result.pattern_type == BehaviorPatternType.POWER_USER
        assert result.confidence > 0.7

    @pytest.mark.asyncio
    async def test_classify_behavior_pattern_casual_user(self, service):
        """Test classifying casual user behavior."""
        events = [
            Mock(query="simple query", results_count=10, clicked_results=[1]),
            Mock(query="another query", results_count=8, clicked_results=[]),
        ]

        result = await service._classify_behavior_pattern(events)

        assert result.pattern_type == BehaviorPatternType.CASUAL_USER
        assert result.confidence > 0.5

    @pytest.mark.asyncio
    async def test_classify_behavior_pattern_frustrated_user(self, service):
        """Test classifying frustrated user behavior."""
        events = [
            Mock(query="query 1", results_count=0, clicked_results=[]),
            Mock(query="query 2", results_count=0, clicked_results=[]),
            Mock(query="query 3", results_count=2, clicked_results=[]),
        ]

        result = await service._classify_behavior_pattern(events)

        assert result.pattern_type == BehaviorPatternType.FRUSTRATED_USER
        assert result.confidence > 0.6

    # Test Session Analysis
    @pytest.mark.asyncio
    async def test_get_session_analysis(self, service, sample_user_session):
        """Test getting session analysis."""
        with patch.object(service, '_get_session_events') as mock_get_events:
            mock_events = [
                Mock(query="query 1", response_time=200, clicked_results=[1]),
                Mock(query="query 2", response_time=300, clicked_results=[2, 3]),
                Mock(query="query 3", response_time=250, clicked_results=[1])
            ]
            mock_get_events.return_value = mock_events

            result = await service.get_session_analysis(sample_user_session.id)

            assert result["session_id"] == sample_user_session.id
            assert result["total_queries"] == 3
            assert result["avg_response_time"] == 250
            assert result["total_clicks"] == 4
            assert result["click_through_rate"] == pytest.approx(0.44, rel=1e-2)

    @pytest.mark.asyncio
    async def test_get_session_metrics(self, service):
        """Test getting session metrics."""
        organization_id = "org-123"
        time_range = MetricTimeRange.LAST_7D

        with patch.object(service, '_query_sessions_from_db') as mock_query:
            mock_sessions = [
                Mock(duration_seconds=1800, events_count=10, bounce_rate=0.0),
                Mock(duration_seconds=900, events_count=5, bounce_rate=1.0),
                Mock(duration_seconds=2400, events_count=15, bounce_rate=0.0),
            ]
            mock_query.return_value = mock_sessions

            result = await service.get_session_metrics(
                organization_id=organization_id,
                time_range=time_range
            )

            assert result["total_sessions"] == 3
            assert result["avg_duration"] == 1700
            assert result["avg_events_per_session"] == 10
            assert result["bounce_rate"] == pytest.approx(0.33, rel=1e-2)

    # Test User Insights
    @pytest.mark.asyncio
    async def test_get_user_insights(self, service):
        """Test getting user insights."""
        user_id = "user-123"

        with patch.object(service, 'analyze_behavior_patterns') as mock_analyze:
            mock_analyze.return_value = Mock(
                pattern_type=BehaviorPatternType.RESEARCHER,
                confidence=0.85,
                characteristics=["deep_dives", "multiple_queries"]
            )

            with patch.object(service, '_get_user_statistics') as mock_stats:
                mock_stats.return_value = {
                    "total_sessions": 15,
                    "total_queries": 45,
                    "avg_session_duration": 1200,
                    "favorite_search_types": ["hybrid", "semantic"]
                }

                result = await service.get_user_insights(user_id)

                assert result["behavior_pattern"] == BehaviorPatternType.RESEARCHER
                assert result["confidence"] == 0.85
                assert result["statistics"]["total_sessions"] == 15

    @pytest.mark.asyncio
    async def test_get_organization_behavior_trends(self, service):
        """Test getting organization behavior trends."""
        organization_id = "org-123"
        time_range = MetricTimeRange.LAST_30D

        with patch.object(service, '_query_behavior_trends') as mock_query:
            mock_trends = {
                "daily_sessions": [10, 15, 12, 18, 20],
                "behavior_patterns": {
                    "power_user": 15,
                    "casual_user": 45,
                    "researcher": 25,
                    "frustrated_user": 5
                },
                "popular_queries": [
                    {"query": "python tutorial", "count": 25},
                    {"query": "machine learning", "count": 18}
                ]
            }
            mock_query.return_value = mock_trends

            result = await service.get_organization_behavior_trends(
                organization_id=organization_id,
                time_range=time_range
            )

            assert "daily_sessions" in result
            assert "behavior_patterns" in result
            assert "popular_queries" in result
            assert len(result["popular_queries"]) == 2

    # Test Interaction Tracking
    @pytest.mark.asyncio
    async def test_track_interaction(self, service):
        """Test tracking user interactions."""
        with patch.object(service, '_store_interaction') as mock_store:
            mock_store.return_value = Mock(id="interaction-123")

            result = await service.track_interaction(
                session_id="session-123",
                user_id="user-123",
                interaction_type="result_click",
                target_id="result-456",
                metadata={"position": 1, "result_rank": 1}
            )

            assert result.id == "interaction-123"
            mock_store.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_interactions(self, service):
        """Test getting user interactions."""
        user_id = "user-123"
        interaction_type = "result_click"

        with patch.object(service, '_query_interactions_from_db') as mock_query:
            mock_interactions = [Mock(), Mock(), Mock()]
            mock_query.return_value = mock_interactions

            result = await service.get_user_interactions(
                user_id=user_id,
                interaction_type=interaction_type,
                limit=50
            )

            assert len(result) == 3
            mock_query.assert_called_once_with(
                user_id=user_id,
                interaction_type=interaction_type,
                limit=50
            )

    # Test Content Usage Analytics
    @pytest.mark.asyncio
    async def test_get_content_usage_analytics(self, service):
        """Test getting content usage analytics."""
        organization_id = "org-123"

        with patch.object(service, '_query_content_usage') as mock_query:
            mock_usage = [
                {"document_id": "doc-1", "access_count": 45, "unique_users": 12},
                {"document_id": "doc-2", "access_count": 32, "unique_users": 8},
                {"document_id": "doc-3", "access_count": 28, "unique_users": 6}
            ]
            mock_query.return_value = mock_usage

            result = await service.get_content_usage_analytics(organization_id)

            assert len(result) == 3
            assert result[0]["document_id"] == "doc-1"
            assert result[0]["access_count"] == 45

    # Test Performance Metrics
    @pytest.mark.asyncio
    async def test_get_engagement_metrics(self, service):
        """Test getting engagement metrics."""
        organization_id = "org-123"
        time_range = MetricTimeRange.LAST_7D

        with patch.object(service, '_calculate_engagement_metrics') as mock_calc:
            mock_metrics = {
                "daily_active_users": [45, 52, 48, 58, 62],
                "avg_session_duration": 1200,
                "return_user_rate": 0.65,
                "feature_adoption": {
                    "hybrid_search": 0.85,
                    "filters": 0.42,
                    "export": 0.15
                }
            }
            mock_calc.return_value = mock_metrics

            result = await service.get_engagement_metrics(
                organization_id=organization_id,
                time_range=time_range
            )

            assert "daily_active_users" in result
            assert "avg_session_duration" in result
            assert "return_user_rate" in result
            assert "feature_adoption" in result

    # Test Caching
    @pytest.mark.asyncio
    async def test_cache_session_data(self, service, mock_redis_client):
        """Test caching session data."""
        service.redis_client = mock_redis_client
        session_id = "session-123"
        session_data = {"user_id": "user-123", "start_time": "2025-10-09T21:41:00Z"}

        await service._cache_session_data(session_id, session_data)

        mock_redis_client.set.assert_called_once()
        mock_redis_client.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cached_session_data(self, service, mock_redis_client):
        """Test getting cached session data."""
        service.redis_client = mock_redis_client
        session_id = "session-123"
        cached_data = json.dumps({"user_id": "user-123"})

        mock_redis_client.get.return_value = cached_data

        result = await service._get_cached_session_data(session_id)

        assert result["user_id"] == "user-123"
        mock_redis_client.get.assert_called_once_with(session_id)

    # Test Error Handling
    @pytest.mark.asyncio
    async def test_database_error_handling(self, service):
        """Test handling of database errors."""
        with patch.object(service, '_store_search_event') as mock_store:
            mock_store.side_effect = Exception("Database connection failed")

            with pytest.raises(Exception, match="Database connection failed"):
                await service.track_search_event(
                    session_id="session-123",
                    query="test query",
                    search_type="hybrid",
                    results_count=15,
                    response_time=245.5
                )

    @pytest.mark.asyncio
    async def test_invalid_session_id(self, service):
        """Test handling of invalid session ID."""
        with patch.object(service, '_get_session_from_db') as mock_get:
            mock_get.return_value = None

            result = await service.get_session("invalid-session-id")

            assert result is None

    # Test Data Validation
    @pytest.mark.asyncio
    async def test_search_event_data_validation(self, service):
        """Test search event data validation."""
        # Test invalid search type
        with pytest.raises(ValueError, match="Invalid search type"):
            await service.track_search_event(
                session_id="session-123",
                query="test query",
                search_type="invalid_type",
                results_count=15,
                response_time=245.5
            )

        # Test invalid page number
        with pytest.raises(ValueError, match="Page number must be positive"):
            await service.track_search_event(
                session_id="session-123",
                query="test query",
                search_type="hybrid",
                results_count=15,
                response_time=245.5,
                page_number=0
            )

    # Test Performance
    @pytest.mark.asyncio
    async def test_batch_event_processing(self, service):
        """Test batch processing of search events."""
        import time

        events_data = [
            {
                "session_id": f"session_{i}",
                "query": f"query {i}",
                "search_type": "hybrid",
                "results_count": 15,
                "response_time": 200 + i,
                "user_id": "user-123"
            }
            for i in range(100)
        ]

        with patch.object(service, 'track_search_event') as mock_track:
            mock_track.return_value = Mock()

            start_time = time.time()
            results = await service.track_search_events_batch(events_data)
            end_time = time.time()

            assert len(results) == 100
            assert end_time - start_time < 10.0  # Should complete within 10 seconds

    # Test Privacy and Anonymization
    @pytest.mark.asyncio
    async def test_anonymize_user_data(self, service):
        """Test user data anonymization."""
        user_id = "user-123"
        retention_days = 30

        with patch.object(service, '_anonymize_user_events') as mock_anonymize:
            mock_anonymize.return_value = True

            result = await service.anonymize_user_data(user_id, retention_days)

            assert result is True
            mock_anonymize.assert_called_once_with(user_id, retention_days)

    @pytest.mark.asyncio
    async def test_export_user_data(self, service):
        """Test exporting user data (GDPR compliance)."""
        user_id = "user-123"

        with patch.object(service, '_get_all_user_data') as mock_get_data:
            mock_data = {
                "sessions": [{"id": "session-1", "start_time": "2025-10-09T21:41:00Z"}],
                "search_events": [{"query": "test query", "timestamp": "2025-10-09T21:41:00Z"}],
                "interactions": [{"type": "click", "timestamp": "2025-10-09T21:41:00Z"}]
            }
            mock_get_data.return_value = mock_data

            result = await service.export_user_data(user_id)

            assert "sessions" in result
            assert "search_events" in result
            assert "interactions" in result
            assert "export_timestamp" in result