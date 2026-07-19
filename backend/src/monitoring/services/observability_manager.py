"""
Observability Manager

Central orchestrator for all monitoring and observability services.
Manages the lifecycle and coordination of metrics, tracing, logging,
alerting, and health checking components.
"""

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from ..config.monitoring_config import MonitoringConfig, get_monitoring_config
from ..utils.exceptions import ObservabilityError
from .alert_handler import AlertHandler
from .health_check_hub import HealthCheckHub
from .log_aggregator import LogAggregator
from .metrics_collector import MetricsCollector
from .tracing_collector import TracingCollector

logger = logging.getLogger(__name__)


class ObservabilityManager:
    """
    Central manager for all observability services.

    Coordinates initialization, configuration, and lifecycle of
    monitoring components while providing a unified interface.
    """

    def __init__(self, config: Optional[MonitoringConfig] = None):
        """Initialize the observability manager"""
        self.config = config or get_monitoring_config()
        self._initialized = False
        self._running = False

        # Service instances
        self.metrics_collector: Optional[MetricsCollector] = None
        self.tracing_collector: Optional[TracingCollector] = None
        self.log_aggregator: Optional[LogAggregator] = None
        self.alert_handler: Optional[AlertHandler] = None
        self.health_check_hub: Optional[HealthCheckHub] = None

        # Background tasks
        self._background_tasks: List[asyncio.Task] = []

        # Service state
        self.service_registry: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize all monitoring services"""
        async with self._lock:
            if self._initialized:
                logger.warning("Observability manager already initialized")
                return

            try:
                logger.info("Initializing observability manager...")

                # Initialize services in dependency order
                await self._initialize_metrics()
                await self._initialize_tracing()
                await self._initialize_logging()
                await self._initialize_alerting()
                await self._initialize_health_checks()

                # Register services
                await self._register_services()

                self._initialized = True
                logger.info("✅ Observability manager initialized successfully")

            except Exception as e:
                logger.error(f"❌ Failed to initialize observability manager: {e}")
                await self._cleanup_services()
                raise ObservabilityError(f"Initialization failed: {e}")

    async def start(self) -> None:
        """Start all monitoring services and background tasks"""
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            if self._running:
                logger.warning("Observability manager already running")
                return

            try:
                logger.info("Starting observability manager...")

                # Start services
                await self._start_services()

                # Start background tasks
                await self._start_background_tasks()

                self._running = True
                logger.info("✅ Observability manager started successfully")

            except Exception as e:
                logger.error(f"❌ Failed to start observability manager: {e}")
                await self.stop()
                raise ObservabilityError(f"Start failed: {e}")

    async def stop(self) -> None:
        """Stop all monitoring services and background tasks"""
        async with self._lock:
            if not self._running:
                logger.warning("Observability manager not running")
                return

            try:
                logger.info("Stopping observability manager...")

                # Cancel background tasks
                await self._stop_background_tasks()

                # Stop services
                await self._stop_services()

                self._running = False
                logger.info("✅ Observability manager stopped successfully")

            except Exception as e:
                logger.error(f"❌ Error stopping observability manager: {e}")
                # Continue with cleanup even if there are errors

    async def shutdown(self) -> None:
        """Complete shutdown and cleanup of observability manager"""
        await self.stop()
        await self._cleanup_services()
        self._initialized = False
        logger.info("✅ Observability manager shutdown complete")

    async def health_check(self) -> Dict[str, Any]:
        """
        Get comprehensive health status of all observability services

        Returns:
            Dictionary containing health status of all services
        """
        health_status = {
            "manager": {
                "initialized": self._initialized,
                "running": self._running,
                "uptime_seconds": self._get_uptime_seconds() if self._running else 0,
                "background_tasks_count": len(self._background_tasks),
                "status": "healthy" if self._running else "stopped",
            },
            "services": {},
        }

        if not self._initialized:
            return health_status

        try:
            # Get health status from each service
            if self.metrics_collector:
                health_status["services"][
                    "metrics"
                ] = await self.metrics_collector.get_health_status()

            if self.tracing_collector:
                health_status["services"][
                    "tracing"
                ] = await self.tracing_collector.get_health_status()

            if self.log_aggregator:
                health_status["services"][
                    "logging"
                ] = await self.log_aggregator.get_health_status()

            if self.alert_handler:
                health_status["services"][
                    "alerting"
                ] = await self.alert_handler.get_health_status()

            if self.health_check_hub:
                health_status["services"][
                    "health_checks"
                ] = await self.health_check_hub.get_health_status()

            # Determine overall health
            service_statuses = [
                service.get("status", "unknown")
                for service in health_status["services"].values()
            ]

            if "unhealthy" in service_statuses:
                health_status["manager"]["status"] = "unhealthy"
            elif "degraded" in service_statuses:
                health_status["manager"]["status"] = "degraded"

        except Exception as e:
            logger.error(f"Error collecting health status: {e}")
            health_status["manager"]["status"] = "error"
            health_status["error"] = str(e)

        return health_status

    async def get_metrics(
        self,
        service: Optional[str] = None,
        metric_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        labels: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Get metrics from the metrics collector

        Args:
            service: Optional service filter
            metric_name: Optional metric name filter
            start_time: Optional start time filter
            end_time: Optional end time filter
            labels: Optional label filters

        Returns:
            Dictionary containing metrics data
        """
        if not self.metrics_collector:
            raise ObservabilityError("Metrics collector not initialized")

        return await self.metrics_collector.get_metrics(
            service=service,
            metric_name=metric_name,
            start_time=start_time,
            end_time=end_time,
            labels=labels,
        )

    async def get_traces(
        self,
        trace_id: Optional[str] = None,
        service: Optional[str] = None,
        operation: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Get traces from the tracing collector

        Args:
            trace_id: Optional trace ID filter
            service: Optional service filter
            operation: Optional operation filter
            start_time: Optional start time filter
            end_time: Optional end time filter
            limit: Maximum number of traces to return

        Returns:
            Dictionary containing trace data
        """
        if not self.tracing_collector:
            raise ObservabilityError("Tracing collector not initialized")

        return await self.tracing_collector.get_traces(
            trace_id=trace_id,
            service=service,
            operation=operation,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )

    async def get_logs(
        self,
        level: Optional[str] = None,
        service: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        search: Optional[str] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Get logs from the log aggregator

        Args:
            level: Optional log level filter
            service: Optional service filter
            start_time: Optional start time filter
            end_time: Optional end time filter
            search: Optional search string
            limit: Maximum number of logs to return

        Returns:
            Dictionary containing log data
        """
        if not self.log_aggregator:
            raise ObservabilityError("Log aggregator not initialized")

        return await self.log_aggregator.get_logs(
            level=level,
            service=service,
            start_time=start_time,
            end_time=end_time,
            search=search,
            limit=limit,
        )

    async def get_alerts(
        self,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        service: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Get alerts from the alert handler

        Args:
            severity: Optional severity filter
            status: Optional status filter
            service: Optional service filter
            start_time: Optional start time filter
            end_time: Optional end time filter
            limit: Maximum number of alerts to return

        Returns:
            Dictionary containing alert data
        """
        if not self.alert_handler:
            raise ObservabilityError("Alert handler not initialized")

        return await self.alert_handler.get_alerts(
            severity=severity,
            status=status,
            service=service,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )

    async def create_alert_rule(
        self,
        name: str,
        conditions: Dict[str, Any],
        severity: str = "medium",
        channels: Optional[List[str]] = None,
        **kwargs,
    ) -> str:
        """
        Create a new alert rule

        Args:
            name: Alert rule name
            conditions: Alert conditions
            severity: Alert severity
            channels: Notification channels
            **kwargs: Additional alert rule parameters

        Returns:
            ID of the created alert rule
        """
        if not self.alert_handler:
            raise ObservabilityError("Alert handler not initialized")

        return await self.alert_handler.create_rule(
            name=name,
            conditions=conditions,
            severity=severity,
            channels=channels,
            **kwargs,
        )

    async def acknowledge_alert(
        self, alert_id: str, user: str, message: Optional[str] = None
    ) -> bool:
        """
        Acknowledge an alert

        Args:
            alert_id: ID of the alert to acknowledge
            user: User acknowledging the alert
            message: Optional acknowledgment message

        Returns:
            True if successful, False otherwise
        """
        if not self.alert_handler:
            raise ObservabilityError("Alert handler not initialized")

        return await self.alert_handler.acknowledge_alert(
            alert_id=alert_id, user=user, message=message
        )

    async def resolve_alert(
        self, alert_id: str, user: str, message: Optional[str] = None
    ) -> bool:
        """
        Resolve an alert

        Args:
            alert_id: ID of the alert to resolve
            user: User resolving the alert
            message: Optional resolution message

        Returns:
            True if successful, False otherwise
        """
        if not self.alert_handler:
            raise ObservabilityError("Alert handler not initialized")

        return await self.alert_handler.resolve_alert(
            alert_id=alert_id, user=user, message=message
        )

    async def get_service_health(self) -> Dict[str, Any]:
        """Get health status of all monitored services"""
        if not self.health_check_hub:
            raise ObservabilityError("Health check hub not initialized")

        return await self.health_check_hub.get_overall_health()

    async def create_correlation_id(self) -> str:
        """Create a new correlation ID for request tracking"""
        return str(uuid.uuid4())

    @asynccontextmanager
    async def trace_operation(
        self,
        operation_name: str,
        service: str,
        component: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
    ):
        """
        Context manager for tracing operations

        Args:
            operation_name: Name of the operation
            service: Service name
            component: Optional component name
            labels: Optional span labels
        """
        if not self.tracing_collector:
            # If tracing is not initialized, just yield
            yield
            return

        span_context = await self.tracing_collector.start_span(
            operation_name=operation_name,
            service=service,
            component=component,
            labels=labels or {},
        )

        try:
            yield span_context
            await self.tracing_collector.finish_span(span_context, status="ok")
        except Exception as e:
            await self.tracing_collector.finish_span(
                span_context, status="error", error=str(e)
            )
            raise

    def _get_uptime_seconds(self) -> float:
        """Get uptime in seconds (simplified implementation)"""
        # In a real implementation, you'd track the start time
        return 0.0

    async def _initialize_metrics(self) -> None:
        """Initialize metrics collector"""
        try:
            if self.config.metrics.custom_metrics_enabled:
                self.metrics_collector = MetricsCollector(self.config.metrics)
                await self.metrics_collector.initialize()
                logger.info("✅ Metrics collector initialized")
            else:
                logger.info("⚠️ Metrics collection disabled")
        except Exception as e:
            logger.error(f"❌ Failed to initialize metrics collector: {e}")
            raise

    async def _initialize_tracing(self) -> None:
        """Initialize tracing collector"""
        try:
            if self.config.tracing.enabled:
                self.tracing_collector = TracingCollector(self.config.tracing)
                await self.tracing_collector.initialize()
                logger.info("✅ Tracing collector initialized")
            else:
                logger.info("⚠️ Distributed tracing disabled")
        except Exception as e:
            logger.error(f"❌ Failed to initialize tracing collector: {e}")
            raise

    async def _initialize_logging(self) -> None:
        """Initialize log aggregator"""
        try:
            if self.config.logging.structured_logging:
                self.log_aggregator = LogAggregator(self.config.logging)
                await self.log_aggregator.initialize()
                logger.info("✅ Log aggregator initialized")
            else:
                logger.info("⚠️ Structured logging disabled")
        except Exception as e:
            logger.error(f"❌ Failed to initialize log aggregator: {e}")
            raise

    async def _initialize_alerting(self) -> None:
        """Initialize alert handler"""
        try:
            if self.config.alerting.enabled:
                self.alert_handler = AlertHandler(self.config.alerting)
                await self.alert_handler.initialize()
                logger.info("✅ Alert handler initialized")
            else:
                logger.info("⚠️ Alerting disabled")
        except Exception as e:
            logger.error(f"❌ Failed to initialize alert handler: {e}")
            raise

    async def _initialize_health_checks(self) -> None:
        """Initialize health check hub"""
        try:
            if self.config.health_check.enabled:
                self.health_check_hub = HealthCheckHub(self.config.health_check)
                await self.health_check_hub.initialize()
                logger.info("✅ Health check hub initialized")
            else:
                logger.info("⚠️ Health checks disabled")
        except Exception as e:
            logger.error(f"❌ Failed to initialize health check hub: {e}")
            raise

    async def _register_services(self) -> None:
        """Register services in the service registry"""
        services = {
            "metrics": {
                "instance": self.metrics_collector,
                "enabled": self.metrics_collector is not None,
                "config": self.config.metrics.dict()
                if self.metrics_collector
                else None,
            },
            "tracing": {
                "instance": self.tracing_collector,
                "enabled": self.tracing_collector is not None,
                "config": self.config.tracing.dict()
                if self.tracing_collector
                else None,
            },
            "logging": {
                "instance": self.log_aggregator,
                "enabled": self.log_aggregator is not None,
                "config": self.config.logging.dict() if self.log_aggregator else None,
            },
            "alerting": {
                "instance": self.alert_handler,
                "enabled": self.alert_handler is not None,
                "config": self.config.alerting.dict() if self.alert_handler else None,
            },
            "health_checks": {
                "instance": self.health_check_hub,
                "enabled": self.health_check_hub is not None,
                "config": self.config.health_check.dict()
                if self.health_check_hub
                else None,
            },
        }

        self.service_registry = services
        logger.info(
            f"✅ Registered {len([s for s in services.values() if s['enabled']])} monitoring services"
        )

    async def _start_services(self) -> None:
        """Start all monitoring services"""
        services_to_start = [
            self.metrics_collector,
            self.tracing_collector,
            self.log_aggregator,
            self.alert_handler,
            self.health_check_hub,
        ]

        for service in services_to_start:
            if service:
                try:
                    await service.start()
                    logger.info(f"✅ Started {service.__class__.__name__}")
                except Exception as e:
                    logger.error(f"❌ Failed to start {service.__class__.__name__}: {e}")
                    raise

    async def _stop_services(self) -> None:
        """Stop all monitoring services"""
        services_to_stop = [
            self.health_check_hub,
            self.alert_handler,
            self.log_aggregator,
            self.tracing_collector,
            self.metrics_collector,
        ]

        for service in services_to_stop:
            if service:
                try:
                    await service.stop()
                    logger.info(f"✅ Stopped {service.__class__.__name__}")
                except Exception as e:
                    logger.error(f"❌ Error stopping {service.__class__.__name__}: {e}")

    async def _start_background_tasks(self) -> None:
        """Start background monitoring tasks"""
        # Metrics collection task
        if self.metrics_collector:
            task = asyncio.create_task(self._metrics_collection_loop())
            self._background_tasks.append(task)

        # Health check task
        if self.health_check_hub:
            task = asyncio.create_task(self._health_check_loop())
            self._background_tasks.append(task)

        # Log aggregation task
        if self.log_aggregator:
            task = asyncio.create_task(self._log_aggregation_loop())
            self._background_tasks.append(task)

        logger.info(f"✅ Started {len(self._background_tasks)} background tasks")

    async def _stop_background_tasks(self) -> None:
        """Stop all background tasks"""
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self._background_tasks.clear()
        logger.info("✅ Stopped all background tasks")

    async def _cleanup_services(self) -> None:
        """Cleanup service resources"""
        services_to_cleanup = [
            self.health_check_hub,
            self.alert_handler,
            self.log_aggregator,
            self.tracing_collector,
            self.metrics_collector,
        ]

        for service in services_to_cleanup:
            if service:
                try:
                    await self._cleanup_service(service)
                except Exception as e:
                    logger.error(
                        f"❌ Error cleaning up {service.__class__.__name__}: {e}"
                    )

        # Clear service references
        self.metrics_collector = None
        self.tracing_collector = None
        self.log_aggregator = None
        self.alert_handler = None
        self.health_check_hub = None

    async def _cleanup_service(self, service) -> None:
        """Cleanup individual service"""
        if hasattr(service, "cleanup"):
            await service.cleanup()
        elif hasattr(service, "close"):
            await service.close()

    async def _metrics_collection_loop(self) -> None:
        """Background loop for metrics collection"""
        if not self.metrics_collector:
            return

        interval = self.config.metrics.collection_interval_seconds

        while self._running:
            try:
                await self.metrics_collector.collect_system_metrics()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in metrics collection loop: {e}")
                await asyncio.sleep(
                    min(interval, 60)
                )  # Wait at least 1 minute on error

    async def _health_check_loop(self) -> None:
        """Background loop for health checks"""
        if not self.health_check_hub:
            return

        interval = self.config.health_check.check_interval_seconds

        while self._running:
            try:
                await self.health_check_hub.run_all_checks()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(
                    min(interval, 60)
                )  # Wait at least 1 minute on error

    async def _log_aggregation_loop(self) -> None:
        """Background loop for log aggregation"""
        if not self.log_aggregator:
            return

        # Run aggregation every 5 minutes
        interval = 300

        while self._running:
            try:
                await self.log_aggregator.aggregate_logs()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in log aggregation loop: {e}")
                await asyncio.sleep(
                    min(interval, 60)
                )  # Wait at least 1 minute on error


# Global observability manager instance
_observability_manager: Optional[ObservabilityManager] = None


def get_observability_manager() -> ObservabilityManager:
    """Get the global observability manager instance"""
    global _observability_manager
    if _observability_manager is None:
        _observability_manager = ObservabilityManager()
    return _observability_manager
