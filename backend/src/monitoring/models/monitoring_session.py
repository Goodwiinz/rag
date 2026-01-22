"""
Monitoring Session Models

Models for tracking monitoring sessions and correlating metrics/traces.
"""

import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, JSON, Index, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from src.models.base import BaseModel


class SessionType(str, Enum):
    """Session types"""
    USER_SESSION = "user_session"
    API_SESSION = "api_session"
    BACKGROUND_JOB = "background_job"
    SYSTEM_PROCESS = "system_process"
    BATCH_OPERATION = "batch_operation"
    DEBUG_SESSION = "debug_session"


class SessionStatus(str, Enum):
    """Session status"""
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class MonitoringSession(BaseModel):
    """Monitoring session for correlating telemetry data"""
    __tablename__ = "monitoring_sessions"

    session_id = Column(String(128), unique=True, nullable=False, index=True)
    parent_session_id = Column(String(128), index=True)  # For nested sessions
    session_type = Column(String(50), nullable=False, index=True)
    status = Column(String(50), nullable=False, default=SessionStatus.ACTIVE, index=True)

    # Session timing
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time = Column(DateTime(timezone=True))
    duration_seconds = Column(Float, index=True)
    timeout_seconds = Column(Integer)

    # Session context
    user_id = Column(String(255), index=True)
    organization_id = Column(String(255), index=True)
    request_id = Column(String(255), index=True)
    correlation_id = Column(String(128), index=True)

    # Operation details
    operation_name = Column(String(255), nullable=False, index=True)
    operation_type = Column(String(100))
    component = Column(String(255))
    service_name = Column(String(255), index=True)

    # Session metadata
    client_info = Column(JSONB, default=dict)  # User agent, IP, etc.
    request_details = Column(JSONB, default=dict)  # Request parameters, headers, etc.
    environment = Column(JSONB, default=dict)  # Environment variables, etc.

    # Session statistics
    total_requests = Column(Integer, default=0)
    successful_requests = Column(Integer, default=0)
    failed_requests = Column(Integer, default=0)
    total_data_processed_bytes = Column(Integer, default=0)

    # Performance metrics
    avg_response_time_ms = Column(Float)
    min_response_time_ms = Column(Float)
    max_response_time_ms = Column(Float)
    p95_response_time_ms = Column(Float)
    p99_response_time_ms = Column(Float)

    # Resource usage
    peak_memory_usage_mb = Column(Float)
    peak_cpu_usage_percent = Column(Float)
    total_database_queries = Column(Integer, default=0)
    total_cache_hits = Column(Integer, default=0)
    total_cache_misses = Column(Integer, default=0)

    # Error tracking
    error_count = Column(Integer, default=0)
    error_rate_percent = Column(Float, default=0.0)
    critical_errors = Column(JSONB, default=list)

    # Session tags and labels
    tags = Column(JSONB, default=list)
    labels = Column(JSONB, default=dict)
    metadata = Column(JSONB, default=dict)

    # Relationships
    metrics = relationship("SessionMetric", back_populates="session", cascade="all, delete-orphan")
    traces = relationship("SessionTrace", back_populates="session", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_sessions_user_time', 'user_id', 'start_time'),
        Index('idx_sessions_operation_time', 'operation_name', 'start_time'),
        Index('idx_sessions_service_time', 'service_name', 'start_time'),
        Index('idx_sessions_status_time', 'status', 'start_time'),
        Index('idx_sessions_correlation', 'correlation_id'),
        Index('idx_sessions_parent', 'parent_session_id'),
    )


class SessionMetric(BaseModel):
    """Metrics associated with monitoring sessions"""
    __tablename__ = "monitoring_session_metrics"

    session_id = Column(String(128), ForeignKey("monitoring_sessions.session_id"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    metric_name = Column(String(255), nullable=False, index=True)
    metric_value = Column(Float, nullable=False)
    metric_unit = Column(String(50))
    metric_type = Column(String(50))  # counter, gauge, histogram

    # Metric context
    component = Column(String(255))
    labels = Column(JSONB, default=dict)
    tags = Column(JSONB, default=list)

    # Metric metadata
    source = Column(String(255))
    quality = Column(String(20), default="good")
    annotations = Column(JSONB, default=dict)

    # Relationships
    session = relationship("MonitoringSession", back_populates="metrics")

    # Indexes
    __table_args__ = (
        Index('idx_session_metrics_session_time', 'session_id', 'timestamp'),
        Index('idx_session_metrics_name_time', 'metric_name', 'timestamp'),
        Index('idx_session_metrics_labels', 'labels', postgresql_using='gin'),
    )


class SessionTrace(BaseModel):
    """Traces associated with monitoring sessions"""
    __tablename__ = "monitoring_session_traces"

    session_id = Column(String(128), ForeignKey("monitoring_sessions.session_id"), nullable=False, index=True)
    trace_id = Column(String(128), nullable=False, index=True)
    span_id = Column(String(128), nullable=False, index=True)
    parent_span_id = Column(String(128))

    # Trace details
    operation_name = Column(String(255), nullable=False)
    component = Column(String(255))
    service_name = Column(String(255))
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time = Column(DateTime(timezone=True))
    duration_ms = Column(Float, index=True)
    status = Column(String(50))

    # Trace context
    trace_type = Column(String(100))  # user_request, background_job, system_call
    critical_path = Column(Boolean, default=False)
    error_occurred = Column(Boolean, default=False)

    # Trace attributes
    attributes = Column(JSONB, default=dict)
    tags = Column(JSONB, default=list)
    links = Column(JSONB, default=list)

    # Performance analysis
    self_time_ms = Column(Float)  # Time excluding child spans
    child_count = Column(Integer, default=0)
    depth = Column(Integer, default=0)

    # Relationships
    session = relationship("MonitoringSession", back_populates="traces")

    # Indexes
    __table_args__ = (
        Index('idx_session_traces_session_time', 'session_id', 'start_time'),
        Index('idx_session_traces_trace_span', 'trace_id', 'span_id'),
        Index('idx_session_traces_operation_time', 'operation_name', 'start_time'),
        Index('idx_session_traces_status_time', 'status', 'start_time'),
        Index('idx_session_traces_critical', 'critical_path'),
    )