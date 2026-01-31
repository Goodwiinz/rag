"""
Extended analytics models for T3 real-time monitoring and dashboards
This module extends the existing quality.py models with T3-specific functionality
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from .base import Base


class MetricType(enum.Enum):
    """Extended metric types for T3 analytics (compatible with existing)"""

    RELEVANCY = "relevancy"
    PRECISION = "precision"
    RECALL = "recall"
    F1_SCORE = "f1_score"
    RESPONSE_TIME = "response_time"
    USER_SATISFACTION = "user_satisfaction"
    CLICK_THROUGH_RATE = "click_through_rate"
    RESULT_DIVERSITY = "result_diversity"
    COVERAGE = "coverage"
    FRESHNESS = "freshness"


class AlertSeverity(enum.Enum):
    """Alert severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Use the existing QualityMetric from quality.py
# from src.models.quality import QualityMetric


class QualityAlert(Base):
    """
    Alerts for quality threshold violations
    """

    __tablename__ = "quality_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Alert information
    metric_id = Column(
        UUID(as_uuid=True), ForeignKey("quality_metrics.id"), nullable=False
    )
    severity = Column(String(20), nullable=False)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)

    # Status tracking
    status = Column(
        String(20), default="active", nullable=False
    )  # active, acknowledged, resolved
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Context
    organization_id = Column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships - will be set up with the existing QualityMetric model
    # metric = relationship("QualityMetric", back_populates="alerts")
    organization = relationship("Organization")
    acknowledged_by_user = relationship("User", foreign_keys=[acknowledged_by])
    resolved_by_user = relationship("User", foreign_keys=[resolved_by])

    # Indexes
    __table_args__ = (
        Index("idx_quality_alerts_org_status", "organization_id", "status"),
        Index("idx_quality_alerts_severity", "severity", "created_at"),
    )


class MetricAggregation(Base):
    """
    Pre-aggregated metrics for analytics dashboard performance
    """

    __tablename__ = "metric_aggregations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Aggregation information
    metric_type = Column(String(50), nullable=False)
    aggregation_type = Column(
        String(20), nullable=False
    )  # hourly, daily, weekly, monthly
    aggregation_period_start = Column(DateTime, nullable=False)
    aggregation_period_end = Column(DateTime, nullable=False)

    # Aggregated values
    avg_value = Column(Float, nullable=False)
    min_value = Column(Float, nullable=False)
    max_value = Column(Float, nullable=False)
    count_values = Column(Integer, nullable=False)
    sum_values = Column(Float, nullable=False)
    std_deviation = Column(Float, nullable=True)

    # Context
    organization_id = Column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    search_type = Column(String(20), nullable=True)

    # Additional data
    percentiles = Column(JSONB, nullable=True)  # p50, p90, p95, p99

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")

    # Indexes for efficient querying
    __table_args__ = (
        Index(
            "idx_metric_agg_org_type_period",
            "organization_id",
            "metric_type",
            "aggregation_type",
        ),
        Index("idx_metric_agg_period_start", "aggregation_period_start"),
        Index("idx_metric_agg_search_type", "search_type"),
    )


class SearchSession(Base):
    """
    Search session tracking for user behavior analytics
    """

    __tablename__ = "search_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Session information
    session_id = Column(String(100), nullable=False, unique=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    organization_id = Column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )

    # Session tracking
    start_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    end_time = Column(DateTime, nullable=True)
    search_count = Column(Integer, default=0, nullable=False)
    total_response_time = Column(Float, default=0.0, nullable=False)  # in milliseconds

    # Context
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    referrer = Column(Text, nullable=True)

    # Session metrics
    avg_response_time = Column(Float, nullable=True)
    session_duration = Column(Float, nullable=True)  # in seconds
    bounce_rate = Column(Boolean, default=False)  # True if only one search

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="search_sessions")
    organization = relationship("Organization", back_populates="search_sessions")
    searches = relationship(
        "SearchEvent", back_populates="session", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("idx_search_sessions_org_user", "organization_id", "user_id"),
        Index("idx_search_sessions_start_time", "start_time"),
        Index("idx_search_sessions_session_id", "session_id"),
    )


class SearchEvent(Base):
    """
    Individual search events for detailed analytics
    """

    __tablename__ = "search_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Event identification
    session_id = Column(
        UUID(as_uuid=True), ForeignKey("search_sessions.id"), nullable=False
    )
    search_query_id = Column(UUID(as_uuid=True), nullable=True)

    # Search details
    query = Column(Text, nullable=False)
    search_type = Column(String(20), nullable=False)
    results_count = Column(Integer, nullable=False)
    response_time = Column(Float, nullable=False)  # in milliseconds

    # User interaction
    clicked_results = Column(Integer, default=0, nullable=False)
    clicked_result_ids = Column(JSONB, nullable=True)
    time_to_first_click = Column(Float, nullable=True)  # in seconds
    dwell_time = Column(Float, nullable=True)  # time spent on page

    # User feedback
    user_rating = Column(Integer, nullable=True)  # 1-5 stars
    feedback_text = Column(Text, nullable=True)
    is_bookmarked = Column(Boolean, default=False)

    # Context
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    organization_id = Column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )

    # Technical details
    page_number = Column(Integer, default=1, nullable=False)
    filters_applied = Column(JSONB, nullable=True)
    sort_order = Column(String(20), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    session = relationship("SearchSession", back_populates="searches")
    user = relationship("User", back_populates="search_events")
    organization = relationship("Organization", back_populates="search_events")

    # Indexes
    __table_args__ = (
        Index("idx_search_events_org_time", "organization_id", "created_at"),
        Index("idx_search_events_session", "session_id"),
        Index("idx_search_events_query", "query"),
        Index("idx_search_events_user", "user_id"),
    )


class SystemMetric(Base):
    """
    System performance metrics for monitoring
    """

    __tablename__ = "system_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Metric identification
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(Float, nullable=False)
    metric_unit = Column(String(20), nullable=True)

    # System component
    component_name = Column(String(100), nullable=False)  # database, search, api, etc.
    component_instance = Column(String(100), nullable=True)  # for scaling scenarios

    # Context
    organization_id = Column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True
    )

    # Additional data
    system_metadata = Column("metadata", JSONB, nullable=True)

    # Timestamps
    measured_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    organization = relationship("Organization")

    # Indexes
    __table_args__ = (
        Index("idx_system_metrics_component_time", "component_name", "measured_at"),
        Index("idx_system_metrics_name_time", "metric_name", "measured_at"),
        Index("idx_system_metrics_org_time", "organization_id", "measured_at"),
    )


class QualityThreshold(Base):
    """
    Configurable quality thresholds for alerting
    """

    __tablename__ = "quality_thresholds"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Threshold configuration
    metric_type = Column(String(50), nullable=False)
    threshold_min = Column(Float, nullable=True)
    threshold_max = Column(Float, nullable=True)
    threshold_target = Column(Float, nullable=True)

    # Alert configuration
    alert_severity = Column(String(20), default="medium", nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)
    alert_cooldown_minutes = Column(Integer, default=60, nullable=False)

    # Context
    organization_id = Column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True
    )
    search_type = Column(String(20), nullable=True)

    # Metadata
    description = Column(Text, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")
    creator = relationship("User")

    # Indexes
    __table_args__ = (
        Index("idx_quality_thresholds_org_type", "organization_id", "metric_type"),
        Index("idx_quality_thresholds_enabled", "is_enabled"),
    )
