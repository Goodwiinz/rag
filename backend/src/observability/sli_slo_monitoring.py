"""
SLI/SLO Monitoring Framework
Service Level Indicators and Service Level Objectives for the RAG System
"""

import time
import asyncio
import statistics
from typing import Dict, Any, Optional, List, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone as dt_timezone, timedelta
from collections import defaultdict, deque
import json
import logging

from .prometheus_metrics import prometheus_metrics
from .document_processing_observability import document_processing_observability

logger = logging.getLogger(__name__)

class SLOStatus(Enum):
    """SLO compliance status"""
    COMPLIANT = "compliant"
    WARNING = "warning"
    VIOLATION = "violation"
    UNKNOWN = "unknown"

class SLIType(Enum):
    """Types of Service Level Indicators"""
    AVAILABILITY = "availability"
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    SUCCESS_RATE = "success_rate"
    QUALITY_SCORE = "quality_score"

class TimeWindow(Enum):
    """SLO time windows"""
    LAST_1H = "1h"
    LAST_24H = "24h"
    LAST_7D = "7d"
    LAST_30D = "30d"

@dataclass
class SLIDefinition:
    """Service Level Indicator definition"""
    name: str
    description: str
    metric_name: str
    unit: str
    sli_type: SLIType
    labels: Dict[str, str] = field(default_factory=dict)
    aggregation: str = "avg"  # avg, sum, count, rate
    good_threshold: Optional[float] = None  # For binary good/bad classification
    measurement_window: int = 300  # seconds

@dataclass
class SLODefinition:
    """Service Level Objective definition"""
    name: str
    description: str
    sli: SLIDefinition
    target_percentage: float  # 0-100
    time_window: TimeWindow
    error_budget_percentage: float  # 0-100
    alerting_threshold: float  # Alert when SLO falls below this
    is_business_critical: bool = True

@dataclass
class SLIMeasurement:
    """SLI measurement with metadata"""
    sli_name: str
    timestamp: float
    value: float
    sample_count: int
    window_start: float
    window_end: float
    labels: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SLOResult:
    """SLO compliance result"""
    slo_name: str
    sli_value: float
    target_percentage: float
    achieved_percentage: float
    error_budget_consumed: float
    error_budget_remaining: float
    status: SLOStatus
    time_window: TimeWindow
    measurement_timestamp: float
    sample_count: int

class SLIMonitor:
    """Service Level Indicator Monitor"""

    def __init__(self):
        self.sli_definitions: Dict[str, SLIDefinition] = {}
        self.slo_definitions: Dict[str, SLODefinition] = {}
        self.measurements: deque = deque(maxlen=10000)  # Keep last 10k measurements
        self.slo_results: Dict[str, SLOResult] = {}

        # Raw metrics storage for calculations
        self.raw_metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=5000))

        # Initialize default SLIs and SLOs
        self._initialize_default_slis_slos()

    def _initialize_default_slis_slos(self):
        """Initialize default SLIs and SLOs for the RAG system"""

        # Document Processing SLIs
        self.sli_definitions["document_processing_success_rate"] = SLIDefinition(
            name="document_processing_success_rate",
            description="Percentage of documents processed successfully",
            metric_name="document_processing_total",
            unit="percentage",
            sli_type=SLIType.SUCCESS_RATE,
            labels={"status": "completed"},
            aggregation="rate"
        )

        self.slo_definitions["document_processing_reliability"] = SLODefinition(
            name="document_processing_reliability",
            description="Document processing must succeed 99% of the time",
            sli=self.sli_definitions["document_processing_success_rate"],
            target_percentage=99.0,
            time_window=TimeWindow.LAST_24H,
            error_budget_percentage=1.0,
            alerting_threshold=98.0,
            is_business_critical=True
        )

        # API Response Time SLI
        self.sli_definitions["api_response_time_p99"] = SLIDefinition(
            name="api_response_time_p99",
            description="99th percentile API response time",
            metric_name="http_request_duration_seconds",
            unit="seconds",
            sli_type=SLIType.LATENCY,
            aggregation="p99",
            good_threshold=2.0  # 2 seconds is good
        )

        self.slo_definitions["api_latency_slo"] = SLODefinition(
            name="api_latency_slo",
            description="99% of API requests must complete within 2 seconds",
            sli=self.sli_definitions["api_response_time_p99"],
            target_percentage=99.0,
            time_window=TimeWindow.LAST_1H,
            error_budget_percentage=1.0,
            alerting_threshold=95.0,
            is_business_critical=True
        )

        # API Availability SLI
        self.sli_definitions["api_availability"] = SLIDefinition(
            name="api_availability",
            description="API availability percentage",
            metric_name="http_requests_total",
            unit="percentage",
            sli_type=SLIType.AVAILABILITY,
            labels={"status_code": ["2xx", "3xx"]},  # Success codes
            aggregation="rate"
        )

        self.slo_definitions["api_availability_slo"] = SLODefinition(
            name="api_availability_slo",
            description="API must be available 99.9% of the time",
            sli=self.sli_definitions["api_availability"],
            target_percentage=99.9,
            time_window=TimeWindow.LAST_24H,
            error_budget_percentage=0.1,
            alerting_threshold=99.5,
            is_business_critical=True
        )

        # WebSocket Connection SLI
        self.sli_definitions["websocket_connection_success_rate"] = SLIDefinition(
            name="websocket_connection_success_rate",
            description="WebSocket connection success rate",
            metric_name="websocket_connections_total",
            unit="percentage",
            sli_type=SLIType.SUCCESS_RATE,
            aggregation="rate"
        )

        self.slo_definitions["websocket_reliability_slo"] = SLODefinition(
            name="websocket_reliability_slo",
            description="WebSocket connections must succeed 99.5% of the time",
            sli=self.sli_definitions["websocket_connection_success_rate"],
            target_percentage=99.5,
            time_window=TimeWindow.LAST_1H,
            error_budget_percentage=0.5,
            alerting_threshold=98.0,
            is_business_critical=True
        )

        # Search Query Performance SLI
        self.sli_definitions["search_query_latency_p95"] = SLIDefinition(
            name="search_query_latency_p95",
            description="95th percentile search query latency",
            metric_name="search_query_duration_seconds",
            unit="seconds",
            sli_type=SLIType.LATENCY,
            aggregation="p95",
            good_threshold=1.0  # 1 second is good
        )

        self.slo_definitions["search_performance_slo"] = SLODefinition(
            name="search_performance_slo",
            description="95% of search queries must complete within 1 second",
            sli=self.sli_definitions["search_query_latency_p95"],
            target_percentage=95.0,
            time_window=TimeWindow.LAST_1H,
            error_budget_percentage=5.0,
            alerting_threshold=90.0,
            is_business_critical=True
        )

        # Database Query Performance SLI
        self.sli_definitions["database_query_latency_p95"] = SLIDefinition(
            name="database_query_latency_p95",
            description="95th percentile database query latency",
            metric_name="database_query_duration_seconds",
            unit="seconds",
            sli_type=SLIType.LATENCY,
            aggregation="p95",
            good_threshold=0.5  # 500ms is good
        )

        self.slo_definitions["database_performance_slo"] = SLODefinition(
            name="database_performance_slo",
            description="95% of database queries must complete within 500ms",
            sli=self.sli_definitions["database_query_latency_p95"],
            target_percentage=95.0,
            time_window=TimeWindow.LAST_1H,
            error_budget_percentage=5.0,
            alerting_threshold=90.0,
            is_business_critical=True
        )

        # ML Model Quality SLI
        self.sli_definitions["ml_model_accuracy"] = SLIDefinition(
            name="ml_model_accuracy",
            description="ML model accuracy score",
            metric_name="ml_model_accuracy_score",
            unit="score",
            sli_type=SLIType.QUALITY_SCORE,
            aggregation="avg",
            good_threshold=0.85  # 85% accuracy is good
        )

        self.slo_definitions["ml_quality_slo"] = SLODefinition(
            name="ml_quality_slo",
            description="ML models must maintain 85% accuracy",
            sli=self.sli_definitions["ml_model_accuracy"],
            target_percentage=85.0,
            time_window=TimeWindow.LAST_7D,
            error_budget_percentage=15.0,
            alerting_threshold=80.0,
            is_business_critical=False
        )

    def record_metric_value(self, metric_name: str, value: float,
                           labels: Optional[Dict[str, Any]] = None,
                           timestamp: Optional[float] = None):
        """Record a raw metric value for SLI calculations"""
        timestamp = timestamp or time.time()
        labels = labels or {}

        self.raw_metrics[metric_name].append({
            'timestamp': timestamp,
            'value': value,
            'labels': labels
        })

    def calculate_sli(self, sli_name: str, time_window: Optional[TimeWindow] = None) -> Optional[float]:
        """Calculate SLI value for a given time window"""
        if sli_name not in self.sli_definitions:
            logger.error(f"Unknown SLI: {sli_name}")
            return None

        sli = self.sli_definitions[sli_name]
        time_window = time_window or TimeWindow.LAST_1H

        # Calculate time window bounds
        current_time = time.time()
        window_seconds = self._get_window_seconds(time_window)
        window_start = current_time - window_seconds

        # Get relevant metrics
        metrics = [
            m for m in self.raw_metrics.get(sli.metric_name, [])
            if m['timestamp'] >= window_start
        ]

        if not metrics:
            logger.warning(f"No metrics found for SLI {sli_name} in time window {time_window.value}")
            return None

        # Filter by labels if specified
        if sli.labels:
            filtered_metrics = []
            for metric in metrics:
                match = True
                for key, expected_value in sli.labels.items():
                    if isinstance(expected_value, list):
                        if metric['labels'].get(key) not in expected_value:
                            match = False
                            break
                    else:
                        if metric['labels'].get(key) != expected_value:
                            match = False
                            break
                if match:
                    filtered_metrics.append(metric)
            metrics = filtered_metrics

        if not metrics:
            logger.warning(f"No metrics match label filters for SLI {sli_name}")
            return None

        # Calculate SLI based on type and aggregation
        try:
            if sli.sli_type == SLIType.SUCCESS_RATE:
                return self._calculate_success_rate(sli, metrics)
            elif sli.sli_type == SLIType.AVAILABILITY:
                return self._calculate_availability(sli, metrics)
            elif sli.sli_type == SLIType.LATENCY:
                return self._calculate_latency_sli(sli, metrics)
            elif sli.sli_type == SLIType.ERROR_RATE:
                return self._calculate_error_rate(sli, metrics)
            elif sli.sli_type == SLIType.QUALITY_SCORE:
                return self._calculate_quality_score(sli, metrics)
            else:
                # Default: simple aggregation
                return self._calculate_simple_aggregation(sli, metrics)

        except Exception as e:
            logger.error(f"Error calculating SLI {sli_name}: {e}")
            return None

    def _calculate_success_rate(self, sli: SLIDefinition, metrics: List[Dict[str, Any]]) -> float:
        """Calculate success rate SLI"""
        if sli.aggregation == "rate":
            total_requests = len(metrics)
            if total_requests == 0:
                return 100.0

            successful_requests = sum(1 for m in metrics
                                    if m['labels'].get('status') in ['completed', 'success'])
            return (successful_requests / total_requests) * 100
        else:
            # Use good_threshold for binary classification
            total = len(metrics)
            if total == 0:
                return 100.0

            good_count = sum(1 for m in metrics if m['value'] >= (sli.good_threshold or 0))
            return (good_count / total) * 100

    def _calculate_availability(self, sli: SLIDefinition, metrics: List[Dict[str, Any]]) -> float:
        """Calculate availability SLI"""
        total_requests = len(metrics)
        if total_requests == 0:
            return 100.0

        # Count successful requests based on status codes
        successful_statuses = sli.labels.get("status_code", ["2xx", "3xx"])
        successful_requests = sum(1 for m in metrics
                                if any(m['labels'].get('status_code', '').startswith(code[:-1])
                                      for code in successful_statuses))

        return (successful_requests / total_requests) * 100

    def _calculate_latency_sli(self, sli: SLIDefinition, metrics: List[Dict[str, Any]]) -> float:
        """Calculate latency SLI"""
        if not metrics:
            return 100.0

        values = [m['value'] for m in metrics]

        if sli.aggregation == "p95":
            threshold_value = self._percentile(values, 95)
        elif sli.aggregation == "p99":
            threshold_value = self._percentile(values, 99)
        elif sli.aggregation == "avg":
            threshold_value = statistics.mean(values)
        else:
            threshold_value = statistics.mean(values)

        # Convert to percentage based on good threshold
        if sli.good_threshold:
            good_percentage = max(0, 100 - ((threshold_value / sli.good_threshold - 1) * 100))
            return min(100, good_percentage)
        else:
            # If no threshold, return inverse of latency (normalized)
            # This is a simplified approach - in practice, you'd have explicit SLOs
            max_acceptable = 5.0  # 5 seconds
            return max(0, 100 - ((threshold_value / max_acceptable) * 100))

    def _calculate_error_rate(self, sli: SLIDefinition, metrics: List[Dict[str, Any]]) -> float:
        """Calculate error rate SLI"""
        total_requests = len(metrics)
        if total_requests == 0:
            return 0.0  # No errors if no requests

        error_count = sum(1 for m in metrics
                        if m['labels'].get('status') in ['error', 'failed', 'timeout'])

        return (error_count / total_requests) * 100

    def _calculate_quality_score(self, sli: SLIDefinition, metrics: List[Dict[str, Any]]) -> float:
        """Calculate quality score SLI"""
        if not metrics:
            return 0.0

        if sli.aggregation == "avg":
            score = statistics.mean([m['value'] for m in metrics])
        elif sli.aggregation == "p95":
            score = self._percentile([m['value'] for m in metrics], 95)
        else:
            score = statistics.mean([m['value'] for m in metrics])

        # Convert to percentage (assuming scores are 0-1)
        return score * 100

    def _calculate_simple_aggregation(self, sli: SLIDefinition, metrics: List[Dict[str, Any]]) -> float:
        """Calculate simple aggregation SLI"""
        if not metrics:
            return 0.0

        values = [m['value'] for m in metrics]

        if sli.aggregation == "avg":
            return statistics.mean(values)
        elif sli.aggregation == "sum":
            return sum(values)
        elif sli.aggregation == "count":
            return len(values)
        elif sli.aggregation.startswith("p"):
            percentile = int(sli.aggregation[1:])
            return self._percentile(values, percentile)
        else:
            return statistics.mean(values)

    def _percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile of values"""
        if not values:
            return 0.0

        sorted_values = sorted(values)
        index = int((percentile / 100) * len(sorted_values))
        index = min(index, len(sorted_values) - 1)
        return sorted_values[index]

    def _get_window_seconds(self, time_window: TimeWindow) -> int:
        """Get time window in seconds"""
        window_map = {
            TimeWindow.LAST_1H: 3600,
            TimeWindow.LAST_24H: 86400,
            TimeWindow.LAST_7D: 604800,
            TimeWindow.LAST_30D: 2592000
        }
        return window_map.get(time_window, 3600)

    def calculate_slo(self, slo_name: str) -> Optional[SLOResult]:
        """Calculate SLO compliance for a specific SLO"""
        if slo_name not in self.slo_definitions:
            logger.error(f"Unknown SLO: {slo_name}")
            return None

        slo = self.slo_definitions[slo_name]

        # Calculate SLI value
        sli_value = self.calculate_sli(slo.sli.name, slo.time_window)
        if sli_value is None:
            return None

        # Calculate SLO compliance
        achieved_percentage = min(sli_value, slo.target_percentage)
        error_budget_consumed = max(0, (slo.target_percentage - achieved_percentage) / slo.target_percentage * 100)
        error_budget_remaining = max(0, 100 - error_budget_consumed)

        # Determine status
        if achieved_percentage >= slo.target_percentage:
            status = SLOStatus.COMPLIANT
        elif achieved_percentage >= slo.alerting_threshold:
            status = SLOStatus.WARNING
        else:
            status = SLOStatus.VIOLATION

        # Create result
        result = SLOResult(
            slo_name=slo_name,
            sli_value=sli_value,
            target_percentage=slo.target_percentage,
            achieved_percentage=achieved_percentage,
            error_budget_consumed=error_budget_consumed,
            error_budget_remaining=error_budget_remaining,
            status=status,
            time_window=slo.time_window,
            measurement_timestamp=time.time(),
            sample_count=len([m for m in self.raw_metrics.get(slo.sli.metric_name, [])
                            if m['timestamp'] >= time.time() - self._get_window_seconds(slo.time_window)])
        )

        self.slo_results[slo_name] = result
        return result

    def calculate_all_slos(self) -> Dict[str, SLOResult]:
        """Calculate all SLOs"""
        results = {}
        for slo_name in self.slo_definitions.keys():
            result = self.calculate_slo(slo_name)
            if result:
                results[slo_name] = result
        return results

    def get_slo_dashboard(self) -> Dict[str, Any]:
        """Get SLO dashboard data"""
        all_results = self.calculate_all_slos()

        # Summarize by status
        status_counts = defaultdict(int)
        business_critical_violations = 0

        for result in all_results.values():
            status_counts[result.status.value] += 1

            slo = self.slo_definitions[result.slo_name]
            if result.status == SLOStatus.VIOLATION and slo.is_business_critical:
                business_critical_violations += 1

        # Overall health score
        total_slos = len(all_results)
        compliant_slos = sum(1 for r in all_results.values() if r.status == SLOStatus.COMPLIANT)
        overall_health = (compliant_slos / total_slos * 100) if total_slos > 0 else 0

        return {
            "timestamp": time.time(),
            "overall_health_score": overall_health,
            "status_summary": dict(status_counts),
            "business_critical_violations": business_critical_violations,
            "total_slos": total_slos,
            "slo_results": {
                name: {
                    "sli_value": result.sli_value,
                    "target_percentage": result.target_percentage,
                    "achieved_percentage": result.achieved_percentage,
                    "error_budget_remaining": result.error_budget_remaining,
                    "status": result.status.value,
                    "time_window": result.time_window.value,
                    "is_business_critical": self.slo_definitions[name].is_business_critical
                }
                for name, result in all_results.items()
            }
        }

    def add_custom_sli(self, sli: SLIDefinition):
        """Add a custom SLI definition"""
        self.sli_definitions[sli.name] = sli

    def add_custom_slo(self, slo: SLODefinition):
        """Add a custom SLO definition"""
        self.slo_definitions[slo.name] = slo
        # Ensure SLI exists
        self.sli_definitions[slo.sli.name] = slo.sli

    def cleanup_old_metrics(self, max_age_hours: int = 24):
        """Clean up old metrics data"""
        cutoff_time = time.time() - (max_age_hours * 3600)

        for metric_name in self.raw_metrics:
            self.raw_metrics[metric_name] = deque(
                [m for m in self.raw_metrics[metric_name] if m['timestamp'] > cutoff_time],
                maxlen=5000
            )

# Global SLI/SLO monitor instance
sli_slo_monitor = SLIMonitor()

# Convenience functions
def record_api_metric(method: str, endpoint: str, status_code: str,
                     duration_seconds: float):
    """Record API metric for SLI monitoring"""
    # Record for latency SLI
    sli_slo_monitor.record_metric_value(
        "http_request_duration_seconds",
        duration_seconds,
        {
            "method": method,
            "endpoint": endpoint,
            "status_code": str(status_code)
        }
    )

    # Record for availability SLI
    sli_slo_monitor.record_metric_value(
        "http_requests_total",
        1,  # Count
        {
            "method": method,
            "endpoint": endpoint,
            "status_code": str(status_code)
        }
    )

def record_document_processing_metric(file_type: str, status: str,
                                    duration_seconds: Optional[float] = None):
    """Record document processing metric for SLI monitoring"""
    sli_slo_monitor.record_metric_value(
        "document_processing_total",
        1,  # Count
        {
            "file_type": file_type,
            "status": status
        }
    )

def record_websocket_metric(event_type: str, success: bool = True,
                          latency_ms: Optional[float] = None):
    """Record WebSocket metric for SLI monitoring"""
    sli_slo_monitor.record_metric_value(
        "websocket_connections_total",
        1,  # Count
        {
            "event_type": event_type,
            "status": "success" if success else "error"
        }
    )

def get_slo_status() -> Dict[str, Any]:
    """Get current SLO status"""
    return sli_slo_monitor.get_slo_dashboard()