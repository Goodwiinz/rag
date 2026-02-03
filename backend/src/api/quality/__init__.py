"""
Quality API routes for metrics, recommendations, user behavior, and performance
Note: ab_testing router disabled due to missing ab_testing_service.py (pre-existing issue)
"""

from .performance_dashboard import router as performance_dashboard_router
from .quality_metrics import router as quality_metrics_router
from .quality_recommendations import router as quality_recommendations_router
from .user_behavior import router as user_behavior_router

# TODO: Re-enable when ab_testing_service.py is implemented
# from .ab_testing import router as ab_testing_router

__all__ = [
    "quality_metrics_router",
    "quality_recommendations_router",
    "user_behavior_router",
    "performance_dashboard_router",
    # "ab_testing_router",  # Disabled - missing ab_testing_service.py
]
