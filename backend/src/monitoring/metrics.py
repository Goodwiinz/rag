"""
Custom Metrics Collection for Knowledge Graph Analytics Dashboard
Business and application-specific metrics collection and aggregation
"""

import time
import uuid
import asyncio
import logging
from typing import Dict, Any, Optional, List, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import json
import statistics

from .opentelemetry import otel_manager

logger = logging.getLogger(__name__)

class MetricType(Enum):
    """Types of metrics supported"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
    UNTYPED = "untyped"

@dataclass
class MetricValue:
    """Single metric value with metadata"""
    value: float
    timestamp: float
    labels: Dict[str, str] = field(default_factory=dict)
    unit: str = ""
    description: str = ""

@dataclass
class HistogramBucket:
    """Histogram bucket for distribution tracking"""
    upper_bound: float
    count: int = 0

class CustomMetric:
    """Base class for custom metrics"""

    def __init__(self, name: str, description: str, unit: str = "", labels: Optional[Dict[str, str]] = None):
        self.name = name
        self.description = description
        self.unit = unit
        self.default_labels = labels or {}
        self.values: deque = deque(maxlen=10000)  # Keep last 10k values
        self.created_at = time.time()
        self.last_updated = time.time()

    def add_label(self, key: str, value: str):
        """Add a default label"""
        self.default_labels[key] = value

    def record_value(self, value: float, labels: Optional[Dict[str, str]] = None):
        """Record a metric value"""
        metric_value = MetricValue(
            value=value,
            timestamp=time.time(),
            labels={**self.default_labels, **(labels or {})},
            unit=self.unit,
            description=self.description
        )
        self.values.append(metric_value)
        self.last_updated = time.time()

    def get_values(self, labels: Optional[Dict[str, str]] = None, limit: Optional[int] = None) -> List[MetricValue]:
        """Get metric values with optional filtering"""
        values = list(self.values)

        if labels:
            values = [v for v in values if all(v.labels.get(k) == v for k, v in labels.items())]

        if limit:
            values = values[-limit:]

        return values

    def get_latest_value(self, labels: Optional[Dict[str, str]] = None) -> Optional[MetricValue]:
        """Get the latest metric value"""
        values = self.get_values(labels, limit=1)
        return values[0] if values else None

    def clear(self):
        """Clear all stored values"""
        self.values.clear()

class Counter(CustomMetric):
    """Counter metric that only increases"""

    def __init__(self, name: str, description: str, unit: str = "", labels: Optional[Dict[str, str]] = None):
        super().__init__(name, description, unit, labels)
        self._counts: Dict[str, float] = defaultdict(float)

    def inc(self, value: float = 1, labels: Optional[Dict[str, str]] = None):
        """Increment the counter"""
        if value < 0:
            raise ValueError("Counter increment must be non-negative")

        merged_labels = {**self.default_labels, **(labels or {})}
        label_key = json.dumps(merged_labels, sort_keys=True)

        self._counts[label_key] += value

        # Record to OpenTelemetry
        otel_manager.increment_counter(self.name, merged_labels)

        # Store local value
        self.record_value(self._counts[label_key], merged_labels)

    def get(self, labels: Optional[Dict[str, str]] = None) -> float:
        """Get current counter value"""
        merged_labels = {**self.default_labels, **(labels or {})}
        label_key = json.dumps(merged_labels, sort_keys=True)
        return self._counts[label_key]

class Gauge(CustomMetric):
    """Gauge metric that can increase or decrease"""

    def __init__(self, name: str, description: str, unit: str = "", labels: Optional[Dict[str, str]] = None):
        super().__init__(name, description, unit, labels)
        self._values: Dict[str, float] = {}

    def set(self, value: float, labels: Optional[Dict[str, str]] = None):
        """Set the gauge value"""
        merged_labels = {**self.default_labels, **(labels or {})}
        label_key = json.dumps(merged_labels, sort_keys=True)

        self._values[label_key] = value

        # Record to OpenTelemetry
        otel_manager.record_metric(self.name, value, merged_labels)

        # Store local value
        self.record_value(value, merged_labels)

    def inc(self, value: float = 1, labels: Optional[Dict[str, str]] = None):
        """Increment the gauge"""
        merged_labels = {**self.default_labels, **(labels or {})}
        label_key = json.dumps(merged_labels, sort_keys=True)

        self._values[label_key] = self._values.get(label_key, 0) + value

        # Record to OpenTelemetry
        otel_manager.record_metric(self.name, self._values[label_key], merged_labels)

        # Store local value
        self.record_value(self._values[label_key], merged_labels)

    def dec(self, value: float = 1, labels: Optional[Dict[str, str]] = None):
        """Decrement the gauge"""
        self.inc(-value, labels)

    def get(self, labels: Optional[Dict[str, str]] = None) -> Optional[float]:
        """Get current gauge value"""
        merged_labels = {**self.default_labels, **(labels or {})}
        label_key = json.dumps(merged_labels, sort_keys=True)
        return self._values.get(label_key)

class Histogram(CustomMetric):
    """Histogram metric with buckets for distributions"""

    def __init__(self, name: str, description: str, buckets: List[float] = None,
                 unit: str = "", labels: Optional[Dict[str, str]] = None):
        super().__init__(name, description, unit, labels)
        self.buckets = buckets or [0.1, 0.5, 1.0, 2.5, 5.0, 10.0]
        self._counts: Dict[str, List[int]] = defaultdict(lambda: [0] * (len(self.buckets) + 1))
        self._sums: Dict[str, float] = defaultdict(float)

    def observe(self, value: float, labels: Optional[Dict[str, str]] = None):
        """Observe a value"""
        merged_labels = {**self.default_labels, **(labels or {})}
        label_key = json.dumps(merged_labels, sort_keys=True)

        # Update bucket counts
        bucket_counts = self._counts[label_key]
        for i, upper_bound in enumerate(self.buckets):
            if value <= upper_bound:
                bucket_counts[i] += 1

        # Update +Inf bucket
        bucket_counts[-1] += 1

        # Update sum
        self._sums[label_key] += value

        # Record to OpenTelemetry
        otel_manager.record_metric(f"{name}_bucket", value, {**merged_labels, "le": str(upper_bound)})
        otel_manager.record_metric(f"{name}_sum", value, merged_labels)
        otel_manager.record_metric(f"{name}_count", 1, merged_labels)

        # Store local value
        self.record_value(value, merged_labels)

    def get_buckets(self, labels: Optional[Dict[str, str]] = None) -> List[HistogramBucket]:
        """Get bucket counts"""
        merged_labels = {**self.default_labels, **(labels or {})}
        label_key = json.dumps(merged_labels, sort_keys=True)

        bucket_counts = self._counts[label_key]
        return [
            HistogramBucket(upper_bound=upper_bound, count=count)
            for upper_bound, count in zip(self.buckets, bucket_counts[:-1])
        ]

    def get_sum(self, labels: Optional[Dict[str, str]] = None) -> float:
        """Get sum of observed values"""
        merged_labels = {**self.default_labels, **(labels or {})}
        label_key = json.dumps(merged_labels, sort_keys=True)
        return self._sums[label_key]

    def get_count(self, labels: Optional[Dict[str, str]] = None) -> int:
        """Get count of observed values"""
        merged_labels = {**self.default_labels, **(labels or {})}
        label_key = json.dumps(merged_labels, sort_keys=True)
        return self._counts[label_key][-1]  # +Inf bucket

    def get_percentile(self, percentile: float, labels: Optional[Dict[str, str]] = None) -> float:
        """Calculate percentile from observed values"""
        values = [v.value for v in self.get_values(labels)]
        if not values:
            return 0.0

        values.sort()
        index = int(len(values) * percentile / 100)
        return values[min(index, len(values) - 1)]

class BusinessMetrics:
    """Business-specific metrics for the Knowledge Graph Analytics Dashboard"""

    def __init__(self):
        self.metrics: Dict[str, CustomMetric] = {}
        self._initialize_business_metrics()

    def _initialize_business_metrics(self):
        """Initialize all business metrics"""

        # User Engagement Metrics
        self.metrics["user_sessions_total"] = Counter(
            "user_sessions_total",
            "Total number of user sessions",
            "sessions"
        )

        self.metrics["user_session_duration_seconds"] = Histogram(
            "user_session_duration_seconds",
            "Duration of user sessions",
            buckets=[10, 30, 60, 300, 600, 1800, 3600],
            unit="seconds"
        )

        self.metrics["page_views_total"] = Counter(
            "page_views_total",
            "Total number of page views",
            "views"
        )

        self.metrics["feature_usage_total"] = Counter(
            "feature_usage_total",
            "Total feature usage",
            "usages"
        )

        # Knowledge Graph Metrics
        self.metrics["nodes_total"] = Gauge(
            "nodes_total",
            "Total number of nodes in the knowledge graph",
            "nodes"
        )

        self.metrics["edges_total"] = Gauge(
            "edges_total",
            "Total number of edges in the knowledge graph",
            "edges"
        )

        self.metrics["graph_query_duration_seconds"] = Histogram(
            "graph_query_duration_seconds",
            "Duration of graph queries",
            buckets=[0.001, 0.01, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0],
            unit="seconds"
        )

        self.metrics["graph_query_complexity_score"] = Histogram(
            "graph_query_complexity_score",
            "Complexity score of graph queries",
            buckets=[1, 2, 3, 5, 8, 13, 21, 34],
            unit="score"
        )

        # Search & Analytics Metrics
        self.metrics["search_queries_total"] = Counter(
            "search_queries_total",
            "Total number of search queries",
            "queries"
        )

        self.metrics["search_results_total"] = Histogram(
            "search_results_total",
            "Number of search results returned",
            buckets=[0, 1, 5, 10, 25, 50, 100, 250, 500],
            unit="results"
        )

        self.metrics["search_query_duration_seconds"] = Histogram(
            "search_query_duration_seconds",
            "Duration of search queries",
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
            unit="seconds"
        )

        self.metrics["search_precision_score"] = Gauge(
            "search_precision_score",
            "Search precision score",
            "score"
        )

        self.metrics["search_recall_score"] = Gauge(
            "search_recall_score",
            "Search recall score",
            "score"
        )

        # Document Processing Metrics
        self.metrics["documents_processed_total"] = Counter(
            "documents_processed_total",
            "Total number of documents processed",
            "documents"
        )

        self.metrics["document_processing_duration_seconds"] = Histogram(
            "document_processing_duration_seconds",
            "Duration of document processing",
            buckets=[1, 5, 10, 30, 60, 300, 600, 1800],
            unit="seconds"
        )

        self.metrics["document_size_bytes"] = Histogram(
            "document_size_bytes",
            "Size of processed documents",
            buckets=[1024, 10240, 102400, 1048576, 10485760, 104857600],
            unit="bytes"
        )

        self.metrics["extraction_entities_total"] = Histogram(
            "extraction_entities_total",
            "Number of entities extracted from documents",
            buckets=[1, 5, 10, 25, 50, 100, 250, 500],
            unit="entities"
        )

        # API Performance Metrics
        self.metrics["api_request_duration_seconds"] = Histogram(
            "api_request_duration_seconds",
            "Duration of API requests",
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
            unit="seconds"
        )

        self.metrics["api_request_size_bytes"] = Histogram(
            "api_request_size_bytes",
            "Size of API requests",
            buckets=[1024, 10240, 102400, 1048576],
            unit="bytes"
        )

        self.metrics["api_response_size_bytes"] = Histogram(
            "api_response_size_bytes",
            "Size of API responses",
            buckets=[1024, 10240, 102400, 1048576, 10485760],
            unit="bytes"
        )

        self.metrics["api_errors_total"] = Counter(
            "api_errors_total",
            "Total number of API errors",
            "errors"
        )

        # System Resource Metrics
        self.metrics["memory_usage_bytes"] = Gauge(
            "memory_usage_bytes",
            "Memory usage in bytes",
            "bytes"
        )

        self.metrics["cpu_usage_percent"] = Gauge(
            "cpu_usage_percent",
            "CPU usage percentage",
            "percent"
        )

        self.metrics["disk_usage_bytes"] = Gauge(
            "disk_usage_bytes",
            "Disk usage in bytes",
            "bytes"
        )

        self.metrics["active_connections_total"] = Gauge(
            "active_connections_total",
            "Total number of active connections",
            "connections"
        )

        # Quality & Reliability Metrics
        self.metrics["uptime_percentage"] = Gauge(
            "uptime_percentage",
            "System uptime percentage",
            "percent"
        )

        self.metrics["error_rate_percentage"] = Gauge(
            "error_rate_percentage",
            "Error rate percentage",
            "percent"
        )

        self.metrics["availability_score"] = Gauge(
            "availability_score",
            "Availability score",
            "score"
        )

        self.metrics["response_time_p95_seconds"] = Gauge(
            "response_time_p95_seconds",
            "95th percentile response time",
            "seconds"
        )

        # Machine Learning Metrics
        self.metrics["ml_model_inference_duration_seconds"] = Histogram(
            "ml_model_inference_duration_seconds",
            "ML model inference duration",
            buckets=[0.001, 0.01, 0.1, 0.5, 1.0, 2.5, 5.0],
            unit="seconds"
        )

        self.metrics["ml_model_accuracy_score"] = Gauge(
            "ml_model_accuracy_score",
            "ML model accuracy score",
            "score"
        )

        self.metrics["ml_model_predictions_total"] = Counter(
            "ml_model_predictions_total",
            "Total number of ML model predictions",
            "predictions"
        )

        self.metrics["ml_model_errors_total"] = Counter(
            "ml_model_errors_total",
            "Total number of ML model errors",
            "errors"
        )

    def get_metric(self, name: str) -> Optional[CustomMetric]:
        """Get a metric by name"""
        return self.metrics.get(name)

    def get_all_metrics(self) -> Dict[str, CustomMetric]:
        """Get all metrics"""
        return self.metrics.copy()

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics"""
        summary = {
            "total_metrics": len(self.metrics),
            "metrics_by_type": defaultdict(int),
            "metrics_with_data": 0,
            "last_updated": 0
        }

        for metric in self.metrics.values():
            # Count by type
            summary["metrics_by_type"][type(metric).__name__.lower()] += 1

            # Check if metric has data
            if metric.values:
                summary["metrics_with_data"] += 1

            # Track latest update
            summary["last_updated"] = max(summary["last_updated"], metric.last_updated)

        return dict(summary)

    def export_metrics_json(self) -> str:
        """Export all metrics as JSON"""
        export_data = {
            "timestamp": time.time(),
            "metrics": {}
        }

        for name, metric in self.metrics.items():
            metric_data = {
                "name": metric.name,
                "description": metric.description,
                "unit": metric.unit,
                "type": type(metric).__name__.lower(),
                "created_at": metric.created_at,
                "last_updated": metric.last_updated,
                "values_count": len(metric.values)
            }

            # Add latest value if available
            latest = metric.get_latest_value()
            if latest:
                metric_data["latest_value"] = {
                    "value": latest.value,
                    "timestamp": latest.timestamp,
                    "labels": latest.labels
                }

            export_data["metrics"][name] = metric_data

        return json.dumps(export_data, indent=2)

# Global business metrics instance
business_metrics = BusinessMetrics()

# Convenience functions for commonly used metrics
def track_user_session(duration_seconds: float, user_id: Optional[str] = None):
    """Track a user session"""
    labels = {}
    if user_id:
        labels["user_id"] = user_id

    business_metrics.metrics["user_sessions_total"].inc(1, labels)
    business_metrics.metrics["user_session_duration_seconds"].observe(duration_seconds, labels)

def track_page_view(page: str, user_id: Optional[str] = None):
    """Track a page view"""
    labels = {"page": page}
    if user_id:
        labels["user_id"] = user_id

    business_metrics.metrics["page_views_total"].inc(1, labels)

def track_feature_usage(feature: str, action: str, user_id: Optional[str] = None):
    """Track feature usage"""
    labels = {"feature": feature, "action": action}
    if user_id:
        labels["user_id"] = user_id

    business_metrics.metrics["feature_usage_total"].inc(1, labels)

def track_search_query(query: str, results_count: int, duration_seconds: float,
                      precision: Optional[float] = None, recall: Optional[float] = None):
    """Track a search query"""
    labels = {"query_length": str(len(query))}

    business_metrics.metrics["search_queries_total"].inc(1, labels)
    business_metrics.metrics["search_results_total"].observe(results_count, labels)
    business_metrics.metrics["search_query_duration_seconds"].observe(duration_seconds, labels)

    if precision is not None:
        business_metrics.metrics["search_precision_score"].set(precision, labels)
    if recall is not None:
        business_metrics.metrics["search_recall_score"].set(recall, labels)

def track_document_processing(file_size_bytes: int, duration_seconds: float,
                            entities_extracted: int, file_type: str):
    """Track document processing"""
    labels = {"file_type": file_type}

    business_metrics.metrics["documents_processed_total"].inc(1, labels)
    business_metrics.metrics["document_processing_duration_seconds"].observe(duration_seconds, labels)
    business_metrics.metrics["document_size_bytes"].observe(file_size_bytes, labels)
    business_metrics.metrics["extraction_entities_total"].observe(entities_extracted, labels)

def track_graph_query(query_complexity: int, duration_seconds: float, nodes_returned: int):
    """Track graph query"""
    labels = {}

    business_metrics.metrics["graph_query_duration_seconds"].observe(duration_seconds, labels)
    business_metrics.metrics["graph_query_complexity_score"].observe(query_complexity, labels)

def track_api_request(endpoint: str, method: str, status_code: int,
                     duration_seconds: float, request_size: int, response_size: int):
    """Track API request"""
    labels = {
        "endpoint": endpoint,
        "method": method,
        "status_code": str(status_code)
    }

    business_metrics.metrics["api_request_duration_seconds"].observe(duration_seconds, labels)
    business_metrics.metrics["api_request_size_bytes"].observe(request_size, labels)
    business_metrics.metrics["api_response_size_bytes"].observe(response_size, labels)

    if status_code >= 400:
        business_metrics.metrics["api_errors_total"].inc(1, labels)

def track_ml_inference(model_name: str, duration_seconds: float, accuracy: Optional[float] = None,
                      success: bool = True):
    """Track ML model inference"""
    labels = {"model_name": model_name}

    business_metrics.metrics["ml_model_inference_duration_seconds"].observe(duration_seconds, labels)
    business_metrics.metrics["ml_model_predictions_total"].inc(1, labels)

    if not success:
        business_metrics.metrics["ml_model_errors_total"].inc(1, labels)

    if accuracy is not None:
        business_metrics.metrics["ml_model_accuracy_score"].set(accuracy, labels)