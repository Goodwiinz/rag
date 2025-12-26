"""
Analytics models for metrics and events
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, validator, ConfigDict
from sqlalchemy import (
    Column, String, DateTime, Boolean, Text, JSON, Integer, ForeignKey,
    Float, Enum as SQLEnum, Numeric, BigInteger
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from ..base import BaseModel as SQLBaseModel, GUID


class MetricType(str, Enum):
    """Types of analytics metrics"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"
    AVERAGE = "average"
    SUM = "sum"
    MIN = "min"
    MAX = "max"
    PERCENTILE = "percentile"
    RATE = "rate"


class AggregationType(str, Enum):
    """Types of metric aggregations"""
    SUM = "sum"
    AVERAGE = "avg"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    DISTINCT_COUNT = "distinct_count"
    MEDIAN = "median"
    STDDEV = "stddev"
    VARIANCE = "variance"
    PERCENTILE_95 = "p95"
    PERCENTILE_99 = "p99"
    RATE = "rate"


class EventType(str, Enum):
    """Types of analytics events"""
    PAGE_VIEW = "page_view"
    SEARCH = "search"
    CLICK = "click"
    DOWNLOAD = "download"
    UPLOAD = "upload"
    LOGIN = "login"
    LOGOUT = "logout"
    ERROR = "error"
    PERFORMANCE = "performance"
    CONVERSION = "conversion"
    INTERACTION = "interaction"
    SYSTEM = "system"


class AnalyticsEvent(SQLBaseModel):
    """Analytics event model"""

    __tablename__ = "analytics_events"

    # Event identification
    event_type = Column(SQLEnum(EventType), nullable=False, index=True)
    event_name = Column(String(255), nullable=False, index=True)
    event_category = Column(String(100), nullable=True, index=True)

    # User and session
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=True, index=True)
    session_id = Column(String(255), nullable=True, index=True)
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=True, index=True)

    # Request context
    request_id = Column(String(255), nullable=True, index=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    referrer = Column(Text, nullable=True)

    # Event properties
    properties = Column(JSON, nullable=True)  # Event-specific properties
    value = Column(Numeric(15, 4), nullable=True)  # Numeric value
    tags = Column(JSON, nullable=True)  # Event tags

    # Geographic and temporal
    country = Column(String(2), nullable=True)
    city = Column(String(100), nullable=True)
    timezone = Column(String(50), nullable=True)

    # Processing metadata
    processed = Column(Boolean, default=False, nullable=False, index=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    processing_error = Column(Text, nullable=True)


class AnalyticsMetric(SQLBaseModel):
    """Analytics metric model"""

    __tablename__ = "analytics_metrics"

    # Metric identification
    name = Column(String(255), nullable=False, unique=True, index=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    metric_type = Column(SQLEnum(MetricType), nullable=False)

    # Configuration
    unit = Column(String(50), nullable=True)
    data_source = Column(String(255), nullable=True)  # Where data comes from
    calculation_config = Column(JSON, nullable=True)  # How to calculate

    # Aggregation settings
    default_aggregation = Column(SQLEnum(AggregationType), default=AggregationType.SUM, nullable=False)
    available_aggregations = Column(JSON, nullable=True)  # List of available aggregations

    # Dimensions and filters
    dimensions = Column(JSON, nullable=True)  # Available dimensions
    default_filters = Column(JSON, nullable=True)  # Default filters

    # Visualization
    visualization_type = Column(String(50), nullable=True)  # Recommended visualization
    color_scheme = Column(JSON, nullable=True)  # Color configuration

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_public = Column(Boolean, default=False, nullable=False)

    # Relationships
    kpis = relationship("AnalyticsKPI", back_populates="metric")
    aggregations = relationship("MetricAggregation", back_populates="metric")


class AnalyticsKPI(SQLBaseModel):
    """Key Performance Indicator model"""

    __tablename__ = "analytics_kpis"

    # KPI identification
    name = Column(String(255), nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Metric relationship
    metric_id = Column(GUID(), ForeignKey("analytics_metrics.id"), nullable=False, index=True)

    # Targets and thresholds
    target_value = Column(Numeric(15, 4), nullable=True)
    warning_threshold = Column(Numeric(15, 4), nullable=True)
    critical_threshold = Column(Numeric(15, 4), nullable=True)

    # Calculation settings
    aggregation_type = Column(SQLEnum(AggregationType), nullable=False)
    time_window = Column(Integer, default=3600, nullable=False)  # seconds
    time_range = Column(String(50), default="1h", nullable=False)  # 1h, 1d, 1w, 1m

    # Filters and dimensions
    filters = Column(JSON, nullable=True)
    dimensions = Column(JSON, nullable=True)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_critical = Column(Boolean, default=False, nullable=False)

    # Relationships
    metric = relationship("AnalyticsMetric", back_populates="kpis")


class MetricAggregation(SQLBaseModel):
    """Pre-aggregated metric data"""

    __tablename__ = "analytics_metric_aggregations"

    # Metric identification
    metric_id = Column(GUID(), ForeignKey("analytics_metrics.id"), nullable=False, index=True)
    aggregation_type = Column(SQLEnum(AggregationType), nullable=False, index=True)

    # Time window
    time_window = Column(String(50), nullable=False, index=True)  # 1m, 5m, 1h, 1d
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)

    # Dimensions
    dimensions_hash = Column(String(64), nullable=False, index=True)  # Hash of dimension values
    dimensions = Column(JSON, nullable=True)  # Dimension values

    # Aggregated values
    value = Column(Numeric(15, 4), nullable=False)
    count = Column(BigInteger, nullable=False)
    min_value = Column(Numeric(15, 4), nullable=True)
    max_value = Column(Numeric(15, 4), nullable=True)
    sum_value = Column(Numeric(15, 4), nullable=True)

    # Metadata
    sample_rate = Column(Float, default=1.0, nullable=False)
    data_quality_score = Column(Float, nullable=True)

    # Relationships
    metric = relationship("AnalyticsMetric", back_populates="aggregations")


class AnalyticsReport(SQLBaseModel):
    """Analytics report model"""

    __tablename__ = "analytics_reports"

    # Report identification
    name = Column(String(255), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Owner and sharing
    owner_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=True, index=True)

    # Configuration
    report_config = Column(JSON, nullable=False)  # Report configuration
    filters = Column(JSON, nullable=True)  # Default filters
    schedule_config = Column(JSON, nullable=True)  # Scheduling configuration

    # Output settings
    output_format = Column(String(20), default="pdf", nullable=False)  # pdf, csv, xlsx
    delivery_config = Column(JSON, nullable=True)  # Email, webhook, etc.

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_public = Column(Boolean, default=False, nullable=False)

    # Last run information
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    last_run_status = Column(String(50), nullable=True)
    last_run_error = Column(Text, nullable=True)


# Pydantic models for API serialization

class TimeSeriesData(BaseModel):
    """Time series data point"""
    timestamp: datetime
    value: float
    count: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class AnalyticsFilter(BaseModel):
    """Analytics filter configuration"""
    field: str
    operator: str  # eq, ne, gt, gte, lt, lte, in, nin, contains, regex
    value: Union[str, int, float, bool, List[Any]]
    case_sensitive: bool = True

    @validator('operator')
    def validate_operator(cls, v):
        """Validate operator"""
        valid_operators = ['eq', 'ne', 'gt', 'gte', 'lt', 'lte', 'in', 'nin', 'contains', 'regex']
        if v not in valid_operators:
            raise ValueError(f"Invalid operator: {v}. Must be one of: {valid_operators}")
        return v

    model_config = ConfigDict(from_attributes=True)


class MetricCreate(BaseModel):
    """Create metric request model"""
    name: str = Field(..., min_length=1, max_length=255)
    display_name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    metric_type: MetricType
    unit: Optional[str] = None
    data_source: Optional[str] = None
    calculation_config: Optional[Dict[str, Any]] = None
    default_aggregation: AggregationType = AggregationType.SUM
    available_aggregations: Optional[List[AggregationType]] = None
    dimensions: Optional[List[str]] = None
    default_filters: Optional[List[AnalyticsFilter]] = None
    visualization_type: Optional[str] = None
    color_scheme: Optional[Dict[str, Any]] = None
    is_public: bool = False

    model_config = ConfigDict(from_attributes=True)


class MetricUpdate(BaseModel):
    """Update metric request model"""
    display_name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    unit: Optional[str] = None
    data_source: Optional[str] = None
    calculation_config: Optional[Dict[str, Any]] = None
    default_aggregation: Optional[AggregationType] = None
    available_aggregations: Optional[List[AggregationType]] = None
    dimensions: Optional[List[str]] = None
    default_filters: Optional[List[AnalyticsFilter]] = None
    visualization_type: Optional[str] = None
    color_scheme: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    is_public: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class MetricResponse(BaseModel):
    """Metric response model"""
    id: uuid.UUID
    name: str
    display_name: str
    description: Optional[str]
    metric_type: MetricType
    unit: Optional[str]
    data_source: Optional[str]
    calculation_config: Optional[Dict[str, Any]]
    default_aggregation: AggregationType
    available_aggregations: Optional[List[AggregationType]]
    dimensions: Optional[List[str]]
    default_filters: Optional[List[AnalyticsFilter]]
    visualization_type: Optional[str]
    color_scheme: Optional[Dict[str, Any]]
    is_active: bool
    is_public: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KPICreate(BaseModel):
    """Create KPI request model"""
    name: str = Field(..., min_length=1, max_length=255)
    display_name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    metric_id: uuid.UUID
    target_value: Optional[float] = None
    warning_threshold: Optional[float] = None
    critical_threshold: Optional[float] = None
    aggregation_type: AggregationType
    time_window: int = Field(default=3600, ge=60, le=86400)
    time_range: str = "1h"
    filters: Optional[List[AnalyticsFilter]] = None
    dimensions: Optional[List[str]] = None
    is_critical: bool = False

    @validator('time_range')
    def validate_time_range(cls, v):
        """Validate time range"""
        valid_ranges = ['1m', '5m', '15m', '30m', '1h', '6h', '12h', '1d', '1w', '1M']
        if v not in valid_ranges:
            raise ValueError(f"Invalid time range: {v}. Must be one of: {valid_ranges}")
        return v

    model_config = ConfigDict(from_attributes=True)


class KPIResponse(BaseModel):
    """KPI response model"""
    id: uuid.UUID
    name: str
    display_name: str
    description: Optional[str]
    metric_id: uuid.UUID
    target_value: Optional[float]
    warning_threshold: Optional[float]
    critical_threshold: Optional[float]
    aggregation_type: AggregationType
    time_window: int
    time_range: str
    filters: Optional[List[AnalyticsFilter]]
    dimensions: Optional[List[str]]
    is_active: bool
    is_critical: bool
    created_at: datetime
    updated_at: datetime
    current_value: Optional[float] = None
    status: Optional[str] = None  # good, warning, critical

    model_config = ConfigDict(from_attributes=True)


class EventCreate(BaseModel):
    """Create event request model"""
    event_type: EventType
    event_name: str = Field(..., min_length=1, max_length=255)
    event_category: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    value: Optional[float] = None
    tags: Optional[List[str]] = None

    model_config = ConfigDict(from_attributes=True)


class EventResponse(BaseModel):
    """Event response model"""
    id: uuid.UUID
    event_type: EventType
    event_name: str
    event_category: Optional[str]
    user_id: Optional[uuid.UUID]
    session_id: Optional[str]
    request_id: Optional[str]
    properties: Optional[Dict[str, Any]]
    value: Optional[float]
    tags: Optional[List[str]]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MetricQuery(BaseModel):
    """Metric query configuration"""
    metric_ids: List[uuid.UUID]
    aggregation: AggregationType = AggregationType.SUM
    time_range: str = "1h"
    time_window: Optional[str] = None
    filters: Optional[List[AnalyticsFilter]] = None
    dimensions: Optional[List[str]] = None
    group_by: Optional[List[str]] = None
    order_by: Optional[str] = None
    limit: Optional[int] = Field(None, ge=1, le=10000)

    @validator('time_range')
    def validate_time_range(cls, v):
        """Validate time range"""
        valid_ranges = ['1m', '5m', '15m', '30m', '1h', '6h', '12h', '1d', '1w', '1M']
        if v not in valid_ranges:
            raise ValueError(f"Invalid time range: {v}. Must be one of: {valid_ranges}")
        return v

    model_config = ConfigDict(from_attributes=True)


class MetricQueryResult(BaseModel):
    """Metric query result"""
    metric_id: uuid.UUID
    metric_name: str
    aggregation: AggregationType
    time_range: str
    data: List[TimeSeriesData]
    total_count: int
    has_more: bool

    model_config = ConfigDict(from_attributes=True)