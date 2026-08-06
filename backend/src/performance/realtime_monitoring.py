"""
Real-time Performance Monitoring System for the Multimodal Enterprise RAG System

This module provides real-time monitoring, alerting, and visualization of
system performance metrics with WebSocket support for live updates.
"""

import asyncio
import json
import logging
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

import aiofiles
import aiohttp
import asyncio_mqtt as aiomqtt
import numpy as np
import pandas as pd
import psutil
import redis
import websockets
from fastapi import WebSocket, WebSocketDisconnect
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    start_http_server,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class RealtimeMetric:
    """Real-time metric data point"""

    timestamp: datetime
    name: str
    value: float
    unit: str
    tags: Dict[str, str]
    source: str
    severity: str = "info"  # info, warning, critical


@dataclass
class Alert:
    """Performance alert definition"""

    id: str
    name: str
    description: str
    condition: str
    threshold: float
    severity: str
    metric_name: str
    is_active: bool
    created_at: datetime
    last_triggered: Optional[datetime] = None
    trigger_count: int = 0
    cooldown_minutes: int = 5


@dataclass
class PerformanceSnapshot:
    """Complete performance snapshot"""

    timestamp: datetime
    system_metrics: Dict[str, Any]
    application_metrics: Dict[str, Any]
    database_metrics: Dict[str, Any]
    network_metrics: Dict[str, Any]
    custom_metrics: Dict[str, Any]
    alerts: List[Alert]


class RealtimeMetricsCollector:
    """Collects real-time performance metrics from various sources"""

    def __init__(self):
        self.metrics_buffer: deque = deque(maxlen=10000)
        self.subscribers: Dict[str, WebSocket] = {}
        self.alert_rules: Dict[str, Alert] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.metric_collectors: Dict[str, Callable] = {}
        self.collection_interval = 5  # seconds
        self.is_running = False
        self.redis_client: Optional[redis.Redis] = None

        # Prometheus metrics
        self.prometheus_registry = CollectorRegistry()
        self.prometheus_metrics = {}

    async def initialize(self, redis_url: Optional[str] = None):
        """Initialize the metrics collector"""
        if redis_url:
            self.redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
            await self.redis_client.ping()

        # Register default metric collectors
        self.register_collector("system", self._collect_system_metrics)
        self.register_collector("application", self._collect_application_metrics)
        self.register_collector("database", self._collect_database_metrics)
        self.register_collector("network", self._collect_network_metrics)

        # Initialize Prometheus metrics
        self._setup_prometheus_metrics()

        logger.info("Real-time metrics collector initialized")

    def register_collector(self, name: str, collector: Callable):
        """Register a metric collector"""
        self.metric_collectors[name] = collector
        logger.info(f"Registered metric collector: {name}")

    async def start_collection(self):
        """Start metrics collection"""
        self.is_running = True

        # Start collection task
        asyncio.create_task(self._collection_loop())

        # Start alert monitoring
        asyncio.create_task(self._alert_monitoring_loop())

        # Start cleanup task
        asyncio.create_task(self._cleanup_loop())

        logger.info("Metrics collection started")

    async def stop_collection(self):
        """Stop metrics collection"""
        self.is_running = False
        logger.info("Metrics collection stopped")

    async def _collection_loop(self):
        """Main metrics collection loop"""
        while self.is_running:
            try:
                snapshot = await self._collect_snapshot()
                await self._process_snapshot(snapshot)
                await asyncio.sleep(self.collection_interval)
            except Exception as e:
                logger.error(f"Error in collection loop: {e}")
                await asyncio.sleep(self.collection_interval)

    async def _collect_snapshot(self) -> PerformanceSnapshot:
        """Collect a complete performance snapshot"""
        timestamp = datetime.now()

        # Collect metrics from all registered collectors
        system_metrics = {}
        application_metrics = {}
        database_metrics = {}
        network_metrics = {}
        custom_metrics = {}

        for collector_name, collector_func in self.metric_collectors.items():
            try:
                if asyncio.iscoroutinefunction(collector_func):
                    metrics = await collector_func()
                else:
                    metrics = collector_func()

                if collector_name == "system":
                    system_metrics = metrics
                elif collector_name == "application":
                    application_metrics = metrics
                elif collector_name == "database":
                    database_metrics = metrics
                elif collector_name == "network":
                    network_metrics = metrics
                else:
                    custom_metrics[collector_name] = metrics

            except Exception as e:
                logger.error(f"Error collecting metrics from {collector_name}: {e}")

        return PerformanceSnapshot(
            timestamp=timestamp,
            system_metrics=system_metrics,
            application_metrics=application_metrics,
            database_metrics=database_metrics,
            network_metrics=network_metrics,
            custom_metrics=custom_metrics,
            alerts=list(self.active_alerts.values()),
        )

    async def _process_snapshot(self, snapshot: PerformanceSnapshot):
        """Process and store performance snapshot"""
        # Convert snapshot to individual metrics
        metrics = self._snapshot_to_metrics(snapshot)

        # Store in buffer
        for metric in metrics:
            self.metrics_buffer.append(metric)

        # Update Prometheus metrics
        self._update_prometheus_metrics(metrics)

        # Store in Redis if available
        if self.redis_client:
            await self._store_in_redis(snapshot)

        # Broadcast to subscribers
        await self._broadcast_to_subscribers(snapshot)

    def _snapshot_to_metrics(
        self, snapshot: PerformanceSnapshot
    ) -> List[RealtimeMetric]:
        """Convert snapshot to individual metrics"""
        metrics = []
        timestamp = snapshot.timestamp

        # System metrics
        for key, value in snapshot.system_metrics.items():
            if isinstance(value, (int, float)):
                metrics.append(
                    RealtimeMetric(
                        timestamp=timestamp,
                        name=f"system.{key}",
                        value=float(value),
                        unit=self._get_metric_unit(key),
                        tags={"source": "system"},
                        source="system",
                    )
                )

        # Application metrics
        for key, value in snapshot.application_metrics.items():
            if isinstance(value, (int, float)):
                metrics.append(
                    RealtimeMetric(
                        timestamp=timestamp,
                        name=f"app.{key}",
                        value=float(value),
                        unit=self._get_metric_unit(key),
                        tags={"source": "application"},
                        source="application",
                    )
                )

        # Database metrics
        for key, value in snapshot.database_metrics.items():
            if isinstance(value, (int, float)):
                metrics.append(
                    RealtimeMetric(
                        timestamp=timestamp,
                        name=f"db.{key}",
                        value=float(value),
                        unit=self._get_metric_unit(key),
                        tags={"source": "database"},
                        source="database",
                    )
                )

        # Network metrics
        for key, value in snapshot.network_metrics.items():
            if isinstance(value, (int, float)):
                metrics.append(
                    RealtimeMetric(
                        timestamp=timestamp,
                        name=f"network.{key}",
                        value=float(value),
                        unit=self._get_metric_unit(key),
                        tags={"source": "network"},
                        source="network",
                    )
                )

        return metrics

    def _get_metric_unit(self, metric_name: str) -> str:
        """Get unit for a metric based on its name"""
        if "percent" in metric_name.lower() or "usage" in metric_name.lower():
            return "percent"
        elif "bytes" in metric_name.lower() or "memory" in metric_name.lower():
            return "bytes"
        elif "time" in metric_name.lower() or "latency" in metric_name.lower():
            return "milliseconds"
        elif "count" in metric_name.lower() or "number" in metric_name.lower():
            return "count"
        elif "rate" in metric_name.lower():
            return "rate"
        else:
            return "value"

    async def _collect_system_metrics(self) -> Dict[str, Any]:
        """Collect system-level metrics"""
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()

        # Memory metrics
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()

        # Disk metrics
        disk = psutil.disk_usage("/")
        disk_io = psutil.disk_io_counters()

        # Process metrics
        process = psutil.Process()
        process_memory = process.memory_info()
        process_cpu = process.cpu_percent()

        return {
            "cpu_percent": cpu_percent,
            "cpu_count": cpu_count,
            "cpu_freq_current": cpu_freq.current if cpu_freq else 0,
            "cpu_freq_min": cpu_freq.min if cpu_freq else 0,
            "cpu_freq_max": cpu_freq.max if cpu_freq else 0,
            "memory_total": memory.total,
            "memory_available": memory.available,
            "memory_percent": memory.percent,
            "memory_used": memory.used,
            "memory_free": memory.free,
            "swap_total": swap.total,
            "swap_used": swap.used,
            "swap_percent": swap.percent,
            "disk_total": disk.total,
            "disk_used": disk.used,
            "disk_free": disk.free,
            "disk_percent": (disk.used / disk.total) * 100,
            "disk_read_bytes": disk_io.read_bytes if disk_io else 0,
            "disk_write_bytes": disk_io.write_bytes if disk_io else 0,
            "disk_read_count": disk_io.read_count if disk_io else 0,
            "disk_write_count": disk_io.write_count if disk_io else 0,
            "process_pid": process.pid,
            "process_memory_rss": process_memory.rss,
            "process_memory_vms": process_memory.vms,
            "process_cpu_percent": process_cpu,
            "process_num_threads": process.num_threads(),
            "process_num_handles": process.num_handles()
            if hasattr(process, "num_handles")
            else 0,
        }

    async def _collect_application_metrics(self) -> Dict[str, Any]:
        """Collect application-level metrics"""
        # This would collect application-specific metrics
        # For now, return placeholder data
        return {
            "active_connections": 0,  # Would be collected from application
            "requests_per_second": 0.0,
            "avg_response_time": 0.0,
            "error_rate": 0.0,
            "cache_hit_ratio": 0.0,
            "active_sessions": 0,
            "queue_size": 0,
            "processing_time": 0.0,
        }

    async def _collect_database_metrics(self) -> Dict[str, Any]:
        """Collect database metrics"""
        # This would collect database-specific metrics
        return {
            "connections_active": 0,
            "connections_idle": 0,
            "queries_per_second": 0.0,
            "avg_query_time": 0.0,
            "slow_queries": 0,
            "cache_hit_ratio": 0.0,
            "buffer_pool_hit_ratio": 0.0,
            "temp_tables_created": 0,
            "lock_waits": 0,
            "deadlocks": 0,
        }

    async def _collect_network_metrics(self) -> Dict[str, Any]:
        """Collect network metrics"""
        network = psutil.net_io_counters()
        connections = len(psutil.net_connections())

        return {
            "bytes_sent": network.bytes_sent if network else 0,
            "bytes_recv": network.bytes_recv if network else 0,
            "packets_sent": network.packets_sent if network else 0,
            "packets_recv": network.packets_recv if network else 0,
            "connections": connections,
            "connection_rate": 0.0,  # Would need to track over time
        }

    async def _store_in_redis(self, snapshot: PerformanceSnapshot):
        """Store snapshot in Redis"""
        try:
            key = f"metrics:snapshot:{snapshot.timestamp.isoformat()}"
            data = json.dumps(asdict(snapshot), default=str)
            await self.redis_client.setex(key, 3600, data)  # Store for 1 hour

            # Store latest snapshot
            await self.redis_client.set("metrics:latest", data, ex=3600)

        except Exception as e:
            logger.error(f"Error storing snapshot in Redis: {e}")

    async def _broadcast_to_subscribers(self, snapshot: PerformanceSnapshot):
        """Broadcast snapshot to WebSocket subscribers"""
        if not self.subscribers:
            return

        message = json.dumps(
            {
                "type": "snapshot",
                "data": asdict(snapshot),
                "timestamp": snapshot.timestamp.isoformat(),
            },
            default=str,
        )

        disconnected_clients = []

        for client_id, websocket in self.subscribers.items():
            try:
                await websocket.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting to client {client_id}: {e}")
                disconnected_clients.append(client_id)

        # Remove disconnected clients
        for client_id in disconnected_clients:
            del self.subscribers[client_id]

    def _setup_prometheus_metrics(self):
        """Setup Prometheus metrics"""
        self.prometheus_metrics = {
            "cpu_usage": Gauge(
                "cpu_usage_percent",
                "CPU usage percentage",
                registry=self.prometheus_registry,
            ),
            "memory_usage": Gauge(
                "memory_usage_percent",
                "Memory usage percentage",
                registry=self.prometheus_registry,
            ),
            "disk_usage": Gauge(
                "disk_usage_percent",
                "Disk usage percentage",
                registry=self.prometheus_registry,
            ),
            "request_duration": Histogram(
                "request_duration_seconds",
                "Request duration",
                registry=self.prometheus_registry,
            ),
            "request_count": Counter(
                "request_count_total",
                "Total number of requests",
                registry=self.prometheus_registry,
            ),
            "error_count": Counter(
                "error_count_total",
                "Total number of errors",
                registry=self.prometheus_registry,
            ),
        }

    def _update_prometheus_metrics(self, metrics: List[RealtimeMetric]):
        """Update Prometheus metrics"""
        for metric in metrics:
            prom_metric = self.prometheus_metrics.get(metric.name.replace(".", "_"))
            if prom_metric:
                if hasattr(prom_metric, "set"):
                    prom_metric.set(metric.value)
                elif hasattr(prom_metric, "observe"):
                    prom_metric.observe(metric.value)

    async def add_subscriber(self, websocket: WebSocket, client_id: str):
        """Add a WebSocket subscriber"""
        await websocket.accept()
        self.subscribers[client_id] = websocket
        logger.info(f"Added subscriber: {client_id}")

    async def remove_subscriber(self, client_id: str):
        """Remove a WebSocket subscriber"""
        if client_id in self.subscribers:
            del self.subscribers[client_id]
            logger.info(f"Removed subscriber: {client_id}")

    def register_alert_rule(self, alert: Alert):
        """Register an alert rule"""
        self.alert_rules[alert.id] = alert
        logger.info(f"Registered alert rule: {alert.name}")

    async def _alert_monitoring_loop(self):
        """Monitor alerts and trigger when conditions are met"""
        while self.is_running:
            try:
                await self._check_alerts()
                await asyncio.sleep(10)  # Check alerts every 10 seconds
            except Exception as e:
                logger.error(f"Error in alert monitoring: {e}")
                await asyncio.sleep(10)

    async def _check_alerts(self):
        """Check all alert rules"""
        current_time = datetime.now()

        for alert_rule in self.alert_rules.values():
            try:
                # Get latest metric for this alert
                latest_metric = self._get_latest_metric(alert_rule.metric_name)
                if not latest_metric:
                    continue

                # Evaluate alert condition
                should_trigger = self._evaluate_alert_condition(
                    latest_metric.value, alert_rule.condition, alert_rule.threshold
                )

                if should_trigger:
                    # Check cooldown
                    if (
                        alert_rule.last_triggered is None
                        or current_time - alert_rule.last_triggered
                        > timedelta(minutes=alert_rule.cooldown_minutes)
                    ):
                        await self._trigger_alert(alert_rule, latest_metric)
                else:
                    # Clear alert if it was active
                    if alert_rule.id in self.active_alerts:
                        await self._clear_alert(alert_rule.id)

            except Exception as e:
                logger.error(f"Error checking alert {alert_rule.id}: {e}")

    def _get_latest_metric(self, metric_name: str) -> Optional[RealtimeMetric]:
        """Get latest metric by name"""
        for metric in reversed(self.metrics_buffer):
            if metric.name == metric_name:
                return metric
        return None

    def _evaluate_alert_condition(
        self, value: float, condition: str, threshold: float
    ) -> bool:
        """Evaluate alert condition"""
        if condition == "gt":
            return value > threshold
        elif condition == "lt":
            return value < threshold
        elif condition == "eq":
            return value == threshold
        elif condition == "gte":
            return value >= threshold
        elif condition == "lte":
            return value <= threshold
        else:
            logger.warning(f"Unknown alert condition: {condition}")
            return False

    async def _trigger_alert(self, alert_rule: Alert, metric: RealtimeMetric):
        """Trigger an alert"""
        # Update alert rule
        alert_rule.last_triggered = datetime.now()
        alert_rule.trigger_count += 1

        # Create active alert
        active_alert = Alert(**asdict(alert_rule), is_active=True)
        self.active_alerts[alert_rule.id] = active_alert

        # Log alert
        logger.warning(
            f"ALERT TRIGGERED: {alert_rule.name} - "
            f"{metric.name} = {metric.value} {metric.unit} "
            f"(threshold: {alert_rule.threshold} {alert_rule.condition})"
        )

        # Send alert to subscribers
        await self._broadcast_alert(active_alert)

        # Store alert in Redis
        if self.redis_client:
            alert_key = f"alerts:active:{alert_rule.id}"
            await self.redis_client.setex(
                alert_key,
                3600,  # Store for 1 hour
                json.dumps(asdict(active_alert), default=str),
            )

    async def _clear_alert(self, alert_id: str):
        """Clear an active alert"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.is_active = False
            del self.active_alerts[alert_id]

            logger.info(f"Alert cleared: {alert.name}")

            # Broadcast alert clearance
            await self._broadcast_alert_cleared(alert)

            # Remove from Redis
            if self.redis_client:
                alert_key = f"alerts:active:{alert_id}"
                await self.redis_client.delete(alert_key)

    async def _broadcast_alert(self, alert: Alert):
        """Broadcast alert to subscribers"""
        if not self.subscribers:
            return

        message = json.dumps(
            {
                "type": "alert",
                "data": asdict(alert),
                "timestamp": datetime.now().isoformat(),
            },
            default=str,
        )

        for client_id, websocket in self.subscribers.items():
            try:
                await websocket.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting alert to client {client_id}: {e}")

    async def _broadcast_alert_cleared(self, alert: Alert):
        """Broadcast alert clearance to subscribers"""
        if not self.subscribers:
            return

        message = json.dumps(
            {
                "type": "alert_cleared",
                "data": asdict(alert),
                "timestamp": datetime.now().isoformat(),
            },
            default=str,
        )

        for client_id, websocket in self.subscribers.items():
            try:
                await websocket.send_text(message)
            except Exception as e:
                logger.error(
                    f"Error broadcasting alert clearance to client {client_id}: {e}"
                )

    async def _cleanup_loop(self):
        """Cleanup old data"""
        while self.is_running:
            try:
                # Clean old metrics (keep last 10000)
                while len(self.metrics_buffer) > 10000:
                    self.metrics_buffer.popleft()

                # Clean old Redis data
                if self.redis_client:
                    # Clean old snapshots
                    pattern = "metrics:snapshot:*"
                    keys = await self.redis_client.keys(pattern)
                    if len(keys) > 1000:
                        # Keep only latest 1000
                        old_keys = sorted(keys)[:-1000]
                        if old_keys:
                            await self.redis_client.delete(*old_keys)

                await asyncio.sleep(300)  # Cleanup every 5 minutes

            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(300)

    def get_recent_metrics(self, minutes: int = 10) -> List[RealtimeMetric]:
        """Get recent metrics"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [m for m in self.metrics_buffer if m.timestamp > cutoff_time]

    def get_active_alerts(self) -> List[Alert]:
        """Get active alerts"""
        return list(self.active_alerts.values())

    def get_metric_history(
        self, metric_name: str, minutes: int = 60
    ) -> List[RealtimeMetric]:
        """Get history for a specific metric"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [
            m
            for m in self.metrics_buffer
            if m.name == metric_name and m.timestamp > cutoff_time
        ]

    async def export_metrics(
        self, filename: str, format: str = "json", minutes: int = 60
    ):
        """Export metrics to file"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        recent_metrics = [m for m in self.metrics_buffer if m.timestamp > cutoff_time]

        if format.lower() == "json":
            data = {
                "export_time": datetime.now().isoformat(),
                "time_range_minutes": minutes,
                "metrics_count": len(recent_metrics),
                "metrics": [asdict(m) for m in recent_metrics],
            }
            with open(filename, "w") as f:
                json.dump(data, f, indent=2, default=str)

        elif format.lower() == "csv":
            if recent_metrics:
                df = pd.DataFrame([asdict(m) for m in recent_metrics])
                df.to_csv(filename, index=False)

        logger.info(f"Metrics exported to {filename}")


# WebSocket manager for real-time updates
class WebSocketManager:
    """Manages WebSocket connections for real-time updates"""

    def __init__(self, metrics_collector: RealtimeMetricsCollector):
        self.metrics_collector = metrics_collector
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        """Connect a WebSocket client"""
        await self.metrics_collector.add_subscriber(websocket, client_id)
        self.active_connections[client_id] = websocket

        # Send current state
        await self._send_current_state(websocket)

    async def disconnect(self, client_id: str):
        """Disconnect a WebSocket client"""
        await self.metrics_collector.remove_subscriber(client_id)
        if client_id in self.active_connections:
            del self.active_connections[client_id]

    async def _send_current_state(self, websocket: WebSocket):
        """Send current system state to a new connection"""
        recent_metrics = self.metrics_collector.get_recent_metrics(minutes=1)
        active_alerts = self.metrics_collector.get_active_alerts()

        message = json.dumps(
            {
                "type": "initial_state",
                "data": {
                    "recent_metrics": [asdict(m) for m in recent_metrics],
                    "active_alerts": [asdict(a) for a in active_alerts],
                    "subscriber_count": len(self.metrics_collector.subscribers),
                },
                "timestamp": datetime.now().isoformat(),
            },
            default=str,
        )

        await websocket.send_text(message)

    async def send_personal_message(self, message: str, client_id: str):
        """Send a message to a specific client"""
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_text(message)

    async def broadcast(self, message: str):
        """Broadcast a message to all connected clients"""
        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting to client {client_id}: {e}")


# Alert management system
class AlertManager:
    """Manages alert rules and notifications"""

    def __init__(self, metrics_collector: RealtimeMetricsCollector):
        self.metrics_collector = metrics_collector
        self.notification_channels: Dict[str, Callable] = {}

    def add_notification_channel(self, name: str, channel: Callable):
        """Add a notification channel"""
        self.notification_channels[name] = channel

    async def send_notification(self, alert: Alert, channel_name: str = "default"):
        """Send alert notification"""
        if channel_name in self.notification_channels:
            try:
                await self.notification_channels[channel_name](alert)
            except Exception as e:
                logger.error(f"Error sending notification via {channel_name}: {e}")


# Predefined alert rules
def create_default_alert_rules() -> List[Alert]:
    """Create default alert rules"""
    return [
        Alert(
            id="high_cpu_usage",
            name="High CPU Usage",
            description="CPU usage is above 80%",
            condition="gt",
            threshold=80.0,
            severity="warning",
            metric_name="system.cpu_percent",
            is_active=False,
            created_at=datetime.now(),
            cooldown_minutes=5,
        ),
        Alert(
            id="high_memory_usage",
            name="High Memory Usage",
            description="Memory usage is above 85%",
            condition="gt",
            threshold=85.0,
            severity="warning",
            metric_name="system.memory_percent",
            is_active=False,
            created_at=datetime.now(),
            cooldown_minutes=5,
        ),
        Alert(
            id="high_disk_usage",
            name="High Disk Usage",
            description="Disk usage is above 90%",
            condition="gt",
            threshold=90.0,
            severity="critical",
            metric_name="system.disk_percent",
            is_active=False,
            created_at=datetime.now(),
            cooldown_minutes=10,
        ),
        Alert(
            id="high_error_rate",
            name="High Error Rate",
            description="Error rate is above 5%",
            condition="gt",
            threshold=5.0,
            severity="warning",
            metric_name="app.error_rate",
            is_active=False,
            created_at=datetime.now(),
            cooldown_minutes=5,
        ),
        Alert(
            id="slow_response_time",
            name="Slow Response Time",
            description="Average response time is above 2 seconds",
            condition="gt",
            threshold=2000.0,
            severity="warning",
            metric_name="app.avg_response_time",
            is_active=False,
            created_at=datetime.now(),
            cooldown_minutes=5,
        ),
    ]


# Initialize global instances
metrics_collector = RealtimeMetricsCollector()
websocket_manager = WebSocketManager(metrics_collector)
alert_manager = AlertManager(metrics_collector)


# Startup and shutdown functions
async def initialize_monitoring(redis_url: Optional[str] = None):
    """Initialize monitoring system"""
    await metrics_collector.initialize(redis_url)
    await metrics_collector.start_collection()

    # Register default alert rules
    for alert in create_default_alert_rules():
        metrics_collector.register_alert_rule(alert)

    # Start Prometheus metrics server
    start_http_server(8001)

    logger.info("Real-time monitoring system initialized")


async def shutdown_monitoring():
    """Shutdown monitoring system"""
    await metrics_collector.stop_collection()
    logger.info("Real-time monitoring system shutdown")
