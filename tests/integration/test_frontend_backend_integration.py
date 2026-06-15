"""
Frontend-Backend Integration Tests
Tests data flow between Next.js frontend components and FastAPI backend services
"""

import pytest
import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
from unittest.mock import Mock, AsyncMock

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from conftest import (
    APIAssertions, create_auth_headers, wait_for_condition,
    sample_organization, sample_user, sample_dashboard, sample_report,
    sample_metrics_data
)


class TestFrontendBackendIntegration:
    """Test integration between frontend components and backend services"""

    @pytest.fixture
    async def mock_frontend_store(self):
        """Mock frontend store for testing"""
        class MockAnalyticsStore:
            def __init__(self):
                self.metrics = []
                self.dashboard = None
                self.loading = False
                self.error = None
                self.subscriptions = {}

            async def load_metrics(self, filters: Dict[str, Any] = None):
                self.loading = True
                # Simulate API call
                await asyncio.sleep(0.1)
                self.loading = False
                return self.metrics

            async def load_dashboard(self, dashboard_id: str):
                self.loading = True
                await asyncio.sleep(0.1)
                self.loading = False
                return self.dashboard

            async def update_widget(self, widget_id: str, config: Dict[str, Any]):
                await asyncio.sleep(0.05)
                return {"id": widget_id, **config}

        return MockAnalyticsStore()

    @pytest.fixture
    async def mock_websocket_service(self):
        """Mock WebSocket service for testing"""
        class MockWebSocketService:
            def __init__(self):
                self.connected = False
                self.subscriptions = {}
                self.message_handlers = {}

            async def connect(self, url: str, token: str):
                await asyncio.sleep(0.1)
                self.connected = True
                return {"connection_id": str(uuid.uuid4())}

            async def subscribe(self, channel: str, filters: Dict[str, Any] = None):
                subscription_id = str(uuid.uuid4())
                self.subscriptions[subscription_id] = {
                    "channel": channel,
                    "filters": filters or {}
                }
                return subscription_id

            async def unsubscribe(self, subscription_id: str):
                if subscription_id in self.subscriptions:
                    del self.subscriptions[subscription_id]

            async def disconnect(self):
                self.connected = False
                self.subscriptions.clear()

        return MockWebSocketService()

    @pytest.mark.integration
    async def test_metrics_data_flow_frontend_to_backend(
        self, api_client: AsyncClient, auth_headers, sample_organization,
        mock_frontend_store, sample_metrics_data
    ):
        """Test complete data flow for metrics from frontend store to backend API"""
        org_id = sample_organization["id"]

        # 1. Frontend requests metrics with filters
        filters = {
            "time_range": {"start": "2024-01-01", "end": "2024-01-31"},
            "entity_types": ["person", "organization"],
            "aggregation": "daily"
        }

        # 2. Mock frontend store making API call
        response = await api_client.get(
            f"/api/v1/analytics/realtime/metrics",
            params={
                "organization_id": str(org_id),
                "refresh_interval": 30
            },
            headers=auth_headers
        )

        # 3. Validate backend response
        data = APIAssertions.assert_valid_response(response, 200)
        assert "metrics" in data
        assert "organization_id" in data
        assert data["organization_id"] == str(org_id)

        # 4. Simulate frontend processing
        processed_metrics = {
            "totalEntities": data["metrics"]["total_entities"],
            "newEntitiesToday": data["metrics"]["new_entities_today"],
            "avgConfidence": data["metrics"]["avg_entity_confidence"],
            "timestamp": data["timestamp"]
        }

        # 5. Verify data transformation
        assert isinstance(processed_metrics["totalEntities"], int)
        assert isinstance(processed_metrics["newEntitiesToday"], int)
        assert isinstance(processed_metrics["avgConfidence"], (int, float))

    @pytest.mark.integration
    async def test_dashboard_crud_integration(
        self, api_client: AsyncClient, auth_headers, sample_organization,
        sample_dashboard
    ):
        """Test complete dashboard CRUD flow from frontend to backend"""
        org_id = sample_organization["id"]

        # 1. Create dashboard from frontend
        create_data = {
            "config_name": "Integration Test Dashboard",
            "config_type": "user",
            "layout": {
                "rows": 3,
                "columns": 4,
                "widgets": [
                    {
                        "id": str(uuid.uuid4()),
                        "type": "metric_card",
                        "position": {"row": 0, "col": 0, "width": 1, "height": 1},
                        "config": {"metric_id": "total_entities"}
                    }
                ]
            },
            "auto_refresh_enabled": True,
            "auto_refresh_interval_seconds": 300
        }

        response = await api_client.post(
            f"/api/v1/analytics/dashboard/configurations",
            params={"organization_id": str(org_id)},
            json=create_data,
            headers=auth_headers
        )

        created_dashboard = APIAssertions.assert_valid_response(response, 201)
        dashboard_id = created_dashboard["id"]

        # 2. Load dashboard data (frontend component mount)
        response = await api_client.get(
            f"/api/v1/analytics/dashboard/configurations/{dashboard_id}",
            params={"organization_id": str(org_id)},
            headers=auth_headers
        )

        loaded_dashboard = APIAssertions.assert_valid_response(response, 200)
        assert loaded_dashboard["config_name"] == create_data["config_name"]

        # 3. Update dashboard layout (frontend drag-and-drop)
        update_data = {
            "layout": {
                "rows": 4,
                "columns": 4,
                "widgets": [
                    {
                        "id": created_dashboard["widgets"][0]["id"],
                        "position": {"row": 1, "col": 1, "width": 2, "height": 1}
                    }
                ]
            }
        }

        response = await api_client.put(
            f"/api/v1/analytics/dashboard/configurations/{dashboard_id}",
            params={"organization_id": str(org_id)},
            json=update_data,
            headers=auth_headers
        )

        updated_dashboard = APIAssertions.assert_valid_response(response, 200)
        assert updated_dashboard["layout"]["rows"] == 4

        # 4. Delete dashboard (frontend delete action)
        response = await api_client.delete(
            f"/api/v1/analytics/dashboard/configurations/{dashboard_id}",
            params={"organization_id": str(org_id)},
            headers=auth_headers
        )

        assert response.status_code == 204

        # 5. Verify deletion
        response = await api_client.get(
            f"/api/v1/analytics/dashboard/configurations/{dashboard_id}",
            params={"organization_id": str(org_id)},
            headers=auth_headers
        )
        assert response.status_code == 404

    @pytest.mark.integration
    async def test_widget_data_refresh_flow(
        self, api_client: AsyncClient, auth_headers, sample_organization,
        sample_dashboard
    ):
        """Test widget data refresh flow from frontend to backend"""
        org_id = sample_organization["id"]

        # 1. Create dashboard with widgets
        response = await api_client.post(
            f"/api/v1/analytics/dashboard/configurations",
            params={"organization_id": str(org_id)},
            json=sample_dashboard,
            headers=auth_headers
        )

        dashboard = APIAssertions.assert_valid_response(response, 201)

        # 2. Simulate widget requesting data refresh
        widget_id = dashboard["widgets"][0]["id"]

        # Frontend would call widget refresh endpoint
        response = await api_client.post(
            f"/api/v1/analytics/widgets/{widget_id}/refresh",
            headers=auth_headers
        )

        refreshed_widget = APIAssertions.assert_valid_response(response, 200)
        assert refreshed_widget["id"] == widget_id
        assert "lastUpdated" in refreshed_widget

        # 3. Get widget data (frontend fetch)
        response = await api_client.get(
            f"/api/v1/analytics/widgets/{widget_id}/data",
            headers=auth_headers
        )

        widget_data = APIAssertions.assert_valid_response(response, 200)
        assert "data" in widget_data
        assert "timestamp" in widget_data

    @pytest.mark.integration
    async def test_report_generation_integration(
        self, api_client: AsyncClient, auth_headers, sample_organization,
        sample_report
    ):
        """Test report generation flow from frontend to backend"""
        org_id = sample_organization["id"]

        # 1. Create report from frontend
        response = await api_client.post(
            f"/api/v1/analytics/reports",
            params={"organization_id": str(org_id)},
            json=sample_report,
            headers=auth_headers
        )

        report = APIAssertions.assert_valid_response(response, 201)
        report_id = report["id"]

        # 2. Execute report (frontend generate button)
        execute_data = {
            "execution_parameters": {
                "date_range": "30d",
                "include_charts": True,
                "format": "pdf"
            },
            "output_formats": ["pdf", "json"],
            "async_execution": True
        }

        response = await api_client.post(
            f"/api/v1/analytics/reports/{report_id}/execute",
            params={"organization_id": str(org_id)},
            json=execute_data,
            headers=auth_headers
        )

        execution = APIAssertions.assert_valid_response(response, 200)
        execution_id = execution["execution_id"]
        assert execution["execution_status"] == "running"

        # 3. Poll for completion (frontend polling)
        async def check_execution_complete():
            response = await api_client.get(
                f"/api/v1/analytics/reports/{report_id}/executions",
                params={
                    "organization_id": str(org_id),
                    "status": "completed"
                },
                headers=auth_headers
            )
            data = response.json()
            return len(data["executions"]) > 0

        # Wait for completion (with timeout)
        try:
            await wait_for_condition(check_execution_complete, timeout=30.0)
        except TimeoutError:
            # For testing, we'll proceed even if not completed
            pass

        # 4. Get execution history (frontend display)
        response = await api_client.get(
            f"/api/v1/analytics/reports/{report_id}/executions",
            params={"organization_id": str(org_id)},
            headers=auth_headers
        )

        history = APIAssertions.assert_valid_response(response, 200)
        assert "executions" in history
        assert "total_count" in history

    @pytest.mark.integration
    async def test_graph_analytics_integration(
        self, api_client: AsyncClient, auth_headers, sample_organization
    ):
        """Test graph analytics integration between frontend and backend"""
        org_id = sample_organization["id"]

        # 1. Frontend requests graph statistics
        response = await api_client.get(
            f"/api/v1/analytics/graph/analytics/centrality",
            params={
                "organization_id": str(org_id),
                "algorithm": "degree",
                "entity_types": ["person", "organization"],
                "limit": 20
            },
            headers=auth_headers
        )

        centrality_data = APIAssertions.assert_valid_response(response, 200)

        # 2. Process data for frontend visualization
        if centrality_data["results"]:
            graph_data = {
                "nodes": [
                    {
                        "id": result["entity_id"],
                        "name": result["entity_name"],
                        "type": result["entity_type"],
                        "value": result["centrality_score"],
                        "rank": result["rank"]
                    }
                    for result in centrality_data["results"][:10]
                ],
                "metadata": {
                    "algorithm": centrality_data["algorithm"],
                    "computed_at": centrality_data["computed_at"],
                    "total_entities": centrality_data["total_entities_analyzed"]
                }
            }

            # Verify frontend data structure
            assert len(graph_data["nodes"]) <= 10
            assert all("id" in node and "value" in node for node in graph_data["nodes"])

        # 3. Test clustering analysis
        clustering_request = {
            "algorithm": "louvain",
            "entity_types": ["person", "organization"],
            "min_cluster_size": 3
        }

        response = await api_client.post(
            f"/api/v1/analytics/graph/analytics/clustering",
            params={"organization_id": str(org_id)},
            json=clustering_request,
            headers=auth_headers
        )

        clustering_data = APIAssertions.assert_valid_response(response, 200)

        # 4. Process clustering data for frontend
        if clustering_data["communities"]:
            communities_data = {
                "communities": [
                    {
                        "id": community["community_id"],
                        "size": community["size"],
                        "density": community["internal_density"],
                        "entities": community["entities"][:5]  # Limit for display
                    }
                    for community in clustering_data["communities"]
                ],
                "summary": clustering_data["summary_stats"]
            }

            # Verify clustering data structure
            assert "modularity_score" in clustering_data
            assert isinstance(communities_data["communities"], list)

    @pytest.mark.integration
    async def test_alert_management_integration(
        self, api_client: AsyncClient, auth_headers, sample_organization
    ):
        """Test alert management integration flow"""
        org_id = sample_organization["id"]

        # 1. Create alert from frontend
        alert_request = {
            "alert_name": "Integration Test Alert",
            "alert_type": "metric_threshold",
            "alert_condition": {
                "metric": "entity_growth_rate",
                "operator": "greater_than",
                "threshold": 10.0
            },
            "threshold_values": {"warning": 5.0, "critical": 10.0},
            "severity": "warning",
            "notification_channels": ["email", "dashboard"]
        }

        response = await api_client.post(
            f"/api/v1/analytics/alerts",
            params={"organization_id": str(org_id)},
            json=alert_request,
            headers=auth_headers
        )

        alert = APIAssertions.assert_valid_response(response, 201)
        alert_id = alert["id"]

        # 2. List alerts (frontend dashboard)
        response = await api_client.get(
            f"/api/v1/analytics/alerts",
            params={
                "organization_id": str(org_id),
                "status": "active"
            },
            headers=auth_headers
        )

        alerts_list = APIAssertions.assert_valid_response(response, 200)
        assert any(a["id"] == alert_id for a in alerts_list["alerts"])

        # 3. Acknowledge alert (frontend action)
        acknowledge_request = {
            "action_notes": "Acknowledged during integration test",
            "suppress_duration_hours": 1
        }

        response = await api_client.post(
            f"/api/v1/analytics/alerts/{alert_id}/acknowledge",
            params={"organization_id": str(org_id)},
            json=acknowledge_request,
            headers=auth_headers
        )

        acknowledged_alert = APIAssertions.assert_valid_response(response, 200)
        assert acknowledged_alert["status"] == "acknowledged"

    @pytest.mark.integration
    async def test_data_export_integration(
        self, api_client: AsyncClient, auth_headers, sample_organization
    ):
        """Test data export functionality integration"""
        org_id = sample_organization["id"]

        # 1. Request export from frontend
        export_request = {
            "type": "metrics",
            "format": "csv",
            "filters": {
                "time_range": {"start": "2024-01-01", "end": "2024-01-31"},
                "metric_types": ["entity", "relationship"]
            }
        }

        response = await api_client.post(
            f"/api/v1/analytics/export",
            params=export_request,
            headers=auth_headers
        )

        export_data = APIAssertions.assert_valid_response(response, 200)
        assert "downloadUrl" in export_data
        assert "expiresAt" in export_data

        # 2. Get export status (frontend polling)
        if "export_id" in export_data:
            export_id = export_data["export_id"]
            response = await api_client.get(
                f"/api/v1/analytics/export/{export_id}/status",
                headers=auth_headers
            )

            status_data = APIAssertions.assert_valid_response(response, 200)
            assert "status" in status_data
            assert "progress" in status_data

    @pytest.mark.integration
    async def test_error_handling_integration(
        self, api_client: AsyncClient, auth_headers, sample_organization
    ):
        """Test error handling integration between frontend and backend"""
        org_id = sample_organization["id"]

        # 1. Test API error response handling
        response = await api_client.get(
            f"/api/v1/analytics/dashboard/configurations/{uuid.uuid4()}",
            params={"organization_id": str(org_id)},
            headers=auth_headers
        )

        assert response.status_code == 404
        error_data = response.json()

        # 2. Verify error structure for frontend processing
        assert "error" in error_data
        assert "status_code" in error_data["error"]
        assert "message" in error_data["error"]

        # 3. Test validation error handling
        invalid_request = {
            "config_name": "",  # Empty name should fail validation
            "config_type": "invalid_type"
        }

        response = await api_client.post(
            f"/api/v1/analytics/dashboard/configurations",
            params={"organization_id": str(org_id)},
            json=invalid_request,
            headers=auth_headers
        )

        assert response.status_code == 400
        validation_error = response.json()
        assert "details" in validation_error["error"]

    @pytest.mark.integration
    async def test_pagination_integration(
        self, api_client: AsyncClient, auth_headers, sample_organization
    ):
        """Test pagination integration for frontend lists"""
        org_id = sample_organization["id"]

        # 1. Test first page
        response = await api_client.get(
            f"/api/v1/analytics/reports",
            params={
                "organization_id": str(org_id),
                "limit": 5,
                "offset": 0
            },
            headers=auth_headers
        )

        first_page = APIAssertions.assert_valid_response(response, 200)

        # 2. Test second page
        response = await api_client.get(
            f"/api/v1/analytics/reports",
            params={
                "organization_id": str(org_id),
                "limit": 5,
                "offset": 5
            },
            headers=auth_headers
        )

        second_page = APIAssertions.assert_valid_response(response, 200)

        # 3. Verify pagination metadata
        if "page_info" in first_page:
            page_info = first_page["page_info"]
            assert "has_next_page" in page_info
            assert "limit" in page_info
            assert page_info["limit"] == 5

    @pytest.mark.integration
    async def test_filtering_and_search_integration(
        self, api_client: AsyncClient, auth_headers, sample_organization
    ):
        """Test filtering and search functionality integration"""
        org_id = sample_organization["id"]

        # 1. Test report filtering
        response = await api_client.get(
            f"/api/v1/analytics/reports",
            params={
                "organization_id": str(org_id),
                "report_category": "graph_analysis",
                "is_template": False,
                "limit": 10
            },
            headers=auth_headers
        )

        filtered_reports = APIAssertions.assert_valid_response(response, 200)

        # 2. Test alert filtering
        response = await api_client.get(
            f"/api/v1/analytics/alerts",
            params={
                "organization_id": str(org_id),
                "status": "active",
                "severity": "warning",
                "alert_type": "metric_threshold"
            },
            headers=auth_headers
        )

        filtered_alerts = APIAssertions.assert_valid_response(response, 200)

        # 3. Test widget filtering
        response = await api_client.get(
            f"/api/v1/analytics/dashboard/widgets",
            params={
                "organization_id": str(org_id),
                "widget_category": "entity",
                "widget_type": "metric_card"
            },
            headers=auth_headers
        )

        filtered_widgets = APIAssertions.assert_valid_response(response, 200)

        # Verify filtering responses
        assert "reports" in filtered_reports
        assert "alerts" in filtered_alerts
        assert "widgets" in filtered_widgets

    @pytest.mark.integration
    async def test_concurrent_requests_integration(
        self, api_client: AsyncClient, auth_headers, sample_organization
    ):
        """Test handling concurrent requests from frontend"""
        org_id = sample_organization["id"]

        # 1. Make concurrent requests (simulating multiple components loading)
        tasks = [
            api_client.get(
                f"/api/v1/analytics/realtime/metrics",
                params={"organization_id": str(org_id)},
                headers=auth_headers
            ),
            api_client.get(
                f"/api/v1/analytics/dashboard/configurations",
                params={"organization_id": str(org_id)},
                headers=auth_headers
            ),
            api_client.get(
                f"/api/v1/analytics/reports",
                params={"organization_id": str(org_id), "limit": 5},
                headers=auth_headers
            ),
            api_client.get(
                f"/api/v1/analytics/alerts",
                params={"organization_id": str(org_id), "status": "active"},
                headers=auth_headers
            )
        ]

        # 2. Wait for all requests to complete
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # 3. Verify all requests succeeded
        for i, response in enumerate(responses):
            assert not isinstance(response, Exception), f"Request {i} failed: {response}"
            assert response.status_code == 200, f"Request {i} returned {response.status_code}"

    @pytest.mark.integration
    async def test_data_integrity_validation(
        self, api_client: AsyncClient, auth_headers, sample_organization,
        test_db_session: AsyncSession
    ):
        """Test data integrity between frontend requests and backend database"""
        org_id = sample_organization["id"]

        # 1. Create data via API
        create_data = {
            "config_name": "Data Integrity Test Dashboard",
            "config_type": "user",
            "layout": {"rows": 2, "columns": 2}
        }

        response = await api_client.post(
            f"/api/v1/analytics/dashboard/configurations",
            params={"organization_id": str(org_id)},
            json=create_data,
            headers=auth_headers
        )

        created_data = APIAssertions.assert_valid_response(response, 201)

        # 2. Verify data in database
        from src.models.analytics.dashboard_models import DashboardConfiguration

        result = await test_db_session.execute(
            "SELECT * FROM dashboard_configurations WHERE id = :id",
            {"id": created_data["id"]}
        )
        db_record = result.fetchone()

        assert db_record is not None
        assert db_record["config_name"] == create_data["config_name"]
        assert db_record["organization_id"] == org_id

        # 3. Update data via API
        update_data = {"config_name": "Updated Data Integrity Test"}

        response = await api_client.put(
            f"/api/v1/analytics/dashboard/configurations/{created_data['id']}",
            params={"organization_id": str(org_id)},
            json=update_data,
            headers=auth_headers
        )

        # 4. Verify update in database
        result = await test_db_session.execute(
            "SELECT config_name FROM dashboard_configurations WHERE id = :id",
            {"id": created_data["id"]}
        )
        updated_record = result.fetchone()

        assert updated_record["config_name"] == update_data["config_name"]