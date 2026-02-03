"""
Metrics Database Models

Models for storing metrics, metric definitions, and time series data.
"""

import uuid
from datetime import datetime
from enum import Enum

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

from src.models.base import BaseModel


class MetricType(str, Enum):
    """Metric types"""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class MetricUnit(str, Enum):
    """Metric units"""

    COUNT = "count"
    PERCENTAGE = "percentage"
    MILLISECONDS = "milliseconds"
    SECONDS = "seconds"
    BYTES = "bytes"
    REQUESTS_PER_SECOND = "requests_per_second"
    CUSTOM = "custom"


class MetricDefinition(BaseModel):
    """Definition of a metric"""

    __tablename__ = "monitoring_metric_definitions"

    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text)
    metric_type = Column(
        String(50), nullable=False
    )  # counter, gauge, histogram, summary
    unit = Column(String(50), nullable=False)
    tags = Column(JSONB, default=dict)
    labels_schema = Column(JSONB, default=dict)  # Schema for label validation
    aggregation_rules = Column(JSONB, default=dict)
    retention_days = Column(Integer, default=30)
    is_active = Column(Boolean, default=True)
    category = Column(String(100))  # system, application, business, custom

    # Relationships
    metrics = relationship(
        "Metric", back_populates="definition", cascade="all, delete-orphan"
    )
    aggregations = relationship("MetricAggregation", back_populates="definition")


class Metric(BaseModel):
    """Individual metric data point"""

    __tablename__ = "monitoring_metrics"

    definition_id = Column(
        UUID(as_uuid=True),
        ForeignKey("monitoring_metric_definitions.id"),
        nullable=False,
    )
    value = Column(Float, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    labels = Column(JSONB, default=dict)  # Additional labels/dimensions
    source = Column(String(100))  # Source service/component
    instance = Column(String(255))  # Instance identifier
    metadata = Column(JSONB, default=dict)

    # Relationships
    definition = relationship("MetricDefinition", back_populates="metrics")

    # Indexes for efficient querying
    __table_args__ = (
        Index("idx_metrics_definition_timestamp", "definition_id", "timestamp"),
        Index("idx_metrics_source_timestamp", "source", "timestamp"),
        Index("idx_metrics_labels", "labels", postgresql_using="gin"),
    )


class MetricAggregation(BaseModel):
    """Aggregated metrics data"""

    __tablename__ = "monitoring_metric_aggregations"

    definition_id = Column(
        UUID(as_uuid=True),
        ForeignKey("monitoring_metric_definitions.id"),
        nullable=False,
    )
    aggregation_type = Column(
        String(50), nullable=False
    )  # sum, avg, min, max, count, p50, p95, p99
    time_bucket = Column(DateTime(timezone=True), nullable=False, index=True)
    bucket_size_minutes = Column(Integer, nullable=False)
    value = Column(Float, nullable=False)
    sample_count = Column(Integer, default=0)
    labels = Column(JSONB, default=dict)

    # Relationships
    definition = relationship("MetricDefinition", back_populates="aggregations")

    # Indexes
    __table_args__ = (
        Index(
            "idx_aggregations_definition_bucket",
            "definition_id",
            "time_bucket",
            "aggregation_type",
        ),
        Index("idx_aggregations_bucket_type", "time_bucket", "aggregation_type"),
    )


class TimeSeriesData(BaseModel):
    """Time series data for complex metrics"""

    __tablename__ = "monitoring_time_series"

    metric_name = Column(String(255), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    value = Column(Float, nullable=False)
    labels = Column(JSONB, default=dict)
    source = Column(String(100))
    quality = Column(String(20), default="good")  # good, bad, uncertain
    annotations = Column(JSONB, default=dict)

    # Indexes for time series queries
    __table_args__ = (
        Index("idx_timeseries_metric_timestamp", "metric_name", "timestamp"),
        Index("idx_timeseries_source_timestamp", "source", "timestamp"),
        Index("idx_timeseries_labels", "labels", postgresql_using="gin"),
    )
