"""
WebSocket services for real-time communication
"""

from .websocket_manager import ConnectionInfo
from .websocket_manager import EnhancedConnectionManager as WebSocketManager
from .websocket_manager import MessageType, WebSocketMessage, connection_manager


# Lazy load other components to avoid circular imports
def get_websocket_error_handler():
    from .websocket_error_handler import websocket_error_handler

    return websocket_error_handler


def get_websocket_service_initializer():
    from .websocket_service_initializer import WebSocketServiceInitializer

    return WebSocketServiceInitializer


__all__ = [
    "WebSocketManager",
    "EnhancedConnectionManager",
    "connection_manager",
    "WebSocketMessage",
    "MessageType",
    "ConnectionInfo",
    "get_websocket_error_handler",
    "get_websocket_service_initializer",
]
