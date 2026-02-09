"""
Analytics models for Knowledge Graph Analytics Dashboard
"""

from .analytics_models import (
    AnalyticsEvent,
    AnalyticsFilter,
    AnalyticsKPI,
    AnalyticsMetric,
    AnalyticsReport,
    MetricAggregation,
    TimeSeriesData,
)
from .dashboard_models import (
    Dashboard,
    DashboardLayout,
    DashboardPermission,
    DashboardTheme,
    DashboardWidget,
    DashboardWidgetType,
    WidgetConfiguration,
)
from .graph_analytics import (
    CommunityMetrics,
    EdgeMetrics,
    GraphAnalyticsResult,
    GraphMetrics,
    NodeMetrics,
    PathAnalytics,
)
from .realtime_models import (
    EventStream,
    LiveMetric,
    RealtimeSubscription,
    WebSocketMessage,
)

__all__ = [
    # Dashboard models
    "Dashboard",
    "DashboardWidget",
    "DashboardLayout",
    "WidgetConfiguration",
    "DashboardWidgetType",
    "DashboardTheme",
    "DashboardPermission",
    # Analytics models
    "AnalyticsEvent",
    "AnalyticsMetric",
    "AnalyticsKPI",
    "AnalyticsReport",
    "MetricAggregation",
    "TimeSeriesData",
    "AnalyticsFilter",
    # Graph analytics models
    "GraphAnalyticsResult",
    "GraphMetrics",
    "NodeMetrics",
    "EdgeMetrics",
    "CommunityMetrics",
    "PathAnalytics",
    # Realtime models
    "RealtimeSubscription",
    "WebSocketMessage",
    "LiveMetric",
    "EventStream",
]
