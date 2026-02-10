"""
Analytics-related data models for the RAG system
"""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator


class MetricType(str, Enum):
    """Metric types"""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


class TimeWindow(str, Enum):
    """Time windows for analytics"""

    REAL_TIME = "real_time"
    LAST_MINUTE = "last_minute"
    LAST_5_MINUTES = "last_5_minutes"
    LAST_15_MINUTES = "last_15_minutes"
    LAST_HOUR = "last_hour"
    LAST_6_HOURS = "last_6_hours"
    LAST_24_HOURS = "last_24_hours"
    LAST_7_DAYS = "last_7_days"
    LAST_30_DAYS = "last_30_days"
    CUSTOM = "custom"


class AlertSeverity(str, Enum):
    """Alert severity levels"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AnomalyType(str, Enum):
    """Anomaly types"""

    STATISTICAL = "statistical"
    ML_BASED = "ml_based"
    THRESHOLD = "threshold"
    PATTERN = "pattern"
    SEASONAL = "seasonal"


class MetricDataPoint(BaseModel):
    """Single metric data point"""

    timestamp: datetime = Field(..., description="Data point timestamp")
    value: float = Field(..., description="Metric value")
    labels: Dict[str, str] = Field(default_factory=dict, description="Metric labels")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class TimeSeriesData(BaseModel):
    """Time series data for analytics"""

    metric_name: str = Field(..., description="Metric name")
    data_points: List[MetricDataPoint] = Field(..., description="Data points")
    aggregation_method: str = Field("mean", description="Aggregation method")
    time_window: TimeWindow = Field(TimeWindow.LAST_HOUR, description="Time window")

    def get_values(self) -> List[float]:
        """Get all values from data points"""
        return [dp.value for dp in self.data_points]

    def get_timestamps(self) -> List[datetime]:
        """Get all timestamps from data points"""
        return [dp.timestamp for dp in self.data_points]


class AnalyticsMetrics(BaseModel):
    """Base analytics metrics model"""

    metric_name: str = Field(..., description="Metric name")
    metric_type: MetricType = Field(..., description="Metric type")
    value: float = Field(..., description="Current value")
    previous_value: Optional[float] = Field(None, description="Previous value")
    change_percentage: Optional[float] = Field(None, description="Percentage change")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp"
    )
    labels: Dict[str, str] = Field(default_factory=dict, description="Metric labels")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class UserAnalytics(BaseModel):
    """User analytics model"""

    user_id: Optional[UUID] = Field(None, description="User ID (None for aggregate)")
    period_start: date = Field(..., description="Analytics period start")
    period_end: date = Field(..., description="Analytics period end")
    total_sessions: int = Field(..., ge=0, description="Total sessions")
    total_queries: int = Field(..., ge=0, description="Total queries")
    unique_queries: int = Field(..., ge=0, description="Unique queries")
    avg_session_duration_ms: float = Field(
        ..., ge=0.0, description="Average session duration"
    )
    avg_dwell_time_ms: float = Field(..., ge=0.0, description="Average dwell time")
    click_through_rate: float = Field(
        ..., ge=0.0, le=1.0, description="Click-through rate"
    )
    satisfaction_score: Optional[float] = Field(
        None, ge=1.0, le=5.0, description="Satisfaction score"
    )
    top_queries: List[Dict[str, Any]] = Field(
        default_factory=list, description="Top queries"
    )
    preferred_modalities: List[str] = Field(
        default_factory=list, description="Preferred modalities"
    )
    expertise_areas: List[str] = Field(
        default_factory=list, description="Identified expertise areas"
    )
    engagement_score: float = Field(..., ge=0.0, le=1.0, description="Engagement score")

    class Config:
        json_encoders = {date: lambda v: v.isoformat(), UUID: lambda v: str(v)}


class ContentAnalytics(BaseModel):
    """Content analytics model"""

    content_id: Optional[UUID] = Field(
        None, description="Content ID (None for aggregate)"
    )
    period_start: date = Field(..., description="Analytics period start")
    period_end: date = Field(..., description="Analytics period end")
    total_views: int = Field(..., ge=0, description="Total views")
    unique_viewers: int = Field(..., ge=0, description="Unique viewers")
    avg_view_duration_ms: float = Field(
        ..., ge=0.0, description="Average view duration"
    )
    click_through_rate: float = Field(
        ..., ge=0.0, le=1.0, description="Click-through rate"
    )
    quality_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Quality score"
    )
    relevance_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Relevance score"
    )
    popularity_score: float = Field(..., ge=0.0, description="Popularity score")
    modality: str = Field(..., description="Content modality")
    tags: List[str] = Field(default_factory=list, description="Content tags")
    search_queries: List[str] = Field(
        default_factory=list, description="Search queries that found this content"
    )

    class Config:
        json_encoders = {date: lambda v: v.isoformat(), UUID: lambda v: str(v)}


class SystemAnalytics(BaseModel):
    """System analytics model"""

    timestamp: datetime = Field(..., description="Analytics timestamp")
    cpu_usage_percent: float = Field(
        ..., ge=0.0, le=100.0, description="CPU usage percentage"
    )
    memory_usage_percent: float = Field(
        ..., ge=0.0, le=100.0, description="Memory usage percentage"
    )
    disk_usage_percent: float = Field(
        ..., ge=0.0, le=100.0, description="Disk usage percentage"
    )
    network_io_mbps: float = Field(..., ge=0.0, description="Network I/O in Mbps")
    request_rate: float = Field(..., ge=0.0, description="Request rate per second")
    error_rate: float = Field(..., ge=0.0, le=1.0, description="Error rate")
    response_time_p50_ms: float = Field(
        ..., ge=0.0, description="50th percentile response time"
    )
    response_time_p95_ms: float = Field(
        ..., ge=0.0, description="95th percentile response time"
    )
    response_time_p99_ms: float = Field(
        ..., ge=0.0, description="99th percentile response time"
    )
    active_connections: int = Field(..., ge=0, description="Active connections")
    queue_size: int = Field(..., ge=0, description="Queue size")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class QualityMetrics(BaseModel):
    """Quality metrics model"""

    metric_name: str = Field(..., description="Quality metric name")
    value: float = Field(..., ge=0.0, le=1.0, description="Metric value")
    threshold: float = Field(..., ge=0.0, le=1.0, description="Quality threshold")
    passed_threshold: bool = Field(..., description="Whether metric passes threshold")
    sample_size: int = Field(..., ge=0, description="Sample size")
    confidence_interval: Optional[List[float]] = Field(
        None, description="Confidence interval"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class PerformanceMetrics(BaseModel):
    """Performance metrics model"""

    endpoint: str = Field(..., description="API endpoint")
    method: str = Field(..., description="HTTP method")
    request_count: int = Field(..., ge=0, description="Request count")
    success_count: int = Field(..., ge=0, description="Success count")
    error_count: int = Field(..., ge=0, description="Error count")
    avg_response_time_ms: float = Field(
        ..., ge=0.0, description="Average response time"
    )
    p50_response_time_ms: float = Field(
        ..., ge=0.0, description="50th percentile response time"
    )
    p95_response_time_ms: float = Field(
        ..., ge=0.0, description="95th percentile response time"
    )
    p99_response_time_ms: float = Field(
        ..., ge=0.0, description="99th percentile response time"
    )
    throughput_rps: float = Field(
        ..., ge=0.0, description="Throughput requests per second"
    )
    error_rate: float = Field(..., ge=0.0, le=1.0, description="Error rate")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class BusinessMetrics(BaseModel):
    """Business metrics model"""

    period_start: date = Field(..., description="Metrics period start")
    period_end: date = Field(..., description="Metrics period end")
    total_users: int = Field(..., ge=0, description="Total users")
    active_users: int = Field(..., ge=0, description="Active users")
    new_users: int = Field(..., ge=0, description="New users")
    user_retention_rate: float = Field(
        ..., ge=0.0, le=1.0, description="User retention rate"
    )
    total_queries: int = Field(..., ge=0, description="Total queries")
    documents_processed: int = Field(..., ge=0, description="Documents processed")
    system_uptime_percentage: float = Field(
        ..., ge=0.0, le=100.0, description="System uptime percentage"
    )
    customer_satisfaction_score: Optional[float] = Field(
        None, ge=1.0, le=5.0, description="Customer satisfaction"
    )
    revenue: Optional[float] = Field(None, ge=0.0, description="Revenue")
    cost: Optional[float] = Field(None, ge=0.0, description="Cost")

    class Config:
        json_encoders = {date: lambda v: v.isoformat()}


class AnomalyDetection(BaseModel):
    """Anomaly detection result"""

    id: UUID = Field(default_factory=uuid4, description="Anomaly ID")
    metric_name: str = Field(..., description="Metric name")
    anomaly_type: AnomalyType = Field(..., description="Anomaly type")
    severity: AlertSeverity = Field(..., description="Anomaly severity")
    detected_at: datetime = Field(..., description="Detection timestamp")
    value: float = Field(..., description="Anomalous value")
    expected_range: List[float] = Field(..., description="Expected value range")
    anomaly_score: float = Field(..., ge=0.0, description="Anomaly score")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence")
    description: str = Field(..., description="Anomaly description")
    affected_entities: List[str] = Field(
        default_factory=list, description="Affected entities"
    )
    resolved: bool = Field(False, description="Resolution status")
    resolved_at: Optional[datetime] = Field(None, description="Resolution timestamp")
    resolution_notes: Optional[str] = Field(None, description="Resolution notes")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat(), UUID: lambda v: str(v)}


class AnalyticsAlert(BaseModel):
    """Analytics alert model"""

    id: UUID = Field(default_factory=uuid4, description="Alert ID")
    alert_type: str = Field(..., description="Alert type")
    severity: AlertSeverity = Field(..., description="Alert severity")
    title: str = Field(..., description="Alert title")
    message: str = Field(..., description="Alert message")
    source: str = Field(..., description="Alert source")
    metric_name: Optional[str] = Field(None, description="Related metric name")
    threshold: Optional[float] = Field(None, description="Alert threshold")
    current_value: Optional[float] = Field(None, description="Current value")
    triggered_at: datetime = Field(
        default_factory=datetime.utcnow, description="Trigger timestamp"
    )
    acknowledged: bool = Field(False, description="Acknowledgment status")
    acknowledged_by: Optional[str] = Field(None, description="Acknowledged by")
    acknowledged_at: Optional[datetime] = Field(
        None, description="Acknowledgment timestamp"
    )
    resolved: bool = Field(False, description="Resolution status")
    resolved_at: Optional[datetime] = Field(None, description="Resolution timestamp")
    resolved_by: Optional[str] = Field(None, description="Resolved by")
    tags: List[str] = Field(default_factory=list, description="Alert tags")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat(), UUID: lambda v: str(v)}


class ForecastData(BaseModel):
    """Forecast data model"""

    metric_name: str = Field(..., description="Metric name")
    forecast_method: str = Field(..., description="Forecast method")
    historical_period_start: datetime = Field(
        ..., description="Historical period start"
    )
    historical_period_end: datetime = Field(..., description="Historical period end")
    forecast_periods: int = Field(..., ge=1, description="Number of forecast periods")
    forecast_values: List[float] = Field(..., description="Forecast values")
    confidence_intervals: List[List[float]] = Field(
        ..., description="Confidence intervals"
    )
    model_accuracy: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Model accuracy"
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Generation timestamp"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class AnalyticsDashboard(BaseModel):
    """Analytics dashboard model"""

    id: UUID = Field(default_factory=uuid4, description="Dashboard ID")
    name: str = Field(..., description="Dashboard name")
    description: str = Field(..., description="Dashboard description")
    widgets: List[Dict[str, Any]] = Field(..., description="Dashboard widgets")
    time_window: TimeWindow = Field(
        TimeWindow.LAST_24_HOURS, description="Default time window"
    )
    refresh_interval_seconds: int = Field(300, ge=30, description="Refresh interval")
    created_by: str = Field(..., description="Creator")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Update timestamp"
    )
    is_public: bool = Field(False, description="Public dashboard")
    tags: List[str] = Field(default_factory=list, description="Dashboard tags")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat(), UUID: lambda v: str(v)}


class AnalyticsReport(BaseModel):
    """Analytics report model"""

    id: UUID = Field(default_factory=uuid4, description="Report ID")
    title: str = Field(..., description="Report title")
    description: str = Field(..., description="Report description")
    report_type: str = Field(..., description="Report type")
    period_start: date = Field(..., description="Report period start")
    period_end: date = Field(..., description="Report period end")
    metrics: Dict[str, Any] = Field(..., description="Report metrics")
    insights: List[str] = Field(default_factory=list, description="Key insights")
    recommendations: List[str] = Field(
        default_factory=list, description="Recommendations"
    )
    charts: List[Dict[str, Any]] = Field(
        default_factory=list, description="Chart configurations"
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Generation timestamp"
    )
    generated_by: str = Field(..., description="Generated by")
    file_path: Optional[str] = Field(None, description="Exported file path")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }


class DataExport(BaseModel):
    """Data export model"""

    id: UUID = Field(default_factory=uuid4, description="Export ID")
    export_type: str = Field(..., description="Export type")
    format: str = Field(..., description="Export format (csv, json, xlsx)")
    filters: Dict[str, Any] = Field(..., description="Export filters")
    time_range: Dict[str, datetime] = Field(..., description="Time range")
    status: str = Field(..., description="Export status")
    file_path: Optional[str] = Field(None, description="Export file path")
    file_size_bytes: Optional[int] = Field(None, ge=0, description="File size")
    record_count: Optional[int] = Field(None, ge=0, description="Record count")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation timestamp"
    )
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    created_by: str = Field(..., description="Created by")
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat(), UUID: lambda v: str(v)}
