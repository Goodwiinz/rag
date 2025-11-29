"""
API Contract Tests for Knowledge Graph Analytics Dashboard
Validates all endpoints match the OpenAPI specification in /docs/api/knowledge-graph-analytics-dashboard.yaml
"""

import pytest
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List
import yaml
from httpx import AsyncClient

from conftest import (
    TEST_CONFIG, APIAssertions, create_auth_headers,
    sample_organization, sample_user, sample_dashboard, sample_report, sample_alert
)


class TestAPIContracts:
    """Test API contracts against OpenAPI specification"""

    @pytest.fixture(scope="class")
    async def openapi_spec(self):
        """Load OpenAPI specification"""
        spec_path = "/Users/goodwiinz/development/RAG_system/rag/docs/api/knowledge-graph-analytics-dashboard.yaml"
        with open(spec_path, 'r') as f:
            spec = yaml.safe_load(f)
        return spec

    @pytest.fixture(scope="class")
    async def auth_headers(self, sample_user):
        """Create authentication headers"""
        import jwt
        token = jwt.encode(
            {
                "sub": str(sample_user["id"]),
                "email": sample_user["email"],
                "organization_id": str(sample_user["organization_id"]),
                "roles": sample_user["roles"],
                "exp": datetime.utcnow() + timedelta(hours=1)
            },
            "test_secret_key",
            algorithm="HS256"
        )
        return create_auth_headers(token)

    @pytest.mark.integration
    @pytest.mark.api_contract
    async def test_realtime_metrics_endpoint_contract(self, api_client: AsyncClient, openapi_spec, auth_headers, sample_organization):
        """Test /realtime/metrics endpoint contract compliance"""
        endpoint_spec = openapi_spec["paths"]["/realtime/metrics"]["get"]
        org_id = sample_organization["id"]

        # Test valid request
        response = await api_client.get(
            f"/api/v1/analytics/realtime/metrics",
            params={"organization_id": str(org_id), "refresh_interval": 5},
            headers=auth_headers
        )

        data = APIAssertions.assert_valid_response(response, 200)

        # Validate response schema
        schema = openapi_spec["components"]["schemas"]["RealtimeMetricsResponse"]
        APIAssertions.assert_openapi_schema_compliance(data, schema)

        # Check required fields
        assert "organization_id" in data
        assert "timestamp" in data
        assert "metrics" in data
        assert "last_updated" in data

        # Validate metrics structure
        metrics = data["metrics"]
        required_metrics = [
            "total_entities", "new_entities_today", "avg_entity_confidence",
            "total_relationships", "new_relationships_today", "total_documents",
            "documents_processed_today", "avg_document_quality", "processing_success_rate",
            "active_users_today", "total_searches_today", "avg_search_response_time",
            "system_health_score", "total_storage_used"
        ]

        for metric in required_metrics:
            assert metric in metrics, f"Missing metric: {metric}"

    @pytest.mark.integration
    @pytest.mark.api_contract
    async def test_realtime_subscribe_endpoint_contract(self, api_client: AsyncClient, openapi_spec, auth_headers, sample_organization):
        """Test /realtime/subscribe endpoint contract compliance"""
        org_id = sample_organization["id"]

        response = await api_client.post(
            f"/api/v1/analytics/realtime/subscribe",
            params={"organization_id": str(org_id)},
            headers=auth_headers
        )

        data = APIAssertions.assert_valid_response(response, 200)

        # Validate response schema
        schema = openapi_spec["components"]["schemas"]["WebSocketConnectionResponse"]
        APIAssertions.assert_openapi_schema_compliance(data, schema)

        # Check required fields
        assert "connection_id" in data
        assert "websocket_url" in data
        assert "auth_token" in data
        assert "expires_at" in data

    @pytest.mark.integration
    @pytest.mark.api_contract
    async def test_graph_centrality_endpoint_contract(self, api_client: AsyncClient, openapi_spec, auth_headers, sample_organization):
        """Test /graph/analytics/centrality endpoint contract compliance"""
        org_id = sample_organization["id"]

        # Test each algorithm
        algorithms = ["degree", "betweenness", "closeness", "pagerank", "eigenvector"]

        for algorithm in algorithms:
            response = await api_client.get(
                f"/api/v1/analytics/graph/analytics/centrality",
                params={
                    "organization_id": str(org_id),
                    "algorithm": algorithm,
                    "entity_types": ["person", "organization"],
                    "limit": 50
                },
                headers=auth_headers
            )

            data = APIAssertions.assert_valid_response(response, 200)

            # Validate response schema
            schema = openapi_spec["components"]["schemas"]["GraphCentralityResponse"]
            APIAssertions.assert_openapi_schema_compliance(data, schema)

            # Check required fields
            assert "algorithm" in data
            assert "computed_at" in data
            assert "computation_time_ms" in data
            assert "total_entities_analyzed" in data
            assert "results" in data
            assert "metadata" in data

            # Validate results structure
            results = data["results"]
            if len(results) > 0:
                result = results[0]
                required_fields = ["entity_id", "entity_name", "entity_type", "centrality_score", "rank"]
                for field in required_fields:
                    assert field in result, f"Missing result field: {field}"

    @pytest.mark.integration
    @pytest.mark.api_contract
    async def test_graph_clustering_endpoint_contract(self, api_client: AsyncClient, openapi_spec, auth_headers, sample_organization):
        """Test /graph/analytics/clustering endpoint contract compliance"""
        org_id = sample_organization["id"]

        request_data = {
            "algorithm": "louvain",
            "entity_types": ["person", "organization"],
            "relationship_types": ["works_for", "related_to"],
            "min_cluster_size": 3,
            "max_clusters": 50,
            "resolution": 1.0
        }

        response = await api_client.post(
            f"/api/v1/analytics/graph/analytics/clustering",
            params={"organization_id": str(org_id)},
            json=request_data,
            headers=auth_headers
        )

        data = APIAssertions.assert_valid_response(response, 200)

        # Validate response schema
        schema = openapi_spec["components"]["schemas"]["ClusteringResponse"]
        APIAssertions.assert_openapi_schema_compliance(data, schema)

        # Check required fields
        assert "algorithm" in data
        assert "computed_at" in data
        assert "computation_time_ms" in data
        assert "total_communities" in data
        assert "modularity_score" in data
        assert "communities" in data
        assert "summary_stats" in data

    @pytest.mark.integration
    @pytest.mark.api_contract
    async def test_graph_paths_endpoint_contract(self, api_client: AsyncClient, openapi_spec, auth_headers, sample_organization):
        """Test /graph/analytics/paths endpoint contract compliance"""
        org_id = sample_organization["id"]
        source_id = str(uuid.uuid4())
        target_id = str(uuid.uuid4())

        request_data = {
            "source_entity_id": source_id,
            "target_entity_id": target_id,
            "algorithm": "dijkstra",
            "max_path_length": 10,
            "max_paths": 5,
            "include_path_weights": True
        }

        response = await api_client.post(
            f"/api/v1/analytics/graph/analytics/paths",
            params={"organization_id": str(org_id)},
            json=request_data,
            headers=auth_headers
        )

        data = APIAssertions.assert_valid_response(response, 200)

        # Validate response schema
        schema = openapi_spec["components"]["schemas"]["PathAnalysisResponse"]
        APIAssertions.assert_openapi_schema_compliance(data, schema)

        # Check required fields
        assert "computed_at" in data
        assert "computation_time_ms" in data
        assert "source_entity" in data
        assert "target_entity" in data
        assert "paths" in data

    @pytest.mark.integration
    @pytest.mark.api_contract
    async def test_dashboard_configurations_crud_contract(self, api_client: AsyncClient, openapi_spec, auth_headers, sample_organization, sample_dashboard):
        """Test dashboard configurations CRUD operations contract compliance"""
        org_id = sample_organization["id"]

        # Test GET /dashboard/configurations
        response = await api_client.get(
            f"/api/v1/analytics/dashboard/configurations",
            params={"organization_id": str(org_id)},
            headers=auth_headers
        )

        data = APIAssertions.assert_valid_response(response, 200)
        schema = openapi_spec["components"]["schemas"]["DashboardConfigurationsResponse"]
        APIAssertions.assert_openapi_schema_compliance(data, schema)

        # Test POST /dashboard/configurations
        create_request = {
            "config_name": "Test Contract Dashboard",
            "config_type": "user",
            "is_default": False,
            "layout": {"rows": 2, "columns": 3},
            "widgets": [],
            "time_range_default": "7d",
            "auto_refresh_enabled": True,
            "auto_refresh_interval_seconds": 300
        }

        response = await api_client.post(
            f"/api/v1/analytics/dashboard/configurations",
            params={"organization_id": str(org_id)},
            json=create_request,
            headers=auth_headers
        )

        created_data = APIAssertions.assert_valid_response(response, 201)
        schema = openapi_spec["components"]["schemas"]["DashboardConfigurationResponse"]
        APIAssertions.assert_openapi_schema_compliance(created_data, schema)

        config_id = created_data["id"]

        # Test GET /dashboard/configurations/{config_id}
        response = await api_client.get(
            f"/api/v1/analytics/dashboard/configurations/{config_id}",
            params={"organization_id": str(org_id)},
            headers=auth_headers
        )

        data = APIAssertions.assert_valid_response(response, 200)
        APIAssertions.assert_openapi_schema_compliance(data, schema)

        # Test PUT /dashboard/configurations/{config_id}
        update_request = {
            "config_name": "Updated Contract Dashboard",
            "layout": {"rows": 3, "columns": 4}
        }

        response = await api_client.put(
            f"/api/v1/analytics/dashboard/configurations/{config_id}",
            params={"organization_id": str(org_id)},
            json=update_request,
            headers=auth_headers
        )

        updated_data = APIAssertions.assert_valid_response(response, 200)
        assert updated_data["config_name"] == "Updated Contract Dashboard"

        # Test DELETE /dashboard/configurations/{config_id}
        response = await api_client.delete(
            f"/api/v1/analytics/dashboard/configurations/{config_id}",
            params={"organization_id": str(org_id)},
            headers=auth_headers
        )

        assert response.status_code == 204

    @pytest.mark.integration
    @pytest.mark.api_contract
    async def test_widgets_endpoint_contract(self, api_client: AsyncClient, openapi_spec, auth_headers, sample_organization):
        """Test /dashboard/widgets endpoint contract compliance"""
        org_id = sample_organization["id"]

        response = await api_client.get(
            f"/api/v1/analytics/dashboard/widgets",
            params={"organization_id": str(org_id)},
            headers=auth_headers
        )

        data = APIAssertions.assert_valid_response(response, 200)

        # Validate response schema
        schema = openapi_spec["components"]["schemas"]["WidgetsResponse"]
        APIAssertions.assert_openapi_schema_compliance(data, schema)

        # Check required fields
        assert "widgets" in data
        assert "total_count" in data

        # Validate widget structure if present
        if len(data["widgets"]) > 0:
            widget = data["widgets"][0]
            widget_schema = openapi_spec["components"]["schemas"]["WidgetDefinition"]
            APIAssertions.assert_openapi_schema_compliance(widget, widget_schema)

    @pytest.mark.integration
    @pytest.mark.api_contract
    async def test_reports_crud_contract(self, api_client: AsyncClient, openapi_spec, auth_headers, sample_organization, sample_report):
        """Test reports CRUD operations contract compliance"""
        org_id = sample_organization["id"]

        # Test GET /reports
        response = await api_client.get(
            f"/api/v1/analytics/reports",
            params={
                "organization_id": str(org_id),
                "limit": 10,
                "offset": 0
            },
            headers=auth_headers
        )

        data = APIAssertions.assert_valid_response(response, 200)
        schema = openapi_spec["components"]["schemas"]["ReportsResponse"]
        APIAssertions.assert_openapi_schema_compliance(data, schema)

        # Test POST /reports
        create_request = {
            "report_name": "Contract Test Report",
            "report_description": "Test report for API contract validation",
            "report_category": "test",
            "report_definition": {
                "metrics": ["entity_count", "relationship_count"],
                "filters": {"time_range": "7d"}
            },
            "output_formats": ["json", "pdf"],
            "delivery_methods": ["download"]
        }

        response = await api_client.post(
            f"/api/v1/analytics/reports",
            params={"organization_id": str(org_id)},
            json=create_request,
            headers=auth_headers
        )

        created_data = APIAssertions.assert_valid_response(response, 201)
        schema = openapi_spec["components"]["schemas"]["ReportResponse"]
        APIAssertions.assert_openapi_schema_compliance(created_data, schema)

        report_id = created_data["id"]

        # Test POST /reports/{report_id}/execute
        execute_request = {
            "execution_parameters": {"include_charts": True},
            "output_formats": ["json"],
            "async_execution": True
        }

        response = await api_client.post(
            f"/api/v1/analytics/reports/{report_id}/execute",
            params={"organization_id": str(org_id)},
            json=execute_request,
            headers=auth_headers
        )

        execution_data = APIAssertions.assert_valid_response(response, 200)
        schema = openapi_spec["components"]["schemas"]["ReportExecutionResponse"]
        APIAssertions.assert_openapi_schema_compliance(execution_data, schema)

        # Test GET /reports/{report_id}/executions
        response = await api_client.get(
            f"/api/v1/analytics/reports/{report_id}/executions",
            params={"organization_id": str(org_id)},
            headers=auth_headers
        )

        data = APIAssertions.assert_valid_response(response, 200)
        schema = openapi_spec["components"]["schemas"]["ReportExecutionsResponse"]
        APIAssertions.assert_openapi_schema_compliance(data, schema)

    @pytest.mark.integration
    @pytest.mark.api_contract
    async def test_alerts_crud_contract(self, api_client: AsyncClient, openapi_spec, auth_headers, sample_organization, sample_alert):
        """Test alerts CRUD operations contract compliance"""
        org_id = sample_organization["id"]

        # Test GET /alerts
        response = await api_client.get(
            f"/api/v1/analytics/alerts",
            params={
                "organization_id": str(org_id),
                "status": "active",
                "severity": "warning"
            },
            headers=auth_headers
        )

        data = APIAssertions.assert_valid_response(response, 200)
        schema = openapi_spec["components"]["schemas"]["AlertsResponse"]
        APIAssertions.assert_openapi_schema_compliance(data, schema)

        # Test POST /alerts
        create_request = {
            "alert_name": "Contract Test Alert",
            "alert_type": "metric_threshold",
            "alert_condition": {
                "metric": "test_metric",
                "operator": "greater_than",
                "threshold": 100
            },
            "threshold_values": {"warning": 50, "critical": 100},
            "severity": "warning",
            "notification_channels": ["email"]
        }

        response = await api_client.post(
            f"/api/v1/analytics/alerts",
            params={"organization_id": str(org_id)},
            json=create_request,
            headers=auth_headers
        )

        created_data = APIAssertions.assert_valid_response(response, 201)
        schema = openapi_spec["components"]["schemas"]["AlertResponse"]
        APIAssertions.assert_openapi_schema_compliance(created_data, schema)

        alert_id = created_data["id"]

        # Test POST /alerts/{alert_id}/acknowledge
        acknowledge_request = {
            "action_notes": "Acknowledged during contract test",
            "suppress_duration_hours": 2
        }

        response = await api_client.post(
            f"/api/v1/analytics/alerts/{alert_id}/acknowledge",
            params={"organization_id": str(org_id)},
            json=acknowledge_request,
            headers=auth_headers
        )

        data = APIAssertions.assert_valid_response(response, 200)
        assert data["status"] == "acknowledged"

    @pytest.mark.integration
    @pytest.mark.api_contract
    async def test_metrics_aggregations_endpoint_contract(self, api_client: AsyncClient, openapi_spec, auth_headers, sample_organization):
        """Test /metrics/aggregations endpoint contract compliance"""
        org_id = sample_organization["id"]

        # Test with different metric types and time buckets
        test_cases = [
            {
                "metric_type": "entity",
                "time_bucket": "hour",
                "aggregations": ["sum", "avg", "count"]
            },
            {
                "metric_type": "relationship",
                "time_bucket": "day",
                "aggregations": ["sum", "max", "distinct_count"]
            }
        ]

        for test_case in test_cases:
            params = {
                "organization_id": str(org_id),
                "metric_type": test_case["metric_type"],
                "time_bucket": test_case["time_bucket"],
                "start_time": (datetime.utcnow() - timedelta(days=7)).isoformat(),
                "end_time": datetime.utcnow().isoformat(),
                "aggregations": test_case["aggregations"]
            }

            response = await api_client.get(
                f"/api/v1/analytics/metrics/aggregations",
                params=params,
                headers=auth_headers
            )

            data = APIAssertions.assert_valid_response(response, 200)

            # Validate response schema
            schema = openapi_spec["components"]["schemas"]["MetricsAggregationsResponse"]
            APIAssertions.assert_openapi_schema_compliance(data, schema)

            # Check required fields
            assert "metric_type" in data
            assert "time_bucket" in data
            assert "time_range" in data
            assert "aggregations" in data
            assert "summary_stats" in data
            assert "computed_at" in data
            assert "computation_time_ms" in data

            # Validate time range
            time_range = data["time_range"]
            assert "start_time" in time_range
            assert "end_time" in time_range

            # Validate aggregations
            aggregations = data["aggregations"]
            if len(aggregations) > 0:
                agg_schema = openapi_spec["components"]["schemas"]["MetricAggregation"]
                APIAssertions.assert_openapi_schema_compliance(aggregations[0], agg_schema)

    @pytest.mark.integration
    @pytest.mark.api_contract
    async def test_error_response_contracts(self, api_client: AsyncClient, openapi_spec, auth_headers):
        """Test error response contract compliance"""
        # Test 401 Unauthorized
        response = await api_client.get(
            "/api/v1/analytics/realtime/metrics",
            params={"organization_id": str(uuid.uuid4())}
        )
        assert response.status_code == 401

        # Test 400 Bad Request - Missing required parameter
        response = await api_client.get(
            "/api/v1/analytics/realtime/metrics",
            headers=auth_headers
        )
        assert response.status_code == 400

        error_data = response.json()
        schema = openapi_spec["components"]["schemas"]["ErrorResponse"]
        APIAssertions.assert_openapi_schema_compliance(error_data, schema)

        # Test 404 Not Found
        response = await api_client.get(
            f"/api/v1/analytics/dashboard/configurations/{uuid.uuid4()}",
            params={"organization_id": str(uuid.uuid4())},
            headers=auth_headers
        )
        assert response.status_code == 404

        # Test 429 Too Many Requests (if rate limiting is implemented)
        # This would require setting up rate limiting for tests

    @pytest.mark.integration
    @pytest.mark.api_contract
    async def test_parameter_validation_contracts(self, api_client: AsyncClient, openapi_spec, auth_headers, sample_organization):
        """Test parameter validation according to OpenAPI specs"""
        org_id = sample_organization["id"]

        # Test invalid refresh_interval (should be 1-300)
        response = await api_client.get(
            f"/api/v1/analytics/realtime/metrics",
            params={"organization_id": str(org_id), "refresh_interval": 500},
            headers=auth_headers
        )
        assert response.status_code == 400

        # Test invalid algorithm for centrality
        response = await api_client.get(
            f"/api/v1/analytics/graph/analytics/centrality",
            params={
                "organization_id": str(org_id),
                "algorithm": "invalid_algorithm"
            },
            headers=auth_headers
        )
        assert response.status_code == 400

        # Test invalid limit value (should be 1-1000)
        response = await api_client.get(
            f"/api/v1/analytics/graph/analytics/centrality",
            params={
                "organization_id": str(org_id),
                "algorithm": "degree",
                "limit": 2000
            },
            headers=auth_headers
        )
        assert response.status_code == 400

        # Test invalid time_bucket for metrics aggregations
        response = await api_client.get(
            f"/api/v1/analytics/metrics/aggregations",
            params={
                "organization_id": str(org_id),
                "metric_type": "entity",
                "time_bucket": "invalid_bucket",
                "start_time": datetime.utcnow().isoformat(),
                "end_time": datetime.utcnow().isoformat()
            },
            headers=auth_headers
        )
        assert response.status_code == 400

    @pytest.mark.integration
    @pytest.mark.api_contract
    async def test_response_headers_contracts(self, api_client: AsyncClient, auth_headers, sample_organization):
        """Test response headers compliance"""
        org_id = sample_organization["id"]

        response = await api_client.get(
            f"/api/v1/analytics/realtime/metrics",
            params={"organization_id": str(org_id)},
            headers=auth_headers
        )

        # Check for standard headers
        assert "content-type" in response.headers
        assert response.headers["content-type"] == "application/json"

        # Check for rate limiting headers (if implemented)
        # assert "x-ratelimit-limit" in response.headers
        # assert "x-ratelimit-remaining" in response.headers

        # Check for CORS headers (if applicable)
        # assert "access-control-allow-origin" in response.headers

    @pytest.mark.integration
    @pytest.mark.api_contract
    async def test_pagination_contracts(self, api_client: AsyncClient, openapi_spec, auth_headers, sample_organization):
        """Test pagination response contracts"""
        org_id = sample_organization["id"]

        # Test reports pagination
        response = await api_client.get(
            f"/api/v1/analytics/reports",
            params={
                "organization_id": str(org_id),
                "limit": 5,
                "offset": 0
            },
            headers=auth_headers
        )

        data = APIAssertions.assert_valid_response(response, 200)

        # Validate pagination structure
        if "page_info" in data:
            page_info = data["page_info"]
            required_fields = ["has_next_page", "has_previous_page", "limit", "offset"]
            for field in required_fields:
                assert field in page_info, f"Missing pagination field: {field}"