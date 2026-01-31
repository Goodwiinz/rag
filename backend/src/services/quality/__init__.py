"""
Quality metrics and recommendations services
"""

from .performance_dashboard_service import (
    AlertLevel,
    DashboardMetric,
    DashboardWidget,
    DashboardWidgetType,
    MetricTimeRange,
    PerformanceDashboardService,
    QualityMetricsSummary,
    SearchPerformanceMetrics,
    SystemHealthMetrics,
    SystemMonitor,
    UserEngagementMetrics,
)
from .performance_optimizer import PerformanceOptimizer
from .quality_metrics_service import MetricCalculation, QualityMetricsService
from .quality_recommendations_service import (
    QualityInsight,
    QualityRecommendation,
    QualityRecommendationsService,
    RecommendationCategory,
    RecommendationPriority,
    RecommendationStatus,
)
from .realtime_quality_metrics import (
    RealTimeQualityMetrics,
    RealTimeQualityMetricsService,
)
from .user_behavior_service import (
    BehaviorPattern,
    SessionAnalysis,
    UserBehaviorMetrics,
    UserBehaviorService,
)

__all__ = [
    # Quality metrics
    "QualityMetricsService",
    "MetricCalculation",
    # Quality recommendations
    "QualityRecommendationsService",
    "QualityRecommendation",
    "QualityInsight",
    "RecommendationCategory",
    "RecommendationPriority",
    "RecommendationStatus",
    # Realtime metrics
    "RealTimeQualityMetricsService",
    "RealTimeQualityMetrics",
    # User behavior
    "UserBehaviorService",
    "UserBehaviorMetrics",
    "SessionAnalysis",
    "BehaviorPattern",
    # Performance dashboard
    "PerformanceDashboardService",
    "SystemMonitor",
    "DashboardMetric",
    "DashboardWidget",
    "SystemHealthMetrics",
    "SearchPerformanceMetrics",
    "QualityMetricsSummary",
    "UserEngagementMetrics",
    "MetricTimeRange",
    "DashboardWidgetType",
    "AlertLevel",
    # Performance optimizer
    "PerformanceOptimizer",
]
