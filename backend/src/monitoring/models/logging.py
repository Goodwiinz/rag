"""
Logging Database Models

Models for storing structured log data and log patterns.
"""

import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, JSON, Index, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from ...models.base import BaseModel


class LogLevel(str, Enum):
    """Log levels"""
    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    FATAL = "FATAL"


class LogEntry(BaseModel):
    """Structured log entry"""
    __tablename__ = "monitoring_logs"

    # Basic log information
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    level = Column(String(10), nullable=False, index=True)
    message = Column(Text, nullable=False)
    logger_name = Column(String(255), index=True)
    thread_name = Column(String(255))

    # Source information
    service_name = Column(String(255), nullable=False, index=True)
    host_name = Column(String(255), index=True)
    process_id = Column(Integer)
    thread_id = Column(String(50))

    # Context and correlation
    correlation_id = Column(String(128), index=True)
    trace_id = Column(String(128), index=True)
    span_id = Column(String(128), index=True)
    user_id = Column(String(255), index=True)
    session_id = Column(String(255), index=True)
    request_id = Column(String(255), index=True)

    # Code location
    file_name = Column(String(255))
    line_number = Column(Integer)
    function_name = Column(String(255))
    class_name = Column(String(255))
    module = Column(String(255))

    # Exception information
    exception_class = Column(String(255))
    exception_message = Column(Text)
    stack_trace = Column(Text)

    # Structured data
    fields = Column(JSONB, default=dict)
    tags = Column(JSONB, default=list)
    labels = Column(JSONB, default=dict)

    # Processing flags
    processed = Column(Boolean, default=False)
    indexed = Column(Boolean, default=False)
    archived = Column(Boolean, default=False)

    # Quality and reliability
    quality_score = Column(Integer, default=100)  # 0-100
    is_sensitive = Column(Boolean, default=False)
    retention_days = Column(Integer, default=30)

    # Relationships
    patterns = relationship("LogPattern", secondary="monitoring_log_pattern_matches", back_populates="logs")

    # Indexes for efficient querying
    __table_args__ = (
        Index('idx_logs_timestamp_level', 'timestamp', 'level'),
        Index('idx_logs_service_timestamp', 'service_name', 'timestamp'),
        Index('idx_logs_correlation', 'correlation_id'),
        Index('idx_logs_trace_span', 'trace_id', 'span_id'),
        Index('idx_logs_user_session', 'user_id', 'session_id'),
        Index('idx_logs_exception', 'exception_class'),
        Index('idx_logs_fields', 'fields', postgresql_using='gin'),
        Index('idx_logs_tags', 'tags', postgresql_using='gin'),
    )


class LogPattern(BaseModel):
    """Detected log patterns"""
    __tablename__ = "monitoring_log_patterns"

    name = Column(String(255), nullable=False, index=True)
    pattern_type = Column(String(50), nullable=False)  # error_pattern, performance_pattern, business_pattern
    pattern_regex = Column(Text, nullable=False)
    description = Column(Text)

    # Pattern metadata
    severity = Column(String(20), default="info")
    category = Column(String(100))
    tags = Column(JSONB, default=list)
    is_active = Column(Boolean, default=True)

    # Pattern statistics
    match_count = Column(Integer, default=0)
    first_seen = Column(DateTime(timezone=True))
    last_seen = Column(DateTime(timezone=True))
    frequency_per_hour = Column(Float, default=0.0)

    # Pattern configuration
    sample_rate = Column(Float, default=1.0)
    alert_on_match = Column(Boolean, default=False)
    auto_tag = Column(JSONB, default=dict)

    # Relationships
    logs = relationship("LogEntry", secondary="monitoring_log_pattern_matches", back_populates="patterns")
    aggregations = relationship("LogAggregation", back_populates="pattern")

    # Indexes
    __table_args__ = (
        Index('idx_log_patterns_type_active', 'pattern_type', 'is_active'),
        Index('idx_log_patterns_frequency', 'frequency_per_hour'),
    )


# Association table for log-pattern many-to-many relationship
class LogPatternMatch(BaseModel):
    """Association table for log pattern matches"""
    __tablename__ = "monitoring_log_pattern_matches"

    log_id = Column(UUID(as_uuid=True), ForeignKey("monitoring_logs.id"), nullable=False)
    pattern_id = Column(UUID(as_uuid=True), ForeignKey("monitoring_log_patterns.id"), nullable=False)
    match_timestamp = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    confidence = Column(Float, default=1.0)  # 0.0 to 1.0
    match_details = Column(JSONB, default=dict)

    # Indexes
    __table_args__ = (
        Index('idx_log_pattern_matches_log', 'log_id'),
        Index('idx_log_pattern_matches_pattern', 'pattern_id'),
        Index('idx_log_pattern_matches_timestamp', 'match_timestamp'),
    )


class LogAggregation(BaseModel):
    """Aggregated log statistics"""
    __tablename__ = "monitoring_log_aggregations"

    # Aggregation dimensions
    time_bucket = Column(DateTime(timezone=True), nullable=False, index=True)
    bucket_size_minutes = Column(Integer, nullable=False)
    service_name = Column(String(255), index=True)
    level = Column(String(10), index=True)
    logger_name = Column(String(255), index=True)

    # Pattern aggregation
    pattern_id = Column(UUID(as_uuid=True), ForeignKey("monitoring_log_patterns.id"), index=True)

    # Aggregated metrics
    count = Column(Integer, default=0)
    unique_messages = Column(Integer, default=0)
    unique_users = Column(Integer, default=0)
    error_rate = Column(Float, default=0.0)

    # Performance metrics
    avg_response_time = Column(Float)
    max_response_time = Column(Float)
    min_response_time = Column(Float)

    # Top occurrences
    top_messages = Column(JSONB, default=list)
    top_exceptions = Column(JSONB, default=list)
    top_users = Column(JSONB, default=list)

    # Relationships
    pattern = relationship("LogPattern", back_populates="aggregations")

    # Indexes
    __table_args__ = (
        Index('idx_log_aggregations_time_service', 'time_bucket', 'service_name'),
        Index('idx_log_aggregations_time_level', 'time_bucket', 'level'),
        Index('idx_log_aggregations_pattern_time', 'pattern_id', 'time_bucket'),
    )