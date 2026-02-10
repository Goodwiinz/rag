"""Quality metrics and recommendations services.

Exports are resolved lazily to avoid import cycles between evaluation and
real-time quality modules during app/test startup.
"""

from importlib import import_module
from typing import Dict, Tuple

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

_EXPORTS: Dict[str, Tuple[str, str]] = {
    # Quality metrics
    "QualityMetricsService": ("src.services.quality.quality_metrics_service", "QualityMetricsService"),
    "MetricCalculation": ("src.services.quality.quality_metrics_service", "MetricCalculation"),
    # Quality recommendations
    "QualityRecommendationsService": (
        "src.services.quality.quality_recommendations_service",
        "QualityRecommendationsService",
    ),
    "QualityRecommendation": ("src.services.quality.quality_recommendations_service", "QualityRecommendation"),
    "QualityInsight": ("src.services.quality.quality_recommendations_service", "QualityInsight"),
    "RecommendationCategory": (
        "src.services.quality.quality_recommendations_service",
        "RecommendationCategory",
    ),
    "RecommendationPriority": (
        "src.services.quality.quality_recommendations_service",
        "RecommendationPriority",
    ),
    "RecommendationStatus": (
        "src.services.quality.quality_recommendations_service",
        "RecommendationStatus",
    ),
    # Realtime metrics
    "RealTimeQualityMetricsService": ("src.services.quality.realtime_quality_metrics", "RealTimeQualityMetricsService"),
    "RealTimeQualityMetrics": ("src.services.quality.realtime_quality_metrics", "RealTimeQualityMetrics"),
    # User behavior
    "UserBehaviorService": ("src.services.quality.user_behavior_service", "UserBehaviorService"),
    "UserBehaviorMetrics": ("src.services.quality.user_behavior_service", "UserBehaviorMetrics"),
    "SessionAnalysis": ("src.services.quality.user_behavior_service", "SessionAnalysis"),
    "BehaviorPattern": ("src.services.quality.user_behavior_service", "BehaviorPattern"),
    # Performance dashboard
    "PerformanceDashboardService": (
        "src.services.quality.performance_dashboard_service",
        "PerformanceDashboardService",
    ),
    "SystemMonitor": ("src.services.quality.performance_dashboard_service", "SystemMonitor"),
    "DashboardMetric": ("src.services.quality.performance_dashboard_service", "DashboardMetric"),
    "DashboardWidget": ("src.services.quality.performance_dashboard_service", "DashboardWidget"),
    "SystemHealthMetrics": (
        "src.services.quality.performance_dashboard_service",
        "SystemHealthMetrics",
    ),
    "SearchPerformanceMetrics": (
        "src.services.quality.performance_dashboard_service",
        "SearchPerformanceMetrics",
    ),
    "QualityMetricsSummary": (
        "src.services.quality.performance_dashboard_service",
        "QualityMetricsSummary",
    ),
    "UserEngagementMetrics": (
        "src.services.quality.performance_dashboard_service",
        "UserEngagementMetrics",
    ),
    "MetricTimeRange": ("src.services.quality.performance_dashboard_service", "MetricTimeRange"),
    "DashboardWidgetType": (
        "src.services.quality.performance_dashboard_service",
        "DashboardWidgetType",
    ),
    "AlertLevel": ("src.services.quality.performance_dashboard_service", "AlertLevel"),
    # Performance optimizer
    "PerformanceOptimizer": ("src.services.quality.performance_optimizer", "PerformanceOptimizer"),
}


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_path, attr_name = _EXPORTS[name]
    module = import_module(module_path)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
