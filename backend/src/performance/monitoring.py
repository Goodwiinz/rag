"""
Comprehensive performance monitoring and alerting system
Real-time metrics collection, SLA tracking, and automated alerts
"""

import asyncio
import time
import json
import psutil
import logging
from datetime import datetime, timezone as dt_timezone, timedelta
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict, deque
import numpy as np
import aioredis
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class MetricType(Enum):
    """Types of performance metrics"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"

class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class SLOStatus(Enum):
    """Service Level Objective status"""
    HEALTHY = "healthy"
    WARNING = "warning"
    VIOLATED = "violated"
    UNKNOWN = "unknown"

@dataclass
class MetricDefinition:
    """Definition of a performance metric"""
    name: str
    description: str
    metric_type: MetricType
    unit: str
    tags: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True

@dataclass
class MetricValue:
    """Single metric value with timestamp"""
    metric_name: str
    value: Union[float, int]
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)

@dataclass
class SLODefinition:
    """Service Level Objective definition"""
    name: str
    description: str
    metric_name: str
    target_value: float
    comparison: str  # 'lt', 'gt', 'lte', 'gte'
    time_window_minutes: int
    alert_severity: AlertSeverity
    tags: Dict[str, str] = field(default_factory=dict)

@dataclass
class Alert:
    """Performance alert"""
    id: str
    slo_name: str
    severity: AlertSeverity
    message: str
    metric_value: float
    target_value: float
    triggered_at: datetime
    resolved_at: Optional[datetime] = None
    tags: Dict[str, str] = field(default_factory=dict)

@dataclass
class PerformanceSnapshot:
    """Snapshot of system performance at a point in time"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_usage_mb: float
    disk_usage_percent: float
    network_io: Dict[str, int]
    process_count: int
    active_connections: int
    custom_metrics: Dict[str, MetricValue] = field(default_factory=dict)

class MetricsCollector:
    """Collects and stores performance metrics"""

    def __init__(self, redis_client: aioredis.Redis = None):
        self.redis_client = redis_client
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.metric_definitions: Dict[str, MetricDefinition] = {}
        self.counters: Dict[str, float] = defaultdict(float)
        self.gauges: Dict[str, float] = defaultdict(float)
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        self.timers: Dict[str, List[float]] = defaultdict(list)
        self.executor = ThreadPoolExecutor(max_workers=2)

        # Predefined metrics
        self._initialize_builtin_metrics()

    def _initialize_builtin_metrics(self):
        """Initialize built-in metric definitions"""
        builtin_metrics = [
            MetricDefinition("cpu_usage", "CPU usage percentage", MetricType.GAUGE, "percent"),
            MetricDefinition("memory_usage", "Memory usage percentage", MetricType.GAUGE, "percent"),
            MetricDefinition("memory_usage_mb", "Memory usage in MB", MetricType.GAUGE, "megabytes"),
            MetricDefinition("disk_usage", "Disk usage percentage", MetricType.GAUGE, "percent"),
            MetricDefinition("network_bytes_sent", "Network bytes sent", MetricType.COUNTER, "bytes"),
            MetricDefinition("network_bytes_recv", "Network bytes received", MetricType.COUNTER, "bytes"),
            MetricDefinition("active_connections", "Active network connections", MetricType.GAUGE, "count"),
            MetricDefinition("response_time_ms", "API response time", MetricType.HISTOGRAM, "milliseconds"),
            MetricDefinition("query_time_ms", "Database query time", MetricType.HISTOGRAM, "milliseconds"),
            MetricDefinition("cache_hit_rate", "Cache hit rate", MetricType.GAUGE, "percent"),
            MetricDefinition("error_rate", "Error rate", MetricType.GAUGE, "percent"),
            MetricDefinition("request_rate", "Request rate per second", MetricType.GAUGE, "rps"),
            MetricDefinition("websocket_connections", "WebSocket connections", MetricType.GAUGE, "count"),
            MetricDefinition("message_rate", "WebSocket messages per second", MetricType.GAUGE, "mps"),
        ]

        for metric_def in builtin_metrics:
            self.metric_definitions[metric_def.name] = metric_def

    def define_metric(self, metric_def: MetricDefinition):
        """Define a new custom metric"""
        self.metric_definitions[metric_def.name] = metric_def

    def increment_counter(self, metric_name: str, value: float = 1.0, tags: Dict[str, str] = None):
        """Increment a counter metric"""
        if metric_name not in self.metric_definitions:
            self.define_metric(MetricDefinition(metric_name, "", MetricType.COUNTER, "count"))

        self.counters[metric_name] += value
        self._record_metric(metric_name, self.counters[metric_name], tags)

    def set_gauge(self, metric_name: str, value: float, tags: Dict[str, str] = None):
        """Set a gauge metric value"""
        if metric_name not in self.metric_definitions:
            self.define_metric(MetricDefinition(metric_name, "", MetricType.GAUGE, "value"))

        self.gauges[metric_name] = value
        self._record_metric(metric_name, value, tags)

    def record_histogram(self, metric_name: str, value: float, tags: Dict[str, str] = None):
        """Record a histogram metric value"""
        if metric_name not in self.metric_definitions:
            self.define_metric(MetricDefinition(metric_name, "", MetricType.HISTOGRAM, "value"))

        self.histograms[metric_name].append(value)
        # Keep only last 1000 values
        if len(self.histograms[metric_name]) > 1000:
            self.histograms[metric_name] = self.histograms[metric_name][-1000:]

        self._record_metric(metric_name, value, tags)

    def record_timer(self, metric_name: str, duration_ms: float, tags: Dict[str, str] = None):
        """Record a timer metric"""
        if metric_name not in self.metric_definitions:
            self.define_metric(MetricDefinition(metric_name, "", MetricType.TIMER, "milliseconds"))

        self.timers[metric_name].append(duration_ms)
        # Keep only last 1000 values
        if len(self.timers[metric_name]) > 1000:
            self.timers[metric_name] = self.timers[metric_name][-1000:]

        self._record_metric(metric_name, duration_ms, tags)

    def _record_metric(self, metric_name: str, value: float, tags: Dict[str, str] = None):
        """Record a metric value with timestamp"""
        metric_value = MetricValue(
            metric_name=metric_name,
            value=value,
            timestamp=datetime.utcnow(),
            tags=tags or {}
        )

        self.metrics[metric_name].append(metric_value)

        # Store in Redis if available
        if self.redis_client:
            asyncio.create_task(self._store_metric_redis(metric_value))

    async def _store_metric_redis(self, metric_value: MetricValue):
        """Store metric in Redis for persistence"""
        try:
            key = f"metrics:{metric_value.metric_name}:{int(metric_value.timestamp.timestamp())}"
            await self.redis_client.setex(
                key,
                3600,  # 1 hour TTL
                json.dumps({
                    'value': metric_value.value,
                    'timestamp': metric_value.timestamp.isoformat(),
                    'tags': metric_value.tags
                })
            )
        except Exception as e:
            logger.error(f"Failed to store metric in Redis: {e}")

    def get_metric_stats(self, metric_name: str, time_window_minutes: int = 5) -> Dict[str, Any]:
        """Get statistics for a metric over a time window"""
        cutoff_time = datetime.utcnow() - timedelta(minutes=time_window_minutes)

        if metric_name in self.metrics:
            recent_values = [
                mv.value for mv in self.metrics[metric_name]
                if mv.timestamp >= cutoff_time
            ]
        else:
            recent_values = []

        if not recent_values:
            return {
                'count': 0,
                'min': 0,
                'max': 0,
                'avg': 0,
                'sum': 0,
                'percentiles': {}
            }

        values_array = np.array(recent_values)
        percentiles = {
            'p50': float(np.percentile(values_array, 50)),
            'p90': float(np.percentile(values_array, 90)),
            'p95': float(np.percentile(values_array, 95)),
            'p99': float(np.percentile(values_array, 99)),
        }

        return {
            'count': len(recent_values),
            'min': float(np.min(values_array)),
            'max': float(np.max(values_array)),
            'avg': float(np.mean(values_array)),
            'sum': float(np.sum(values_array)),
            'std': float(np.std(values_array)),
            'percentiles': percentiles
        }

class SystemMonitor:
    """Monitors system-level performance metrics"""

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self.monitoring_task: Optional[asyncio.Task] = None
        self.collection_interval = 10  # seconds
        self.initial_network_io = None

    async def start(self):
        """Start system monitoring"""
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.initial_network_io = psutil.net_io_counters()
        logger.info("System monitoring started")

    async def stop(self):
        """Stop system monitoring"""
        if self.monitoring_task:
            self.monitoring_task.cancel()
        logger.info("System monitoring stopped")

    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while True:
            try:
                await self._collect_system_metrics()
                await asyncio.sleep(self.collection_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in system monitoring loop: {e}")
                await asyncio.sleep(5)

    async def _collect_system_metrics(self):
        """Collect system performance metrics"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            self.metrics_collector.set_gauge("cpu_usage", cpu_percent)

            # Memory metrics
            memory = psutil.virtual_memory()
            self.metrics_collector.set_gauge("memory_usage", memory.percent)
            self.metrics_collector.set_gauge("memory_usage_mb", memory.used / (1024 * 1024))

            # Disk metrics
            disk = psutil.disk_usage('/')
            self.metrics_collector.set_gauge("disk_usage", disk.percent)

            # Network metrics
            if self.initial_network_io:
                current_io = psutil.net_io_counters()
                bytes_sent = current_io.bytes_sent - self.initial_network_io.bytes_sent
                bytes_recv = current_io.bytes_recv - self.initial_network_io.bytes_recv
                self.metrics_collector.set_gauge("network_bytes_sent", bytes_sent)
                self.metrics_collector.set_gauge("network_bytes_recv", bytes_recv)

            # Process metrics
            process_count = len(psutil.pids())
            self.metrics_collector.set_gauge("process_count", process_count)

            # Network connections
            try:
                connections = len(psutil.net_connections())
                self.metrics_collector.set_gauge("active_connections", connections)
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass

        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")

    def get_system_snapshot(self) -> PerformanceSnapshot:
        """Get current system performance snapshot"""
        try:
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network_io = psutil.net_io_counters()
            process_count = len(psutil.pids())

            return PerformanceSnapshot(
                timestamp=datetime.utcnow(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_usage_mb=memory.used / (1024 * 1024),
                disk_usage_percent=disk.percent,
                network_io={
                    'bytes_sent': network_io.bytes_sent,
                    'bytes_recv': network_io.bytes_recv,
                    'packets_sent': network_io.packets_sent,
                    'packets_recv': network_io.packets_recv,
                },
                process_count=process_count,
                active_connections=len(psutil.net_connections())
            )
        except Exception as e:
            logger.error(f"Error getting system snapshot: {e}")
            return PerformanceSnapshot(
                timestamp=datetime.utcnow(),
                cpu_percent=0,
                memory_percent=0,
                memory_usage_mb=0,
                disk_usage_percent=0,
                network_io={},
                process_count=0,
                active_connections=0
            )

class SLOMonitor:
    """Monitors Service Level Objectives and generates alerts"""

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self.slos: Dict[str, SLODefinition] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.monitoring_task: Optional[asyncio.Task] = None
        self.check_interval = 30  # seconds
        self.alert_callbacks: List[Callable[[Alert], None]] = []

        # Initialize default SLOs
        self._initialize_default_slos()

    def _initialize_default_slos(self):
        """Initialize default Service Level Objectives"""
        default_slos = [
            SLODefinition(
                name="cpu_usage_slo",
                description="CPU usage should be below 80%",
                metric_name="cpu_usage",
                target_value=80.0,
                comparison="lt",
                time_window_minutes=5,
                alert_severity=AlertSeverity.WARNING
            ),
            SLODefinition(
                name="memory_usage_slo",
                description="Memory usage should be below 85%",
                metric_name="memory_usage",
                target_value=85.0,
                comparison="lt",
                time_window_minutes=5,
                alert_severity=AlertSeverity.WARNING
            ),
            SLODefinition(
                name="response_time_slo",
                description="95th percentile response time should be below 500ms",
                metric_name="response_time_ms",
                target_value=500.0,
                comparison="lt",
                time_window_minutes=5,
                alert_severity=AlertSeverity.ERROR
            ),
            SLODefinition(
                name="error_rate_slo",
                description="Error rate should be below 1%",
                metric_name="error_rate",
                target_value=1.0,
                comparison="lt",
                time_window_minutes=5,
                alert_severity=AlertSeverity.ERROR
            ),
            SLODefinition(
                name="cache_hit_rate_slo",
                description="Cache hit rate should be above 80%",
                metric_name="cache_hit_rate",
                target_value=80.0,
                comparison="gt",
                time_window_minutes=10,
                alert_severity=AlertSeverity.WARNING
            ),
        ]

        for slo in default_slos:
            self.slos[slo.name] = slo

    def add_slo(self, slo: SLODefinition):
        """Add a new Service Level Objective"""
        self.slos[slo.name] = slo

    def add_alert_callback(self, callback: Callable[[Alert], None]):
        """Add callback function for alerts"""
        self.alert_callbacks.append(callback)

    async def start(self):
        """Start SLO monitoring"""
        self.monitoring_task = asyncio.create_task(self._slo_monitoring_loop())
        logger.info("SLO monitoring started")

    async def stop(self):
        """Stop SLO monitoring"""
        if self.monitoring_task:
            self.monitoring_task.cancel()
        logger.info("SLO monitoring stopped")

    async def _slo_monitoring_loop(self):
        """Main SLO monitoring loop"""
        while True:
            try:
                await self._check_all_slos()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in SLO monitoring loop: {e}")
                await asyncio.sleep(5)

    async def _check_all_slos(self):
        """Check all Service Level Objectives"""
        for slo_name, slo in self.slos.items():
            try:
                await self._check_slo(slo)
            except Exception as e:
                logger.error(f"Error checking SLO {slo_name}: {e}")

    async def _check_slo(self, slo: SLODefinition):
        """Check a single Service Level Objective"""
        # Get metric statistics for the time window
        stats = self.metrics_collector.get_metric_stats(slo.metric_name, slo.time_window_minutes)

        if stats['count'] == 0:
            return  # No data to evaluate

        # Use average for evaluation (could be configurable)
        metric_value = stats['avg']

        # Check SLO condition
        slo_met = self._evaluate_condition(metric_value, slo.target_value, slo.comparison)

        # Get existing alert for this SLO
        existing_alert = self.active_alerts.get(slo_name)

        if not slo_met and existing_alert is None:
            # SLO violation - create new alert
            alert = Alert(
                id=f"{slo_name}_{int(time.time())}",
                slo_name=slo_name,
                severity=slo.alert_severity,
                message=f"SLO Violation: {slo.description}. Current: {metric_value:.2f}, Target: {slo.target_value:.2f}",
                metric_value=metric_value,
                target_value=slo.target_value,
                triggered_at=datetime.utcnow(),
                tags=slo.tags
            )

            self.active_alerts[slo_name] = alert
            self.alert_history.append(alert)
            await self._trigger_alert(alert)

        elif slo_met and existing_alert is not None:
            # SLO recovered - resolve alert
            existing_alert.resolved_at = datetime.utcnow()
            del self.active_alerts[slo_name]
            await self._resolve_alert(existing_alert)

    def _evaluate_condition(self, actual: float, target: float, comparison: str) -> bool:
        """Evaluate SLO condition"""
        if comparison == "lt":
            return actual < target
        elif comparison == "lte":
            return actual <= target
        elif comparison == "gt":
            return actual > target
        elif comparison == "gte":
            return actual >= target
        else:
            return False

    async def _trigger_alert(self, alert: Alert):
        """Trigger an alert"""
        logger.warning(f"Alert triggered: {alert.message}")

        # Call alert callbacks
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")

        # Store alert in Redis if available
        if self.metrics_collector.redis_client:
            try:
                await self.metrics_collector.redis_client.setex(
                    f"alert:{alert.id}",
                    86400,  # 24 hours
                    json.dumps(asdict(alert), default=str)
                )
            except Exception as e:
                logger.error(f"Failed to store alert in Redis: {e}")

    async def _resolve_alert(self, alert: Alert):
        """Resolve an alert"""
        logger.info(f"Alert resolved: {alert.message}")

        # Call alert callbacks
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")

        # Update alert in Redis if available
        if self.metrics_collector.redis_client:
            try:
                await self.metrics_collector.redis_client.setex(
                    f"alert:{alert.id}",
                    86400,  # 24 hours
                    json.dumps(asdict(alert), default=str)
                )
            except Exception as e:
                logger.error(f"Failed to update alert in Redis: {e}")

    def get_slo_status(self) -> Dict[str, Dict[str, Any]]:
        """Get current status of all SLOs"""
        status = {}

        for slo_name, slo in self.slos.items():
            stats = self.metrics_collector.get_metric_stats(slo.metric_name, slo.time_window_minutes)
            metric_value = stats['avg'] if stats['count'] > 0 else 0
            slo_met = self._evaluate_condition(metric_value, slo.target_value, slo.comparison)

            if stats['count'] == 0:
                slo_status = SLOStatus.UNKNOWN
            elif slo_met:
                slo_status = SLOStatus.HEALTHY
            else:
                slo_status = SLOStatus.VIOLATED

            status[slo_name] = {
                'description': slo.description,
                'current_value': metric_value,
                'target_value': slo.target_value,
                'comparison': slo.comparison,
                'status': slo_status.value,
                'alert_severity': slo.alert_severity.value if not slo_met else None,
                'active_alert': self.active_alerts.get(slo_name) is not None,
                'data_points': stats['count']
            }

        return status

class PerformanceMonitor:
    """Main performance monitoring coordinator"""

    def __init__(self, redis_client: aioredis.Redis = None):
        self.redis_client = redis_client
        self.metrics_collector = MetricsCollector(redis_client)
        self.system_monitor = SystemMonitor(self.metrics_collector)
        self.slo_monitor = SLOMonitor(self.metrics_collector)

        # Performance dashboard data
        self.dashboard_data = {
            'last_updated': None,
            'system_metrics': {},
            'slo_status': {},
            'active_alerts': [],
            'performance_trends': {}
        }

    async def start(self):
        """Start all monitoring components"""
        await self.system_monitor.start()
        await self.slo_monitor.start()
        logger.info("Performance monitoring started")

    async def stop(self):
        """Stop all monitoring components"""
        await self.system_monitor.stop()
        await self.slo_monitor.stop()
        logger.info("Performance monitoring stopped")

    def record_request(self, endpoint: str, duration_ms: float, status_code: int):
        """Record an API request for performance tracking"""
        # Record response time
        self.metrics_collector.record_timer("response_time_ms", duration_ms, {"endpoint": endpoint})

        # Record error if applicable
        if status_code >= 400:
            self.metrics_collector.increment_counter("error_count", 1.0, {"endpoint": endpoint})

        # Record request
        self.metrics_collector.increment_counter("request_count", 1.0, {"endpoint": endpoint})

    def record_database_query(self, query_type: str, duration_ms: float, success: bool):
        """Record a database query"""
        self.metrics_collector.record_timer("query_time_ms", duration_ms, {"query_type": query_type})

        if not success:
            self.metrics_collector.increment_counter("database_errors", 1.0, {"query_type": query_type})

    def record_cache_operation(self, operation: str, hit: bool):
        """Record a cache operation"""
        self.metrics_collector.increment_counter("cache_operations", 1.0, {"operation": operation, "hit": str(hit)})

        # Update cache hit rate
        total_ops = sum(self.metrics_collector.counters.get(k, 0) for k in self.metrics_collector.counters.keys() if k.startswith("cache_operations"))
        if total_ops > 0:
            hits = sum(v for k, v in self.metrics_collector.counters.items() if k.startswith("cache_operations") and "hit=true" in k)
            hit_rate = (hits / total_ops) * 100
            self.metrics_collector.set_gauge("cache_hit_rate", hit_rate)

    def record_websocket_connection(self, action: str):
        """Record WebSocket connection event"""
        self.metrics_collector.increment_counter("websocket_events", 1.0, {"action": action})

        # Update connection count
        if action == "connect":
            current = self.metrics_collector.gauges.get("websocket_connections", 0)
            self.metrics_collector.set_gauge("websocket_connections", current + 1)
        elif action == "disconnect":
            current = max(0, self.metrics_collector.gauges.get("websocket_connections", 0) - 1)
            self.metrics_collector.set_gauge("websocket_connections", current)

    def update_dashboard_data(self):
        """Update performance dashboard data"""
        self.dashboard_data['last_updated'] = datetime.utcnow()
        self.dashboard_data['system_metrics'] = self.system_monitor.get_system_snapshot().__dict__
        self.dashboard_data['slo_status'] = self.slo_monitor.get_slo_status()
        self.dashboard_data['active_alerts'] = list(self.slo_monitor.active_alerts.values())

        # Calculate performance trends
        self.dashboard_data['performance_trends'] = {
            'cpu_trend': self.metrics_collector.get_metric_stats("cpu_usage", 60),
            'memory_trend': self.metrics_collector.get_metric_stats("memory_usage", 60),
            'response_time_trend': self.metrics_collector.get_metric_stats("response_time_ms", 60),
            'error_rate_trend': self.metrics_collector.get_metric_stats("error_rate", 60),
        }

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get current dashboard data"""
        self.update_dashboard_data()
        return self.dashboard_data

    def get_comprehensive_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'system_snapshot': self.system_monitor.get_system_snapshot().__dict__,
            'metrics_summary': {
                name: self.metrics_collector.get_metric_stats(name)
                for name in self.metrics_collector.metrics.keys()
            },
            'slo_status': self.slo_monitor.get_slo_status(),
            'active_alerts': [asdict(alert) for alert in self.slo_monitor.active_alerts.values()],
            'alert_history': [asdict(alert) for alert in self.slo_monitor.alert_history[-100:]],  # Last 100 alerts
            'performance_trends': self.dashboard_data.get('performance_trends', {}),
        }

# Global performance monitor instance
_performance_monitor = None

def get_performance_monitor(redis_client: aioredis.Redis = None) -> PerformanceMonitor:
    """Get or create the global performance monitor"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor(redis_client)
    return _performance_monitor