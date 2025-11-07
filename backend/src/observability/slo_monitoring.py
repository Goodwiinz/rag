"""
SLI/SLO monitoring and alerting system for the Multimodal RAG System.
"""

import time
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import statistics

from .config import config
from .metrics import (
    SLI_RESPONSE_TIME, SLI_ERROR_RATE, SLI_AVAILABILITY,
    record_histogram, increment_counter, increment_updown_counter
)
from .logging import get_logger

logger = get_logger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class SLOStatus(Enum):
    """SLO compliance status."""
    COMPLIANT = "compliant"
    WARNING = "warning"
    VIOLATION = "violation"
    CRITICAL = "critical"


@dataclass
class SLITarget:
    """Service Level Indicator target configuration."""
    name: str
    description: str
    unit: str
    target_value: float
    warning_threshold: Optional[float] = None
    critical_threshold: Optional[float] = None


@dataclass
class SLODefinition:
    """Service Level Objective definition."""
    name: str
    description: str
    sli_targets: List[SLITarget]
    time_window_minutes: int = 60
    evaluation_interval_minutes: int = 5
    alerting_enabled: bool = True
    status: SLOStatus = SLOStatus.COMPLIANT
    last_evaluation: Optional[datetime] = None
    current_values: Dict[str, float] = field(default_factory=dict)


class SLAMonitor:
    """Service Level Agreement monitoring system."""

    def __init__(self):
        self.slos: Dict[str, SLODefinition] = {}
        self.sli_data: Dict[str, List[Tuple[datetime, float]]] = {}
        self.alert_callbacks: List[callable] = []
        self._initialize_default_slos()

    def _initialize_default_slos(self):
        """Initialize default SLOs based on configuration."""

        # Response Time SLO
        response_time_slo = SLODefinition(
            name="response_time_p95",
            description="95th percentile response time",
            sli_targets=[
                SLITarget(
                    name="p95_response_time",
                    description="95th percentile response time",
                    unit="ms",
                    target_value=config.slo_response_time_p95_target,
                    warning_threshold=config.slo_response_time_p95_target * 0.8,
                    critical_threshold=config.slo_response_time_p95_target * 1.2
                ),
                SLITarget(
                    name="p99_response_time",
                    description="99th percentile response time",
                    unit="ms",
                    target_value=config.slo_response_time_p99_target,
                    warning_threshold=config.slo_response_time_p99_target * 0.8,
                    critical_threshold=config.slo_response_time_p99_target * 1.2
                )
            ],
            time_window_minutes=60,
            evaluation_interval_minutes=5
        )
        self.slos["response_time"] = response_time_slo

        # Error Rate SLO
        error_rate_slo = SLODefinition(
            name="error_rate",
            description="System error rate",
            sli_targets=[
                SLITarget(
                    name="error_rate_percentage",
                    description="Percentage of failed requests",
                    unit="percent",
                    target_value=config.slo_error_rate_target * 100,
                    warning_threshold=config.slo_error_rate_target * 100 * 0.5,
                    critical_threshold=config.slo_error_rate_target * 100 * 2
                )
            ],
            time_window_minutes=60,
            evaluation_interval_minutes=5
        )
        self.slos["error_rate"] = error_rate_slo

        # Availability SLO
        availability_slo = SLODefinition(
            name="availability",
            description="Service availability",
            sli_targets=[
                SLITarget(
                    name="availability_percentage",
                    description="Service uptime percentage",
                    unit="percent",
                    target_value=config.slo_availability_target * 100,
                    warning_threshold=config.slo_availability_target * 100 * 0.99,
                    critical_threshold=config.slo_availability_target * 100 * 0.95
                )
            ],
            time_window_minutes=60,
            evaluation_interval_minutes=5
        )
        self.slos["availability"] = availability_slo

        # RAG Quality SLOs
        rag_quality_slo = SLODefinition(
            name="rag_quality",
            description="RAG response quality metrics",
            sli_targets=[
                SLITarget(
                    name="answer_relevancy_score",
                    description="RAG answer relevancy score",
                    unit="score",
                    target_value=0.7,
                    warning_threshold=0.6,
                    critical_threshold=0.5
                ),
                SLITarget(
                    name="faithfulness_score",
                    description="RAG faithfulness score",
                    unit="score",
                    target_value=0.9,
                    warning_threshold=0.8,
                    critical_threshold=0.7
                ),
                SLITarget(
                    name="contextual_relevancy_score",
                    description="RAG contextual relevancy score",
                    unit="score",
                    target_value=0.7,
                    warning_threshold=0.6,
                    critical_threshold=0.5
                )
            ],
            time_window_minutes=60,
            evaluation_interval_minutes=5
        )
        self.slos["rag_quality"] = rag_quality_slo

        # Document Processing SLO
        doc_processing_slo = SLODefinition(
            name="document_processing",
            description="Document processing performance",
            sli_targets=[
                SLITarget(
                    name="processing_time_p95",
                    description="95th percentile document processing time",
                    unit="seconds",
                    target_value=300,  # 5 minutes
                    warning_threshold=240,  # 4 minutes
                    critical_threshold=600  # 10 minutes
                )
            ],
            time_window_minutes=60,
            evaluation_interval_minutes=5
        )
        self.slos["document_processing"] = doc_processing_slo

    def record_sli(
        self,
        slo_name: str,
        sli_name: str,
        value: float,
        timestamp: Optional[datetime] = None
    ):
        """Record an SLI measurement."""
        if timestamp is None:
            timestamp = datetime.utcnow()

        key = f"{slo_name}.{sli_name}"
        if key not in self.sli_data:
            self.sli_data[key] = []

        self.sli_data[key].append((timestamp, value))

        # Clean old data beyond retention period
        cutoff_time = timestamp - timedelta(minutes=1440)  # Keep 24 hours
        self.sli_data[key] = [
            (t, v) for t, v in self.sli_data[key]
            if t > cutoff_time
        ]

        # Record to metrics system
        record_histogram(f"sli_{sli_name}", value, {"slo": slo_name})

    def evaluate_slo(self, slo_name: str) -> SLOStatus:
        """Evaluate SLO compliance."""
        if slo_name not in self.slos:
            logger.warning(f"SLO not found: {slo_name}")
            return SLOStatus.VIOLATION

        slo = self.slos[slo_name]
        current_time = datetime.utcnow()
        evaluation_window = timedelta(minutes=slo.time_window_minutes)

        overall_status = SLOStatus.COMPLIANT
        sli_values = {}

        for target in slo.sli_targets:
            key = f"{slo_name}.{target.name}"
            if key not in self.sli_data:
                logger.warning(f"No data for SLI: {key}")
                sli_values[target.name] = 0.0
                overall_status = SLOStatus.VIOLATION
                continue

            # Filter data within evaluation window
            recent_data = [
                value for timestamp, value in self.sli_data[key]
                if current_time - timestamp <= evaluation_window
            ]

            if not recent_data:
                logger.warning(f"No recent data for SLI: {key}")
                sli_values[target.name] = 0.0
                overall_status = SLOStatus.VIOLATION
                continue

            # Calculate percentile-based metrics
            if "response_time" in target.name:
                current_value = statistics.quantiles(recent_data, n=20)[18]  # 95th percentile
            elif "processing_time" in target.name:
                current_value = statistics.quantiles(recent_data, n=20)[18]  # 95th percentile
            else:
                current_value = statistics.mean(recent_data)

            sli_values[target.name] = current_value

            # Determine SLI status
            sli_status = self._evaluate_sli_status(current_value, target)
            if sli_status.value > overall_status.value:
                overall_status = sli_status

        # Update SLO status
        old_status = slo.status
        slo.status = overall_status
        slo.last_evaluation = current_time
        slo.current_values = sli_values

        # Trigger alerts if status changed
        if old_status != overall_status and slo.alerting_enabled:
            self._trigger_slo_alert(slo_name, slo, old_status, overall_status)

        return overall_status

    def _evaluate_sli_status(self, current_value: float, target: SLITarget) -> SLOStatus:
        """Evaluate individual SLI status against targets."""
        if target.critical_threshold and current_value > target.critical_threshold:
            return SLOStatus.CRITICAL
        elif target.warning_threshold and current_value > target.warning_threshold:
            return SLOStatus.WARNING
        elif current_value > target.target_value:
            return SLOStatus.VIOLATION
        else:
            return SLOStatus.COMPLIANT

    def _trigger_slo_alert(
        self,
        slo_name: str,
        slo: SLODefinition,
        old_status: SLOStatus,
        new_status: SLOStatus
    ):
        """Trigger SLO alert."""
        alert_data = {
            "slo_name": slo_name,
            "slo_description": slo.description,
            "old_status": old_status.value,
            "new_status": new_status.value,
            "current_values": slo.current_values,
            "timestamp": datetime.utcnow().isoformat(),
            "severity": self._map_status_to_severity(new_status).value
        }

        logger.warning(
            f"SLO Status Change: {slo_name} from {old_status.value} to {new_status.value}",
            **alert_data
        )

        # Call alert callbacks
        for callback in self.alert_callbacks:
            try:
                callback(alert_data)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")

    def _map_status_to_severity(self, status: SLOStatus) -> AlertSeverity:
        """Map SLO status to alert severity."""
        mapping = {
            SLOStatus.COMPLIANT: AlertSeverity.INFO,
            SLOStatus.WARNING: AlertSeverity.MEDIUM,
            SLOStatus.VIOLATION: AlertSeverity.HIGH,
            SLOStatus.CRITICAL: AlertSeverity.CRITICAL
        }
        return mapping.get(status, AlertSeverity.LOW)

    def get_slo_status(self, slo_name: str) -> Optional[SLODefinition]:
        """Get current SLO status."""
        return self.slos.get(slo_name)

    def get_all_slo_status(self) -> Dict[str, SLODefinition]:
        """Get status of all SLOs."""
        return self.slos.copy()

    def add_alert_callback(self, callback: callable):
        """Add alert callback function."""
        self.alert_callbacks.append(callback)

    def record_request_metrics(
        self,
        operation: str,
        duration: float,
        success: bool,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Record request metrics for SLO monitoring."""
        # Record response time
        self.record_sli("response_time", "response_time", duration)

        # Record error rate
        self.record_sli("error_rate", "error_rate", 0.0 if success else 1.0)

        # Record availability
        self.record_sli("availability", "availability", 1.0 if success else 0.0)

    def record_rag_quality_metrics(
        self,
        answer_relevancy: float,
        faithfulness: float,
        contextual_relevancy: float
    ):
        """Record RAG quality metrics."""
        self.record_sli("rag_quality", "answer_relevancy_score", answer_relevancy)
        self.record_sli("rag_quality", "faithfulness_score", faithfulness)
        self.record_sli("rag_quality", "contextual_relevancy_score", contextual_relevancy)

    def record_document_processing_metrics(
        self,
        processing_time: float,
        file_type: str,
        success: bool
    ):
        """Record document processing metrics."""
        self.record_sli("document_processing", "processing_time_p95", processing_time)

    def evaluate_all_slos(self) -> Dict[str, SLOStatus]:
        """Evaluate all defined SLOs."""
        results = {}
        for slo_name in self.slos:
            results[slo_name] = self.evaluate_slo(slo_name)
        return results

    def get_sli_summary(
        self,
        slo_name: str,
        sli_name: str,
        time_window_minutes: int = 60
    ) -> Dict[str, Any]:
        """Get summary statistics for an SLI."""
        key = f"{slo_name}.{sli_name}"
        if key not in self.sli_data:
            return {}

        current_time = datetime.utcnow()
        cutoff_time = current_time - timedelta(minutes=time_window_minutes)
        recent_data = [
            value for timestamp, value in self.sli_data[key]
            if timestamp > cutoff_time
        ]

        if not recent_data:
            return {}

        return {
            "count": len(recent_data),
            "mean": statistics.mean(recent_data),
            "median": statistics.median(recent_data),
            "min": min(recent_data),
            "max": max(recent_data),
            "p95": statistics.quantiles(recent_data, n=20)[18] if len(recent_data) >= 20 else max(recent_data),
            "p99": statistics.quantiles(recent_data, n=100)[98] if len(recent_data) >= 100 else max(recent_data),
            "std_dev": statistics.stdev(recent_data) if len(recent_data) > 1 else 0.0
        }


# Global SLO monitor instance
_slo_monitor = None


def get_slo_monitor() -> SLAMonitor:
    """Get the global SLO monitor instance."""
    global _slo_monitor
    if _slo_monitor is None:
        _slo_monitor = SLAMonitor()
    return _slo_monitor


def record_slo_metrics(
    operation: str,
    duration: float,
    success: bool = True,
    metadata: Optional[Dict[str, Any]] = None
):
    """Record SLO metrics for an operation."""
    monitor = get_slo_monitor()
    monitor.record_request_metrics(operation, duration, success, metadata)


def evaluate_slos():
    """Evaluate all SLOs (called periodically)."""
    monitor = get_slo_monitor()
    return monitor.evaluate_all_slos()