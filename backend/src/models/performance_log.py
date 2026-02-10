"""
Performance log model for T3 monitoring
Tracks system performance metrics and health indicators
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from .base import GUID, BaseModel


class MetricCategory(enum.Enum):
    """Performance metric categories"""

    SYSTEM = "system"
    DATABASE = "database"
    API = "api"
    SEARCH = "search"
    CACHE = "cache"
    MEMORY = "memory"
    NETWORK = "network"
    STORAGE = "storage"
    EXTERNAL_SERVICE = "external_service"


class PerformanceLevel(enum.Enum):
    """Performance level indicators"""

    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


class PerformanceLog(BaseModel):
    """
    System performance monitoring and logging
    """

    __tablename__ = "performance_logs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # Metric classification
    metric_name = Column(String(255), nullable=False, index=True)
    metric_category = Column(Enum(MetricCategory), nullable=False, index=True)
    performance_level = Column(Enum(PerformanceLevel), nullable=False, index=True)

    # Organization context (for multi-tenant monitoring)
    organization_id = Column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True
    )

    # Metric values
    value = Column(Float, nullable=False)
    unit = Column(String(50), nullable=True)  # ms, %, MB, GB, requests/sec, etc.
    baseline_value = Column(Float, nullable=True)  # Expected/normal value
    threshold_warning = Column(Float, nullable=True)  # Warning threshold
    threshold_critical = Column(Float, nullable=True)  # Critical threshold

    # System resource metrics
    cpu_usage_percent = Column(Float, nullable=True)
    memory_usage_mb = Column(Float, nullable=True)
    memory_usage_percent = Column(Float, nullable=True)
    disk_usage_gb = Column(Float, nullable=True)
    disk_usage_percent = Column(Float, nullable=True)
    network_io_mb = Column(Float, nullable=True)

    # Application metrics
    response_time_ms = Column(Integer, nullable=True)
    request_count = Column(Integer, nullable=True)
    error_count = Column(Integer, nullable=True)
    active_connections = Column(Integer, nullable=True)
    queue_size = Column(Integer, nullable=True)

    # Database metrics
    db_connections = Column(Integer, nullable=True)
    db_query_time_ms = Column(Integer, nullable=True)
    db_slow_queries = Column(Integer, nullable=True)
    db_cache_hit_rate = Column(Float, nullable=True)

    # Search-specific metrics
    search_query_time_ms = Column(Integer, nullable=True)
    index_size_mb = Column(Float, nullable=True)
    search_results_count = Column(Integer, nullable=True)

    # Context information
    component = Column(
        String(100), nullable=True, index=True
    )  # API endpoint, service name, etc.
    environment = Column(String(50), nullable=True)  # prod, staging, dev
    version = Column(String(50), nullable=True)  # Application version
    node_id = Column(String(100), nullable=True)  # Server/container ID

    # Additional metadata
    tags = Column(JSONB, nullable=True)  # Flexible tagging system
    event_metadata = Column(
        JSONB, nullable=True
    )  # Additional context data (renamed from metadata to avoid SQLAlchemy conflict)
    alert_triggered = Column(Boolean, default=False, nullable=False, index=True)

    # Temporal data
    timestamp = Column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True
    )
    date_hour = Column(String(13), nullable=False, index=True)  # YYYY-MM-DDTHH
    date_day = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD

    # Processing metadata
    created_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    batch_id = Column(String(100), nullable=True, index=True)

    # Relationships
    organization = relationship("Organization", back_populates="performance_logs")

    # Performance indexes
    __table_args__ = (
        Index("idx_performance_logs_metric_time", "metric_name", "timestamp"),
        Index("idx_performance_logs_category_time", "metric_category", "timestamp"),
        Index("idx_performance_logs_org_time", "organization_id", "timestamp"),
        Index("idx_performance_logs_level_time", "performance_level", "timestamp"),
        Index("idx_performance_logs_component_time", "component", "timestamp"),
        Index("idx_performance_logs_date_hour", "date_hour"),
        Index("idx_performance_logs_date_day", "date_day"),
        Index("idx_performance_logs_alert", "alert_triggered", "timestamp"),
        Index(
            "idx_performance_logs_composite",
            "metric_category",
            "organization_id",
            "date_day",
        ),
    )

    def __repr__(self):
        return f"<PerformanceLog(id={self.id}, metric={self.metric_name}, value={self.value}, level={self.performance_level.value})>"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Auto-calculate date fields from timestamp
        if self.timestamp:
            self.date_day = self.timestamp.strftime("%Y-%m-%d")
            self.date_hour = self.timestamp.strftime("%Y-%m-%dT%H")
        # Auto-calculate performance level if not set
        if not self.performance_level:
            self.calculate_performance_level()

    def calculate_performance_level(self):
        """Calculate performance level based on thresholds"""
        if not self.value:
            self.performance_level = PerformanceLevel.FAIR
            return self.performance_level

        # For metrics where lower is better (response times, error rates)
        if self.metric_name in [
            "response_time",
            "error_rate",
            "memory_usage",
            "cpu_usage",
        ]:
            if self.threshold_critical and self.value >= self.threshold_critical:
                self.performance_level = PerformanceLevel.CRITICAL
            elif self.threshold_warning and self.value >= self.threshold_warning:
                self.performance_level = PerformanceLevel.POOR
            elif self.baseline_value and self.value >= self.baseline_value * 2:
                self.performance_level = PerformanceLevel.FAIR
            elif self.baseline_value and self.value >= self.baseline_value * 1.5:
                self.performance_level = PerformanceLevel.GOOD
            else:
                self.performance_level = PerformanceLevel.EXCELLENT

        # For metrics where higher is better (cache hit rate, success rate)
        else:
            if self.threshold_critical and self.value <= self.threshold_critical:
                self.performance_level = PerformanceLevel.CRITICAL
            elif self.threshold_warning and self.value <= self.threshold_warning:
                self.performance_level = PerformanceLevel.POOR
            elif self.baseline_value and self.value <= self.baseline_value * 0.5:
                self.performance_level = PerformanceLevel.FAIR
            elif self.baseline_value and self.value <= self.baseline_value * 0.8:
                self.performance_level = PerformanceLevel.GOOD
            else:
                self.performance_level = PerformanceLevel.EXCELLENT

        return self.performance_level

    @classmethod
    def create_system_metric(cls, metric_name, value, unit=None, **kwargs):
        """Create a system-level performance metric"""
        return cls(
            metric_name=metric_name,
            metric_category=MetricCategory.SYSTEM,
            value=value,
            unit=unit,
            component=kwargs.get("component", "system"),
            environment=kwargs.get("environment", "production"),
            **kwargs,
        )

    @classmethod
    def create_api_metric(cls, endpoint, response_time_ms, status_code, **kwargs):
        """Create an API performance metric"""
        # Determine performance level based on response time
        if response_time_ms >= 5000:
            level = PerformanceLevel.CRITICAL
        elif response_time_ms >= 2000:
            level = PerformanceLevel.POOR
        elif response_time_ms >= 1000:
            level = PerformanceLevel.FAIR
        elif response_time_ms >= 500:
            level = PerformanceLevel.GOOD
        else:
            level = PerformanceLevel.EXCELLENT

        return cls(
            metric_name="api_response_time",
            metric_category=MetricCategory.API,
            performance_level=level,
            value=response_time_ms,
            unit="ms",
            threshold_warning=1000,
            threshold_critical=5000,
            component=endpoint,
            metadata={
                "status_code": status_code,
                "method": kwargs.get("method", "GET"),
                "endpoint": endpoint,
            },
            **kwargs,
        )

    @classmethod
    def create_database_metric(cls, metric_name, value, **kwargs):
        """Create a database performance metric"""
        return cls(
            metric_name=metric_name,
            metric_category=MetricCategory.DATABASE,
            value=value,
            component=kwargs.get("component", "database"),
            metadata={
                "query_type": kwargs.get("query_type", "unknown"),
                "table_name": kwargs.get("table_name"),
            },
            **kwargs,
        )

    @classmethod
    def create_search_metric(cls, query_time_ms, results_count, **kwargs):
        """Create a search performance metric"""
        if query_time_ms >= 5000:
            level = PerformanceLevel.CRITICAL
        elif query_time_ms >= 2000:
            level = PerformanceLevel.POOR
        elif query_time_ms >= 1000:
            level = PerformanceLevel.FAIR
        elif query_time_ms >= 500:
            level = PerformanceLevel.GOOD
        else:
            level = PerformanceLevel.EXCELLENT

        return cls(
            metric_name="search_response_time",
            metric_category=MetricCategory.SEARCH,
            performance_level=level,
            value=query_time_ms,
            unit="ms",
            threshold_warning=1000,
            threshold_critical=5000,
            search_query_time_ms=query_time_ms,
            search_results_count=results_count,
            component="search_engine",
            metadata={
                "query_type": kwargs.get("query_type", "hybrid"),
                "index_used": kwargs.get("index_used", "default"),
            },
            **kwargs,
        )

    def should_trigger_alert(self):
        """Check if this metric should trigger an alert"""
        if self.alert_triggered:
            return False

        if self.performance_level in [PerformanceLevel.CRITICAL, PerformanceLevel.POOR]:
            return True

        if self.threshold_critical and self.value >= self.threshold_critical:
            return True

        if self.threshold_warning and self.value >= self.threshold_warning:
            # Only trigger warning if it's significantly worse than baseline
            if self.baseline_value and self.value >= self.baseline_value * 2:
                return True

        return False

    def trigger_alert(self):
        """Mark this log as triggering an alert"""
        self.alert_triggered = True

    def get_trend_data(self, days=7):
        """Get trend data for this metric (placeholder for query logic)"""
        # This would typically query historical data
        # For now, return a structure that would be populated by a service
        return {
            "metric_name": self.metric_name,
            "current_value": self.value,
            "performance_level": self.performance_level.value,
            "trend_direction": "stable",  # Would be calculated
            "trend_percentage": 0.0,  # Would be calculated
            "days_analyzed": days,
        }

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": str(self.id),
            "metric_name": self.metric_name,
            "metric_category": self.metric_category.value,
            "performance_level": self.performance_level.value,
            "value": self.value,
            "unit": self.unit,
            "baseline_value": self.baseline_value,
            "threshold_warning": self.threshold_warning,
            "threshold_critical": self.threshold_critical,
            "component": self.component,
            "organization_id": str(self.organization_id)
            if self.organization_id
            else None,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "cpu_usage_percent": self.cpu_usage_percent,
            "memory_usage_percent": self.memory_usage_percent,
            "response_time_ms": self.response_time_ms,
            "alert_triggered": self.alert_triggered,
            "metadata": self.event_metadata,  # Map to metadata for API compatibility
        }

    @staticmethod
    def get_aggregation_buckets(bucket_size: str = "hour") -> str:
        """Get SQL date truncation for aggregation"""
        if bucket_size == "minute":
            return "date_trunc('minute', timestamp)"
        elif bucket_size == "hour":
            return "date_trunc('hour', timestamp)"
        elif bucket_size == "day":
            return "date_trunc('day', timestamp)"
        elif bucket_size == "week":
            return "date_trunc('week', timestamp)"
        elif bucket_size == "month":
            return "date_trunc('month', timestamp)"
        else:
            return "date_trunc('hour', timestamp)"
