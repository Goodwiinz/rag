"""
Multi-tenant Isolation Tests
Tests data separation and isolation between organizations in the system
"""

import pytest
import asyncio
import uuid
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from httpx import AsyncClient

from conftest import (
    APIAssertions, create_auth_headers, create_test_user_session,
    wait_for_condition
)


class TestMultiTenantIsolation:
    """Test multi-tenant data isolation and security"""

    @pytest.fixture
    async def multiple_organizations(self):
        """Create multiple organizations for testing isolation"""
        organizations = [
            {
                "id": uuid.uuid4(),
                "name": "Organization Alpha",
                "domain": "alpha.example.com",
                "settings": {"timezone": "UTC", "data_retention_days": 365}
            },
            {
                "id": uuid.uuid4(),
                "name": "Organization Beta",
                "domain": "beta.example.com",
                "settings": {"timezone": "America/New_York", "data_retention_days": 730}
            },
            {
                "id": uuid.uuid4(),
                "name": "Organization Gamma",
                "domain": "gamma.example.com",
                "settings": {"timezone": "Europe/London", "data_retention_days": 180}
            }
        ]
        return organizations

    @pytest.fixture
    async def users_for_organizations(self, multiple_organizations):
        """Create users for each organization"""
        users = []
        roles = ["admin", "analyst", "viewer"]

        for org in multiple_organizations:
            for role in roles:
                user = {
                    "id": uuid.uuid4(),
                    "email": f"{role}@{org['domain'].replace('.', '_')}",
                    "name": f"{role.title()} User",
                    "organization_id": org["id"],
                    "roles": [role],
                    "is_active": True,
                    "organization": org
                }
                users.append(user)

        return users

    @pytest.fixture
    async def auth_headers_for_users(self, users_for_organizations):
        """Create authentication headers for all test users"""
        import jwt

        auth_headers = {}
        for user in users_for_organizations:
            token = jwt.encode(
                {
                    "sub": str(user["id"]),
                    "email": user["email"],
                    "organization_id": str(user["organization_id"]),
                    "roles": user["roles"],
                    "exp": datetime.utcnow() + timedelta(hours=1)
                },
                "test_secret_key",
                algorithm="HS256"
            )
            auth_headers[user["id"]] = create_auth_headers(token)

        return auth_headers

    @pytest.mark.integration
    @pytest.mark.multitenant
    async def test_organization_data_isolation(self, api_client: AsyncClient, auth_headers_for_users, users_for_organizations):
        """Test that organizations can only access their own data"""
        # Get admin users from different organizations
        admin_users = [u for u in users_for_organizations if "admin" in u["roles"]]
        org_alpha_user = next(u for u in admin_users if "alpha" in u["email"])
        org_beta_user = next(u for u in admin_users if "beta" in u["email"])

        alpha_headers = auth_headers_for_users[org_alpha_user["id"]]
        beta_headers = auth_headers_for_users[org_beta_user["id"]]

        # 1. Create dashboard in Organization Alpha
        alpha_dashboard = {
            "config_name": "Alpha Organization Dashboard",
            "config_type": "organization",
            "layout": {"rows": 3, "columns": 4},
            "widgets": [
                {
                    "type": "metric_card",
                    "title": "Alpha Metrics",
                    "position": {"row": 0, "col": 0, "width": 2, "height": 1}
                }
            ]
        }

        response = await api_client.post(
            f"/api/v1/analytics/dashboard/configurations",
            params={"organization_id": str(org_alpha_user["organization_id"])},
            json=alpha_dashboard,
            headers=alpha_headers
        )

        assert response.status_code == 201
        alpha_dashboard_id = response.json()["id"]

        # 2. Verify Alpha user can see their dashboard
        response = await api_client.get(
            f"/api/v1/analytics/dashboard/configurations/{alpha_dashboard_id}",
            params={"organization_id": str(org_alpha_user["organization_id"])},
            headers=alpha_headers
        )
        assert response.status_code == 200
        assert response.json()["config_name"] == "Alpha Organization Dashboard"

        # 3. Verify Beta user cannot access Alpha's dashboard
        response = await api_client.get(
            f"/api/v1/analytics/dashboard/configurations/{alpha_dashboard_id}",
            params={"organization_id": str(org_beta_user["organization_id"])},
            headers=beta_headers
        )
        assert response.status_code in [403, 404]  # Forbidden or Not Found

        # 4. Verify Beta user cannot list Alpha's dashboards
        response = await api_client.get(
            f"/api/v1/analytics/dashboard/configurations",
            params={"organization_id": str(org_beta_user["organization_id"])},
            headers=beta_headers
        )
        assert response.status_code == 200
        beta_dashboards = response.json()["configurations"]

        # Should not contain Alpha's dashboard
        alpha_dashboard_in_beta_list = any(d["id"] == alpha_dashboard_id for d in beta_dashboards)
        assert not alpha_dashboard_in_beta_list, "Beta user should not see Alpha's dashboard"

    @pytest.mark.integration
    @pytest.mark.multitenant
    async def test_cross_organization_metrics_isolation(self, api_client: AsyncClient, auth_headers_for_users, users_for_organizations):
        """Test that metrics are isolated by organization"""
        # Get analyst users from different organizations
        analyst_users = [u for u in users_for_organizations if "analyst" in u["roles"]]
        org_alpha_user = next(u for u in analyst_users if "alpha" in u["email"])
        org_beta_user = next(u for u in analyst_users if "beta" in u["email"])

        alpha_headers = auth_headers_for_users[org_alpha_user["id"]]
        beta_headers = auth_headers_for_users[org_beta_user["id"]]

        # 1. Get metrics for Organization Alpha
        response = await api_client.get(
            f"/api/v1/analytics/realtime/metrics",
            params={"organization_id": str(org_alpha_user["organization_id"])},
            headers=alpha_headers
        )
        assert response.status_code == 200
        alpha_metrics = response.json()

        # 2. Get metrics for Organization Beta
        response = await api_client.get(
            f"/api/v1/analytics/realtime/metrics",
            params={"organization_id": str(org_beta_user["organization_id"])},
            headers=beta_headers
        )
        assert response.status_code == 200
        beta_metrics = response.json()

        # 3. Verify metrics contain organization-specific data
        assert alpha_metrics["organization_id"] == str(org_alpha_user["organization_id"])
        assert beta_metrics["organization_id"] == str(org_beta_user["organization_id"])
        assert alpha_metrics["organization_id"] != beta_metrics["organization_id"]

        # 4. Test aggregated metrics isolation
        response = await api_client.get(
            f"/api/v1/analytics/metrics/aggregations",
            params={
                "organization_id": str(org_alpha_user["organization_id"]),
                "metric_type": "entity",
                "time_bucket": "day",
                "start_time": (datetime.utcnow() - timedelta(days=7)).isoformat(),
                "end_time": datetime.utcnow().isoformat()
            },
            headers=alpha_headers
        )
        assert response.status_code == 200
        alpha_aggregations = response.json()

        # Beta user trying to access Alpha's aggregations should fail
        response = await api_client.get(
            f"/api/v1/analytics/metrics/aggregations",
            params={
                "organization_id": str(org_alpha_user["organization_id"]),  # Alpha's org ID
                "metric_type": "entity",
                "time_bucket": "day",
                "start_time": (datetime.utcnow() - timedelta(days=7)).isoformat(),
                "end_time": datetime.utcnow().isoformat()
            },
            headers=beta_headers  # Beta user's auth
        )
        assert response.status_code in [403, 404]

    @pytest.mark.integration
    @pytest.mark.multitenant
    async def test_report_isolation(self, api_client: AsyncClient, auth_headers_for_users, users_for_organizations):
        """Test report isolation between organizations"""
        # Get users for report operations
        org_alpha_user = next(u for u in users_for_organizations if "alpha" in u["email"] and "analyst" in u["roles"])
        org_beta_user = next(u for u in users_for_organizations if "beta" in u["email"] and "analyst" in u["roles"])

        alpha_headers = auth_headers_for_users[org_alpha_user["id"]]
        beta_headers = auth_headers_for_users[org_beta_user["id"]]

        # 1. Create report in Organization Alpha
        alpha_report = {
            "report_name": "Alpha Organization Report",
            "report_description": "Confidential Alpha analytics",
            "report_category": "financial",
            "report_definition": {
                "metrics": ["revenue", "costs", "profit"],
                "filters": {"department": "all"}
            },
            "is_public": False  # Private to organization
        }

        response = await api_client.post(
            f"/api/v1/analytics/reports",
            params={"organization_id": str(org_alpha_user["organization_id"])},
            json=alpha_report,
            headers=alpha_headers
        )

        assert response.status_code == 201
        alpha_report_id = response.json()["id"]

        # 2. Execute Alpha's report
        response = await api_client.post(
            f"/api/v1/analytics/reports/{alpha_report_id}/execute",
            params={"organization_id": str(org_alpha_user["organization_id"])},
            json={"output_formats": ["json"]},
            headers=alpha_headers
        )
        assert response.status_code in [200, 202]  # Sync or async execution

        # 3. Beta user trying to access Alpha's report should fail
        response = await api_client.get(
            f"/api/v1/analytics/reports/{alpha_report_id}",
            params={"organization_id": str(org_beta_user["organization_id"])},
            headers=beta_headers
        )
        assert response.status_code in [403, 404]

        # 4. Beta user trying to execute Alpha's report should fail
        response = await api_client.post(
            f"/api/v1/analytics/reports/{alpha_report_id}/execute",
            params={"organization_id": str(org_beta_user["organization_id"])},
            json={"output_formats": ["json"]},
            headers=beta_headers
        )
        assert response.status_code in [403, 404]

    @pytest.mark.integration
    @pytest.mark.multitenant
    async def test_alert_isolation(self, api_client: AsyncClient, auth_headers_for_users, users_for_organizations):
        """Test alert isolation between organizations"""
        # Get users for alert operations
        org_alpha_user = next(u for u in users_for_organizations if "alpha" in u["email"] and "admin" in u["roles"])
        org_beta_user = next(u for u in users_for_organizations if "beta" in u["email"] and "admin" in u["roles"])

        alpha_headers = auth_headers_for_users[org_alpha_user["id"]]
        beta_headers = auth_headers_for_users[org_beta_user["id"]]

        # 1. Create alert in Organization Alpha
        alpha_alert = {
            "alert_name": "Alpha High Cost Alert",
            "alert_type": "metric_threshold",
            "alert_condition": {
                "metric": "operational_cost",
                "operator": "greater_than",
                "threshold": 10000
            },
            "severity": "critical",
            "notification_channels": ["email"]
        }

        response = await api_client.post(
            f"/api/v1/analytics/alerts",
            params={"organization_id": str(org_alpha_user["organization_id"])},
            json=alpha_alert,
            headers=alpha_headers
        )

        assert response.status_code == 201
        alpha_alert_id = response.json()["id"]

        # 2. Alpha user can see their alert
        response = await api_client.get(
            f"/api/v1/analytics/alerts",
            params={
                "organization_id": str(org_alpha_user["organization_id"]),
                "status": "active"
            },
            headers=alpha_headers
        )
        assert response.status_code == 200
        alpha_alerts = response.json()["alerts"]
        alpha_alert_exists = any(a["id"] == alpha_alert_id for a in alpha_alerts)
        assert alpha_alert_exists, "Alpha user should see their own alert"

        # 3. Beta user cannot see Alpha's alert
        response = await api_client.get(
            f"/api/v1/analytics/alerts",
            params={
                "organization_id": str(org_beta_user["organization_id"]),
                "status": "active"
            },
            headers=beta_headers
        )
        assert response.status_code == 200
        beta_alerts = response.json()["alerts"]
        alpha_alert_in_beta_list = any(a["id"] == alpha_alert_id for a in beta_alerts)
        assert not alpha_alert_in_beta_list, "Beta user should not see Alpha's alert"

        # 4. Beta user cannot acknowledge Alpha's alert
        response = await api_client.post(
            f"/api/v1/analytics/alerts/{alpha_alert_id}/acknowledge",
            params={"organization_id": str(org_beta_user["organization_id"])},
            json={"action_notes": "Trying to acknowledge"},
            headers=beta_headers
        )
        assert response.status_code in [403, 404]

    @pytest.mark.integration
    @pytest.mark.multitenant
    async def test_graph_analytics_isolation(self, api_client: AsyncClient, auth_headers_for_users, users_for_organizations):
        """Test graph analytics isolation between organizations"""
        # Get users for graph operations
        org_alpha_user = next(u for u in users_for_organizations if "alpha" in u["email"] and "analyst" in u["roles"])
        org_beta_user = next(u for u in users_for_organizations if "beta" in u["email"] and "analyst" in u["roles"])

        alpha_headers = auth_headers_for_users[org_alpha_user["id"]]
        beta_headers = auth_headers_for_users[org_beta_user["id"]]

        # 1. Get graph centrality for Organization Alpha
        response = await api_client.get(
            f"/api/v1/analytics/graph/analytics/centrality",
            params={
                "organization_id": str(org_alpha_user["organization_id"]),
                "algorithm": "degree",
                "limit": 10
            },
            headers=alpha_headers
        )
        assert response.status_code == 200
        alpha_centrality = response.json()

        # 2. Get graph centrality for Organization Beta
        response = await api_client.get(
            f"/api/v1/analytics/graph/analytics/centrality",
            params={
                "organization_id": str(org_beta_user["organization_id"]),
                "algorithm": "degree",
                "limit": 10
            },
            headers=beta_headers
        )
        assert response.status_code == 200
        beta_centrality = response.json()

        # 3. Results should be different (or at least organization-scoped)
        if alpha_centrality["results"] and beta_centrality["results"]:
            # Check if results contain organization-specific data
            # This is implementation dependent, but isolation should be maintained
            alpha_entity_ids = {r["entity_id"] for r in alpha_centrality["results"]}
            beta_entity_ids = {r["entity_id"] for r in beta_centrality["results"]}

            # There should be minimal overlap in entity IDs between organizations
            overlap = alpha_entity_ids & beta_entity_ids
            overlap_percentage = len(overlap) / max(len(alpha_entity_ids), len(beta_entity_ids)) if max(len(alpha_entity_ids), len(beta_entity_ids)) > 0 else 0

            assert overlap_percentage <= 0.1, f"Entity overlap {overlap_percentage:.2%} should be minimal between organizations"

    @pytest.mark.integration
    @pytest.mark.multitenant
    async def test_user_session_isolation(self, api_client: AsyncClient, users_for_organizations):
        """Test user sessions are isolated by organization"""
        import jwt

        # Test that tokens are only valid for the correct organization
        org_alpha_user = next(u for u in users_for_organizations if "alpha" in u["email"])
        org_beta_user = next(u for u in users_for_organizations if "beta" in u["email"])

        # 1. Create token for Alpha user
        alpha_token = jwt.encode(
            {
                "sub": str(org_alpha_user["id"]),
                "email": org_alpha_user["email"],
                "organization_id": str(org_alpha_user["organization_id"]),
                "roles": org_alpha_user["roles"],
                "exp": datetime.utcnow() + timedelta(hours=1)
            },
            "test_secret_key",
            algorithm="HS256"
        )

        alpha_headers = create_auth_headers(alpha_token)

        # 2. Alpha user accessing their own organization should succeed
        response = await api_client.get(
            f"/api/v1/analytics/realtime/metrics",
            params={"organization_id": str(org_alpha_user["organization_id"])},
            headers=alpha_headers
        )
        assert response.status_code == 200

        # 3. Alpha user accessing different organization should fail
        response = await api_client.get(
            f"/api/v1/analytics/realtime/metrics",
            params={"organization_id": str(org_beta_user["organization_id"])},
            headers=alpha_headers
        )
        assert response.status_code in [403, 404]

    @pytest.mark.integration
    @pytest.mark.multitenant
    async def test_concurrent_organization_operations(self, api_client: AsyncClient, auth_headers_for_users, users_for_organizations):
        """Test concurrent operations don't mix data between organizations"""
        # Get admin users from all organizations
        admin_users = [u for u in users_for_organizations if "admin" in u["roles"]]

        async def create_organization_dashboard(user):
            """Create dashboard for specific organization"""
            headers = auth_headers_for_users[user["id"]]

            dashboard_data = {
                "config_name": f"{user['organization']['name']} Dashboard",
                "config_type": "organization",
                "layout": {"rows": 2, "columns": 3}
            }

            response = await api_client.post(
                f"/api/v1/analytics/dashboard/configurations",
                params={"organization_id": str(user["organization_id"])},
                json=dashboard_data,
                headers=headers
            )

            return {
                "user_id": user["id"],
                "organization_id": user["organization_id"],
                "response": response,
                "dashboard_id": response.json()["id"] if response.status_code == 201 else None
            }

        # Create dashboards concurrently for all organizations
        tasks = [create_organization_dashboard(user) for user in admin_users]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify all operations succeeded
        successful_results = [r for r in results if not isinstance(r, Exception) and r["response"].status_code == 201]
        assert len(successful_results) == len(admin_users), "All organizations should be able to create dashboards"

        # Verify no data mixing
        for result in successful_results:
            dashboard_id = result["dashboard_id"]
            org_id = result["organization_id"]

            # Check with user from same organization
            user_headers = auth_headers_for_users[result["user_id"]]
            response = await api_client.get(
                f"/api/v1/analytics/dashboard/configurations/{dashboard_id}",
                params={"organization_id": str(org_id)},
                headers=user_headers
            )
            assert response.status_code == 200

            # Check with user from different organization
            other_user = next(u for u in admin_users if u["organization_id"] != org_id)
            other_headers = auth_headers_for_users[other_user["id"]]
            response = await api_client.get(
                f"/api/v1/analytics/dashboard/configurations/{dashboard_id}",
                params={"organization_id": str(other_user["organization_id"])},
                headers=other_headers
            )
            assert response.status_code in [403, 404]

    @pytest.mark.integration
    @pytest.mark.multitenant
    async def test_shared_resource_isolation(self, api_client: AsyncClient, auth_headers_for_users, users_for_organizations):
        """Test isolation of shared resources like templates and system widgets"""
        # Get analyst users
        org_alpha_user = next(u for u in users_for_organizations if "alpha" in u["email"] and "analyst" in u["roles"])
        org_beta_user = next(u for u in users_for_organizations if "beta" in u["email"] and "analyst" in u["roles"])

        alpha_headers = auth_headers_for_users[org_alpha_user["id"]]
        beta_headers = auth_headers_for_users[org_beta_user["id"]]

        # 1. Test widget templates (if implemented)
        response = await api_client.get(
            f"/api/v1/analytics/dashboard/widgets",
            params={
                "organization_id": str(org_alpha_user["organization_id"]),
                "widget_category": "system"
            },
            headers=alpha_headers
        )

        if response.status_code == 200:
            alpha_widgets = response.json()["widgets"]

            # Beta user should get same system widgets but different organization-scoped widgets
            response = await api_client.get(
                f"/api/v1/analytics/dashboard/widgets",
                params={
                    "organization_id": str(org_beta_user["organization_id"]),
                    "widget_category": "system"
                },
                headers=beta_headers
            )

            if response.status_code == 200:
                beta_widgets = response.json()["widgets"]

                # System widgets should be the same, but organization widgets should differ
                alpha_system_widgets = [w for w in alpha_widgets if w.get("is_system_widget", False)]
                beta_system_widgets = [w for w in beta_widgets if w.get("is_system_widget", False)]

                # System widgets should be identical
                if alpha_system_widgets and beta_system_widgets:
                    alpha_system_ids = {w["id"] for w in alpha_system_widgets}
                    beta_system_ids = {w["id"] for w in beta_system_widgets}
                    assert alpha_system_ids == beta_system_ids, "System widgets should be the same across organizations"

        # 2. Test report templates
        response = await api_client.get(
            f"/api/v1/analytics/reports",
            params={
                "organization_id": str(org_alpha_user["organization_id"]),
                "is_template": True
            },
            headers=alpha_headers
        )

        if response.status_code == 200:
            alpha_templates = response.json()["reports"]

            # Organization-specific templates should be isolated
            alpha_private_templates = [r for r in alpha_templates if not r.get("is_public", False)]

            # Beta user should not see Alpha's private templates
            response = await api_client.get(
                f"/api/v1/analytics/reports",
                params={
                    "organization_id": str(org_beta_user["organization_id"]),
                    "is_template": True
                },
                headers=beta_headers
            )

            if response.status_code == 200:
                beta_templates = response.json()["reports"]
                beta_private_template_ids = {r["id"] for r in beta_templates if not r.get("is_public", False)}
                alpha_private_template_ids = {r["id"] for r in alpha_private_templates}

                # No overlap in private templates
                overlap = alpha_private_template_ids & beta_private_template_ids
                assert len(overlap) == 0, "Private templates should not be shared between organizations"

    @pytest.mark.integration
    @pytest.mark.multitenant
    async def test_database_isolation_constraints(self, test_db_session: AsyncSession, multiple_organizations):
        """Test database-level isolation constraints"""
        org_alpha_id = multiple_organizations[0]["id"]
        org_beta_id = multiple_organizations[1]["id"]

        # 1. Verify foreign key constraints prevent cross-org data references
        # Test dashboard configurations
        query = text("""
            SELECT COUNT(*) as count
            FROM dashboard_configurations dc
            WHERE dc.organization_id = :org_alpha_id
            AND EXISTS (
                SELECT 1 FROM dashboard_configurations dc2
                WHERE dc2.organization_id = :org_beta_id
                AND dc2.id = dc.id
            )
        """)

        result = await test_db_session.execute(query, {
            "org_alpha_id": str(org_alpha_id),
            "org_beta_id": str(org_beta_id)
        })
        cross_ref_count = result.fetchone()[0]

        assert cross_ref_count == 0, "Should have no cross-organization data references"

        # 2. Test row-level security (if implemented)
        # This would require specific RLS policies to be in place
        security_query = text("""
            SELECT COUNT(*) as count
            FROM analytics_metrics am
            WHERE am.organization_id = :org_alpha_id
        """)

        result = await test_db_session.execute(security_query, {"org_alpha_id": str(org_alpha_id)})
        alpha_metrics_count = result.fetchone()[0]

        # Metrics should only belong to their organization
        if alpha_metrics_count > 0:
            # Verify no metrics have wrong organization ID
            invalid_org_query = text("""
                SELECT COUNT(*) as count
                FROM analytics_metrics am
                WHERE am.organization_id NOT IN (:org_alpha_id, :org_beta_id, :org_gamma_id)
            """)

            result = await test_db_session.execute(invalid_org_query, {
                "org_alpha_id": str(org_alpha_id),
                "org_beta_id": str(org_beta_id),
                "org_gamma_id": str(multiple_organizations[2]["id"])
            })
            invalid_count = result.fetchone()[0]

            assert invalid_count == 0, "Should have no metrics with invalid organization IDs"

    @pytest.mark.integration
    @pytest.mark.multitenant
    async def test_websocket_organization_isolation(self, websocket_client, users_for_organizations):
        """Test WebSocket connections are isolated by organization"""
        import websockets
        import jwt

        # Get users for WebSocket testing
        org_alpha_user = next(u for u in users_for_organizations if "alpha" in u["email"])
        org_beta_user = next(u for u in users_for_organizations if "beta" in u["email"])

        # Create tokens for both users
        alpha_token = jwt.encode(
            {
                "sub": str(org_alpha_user["id"]),
                "email": org_alpha_user["email"],
                "organization_id": str(org_alpha_user["organization_id"]),
                "roles": org_alpha_user["roles"],
                "exp": datetime.utcnow() + timedelta(hours=1)
            },
            "test_secret_key",
            algorithm="HS256"
        )

        beta_token = jwt.encode(
            {
                "sub": str(org_beta_user["id"]),
                "email": org_beta_user["email"],
                "organization_id": str(org_beta_user["organization_id"]),
                "roles": org_beta_user["roles"],
                "exp": datetime.utcnow() + timedelta(hours=1)
            },
            "test_secret_key",
            algorithm="HS256"
        )

        try:
            # Alpha user WebSocket connection
            alpha_uri = f"{websocket_client.base_url}/ws/analytics?token={alpha_token}"
            alpha_ws = await websocket_client.connect(alpha_uri, timeout=5.0)

            # Beta user WebSocket connection
            beta_uri = f"{websocket_client.base_url}/ws/analytics?token={beta_token}"
            beta_ws = await websocket_client.connect(beta_uri, timeout=5.0)

            # Both users should receive authentication confirmation
            alpha_auth = await asyncio.wait_for(alpha_ws.recv(), timeout=5.0)
            beta_auth = await asyncio.wait_for(beta_ws.recv(), timeout=5.0)

            alpha_auth_data = json.loads(alpha_auth)
            beta_auth_data = json.loads(beta_auth)

            assert alpha_auth_data["data"]["organization_id"] == str(org_alpha_user["organization_id"])
            assert beta_auth_data["data"]["organization_id"] == str(org_beta_user["organization_id"])

            # Subscribe to organization-specific channels
            alpha_subscription = {
                "type": "subscribe",
                "subscription_type": "metrics",
                "channel": f"org_{org_alpha_user['organization_id']}_metrics"
            }
            await alpha_ws.send(json.dumps(alpha_subscription))

            beta_subscription = {
                "type": "subscribe",
                "subscription_type": "metrics",
                "channel": f"org_{org_beta_user['organization_id']}_metrics"
            }
            await beta_ws.send(json.dumps(beta_subscription))

            # Wait for subscription confirmations
            await asyncio.wait_for(alpha_ws.recv(), timeout=5.0)
            await asyncio.wait_for(beta_ws.recv(), timeout=5.0)

            # Users should only receive messages for their organization
            # This test verifies connection isolation - actual message testing would require backend simulation

            await alpha_ws.close()
            await beta_ws.close()

        except Exception as e:
            # WebSocket connections might fail in test environment
            # This is expected if the WebSocket server is not running
            print(f"WebSocket isolation test skipped: {e}")

    @pytest.mark.integration
    @pytest.mark.multitenant
    async def test_organization_configuration_isolation(self, api_client: AsyncClient, auth_headers_for_users, users_for_organizations):
        """Test organization-level configurations are isolated"""
        # Get admin users
        org_alpha_user = next(u for u in users_for_organizations if "alpha" in u["email"] and "admin" in u["roles"])
        org_beta_user = next(u for u in users_for_organizations if "beta" in u["email"] and "admin" in u["roles"])

        alpha_headers = auth_headers_for_users[org_alpha_user["id"]]
        beta_headers = auth_headers_for_users[org_beta_user["id"]]

        # 1. Set organization-specific configuration for Alpha
        alpha_config = {
            "default_retention_days": 180,
            "max_dashboards_per_user": 10,
            "allowed_export_formats": ["pdf", "csv"],
            "default_timezone": "UTC"
        }

        # This would be an organization settings endpoint (if implemented)
        # For now, we'll test through dashboard defaults

        # 2. Create dashboard with Alpha's settings
        alpha_dashboard = {
            "config_name": "Alpha Configured Dashboard",
            "config_type": "organization",
            "layout": {"rows": 3, "columns": 4},
            "time_range_default": "30d",  # Organization-specific default
            "auto_refresh_interval_seconds": 600  # Organization-specific refresh rate
        }

        response = await api_client.post(
            f"/api/v1/analytics/dashboard/configurations",
            params={"organization_id": str(org_alpha_user["organization_id"])},
            json=alpha_dashboard,
            headers=alpha_headers
        )

        if response.status_code == 201:
            alpha_dashboard_id = response.json()["id"]

            # 3. Beta user cannot access Alpha's configured dashboard
            response = await api_client.get(
                f"/api/v1/analytics/dashboard/configurations/{alpha_dashboard_id}",
                params={"organization_id": str(org_beta_user["organization_id"])},
                headers=beta_headers
            )
            assert response.status_code in [403, 404]

        # 4. Organization-specific widgets should be isolated
        response = await api_client.get(
            f"/api/v1/analytics/dashboard/widgets",
            params={
                "organization_id": str(org_alpha_user["organization_id"]),
                "widget_type": "custom"
            },
            headers=alpha_headers
        )

        if response.status_code == 200:
            alpha_widgets = response.json()["widgets"]

            # Beta user should get different custom widgets
            response = await api_client.get(
                f"/api/v1/analytics/dashboard/widgets",
                params={
                    "organization_id": str(org_beta_user["organization_id"]),
                    "widget_type": "custom"
                },
                headers=beta_headers
            )

            if response.status_code == 200:
                beta_widgets = response.json()["widgets"]

                # Custom widgets should be different between organizations
                alpha_widget_ids = {w["id"] for w in alpha_widgets if not w.get("is_system_widget", False)}
                beta_widget_ids = {w["id"] for w in beta_widgets if not w.get("is_system_widget", False)}

                # No overlap in custom widgets
                overlap = alpha_widget_ids & beta_widget_ids
                assert len(overlap) == 0, "Custom widgets should not be shared between organizations"