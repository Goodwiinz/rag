"""
Metrics Collector Service

Comprehensive metrics collection service for system, application,
and business metrics with Prometheus integration.
"""

import asyncio
import logging
import time
import psutil
import platform
import json
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import uuid

from prometheus_client import Counter, Histogram, Gauge, Summary, CollectorRegistry, generate_latest
from prometheus_client.core import REGISTRY

from ..config.monitoring_config import MetricsConfig
from ..models.metrics import MetricDefinition, Metric, MetricAggregation, TimeSeriesData
from ..utils.exceptions import MetricsError

logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """Single metric data point"""
    name: str
    value: float
    labels: Dict[str, str]
    timestamp: datetime
    unit: str
    metric_type: str


class MetricsCollector:
    """
    Comprehensive metrics collection service

    Collects system, application, and business metrics with
    Prometheus integration and custom metric support.
    """

    def __init__(self, config: MetricsConfig):
        """Initialize metrics collector"""
        self.config = config
        self._initialized = False
        self._running = False

        # Prometheus registry and metrics
        self._registry = CollectorRegistry()
        self._prometheus_metrics: Dict[str, Any] = {}

        # Metric storage
        self._metric_definitions: Dict[str, MetricDefinition] = {}
        self._metric_buffer: List[MetricPoint] = []
        self._buffer_lock = asyncio.Lock()

        # Background task
        self._collection_task: Optional[asyncio.Task] = None

        # System info
        self._system_info = self._get_system_info()

    async def initialize(self) -> None:
        """Initialize the metrics collector"""
        if self._initialized:
            return

        try:
            logger.info("Initializing metrics collector...")

            # Initialize Prometheus metrics
            if self.config.prometheus_enabled:
                await self._initialize_prometheus_metrics()

            # Create default metric definitions
            await self._create_default_metric_definitions()

            # Initialize metric collectors
            await self._initialize_collectors()

            self._initialized = True
            logger.info("✅ Metrics collector initialized")

        except Exception as e:
            logger.error(f"❌ Failed to initialize metrics collector: {e}")
            raise MetricsError(f"Initialization failed: {e}")

    async def start(self) -> None:
        """Start metrics collection"""
        if not self._initialized:
            await self.initialize()

        if self._running:
            return

        try:
            logger.info("Starting metrics collector...")

            # Start background collection task
            if self.config.custom_metrics_enabled:
                self._collection_task = asyncio.create_task(self._collection_loop())

            self._running = True
            logger.info("✅ Metrics collector started")

        except Exception as e:
            logger.error(f"❌ Failed to start metrics collector: {e}")
            raise MetricsError(f"Start failed: {e}")

    async def stop(self) -> None:
        """Stop metrics collection"""
        if not self._running:
            return

        try:
            logger.info("Stopping metrics collector...")

            # Cancel background task
            if self._collection_task:
                self._collection_task.cancel()
                try:
                    await self._collection_task
                except asyncio.CancelledError:
                    pass

            # Flush any remaining metrics
            await self._flush_metrics()

            self._running = False
            logger.info("✅ Metrics collector stopped")

        except Exception as e:
            logger.error(f"❌ Error stopping metrics collector: {e}")

    async def cleanup(self) -> None:
        """Cleanup metrics collector resources"""
        await self.stop()
        self._metric_definitions.clear()
        self._prometheus_metrics.clear()
        self._metric_buffer.clear()
        logger.info("✅ Metrics collector cleanup complete")

    async def record_metric(self,
                           name: str,
                           value: float,
                           labels: Optional[Dict[str, str]] = None,
                           timestamp: Optional[datetime] = None,
                           source: Optional[str] = None) -> None:
        """
        Record a metric

        Args:
            name: Metric name
            value: Metric value
            labels: Optional metric labels
            timestamp: Optional timestamp (defaults to now)
            source: Optional source identifier
        """
        if not self._running:
            return

        try:
            # Get metric definition
            definition = self._metric_definitions.get(name)
            if not definition:
                logger.warning(f"Unknown metric: {name}")
                return

            # Create metric point
            metric_point = MetricPoint(
                name=name,
                value=value,
                labels=labels or {},
                timestamp=timestamp or datetime.utcnow(),
                unit=definition.unit,
                metric_type=definition.metric_type
            )

            # Add to buffer
            async with self._buffer_lock:
                self._metric_buffer.append(metric_point)

            # Update Prometheus metric
            if self.config.prometheus_enabled:
                await self._update_prometheus_metric(metric_point)

        except Exception as e:
            logger.error(f"Error recording metric {name}: {e}")

    async def increment_counter(self,
                              name: str,
                              value: float = 1.0,
                              labels: Optional[Dict[str, str]] = None) -> None:
        """Increment a counter metric"""
        await self.record_metric(name, value, labels)

    async def set_gauge(self,
                       name: str,
                       value: float,
                       labels: Optional[Dict[str, str]] = None) -> None:
        """Set a gauge metric value"""
        await self.record_metric(name, value, labels)

    async def observe_histogram(self,
                               name: str,
                               value: float,
                               labels: Optional[Dict[str, str]] = None) -> None:
        """Observe a histogram metric value"""
        await self.record_metric(name, value, labels)

    async def create_metric_definition(self,
                                     name: str,
                                     metric_type: str,
                                     unit: str,
                                     description: Optional[str] = None,
                                     labels_schema: Optional[Dict[str, Any]] = None,
                                     aggregation_rules: Optional[Dict[str, Any]] = None,
                                     category: Optional[str] = None) -> None:
        """
        Create a new metric definition

        Args:
            name: Metric name
            metric_type: Type of metric (counter, gauge, histogram, summary)
            unit: Metric unit
            description: Optional description
            labels_schema: Optional labels schema
            aggregation_rules: Optional aggregation rules
            category: Optional metric category
        """
        try:
            definition = MetricDefinition(
                name=name,
                description=description or f"Metric: {name}",
                metric_type=metric_type,
                unit=unit,
                labels_schema=labels_schema or {},
                aggregation_rules=aggregation_rules or {},
                category=category or "custom"
            )

            self._metric_definitions[name] = definition

            # Create Prometheus metric if enabled
            if self.config.prometheus_enabled:
                await self._create_prometheus_metric(definition)

            logger.info(f"✅ Created metric definition: {name}")

        except Exception as e:
            logger.error(f"❌ Failed to create metric definition {name}: {e}")
            raise MetricsError(f"Failed to create metric definition: {e}")

    async def get_metrics(self,
                         service: Optional[str] = None,
                         metric_name: Optional[str] = None,
                         start_time: Optional[datetime] = None,
                         end_time: Optional[datetime] = None,
                         labels: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Get metrics data

        Args:
            service: Optional service filter
            metric_name: Optional metric name filter
            start_time: Optional start time filter
            end_time: Optional end time filter
            labels: Optional label filters

        Returns:
            Dictionary containing metrics data
        """
        try:
            # Default time range to last hour if not specified
            if not end_time:
                end_time = datetime.utcnow()
            if not start_time:
                start_time = end_time - timedelta(hours=1)

            # Filter metrics from buffer
            async with self._buffer_lock:
                filtered_metrics = [
                    metric for metric in self._metric_buffer
                    if start_time <= metric.timestamp <= end_time
                ]

            # Apply filters
            if service:
                filtered_metrics = [
                    m for m in filtered_metrics
                    if m.labels.get('service') == service
                ]

            if metric_name:
                filtered_metrics = [
                    m for m in filtered_metrics
                    if m.name == metric_name
                ]

            if labels:
                filtered_metrics = [
                    m for m in filtered_metrics
                    if all(m.labels.get(k) == v for k, v in labels.items())
                ]

            # Group by metric name
            metrics_by_name = {}
            for metric in filtered_metrics:
                if metric.name not in metrics_by_name:
                    metrics_by_name[metric.name] = []
                metrics_by_name[metric.name].append(asdict(metric))

            return {
                "metrics": metrics_by_name,
                "count": len(filtered_metrics),
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "filters": {
                    "service": service,
                    "metric_name": metric_name,
                    "labels": labels
                }
            }

        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            raise MetricsError(f"Failed to get metrics: {e}")

    async def get_prometheus_metrics(self) -> str:
        """Get Prometheus metrics in text format"""
        if not self.config.prometheus_enabled:
            return ""

        try:
            return generate_latest(self._registry).decode('utf-8')
        except Exception as e:
            logger.error(f"Error generating Prometheus metrics: {e}")
            return ""

    async def collect_system_metrics(self) -> None:
        """Collect system-level metrics"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            await self.set_gauge("system_cpu_usage_percent", cpu_percent, {
                "host": platform.node(),
                "cores": str(psutil.cpu_count())
            })

            # Memory metrics
            memory = psutil.virtual_memory()
            await self.set_gauge("system_memory_usage_percent", memory.percent, {
                "host": platform.node()
            })
            await self.set_gauge("system_memory_available_bytes", memory.available, {
                "host": platform.node()
            })

            # Disk metrics
            disk = psutil.disk_usage('/')
            await self.set_gauge("system_disk_usage_percent", disk.percent, {
                "host": platform.node(),
                "mount": "/"
            })
            await self.set_gauge("system_disk_free_bytes", disk.free, {
                "host": platform.node(),
                "mount": "/"
            })

            # Network metrics
            network = psutil.net_io_counters()
            await self.increment_counter("system_network_bytes_sent", network.bytes_sent, {
                "host": platform.node(),
                "direction": "sent"
            })
            await self.increment_counter("system_network_bytes_recv", network.bytes_recv, {
                "host": platform.node(),
                "direction": "received"
            })

            # Process metrics
            process = psutil.Process()
            await self.set_gauge("process_memory_rss_bytes", process.memory_info().rss, {
                "host": platform.node(),
                "pid": str(process.pid)
            })
            await self.set_gauge("process_cpu_percent", process.cpu_percent(), {
                "host": platform.node(),
                "pid": str(process.pid)
            })

        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")

    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the metrics collector"""
        return {
            "initialized": self._initialized,
            "running": self._running,
            "prometheus_enabled": self.config.prometheus_enabled,
            "custom_metrics_enabled": self.config.custom_metrics_enabled,
            "metric_definitions_count": len(self._metric_definitions),
            "buffer_size": len(self._metric_buffer),
            "collection_interval": self.config.collection_interval_seconds,
            "status": "healthy" if self._running else "stopped",
            "system_info": self._system_info
        }

    async def _initialize_prometheus_metrics(self) -> None:
        """Initialize Prometheus metrics"""
        try:
            # Default system metrics
            self._prometheus_metrics['uptime_seconds'] = Gauge(
                'uptime_seconds',
                'Service uptime in seconds',
                registry=self._registry
            )

            self._prometheus_metrics['requests_total'] = Counter(
                'requests_total',
                'Total number of requests',
                ['method', 'endpoint', 'status'],
                registry=self._registry
            )

            self._prometheus_metrics['request_duration_seconds'] = Histogram(
                'request_duration_seconds',
                'Request duration in seconds',
                ['method', 'endpoint'],
                registry=self._registry
            )

            self._prometheus_metrics['active_connections'] = Gauge(
                'active_connections',
                'Number of active connections',
                registry=self._registry
            )

            logger.info("✅ Prometheus metrics initialized")

        except Exception as e:
            logger.error(f"❌ Failed to initialize Prometheus metrics: {e}")
            raise

    async def _create_default_metric_definitions(self) -> None:
        """Create default metric definitions"""
        default_metrics = [
            {
                "name": "http_requests_total",
                "metric_type": "counter",
                "unit": "count",
                "description": "Total HTTP requests",
                "category": "application"
            },
            {
                "name": "http_request_duration_ms",
                "metric_type": "histogram",
                "unit": "milliseconds",
                "description": "HTTP request duration",
                "category": "application"
            },
            {
                "name": "system_cpu_usage_percent",
                "metric_type": "gauge",
                "unit": "percentage",
                "description": "System CPU usage percentage",
                "category": "system"
            },
            {
                "name": "system_memory_usage_percent",
                "metric_type": "gauge",
                "unit": "percentage",
                "description": "System memory usage percentage",
                "category": "system"
            },
            {
                "name": "rag_query_total",
                "metric_type": "counter",
                "unit": "count",
                "description": "Total RAG queries",
                "category": "business"
            },
            {
                "name": "rag_query_duration_ms",
                "metric_type": "histogram",
                "unit": "milliseconds",
                "description": "RAG query duration",
                "category": "business"
            },
            {
                "name": "rag_documents_indexed_total",
                "metric_type": "counter",
                "unit": "count",
                "description": "Total documents indexed",
                "category": "business"
            }
        ]

        for metric_config in default_metrics:
            await self.create_metric_definition(**metric_config)

    async def _initialize_collectors(self) -> None:
        """Initialize metric collectors"""
        # Initialize any additional collectors here
        pass

    async def _create_prometheus_metric(self, definition: MetricDefinition) -> None:
        """Create a Prometheus metric from definition"""
        try:
            name = definition.name
            description = definition.description or f"Metric: {name}"

            if definition.metric_type == "counter":
                metric = Counter(
                    name,
                    description,
                    list(definition.labels_schema.keys()) if definition.labels_schema else [],
                    registry=self._registry
                )
            elif definition.metric_type == "gauge":
                metric = Gauge(
                    name,
                    description,
                    list(definition.labels_schema.keys()) if definition.labels_schema else [],
                    registry=self._registry
                )
            elif definition.metric_type == "histogram":
                metric = Histogram(
                    name,
                    description,
                    list(definition.labels_schema.keys()) if definition.labels_schema else [],
                    registry=self._registry
                )
            elif definition.metric_type == "summary":
                metric = Summary(
                    name,
                    description,
                    list(definition.labels_schema.keys()) if definition.labels_schema else [],
                    registry=self._registry
                )
            else:
                logger.warning(f"Unsupported metric type: {definition.metric_type}")
                return

            self._prometheus_metrics[name] = metric
            logger.debug(f"Created Prometheus metric: {name}")

        except Exception as e:
            logger.error(f"❌ Failed to create Prometheus metric {name}: {e}")

    async def _update_prometheus_metric(self, metric_point: MetricPoint) -> None:
        """Update Prometheus metric with new value"""
        try:
            metric = self._prometheus_metrics.get(metric_point.name)
            if not metric:
                return

            labels = metric_point.labels

            if metric_point.metric_type == "counter":
                if labels:
                    metric.labels(**labels).inc(metric_point.value)
                else:
                    metric.inc(metric_point.value)
            elif metric_point.metric_type == "gauge":
                if labels:
                    metric.labels(**labels).set(metric_point.value)
                else:
                    metric.set(metric_point.value)
            elif metric_point.metric_type == "histogram":
                if labels:
                    metric.labels(**labels).observe(metric_point.value)
                else:
                    metric.observe(metric_point.value)
            elif metric_point.metric_type == "summary":
                if labels:
                    metric.labels(**labels).observe(metric_point.value)
                else:
                    metric.observe(metric_point.value)

        except Exception as e:
            logger.error(f"Error updating Prometheus metric {metric_point.name}: {e}")

    async def _collection_loop(self) -> None:
        """Background loop for metrics collection"""
        interval = self.config.collection_interval_seconds

        while self._running:
            try:
                # Collect system metrics
                if interval >= 60:  # Only collect system metrics for longer intervals
                    await self.collect_system_metrics()

                # Process buffered metrics
                await self._flush_metrics()

                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in metrics collection loop: {e}")
                await asyncio.sleep(min(interval, 60))

    async def _flush_metrics(self) -> None:
        """Flush buffered metrics to storage"""
        async with self._buffer_lock:
            if not self._metric_buffer:
                return

            metrics_to_process = self._metric_buffer.copy()
            self._metric_buffer.clear()

        # Process metrics (in a real implementation, this would store to database)
        for metric in metrics_to_process:
            try:
                # Store metric to database or other storage
                # This is where you'd implement the actual storage logic
                pass
            except Exception as e:
                logger.error(f"Error processing metric {metric.name}: {e}")

        if metrics_to_process:
            logger.debug(f"Processed {len(metrics_to_process)} metrics")

    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information"""
        return {
            "hostname": platform.node(),
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": psutil.cpu_count(),
            "memory_total": psutil.virtual_memory().total,
            "disk_total": psutil.disk_usage('/').total
        }