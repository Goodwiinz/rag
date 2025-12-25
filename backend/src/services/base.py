"""
Base service class for enterprise services
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from abc import ABC, abstractmethod


class BaseService(ABC):
    """Base service class with common functionality for all enterprise services"""

    def __init__(self, logger_name: Optional[str] = None):
        """Initialize the base service with optional custom logger name"""
        self.logger_name = logger_name or self.__class__.__name__
        self.logger = logging.getLogger(self.logger_name)
        self._created_at = datetime.utcnow()

    @property
    def service_name(self) -> str:
        """Get the service name"""
        return self.__class__.__name__

    def log_info(self, message: str, **kwargs):
        """Log an info message"""
        extra_info = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
        full_message = f"{message} | {extra_info}" if extra_info else message
        self.logger.info(f"[{self.service_name}] {full_message}")

    def log_error(self, message: str, error: Optional[Exception] = None, **kwargs):
        """Log an error message"""
        extra_info = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
        full_message = f"{message} | {extra_info}" if extra_info else message
        if error:
            self.logger.error(f"[{self.service_name}] {full_message} | Error: {str(error)}", exc_info=True)
        else:
            self.logger.error(f"[{self.service_name}] {full_message}")

    def log_warning(self, message: str, **kwargs):
        """Log a warning message"""
        extra_info = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
        full_message = f"{message} | {extra_info}" if extra_info else message
        self.logger.warning(f"[{self.service_name}] {full_message}")

    def log_debug(self, message: str, **kwargs):
        """Log a debug message"""
        extra_info = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
        full_message = f"{message} | {extra_info}" if extra_info else message
        self.logger.debug(f"[{self.service_name}] {full_message}")

    def get_service_info(self) -> Dict[str, Any]:
        """Get service information"""
        return {
            "service_name": self.service_name,
            "created_at": self._created_at.isoformat(),
            "logger_name": self.logger_name
        }

    async def initialize(self):
        """Initialize the service (override in subclasses)"""
        self.log_info("Service initializing")

    async def cleanup(self):
        """Cleanup the service (override in subclasses)"""
        self.log_info("Service cleaning up")

    async def shutdown(self):
        """Shutdown the service (override in subclasses)"""
        self.log_info("Service shutting down")

    async def health_check(self) -> Dict[str, Any]:
        """Perform a health check (override in subclasses)"""
        return {
            "service": self.service_name,
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat()
        }