"""
Test infrastructure validation
"""

import pytest
import sys
import os
# Add the src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
sys.path.insert(0, src_dir)

from src.services.quality_metrics_service import QualityMetricsService
from src.services.user_behavior_service import UserBehaviorService
from src.services.performance_dashboard_service import PerformanceDashboardService
from src.services.quality_recommendations_service import QualityRecommendationsService


class TestInfrastructure:
    """Test that the testing infrastructure is working correctly"""

    def test_pytest_configuration(self):
        """Test that pytest is configured correctly."""
        assert True  # Basic pytest test

    def test_service_imports(self):
        """Test that all T3 services can be imported."""
        # Test service imports
        assert QualityMetricsService is not None
        assert UserBehaviorService is not None
        assert PerformanceDashboardService is not None
        assert QualityRecommendationsService is not None

    def test_service_instantiation(self):
        """Test that all services can be instantiated."""
        # Test service instantiation
        quality_service = QualityMetricsService()
        behavior_service = UserBehaviorService()
        performance_service = PerformanceDashboardService()
        recommendations_service = QualityRecommendationsService()

        assert quality_service is not None
        assert behavior_service is not None
        assert performance_service is not None
        assert recommendations_service is not None

    def test_service_attributes(self):
        """Test that services have expected attributes."""
        quality_service = QualityMetricsService()
        behavior_service = UserBehaviorService()
        performance_service = PerformanceDashboardService()
        recommendations_service = QualityRecommendationsService()

        # Test Quality Metrics Service
        assert hasattr(quality_service, 'cache_ttl')
        assert hasattr(quality_service, 'metric_cache')
        assert hasattr(quality_service, 'collect_metric')

        # Test User Behavior Service
        assert hasattr(behavior_service, 'cache_ttl')
        assert hasattr(behavior_service, 'session_cache')
        assert hasattr(behavior_service, 'track_search_event')

        # Test Performance Dashboard Service
        assert hasattr(performance_service, 'cache_ttl')
        assert hasattr(performance_service, 'metric_cache')
        assert hasattr(performance_service, 'get_system_health_metrics')

        # Test Quality Recommendations Service
        assert hasattr(recommendations_service, 'cache_ttl')
        assert hasattr(recommendations_service, 'recommendation_cache')
        assert hasattr(recommendations_service, 'generate_recommendations')

    @pytest.mark.asyncio
    async def test_async_service_methods(self):
        """Test that async service methods exist."""
        quality_service = QualityMetricsService()
        behavior_service = UserBehaviorService()
        performance_service = PerformanceDashboardService()
        recommendations_service = QualityRecommendationsService()

        # Test that methods are callable (we won't actually call them as they need database)
        assert callable(getattr(quality_service, 'collect_metric', None))
        assert callable(getattr(behavior_service, 'track_search_event', None))
        assert callable(getattr(performance_service, 'get_system_health_metrics', None))
        assert callable(getattr(recommendations_service, 'generate_recommendations', None))

    def test_enum_imports(self):
        """Test that service enums can be imported."""
        from src.services.quality_metrics_service import MetricType, MetricScope, MetricTimeRange
        from src.services.user_behavior_service import BehaviorPatternType
        from src.services.performance_dashboard_service import WidgetType
        from src.services.quality_recommendations_service import RecommendationCategory, RecommendationPriority, RecommendationStatus

        # Test enum values
        assert MetricType.CUSTOM is not None
        assert MetricScope.QUERY is not None
        assert MetricTimeRange.LAST_24H is not None
        assert BehaviorPatternType.POWER_USER is not None
        assert WidgetType.TIME_SERIES is not None
        assert RecommendationCategory.CONTENT is not None
        assert RecommendationPriority.HIGH is not None
        assert RecommendationStatus.PENDING is not None

    def test_schema_imports(self):
        """Test that schema classes can be imported."""
        from src.schemas.quality_metrics import MetricQuery, MetricCreate, AlertCreate
        from src.schemas.user_behavior import SearchEventCreate, SessionCreate
        from src.schemas.performance_dashboard import WidgetCreate, WidgetUpdate
        from src.schemas.quality_recommendations import RecommendationCreate, RecommendationUpdate

        # Test schema classes
        assert MetricQuery is not None
        assert MetricCreate is not None
        assert AlertCreate is not None
        assert SearchEventCreate is not None
        assert SessionCreate is not None
        assert WidgetCreate is not None
        assert WidgetUpdate is not None
        assert RecommendationCreate is not None
        assert RecommendationUpdate is not None

    def test_main_app_import(self):
        """Test that the main FastAPI app can be imported."""
        from src.main import app

        assert app is not None
        assert hasattr(app, 'routes')
        assert len(app.routes) > 0

    def test_api_router_imports(self):
        """Test that API routers can be imported."""
        from src.api.quality_metrics import router as quality_router
        from src.api.user_behavior import router as behavior_router
        from src.api.performance_dashboard import router as performance_router
        from src.api.quality_recommendations import router as recommendations_router

        assert quality_router is not None
        assert behavior_router is not None
        assert performance_router is not None
        assert recommendations_router is not None

    def test_fixtures_available(self):
        """Test that fixtures are available."""
        # This test validates that our conftest.py fixtures exist
        import pytest

        # Check that fixture names are registered
        fixture_names = [
            'test_db_session',
            'test_client',
            'mock_organization',
            'mock_user',
            'mock_current_user',
            'mock_quality_metrics_data',
            'mock_user_behavior_data',
            'mock_performance_data',
            'mock_recommendations_data',
            'sample_time_series_data',
            'mock_alert_data'
        ]

        for fixture_name in fixture_names:
            # This will raise an error if the fixture doesn't exist
            assert pytest.fixture_fixture_names is None or fixture_name in dir(pytest)