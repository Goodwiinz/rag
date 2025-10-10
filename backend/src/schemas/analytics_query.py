"""
Analytics query schema definitions for input validation and sanitization
Provides comprehensive validation for all analytics query parameters
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Union
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator
import re


class TimeRange(str, Enum):
    """Predefined time ranges for analytics queries"""
    LAST_HOUR = "last_hour"
    LAST_24_HOURS = "last_24_hours"
    LAST_7_DAYS = "last_7_days"
    LAST_30_DAYS = "last_30_days"
    LAST_90_DAYS = "last_90_days"
    LAST_YEAR = "last_year"
    CUSTOM = "custom"


class MetricCategory(str, Enum):
    """Analytics metric categories"""
    SYSTEM = "system"
    DATABASE = "database"
    API = "api"
    SEARCH = "search"
    CACHE = "cache"
    MEMORY = "memory"
    NETWORK = "network"
    STORAGE = "storage"
    EXTERNAL_SERVICE = "external_service"


class EventCategory(str, Enum):
    """Analytics event categories"""
    SEARCH = "search"
    CONTENT = "content"
    PERFORMANCE = "performance"
    ERROR = "error"
    QUALITY = "quality"
    USER_BEHAVIOR = "user_behavior"
    SYSTEM = "system"


class AggregationType(str, Enum):
    """Data aggregation types"""
    SUM = "sum"
    AVERAGE = "average"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    MEDIAN = "median"
    PERCENTILE_95 = "percentile_95"
    PERCENTILE_99 = "percentile_99"


class SortOrder(str, Enum):
    """Sort order options"""
    ASC = "asc"
    DESC = "desc"


# Base Analytics Query Models

class BaseAnalyticsQuery(BaseModel):
    """Base query parameters for all analytics endpoints"""

    # Time filtering
    time_range: Optional[TimeRange] = Field(TimeRange.LAST_7_DAYS, description="Predefined time range")
    start_date: Optional[datetime] = Field(None, description="Custom start date (required when time_range=CUSTOM)")
    end_date: Optional[datetime] = Field(None, description="Custom end date (required when time_range=CUSTOM)")

    # Data filtering
    organization_id: Optional[str] = Field(None, description="Organization ID filter")
    user_id: Optional[str] = Field(None, description="User ID filter (for admin users)")
    limit: int = Field(100, ge=1, le=10000, description="Maximum number of results to return")
    offset: int = Field(0, ge=0, description="Number of results to skip (pagination)")

    # Output formatting
    include_metadata: bool = Field(True, description="Include metadata in response")
    timezone: str = Field("UTC", description="Timezone for datetime formatting")

    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_custom_dates(cls, v, info):
        """Validate custom date range"""
        if info.data.get('time_range') == TimeRange.CUSTOM:
            if v is None:
                field_name = info.field_name
                raise ValueError(f"{field_name} is required when time_range=CUSTOM")
        return v

    @model_validator(mode='after')
    def validate_date_range(self):
        """Validate that start_date <= end_date for custom ranges"""
        if self.time_range == TimeRange.CUSTOM:
            start_date = self.start_date
            end_date = self.end_date

            if start_date and end_date:
                if start_date >= end_date:
                    raise ValueError("start_date must be before end_date")

                # Limit custom date range to 1 year
                max_range = timedelta(days=365)
                if end_date - start_date > max_range:
                    raise ValueError("Custom date range cannot exceed 1 year")

        return self

    @field_validator('timezone')
    @classmethod
    def validate_timezone(cls, v):
        """Validate timezone format"""
        try:
            import pytz
            pytz.timezone(v)
            return v
        except Exception:
            raise ValueError(f"Invalid timezone: {v}")


class PerformanceMetricsQuery(BaseAnalyticsQuery):
    """Query parameters for performance metrics"""

    metric_category: Optional[MetricCategory] = Field(None, description="Filter by metric category")
    component: Optional[str] = Field(None, min_length=1, max_length=100, description="Filter by component name")
    environment: Optional[str] = Field(None, min_length=1, max_length=50, description="Filter by environment")
    performance_level: Optional[str] = Field(None, pattern="^(excellent|good|fair|poor|critical)$", description="Filter by performance level")

    # Aggregation parameters
    aggregation: Optional[AggregationType] = Field(AggregationType.AVERAGE, description="Aggregation type for metrics")
    bucket_size: str = Field("hour", pattern="^(minute|hour|day|week|month)$", description="Time bucket size for aggregation")

    # Threshold filtering
    show_alerts_only: bool = Field(False, description="Show only metrics that triggered alerts")
    min_severity: Optional[str] = Field(None, pattern="^(info|warning|error|critical)$", description="Minimum severity level")

    @field_validator('component')
    @classmethod
    def sanitize_component(cls, v):
        """Sanitize component name to prevent injection"""
        if v:
            # Remove any special characters except alphanumeric, underscore, dash, dot
            v = re.sub(r'[^\w\-\.]', '', v)
            if not v:
                raise ValueError("Component name contains invalid characters")
        return v


class UserBehaviorQuery(BaseAnalyticsQuery):
    """Query parameters for user behavior analytics"""

    event_type: Optional[str] = Field(None, description="Filter by specific event type")
    session_id: Optional[str] = Field(None, min_length=10, max_length=255, description="Filter by session ID")

    # User filtering
    include_anonymous: bool = Field(False, description="Include anonymous/anonymized users")
    user_segments: Optional[List[str]] = Field(None, description="Filter by user segments")

    # Behavioral metrics
    min_engagement_score: Optional[float] = Field(None, ge=0, le=100, description="Minimum engagement score filter")
    min_session_duration: Optional[int] = Field(None, ge=0, description="Minimum session duration in seconds")
    bounced_sessions_only: bool = Field(False, description="Show only bounced sessions")

    # Search behavior
    search_query_contains: Optional[str] = Field(None, min_length=1, max_length=100, description="Filter by search query content")
    has_downloads: bool = Field(None, description="Filter sessions with/without downloads")

    @field_validator('search_query_contains')
    @classmethod
    def sanitize_search_query(cls, v):
        """Sanitize search query to prevent injection"""
        if v:
            # Remove SQL injection patterns
            v = re.sub(r"[;'\"]", '', v)
            # Remove excessive whitespace
            v = re.sub(r'\s+', ' ', v).strip()
            if len(v) < 1:
                raise ValueError("Search query too short after sanitization")
        return v


class QualityMetricsQuery(BaseAnalyticsQuery):
    """Query parameters for quality analytics"""

    metric_name: Optional[str] = Field(None, min_length=1, max_length=100, description="Filter by specific quality metric")
    query_type: Optional[str] = Field(None, pattern="^(semantic|hybrid|keyword)$", description="Filter by query type")

    # Quality thresholds
    min_score: Optional[float] = Field(None, ge=0, le=1, description="Minimum quality score filter")
    max_score: Optional[float] = Field(None, ge=0, le=1, description="Maximum quality score filter")
    below_threshold: bool = Field(False, description="Show only metrics below threshold")

    # Comparison and trends
    compare_with_previous: bool = Field(False, description="Compare with previous period")
    trend_direction: Optional[str] = Field(None, pattern="^(up|down|stable)$", description="Filter by trend direction")

    @model_validator(mode='after')
    def validate_score_range(self):
        """Validate that min_score <= max_score"""
        min_score = self.min_score
        max_score = self.max_score

        if min_score is not None and max_score is not None:
            if min_score > max_score:
                raise ValueError("min_score must be less than or equal to max_score")

        return self


class AnalyticsEventsQuery(BaseAnalyticsQuery):
    """Query parameters for analytics events"""

    event_type: Optional[str] = Field(None, description="Filter by event type")
    event_category: Optional[EventCategory] = Field(None, description="Filter by event category")
    severity: Optional[str] = Field(None, pattern="^(info|warning|error|critical)$", description="Filter by severity level")

    # Event-specific filtering
    component: Optional[str] = Field(None, min_length=1, max_length=100, description="Filter by component")
    error_code: Optional[int] = Field(None, ge=100, le=599, description="Filter by HTTP error code")

    # Text-based filtering
    description_contains: Optional[str] = Field(None, min_length=1, max_length=200, description="Filter by description content")

    # Aggregation
    group_by: Optional[List[str]] = Field(None, description="Fields to group by for aggregation")

    @field_validator('description_contains')
    @classmethod
    def sanitize_description(cls, v):
        """Sanitize description text to prevent injection"""
        if v:
            # Remove potentially dangerous characters
            v = re.sub(r"[;<>'\"]", '', v)
            # Remove excessive whitespace
            v = re.sub(r'\s+', ' ', v).strip()
            if len(v) < 1:
                raise ValueError("Description too short after sanitization")
        return v

    @field_validator('group_by')
    @classmethod
    def validate_group_by(cls, v):
        """Validate group_by fields"""
        if v:
            allowed_fields = [
                'event_type', 'event_category', 'severity', 'component',
                'user_id', 'organization_id', 'date_hour', 'date_day'
            ]
            for field in v:
                if field not in allowed_fields:
                    raise ValueError(f"Invalid group_by field: {field}. Allowed: {allowed_fields}")
        return v


class ComparativeAnalyticsQuery(BaseAnalyticsQuery):
    """Query parameters for comparative analytics"""

    # Comparison periods
    current_period_start: datetime = Field(..., description="Start of current period")
    current_period_end: datetime = Field(..., description="End of current period")
    comparison_period_start: datetime = Field(..., description="Start of comparison period")
    comparison_period_end: datetime = Field(..., description="End of comparison period")

    # Comparison metrics
    metrics: List[str] = Field(..., min_items=1, max_items=10, description="List of metrics to compare")
    dimensions: Optional[List[str]] = Field(None, description="Dimensions for comparison")

    # Statistical analysis
    confidence_level: float = Field(0.95, ge=0.8, le=0.99, description="Statistical confidence level")
    show_significant_only: bool = Field(False, description="Show only statistically significant changes")

    @model_validator(mode='after')
    def validate_comparison_periods(self):
        """Validate comparison period definitions"""
        for period_type in ['current', 'comparison']:
            start_attr = f"{period_type}_period_start"
            end_attr = f"{period_type}_period_end"

            start_date = getattr(self, start_attr, None)
            end_date = getattr(self, end_attr, None)

            if start_date and end_date:
                if start_date >= end_date:
                    raise ValueError(f"{period_type.title()} period start must be before end")

                # Limit period length to 90 days
                max_range = timedelta(days=90)
                if end_date - start_date > max_range:
                    raise ValueError(f"{period_type.title()} period cannot exceed 90 days")

        return self


# Response Models

class AnalyticsResponse(BaseModel):
    """Base response model for analytics endpoints"""

    data: Dict[str, Any] = Field(..., description="Analytics data")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Response metadata")
    query_params: Optional[Dict[str, Any]] = Field(None, description="Processed query parameters")

    class Config:
        schema_extra = {
            "example": {
                "data": {"metrics": []},
                "metadata": {"total_count": 100, "execution_time_ms": 150},
                "query_params": {"time_range": "last_7_days", "limit": 100}
            }
        }


class ValidationErrorResponse(BaseModel):
    """Response model for validation errors"""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Dict[str, List[str]] = Field(..., description="Field-specific validation errors")

    class Config:
        json_schema_extra = {
            "example": {
                "error": "ValidationError",
                "message": "Invalid query parameters",
                "details": {
                    "start_date": ["Start date is required when time_range=CUSTOM"],
                    "limit": ["Limit must be between 1 and 10000"]
                }
            }
        }