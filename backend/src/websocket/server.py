"""
Main WebSocket server implementation
Handles real-time document processing updates with authentication and scaling
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..core.config import settings
from .auth import get_websocket_authenticator, websocket_auth_required
from .connection_manager import (
    MessageType,
    RedisBackedConnectionManager,
    WebSocketMessage,
)
from .error_handling import get_websocket_error_handler, handle_websocket_errors
from .message_schemas import MessageTemplates
from .redis_integration import get_websocket_redis_manager
from .websocket_api import router as websocket_api_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global components
connection_manager: Optional[RedisBackedConnectionManager] = None
redis_manager = None
authenticator = None
error_handler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    global connection_manager, redis_manager, authenticator, error_handler

    # Startup
    logger.info("Starting WebSocket service...")

    try:
        # Initialize Redis manager
        redis_manager = get_websocket_redis_manager()
        await redis_manager.initialize()
        logger.info("Redis manager initialized")

        # Initialize authenticator
        authenticator = get_websocket_authenticator()
        await authenticator.initialize()
        logger.info("Authenticator initialized")

        # Initialize error handler
        error_handler = get_websocket_error_handler()
        logger.info("Error handler initialized")

        # Initialize connection manager
        connection_manager = RedisBackedConnectionManager(
            redis_url=settings.REDIS_URL,
            connection_ttl=3600,
            ping_interval=30,
            max_connections_per_user=10,
            max_connections_total=15000,
        )
        await connection_manager.initialize()
        logger.info("Connection manager initialized")

        # Setup message handlers
        setup_message_handlers()

        # Setup document processing event listeners
        setup_document_processing_listeners()

        logger.info("WebSocket service startup complete")

    except Exception as e:
        logger.error(f"Failed to start WebSocket service: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down WebSocket service...")

    try:
        if connection_manager:
            await connection_manager.shutdown()
        if authenticator:
            await authenticator.shutdown()
        if redis_manager:
            await redis_manager.shutdown()

        logger.info("WebSocket service shutdown complete")

    except Exception as e:
        logger.error(f"Error during WebSocket service shutdown: {e}")


# Create FastAPI application
app = FastAPI(
    title="WebSocket Service",
    description="Real-time WebSocket service for document processing updates",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Add CORS middleware
# SECURITY: Restrict allow_headers to specific values instead of "*"
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

# Include API router
app.include_router(websocket_api_router)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check all components
        status = "healthy"
        details = {}

        # Check connection manager
        if connection_manager:
            stats = await connection_manager.get_connection_stats()
            details["connection_manager"] = stats
        else:
            status = "unhealthy"
            details["connection_manager"] = "Not initialized"

        # Check Redis
        if redis_manager and redis_manager._redis_client:
            await redis_manager._redis_client.ping()
            details["redis"] = "Connected"
        else:
            status = "unhealthy"
            details["redis"] = "Not connected"

        return {
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "details": details,
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
            },
        )


# Main WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    organization_id: Optional[str] = Query(None),
):
    """
    Main WebSocket endpoint for real-time document processing updates

    Query Parameters:
    - token: JWT authentication token (required)
    - organization_id: Organization context (optional, uses user's default)

    Supported message types:
    - ping: Health check
    - pong: Response to ping
    - subscribe: Subscribe to specific events
    - unsubscribe: Unsubscribe from events
    """
    connection_id = None

    try:
        # Authenticate WebSocket connection
        user, session_id, org_id = await websocket_auth_required(
            websocket=websocket, token=token, organization_id=organization_id
        )

        # Connect to connection manager
        connection_id = await connection_manager.connect(
            websocket=websocket,
            user_id=str(user.id),
            organization_id=org_id,
            metadata={
                "user_email": user.email,
                "session_id": session_id,
                "client_info": websocket.headers.get("user-agent", "Unknown"),
                "client_ip": websocket.client.host if websocket.client else "Unknown",
            },
        )

        # Send welcome message
        await connection_manager.send_message(
            connection_id,
            WebSocketMessage(
                message_id=f"welcome_{datetime.utcnow().timestamp()}",
                message_type=MessageType.CONNECT,
                timestamp=datetime.utcnow(),
                user_id=str(user.id),
                organization_id=org_id,
                data={
                    "connection_id": connection_id,
                    "user_id": str(user.id),
                    "organization_id": org_id,
                    "server_time": datetime.utcnow().isoformat(),
                    "features": [
                        "document_processing_updates",
                        "real_time_notifications",
                        "system_announcements",
                        "connection_health_monitoring",
                    ],
                },
            ),
        )

        logger.info(
            f"WebSocket connection established: {connection_id} for user {user.id}"
        )

        # Main message loop
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                logger.debug(f"Received message from {connection_id}: {data[:100]}...")

                # Handle message
                await connection_manager.handle_message(connection_id, data)

            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected: {connection_id}")
                break
            except Exception as e:
                logger.error(f"Error in message loop for {connection_id}: {e}")
                await connection_manager.send_message(
                    connection_id,
                    WebSocketMessage(
                        message_id=f"error_{datetime.utcnow().timestamp()}",
                        message_type=MessageType.ERROR,
                        timestamp=datetime.utcnow(),
                        error="Message processing error",
                        data={"details": str(e)},
                    ),
                )

    except WebSocketDisconnect:
        logger.info(f"WebSocket connection closed during handshake: {connection_id}")
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
        if connection_id:
            try:
                await connection_manager.send_message(
                    connection_id,
                    WebSocketMessage(
                        message_id=f"error_{datetime.utcnow().timestamp()}",
                        message_type=MessageType.ERROR,
                        timestamp=datetime.utcnow(),
                        error="Connection error",
                        data={"details": str(e)},
                    ),
                )
            except Exception:
                pass
    finally:
        # Clean up connection
        if connection_id:
            await connection_manager.disconnect(connection_id, "Connection closed")


# Document processing specific endpoints
@app.websocket("/ws/documents/{document_id}")
async def document_websocket(
    document_id: str, websocket: WebSocket, token: Optional[str] = Query(None)
):
    """
    WebSocket endpoint for document-specific processing updates

    Path Parameters:
    - document_id: ID of the document to monitor

    Query Parameters:
    - token: JWT authentication token (required)
    """
    connection_id = None

    try:
        # Authenticate
        user, session_id, org_id = await websocket_auth_required(
            websocket=websocket, token=token
        )

        # Verify user has access to document
        # (Implement document access check here)

        # Connect with document-specific metadata
        connection_id = await connection_manager.connect(
            websocket=websocket,
            user_id=str(user.id),
            organization_id=org_id,
            metadata={
                "document_id": document_id,
                "session_id": session_id,
                "subscription_type": "document_specific",
            },
        )

        # Send initial document status
        # (Implement document status retrieval here)
        await connection_manager.send_message(
            connection_id,
            WebSocketMessage(
                message_id=f"doc_status_{datetime.utcnow().timestamp()}",
                message_type=MessageType.DOC_STATUS_UPDATE,
                timestamp=datetime.utcnow(),
                data={
                    "document_id": document_id,
                    "status": "connected",
                    "message": f"Monitoring document {document_id}",
                },
            ),
        )

        # Message loop
        while True:
            data = await websocket.receive_text()
            await connection_manager.handle_message(connection_id, data)

    except WebSocketDisconnect:
        logger.info(f"Document WebSocket disconnected: {connection_id}")
    except Exception as e:
        logger.error(f"Document WebSocket error: {e}")
    finally:
        if connection_id:
            await connection_manager.disconnect(
                connection_id, "Document monitoring ended"
            )


# Setup functions


def setup_message_handlers():
    """Setup custom message handlers"""
    from .message_schemas import MessageType

    # Add document status update handler
    async def handle_document_status_update(
        connection_id: str, message: WebSocketMessage
    ):
        """Handle document status update requests"""
        try:
            # Process status update request
            logger.info(f"Document status update request from {connection_id}")

            # Send current document status
            # (Implement document status retrieval logic)

        except Exception as e:
            logger.error(f"Error handling document status update: {e}")

    # Add subscription handler
    async def handle_subscription_request(
        connection_id: str, message: WebSocketMessage
    ):
        """Handle subscription requests"""
        try:
            channel = message.data.get("channel") if message.data else None
            if channel:
                logger.info(f"Connection {connection_id} subscribed to {channel}")

                # Store subscription
                # (Implement subscription logic)

        except Exception as e:
            logger.error(f"Error handling subscription: {e}")

    # Register handlers
    if connection_manager:
        connection_manager.add_message_handler(
            MessageType.DOC_STATUS_UPDATE, handle_document_status_update
        )
        connection_manager.add_message_handler(
            MessageType.SUBSCRIBE, handle_subscription_request
        )


def setup_document_processing_listeners():
    """Setup listeners for document processing events"""
    if not redis_manager:
        return

    async def handle_document_processing_event(event_data: Dict[str, Any]):
        """Handle document processing events from Redis pub/sub"""
        try:
            event_type = event_data.get("type")
            data = event_data.get("data", {})

            if event_type == "document_status_change":
                # Broadcast document status change
                document_id = data.get("document_id")
                user_id = data.get("user_id")
                organization_id = data.get("organization_id")
                new_status = data.get("status")

                if document_id and user_id:
                    message = MessageTemplates.document_status_update(
                        document_id=document_id,
                        status=new_status,
                        metadata=data.get("metadata", {}),
                    )

                    if user_id:
                        await connection_manager.broadcast_to_user(user_id, message)
                    if organization_id:
                        await connection_manager.broadcast_to_organization(
                            organization_id, message
                        )

        except Exception as e:
            logger.error(f"Error handling document processing event: {e}")

    # Subscribe to document processing events
    asyncio.create_task(
        redis_manager.subscribe(
            "document_processing_events", handle_document_processing_event
        )
    )


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    """Handle validation errors"""
    logger.error(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": {"message": "Validation error", "details": exc.errors()}},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "message": "Internal server error" if not settings.DEBUG else str(exc)
            }
        },
    )


# Run server (for development)
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.websocket.server:app",
        host="0.0.0.0",
        port=int(os.getenv("WS_PORT", 8001)),
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        ws_ping_interval=20,
        ws_ping_timeout=10,
    )
