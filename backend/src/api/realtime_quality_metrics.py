"""
API endpoints for real-time quality metrics
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import uuid
import logging

from ..core.dependencies import get_current_user, get_db
from ..services.realtime_quality_metrics import realtime_quality_metrics_service
from ..models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/realtime/quality", tags=["realtime-quality-metrics"])


class StartEvaluationRequest(BaseModel):
    query: str = Field(..., description="The query to evaluate")
    websocket_channel: Optional[str] = Field(None, description="WebSocket channel for updates")


class StartEvaluationResponse(BaseModel):
    success: bool
    query_id: str
    message: str
    websocket_channel: str


@router.post("/evaluate", response_model=StartEvaluationResponse)
async def start_realtime_evaluation(
    request: StartEvaluationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Start real-time quality evaluation for a query
    """
    try:
        # Generate unique query ID
        query_id = str(uuid.uuid4())

        # Determine WebSocket channel
        websocket_channel = request.websocket_channel or f"quality_metrics_{current_user.id}"

        # Start evaluation in background
        await realtime_quality_metrics_service.start_query_evaluation(
            query=request.query,
            query_id=query_id,
            user_id=str(current_user.id),
            organization_id=current_user.organization_id,
            websocket_channel=websocket_channel
        )

        # Schedule cleanup task
        background_tasks.add_task(
            realtime_quality_metrics_service.cleanup_old_data,
            max_age_hours=1
        )

        return StartEvaluationResponse(
            success=True,
            query_id=query_id,
            message="Real-time evaluation started",
            websocket_channel=websocket_channel
        )

    except Exception as e:
        logger.error(f"Error starting realtime evaluation: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to start real-time evaluation"
        )


@router.get("/status/{query_id}")
async def get_query_status(
    query_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get status of a query evaluation
    """
    try:
        status = realtime_quality_metrics_service.get_query_status(query_id)

        if status is None:
            raise HTTPException(
                status_code=404,
                detail="Query not found"
            )

        return {
            "query_id": query_id,
            "status": status,
            "timestamp": None  # Could add timestamp from active_queries
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting query status: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get query status"
        )


@router.get("/history/{query_id}")
async def get_query_history(
    query_id: str,
    limit: int = 100,
    current_user: User = Depends(get_current_user)
):
    """
    Get historical metrics for a query
    """
    try:
        history = await realtime_quality_metrics_service.get_query_metrics_history(
            query_id,
            limit=limit
        )

        return {
            "query_id": query_id,
            "history": history,
            "count": len(history)
        }

    except Exception as e:
        logger.error(f"Error getting query history: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get query history"
        )


@router.get("/stats")
async def get_system_stats(
    current_user: User = Depends(get_current_user)
):
    """
    Get system statistics
    """
    try:
        active_queries = realtime_quality_metrics_service.get_active_queries_count()

        return {
            "active_queries": active_queries,
            "status": "healthy",
            "timestamp": None  # Could add current timestamp
        }

    except Exception as e:
        logger.error(f"Error getting system stats: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get system stats"
        )


@router.delete("/cleanup")
async def cleanup_old_data(
    max_age_hours: int = 24,
    current_user: User = Depends(get_current_user)
):
    """
    Clean up old evaluation data
    """
    try:
        await realtime_quality_metrics_service.cleanup_old_data(max_age_hours)

        return {
            "message": f"Cleaned up data older than {max_age_hours} hours",
            "success": True
        }

    except Exception as e:
        logger.error(f"Error cleaning up data: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to cleanup data"
        )