"""
Tests for analytics query and response schemas
Validates input validation, sanitization, and response formatting
"""

import pytest
from datetime import datetime, timedelta
from pydantic import ValidationError

from src.schemas.analytics_query import (
    BaseAnalyticsQuery, PerformanceMetricsQuery, UserBehaviorQuery,
    QualityMetricsQuery, AnalyticsEventsQuery, ComparativeAnalyticsQuery,
    TimeRange, MetricCategory, EventCategory, AggregationType, SortOrder
)
from src.schemas.analytics_response import (
    PerformanceMetricsResponse, UserBehaviorResponse, QualityMetricsResponse,
    AnalyticsEventsResponse, ErrorResponse, ValidationErrorResponse,
    ResponseStatus, DataType, ResponseMetadata, PaginationInfo
)
from src.utils.analytics_validation import (
    SecurityValidator, QueryParameterValidator, AnalyticsInputSanitizer,
    AnalyticsValidationError
)


class TestBaseAnalyticsQuery:
    """Test base analytics query validation"""

    def test_valid_query(self):
        """Test valid query parameters"""
        query = BaseAnalyticsQuery(
            time_range=TimeRange.LAST_7_DAYS,
            limit=100,
            offset=0,
            timezone="UTC"
        )
        assert query.time_range == TimeRange.LAST_7_DAYS
        assert query.limit == 100
        assert query.timezone == "UTC"

    def test_custom_date_range_validation(self):
        """Test custom date range validation"""
        start_date = datetime.utcnow() - timedelta(days=7)
        end_date = datetime.utcnow()

        # Valid custom range
        query = BaseAnalyticsQuery(
            time_range=TimeRange.CUSTOM,
            start_date=start_date,
            end_date=end_date
        )
        assert query.start_date == start_date
        assert query.end_date == end_date

        # Invalid: missing start date
        with pytest.raises(ValidationError) as exc_info:
            BaseAnalyticsQuery(time_range=TimeRange.CUSTOM, end_date=end_date)
        assert "start_date is required" in str(exc_info.value)

        # Invalid: start date after end date
        with pytest.raises(ValidationError) as exc_info:
            BaseAnalyticsQuery(
                time_range=TimeRange.CUSTOM,
                start_date=end_date,
                end_date=start_date
            )
        assert "start_date must be before end_date" in str(exc_info.value)

    def test_date_range_limit(self):
        """Test date range cannot exceed 1 year"""
        start_date = datetime.utcnow() - timedelta(days=400)
        end_date = datetime.utcnow()

        with pytest.raises(ValidationError) as exc_info:
            BaseAnalyticsQuery(
                time_range=TimeRange.CUSTOM,
                start_date=start_date,
                end_date=end_date
            )
        assert "cannot exceed 1 year" in str(exc_info.value)

    def test_limit_validation(self):
        """Test limit parameter validation"""
        # Valid limits
        query1 = BaseAnalyticsQuery(limit=1)
        query2 = BaseAnalyticsQuery(limit=10000)

        assert query1.limit == 1
        assert query2.limit == 10000

        # Invalid limits
        with pytest.raises(ValidationError):
            BaseAnalyticsQuery(limit=0)  # Too low

        with pytest.raises(ValidationError):
            BaseAnalyticsQuery(limit=10001)  # Too high

    def test_timezone_validation(self):
        """Test timezone validation"""
        # Valid timezones
        query1 = BaseAnalyticsQuery(timezone="UTC")
        query2 = BaseAnalyticsQuery(timezone="America/New_York")

        assert query1.timezone == "UTC"
        assert query2.timezone == "America/New_York"

        # Invalid timezone
        with pytest.raises(ValidationError) as exc_info:
            BaseAnalyticsQuery(timezone="Invalid/Timezone")
        assert "Invalid timezone" in str(exc_info.value)


class TestPerformanceMetricsQuery:
    """Test performance metrics query validation"""

    def test_valid_query(self):
        """Test valid performance metrics query"""
        query = PerformanceMetricsQuery(
            metric_category=MetricCategory.API,
            component="api_endpoints",
            aggregation=AggregationType.AVERAGE,
            bucket_size="hour"
        )
        assert query.metric_category == MetricCategory.API
        assert query.component == "api_endpoints"
        assert query.aggregation == AggregationType.AVERAGE
        assert query.bucket_size == "hour"

    def test_component_sanitization(self):
        """Test component name sanitization"""
        # Valid component names
        valid_components = [
            "api-endpoints",
            "search_service",
            "database.v1",
            "cache.redis"
        ]

        for component in valid_components:
            query = PerformanceMetricsQuery(component=component)
            assert query.component == component

        # Invalid component names
        invalid_components = [
            "api; DROP TABLE users; --",
            "component' OR '1'='1",
            "component<script>alert('xss')</script>",
            "   ",  # After sanitization becomes empty
        ]

        for component in invalid_components:
            with pytest.raises(ValidationError):
                PerformanceMetricsQuery(component=component)

    def test_bucket_size_validation(self):
        """Test bucket size validation"""
        valid_buckets = ["minute", "hour", "day", "week", "month"]

        for bucket in valid_buckets:
            query = PerformanceMetricsQuery(bucket_size=bucket)
            assert query.bucket_size == bucket

        # Invalid bucket size
        with pytest.raises(ValidationError):
            PerformanceMetricsQuery(bucket_size="invalid")


class TestUserBehaviorQuery:
    """Test user behavior query validation"""

    def test_valid_query(self):
        """Test valid user behavior query"""
        query = UserBehaviorQuery(
            min_engagement_score=50.0,
            min_session_duration=300,
            search_query_contains="machine learning"
        )
        assert query.min_engagement_score == 50.0
        assert query.min_session_duration == 300
        assert "machine learning" in query.search_query_contains

    def test_search_query_sanitization(self):
        """Test search query sanitization"""
        # SQL injection attempts
        malicious_queries = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "search'; SELECT * FROM sensitive_data; --"
        ]

        for query_text in malicious_queries:
            sanitized = UserBehaviorQuery(search_query_contains=query_text)
            # Should remove dangerous characters
            assert ";" not in sanitized.search_query_contains
            assert "--" not in sanitized.search_query_contains

    def test_engagement_score_validation(self):
        """Test engagement score validation"""
        # Valid scores
        UserBehaviorQuery(min_engagement_score=0)
        UserBehaviorQuery(min_engagement_score=50.5)
        UserBehaviorQuery(min_engagement_score=100)

        # Invalid scores
        with pytest.raises(ValidationError):
            UserBehaviorQuery(min_engagement_score=-1)

        with pytest.raises(ValidationError):
            UserBehaviorQuery(min_engagement_score=101)


class TestQualityMetricsQuery:
    """Test quality metrics query validation"""

    def test_valid_query(self):
        """Test valid quality metrics query"""
        query = QualityMetricsQuery(
            min_score=0.5,
            max_score=0.9,
            query_type="semantic",
            compare_with_previous=True
        )
        assert query.min_score == 0.5
        assert query.max_score == 0.9
        assert query.query_type == "semantic"
        assert query.compare_with_previous is True

    def test_score_range_validation(self):
        """Test score range validation"""
        # Valid ranges
        QualityMetricsQuery(min_score=0.1, max_score=0.5)
        QualityMetricsQuery(min_score=0.5, max_score=0.5)  # Equal values

        # Invalid: min > max
        with pytest.raises(ValidationError) as exc_info:
            QualityMetricsQuery(min_score=0.8, max_score=0.3)
        assert "min_score must be less than or equal to max_score" in str(exc_info.value)

    def test_query_type_validation(self):
        """Test query type validation"""
        valid_types = ["semantic", "hybrid", "keyword"]
        for qtype in valid_types:
            query = QualityMetricsQuery(query_type=qtype)
            assert query.query_type == qtype

        # Invalid query type
        with pytest.raises(ValidationError):
            QualityMetricsQuery(query_type="invalid")


class TestAnalyticsEventsQuery:
    """Test analytics events query validation"""

    def test_valid_query(self):
        """Test valid analytics events query"""
        query = AnalyticsEventsQuery(
            event_category=EventCategory.ERROR,
            severity="error",
            component="search_service"
        )
        assert query.event_category == EventCategory.ERROR
        assert query.severity == "error"
        assert query.component == "search_service"

    def test_group_by_validation(self):
        """Test group_by field validation"""
        allowed_fields = [
            'event_type', 'event_category', 'severity', 'component',
            'user_id', 'organization_id', 'date_hour', 'date_day'
        ]

        # Valid group_by fields
        AnalyticsEventsQuery(group_by=['event_type', 'severity'])
        AnalyticsEventsQuery(group_by=allowed_fields)

        # Invalid group_by field
        with pytest.raises(ValidationError) as exc_info:
            AnalyticsEventsQuery(group_by=['invalid_field'])
        assert "Invalid group_by field" in str(exc_info.value)

    def test_error_code_validation(self):
        """Test error code validation"""
        # Valid HTTP status codes
        AnalyticsEventsQuery(error_code=404)
        AnalyticsEventsQuery(error_code=500)

        # Invalid error codes
        with pytest.raises(ValidationError):
            AnalyticsEventsQuery(error_code=99)  # Too low

        with pytest.raises(ValidationError):
            AnalyticsEventsQuery(error_code=600)  # Too high


class TestComparativeAnalyticsQuery:
    """Test comparative analytics query validation"""

    def test_valid_query(self):
        """Test valid comparative analytics query"""
        now = datetime.utcnow()
        current_start = now - timedelta(days=7)
        current_end = now
        comparison_start = now - timedelta(days=14)
        comparison_end = now - timedelta(days=7)

        query = ComparativeAnalyticsQuery(
            current_period_start=current_start,
            current_period_end=current_end,
            comparison_period_start=comparison_start,
            comparison_period_end=comparison_end,
            metrics=['response_time', 'error_rate']
        )
        assert len(query.metrics) == 2
        assert query.metrics[0] == 'response_time'

    def test_period_validation(self):
        """Test comparison period validation"""
        now = datetime.utcnow()

        # Invalid: current period start after end
        with pytest.raises(ValidationError) as exc_info:
            ComparativeAnalyticsQuery(
                current_period_start=now,
                current_period_end=now - timedelta(days=1),
                comparison_period_start=now - timedelta(days=14),
                comparison_period_end=now - timedelta(days=7),
                metrics=['response_time']
            )
        assert "Current period start must be before end" in str(exc_info.value)

        # Invalid: period too long
        with pytest.raises(ValidationError) as exc_info:
            ComparativeAnalyticsQuery(
                current_period_start=now - timedelta(days=100),
                current_period_end=now,
                comparison_period_start=now - timedelta(days=200),
                comparison_period_end=now - timedelta(days=100),
                metrics=['response_time']
            )
        assert "cannot exceed 90 days" in str(exc_info.value)


class TestSecurityValidator:
    """Test security validation functions"""

    def test_string_sanitization(self):
        """Test string sanitization"""
        validator = SecurityValidator()

        # Normal strings
        assert validator.sanitize_string("normal text") == "normal text"

        # HTML entities
        assert validator.sanitize_string("test &amp; more") == "test & more"

        # SQL injection attempts
        sql_injection = "'; DROP TABLE users; --"
        sanitized = validator.sanitize_string(sql_injection)
        assert "DROP" not in sanitized
        assert "--" not in sanitized

        # XSS attempts
        xss_attempt = "<script>alert('xss')</script>"
        sanitized = validator.sanitize_string(xss_attempt)
        assert "<script>" not in sanitized
        assert "alert" not in sanitized

        # Length limits
        long_string = "a" * 1001
        with pytest.raises(AnalyticsValidationError):
            validator.sanitize_string(long_string, max_length=1000)

    def test_identifier_validation(self):
        """Test identifier validation"""
        validator = SecurityValidator()

        # Valid UUID
        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
        assert validator.validate_identifier(valid_uuid) == valid_uuid

        # Invalid UUIDs
        invalid_uuids = [
            "not-a-uuid",
            "123-456-789",
            "550e8400-e29b-41d4-a716",  # Too short
        ]

        for invalid_uuid in invalid_uuids:
            with pytest.raises(AnalyticsValidationError):
                validator.validate_identifier(invalid_uuid)

    def test_component_name_validation(self):
        """Test component name validation"""
        validator = SecurityValidator()

        # Valid component names
        valid_components = [
            "api_service",
            "search-v1",
            "cache.redis",
            "analytics/processor"
        ]

        for component in valid_components:
            assert validator.validate_component_name(component) == component

        # Invalid component names
        invalid_components = [
            "service; rm -rf /",
            "path/../../../etc/passwd",
            "component<script>alert('xss')</script>",
            "",  # Empty after sanitization
        ]

        for component in invalid_components:
            with pytest.raises(AnalyticsValidationError):
                validator.validate_component_name(component)

    def test_numeric_range_validation(self):
        """Test numeric range validation"""
        validator = SecurityValidator()

        # Valid ranges
        assert validator.validate_numeric_range(50, 0, 100) == 50
        assert validator.validate_numeric_range(0.5, 0.0, 1.0) == 0.5

        # Invalid ranges
        with pytest.raises(AnalyticsValidationError):
            validator.validate_numeric_range(-1, 0, 100)

        with pytest.raises(AnalyticsValidationError):
            validator.validate_numeric_range(150, 0, 100)

    def test_datetime_range_validation(self):
        """Test datetime range validation"""
        validator = SecurityValidator()

        start = datetime.utcnow() - timedelta(days=7)
        end = datetime.utcnow()

        # Valid range
        validated_start, validated_end = validator.validate_datetime_range(start, end)
        assert validated_start == start
        assert validated_end == end

        # Invalid: start after end
        with pytest.raises(AnalyticsValidationError):
            validator.validate_datetime_range(end, start)

        # Invalid: range too long
        far_past = datetime.utcnow() - timedelta(days=400)
        with pytest.raises(AnalyticsValidationError):
            validator.validate_datetime_range(far_past, end)


class TestQueryParameterValidator:
    """Test query parameter validation"""

    def test_pagination_validation(self):
        """Test pagination validation"""
        validator = QueryParameterValidator()

        # Valid pagination
        limit, offset = validator.validate_pagination(100, 50)
        assert limit == 100
        assert offset == 50

        # Invalid limits
        with pytest.raises(AnalyticsValidationError):
            validator.validate_pagination(0, 0)  # Limit too low

        with pytest.raises(AnalyticsValidationError):
            validator.validate_pagination(10001, 0)  # Limit too high

        # Invalid offset
        with pytest.raises(AnalyticsValidationError):
            validator.validate_pagination(100, 100001)  # Offset too high

    def test_sort_fields_validation(self):
        """Test sort fields validation"""
        validator = QueryParameterValidator()

        allowed_fields = ['timestamp', 'value', 'component', 'user_id']

        # Valid sort fields
        validated = validator.validate_sort_fields(['timestamp', 'value'], allowed_fields)
        assert validated == ['timestamp', 'value']

        # Invalid sort field
        with pytest.raises(AnalyticsValidationError):
            validator.validate_sort_fields(['invalid_field'], allowed_fields)

    def test_time_bucket_validation(self):
        """Test time bucket validation"""
        validator = QueryParameterValidator()

        valid_buckets = ['minute', 'hour', 'day', 'week', 'month']
        for bucket in valid_buckets:
            assert validator.validate_time_bucket(bucket) == bucket

        # Invalid bucket
        with pytest.raises(AnalyticsValidationError):
            validator.validate_time_bucket('invalid')


class TestAnalyticsInputSanitizer:
    """Test analytics input sanitizer"""

    def test_query_parameter_sanitization(self):
        """Test query parameter sanitization"""
        sanitizer = AnalyticsInputSanitizer()

        # Valid parameters
        params = {
            'limit': 100,
            'component': 'search_service',
            'time_range': 'last_7_days'
        }

        sanitized = sanitizer.sanitize_query_params(params)
        assert 'limit' in sanitized
        assert sanitized['component'] == 'search_service'

        # Parameters with allowed fields filter
        allowed_fields = ['limit', 'component']
        sanitized = sanitizer.sanitize_query_params(params, allowed_fields)
        assert 'limit' in sanitized
        assert 'component' in sanitized
        assert 'time_range' not in sanitized  # Not in allowed fields

        # Malicious parameters
        malicious_params = {
            'component'; "'; DROP TABLE users; --": 'value',
            'valid_field': 'normal_value'
        }

        # Should handle malicious input gracefully
        sanitized = sanitizer.sanitize_query_params(malicious_params)
        # Malicious key should be filtered out during sanitization

    def test_cache_key_generation(self):
        """Test cache key generation"""
        sanitizer = AnalyticsInputSanitizer()

        params1 = {'limit': 100, 'component': 'search'}
        params2 = {'component': 'search', 'limit': 100}  # Same params, different order
        params3 = {'limit': 50, 'component': 'search'}

        key1 = sanitizer.create_cache_key(params1)
        key2 = sanitizer.create_cache_key(params2)
        key3 = sanitizer.create_cache_key(params3)

        # Same params should generate same key regardless of order
        assert key1 == key2
        # Different params should generate different keys
        assert key1 != key3

        # Keys should be valid MD5 hashes
        assert len(key1) == 32
        assert all(c in '0123456789abcdef' for c in key1)


class TestResponseSchemas:
    """Test response schema validation"""

    def test_performance_metrics_response(self):
        """Test performance metrics response schema"""
        from src.schemas.analytics_response import TimeSeriesData, TimeSeriesPoint

        # Create time series data
        data_points = [
            TimeSeriesPoint(
                timestamp=datetime.utcnow(),
                value=100.5,
                count=10
            )
        ]

        time_series = TimeSeriesData(
            metric_name="response_time",
            unit="ms",
            data_points=data_points
        )

        metadata = ResponseMetadata(
            data_type=DataType.TIME_SERIES,
            total_records=1,
            returned_records=1,
            has_more=False
        )

        response = PerformanceMetricsResponse(
            data=time_series,
            metadata=metadata,
            execution_time_ms=150
        )

        assert response.status == ResponseStatus.SUCCESS
        assert response.execution_time_ms == 150
        assert response.data.metric_name == "response_time"

    def test_error_response(self):
        """Test error response schema"""
        error_response = ErrorResponse(
            error_code="VALIDATION_ERROR",
            error_message="Invalid input parameters",
            execution_time_ms=5
        )

        assert error_response.status == ResponseStatus.ERROR
        assert error_response.error_code == "VALIDATION_ERROR"
        assert "Invalid input" in error_response.error_message

    def test_validation_error_response(self):
        """Test validation error response schema"""
        validation_response = ValidationErrorResponse(
            error_code="VALIDATION_ERROR",
            error_message="Input validation failed",
            validation_errors={
                "limit": ["Must be between 1 and 10000"],
                "start_date": ["Required when time_range=CUSTOM"]
            },
            field_names=["limit", "start_date"],
            execution_time_ms=10
        )

        assert validation_response.status == ResponseStatus.ERROR
        assert "limit" in validation_response.validation_errors
        assert "start_date" in validation_response.field_names


if __name__ == "__main__":
    pytest.main([__file__])