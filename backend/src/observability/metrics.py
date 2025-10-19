"""
OpenTelemetry metrics configuration for custom business and system metrics

Provides comprehensive metrics collection including:
- System performance metrics (CPU, memory, latency)
- Business metrics (RAG quality scores, user engagement)
- Database operation metrics
- File processing pipeline metrics
- Search performance metrics
- Custom SLI/SLO tracking
"""

import time
import threading
from typing import Dict, Any, Optional, List
from collections import defaultdict, deque
from dataclasses import dataclass

from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION, DEPLOYMENT_ENVIRONMENT
from opentelemetry.metrics import Histogram, Counter, UpDownCounter, ObservableGauge

from ..core.config import settings


# Global meter and metrics instances
_meter = None
_metrics_registry = {}


@dataclass
class MetricConfig:
    """Configuration for metric creation"""
    name: str
    description: str
    unit: str = ""
    enabled: bool = True


class MetricsRegistry:
    """Registry for managing all application metrics"""

    def __init__(self):
        self.histograms: Dict[str, Histogram] = {}
        self.counters: Dict[str, Counter] = {}
        self.updown_counters: Dict[str, UpDownCounter] = {}
        self.gauges: Dict[str, ObservableGauge] = {}
        self._lock = threading.Lock()

    def create_histogram(self, config: MetricConfig) -> Histogram:
        """Create or get a histogram metric"""
        with self._lock:
            if config.name not in self.histograms:
                self.histograms[config.name] = _meter.create_histogram(
                    name=config.name,
                    description=config.description,
                    unit=config.unit
                )
            return self.histograms[config.name]

    def create_counter(self, config: MetricConfig) -> Counter:
        """Create or get a counter metric"""
        with self._lock:
            if config.name not in self.counters:
                self.counters[config.name] = _meter.create_counter(
                    name=config.name,
                    description=config.description,
                    unit=config.unit
                )
            return self.counters[config.name]

    def create_updown_counter(self, config: MetricConfig) -> UpDownCounter:
        """Create or get an up-down counter metric"""
        with self._lock:
            if config.name not in self.updown_counters:
                self.updown_counters[config.name] = _meter.create_up_down_counter(
                    name=config.name,
                    description=config.description,
                    unit=config.unit
                )
            return self.updown_counters[config.name]

    def create_gauge(self, config: MetricConfig, callback) -> ObservableGauge:
        """Create or get an observable gauge metric"""
        with self._lock:
            if config.name not in self.gauges:
                self.gauges[config.name] = _meter.create_observable_gauge(
                    name=config.name,
                    description=config.description,
                    unit=config.unit,
                    callbacks=[callback]
                )
            return self.gauges[config.name]


def configure_metrics() -> metrics.Meter:
    """Configure OpenTelemetry metrics with Prometheus and OTLP exporters"""
    global _meter, _metrics_registry

    # Set up resource attributes
    resource = Resource.create({
        SERVICE_NAME: "rag-system-backend",
        SERVICE_VERSION: settings.VERSION,
        DEPLOYMENT_ENVIRONMENT: settings.ENVIRONMENT,
        "service.instance.id": os.environ.get("HOSTNAME", "unknown"),
    })

    # Configure Prometheus exporter for scraping
    prometheus_reader = PrometheusMetricReader()

    # Configure OTLP exporter for remote monitoring
    otlp_endpoint = os.environ.get("OTLP_METRICS_ENDPOINT", "http://tempo:4317")
    otlp_exporter = OTLPMetricExporter(
        endpoint=otlp_endpoint,
        insecure=True,
    )

    # Create periodic exporter for OTLP
    periodic_reader = PeriodicExportingMetricReader(
        exporter=otlp_exporter,
        export_interval_millis=15000,  # 15 seconds
    )

    # Create meter provider
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[prometheus_reader, periodic_reader]
    )

    # Set as global meter provider
    metrics.set_meter_provider(meter_provider)

    # Create and store meter
    _meter = meter_provider.get_meter(__name__)
    _metrics_registry = MetricsRegistry()

    # Initialize default metrics
    initialize_default_metrics()

    return _meter


def get_meter() -> metrics.Meter:
    """Get the meter instance"""
    if _meter is None:
        configure_metrics()
    return _meter


def initialize_default_metrics():
    """Initialize default application metrics"""

    # HTTP Request Metrics
    create_metrics([
        MetricConfig(
            name="http_requests_total",
            description="Total number of HTTP requests",
            unit="requests"
        ),
        MetricConfig(
            name="http_request_duration_seconds",
            description="HTTP request duration in seconds",
            unit="seconds"
        ),
        MetricConfig(
            name="http_requests_active",
            description="Number of active HTTP requests",
            unit="requests"
        ),
    ])

    # Database Metrics
    create_metrics([
        MetricConfig(
            name="database_connections_active",
            description="Number of active database connections",
            unit="connections"
        ),
        MetricConfig(
            name="database_query_duration_seconds",
            description="Database query duration in seconds",
            unit="seconds"
        ),
        MetricConfig(
            name="database_queries_total",
            description="Total number of database queries",
            unit="queries"
        ),
    ])

    # Search Performance Metrics
    create_metrics([
        MetricConfig(
            name="search_requests_total",
            description="Total number of search requests",
            unit="requests"
        ),
        MetricConfig(
            name="search_duration_seconds",
            description="Search request duration in seconds",
            unit="seconds"
        ),
        MetricConfig(
            name="search_results_count",
            description="Number of search results returned",
            unit="results"
        ),
    ])

    # RAG Quality Metrics
    create_metrics([
        MetricConfig(
            name="rag_answer_relevancy_score",
            description="RAG answer relevancy score",
            unit="score"
        ),
        MetricConfig(
            name="rag_faithfulness_score",
            description="RAG faithfulness score",
            unit="score"
        ),
        MetricConfig(
            name="rag_contextual_relevancy_score",
            description="RAG contextual relevancy score",
            unit="score"
        ),
    ])

    # File Processing Metrics
    create_metrics([
        MetricConfig(
            name="file_processing_duration_seconds",
            description="File processing duration in seconds",
            unit="seconds"
        ),
        MetricConfig(
            name="file_processing_total",
            description="Total number of files processed",
            unit="files"
        ),
        MetricConfig(
            name="file_processing_errors_total",
            description="Total number of file processing errors",
            unit="errors"
        ),
    ])

    # System Resource Metrics
    create_metrics([
        MetricConfig(
            name="system_cpu_usage_percent",
            description="System CPU usage percentage",
            unit="percent"
        ),
        MetricConfig(
            name="system_memory_usage_bytes",
            description="System memory usage in bytes",
            unit="bytes"
        ),
        MetricConfig(
            name="system_disk_usage_bytes",
            description="System disk usage in bytes",
            unit="bytes"
        ),
    ])


def create_metrics(configs: List[MetricConfig]) -> Dict[str, Any]:
    """Create multiple metrics from configuration list"""
    metrics_dict = {}

    for config in configs:
        if config.enabled:
            if "duration" in config.name or "latency" in config.name:
                metric = _metrics_registry.create_histogram(config)
            elif "total" in config.name or "count" in config.name:
                metric = _metrics_registry.create_counter(config)
            elif "active" in config.name or "current" in config.name:
                metric = _metrics_registry.create_updown_counter(config)
            else:
                metric = _metrics_registry.create_histogram(config)

            metrics_dict[config.name] = metric

    return metrics_dict


def record_histogram(
    metric_name: str,
    value: float,
    attributes: Optional[Dict[str, str]] = None
):
    """Record a histogram metric value"""
    if metric_name in _metrics_registry.histograms:
        histogram = _metrics_registry.histograms[metric_name]
        if attributes:
            histogram.record(value, attributes)
        else:
            histogram.record(value)


def increment_counter(
    metric_name: str,
    value: int = 1,
    attributes: Optional[Dict[str, str]] = None
):
    """Increment a counter metric"""
    if metric_name in _metrics_registry.counters:
        counter = _metrics_registry.counters[metric_name]
        if attributes:
            counter.add(value, attributes)
        else:
            counter.add(value)


def increment_updown_counter(
    metric_name: str,
    value: int = 1,
    attributes: Optional[Dict[str, str]] = None
):
    """Increment an up-down counter metric"""
    if metric_name in _metrics_registry.updown_counters:
        counter = _metrics_registry.updown_counters[metric_name]
        if attributes:
            counter.add(value, attributes)
        else:
            counter.add(value)


class PerformanceTracker:
    """Track performance metrics for operations"""

    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = None

    def start(self):
        """Start tracking operation"""
        self.start_time = time.time()
        return self

    def record(self, attributes: Optional[Dict[str, str]] = None):
        """Record operation completion"""
        if self.start_time:
            duration = time.time() - self.start_time
            metric_name = f"{self.operation_name}_duration_seconds"
            record_histogram(metric_name, duration, attributes)

            # Also increment operation counter
            counter_name = f"{self.operation_name}_total"
            increment_counter(counter_name, attributes=attributes)

    def record_error(self, error_type: str, attributes: Optional[Dict[str, str]] = None):
        """Record operation error"""
        base_attrs = {"error_type": error_type}
        if attributes:
            base_attrs.update(attributes)

        counter_name = f"{self.operation_name}_errors_total"
        increment_counter(counter_name, attributes=base_attrs)

    def __enter__(self):
        """Context manager entry"""
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if exc_type:
            self.record_error(exc_type.__name__)
        else:
            self.record()


def track_performance(operation_name: str) -> PerformanceTracker:
    """Create a performance tracker for an operation"""
    return PerformanceTracker(operation_name)


def record_rag_metrics(
    answer_relevancy: float,
    faithfulness: float,
    contextual_relevancy: float,
    attributes: Optional[Dict[str, str]] = None
):
    """Record RAG quality metrics"""
    base_attrs = attributes or {}

    record_histogram("rag_answer_relevancy_score", answer_relevancy, base_attrs)
    record_histogram("rag_faithfulness_score", faithfulness, base_attrs)
    record_histogram("rag_contextual_relevancy_score", contextual_relevancy, base_attrs)

    # Check SLO compliance
    slo_attributes = base_attrs.copy()
    slo_attributes["slo_met"] = str(answer_relevancy > 0.7)
    increment_counter("rag_answer_relevancy_slo_total", attributes=slo_attributes)

    slo_attributes["slo_met"] = str(faithfulness > 0.9)
    increment_counter("rag_faithfulness_slo_total", attributes=slo_attributes)

    slo_attributes["slo_met"] = str(contextual_relevancy > 0.7)
    increment_counter("rag_contextual_relevancy_slo_total", attributes=slo_attributes)


def record_search_metrics(
    query: str,
    result_count: int,
    duration: float,
    search_type: str,
    attributes: Optional[Dict[str, str]] = None
):
    """Record search operation metrics"""
    base_attrs = {
        "search_type": search_type,
        "query_length": str(len(query)),
    }
    if attributes:
        base_attrs.update(attributes)

    increment_counter("search_requests_total", attributes=base_attrs)
    record_histogram("search_duration_seconds", duration, base_attrs)
    record_histogram("search_results_count", result_count, base_attrs)


def record_file_processing_metrics(
    file_type: str,
    file_size: int,
    duration: float,
    success: bool,
    attributes: Optional[Dict[str, str]] = None
):
    """Record file processing metrics"""
    base_attrs = {
        "file_type": file_type,
        "success": str(success),
    }
    if attributes:
        base_attrs.update(attributes)

    # File size categories
    if file_size < 1024 * 1024:  # < 1MB
        size_category = "small"
    elif file_size < 10 * 1024 * 1024:  # < 10MB
        size_category = "medium"
    else:
        size_category = "large"

    base_attrs["size_category"] = size_category

    record_histogram("file_processing_duration_seconds", duration, base_attrs)
    increment_counter("file_processing_total", attributes=base_attrs)

    if not success:
        increment_counter("file_processing_errors_total", attributes=base_attrs)