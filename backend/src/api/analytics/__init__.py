"""
Analytics API routes for Knowledge Graph Analytics Dashboard
"""

from .dashboards import router as dashboards_router
from .graph_analytics import router as graph_analytics_router
from .metrics import router as metrics_router
from .realtime import router as realtime_router
from .reports import router as reports_router

__all__ = [
    "dashboards_router",
    "metrics_router",
    "graph_analytics_router",
    "reports_router",
    "realtime_router",
]
