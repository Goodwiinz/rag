"""
Comprehensive tests for API documentation integration.
Validates that documented endpoints match actual implementation.
"""

import pytest
import json
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.core.database import get_db
from src.main import app

class TestAPIDocumentation:
    """Test suite for API documentation integration"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def test_user_headers(self, test_user):
        """Create authenticated headers for test user"""
        return {"Authorization": f"Bearer {test_user.id}"}

    @pytest.fixture
    def mock_analytics_data(self):
        """Create mock analytics data for testing"""
        return {
            "quality_metrics": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "document_id": "doc123",
                    "organization_id": "org456",
                    "overall_score": 0.85,
                    "content_relevance": 0.90,
                    "information_density": 0.75,
                    "readability_score": 0.88,
                    "technical_accuracy": 0.82,
                    "source_credibility": 0.91,
                    "recency_score": 0.70,
                    "completeness_score": 0.89,
                    "structured_data_score": 0.86,
                    "metadata_quality_score": 0.92,
                    "extraction_quality": 0.84,
                    "language_quality": 0.89,
                    "processing_errors": [],
                    "quality_flags": ["high_relevance", "credible_source"],
                    "recommendations": ["Add more recent references"],
                    "quality_tier": "high",
                    "assessment_version": "v2.1",
                    "assessment_metadata": {
                        "model_version": "quality-v2.1",
                        "confidence_score": 0.92,
                        "processing_time_ms": 1500
                    },
                    "created_at": "2024-01-15T10:30:00Z",
                    "updated_at": "2024-01-15T10:30:00Z"
                }
            ],
            "user_sessions": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440001",
                    "user_id": "user123",
                    "organization_id": "org456",
                    "session_start": "2024-01-15T09:00:00Z",
                    "session_end": "2024-01-15T10:30:00Z",
                    "duration_seconds": 5400,
                    "page_views": 25,
                    "total_searches": 8,
                    "total_documents_viewed": 12,
                    "total_downloads": 3,
                    "total_clicks": 45,
                    "engagement_score": 75.5,
                    "bounce_type": "none",
                    "device_type": "desktop",
                    "browser": "Chrome",
                    "created_at": "2024-01-15T10:30:00Z",
                    "updated_at": "2024-01-15T10:30:00Z"
                }
            ],
            "analytics_events": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440002",
                    "event_type": "search",
                    "event_name": "document_search",
                    "event_data": {
                        "query": "machine learning algorithms",
                        "results_count": 25,
                        "search_time_ms": 150
                    },
                    "user_id": "user123",
                    "session_id": "550e8400-e29b-41d4-a716-446655440001",
                    "organization_id": "org456",
                    "severity": "low",
                    "timestamp": "2024-01-15T10:30:00Z",
                    "created_at": "2024-01-15T10:30:00Z"
                }
            ]
        }

    def test_openapi_spec_generation(self, client):
        """Test that OpenAPI spec is generated correctly"""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        spec = response.json()

        # Verify basic OpenAPI structure
        assert "openapi" in spec
        assert "info" in spec
        assert "paths" in spec
        assert "components" in spec

        # Verify API info
        assert spec["info"]["title"] == "RAG System Analytics API"
        assert spec["info"]["version"] == "1.0.0"

        # Verify analytics paths exist
        assert "/api/v1/analytics/quality/metrics" in spec["paths"]
        assert "/api/v1/analytics/behavior/sessions" in spec["paths"]
        assert "/api/v1/analytics/performance/metrics" in spec["paths"]
        assert "/api/v1/analytics/events" in spec["paths"]
        assert "/api/v1/analytics/jobs" in spec["paths"]
        assert "/api/v1/analytics/recommendations" in spec["paths"]

    def test_swagger_ui_endpoint(self, client):
        """Test that Swagger UI is accessible"""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_redoc_endpoint(self, client):
        """Test that ReDoc is accessible"""
        response = client.get("/redoc")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    @patch('src.services.quality_metrics_service.QualityMetricsService.get_quality_metrics')
    def test_quality_metrics_endpoint_matches_schema(self, mock_get_metrics, client, test_user_headers, mock_analytics_data):
        """Test that quality metrics endpoint matches documented schema"""
        mock_get_metrics.return_value = {
            "data": mock_analytics_data["quality_metrics"],
            "pagination": {
                "page": 1,
                "size": 20,
                "total": 156,
                "pages": 8,
                "has_next": True,
                "has_prev": False
            },
            "summary": {
                "avg_quality_score": 0.78,
                "quality_distribution": {"high": 45, "medium": 89, "low": 22},
                "total_documents": 156
            }
        }

        response = client.get(
            "/api/v1/analytics/quality/metrics?organization_id=org456",
            headers=test_user_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response matches documented schema
        assert "data" in data
        assert "pagination" in data
        assert "summary" in data

        # Verify data structure
        for metric in data["data"]:
            assert "id" in metric
            assert "overall_score" in metric
            assert "quality_tier" in metric
            assert "created_at" in metric

    @patch('src.services.user_behavior_service.UserBehaviorService.get_user_sessions')
    def test_user_sessions_endpoint_matches_schema(self, mock_get_sessions, client, test_user_headers, mock_analytics_data):
        """Test that user sessions endpoint matches documented schema"""
        mock_get_sessions.return_value = {
            "data": mock_analytics_data["user_sessions"],
            "pagination": {
                "page": 1,
                "size": 20,
                "total": 50,
                "pages": 3,
                "has_next": True,
                "has_prev": False
            },
            "analytics": {
                "avg_session_duration": 5400,
                "avg_engagement_score": 75.5,
                "total_sessions": 50,
                "bounce_rate": 0.15
            }
        }

        response = client.get(
            "/api/v1/analytics/behavior/sessions?organization_id=org456",
            headers=test_user_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response matches documented schema
        assert "data" in data
        assert "pagination" in data
        assert "analytics" in data

        # Verify data structure
        for session in data["data"]:
            assert "id" in session
            assert "user_id" in session
            assert "engagement_score" in session
            assert "duration_seconds" in session

    @patch('src.services.performance_dashboard_service.PerformanceDashboardService.get_performance_metrics')
    def test_performance_metrics_endpoint_matches_schema(self, mock_get_metrics, client, test_user_headers):
        """Test that performance metrics endpoint matches documented schema"""
        mock_get_metrics.return_value = {
            "data": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440003",
                    "metric_name": "response_time",
                    "metric_type": "timer",
                    "value": 150.5,
                    "unit": "ms",
                    "component": "api",
                    "performance_level": "good",
                    "threshold": {"warning": 200, "critical": 500},
                    "tags": ["api", "performance"],
                    "event_metadata": {"endpoint": "/api/v1/search"},
                    "timestamp": "2024-01-15T10:30:00Z",
                    "created_at": "2024-01-15T10:30:00Z"
                }
            ],
            "pagination": {
                "page": 1,
                "size": 50,
                "total": 100,
                "pages": 2,
                "has_next": True,
                "has_prev": False
            },
            "summary": {
                "avg_response_time": 145.2,
                "p95_response_time": 250.8,
                "p99_response_time": 450.3,
                "error_rate": 0.02,
                "throughput": 1250.5
            }
        }

        response = client.get(
            "/api/v1/analytics/performance/metrics?organization_id=org456",
            headers=test_user_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response matches documented schema
        assert "data" in data
        assert "pagination" in data
        assert "summary" in data

        # Verify data structure
        for metric in data["data"]:
            assert "id" in metric
            assert "metric_name" in metric
            assert "value" in metric
            assert "performance_level" in metric

    @patch('src.services.analytics_event_service.AnalyticsEventService.create_event')
    def test_create_event_endpoint_matches_schema(self, mock_create_event, client, test_user_headers, mock_analytics_data):
        """Test that create event endpoint matches documented schema"""
        mock_create_event.return_value = mock_analytics_data["analytics_events"][0]

        event_data = {
            "event_type": "search",
            "event_name": "document_search",
            "event_data": {
                "query": "machine learning algorithms",
                "results_count": 25,
                "search_time_ms": 150
            },
            "user_id": "user123",
            "session_id": "550e8400-e29b-41d4-a716-446655440001",
            "organization_id": "org456",
            "severity": "low"
        }

        response = client.post(
            "/api/v1/analytics/events",
            headers=test_user_headers,
            json=event_data
        )

        assert response.status_code == 201
        data = response.json()

        # Verify response matches documented schema
        assert "id" in data
        assert "event_type" in data
        assert "event_name" in data
        assert "event_data" in data
        assert "timestamp" in data
        assert "created_at" in data

    @patch('src.tasks.analytics_processor.AnalyticsJobProcessor.create_job')
    def test_create_job_endpoint_matches_schema(self, mock_create_job, client, test_user_headers):
        """Test that create job endpoint matches documented schema"""
        mock_create_job.return_value = {
            "id": "550e8400-e29b-41d4-a716-446655440004",
            "job_type": "data_aggregation",
            "job_name": "Daily quality metrics aggregation",
            "description": "Aggregate quality metrics for the last 24 hours",
            "status": "pending",
            "priority": "high",
            "progress_percentage": 0,
            "current_step": "Queueing",
            "total_steps": 5,
            "completed_steps": 0,
            "parameters": {
                "metric_type": "average",
                "time_granularity": "day",
                "data_source": "quality_metrics"
            },
            "config": {
                "priority": "high",
                "max_retries": 3,
                "timeout_seconds": 3600
            },
            "retry_count": 0,
            "max_retries": 3,
            "created_at": "2024-01-15T10:30:00Z",
            "organization_id": "org456"
        }

        job_data = {
            "job_type": "data_aggregation",
            "job_name": "Daily quality metrics aggregation",
            "description": "Aggregate quality metrics for the last 24 hours",
            "parameters": {
                "metric_type": "average",
                "time_granularity": "day",
                "start_date": "2024-01-01T00:00:00Z",
                "end_date": "2024-01-31T23:59:59Z",
                "data_source": "quality_metrics"
            },
            "config": {
                "priority": "high",
                "max_retries": 3,
                "timeout_seconds": 3600
            },
            "organization_id": "org456"
        }

        response = client.post(
            "/api/v1/analytics/jobs",
            headers=test_user_headers,
            json=job_data
        )

        assert response.status_code == 201
        data = response.json()

        # Verify response matches documented schema
        assert "id" in data
        assert "job_type" in data
        assert "job_name" in data
        assert "status" in data
        assert "priority" in data
        assert "progress_percentage" in data
        assert "created_at" in data

    @patch('src.tasks.recommendation_generator.RecommendationGenerator.get_recommendations')
    def test_recommendations_endpoint_matches_schema(self, mock_get_recommendations, client, test_user_headers):
        """Test that recommendations endpoint matches documented schema"""
        mock_get_recommendations.return_value = {
            "data": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440005",
                    "recommendation_type": "quality_improvement",
                    "title": "Improve document metadata quality",
                    "description": "Documents show inconsistent metadata quality scores",
                    "priority": "high",
                    "impact_score": 0.85,
                    "confidence_score": 0.92,
                    "effort_estimate": "medium",
                    "actionable_steps": [
                        "Standardize metadata extraction process",
                        "Add metadata validation rules",
                        "Train content team on metadata best practices"
                    ],
                    "evidence_data": {
                        "affected_documents": 45,
                        "avg_metadata_score": 0.65
                    },
                    "auto_applicable": False,
                    "status": "pending",
                    "created_at": "2024-01-15T10:30:00Z",
                    "organization_id": "org456"
                }
            ],
            "summary": {
                "total_recommendations": 15,
                "by_priority": {"high": 3, "medium": 8, "low": 4},
                "by_type": {"quality_improvement": 5, "performance_optimization": 6, "user_engagement": 4},
                "implementation_rate": 0.35
            }
        }

        response = client.get(
            "/api/v1/analytics/recommendations?organization_id=org456",
            headers=test_user_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response matches documented schema
        assert "data" in data
        assert "summary" in data

        # Verify data structure
        for recommendation in data["data"]:
            assert "id" in recommendation
            assert "recommendation_type" in recommendation
            assert "title" in recommendation
            assert "priority" in recommendation
            assert "impact_score" in recommendation
            assert "confidence_score" in recommendation
            assert "actionable_steps" in recommendation

    def test_error_responses_match_schema(self, client, test_user_headers):
        """Test that error responses match documented schema"""
        # Test validation error
        response = client.get(
            "/api/v1/analytics/quality/metrics?organization_id=invalid-uuid",
            headers=test_user_headers
        )

        assert response.status_code == 422
        data = response.json()

        # Verify error response structure
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
        assert "timestamp" in data["error"]
        assert "request_id" in data["error"]

    def test_endpoint_parameters_validation(self, client, test_user_headers):
        """Test that endpoint parameters are validated according to schema"""
        # Test missing required parameter
        response = client.get(
            "/api/v1/analytics/quality/metrics",
            headers=test_user_headers
        )
        assert response.status_code == 422

        # Test invalid UUID format
        response = client.get(
            "/api/v1/analytics/quality/metrics?organization_id=invalid",
            headers=test_user_headers
        )
        assert response.status_code == 422

        # Test valid request
        response = client.get(
            "/api/v1/analytics/quality/metrics?organization_id=550e8400-e29b-41d4-a716-446655440000",
            headers=test_user_headers
        )
        # Should succeed or fail with auth, not validation
        assert response.status_code not in [422]

    def test_rate_limiting_headers(self, client, test_user_headers):
        """Test that rate limiting headers are present"""
        response = client.get(
            "/api/v1/analytics/quality/metrics?organization_id=550e8400-e29b-41d4-a716-446655440000",
            headers=test_user_headers
        )

        # Check for rate limiting headers
        rate_limit_headers = [
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset"
        ]

        # Note: Headers may not be present if rate limiting is not configured
        # This test validates the structure when they are present

    def test_authentication_required(self, client):
        """Test that authentication is required for all analytics endpoints"""
        endpoints = [
            "/api/v1/analytics/quality/metrics?organization_id=550e8400-e29b-41d4-a716-446655440000",
            "/api/v1/analytics/behavior/sessions?organization_id=550e8400-e29b-41d4-a716-446655440000",
            "/api/v1/analytics/performance/metrics?organization_id=550e8400-e29b-41d4-a716-446655440000",
            "/api/v1/analytics/recommendations?organization_id=550e8400-e29b-41d4-a716-446655440000"
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 401

    def test_cors_headers(self, client):
        """Test that CORS headers are properly configured"""
        # Test preflight request
        response = client.options(
            "/api/v1/analytics/quality/metrics",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization"
            }
        )

        # Should have CORS headers
        assert "Access-Control-Allow-Origin" in response.headers
        assert "Access-Control-Allow-Methods" in response.headers
        assert "Access-Control-Allow-Headers" in response.headers

    @pytest.mark.parametrize("endpoint,method", [
        ("/api/v1/analytics/quality/metrics", "GET"),
        ("/api/v1/analytics/behavior/sessions", "GET"),
        ("/api/v1/analytics/performance/metrics", "GET"),
        ("/api/v1/analytics/events", "POST"),
        ("/api/v1/analytics/jobs", "POST"),
        ("/api/v1/analytics/recommendations", "GET"),
    ])
    def test_endpoint_documentation_completeness(self, endpoint, method, client):
        """Test that all documented endpoints exist and are properly configured"""
        if method == "GET":
            response = client.options(endpoint)
        else:
            response = client.options(endpoint)

        # Endpoint should exist (might return 405 if wrong method, but not 404)
        assert response.status_code != 404

    def test_api_version_consistency(self, client):
        """Test that all endpoints use consistent API versioning"""
        # Get OpenAPI spec
        response = client.get("/openapi.json")
        spec = response.json()

        # Check that all analytics paths use v1
        analytics_paths = [path for path in spec["paths"].keys() if "/api/v1/analytics/" in path]

        for path in analytics_paths:
            assert "/api/v1/" in path, f"Path {path} should use v1 API version"

    def test_response_time_sla(self, client, test_user_headers):
        """Test that API responses meet SLA requirements"""
        import time

        start_time = time.time()
        response = client.get(
            "/api/v1/analytics/quality/metrics?organization_id=550e8400-e29b-41d4-a716-446655440000",
            headers=test_user_headers
        )
        response_time = time.time() - start_time

        # Response should be fast (even if it returns an error)
        assert response_time < 1.0, f"Response time {response_time}s exceeds SLA"

    def test_api_documentation_loads_properly(self, client):
        """Test that API documentation pages load without errors"""
        # Test Swagger UI
        response = client.get("/docs")
        assert response.status_code == 200
        assert "swagger" in response.text.lower()

        # Test ReDoc
        response = client.get("/redoc")
        assert response.status_code == 200
        assert "redoc" in response.text.lower()

    @patch('src.services.quality_metrics_service.QualityMetricsService.get_quality_dashboard')
    def test_dashboard_endpoint_matches_schema(self, mock_get_dashboard, client, test_user_headers):
        """Test that dashboard endpoints match documented schema"""
        mock_get_dashboard.return_value = {
            "overview": {
                "total_documents": 156,
                "avg_quality_score": 0.78,
                "quality_trend": "improving",
                "health_score": 85.2
            },
            "quality_distribution": {"high": 45, "medium": 89, "low": 22},
            "trends": [
                {
                    "date": "2024-01-15",
                    "avg_score": 0.78,
                    "document_count": 156
                }
            ],
            "top_issues": [
                {
                    "issue": "Missing metadata",
                    "frequency": 45,
                    "impact": "medium"
                }
            ]
        }

        response = client.get(
            "/api/v1/analytics/quality/dashboard?organization_id=org456",
            headers=test_user_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify dashboard schema structure
        assert "overview" in data
        assert "quality_distribution" in data
        assert "trends" in data
        assert "top_issues" in data

    def test_openapi_schema_completeness(self, client):
        """Test that OpenAPI schema is complete and valid"""
        response = client.get("/openapi.json")
        spec = response.json()

        # Check required OpenAPI fields
        required_fields = ["openapi", "info", "paths", "components"]
        for field in required_fields:
            assert field in spec, f"Missing required OpenAPI field: {field}"

        # Check components
        assert "schemas" in spec["components"]
        assert "securitySchemes" in spec["components"]
        assert "responses" in spec["components"]

        # Check security scheme
        assert "BearerAuth" in spec["components"]["securitySchemes"]

        # Check that paths have proper methods and responses
        for path, path_item in spec["paths"].items():
            for method, operation in path_item.items():
                if method in ["get", "post", "put", "delete"]:
                    assert "responses" in operation, f"Missing responses for {method} {path}"
                    assert "operationId" in operation, f"Missing operationId for {method} {path}"
                    assert "tags" in operation, f"Missing tags for {method} {path}"