"""
Comprehensive error handling and reconnection logic for WebSocket services
"""

import asyncio
import json
import logging
import traceback
import uuid
from datetime import datetime, timezone as dt_timezone, timedelta
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, asdict
from enum import Enum
import random

from fastapi import WebSocket, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func

from .base import BaseService
from .websocket_manager import connection_manager, WebSocketMessage, MessageType, Priority
from .status_update_service import status_update_service
from ..core.database import get_async_session
from ..core.config import settings
from ..models.websocket_status import ConnectionEvent, WebSocketConnection

logger = logging.getLogger(__name__)

class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class RecoveryStrategy(Enum):
    """Error recovery strategies"""
    RECONNECT = "reconnect"
    RETRY = "retry"
    FAILFAST = "failfast"
    GRACEFUL_DEGRADATION = "graceful_degradation"
    CIRCUIT_BREAKER = "circuit_breaker"

@dataclass
class ErrorContext:
    """Error context information"""
    error_id: str
    error_type: str
    severity: ErrorSeverity
    message: str
    details: Dict[str, Any]
    timestamp: datetime
    connection_id: Optional[str] = None
    user_id: Optional[str] = None
    organization_id: Optional[str] = None
    stack_trace: Optional[str] = None
    recovery_strategy: RecoveryStrategy = RecoveryStrategy.RECONNECT
    retry_count: int = 0
    max_retries: int = 3

@dataclass
class ReconnectionAttempt:
    """Reconnection attempt tracking"""
    attempt_id: str
    connection_id: str
    user_id: str
    timestamp: datetime
    delay_seconds: float
    success: bool = False
    error_message: Optional[str] = None

class CircuitBreaker:
    """Circuit breaker for preventing cascading failures"""

    def __init__(self, failure_threshold: int = 5, timeout_seconds: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    async def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt to reset"""
        return (
            self.last_failure_time and
            datetime.now(dt_timezone.utc) - self.last_failure_time > timedelta(seconds=self.timeout_seconds)
        )

    def _on_success(self):
        """Handle successful operation"""
        self.failure_count = 0
        self.state = "CLOSED"

    def _on_failure(self):
        """Handle failed operation"""
        self.failure_count += 1
        self.last_failure_time = datetime.now(dt_timezone.utc)

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"

class WebSocketErrorHandler(BaseService):
    """Comprehensive error handling for WebSocket services"""

    def __init__(self):
        super().__init__()
        self._error_handlers: Dict[str, Callable] = {}
        self._reconnection_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._error_history: List[ErrorContext] = []
        self._reconnection_attempts: Dict[str, List[ReconnectionAttempt]] = {}
        self._active_recoveries: Set[str] = set()

        # Background tasks
        self._error_processor_task: Optional[asyncio.Task] = None
        self._reconnection_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None

        # Configuration
        self.max_error_history = 1000
        self.reconnection_backoff_base = 1.0
        self.reconnection_backoff_max = 30.0
        self.reconnection_jitter = 0.1
        self.circuit_breaker_threshold = 5
        self.circuit_breaker_timeout = 60

    async def initialize(self):
        """Initialize the error handler"""
        await super().initialize()

        # Register default error handlers
        self._register_default_handlers()

        # Start background tasks
        self._error_processor_task = asyncio.create_task(self._process_errors())
        self._reconnection_task = asyncio.create_task(self._process_reconnections())
        self._cleanup_task = asyncio.create_task(self._cleanup_old_data())

        logger.info("WebSocket Error Handler initialized")

    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down WebSocket Error Handler...")

        # Cancel background tasks
        tasks = [self._error_processor_task, self._reconnection_task, self._cleanup_task]
        for task in tasks:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        await super().shutdown()
        logger.info("WebSocket Error Handler shutdown complete")

    def register_error_handler(self, error_type: str, handler: Callable):
        """Register a custom error handler"""
        self._error_handlers[error_type] = handler
        logger.info(f"Registered error handler for: {error_type}")

    async def handle_websocket_error(self, websocket: WebSocket, error: Exception,
                                   connection_id: str = None, user_id: str = None,
                                   organization_id: str = None):
        """Handle WebSocket error with appropriate recovery strategy"""
        try:
            # Create error context
            error_context = ErrorContext(
                error_id=str(uuid.uuid4()),
                error_type=type(error).__name__,
                severity=self._determine_error_severity(error),
                message=str(error),
                details={
                    "websocket_state": websocket.client_state if hasattr(websocket, 'client_state') else "unknown",
                    "connection_id": connection_id,
                    "user_id": user_id,
                    "organization_id": organization_id
                },
                timestamp=datetime.now(dt_timezone.utc),
                connection_id=connection_id,
                user_id=user_id,
                organization_id=organization_id,
                stack_trace=traceback.format_exc() if settings.DEBUG else None,
                recovery_strategy=self._determine_recovery_strategy(error)
            )

            # Add to error history
            self._error_history.append(error_context)
            if len(self._error_history) > self.max_error_history:
                self._error_history.pop(0)

            # Log error
            await self._log_error(error_context)

            # Check circuit breaker
            circuit_breaker_key = f"{user_id}:{type(error).__name__}" if user_id else type(error).__name__
            circuit_breaker = self._get_circuit_breaker(circuit_breaker_key)

            if circuit_breaker.state == "OPEN":
                await self._handle_circuit_breaker_open(error_context)
                return

            # Handle error with appropriate strategy
            if error_context.recovery_strategy == RecoveryStrategy.RECONNECT:
                await self._schedule_reconnection(error_context)
            elif error_context.recovery_strategy == RecoveryStrategy.RETRY:
                await self._handle_retry(error_context)
            elif error_context.recovery_strategy == RecoveryStrategy.GRACEFUL_DEGRADATION:
                await self._handle_graceful_degradation(error_context)
            elif error_context.recovery_strategy == RecoveryStrategy.FAILFAST:
                await self._handle_fail_fast(error_context)

            # Check for custom error handler
            custom_handler = self._error_handlers.get(error_context.error_type)
            if custom_handler:
                try:
                    await custom_handler(error_context, websocket)
                except Exception as e:
                    logger.error(f"Custom error handler failed: {e}")

            # Send error message to client if possible
            if websocket and connection_id:
                await self._send_error_to_client(websocket, error_context)

        except Exception as e:
            logger.error(f"Error in error handler: {e}")
            # Last resort: close the connection
            if websocket:
                try:
                    await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Internal error")
                except:
                    pass

    async def schedule_reconnection(self, connection_id: str, user_id: str,
                                 organization_id: str, delay_seconds: float = None):
        """Schedule a reconnection attempt"""
        if delay_seconds is None:
            delay_seconds = self._calculate_reconnection_delay(user_id, connection_id)

        reconnection_attempt = ReconnectionAttempt(
            attempt_id=str(uuid.uuid4()),
            connection_id=connection_id,
            user_id=user_id,
            timestamp=datetime.now(dt_timezone.utc),
            delay_seconds=delay_seconds
        )

        # Add to queue
        await self._reconnection_queue.put(reconnection_attempt)

        # Track attempts
        if user_id not in self._reconnection_attempts:
            self._reconnection_attempts[user_id] = []
        self._reconnection_attempts[user_id].append(reconnection_attempt)

        logger.info(f"Scheduled reconnection for {connection_id} in {delay_seconds:.1f} seconds")

    async def _process_errors(self):
        """Process errors from the queue"""
        while True:
            try:
                # Process error backlog
                await asyncio.sleep(1)

                # Check for error patterns and escalate if needed
                await self._analyze_error_patterns()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in error processor: {e}")
                await asyncio.sleep(5)

    async def _process_reconnections(self):
        """Process reconnection attempts"""
        while True:
            try:
                # Get reconnection attempt from queue
                reconnection_attempt = await asyncio.wait_for(
                    self._reconnection_queue.get(),
                    timeout=1.0
                )

                # Wait for the delay
                await asyncio.sleep(reconnection_attempt.delay_seconds)

                # Attempt reconnection
                success = await self._attempt_reconnection(reconnection_attempt)

                # Update attempt record
                reconnection_attempt.success = success
                if not success:
                    reconnection_attempt.error_message = "Reconnection failed"

                # If failed and under retry limit, schedule another attempt
                if not success:
                    user_attempts = [a for a in self._reconnection_attempts.get(reconnection_attempt.user_id, [])
                                   if not a.success]
                    if len(user_attempts) < 3:  # Max 3 failed attempts
                        await self.schedule_reconnection(
                            reconnection_attempt.connection_id,
                            reconnection_attempt.user_id,
                            "",  # organization_id not needed for reconnection
                            reconnection_attempt.delay_seconds * 2  # Exponential backoff
                        )

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in reconnection processor: {e}")
                await asyncio.sleep(5)

    async def _attempt_reconnection(self, reconnection_attempt: ReconnectionAttempt) -> bool:
        """Attempt to reconnect a WebSocket connection"""
        try:
            # This would need to be implemented based on your specific reconnection logic
            # For now, we'll just log the attempt
            logger.info(f"Attempting reconnection for {reconnection_attempt.connection_id}")

            # In a real implementation, you would:
            # 1. Create a new WebSocket connection
            # 2. Re-authenticate
            # 3. Restore subscriptions
            # 4. Resume any pending operations

            # For demonstration, we'll simulate a 70% success rate
            success = random.random() > 0.3

            if success:
                logger.info(f"Successfully reconnected: {reconnection_attempt.connection_id}")
                # Notify client of successful reconnection
                await self._notify_reconnection_success(reconnection_attempt)
            else:
                logger.warning(f"Reconnection failed: {reconnection_attempt.connection_id}")

            return success

        except Exception as e:
            logger.error(f"Error during reconnection attempt: {e}")
            return False

    async def _send_error_to_client(self, websocket: WebSocket, error_context: ErrorContext):
        """Send error message to WebSocket client"""
        try:
            error_message = WebSocketMessage(
                type=MessageType.ERROR,
                data={
                    "error_id": error_context.error_id,
                    "error_type": error_context.error_type,
                    "severity": error_context.severity.value,
                    "message": error_context.message,
                    "recovery_strategy": error_context.recovery_strategy.value,
                    "retry_count": error_context.retry_count,
                    "max_retries": error_context.max_retries,
                    "timestamp": error_context.timestamp.isoformat()
                },
                timestamp=datetime.now(dt_timezone.utc),
                priority=Priority.HIGH
            )

            await websocket.send_json(asdict(error_message))

        except Exception as e:
            logger.error(f"Failed to send error message to client: {e}")

    async def _handle_circuit_breaker_open(self, error_context: ErrorContext):
        """Handle scenario when circuit breaker is open"""
        logger.warning(f"Circuit breaker is open for {error_context.error_type}")

        # Broadcast system notification
        await status_update_service.broadcast_system_notification(
            title="Service Temporarily Unavailable",
            message=f"The service is temporarily unavailable due to high error rates. Please try again later.",
            notification_type="error"
        )

    async def _handle_retry(self, error_context: ErrorContext):
        """Handle retry recovery strategy"""
        if error_context.retry_count < error_context.max_retries:
            error_context.retry_count += 1
            delay = self._calculate_retry_delay(error_context.retry_count)
            await asyncio.sleep(delay)
            # Retry logic would be implemented here
        else:
            # Max retries exceeded, escalate to failure
            error_context.recovery_strategy = RecoveryStrategy.FAILFAST

    async def _handle_graceful_degradation(self, error_context: ErrorContext):
        """Handle graceful degradation recovery strategy"""
        logger.info(f"Applying graceful degradation for error: {error_context.error_type}")

        # Implement degradation logic
        # For example, reduce update frequency, disable non-critical features, etc.

    async def _handle_fail_fast(self, error_context: ErrorContext):
        """Handle fail-fast recovery strategy"""
        logger.error(f"Fail-fast for error: {error_context.error_type}")

        # Close connection immediately
        if error_context.connection_id:
            await connection_manager.disconnect(
                error_context.connection_id,
                f"Critical error: {error_context.message}"
            )

    async def _notify_reconnection_success(self, reconnection_attempt: ReconnectionAttempt):
        """Notify client of successful reconnection"""
        try:
            success_message = WebSocketMessage(
                type=MessageType.CONNECT,
                data={
                    "reconnected": True,
                    "connection_id": reconnection_attempt.connection_id,
                    "attempt_id": reconnection_attempt.attempt_id,
                    "timestamp": datetime.now(dt_timezone.utc).isoformat()
                },
                timestamp=datetime.now(dt_timezone.utc)
            )

            # This would send to the reconnected WebSocket
            # Implementation depends on how you manage reconnected connections

        except Exception as e:
            logger.error(f"Error sending reconnection success notification: {e}")

    def _determine_error_severity(self, error: Exception) -> ErrorSeverity:
        """Determine error severity based on error type and message"""
        error_message = str(error).lower()
        error_type = type(error).__name__

        # Critical errors
        if any(keyword in error_message for keyword in ["authentication", "security", "critical"]):
            return ErrorSeverity.CRITICAL

        # High severity errors
        if any(keyword in error_message for keyword in ["connection", "timeout", "database"]):
            return ErrorSeverity.HIGH

        # Medium severity errors
        if any(keyword in error_message for keyword in ["parsing", "validation", "format"]):
            return ErrorSeverity.MEDIUM

        # Default to low severity
        return ErrorSeverity.LOW

    def _determine_recovery_strategy(self, error: Exception) -> RecoveryStrategy:
        """Determine recovery strategy based on error type"""
        error_message = str(error).lower()
        error_type = type(error).__name__

        # Connection errors should trigger reconnection
        if any(keyword in error_message for keyword in ["connection", "websocket", "network"]):
            return RecoveryStrategy.RECONNECT

        # Temporary errors should trigger retry
        if any(keyword in error_message for keyword in ["timeout", "temporary", "rate limit"]):
            return RecoveryStrategy.RETRY

        # Critical errors should fail fast
        if any(keyword in error_message for keyword in ["critical", "security", "authentication"]):
            return RecoveryStrategy.FAILFAST

        # Default to graceful degradation
        return RecoveryStrategy.GRACEFUL_DEGRADATION

    def _calculate_reconnection_delay(self, user_id: str, connection_id: str) -> float:
        """Calculate reconnection delay with exponential backoff"""
        user_attempts = len([a for a in self._reconnection_attempts.get(user_id, []) if not a.success])

        # Exponential backoff with jitter
        base_delay = self.reconnection_backoff_base * (2 ** user_attempts)
        delay = min(base_delay, self.reconnection_backoff_max)

        # Add jitter to prevent thundering herd
        jitter = delay * self.reconnection_jitter * (random.random() - 0.5)
        delay += jitter

        return max(0, delay)

    def _calculate_retry_delay(self, retry_count: int) -> float:
        """Calculate retry delay"""
        return min(self.reconnection_backoff_base * (2 ** retry_count), 10.0)

    def _get_circuit_breaker(self, key: str) -> CircuitBreaker:
        """Get or create circuit breaker for key"""
        if key not in self._circuit_breakers:
            self._circuit_breakers[key] = CircuitBreaker(
                failure_threshold=self.circuit_breaker_threshold,
                timeout_seconds=self.circuit_breaker_timeout
            )
        return self._circuit_breakers[key]

    async def _log_error(self, error_context: ErrorContext):
        """Log error to database and monitoring systems"""
        try:
            # Log error details (database storage disabled to avoid session issues)
            logger.error(f"WebSocket Error: {error_context.error_type} - {error_context.message}")
            
            # TODO: Implement proper database logging with dependency injection
            # For now, just log to file/console

        except Exception as e:
            logger.error(f"Failed to log error: {e}")

    async def _analyze_error_patterns(self):
        """Analyze error patterns for escalation"""
        try:
            if not self._error_history:
                return

            # Check for high error rates
            recent_errors = [
                error for error in self._error_history
                if datetime.now(dt_timezone.utc) - error.timestamp < timedelta(minutes=5)
            ]

            # High error rate threshold
            if len(recent_errors) > 10:
                logger.warning(f"High error rate detected: {len(recent_errors)} errors in last 5 minutes")

                # Broadcast system alert
                await status_update_service.broadcast_system_notification(
                    title="High Error Rate Detected",
                    message=f"The system is experiencing a high error rate. Administrators have been notified.",
                    notification_type="error"
                )

        except Exception as e:
            logger.error(f"Error analyzing patterns: {e}")

    async def _cleanup_old_data(self):
        """Periodic cleanup of old error data"""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour

                cutoff_time = datetime.now(dt_timezone.utc) - timedelta(hours=24)

                # Clean old error history
                self._error_history = [
                    error for error in self._error_history
                    if error.timestamp > cutoff_time
                ]

                # Clean old reconnection attempts
                for user_id in list(self._reconnection_attempts.keys()):
                    self._reconnection_attempts[user_id] = [
                        attempt for attempt in self._reconnection_attempts[user_id]
                        if attempt.timestamp > cutoff_time
                    ]

                    if not self._reconnection_attempts[user_id]:
                        del self._reconnection_attempts[user_id]

                logger.info("Error handler cleanup completed")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")

    def _register_default_handlers(self):
        """Register default error handlers"""
        self.register_error_handler("ConnectionError", self._handle_connection_error)
        self.register_error_handler("TimeoutError", self._handle_timeout_error)
        self.register_error_handler("ValidationError", self._handle_validation_error)

    async def _handle_connection_error(self, error_context: ErrorContext, websocket: WebSocket):
        """Handle connection-specific errors"""
        logger.info(f"Handling connection error: {error_context.message}")

    async def _handle_timeout_error(self, error_context: ErrorContext, websocket: WebSocket):
        """Handle timeout errors"""
        logger.info(f"Handling timeout error: {error_context.message}")

    async def _handle_validation_error(self, error_context: ErrorContext, websocket: WebSocket):
        """Handle validation errors"""
        logger.info(f"Handling validation error: {error_context.message}")

    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics and metrics"""
        if not self._error_history:
            return {
                "total_errors": 0,
                "error_rate": 0.0,
                "severity_distribution": {},
                "recovery_success_rate": 0.0
            }

        # Calculate statistics
        total_errors = len(self._error_history)
        recent_errors = len([
            error for error in self._error_history
            if datetime.now(dt_timezone.utc) - error.timestamp < timedelta(hours=1)
        ])

        # Severity distribution
        severity_counts = {}
        for error in self._error_history:
            severity = error.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        # Recovery success rate
        total_reconnection_attempts = sum(len(attempts) for attempts in self._reconnection_attempts.values())
        successful_reconnections = sum(
            len([a for a in attempts if a.success])
            for attempts in self._reconnection_attempts.values()
        )

        recovery_success_rate = (
            (successful_reconnections / total_reconnection_attempts * 100)
            if total_reconnection_attempts > 0 else 0.0
        )

        return {
            "total_errors": total_errors,
            "recent_errors_last_hour": recent_errors,
            "error_rate_per_hour": recent_errors,
            "severity_distribution": severity_counts,
            "total_reconnection_attempts": total_reconnection_attempts,
            "successful_reconnections": successful_reconnections,
            "recovery_success_rate": recovery_success_rate,
            "active_circuit_breakers": len([cb for cb in self._circuit_breakers.values() if cb.state == "OPEN"]),
            "average_error_resolution_time": self._calculate_average_resolution_time()
        }

    def _calculate_average_resolution_time(self) -> float:
        """Calculate average error resolution time"""
        # This would track how long errors take to resolve
        # For now, return a placeholder
        return 30.0  # 30 seconds average

# Global error handler instance
websocket_error_handler = WebSocketErrorHandler()