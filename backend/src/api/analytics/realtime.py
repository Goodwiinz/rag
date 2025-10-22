"""
Real-time Analytics API routes
"""

import logging
import uuid
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from ...services.analytics.realtime_service import realtime_service
from ...models.analytics.realtime_models import (
    SubscriptionCreate, SubscriptionResponse, LiveMetricData, EventStreamData,
    ConnectionStats, RealtimeAnalyticsSummary, ChannelMetrics
)
from ...auth.dependencies import get_current_user
from ...models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/realtime", tags=["analytics-realtime"])


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="Authentication token")
):
    """WebSocket endpoint for real-time analytics"""
    try:
        # Authenticate user from token
        # This is a simplified implementation
        # In production, you'd validate the JWT token properly
        user_id = uuid.uuid4()  # Would extract from token
        session_id = str(uuid.uuid4())

        # Handle WebSocket connection
        await realtime_service.websocket_endpoint(websocket, user_id, session_id)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close(code=1000, reason="Internal server error")


@router.post("/subscriptions", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    request: SubscriptionCreate,
    current_user: User = Depends(get_current_user)
):
    """Create a real-time subscription"""
    try:
        # This would create a subscription via WebSocket in a real implementation
        # For now, return a placeholder response
        subscription_id = str(uuid.uuid4())

        return SubscriptionResponse(
            id=uuid.UUID(subscription_id),
            user_id=current_user.id,
            session_id=request.websocket_id or str(uuid.uuid4()),
            websocket_id=request.websocket_id or str(uuid.uuid4()),
            subscription_type=request.config.subscription_type,
            channel=request.config.channel,
            filters=request.config.filters,
            batch_size=request.config.batch_size,
            update_interval=request.config.update_interval,
            max_buffer_size=request.config.max_buffer_size,
            is_active=True,
            last_activity=datetime.utcnow(),
            message_count=0,
            error_count=0,
            expires_at=request.config.expires_at,
            auto_renew=request.config.auto_renew,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Error creating subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create subscription"
        )


@router.get("/subscriptions", response_model=List[SubscriptionResponse])
async def list_subscriptions(
    subscription_type: Optional[str] = Query(None, description="Filter by subscription type"),
    channel: Optional[str] = Query(None, description="Filter by channel"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    limit: int = Query(50, ge=1, le=100, description="Number of subscriptions to return"),
    current_user: User = Depends(get_current_user)
):
    """List real-time subscriptions"""
    try:
        # This is a simplified implementation
        # In production, you'd query the actual subscriptions from the database
        subscriptions = []

        return subscriptions

    except Exception as e:
        logger.error(f"Error listing subscriptions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list subscriptions"
        )


@router.post("/metrics/publish", status_code=status.HTTP_200_OK)
async def publish_metric(
    metric_data: LiveMetricData,
    current_user: User = Depends(get_current_user)
):
    """Publish a live metric value"""
    try:
        await realtime_service.publish_metric(metric_data)
        return {"message": "Metric published successfully"}

    except Exception as e:
        logger.error(f"Error publishing metric: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to publish metric"
        )


@router.post("/events/publish", status_code=status.HTTP_200_OK)
async def publish_event(
    event_data: EventStreamData,
    current_user: User = Depends(get_current_user)
):
    """Publish an event stream"""
    try:
        await realtime_service.publish_event(event_data)
        return {"message": "Event published successfully"}

    except Exception as e:
        logger.error(f"Error publishing event: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to publish event"
        )


@router.get("/connections/{connection_id}", response_model=ConnectionStats)
async def get_connection_stats(
    connection_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get WebSocket connection statistics"""
    try:
        stats = await realtime_service.get_connection_stats(connection_id)
        if not stats:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found"
            )
        return stats

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting connection stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get connection stats"
        )


@router.get("/summary", response_model=RealtimeAnalyticsSummary)
async def get_realtime_summary(
    current_user: User = Depends(get_current_user)
):
    """Get real-time analytics summary"""
    try:
        summary = await realtime_service.get_realtime_summary()
        return summary

    except Exception as e:
        logger.error(f"Error getting realtime summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get realtime summary"
        )


@router.get("/channels/{channel}/metrics", response_model=ChannelMetrics)
async def get_channel_metrics(
    channel: str,
    current_user: User = Depends(get_current_user)
):
    """Get channel-specific metrics"""
    try:
        metrics = await realtime_service.get_channel_metrics(channel)
        return metrics

    except Exception as e:
        logger.error(f"Error getting channel metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get channel metrics"
        )


@router.get("/channels", response_model=List[str])
async def get_active_channels(
    current_user: User = Depends(get_current_user)
):
    """Get list of active channels"""
    try:
        # This is a simplified implementation
        # In production, you'd query the actual active channels
        active_channels = [
            "metrics:performance",
            "events:user_activity",
            "alerts:system_health",
            "dashboards:updates"
        ]

        return active_channels

    except Exception as e:
        logger.error(f"Error getting active channels: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get active channels"
        )


@router.get("/health", response_model=Dict[str, Any])
async def check_realtime_health(
    current_user: User = Depends(get_current_user)
):
    """Check real-time analytics service health"""
    try:
        summary = await realtime_service.get_realtime_summary()

        return {
            "status": "healthy" if summary.system_health in ["healthy", "degraded"] else "unhealthy",
            "total_connections": summary.total_connections,
            "active_subscriptions": summary.active_subscriptions,
            "messages_per_second": summary.messages_per_second,
            "events_per_second": summary.events_per_second,
            "system_health": summary.system_health,
            "last_updated": summary.last_updated.isoformat(),
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error checking realtime health: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.post("/test/subscribe", status_code=status.HTTP_200_OK)
async def test_subscription(
    channel: str = Query(..., description="Channel to test subscription"),
    message_count: int = Query(10, ge=1, le=100, description="Number of test messages"),
    current_user: User = Depends(get_current_user)
):
    """Test real-time subscription with sample data"""
    try:
        # Generate test messages
        for i in range(message_count):
            test_metric = LiveMetricData(
                metric_id=f"test_metric_{i}",
                metric_name=f"Test Metric {i}",
                channel=channel,
                current_value=float(i * 10),
                previous_value=float((i - 1) * 10) if i > 0 else 0.0,
                change_percentage=10.0,
                timestamp=datetime.utcnow(),
                time_window="1m",
                aggregation_type="sum",
                sample_count=1,
                data_quality_score=1.0,
                dimensions={"test": True},
                tags=["test"],
                is_anomaly=False,
                source="test",
                confidence=1.0
            )

            await realtime_service.publish_metric(test_metric)

        return {
            "message": f"Published {message_count} test messages to channel: {channel}",
            "channel": channel,
            "message_count": message_count
        }

    except Exception as e:
        logger.error(f"Error testing subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to test subscription"
        )