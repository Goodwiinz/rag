"""
Tracing Database Models

Models for storing distributed tracing data including traces, spans, and events.
"""

import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, Text, JSON, Index, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from src.models.base import BaseModel


class SpanStatus(str, Enum):
    """Span status codes"""
    OK = "ok"
    ERROR = "error"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"
    INTERNAL_ERROR = "internal_error"
    TIMEOUT = "timeout"
    NOT_FOUND = "not_found"
    ALREADY_EXISTS = "already_exists"
    PERMISSION_DENIED = "permission_denied"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    FAILED_PRECONDITION = "failed_precondition"
    ABORTED = "aborted"
    OUT_OF_RANGE = "out_of_range"
    UNIMPLEMENTED = "unimplemented"
    DATA_LOSS = "data_loss"
    UNAUTHENTICATED = "unauthenticated"


class SpanKind(str, Enum):
    """Span kinds"""
    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"


class Trace(BaseModel):
    """Trace object containing multiple spans"""
    __tablename__ = "monitoring_traces"

    trace_id = Column(String(128), unique=True, nullable=False, index=True)
    root_span_id = Column(String(128), nullable=False)
    service_name = Column(String(255), nullable=False, index=True)
    operation_name = Column(String(255), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time = Column(DateTime(timezone=True))
    duration_ms = Column(Float, index=True)
    span_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    status = Column(String(50), default=SpanStatus.OK)
    tags = Column(JSONB, default=dict)
    resource_attributes = Column(JSONB, default=dict)

    # Sampling and processing info
    sampled = Column(Boolean, default=True)
    processing_status = Column(String(50), default="pending")  # pending, processed, failed

    # Relationships
    spans = relationship("Span", back_populates="trace", cascade="all, delete-orphan")
    errors = relationship("TraceError", back_populates="trace", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_traces_service_time', 'service_name', 'start_time'),
        Index('idx_traces_operation_time', 'operation_name', 'start_time'),
        Index('idx_traces_status_time', 'status', 'start_time'),
        Index('idx_traces_duration', 'duration_ms'),
    )


class Span(BaseModel):
    """Individual span within a trace"""
    __tablename__ = "monitoring_spans"

    trace_id = Column(String(128), ForeignKey("monitoring_traces.trace_id"), nullable=False, index=True)
    span_id = Column(String(128), unique=True, nullable=False, index=True)
    parent_span_id = Column(String(128))  # Can be null for root spans
    operation_name = Column(String(255), nullable=False)
    kind = Column(String(50), default=SpanKind.INTERNAL)
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time = Column(DateTime(timezone=True))
    duration_ms = Column(Float, index=True)
    status = Column(String(50), default=SpanStatus.OK)
    status_message = Column(Text)

    # Attributes and tags
    attributes = Column(JSONB, default=dict)
    tags = Column(JSONB, default=dict)
    resource_attributes = Column(JSONB, default=dict)

    # Service and component info
    service_name = Column(String(255), nullable=False, index=True)
    component = Column(String(255))
    library = Column(String(255))  # Instrumentation library

    # Processing info
    sampled = Column(Boolean, default=True)
    processing_status = Column(String(50), default="pending")

    # Relationships
    trace = relationship("Trace", back_populates="spans")
    events = relationship("SpanEvent", back_populates="span", cascade="all, delete-orphan")
    links = relationship("SpanLink", back_populates="span", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_spans_trace_operation', 'trace_id', 'operation_name'),
        Index('idx_spans_service_time', 'service_name', 'start_time'),
        Index('idx_spans_parent', 'parent_span_id'),
        Index('idx_spans_attributes', 'attributes', postgresql_using='gin'),
    )


class SpanEvent(BaseModel):
    """Events within a span"""
    __tablename__ = "monitoring_span_events"

    span_id = Column(String(128), ForeignKey("monitoring_spans.span_id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    attributes = Column(JSONB, default=dict)
    dropped_attributes_count = Column(Integer, default=0)

    # Relationships
    span = relationship("Span", back_populates="events")

    # Indexes
    __table_args__ = (
        Index('idx_span_events_span_time', 'span_id', 'timestamp'),
        Index('idx_span_events_name_time', 'name', 'timestamp'),
    )


class SpanLink(BaseModel):
    """Links to other spans (cross-trace correlation)"""
    __tablename__ = "monitoring_span_links"

    span_id = Column(String(128), ForeignKey("monitoring_spans.span_id"), nullable=False, index=True)
    linked_trace_id = Column(String(128), nullable=False)
    linked_span_id = Column(String(128), nullable=False)
    attributes = Column(JSONB, default=dict)
    dropped_attributes_count = Column(Integer, default=0)

    # Relationships
    span = relationship("Span", back_populates="links")

    # Indexes
    __table_args__ = (
        Index('idx_span_links_span_linked', 'span_id', 'linked_span_id'),
        Index('idx_span_links_trace', 'linked_trace_id'),
    )


class TraceError(BaseModel):
    """Errors captured in traces"""
    __tablename__ = "monitoring_trace_errors"

    trace_id = Column(String(128), ForeignKey("monitoring_traces.trace_id"), nullable=False, index=True)
    span_id = Column(String(128), nullable=False, index=True)
    error_type = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    stack_trace = Column(Text)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)

    # Error classification
    severity = Column(String(50), default="error")  # error, warning, fatal
    category = Column(String(100))  # system, application, network, timeout

    # Additional attributes
    attributes = Column(JSONB, default=dict)

    # Relationships
    trace = relationship("Trace", back_populates="errors")

    # Indexes
    __table_args__ = (
        Index('idx_trace_errors_type_time', 'error_type', 'timestamp'),
        Index('idx_trace_errors_severity_time', 'severity', 'timestamp'),
        Index('idx_trace_errors_span', 'span_id'),
    )