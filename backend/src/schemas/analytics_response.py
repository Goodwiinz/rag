"""
Analytics response schema definitions for standardized API responses
Provides consistent structure for all analytics data responses
"""

from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field, field_validator
from decimal import Decimal


class ResponseStatus(str, Enum):
    """Response status types"""
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"
    NO_DATA = "no_data"


class DataType(str, Enum):
    """Data type identifiers"""
    TIME_SERIES = "time_series"
    CATEGORICAL = "categorical"
    NUMERICAL = "numerical"
    DISTRIBUTION = "distribution"
    TABLE = "table"
    SUMMARY = "summary"


# Base Response Models

class BaseAnalyticsResponse(BaseModel):
    """Base response model for all analytics endpoints"""

    status: ResponseStatus = Field(ResponseStatus.SUCCESS, description="Response status")
    timestamp: datetime = Field(..., description="Response generation timestamp")
    execution_time_ms: int = Field(..., description="Server-side execution time in milliseconds")
    cache_hit: bool = Field(False, description="Whether response was served from cache")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ResponseMetadata(BaseModel):
    """Metadata about the analytics response"""

    data_type: DataType = Field(..., description="Type of data returned")
    total_records: int = Field(..., description="Total number of records in dataset")
    returned_records: int = Field(..., description="Number of records returned in this response")
    has_more: bool = Field(False, description="Whether more records are available")

    # Time period information
    actual_start_date: Optional[datetime] = Field(None, description="Actual start date of data")
    actual_end_date: Optional[datetime] = Field(None, description="Actual end date of data")

    # Data quality indicators
    completeness_percentage: Optional[float] = Field(None, ge=0, le=100, description="Data completeness percentage")
    freshness_minutes: Optional[int] = Field(None, description="Data freshness in minutes")

    # Query information
    query_complexity: Optional[str] = Field(None, description="Query complexity level")
    indexes_used: Optional[List[str]] = Field(None, description="Database indexes utilized")

    @field_validator('completeness_percentage')
    @classmethod
    def validate_completeness(cls, v):
        """Validate completeness percentage"""
        if v is not None and (v < 0 or v > 100):
            raise ValueError("completeness_percentage must be between 0 and 100")
        return v


class PaginationInfo(BaseModel):
    """Pagination information for paginated responses"""

    page: int = Field(1, ge=1, description="Current page number")
    per_page: int = Field(100, ge=1, le=10000, description="Items per page")
    total_pages: int = Field(1, ge=1, description="Total number of pages")
    total_items: int = Field(0, ge=0, description="Total number of items")
    has_next: bool = Field(False, description="Whether there's a next page")
    has_previous: bool = Field(False, description="Whether there's a previous page")

    @field_validator('total_pages')
    @classmethod
    def calculate_total_pages(cls, v, info):
        """Calculate total pages from total items and per_page"""
        total_items = info.data.get('total_items', 0)
        per_page = info.data.get('per_page', 100)
        if per_page > 0:
            return max(1, (total_items + per_page - 1) // per_page)
        return v


# Data Structures

class TimeSeriesPoint(BaseModel):
    """Single point in a time series"""
    timestamp: datetime = Field(..., description="Timestamp for this data point")
    value: Union[float, int, Decimal] = Field(..., description="Value at this timestamp")
    count: Optional[int] = Field(None, description="Number of items aggregated for this point")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata for this point")


class TimeSeriesData(BaseModel):
    """Time series data structure"""

    metric_name: str = Field(..., description="Name of the metric")
    unit: Optional[str] = Field(None, description="Unit of measurement")
    data_points: List[TimeSeriesPoint] = Field(..., description="Time series data points")
    aggregation: Optional[str] = Field(None, description="Aggregation method used")

    # Statistical summary
    min_value: Optional[float] = Field(None, description="Minimum value in series")
    max_value: Optional[float] = Field(None, description="Maximum value in series")
    avg_value: Optional[float] = Field(None, description="Average value in series")
    trend_percentage: Optional[float] = Field(None, description="Trend percentage")


class CategoryDataPoint(BaseModel):
    """Single data point for categorical data"""
    category: str = Field(..., description="Category name")
    value: Union[float, int, Decimal] = Field(..., description="Value for this category")
    percentage: Optional[float] = Field(None, ge=0, le=100, description="Percentage of total")
    count: Optional[int] = Field(None, description="Count of items in this category")


class CategoricalData(BaseModel):
    """Categorical data structure"""

    field_name: str = Field(..., description="Name of the field/category")
    categories: List[CategoryDataPoint] = Field(..., description="Category data points")
    total_value: Optional[float] = Field(None, description="Total value across all categories")
    other_count: Optional[int] = Field(None, description="Count of items not shown")


class DistributionBin(BaseModel):
    """Single bin in a distribution"""
    range_start: Union[float, int, Decimal] = Field(..., description="Start of bin range")
    range_end: Union[float, int, Decimal] = Field(..., description="End of bin range")
    count: int = Field(..., description="Number of items in this bin")
    percentage: Optional[float] = Field(None, ge=0, le=100, description="Percentage of items in this bin")


class DistributionData(BaseModel):
    """Distribution data structure"""

    field_name: str = Field(..., description="Name of the field")
    bins: List[DistributionBin] = Field(..., description="Distribution bins")
    total_count: int = Field(..., description="Total count of items")
    mean_value: Optional[float] = Field(None, description="Mean value")
    median_value: Optional[float] = Field(None, description="Median value")
    std_deviation: Optional[float] = Field(None, description="Standard deviation")


class TableColumn(BaseModel):
    """Table column definition"""
    name: str = Field(..., description="Column name")
    type: str = Field(..., description="Data type (string, number, date, boolean)")
    display_name: Optional[str] = Field(None, description="Display name for column")
    format: Optional[str] = Field(None, description="Formatting pattern")


class TableRow(BaseModel):
    """Single table row"""
    values: Dict[str, Any] = Field(..., description="Row values keyed by column name")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Row metadata")


class TableData(BaseModel):
    """Tabular data structure"""

    columns: List[TableColumn] = Field(..., description="Table column definitions")
    rows: List[TableRow] = Field(..., description="Table rows")
    total_rows: int = Field(..., description="Total number of rows in dataset")
    sortable_columns: Optional[List[str]] = Field(None, description="Columns that can be sorted")


class MetricSummary(BaseModel):
    """Summary statistics for a metric"""

    metric_name: str = Field(..., description="Name of the metric")
    current_value: Union[float, int, Decimal] = Field(..., description="Current value")
    previous_value: Optional[Union[float, int, Decimal]] = Field(None, description="Previous period value")
    change_percentage: Optional[float] = Field(None, description="Percentage change from previous period")
    trend_direction: Optional[str] = Field(None, pattern="^(up|down|stable)$", description="Trend direction")

    # Statistical values
    min_value: Optional[Union[float, int, Decimal]] = Field(None, description="Minimum value")
    max_value: Optional[Union[float, int, Decimal]] = Field(None, description="Maximum value")
    avg_value: Optional[float] = Field(None, description="Average value")
    median_value: Optional[float] = Field(None, description="Median value")

    # Quality indicators
    data_points: int = Field(..., description="Number of data points")
    confidence_level: Optional[float] = Field(None, ge=0, le=1, description="Statistical confidence")
    is_significant: Optional[bool] = Field(None, description="Whether change is statistically significant")


# Specific Response Models

class PerformanceMetricsResponse(BaseAnalyticsResponse):
    """Response model for performance metrics"""

    data: Union[TimeSeriesData, DistributionData, List[MetricSummary]] = Field(..., description="Performance metrics data")
    metadata: ResponseMetadata = Field(..., description="Response metadata")
    pagination: Optional[PaginationInfo] = Field(None, description="Pagination information")

    # Performance-specific metadata
    alert_count: Optional[int] = Field(0, description="Number of active alerts")
    system_health_score: Optional[float] = Field(None, ge=0, le=100, description="Overall system health score")


class UserBehaviorResponse(BaseAnalyticsResponse):
    """Response model for user behavior analytics"""

    data: Union[TimeSeriesData, CategoricalData, TableData] = Field(..., description="User behavior data")
    metadata: ResponseMetadata = Field(..., description="Response metadata")
    pagination: Optional[PaginationInfo] = Field(None, description="Pagination information")

    # Behavior-specific metadata
    unique_users: Optional[int] = Field(None, description="Number of unique users")
    avg_session_duration: Optional[float] = Field(None, description="Average session duration in seconds")
    engagement_score: Optional[float] = Field(None, ge=0, le=100, description="Overall engagement score")
    conversion_rate: Optional[float] = Field(None, ge=0, le=100, description="Conversion rate percentage")


class QualityMetricsResponse(BaseAnalyticsResponse):
    """Response model for quality analytics"""

    data: Union[TimeSeriesData, DistributionData, List[MetricSummary]] = Field(..., description="Quality metrics data")
    metadata: ResponseMetadata = Field(..., description="Response metadata")
    pagination: Optional[PaginationInfo] = Field(None, description="Pagination information")

    # Quality-specific metadata
    overall_quality_score: Optional[float] = Field(None, ge=0, le=100, description="Overall quality score")
    queries_analyzed: Optional[int] = Field(None, description="Number of queries analyzed")
    below_threshold_count: Optional[int] = Field(None, description="Count of metrics below threshold")


class AnalyticsEventsResponse(BaseAnalyticsResponse):
    """Response model for analytics events"""

    data: Union[TableData, CategoricalData, TimeSeriesData] = Field(..., description="Analytics events data")
    metadata: ResponseMetadata = Field(..., description="Response metadata")
    pagination: PaginationInfo = Field(..., description="Pagination information")

    # Events-specific metadata
    total_events: Optional[int] = Field(None, description="Total number of events")
    unique_sessions: Optional[int] = Field(None, description="Number of unique sessions")
    error_rate: Optional[float] = Field(None, ge=0, le=100, description="Error rate percentage")


class ComparativeAnalyticsResponse(BaseAnalyticsResponse):
    """Response model for comparative analytics"""

    data: Dict[str, Any] = Field(..., description="Comparative analysis data")
    metadata: ResponseMetadata = Field(..., description="Response metadata")

    # Comparison-specific metadata
    current_period_label: str = Field(..., description="Label for current period")
    comparison_period_label: str = Field(..., description="Label for comparison period")
    statistical_significance: Optional[float] = Field(None, ge=0, le=1, description="Statistical significance level")
    confidence_interval: Optional[str] = Field(None, description="Confidence interval information")


# Error Response Models

class ErrorResponse(BaseAnalyticsResponse):
    """Error response model"""

    status: ResponseStatus = Field(ResponseStatus.ERROR, description="Response status")
    error_code: str = Field(..., description="Error code")
    error_message: str = Field(..., description="Human-readable error message")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    stack_trace: Optional[str] = Field(None, description="Technical stack trace (development only)")


class ValidationErrorResponse(ErrorResponse):
    """Validation error response"""

    validation_errors: Dict[str, List[str]] = Field(..., description="Field-specific validation errors")
    field_names: List[str] = Field(..., description="List of fields with validation errors")


class RateLimitResponse(ErrorResponse):
    """Rate limit exceeded response"""

    error_code: str = Field("RATE_LIMIT_EXCEEDED", description="Error code")
    retry_after_seconds: int = Field(..., description="Seconds to wait before retrying")
    limit_type: str = Field(..., description="Type of rate limit")
    current_usage: int = Field(..., description="Current usage count")
    limit: int = Field(..., description="Rate limit threshold")


# Cache and Performance Models

class CacheInfo(BaseModel):
    """Cache information in response"""

    cache_key: Optional[str] = Field(None, description="Cache key used")
    cache_ttl: Optional[int] = Field(None, description="Cache time-to-live in seconds")
    cache_age: Optional[int] = Field(None, description="Age of cached data in seconds")
    cache_version: Optional[str] = Field(None, description="Cache version identifier")


class PerformanceInfo(BaseModel):
    """Performance information in response"""

    query_time_ms: int = Field(..., description="Database query time in milliseconds")
    serialization_time_ms: Optional[int] = Field(None, description="Response serialization time in milliseconds")
    total_time_ms: int = Field(..., description="Total server processing time in milliseconds")
    memory_usage_mb: Optional[float] = Field(None, description="Memory usage during request")
    database_rows_examined: Optional[int] = Field(None, description="Number of database rows examined")


# Composite Response Model

class AnalyticsApiResponse(BaseModel):
    """Complete analytics API response"""

    response: Union[
        PerformanceMetricsResponse,
        UserBehaviorResponse,
        QualityMetricsResponse,
        AnalyticsEventsResponse,
        ComparativeAnalyticsResponse,
        ErrorResponse
    ] = Field(..., description="Primary response data")

    cache_info: Optional[CacheInfo] = Field(None, description="Cache information")
    performance_info: PerformanceInfo = Field(..., description="Performance information")

    # Request context
    request_id: Optional[str] = Field(None, description="Unique request identifier")
    user_context: Optional[Dict[str, Any]] = Field(None, description="User context information")

    @field_validator('performance_info')
    @classmethod
    def validate_performance_info(cls, v):
        """Ensure performance info is provided"""
        if not v or v.total_time_ms is None:
            raise ValueError("Performance information is required")
        return v