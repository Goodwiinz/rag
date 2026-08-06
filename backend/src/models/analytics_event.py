"""
Analytics event model for T3 monitoring
Generic event tracking system for all analytics data
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


class EventType(enum.Enum):
    """Analytics event types"""

    SEARCH_QUERY = "search_query"
    DOCUMENT_VIEW = "document_view"
    DOCUMENT_DOWNLOAD = "document_download"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    CLICK_EVENT = "click_event"
    PAGE_VIEW = "page_view"
    ERROR_OCCURRED = "error_occurred"
    PERFORMANCE_METRIC = "performance_metric"
    QUALITY_METRIC = "quality_metric"
    RECOMMENDATION_SHOWN = "recommendation_shown"
    RECOMMENDATION_CLICKED = "recommendation_clicked"
    FEEDBACK_SUBMITTED = "feedback_submitted"
    FILTER_APPLIED = "filter_applied"
    SORT_CHANGED = "sort_changed"


class EventSeverity(enum.Enum):
    """Event severity levels"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AnalyticsEvent(BaseModel):
    """
    Generic analytics event for tracking all user and system activities
    """

    __tablename__ = "analytics_events"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # Event classification
    event_type = Column(Enum(EventType), nullable=False, index=True)
    event_category = Column(
        String(100), nullable=True, index=True
    )  # Additional categorization
    severity = Column(Enum(EventSeverity), default=EventSeverity.INFO, nullable=False)

    # User and session context
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    session_id = Column(String(255), nullable=True, index=True)
    organization_id = Column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )

    # Event data
    event_name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    event_data = Column(JSONB, nullable=True)  # Flexible event-specific data

    # Technical details
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    referrer = Column(Text, nullable=True)
    page_url = Column(Text, nullable=True)
    api_endpoint = Column(String(500), nullable=True)

    # Performance metrics
    response_time_ms = Column(Integer, nullable=True)
    memory_usage_mb = Column(Float, nullable=True)
    cpu_usage_percent = Column(Float, nullable=True)

    # Business metrics
    value = Column(Float, nullable=True)  # Numeric value for metrics
    unit = Column(String(50), nullable=True)  # Unit of measurement (ms, %, count, etc.)
    tags = Column(JSONB, nullable=True)  # Tag-based categorization

    # Temporal data
    event_timestamp = Column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True
    )
    date_hour = Column(
        String(13), nullable=False, index=True
    )  # YYYY-MM-DDTHH for time-series queries
    date_day = Column(
        String(10), nullable=False, index=True
    )  # YYYY-MM-DD for daily aggregation

    # Metadata
    created_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    processed = Column(
        Boolean, default=False, nullable=False, index=True
    )  # For async processing
    batch_id = Column(String(100), nullable=True, index=True)  # For batch processing

    # Relationships
    user = relationship("User", back_populates="analytics_events")
    organization = relationship("Organization", back_populates="analytics_events")

    # Indexes for performance
    __table_args__ = (
        Index("idx_analytics_events_type_org", "event_type", "organization_id"),
        Index("idx_analytics_events_user_time", "user_id", "event_timestamp"),
        Index("idx_analytics_events_org_time", "organization_id", "event_timestamp"),
        Index("idx_analytics_events_session", "session_id", "event_timestamp"),
        Index("idx_analytics_events_severity", "severity", "event_timestamp"),
        Index("idx_analytics_events_date_hour", "date_hour"),
        Index("idx_analytics_events_date_day", "date_day"),
        Index("idx_analytics_events_processed", "processed"),
        Index("idx_analytics_events_batch", "batch_id"),
        Index(
            "idx_analytics_events_composite",
            "organization_id",
            "event_type",
            "date_day",
        ),
    )

    def __repr__(self):
        return f"<AnalyticsEvent(id={self.id}, type={self.event_type.value}, user_id={self.user_id}, timestamp={self.event_timestamp})>"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Auto-calculate date fields from timestamp
        if self.event_timestamp:
            self.date_day = self.event_timestamp.strftime("%Y-%m-%d")
            self.date_hour = self.event_timestamp.strftime("%Y-%m-%dT%H")

    @classmethod
    def create_search_event(
        cls,
        user_id,
        organization_id,
        session_id,
        query,
        results_count,
        response_time_ms,
        **kwargs,
    ):
        """Create a search query event"""
        return cls(
            event_type=EventType.SEARCH_QUERY,
            event_category="search",
            user_id=user_id,
            organization_id=organization_id,
            session_id=session_id,
            event_name="search_query",
            description=f"Search query: {query}",
            event_data={
                "query": query,
                "results_count": results_count,
                "filters_applied": kwargs.get("filters_applied", {}),
                "sort_order": kwargs.get("sort_order", "relevance"),
            },
            response_time_ms=response_time_ms,
            value=results_count,
            unit="count",
            **kwargs,
        )

    @classmethod
    def create_document_view_event(
        cls,
        user_id,
        organization_id,
        session_id,
        document_id,
        view_duration_seconds,
        **kwargs,
    ):
        """Create a document view event"""
        return cls(
            event_type=EventType.DOCUMENT_VIEW,
            event_category="content",
            user_id=user_id,
            organization_id=organization_id,
            session_id=session_id,
            event_name="document_view",
            description=f"Document viewed: {document_id}",
            event_data={
                "document_id": str(document_id),
                "view_duration_seconds": view_duration_seconds,
                "scroll_depth": kwargs.get("scroll_depth", 0),
            },
            value=view_duration_seconds,
            unit="seconds",
            **kwargs,
        )

    @classmethod
    def create_performance_event(
        cls, organization_id, metric_name, value, unit="ms", **kwargs
    ):
        """Create a performance metric event"""
        return cls(
            event_type=EventType.PERFORMANCE_METRIC,
            event_category="performance",
            organization_id=organization_id,
            event_name=metric_name,
            description=f"Performance metric: {metric_name}",
            event_data={
                "metric_name": metric_name,
                "component": kwargs.get("component", "system"),
            },
            value=value,
            unit=unit,
            severity=EventSeverity.WARNING
            if value > kwargs.get("threshold", 1000)
            else EventSeverity.INFO,
            **kwargs,
        )

    @classmethod
    def create_error_event(
        cls, user_id, organization_id, error_message, error_code, **kwargs
    ):
        """Create an error event"""
        return cls(
            event_type=EventType.ERROR_OCCURRED,
            event_category="error",
            user_id=user_id,
            organization_id=organization_id,
            event_name="error",
            description=error_message,
            event_data={
                "error_code": error_code,
                "stack_trace": kwargs.get("stack_trace"),
                "component": kwargs.get("component", "unknown"),
            },
            severity=EventSeverity.CRITICAL
            if error_code >= 500
            else EventSeverity.ERROR,
            **kwargs,
        )

    @classmethod
    def create_quality_metric_event(
        cls, organization_id, metric_name, value, threshold=None, **kwargs
    ):
        """Create a quality metric event"""
        severity = EventSeverity.INFO
        if threshold:
            if value < threshold * 0.8:
                severity = EventSeverity.WARNING
            elif value < threshold * 0.6:
                severity = EventSeverity.ERROR
            elif value < threshold * 0.4:
                severity = EventSeverity.CRITICAL

        return cls(
            event_type=EventType.QUALITY_METRIC,
            event_category="quality",
            organization_id=organization_id,
            event_name=metric_name,
            description=f"Quality metric: {metric_name}",
            event_data={
                "metric_name": metric_name,
                "threshold": threshold,
                "query_type": kwargs.get("query_type", "unknown"),
            },
            value=value,
            unit="score",
            severity=severity,
            **kwargs,
        )

    def mark_processed(self, batch_id=None):
        """Mark event as processed"""
        self.processed = True
        if batch_id:
            self.batch_id = batch_id

    def to_dict(self):
        """Convert event to dictionary for API responses"""
        return {
            "id": str(self.id),
            "event_type": self.event_type.value,
            "event_category": self.event_category,
            "severity": self.severity.value if self.severity else None,
            "event_name": self.event_name,
            "description": self.description,
            "event_data": self.event_data,
            "value": self.value,
            "unit": self.unit,
            "response_time_ms": self.response_time_ms,
            "user_id": str(self.user_id) if self.user_id else None,
            "session_id": self.session_id,
            "organization_id": str(self.organization_id),
            "event_timestamp": self.event_timestamp.isoformat()
            if self.event_timestamp
            else None,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @staticmethod
    def get_time_bucket(timestamp: datetime, bucket_size: str = "hour") -> str:
        """Get time bucket for aggregation"""
        if bucket_size == "minute":
            return timestamp.strftime("%Y-%m-%dT%H:%M")
        elif bucket_size == "hour":
            return timestamp.strftime("%Y-%m-%dT%H")
        elif bucket_size == "day":
            return timestamp.strftime("%Y-%m-%d")
        elif bucket_size == "week":
            # ISO week
            year, week, _ = timestamp.isocalendar()
            return f"{year}-W{week:02d}"
        elif bucket_size == "month":
            return timestamp.strftime("%Y-%m")
        else:
            return timestamp.strftime("%Y-%m-%dT%H")
