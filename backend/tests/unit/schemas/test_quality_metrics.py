"""
Unit tests for quality metrics schemas
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from src.schemas.quality_metrics import (
    QualityMetricResponse,
    QualityAlertResponse,
    QualityThresholdCreate,
    QualityThresholdResponse,
    AlertAcknowledgmentRequest,
    SearchEventCreate,
    SearchEventUpdate,
    SessionCreate,
    QualityReportRequest,
    SystemHealthCheck,
    AnalyticsExportRequest
)


class TestQualityMetricResponse:
    """Test QualityMetricResponse schema"""

    def test_valid_metric_response(self):
        """Test creating a valid metric response"""
        data = {
            "id": "metric-123",
            "metric_type": "response_time",
            "metric_value": 250.5,
            "metric_unit": "ms",
            "query": "test query",
            "search_type": "semantic",
            "measured_at": "2024-01-01T10:00:00Z",
            "is_threshold_violation": False,
            "metadata": {"source": "test"}
        }
        
        metric = QualityMetricResponse(**data)
        assert metric.id == "metric-123"
        assert metric.metric_type == "response_time"
        assert metric.metric_value == 250.5
        assert metric.is_threshold_violation is False
        assert metric.metadata == {"source": "test"}

    def test_metric_response_optional_fields(self):
        """Test metric response with optional fields None"""
        data = {
            "id": "metric-456",
            "metric_type": "accuracy",
            "metric_value": 0.95,
            "query": "search query",
            "search_type": "hybrid",
            "measured_at": "2024-01-01T11:00:00Z"
        }
        
        metric = QualityMetricResponse(**data)
        assert metric.metric_unit is None
        assert metric.is_threshold_violation is False  # Default value
        assert metric.metadata is None

    def test_metric_response_required_fields(self):
        """Test that required fields are validated"""
        with pytest.raises(ValidationError) as exc_info:
            QualityMetricResponse(
                metric_type="response_time",
                metric_value=100.0
                # Missing required fields
            )
        
        error = exc_info.value
        assert "id" in str(error)
        assert "query" in str(error)
        assert "search_type" in str(error)
        assert "measured_at" in str(error)


class TestQualityAlertResponse:
    """Test QualityAlertResponse schema"""

    def test_valid_alert_response(self):
        """Test creating a valid alert response"""
        data = {
            "id": "alert-789",
            "metric_type": "response_time",
            "severity": "high",
            "title": "High Response Time",
            "message": "Response time exceeded threshold",
            "status": "active",
            "created_at": "2024-01-01T12:00:00Z",
            "acknowledged_at": "2024-01-01T12:30:00Z",
            "resolved_at": None
        }
        
        alert = QualityAlertResponse(**data)
        assert alert.id == "alert-789"
        assert alert.severity == "high"
        assert alert.status == "active"
        assert alert.acknowledged_at == "2024-01-01T12:30:00Z"
        assert alert.resolved_at is None

    def test_alert_response_optional_fields_none(self):
        """Test alert response with optional fields as None"""
        data = {
            "id": "alert-101",
            "severity": "medium",
            "title": "Test Alert",
            "message": "Test message",
            "status": "pending",
            "created_at": "2024-01-01T13:00:00Z"
        }
        
        alert = QualityAlertResponse(**data)
        assert alert.metric_type is None
        assert alert.acknowledged_at is None
        assert alert.resolved_at is None


class TestQualityThresholdCreate:
    """Test QualityThresholdCreate schema"""

    def test_valid_threshold_create(self):
        """Test creating a valid threshold"""
        data = {
            "metric_type": "response_time",
            "threshold_max": 1000.0,
            "threshold_target": 500.0,
            "alert_severity": "high",
            "is_enabled": True,
            "alert_cooldown_minutes": 30,
            "search_type": "semantic",
            "description": "Response time threshold"
        }
        
        threshold = QualityThresholdCreate(**data)
        assert threshold.metric_type == "response_time"
        assert threshold.threshold_max == 1000.0
        assert threshold.alert_severity == "high"
        assert threshold.alert_cooldown_minutes == 30

    def test_threshold_create_defaults(self):
        """Test threshold create with default values"""
        data = {
            "metric_type": "accuracy"
        }
        
        threshold = QualityThresholdCreate(**data)
        assert threshold.alert_severity == "medium"  # Default
        assert threshold.is_enabled is True  # Default
        assert threshold.alert_cooldown_minutes == 60  # Default
        assert threshold.threshold_min is None
        assert threshold.threshold_max is None
        assert threshold.threshold_target is None

    def test_threshold_create_required_field(self):
        """Test that metric_type is required"""
        with pytest.raises(ValidationError) as exc_info:
            QualityThresholdCreate()
        
        error = exc_info.value
        assert "metric_type" in str(error)

    def test_threshold_create_field_descriptions(self):
        """Test that field descriptions exist"""
        schema = QualityThresholdCreate.model_json_schema()
        properties = schema["properties"]
        
        assert "description" in properties["metric_type"]
        assert "Type of metric" in properties["metric_type"]["description"]
        assert "Alert severity level" in properties["alert_severity"]["description"]


class TestSearchEventCreate:
    """Test SearchEventCreate schema"""

    def test_valid_search_event_create(self):
        """Test creating a valid search event"""
        data = {
            "session_id": "session-123",
            "query": "test search query",
            "search_type": "semantic",
            "results_count": 15,
            "response_time": 245.7,
            "user_id": "user-456",
            "page_number": 1,
            "filters_applied": {"category": "documents"},
            "sort_order": "relevance"
        }
        
        event = SearchEventCreate(**data)
        assert event.session_id == "session-123"
        assert event.query == "test search query"
        assert event.results_count == 15
        assert event.response_time == 245.7
        assert event.page_number == 1
        assert event.filters_applied == {"category": "documents"}

    def test_search_event_create_defaults(self):
        """Test search event create with default values"""
        data = {
            "session_id": "session-789",
            "query": "minimal query",
            "search_type": "keyword",
            "results_count": 5,
            "response_time": 100.0
        }
        
        event = SearchEventCreate(**data)
        assert event.page_number == 1  # Default value
        assert event.user_id is None
        assert event.filters_applied is None
        assert event.sort_order is None

    def test_search_event_page_number_validation(self):
        """Test that page_number must be >= 1"""
        data = {
            "session_id": "session-999",
            "query": "test",
            "search_type": "semantic",
            "results_count": 10,
            "response_time": 200.0,
            "page_number": 0  # Invalid
        }
        
        with pytest.raises(ValidationError) as exc_info:
            SearchEventCreate(**data)
        
        error = exc_info.value
        assert "greater than or equal to 1" in str(error).lower()

    def test_search_event_required_fields(self):
        """Test that all required fields are validated"""
        with pytest.raises(ValidationError) as exc_info:
            SearchEventCreate(session_id="test")
        
        error = exc_info.value
        assert "query" in str(error)
        assert "search_type" in str(error)
        assert "results_count" in str(error)
        assert "response_time" in str(error)


class TestSearchEventUpdate:
    """Test SearchEventUpdate schema"""

    def test_valid_search_event_update(self):
        """Test creating a valid search event update"""
        data = {
            "clicked_results": 3,
            "clicked_result_ids": ["doc-1", "doc-2", "doc-3"],
            "time_to_first_click": 5.2,
            "dwell_time": 45.8,
            "user_rating": 4,
            "feedback_text": "Good results",
            "is_bookmarked": True
        }
        
        update = SearchEventUpdate(**data)
        assert update.clicked_results == 3
        assert update.clicked_result_ids == ["doc-1", "doc-2", "doc-3"]
        assert update.time_to_first_click == 5.2
        assert update.user_rating == 4
        assert update.is_bookmarked is True

    def test_search_event_update_defaults(self):
        """Test search event update with default values"""
        update = SearchEventUpdate()
        assert update.clicked_results == 0
        assert update.clicked_result_ids is None
        assert update.time_to_first_click is None
        assert update.dwell_time is None
        assert update.user_rating is None
        assert update.feedback_text is None
        assert update.is_bookmarked is False

    def test_search_event_update_validation(self):
        """Test validation constraints"""
        # Test clicked_results >= 0
        with pytest.raises(ValidationError):
            SearchEventUpdate(clicked_results=-1)
        
        # Test time_to_first_click >= 0
        with pytest.raises(ValidationError):
            SearchEventUpdate(time_to_first_click=-1.0)
        
        # Test dwell_time >= 0
        with pytest.raises(ValidationError):
            SearchEventUpdate(dwell_time=-5.0)
        
        # Test user_rating range 1-5
        with pytest.raises(ValidationError):
            SearchEventUpdate(user_rating=0)
        
        with pytest.raises(ValidationError):
            SearchEventUpdate(user_rating=6)


class TestQualityReportRequest:
    """Test QualityReportRequest schema"""

    def test_valid_report_request(self):
        """Test creating a valid report request"""
        data = {
            "report_type": "weekly_summary",
            "start_date": datetime(2024, 1, 1),
            "end_date": datetime(2024, 1, 7),
            "metric_types": ["response_time", "accuracy"],
            "include_alerts": True,
            "include_recommendations": False,
            "format": "pdf"
        }
        
        request = QualityReportRequest(**data)
        assert request.report_type == "weekly_summary"
        assert request.start_date == datetime(2024, 1, 1)
        assert request.end_date == datetime(2024, 1, 7)
        assert request.metric_types == ["response_time", "accuracy"]
        assert request.format == "pdf"

    def test_report_request_defaults(self):
        """Test report request with default values"""
        data = {
            "report_type": "daily",
            "start_date": datetime(2024, 1, 1),
            "end_date": datetime(2024, 1, 2)
        }
        
        request = QualityReportRequest(**data)
        assert request.metric_types is None
        assert request.include_alerts is True  # Default
        assert request.include_recommendations is True  # Default
        assert request.format == "json"  # Default

    def test_report_request_required_fields(self):
        """Test required fields validation"""
        with pytest.raises(ValidationError) as exc_info:
            QualityReportRequest(report_type="test")
        
        error = exc_info.value
        assert "start_date" in str(error)
        assert "end_date" in str(error)


class TestSystemHealthCheck:
    """Test SystemHealthCheck schema"""

    def test_valid_health_check(self):
        """Test creating a valid health check response"""
        data = {
            "status": "healthy",
            "service": "search-api",
            "timestamp": "2024-01-01T15:00:00Z",
            "version": "1.2.3",
            "uptime": 86400.5,
            "dependencies": {"database": "healthy", "redis": "healthy"},
            "features": {"search": True, "analytics": True},
            "metrics": {"cpu_usage": 45.2, "memory_usage": 67.8}
        }
        
        health = SystemHealthCheck(**data)
        assert health.status == "healthy"
        assert health.service == "search-api"
        assert health.version == "1.2.3"
        assert health.uptime == 86400.5
        assert health.dependencies == {"database": "healthy", "redis": "healthy"}

    def test_health_check_required_fields(self):
        """Test that required fields are validated"""
        with pytest.raises(ValidationError) as exc_info:
            SystemHealthCheck(status="healthy")
        
        error = exc_info.value
        assert "service" in str(error)
        assert "timestamp" in str(error)
        assert "dependencies" in str(error)
        assert "features" in str(error)
        assert "metrics" in str(error)

    def test_health_check_optional_fields(self):
        """Test health check with optional fields None"""
        data = {
            "status": "unhealthy",
            "service": "test-service",
            "timestamp": "2024-01-01T16:00:00Z",
            "dependencies": {},
            "features": {},
            "metrics": {}
        }
        
        health = SystemHealthCheck(**data)
        assert health.version is None
        assert health.uptime is None


class TestAnalyticsExportRequest:
    """Test AnalyticsExportRequest schema"""

    def test_valid_export_request(self):
        """Test creating a valid export request"""
        data = {
            "data_type": "search_events",
            "start_date": datetime(2024, 1, 1),
            "end_date": datetime(2024, 1, 31),
            "format": "csv",
            "filters": {"user_type": "premium"},
            "include_metadata": False
        }
        
        export_req = AnalyticsExportRequest(**data)
        assert export_req.data_type == "search_events"
        assert export_req.format == "csv"
        assert export_req.filters == {"user_type": "premium"}
        assert export_req.include_metadata is False

    def test_export_request_defaults(self):
        """Test export request with default values"""
        data = {
            "data_type": "metrics",
            "start_date": datetime(2024, 1, 1),
            "end_date": datetime(2024, 1, 2)
        }
        
        export_req = AnalyticsExportRequest(**data)
        assert export_req.format == "csv"  # Default
        assert export_req.filters is None
        assert export_req.include_metadata is True  # Default

    def test_export_request_required_fields(self):
        """Test required fields validation"""
        with pytest.raises(ValidationError):
            AnalyticsExportRequest(data_type="test")


class TestAlertAcknowledgmentRequest:
    """Test AlertAcknowledgmentRequest schema"""

    def test_valid_acknowledgment_request(self):
        """Test creating a valid acknowledgment request"""
        data = {"note": "Acknowledged and investigating"}
        
        ack = AlertAcknowledgmentRequest(**data)
        assert ack.note == "Acknowledged and investigating"

    def test_acknowledgment_request_optional_note(self):
        """Test acknowledgment request without note"""
        ack = AlertAcknowledgmentRequest()
        assert ack.note is None

    def test_acknowledgment_request_empty_dict(self):
        """Test acknowledgment request with empty data"""
        ack = AlertAcknowledgmentRequest(**{})
        assert ack.note is None


class TestSessionCreate:
    """Test SessionCreate schema"""

    def test_valid_session_create(self):
        """Test creating a valid session"""
        data = {
            "session_id": "sess-123",
            "user_id": "user-456",
            "user_agent": "Mozilla/5.0...",
            "ip_address": "192.168.1.100",
            "referrer": "https://example.com"
        }
        
        session = SessionCreate(**data)
        assert session.session_id == "sess-123"
        assert session.user_id == "user-456"
        assert session.user_agent == "Mozilla/5.0..."
        assert session.ip_address == "192.168.1.100"
        assert session.referrer == "https://example.com"

    def test_session_create_optional_fields(self):
        """Test session create with only required field"""
        data = {"session_id": "sess-789"}
        
        session = SessionCreate(**data)
        assert session.session_id == "sess-789"
        assert session.user_id is None
        assert session.user_agent is None
        assert session.ip_address is None
        assert session.referrer is None

    def test_session_create_required_field(self):
        """Test that session_id is required"""
        with pytest.raises(ValidationError) as exc_info:
            SessionCreate()
        
        error = exc_info.value
        assert "session_id" in str(error)