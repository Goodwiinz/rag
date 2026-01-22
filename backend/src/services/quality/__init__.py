"""
Quality metrics and recommendations services
"""

from .quality_metrics_service import QualityMetricsService, MetricCalculation
from .quality_recommendations_service import (
    QualityRecommendationsService,
    QualityRecommendation,
    QualityInsight,
    RecommendationCategory,
    RecommendationPriority,
    RecommendationStatus,
)
from .realtime_quality_metrics import RealTimeQualityMetricsService, RealTimeQualityMetrics
from .user_behavior_service import UserBehaviorService, UserBehaviorMetrics, SessionAnalysis, BehaviorPattern
from .performance_dashboard_service import (
    PerformanceDashboardService,
    SystemMonitor,
    DashboardMetric,
    DashboardWidget,
    SystemHealthMetrics,
    SearchPerformanceMetrics,
    QualityMetricsSummary,
    UserEngagementMetrics,
    MetricTimeRange,
    DashboardWidgetType,
    AlertLevel,
)
from .performance_optimizer import PerformanceOptimizer

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
