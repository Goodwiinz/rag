"""
Main Analytics API router
"""

from fastapi import APIRouter

from .analytics import (
    dashboards_router,
    graph_analytics_router,
    metrics_router,
    realtime_router,
    reports_router,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])

# Include all analytics routers
router.include_router(dashboards_router)
router.include_router(metrics_router)
router.include_router(graph_analytics_router)
router.include_router(reports_router)
router.include_router(realtime_router)

__all__ = ["router"]
