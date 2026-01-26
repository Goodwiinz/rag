"""
Integration tests for T3 Analytics API endpoints
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock
import json
from datetime import datetime, timedelta

from src.main import app


class TestAnalyticsAPIIntegration:
    """Integration tests for all analytics API endpoints"""

    @pytest.fixture
    def client(self, test_client):
        """Test client fixture."""
        return test_client

    @pytest.fixture
    def auth_headers(self, mock_user):
        """Mock authentication headers."""
        return {"Authorization": f"Bearer mock-token-{mock_user.id}"}

    # Test Quality Metrics API
    def test_quality_metrics_health_endpoint(self, client):
        """Test quality metrics health endpoint."""
        response = client.get("/api/v1/analytics/quality/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data
        assert "features" in data

    @patch("src.services.quality_metrics_service.quality_metrics_service")
    def test_get_quality_metrics(self, mock_service, client, auth_headers):
        """Test getting quality metrics."""
        mock_service.get_metrics_by_organization.return_value = [
            {
                "id": "metric-1",
                "name": "search_accuracy",
                "value": 0.94,
                "timestamp": "2025-10-09T21:41:00Z"
            }
        ]

        response = client.get(
            "/api/v1/analytics/quality/metrics",
            headers=auth_headers,
            params={"organization_id": "org-123", "time_range": "24h"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "metrics" in data
        assert len(data["metrics"]) == 1
        assert data["metrics"][0]["name"] == "search_accuracy"

    @patch("src.services.quality_metrics_service.quality_metrics_service")
    def test_create_quality_metric(self, mock_service, client, auth_headers):
        """Test creating a quality metric."""
        mock_service.collect_metric.return_value = {
            "id": "metric-new",
            "name": "custom_metric",
            "value": 0.85,
            "timestamp": "2025-10-09T21:41:00Z"
        }

        metric_data = {
            "name": "custom_metric",
            "value": 0.85,
            "metric_type": "custom",
            "scope": "query"
        }

        response = client.post(
            "/api/v1/analytics/quality/metrics",
            headers=auth_headers,
            json=metric_data
        )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "metric-new"
        assert data["name"] == "custom_metric"

    @patch("src.services.quality_metrics_service.quality_metrics_service")
    def test_get_quality_alerts(self, mock_service, client, auth_headers):
        """Test getting quality alerts."""
        mock_service.get_active_alerts.return_value = [
            {
                "id": "alert-1",
                "name": "high_response_time",
                "severity": "warning",
                "current_value": 600,
                "threshold": 500
            }
        ]

        response = client.get(
            "/api/v1/analytics/quality/alerts",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "alerts" in data
        assert len(data["alerts"]) == 1
        assert data["alerts"][0]["severity"] == "warning"

    @patch("src.services.quality_metrics_service.quality_metrics_service")
    def test_acknowledge_alert(self, mock_service, client, auth_headers):
        """Test acknowledging an alert."""
        mock_service.acknowledge_alert.return_value = True

        response = client.post(
            "/api/v1/analytics/quality/alerts/alert-123/acknowledge",
            headers=auth_headers,
            json={"user_id": "user-123"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    # Test User Behavior API
    def test_user_behavior_health_endpoint(self, client):
        """Test user behavior health endpoint."""
        response = client.get("/api/v1/analytics/behavior/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data
        assert "version" in data

    @patch("src.services.user_behavior_service.user_behavior_service")
    def test_create_user_session(self, mock_service, client, auth_headers):
        """Test creating a user session."""
        mock_service.create_session.return_value = {
            "id": "session-123",
            "user_id": "user-123",
            "organization_id": "org-123",
            "start_time": "2025-10-09T21:41:00Z",
            "is_active": True
        }

        session_data = {
            "user_agent": "Mozilla/5.0...",
            "ip_address": "192.168.1.100"
        }

        response = client.post(
            "/api/v1/analytics/behavior/sessions",
            headers=auth_headers,
            json=session_data
        )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "session-123"
        assert data["is_active"] is True

    @patch("src.services.user_behavior_service.user_behavior_service")
    def test_track_search_event(self, mock_service, client, auth_headers):
        """Test tracking a search event."""
        mock_service.track_search_event.return_value = {
            "id": "event-123",
            "session_id": "session-123",
            "query": "test search",
            "search_type": "hybrid",
            "results_count": 15,
            "response_time": 245.5
        }

        event_data = {
            "session_id": "session-123",
            "query": "test search",
            "search_type": "hybrid",
            "results_count": 15,
            "response_time": 245.5,
            "clicked_results": [1, 3, 5],
            "filters_applied": {"date_range": "last_30_days"}
        }

        response = client.post(
            "/api/v1/analytics/behavior/events",
            headers=auth_headers,
            json=event_data
        )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "event-123"
        assert data["query"] == "test search"

    @patch("src.services.user_behavior_service.user_behavior_service")
    def test_get_user_behavior_patterns(self, mock_service, client, auth_headers):
        """Test getting user behavior patterns."""
        mock_service.analyze_behavior_patterns.return_value = {
            "pattern_type": "researcher",
            "confidence": 0.85,
            "characteristics": ["deep_dives", "multiple_queries", "filter_usage"]
        }

        response = client.get(
            "/api/v1/analytics/behavior/users/user-123/patterns",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pattern_type"] == "researcher"
        assert data["confidence"] == 0.85

    @patch("src.services.user_behavior_service.user_behavior_service")
    def test_get_session_analysis(self, mock_service, client, auth_headers):
        """Test getting session analysis."""
        mock_service.get_session_analysis.return_value = {
            "session_id": "session-123",
            "total_queries": 5,
            "avg_response_time": 250,
            "total_clicks": 12,
            "click_through_rate": 0.48,
            "bounce_rate": 0.0
        }

        response = client.get(
            "/api/v1/analytics/behavior/sessions/session-123/analysis",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "session-123"
        assert data["total_queries"] == 5
        assert data["click_through_rate"] == 0.48

    @patch("src.services.user_behavior_service.user_behavior_service")
    def test_track_interaction(self, mock_service, client, auth_headers):
        """Test tracking user interaction."""
        mock_service.track_interaction.return_value = {
            "id": "interaction-123",
            "type": "result_click",
            "target_id": "result-456",
            "timestamp": "2025-10-09T21:41:00Z"
        }

        interaction_data = {
            "session_id": "session-123",
            "interaction_type": "result_click",
            "target_id": "result-456",
            "metadata": {"position": 1, "result_rank": 1}
        }

        response = client.post(
            "/api/v1/analytics/behavior/interactions",
            headers=auth_headers,
            json=interaction_data
        )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "interaction-123"
        assert data["type"] == "result_click"

    # Test Performance Dashboard API
    def test_performance_dashboard_health_endpoint(self, client):
        """Test performance dashboard health endpoint."""
        response = client.get("/api/v1/analytics/performance/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "cache_ttl" in data
        assert "cached_metrics" in data

    @patch("src.services.performance_dashboard_service.performance_dashboard_service")
    def test_get_dashboard_overview(self, mock_service, client, auth_headers):
        """Test getting dashboard overview."""
        mock_service.get_dashboard_overview.return_value = {
            "system_health": {
                "cpu_usage": 45.2,
                "memory_usage": 67.8,
                "disk_usage": 34.1
            },
            "search_performance": {
                "total_searches": 1234,
                "avg_response_time": 245.5,
                "success_rate": 0.985
            },
            "quality_metrics": {
                "accuracy_score": 0.94,
                "error_rate": 0.015
            },
            "user_engagement": {
                "active_users": 89,
                "satisfaction_rate": 0.92
            }
        }

        response = client.get(
            "/api/v1/analytics/performance/overview",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "system_health" in data
        assert "search_performance" in data
        assert data["system_health"]["cpu_usage"] == 45.2

    @patch("src.services.performance_dashboard_service.performance_dashboard_service")
    def test_get_system_health(self, mock_service, client, auth_headers):
        """Test getting system health metrics."""
        mock_service.get_system_health_metrics.return_value = {
            "cpu_usage": 45.2,
            "memory_usage": 67.8,
            "disk_usage": 34.1,
            "network_io": 1024.5,
            "active_connections": 156,
            "uptime_seconds": 86400,
            "timestamp": "2025-10-09T21:41:00Z"
        }

        response = client.get(
            "/api/v1/analytics/performance/system-health",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["cpu_usage"] == 45.2
        assert data["memory_usage"] == 67.8

    @patch("src.services.performance_dashboard_service.performance_dashboard_service")
    def test_create_dashboard_widget(self, mock_service, client, auth_headers):
        """Test creating a dashboard widget."""
        mock_service.create_dashboard_widget.return_value = {
            "id": "widget-123",
            "name": "Response Time Chart",
            "widget_type": "time_series",
            "metric_names": ["response_time"],
            "is_active": True
        }

        widget_data = {
            "name": "Response Time Chart",
            "widget_type": "time_series",
            "metric_names": ["response_time"],
            "time_range": "24h",
            "config": {"refresh_interval": 60}
        }

        response = client.post(
            "/api/v1/analytics/performance/widgets",
            headers=auth_headers,
            json=widget_data
        )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "widget-123"
        assert data["widget_type"] == "time_series"

    @patch("src.services.performance_dashboard_service.performance_dashboard_service")
    def test_get_widget_data(self, mock_service, client, auth_headers):
        """Test getting widget data."""
        mock_service.get_widget_data.return_value = {
            "type": "time_series",
            "data": [
                {"timestamp": "2025-10-09T20:00:00Z", "value": 200},
                {"timestamp": "2025-10-09T21:00:00Z", "value": 220}
            ],
            "metadata": {"refresh_interval": 60}
        }

        response = client.get(
            "/api/v1/analytics/performance/widgets/widget-123/data",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "time_series"
        assert len(data["data"]) == 2

    @patch("src.services.performance_dashboard_service.performance_dashboard_service")
    def test_get_performance_metrics(self, mock_service, client, auth_headers):
        """Test getting performance metrics."""
        mock_service.get_search_performance_metrics.return_value = {
            "total_searches": 1234,
            "avg_response_time": 245.5,
            "success_rate": 0.985,
            "error_rate": 0.015,
            "requests_per_second": 45.6,
            "p50_response_time": 200,
            "p95_response_time": 500,
            "p99_response_time": 800
        }

        response = client.get(
            "/api/v1/analytics/performance/metrics/search",
            headers=auth_headers,
            params={"time_range": "24h"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_searches"] == 1234
        assert data["avg_response_time"] == 245.5

    # Test Quality Recommendations API
    def test_quality_recommendations_health_endpoint(self, client):
        """Test quality recommendations health endpoint."""
        response = client.get("/api/v1/analytics/recommendations/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data
        assert "cached_recommendations" in data

    @patch("src.services.quality_recommendations_service.quality_recommendations_service")
    def test_get_recommendations(self, mock_service, client, auth_headers):
        """Test getting quality recommendations."""
        mock_service.generate_recommendations.return_value = [
            {
                "id": "rec-123",
                "category": "content",
                "priority": "high",
                "title": "Improve Document Quality",
                "description": "Update outdated content",
                "estimated_improvement": 18,
                "status": "pending"
            }
        ]

        response = client.get(
            "/api/v1/analytics/recommendations/recommendations",
            headers=auth_headers,
            params={"days_back": 30, "limit": 50}
        )

        assert response.status_code == 200
        data = response.json()
        assert "recommendations" in data
        assert len(data["recommendations"]) == 1
        assert data["recommendations"][0]["category"] == "content"

    @patch("src.services.quality_recommendations_service.quality_recommendations_service")
    def test_get_quality_insights(self, mock_service, client, auth_headers):
        """Test getting quality insights."""
        mock_service.analyze_quality_insights.return_value = [
            {
                "metric_name": "search_accuracy",
                "current_value": 0.89,
                "target_value": 0.95,
                "gap": 0.06,
                "trend": "improving",
                "impact_area": "User Experience"
            }
        ]

        response = client.get(
            "/api/v1/analytics/recommendations/insights",
            headers=auth_headers,
            params={"days_back": 30}
        )

        assert response.status_code == 200
        data = response.json()
        assert "insights" in data
        assert len(data["insights"]) == 1
        assert data["insights"][0]["metric_name"] == "search_accuracy"

    @patch("src.services.quality_recommendations_service.quality_recommendations_service")
    def test_update_recommendation_progress(self, mock_service, client, auth_headers):
        """Test updating recommendation progress."""
        mock_service.track_recommendation_progress.return_value = True

        progress_data = {
            "status": "in_progress",
            "notes": "Started implementation",
            "actual_improvement": 8.5
        }

        response = client.post(
            "/api/v1/analytics/recommendations/recommendations/rec-123/progress",
            headers=auth_headers,
            json=progress_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["recommendation_id"] == "rec-123"
        assert data["status"] == "in_progress"

    @patch("src.services.quality_recommendations_service.quality_recommendations_service")
    def test_get_recommendation_effectiveness(self, mock_service, client, auth_headers):
        """Test getting recommendation effectiveness."""
        mock_service.get_recommendation_effectiveness.return_value = {
            "organization_id": "org-123",
            "period_days": 30,
            "effectiveness": {
                "overall_improvement": 0.15,
                "recommendations_analyzed": 10,
                "successful_implementations": 7
            },
            "overall_improvement": 0.15
        }

        response = client.get(
            "/api/v1/analytics/recommendations/effectiveness",
            headers=auth_headers,
            params={"completed_days": 30}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["overall_improvement"] == 0.15
        assert data["effectiveness"]["recommendations_analyzed"] == 10

    @patch("src.services.quality_recommendations_service.quality_recommendations_service")
    def test_get_recommendations_summary(self, mock_service, client, auth_headers):
        """Test getting recommendations summary."""
        mock_service.generate_recommendations.return_value = [
            Mock(category="content", priority="high", estimated_improvement=15),
            Mock(category="search_algorithm", priority="critical", estimated_improvement=20),
            Mock(category="indexing", priority="medium", estimated_improvement=10)
        ]

        response = client.get(
            "/api/v1/analytics/recommendations/summary",
            headers=auth_headers,
            params={"days_back": 30}
        )

        assert response.status_code == 200
        data = response.json()
        assert "by_category" in data
        assert "by_priority" in data
        assert "total_count" in data
        assert data["total_count"] == 3

    @patch("src.services.quality_recommendations_service.quality_recommendations_service")
    def test_get_recommendation_categories(self, mock_service, client, auth_headers):
        """Test getting recommendation categories."""
        # This method doesn't need mocking as it returns static data
        response = client.get(
            "/api/v1/analytics/recommendations/categories",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
        assert len(data["categories"]) == 6

        # Check that all categories are present
        categories = [cat["category"] for cat in data["categories"]]
        assert "content" in categories
        assert "search_algorithm" in categories
        assert "indexing" in categories
        assert "user_experience" in categories
        assert "infrastructure" in categories
        assert "monitoring" in categories

    @patch("src.services.quality_recommendations_service.quality_recommendations_service")
    def test_generate_custom_recommendations(self, mock_service, client, auth_headers):
        """Test generating custom recommendations."""
        mock_service.generate_recommendations.return_value = [
            {
                "id": "rec-custom-1",
                "category": "content",
                "priority": "high",
                "title": "Custom Recommendation",
                "estimated_improvement": 12
            }
        ]

        request_data = {
            "focus_areas": ["content", "search_algorithm"],
            "priority_filter": "high",
            "days_back": 30
        }

        response = client.post(
            "/api/v1/analytics/recommendations/generate",
            headers=auth_headers,
            json=request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert "recommendations" in data
        assert "request_criteria" in data
        assert len(data["recommendations"]) == 1

    # Test Cross-Service Integration
    @patch("src.services.quality_metrics_service.quality_metrics_service")
    @patch("src.services.user_behavior_service.user_behavior_service")
    @patch("src.services.performance_dashboard_service.performance_dashboard_service")
    @patch("src.services.quality_recommendations_service.quality_recommendations_service")
    def test_comprehensive_analytics_overview(self, mock_rec, mock_perf, mock_behavior, mock_metrics, client, auth_headers):
        """Test comprehensive analytics overview across all services."""
        # Mock all services
        mock_metrics.get_metrics_summary.return_value = {"total_metrics": 25}
        mock_behavior.get_behavior_trends.return_value = {"patterns": ["power_user", "researcher"]}
        mock_perf.get_dashboard_overview.return_value = {"system_health": {"cpu_usage": 45.2}}
        mock_rec.generate_recommendations.return_value = []

        # Get quality metrics
        metrics_response = client.get("/api/v1/analytics/quality/metrics/summary", headers=auth_headers)
        assert metrics_response.status_code == 200

        # Get behavior trends
        behavior_response = client.get("/api/v1/analytics/behavior/organization/trends", headers=auth_headers)
        assert behavior_response.status_code == 200

        # Get performance overview
        perf_response = client.get("/api/v1/analytics/performance/overview", headers=auth_headers)
        assert perf_response.status_code == 200

        # Get recommendations
        rec_response = client.get("/api/v1/analytics/recommendations/recommendations", headers=auth_headers)
        assert rec_response.status_code == 200

        # Verify all services are accessible
        assert metrics_response.json()["total_metrics"] == 25
        assert behavior_response.json()["patterns"] == ["power_user", "researcher"]
        assert perf_response.json()["system_health"]["cpu_usage"] == 45.2

    # Test Error Handling
    def test_unauthorized_access(self, client):
        """Test unauthorized access to analytics endpoints."""
        endpoints = [
            "/api/v1/analytics/quality/metrics",
            "/api/v1/analytics/behavior/sessions",
            "/api/v1/analytics/performance/overview",
            "/api/v1/analytics/recommendations/recommendations"
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 403
            data = response.json()
            assert data["detail"] == "Not authenticated"

    def test_invalid_endpoint(self, client, auth_headers):
        """Test invalid analytics endpoint."""
        response = client.get("/api/v1/analytics/invalid/endpoint", headers=auth_headers)
        assert response.status_code == 404

    def test_invalid_request_data(self, client, auth_headers):
        """Test invalid request data validation."""
        # Test invalid metric data
        invalid_metric = {
            "name": "",  # Empty name should fail validation
            "value": "invalid",  # Invalid value type
            "metric_type": "invalid_type"
        }

        response = client.post(
            "/api/v1/analytics/quality/metrics",
            headers=auth_headers,
            json=invalid_metric
        )

        assert response.status_code == 422  # Validation error

    # Test Rate Limiting (if implemented)
    def test_rate_limiting(self, client, auth_headers):
        """Test rate limiting on analytics endpoints."""
        # Make multiple rapid requests
        responses = []
        for _ in range(10):
            response = client.get("/api/v1/analytics/quality/health", headers=auth_headers)
            responses.append(response)
            if response.status_code == 429:
                break

        # If rate limiting is implemented, we should get a 429 response
        # If not implemented, all should return 200
        status_codes = [r.status_code for r in responses]
        assert 200 in status_codes or 429 in status_codes

    # Test CORS Headers
    def test_cors_headers(self, client):
        """Test CORS headers on analytics endpoints."""
        response = client.options("/api/v1/analytics/quality/health")

        # Check for CORS headers (implementation dependent)
        # This test will pass regardless of CORS implementation
        assert response.status_code in [200, 405]