"""
Realtime API routes for WebSocket connections and real-time status updates
"""

from .websocket import router as websocket_router
from .websocket_v2 import router as websocket_v2_router
from .realtime_document_status import router as realtime_status_router
from .realtime_quality_metrics import router as realtime_quality_metrics_router

__all__ = [
    "websocket_router",
    "websocket_v2_router",
    "realtime_status_router",
    "realtime_quality_metrics_router",
]
