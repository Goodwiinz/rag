"""
WebSocket-related REST API endpoints
Provides management and monitoring endpoints for WebSocket services
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Path, Body, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import logging

from ..core.database import get_db_session
from ..websocket.auth import get_websocket_authenticator
from ..websocket.connection_manager import RedisBackedConnectionManager
from ..websocket.redis_integration import get_websocket_redis_manager
from ..websocket.error_handling import get_websocket_error_handler

logger = logging.getLogger(__name__)

# Security
security = HTTPBearer()

# Router
router = APIRouter(prefix="/api/v1/websocket", tags=["WebSocket"])

# Pydantic models

class ConnectionInfo(BaseModel):
    connection_id: str
    user_id: str
    organization_id: str
    connected_at: datetime
    last_activity: datetime
    subscriptions: List[str]
    metadata: Dict[str, Any] = Field(default_factory=dict)

class WebSocketStats(BaseModel):
    total_connections: int
    active_connections: int
    user_connections: int
    organization_connections: int
    connections_by_status: Dict[str, int]
    messages_sent: int
    messages_received: int
    errors: int

class ConnectionMetrics(BaseModel):
    total_connections: int
    active_connections: int
    user_connections: int
    organization_connections: int
    redis_connections: int
    messages_sent: int
    messages_received: int
    errors: int
    timestamp: datetime

class WebSocketConfig(BaseModel):
    max_connections: int = Field(default=10000, ge=100, le=50000)
    heartbeat_interval: int = Field(default=30, ge=5, le=300)
    connection_ttl: int = Field(default=3600, ge=60, le=86400)
    rate_limit_per_minute: int = Field(default=60, ge=10, le=1000)
    max_concurrent_sessions: int = Field(default=10, ge=1, le=50)

class SessionInfo(BaseModel):
    session_id: str
    user_id: str
    organization_id: str
    created_at: datetime
    last_activity: datetime
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    is_active: bool = True

class BroadcastRequest(BaseModel):
    message_type: str = Field(..., description="Type of message to broadcast")
    message_data: Dict[str, Any] = Field(..., description="Message payload")
    target_type: str = Field(..., description="Target: 'all', 'user', 'organization'")
    target_id: Optional[str] = Field(None, description="Target user/organization ID")
    channels: Optional[List[str]] = Field(None, description="Specific channels to target")

class SystemAnnouncementRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=1000)
    severity: str = Field(..., regex="^(info|warning|error|critical)$")
    target_roles: Optional[List[str]] = Field(None)
    expires_at: Optional[datetime] = Field(None)
    action_url: Optional[str] = Field(None)

class WebSocketEndpoint(BaseModel):
    endpoint: str
    method: str
    path: str
    summary: str
    description: str
    parameters: List[Dict[str, Any]] = Field(default_factory=list)
    responses: Dict[str, Any] = Field(default_factory=dict)

# API Endpoints

@router.get("/stats", response_model=WebSocketStats)
async def get_websocket_stats(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get WebSocket connection statistics and metrics
    """
    try:
        redis_manager = get_websocket_redis_manager()
        metrics = await redis_manager.get_performance_metrics()

        return WebSocketStats(
            total_connections=metrics.get('websocket_metrics', {}).get('total_connections', 0),
            active_connections=metrics.get('websocket_metrics', {}).get('active_connections', 0),
            user_connections=len(metrics.get('subscription_metrics', {}).get('total_subscribers', 0)),
            organization_connections=metrics.get('subscription_metrics', {}).get('active_subscriptions', 0),
            connections_by_status={
                'connected': metrics.get('websocket_metrics', {}).get('active_connections', 0),
                'disconnected': 0
            },
            messages_sent=metrics.get('websocket_metrics', {}).get('messages_sent', 0),
            messages_received=metrics.get('websocket_metrics', {}).get('messages_received', 0),
            errors=metrics.get('websocket_metrics', {}).get('redis_errors', 0)
        )

    except Exception as e:
        logger.error(f"Error getting WebSocket stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve WebSocket statistics"
        )

@router.get("/connections", response_model=List[ConnectionInfo])
async def get_active_connections(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user_id: Optional[str] = Query(None),
    organization_id: Optional[str] = Query(None),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get list of active WebSocket connections with filtering
    """
    try:
        redis_manager = get_websocket_redis_manager()

        # Get connections from Redis
        if user_id:
            connection_ids = await redis_manager.get_user_connections(user_id)
        elif organization_id:
            connection_ids = await redis_manager.get_organization_connections(organization_id)
        else:
            # Get all connections (this might be expensive, consider pagination)
            connection_ids = []  # Implement based on your needs

        connections = []
        for conn_id in connection_ids[offset:offset + limit]:
            session_info = await redis_manager.get_session(conn_id)
            if session_info:
                connections.append(ConnectionInfo(
                    connection_id=conn_id,
                    user_id=session_info['user_id'],
                    organization_id=session_info['organization_id'],
                    connected_at=datetime.fromisoformat(session_info['created_at']),
                    last_activity=datetime.fromisoformat(session_info['last_activity']),
                    subscriptions=[],  # Get from connection metadata
                    metadata=session_info.get('data', {})
                ))

        return connections

    except Exception as e:
        logger.error(f"Error getting connections: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve connections"
        )

@router.get("/connections/{connection_id}", response_model=ConnectionInfo)
async def get_connection_details(
    connection_id: str = Path(..., description="WebSocket connection ID"),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get detailed information about a specific WebSocket connection
    """
    try:
        redis_manager = get_websocket_redis_manager()
        session_info = await redis_manager.get_session(connection_id)

        if not session_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found"
            )

        return ConnectionInfo(
            connection_id=connection_id,
            user_id=session_info['user_id'],
            organization_id=session_info['organization_id'],
            connected_at=datetime.fromisoformat(session_info['created_at']),
            last_activity=datetime.fromisoformat(session_info['last_activity']),
            subscriptions=[],  # Get from connection metadata
            metadata=session_info.get('data', {})
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting connection details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve connection details"
        )

@router.delete("/connections/{connection_id}")
async def disconnect_connection(
    connection_id: str = Path(..., description="WebSocket connection ID"),
    reason: str = Query(default="Admin disconnect", description="Reason for disconnection"),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Force disconnect a WebSocket connection
    """
    try:
        # Verify connection exists
        redis_manager = get_websocket_redis_manager()
        session_info = await redis_manager.get_session(connection_id)

        if not session_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found"
            )

        # Remove connection
        await redis_manager.remove_connection(connection_id)
        await redis_manager.delete_session(connection_id)

        return {"message": "Connection disconnected successfully", "connection_id": connection_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disconnecting connection: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to disconnect connection"
        )

@router.get("/users/{user_id}/connections", response_model=List[ConnectionInfo])
async def get_user_connections(
    user_id: str = Path(..., description="User ID"),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get all WebSocket connections for a specific user
    """
    try:
        redis_manager = get_websocket_redis_manager()
        connection_ids = await redis_manager.get_user_connections(user_id)

        connections = []
        for conn_id in connection_ids:
            session_info = await redis_manager.get_session(conn_id)
            if session_info:
                connections.append(ConnectionInfo(
                    connection_id=conn_id,
                    user_id=session_info['user_id'],
                    organization_id=session_info['organization_id'],
                    connected_at=datetime.fromisoformat(session_info['created_at']),
                    last_activity=datetime.fromisoformat(session_info['last_activity']),
                    subscriptions=[],
                    metadata=session_info.get('data', {})
                ))

        return connections

    except Exception as e:
        logger.error(f"Error getting user connections: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user connections"
        )

@router.get("/organizations/{organization_id}/connections", response_model=List[ConnectionInfo])
async def get_organization_connections(
    organization_id: str = Path(..., description="Organization ID"),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get all WebSocket connections for a specific organization
    """
    try:
        redis_manager = get_websocket_redis_manager()
        connection_ids = await redis_manager.get_organization_connections(organization_id)

        connections = []
        for conn_id in connection_ids:
            session_info = await redis_manager.get_session(conn_id)
            if session_info:
                connections.append(ConnectionInfo(
                    connection_id=conn_id,
                    user_id=session_info['user_id'],
                    organization_id=session_info['organization_id'],
                    connected_at=datetime.fromisoformat(session_info['created_at']),
                    last_activity=datetime.fromisoformat(session_info['last_activity']),
                    subscriptions=[],
                    metadata=session_info.get('data', {})
                ))

        return connections

    except Exception as e:
        logger.error(f"Error getting organization connections: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve organization connections"
        )

@router.post("/broadcast")
async def broadcast_message(
    broadcast: BroadcastRequest = Body(...),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Broadcast a message to WebSocket connections
    """
    try:
        redis_manager = get_websocket_redis_manager()

        # Create message
        message = {
            'message_id': f"broadcast_{datetime.utcnow().timestamp()}",
            'type': broadcast.message_type,
            'timestamp': datetime.utcnow().isoformat(),
            'data': broadcast.message_data
        }

        # Send based on target type
        if broadcast.target_type == 'all':
            await redis_manager.publish('ws:broadcast:all', message)
        elif broadcast.target_type == 'user' and broadcast.target_id:
            await redis_manager.publish(f'ws:broadcast:user:{broadcast.target_id}', message)
        elif broadcast.target_type == 'organization' and broadcast.target_id:
            await redis_manager.publish(f'ws:broadcast:org:{broadcast.target_id}', message)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid target configuration"
            )

        return {"message": "Message broadcast successfully", "message_id": message['message_id']}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error broadcasting message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to broadcast message"
        )

@router.post("/announcements")
async def create_system_announcement(
    announcement: SystemAnnouncementRequest = Body(...),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Create a system announcement to be sent to WebSocket clients
    """
    try:
        redis_manager = get_websocket_redis_manager()

        # Create announcement message
        message = {
            'message_id': f"announcement_{datetime.utcnow().timestamp()}",
            'type': 'system_announcement',
            'timestamp': datetime.utcnow().isoformat(),
            'data': {
                'announcement_type': 'system',
                'title': announcement.title,
                'message': announcement.message,
                'severity': announcement.severity,
                'target_roles': announcement.target_roles,
                'expires_at': announcement.expires_at.isoformat() if announcement.expires_at else None,
                'action_url': announcement.action_url,
                'action_required': bool(announcement.action_url)
            }
        }

        # Broadcast to all
        await redis_manager.publish('ws:broadcast:all', message)

        return {
            "message": "Announcement created successfully",
            "message_id": message['message_id'],
            "title": announcement.title,
            "severity": announcement.severity
        }

    except Exception as e:
        logger.error(f"Error creating announcement: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create announcement"
        )

@router.get("/config", response_model=WebSocketConfig)
async def get_websocket_config(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get current WebSocket service configuration
    """
    try:
        # This would typically come from configuration service
        return WebSocketConfig(
            max_connections=10000,
            heartbeat_interval=30,
            connection_ttl=3600,
            rate_limit_per_minute=60,
            max_concurrent_sessions=10
        )

    except Exception as e:
        logger.error(f"Error getting WebSocket config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve WebSocket configuration"
        )

@router.put("/config")
async def update_websocket_config(
    config: WebSocketConfig = Body(...),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Update WebSocket service configuration
    """
    try:
        # Validate configuration
        if config.max_connections < 100 or config.max_connections > 50000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="max_connections must be between 100 and 50000"
            )

        # Update configuration (implement based on your config management)
        logger.info(f"WebSocket config updated: {config}")

        return {"message": "Configuration updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating WebSocket config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update WebSocket configuration"
        )

@router.get("/health")
async def websocket_health_check():
    """
    WebSocket service health check
    """
    try:
        redis_manager = get_websocket_redis_manager()

        # Check Redis connection
        if not redis_manager._redis_client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Redis client not available"
            )

        await redis_manager._redis_client.ping()

        return {
            "status": "healthy",
            "timestamp": datetime.utcnow(),
            "version": "1.0.0"
        }

    except Exception as e:
        logger.error(f"WebSocket health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WebSocket service unhealthy"
        )

@router.get("/metrics", response_model=ConnectionMetrics)
async def get_detailed_metrics(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get detailed WebSocket service metrics
    """
    try:
        redis_manager = get_websocket_redis_manager()
        metrics = await redis_manager.get_performance_metrics()

        websocket_metrics = metrics.get('websocket_metrics', {})
        local_cache_metrics = metrics.get('local_cache_metrics', {})

        return ConnectionMetrics(
            total_connections=websocket_metrics.get('total_connections', 0),
            active_connections=websocket_metrics.get('active_connections', 0),
            user_connections=local_cache_metrics.get('local_cache_size', 0),
            organization_connections=metrics.get('subscription_metrics', {}).get('active_subscriptions', 0),
            redis_connections=metrics.get('redis_metrics', {}).get('connected_clients', 0),
            messages_sent=websocket_metrics.get('messages_sent', 0),
            messages_received=websocket_metrics.get('messages_received', 0),
            errors=websocket_metrics.get('redis_errors', 0),
            timestamp=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve metrics"
        )