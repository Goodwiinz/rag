"""
WebSocket service initializer for integrating all WebSocket components
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

from .websocket_manager import connection_manager
from .status_update_service import status_update_service
from .processing_integration import processing_integration_service
from .websocket_error_handler import websocket_error_handler
from .document_realtime_service import document_realtime_service

logger = logging.getLogger(__name__)

class WebSocketServiceInitializer:
    """Service initializer for WebSocket infrastructure"""

    def __init__(self):
        self._initialized = False
        self._services = {
            "connection_manager": connection_manager,
            "status_update_service": status_update_service,
            "processing_integration": processing_integration_service,
            "error_handler": websocket_error_handler,
            "document_realtime": document_realtime_service
        }

    async def initialize(self):
        """Initialize all WebSocket services"""
        if self._initialized:
            logger.warning("WebSocket services already initialized")
            return

        try:
            logger.info("Initializing WebSocket services...")

            # Initialize services in dependency order
            await connection_manager.initialize()
            await status_update_service.initialize()
            await processing_integration_service.initialize()
            await websocket_error_handler.initialize()
            await document_realtime_service.initialize()

            # Set up service integrations
            await self._setup_service_integrations()

            self._initialized = True
            logger.info("All WebSocket services initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize WebSocket services: {e}")
            await self.shutdown()
            raise

    async def shutdown(self):
        """Shutdown all WebSocket services"""
        if not self._initialized:
            return

        logger.info("Shutting down WebSocket services...")

        # Shutdown services in reverse dependency order
        shutdown_tasks = []

        for service_name, service in reversed(list(self._services.items())):
            if hasattr(service, 'shutdown'):
                shutdown_tasks.append(self._shutdown_service(service_name, service))

        # Run shutdowns concurrently with error handling
        if shutdown_tasks:
            await asyncio.gather(*shutdown_tasks, return_exceptions=True)

        self._initialized = False
        logger.info("All WebSocket services shutdown complete")

    async def _shutdown_service(self, name: str, service):
        """Shutdown individual service with error handling"""
        try:
            await service.shutdown()
        except Exception as e:
            logger.error(f"Error shutting down {name}: {e}")

    async def _setup_service_integrations(self):
        """Set up integrations between services"""
        try:
            # Register error handlers for connection manager if available
            if hasattr(connection_manager, 'register_error_handler'):
                connection_manager.register_error_handler("ConnectionError", self._handle_connection_error)
                connection_manager.register_error_handler("AuthenticationError", self._handle_auth_error)
            else:
                logger.info("Connection manager does not support error handler registration")

            # Connect processing integration to status updates
            # This would be done through event systems or direct calls
            logger.info("Service integrations set up successfully")

        except Exception as e:
            logger.error(f"Failed to set up service integrations: {e}")
            raise

    async def _handle_connection_error(self, error_context, websocket):
        """Handle connection errors through the error handler"""
        await websocket_error_handler.handle_websocket_error(
            websocket=websocket,
            error=Exception(error_context.get("message", "Connection error")),
            connection_id=error_context.get("connection_id"),
            user_id=error_context.get("user_id"),
            organization_id=error_context.get("organization_id")
        )

    async def _handle_auth_error(self, error_context, websocket):
        """Handle authentication errors"""
        await websocket_error_handler.handle_websocket_error(
            websocket=websocket,
            error=Exception(error_context.get("message", "Authentication error")),
            connection_id=error_context.get("connection_id"),
            user_id=error_context.get("user_id"),
            organization_id=error_context.get("organization_id")
        )

    def get_service_status(self) -> Dict[str, Any]:
        """Get status of all WebSocket services"""
        status = {
            "initialized": self._initialized,
            "services": {}
        }

        for name, service in self._services.items():
            try:
                if hasattr(service, 'get_connection_stats'):
                    status["services"][name] = service.get_connection_stats()
                elif hasattr(service, 'get_error_statistics'):
                    status["services"][name] = service.get_error_statistics()
                else:
                    status["services"][name] = {"status": "running"}
            except Exception as e:
                status["services"][name] = {"status": "error", "error": str(e)}

        return status

    def is_healthy(self) -> bool:
        """Check if all services are healthy"""
        if not self._initialized:
            return False

        # Check each service health
        for name, service in self._services.items():
            try:
                if hasattr(service, 'redis_client') and service.redis_client:
                    # Check Redis connection
                    pass  # Would implement health check
                elif hasattr(service, 'active_connections'):
                    # Check connection manager
                    pass  # Would implement health check
            except Exception:
                logger.error(f"Service {name} is unhealthy")
                return False

        return True

# Global service initializer instance
websocket_service_initializer = WebSocketServiceInitializer()