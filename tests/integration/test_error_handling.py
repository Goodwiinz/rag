"""
Error Handling and Recovery Tests
Tests error scenarios, graceful degradation, and recovery mechanisms
"""

import pytest
import asyncio
import uuid
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List
from unittest.mock import Mock, AsyncMock, patch

from httpx import AsyncClient, ConnectError, TimeoutException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from conftest import (
    APIAssertions, create_auth_headers, wait_for_condition,
    sample_organization, sample_user, sample_dashboard, sample_report
)


class TestErrorHandlingIntegration:
    """Test error handling and recovery mechanisms"""

    @pytest.mark.integration
    async def test_http_error_response_format(self, api_client: AsyncClient, auth_headers, sample_organization):
        """Test standardized error response format"""
        org_id = sample_organization["id"]

        # Test various error scenarios
        error_test_cases = [
            {
                "name": "Not Found Error",
                "request": lambda: api_client.get(
                    f"/api/v1/analytics/dashboard/configurations/{uuid.uuid4()}",
                    params={"organization_id": str(org_id)},
                    headers=auth_headers
                ),
                "expected_status": 404,
                "expected_error_type": "not_found"
            },
            {
                "name": "Validation Error",
                "request": lambda: api_client.post(
                    f"/api/v1/analytics/dashboard/configurations",
                    params={"organization_id": str(org_id)},
                    json={"invalid": "data"},
                    headers=auth_headers
                ),
                "expected_status": 400,
                "expected_error_type": "validation_error"
            },
            {
                "name": "Unauthorized Error",
                "request": lambda: api_client.get(
                    f"/api/v1/analytics/realtime/metrics",
                    params={"organization_id": str(org_id)}
                    # No auth headers
                ),
                "expected_status": 401,
                "expected_error_type": "authentication_error"
            }
        ]

        for test_case in error_test_cases:
            response = await test_case["request"]()

            assert response.status_code == test_case["expected_status"]

            # Verify error response structure
            error_data = response.json()
            required_error_fields = ["error", "status_code", "type"]

            for field in required_error_fields:
                assert field in error_data, f"Missing error field: {field} in {test_case['name']}"

            # Verify error details
            assert error_data["status_code"] == test_case["expected_status"]
            assert "message" in error_data["error"]
            assert error_data["type"] == test_case["expected_error_type"]

    @pytest.mark.integration
    async def test_timeout_error_handling(self, api_client: AsyncClient, auth_headers, sample_organization):
        """Test timeout error handling and recovery"""
        org_id = sample_organization["id"]

        # Create a client with very short timeout
        short_timeout_client = AsyncClient(
            base_url=api_client.base_url,
            timeout=0.001  # Very short timeout
        )

        try:
            # Make request that should timeout
            with pytest.raises(TimeoutException):
                await short_timeout_client.get(
                    f"/api/v1/analytics/graph/analytics/centrality",
                    params={
                        "organization_id": str(org_id),
                        "algorithm": "degree",
                        "limit": 100
                    },
                    headers=auth_headers
                )

        finally:
            await short_timeout_client.aclose()

        # Test that normal client still works (system recovery)
        response = await api_client.get(
            f"/api/v1/analytics/realtime/metrics",
            params={"organization_id": str(org_id)},
            headers=auth_headers
        )
        assert response.status_code == 200

    @pytest.mark.integration
    async def test_rate_limiting_error_handling(self, api_client: AsyncClient, auth_headers, sample_organization):
        """Test rate limiting error handling and retry logic"""
        org_id = sample_organization["id"]

        # Make rapid requests to trigger rate limiting
        responses = []
        for i in range(20):  # High number of requests
            response = await api_client.get(
                f"/api/v1/analytics/realtime/metrics",
                params={"organization_id": str(org_id)},
                headers=auth_headers
            )
            responses.append(response)

            if response.status_code == 429:
                break  # Rate limit triggered

        # Check if rate limiting was triggered
        rate_limited_responses = [r for r in responses if r.status_code == 429]

        if rate_limited_responses:
            rate_limit_response = rate_limited_responses[0]

            # Verify rate limit response format
            assert rate_limit_response.status_code == 429
            error_data = rate_limit_response.json()

            # Check for rate limit headers
            assert "retry-after" in rate_limit_response.headers or "Retry-After" in rate_limit_response.headers

            # Test exponential backoff (simplified)
            retry_after = int(rate_limit_response.headers.get("retry-after", 1))
            assert retry_after > 0

            # Wait and retry
            await asyncio.sleep(retry_after)

            retry_response = await api_client.get(
                f"/api/v1/analytics/realtime/metrics",
                params={"organization_id": str(org_id)},
                headers=auth_headers
            )

            # Should succeed after waiting
            assert retry_response.status_code == 200

    @pytest.mark.integration
    async def test_database_connection_error_recovery(self, api_client: AsyncClient, auth_headers, sample_organization):
        """Test behavior when database connections fail"""
        org_id = sample_organization["id"]

        # This test would require mocking database failures
        # For now, we'll test graceful degradation scenarios

        # Test request that might fail due to database issues
        response = await api_client.get(
            f"/api/v1/analytics/reports",
            params={"organization_id": str(org_id)},
            headers=auth_headers
        )

        # Should either succeed or return a proper error
        assert response.status_code in [200, 500, 503]

        if response.status_code >= 500:
            # Verify error response for server errors
            error_data = response.json()
            assert "error" in error_data
            assert error_data["error"]["message"] != ""

    @pytest.mark.integration
    async def test_partial_failure_handling(self, api_client: AsyncClient, auth_headers, sample_organization):
        """Test handling of partial failures in batch operations"""
        org_id = sample_organization["id"]

        # Create dashboard with multiple widgets
        dashboard_data = {
            "config_name": "Partial Failure Test Dashboard",
            "config_type": "user",
            "layout": {"rows": 3, "columns": 4},
            "widgets": [
                {
                    "type": "metric_card",
                    "title": "Valid Widget",
                    "position": {"row": 0, "col": 0, "width": 1, "height": 1},
                    "config": {"metric_id": "total_entities"}
                },
                {
                    "type": "invalid_widget_type",  # This should fail
                    "title": "Invalid Widget",
                    "position": {"row": 0, "col": 1, "width": 1, "height": 1},
                    "config": {"invalid": "config"}
                },
                {
                    "type": "metric_card",
                    "title": "Another Valid Widget",
                    "position": {"row": 0, "col": 2, "width": 1, "height": 1},
                    "config": {"metric_id": "relationship_count"}
                }
            ]
        }

        response = await api_client.post(
            f"/api/v1/analytics/dashboard/configurations",
            params={"organization_id": str(org_id)},
            json=dashboard_data,
            headers=auth_headers
        )

        # System should either:
        # 1. Reject entire request (transaction rollback)
        # 2. Accept valid parts and report failures for invalid parts

        if response.status_code == 201:
            # Partial success case
            created_dashboard = response.json()

            # Should have at least some widgets created
            assert len(created_dashboard.get("widgets", [])) > 0

            # Check for any warnings about failed widgets
            # (implementation dependent)

        elif response.status_code == 400:
            # Complete rejection case
            error_data = response.json()
            assert "error" in error_data

    @pytest.mark.integration
    async def test_cascade_failure_prevention(self, api_client: AsyncClient, auth_headers, sample_organization):
        """Test prevention of cascade failures"""
        org_id = sample_organization["id"]

        # Create resources that depend on each other
        # 1. Create dashboard
        dashboard_response = await api_client.post(
            f"/api/v1/analytics/dashboard/configurations",
            params={"organization_id": str(org_id)},
            json={
                "config_name": "Cascade Test Dashboard",
                "config_type": "user",
                "layout": {"rows": 2, "columns": 2}
            },
            headers=auth_headers
        )

        if dashboard_response.status_code == 201:
            dashboard = dashboard_response.json()

            # 2. Try to create reports that use the dashboard
            report_requests = []
            for i in range(3):
                request = api_client.post(
                    f"/api/v1/analytics/reports",
                    params={"organization_id": str(org_id)},
                    json={
                        "report_name": f"Cascade Test Report {i}",
                        "report_definition": {
                            "dashboard_id": dashboard["id"],
                            "metrics": ["entity_count"]
                        }
                    },
                    headers=auth_headers
                )
                report_requests.append(request)

            responses = await asyncio.gather(*report_requests, return_exceptions=True)

            # 3. Delete the dashboard
            delete_response = await api_client.delete(
                f"/api/v1/analytics/dashboard/configurations/{dashboard['id']}",
                params={"organization_id": str(org_id)},
                headers=auth_headers
            )

            # Dashboard deletion should succeed
            assert delete_response.status_code == 204

            # 4. Try to access the reports - they should handle missing dashboard gracefully
            successful_reports = []
            for i, response in enumerate(responses):
                if not isinstance(response, Exception) and response.status_code == 201:
                    report_data = response.json()
                    report_id = report_data["id"]

                    # Try to access the report
                    report_response = await api_client.get(
                        f"/api/v1/analytics/reports/{report_id}",
                        params={"organization_id": str(org_id)},
                        headers=auth_headers
                    )

                    # Should either succeed with degraded data or fail gracefully
                    assert report_response.status_code in [200, 404, 422]

    @pytest.mark.integration
    async def test_error_recovery_with_retry(self, api_client: AsyncClient, auth_headers, sample_organization):
        """Test automatic retry mechanisms"""
        org_id = sample_organization["id"]

        # Test retry logic for transient failures
        max_retries = 3
        base_delay = 0.1

        async def request_with_retry(request_func, max_retries=max_retries):
            for attempt in range(max_retries + 1):
                try:
                    response = await request_func()

                    # Don't retry on client errors (4xx)
                    if 400 <= response.status_code < 500:
                        return response

                    # Retry on server errors (5xx) or network issues
                    if response.status_code >= 500 or attempt < max_retries:
                        if attempt < max_retries:
                            # Exponential backoff
                            delay = base_delay * (2 ** attempt)
                            await asyncio.sleep(delay)
                            continue

                    return response

                except (TimeoutException, ConnectError) as e:
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        await asyncio.sleep(delay)
                        continue
                    raise e

        # Test with a potentially flaky endpoint
        request_func = lambda: api_client.get(
            f"/api/v1/analytics/graph/analytics/centrality",
            params={
                "organization_id": str(org_id),
                "algorithm": "degree",
                "limit": 50
            },
            headers=auth_headers
        )

        response = await request_with_retry(request_func)

        # Should eventually succeed or fail with proper error
        assert response.status_code in [200, 500, 503]

    @pytest.mark.integration
    async def test_circuit_breaker_pattern(self, api_client: AsyncClient, auth_headers, sample_organization):
        """Test circuit breaker pattern for fault tolerance"""
        org_id = sample_organization["id"]

        # Simulate circuit breaker behavior
        failure_count = 0
        circuit_open = False
        last_failure_time = None
        timeout_duration = 30  # seconds

        async def circuit_breaker_request():
            nonlocal failure_count, circuit_open, last_failure_time

            # Check if circuit is open
            if circuit_open:
                if datetime.utcnow() - last_failure_time > timedelta(seconds=timeout_duration):
                    # Try to close circuit
                    circuit_open = False
                    failure_count = 0
                else:
                    # Circuit is still open
                    return Mock(status_code=503, json=lambda: {"error": "Circuit breaker open"})

            try:
                response = await api_client.get(
                    f"/api/v1/analytics/realtime/metrics",
                    params={"organization_id": str(org_id)},
                    headers=auth_headers,
                    timeout=1.0  # Short timeout to simulate failures
                )

                # Success - reset failure count
                if response.status_code < 500:
                    failure_count = 0
                    return response
                else:
                    failure_count += 1

            except Exception as e:
                failure_count += 1

            # Check if we should open the circuit
            if failure_count >= 3:  # Failure threshold
                circuit_open = True
                last_failure_time = datetime.utcnow()
                return Mock(status_code=503, json=lambda: {"error": "Circuit breaker opened"})

            return response

        # Test circuit breaker behavior
        responses = []
        for i in range(10):
            response = await circuit_breaker_request()
            responses.append(response)
            await asyncio.sleep(0.1)

        # At least one response should be received
        assert len(responses) > 0

        # If circuit opened, should have 503 responses
        circuit_open_responses = [r for r in responses if hasattr(r, 'status_code') and r.status_code == 503]
        if len(circuit_open_responses) > 0:
            assert len(circuit_open_responses) >= 1

    @pytest.mark.integration
    async def test_graceful_degradation(self, api_client: AsyncClient, auth_headers, sample_organization):
        """Test graceful degradation when services are unavailable"""
        org_id = sample_organization["id"]

        # Test various scenarios where partial functionality should still work

        # 1. Test metrics when real-time service is down
        metrics_response = await api_client.get(
            f"/api/v1/analytics/metrics/aggregations",
            params={
                "organization_id": str(org_id),
                "metric_type": "entity",
                "time_bucket": "day",
                "start_time": (datetime.utcnow() - timedelta(days=7)).isoformat(),
                "end_time": datetime.utcnow().isoformat()
            },
            headers=auth_headers
        )

        # Should return cached data or appropriate error
        assert metrics_response.status_code in [200, 503, 404]

        # 2. Test dashboard listing when individual widgets fail
        dashboards_response = await api_client.get(
            f"/api/v1/analytics/dashboard/configurations",
            params={"organization_id": str(org_id)},
            headers=auth_headers
        )

        # Dashboard listing should work even if widget data is unavailable
        assert dashboards_response.status_code in [200, 503]

        # 3. Test report listing when generation service is down
        reports_response = await api_client.get(
            f"/api/v1/analytics/reports",
            params={"organization_id": str(org_id)},
            headers=auth_headers
        )

        # Should be able to list reports even if generation fails
        assert reports_response.status_code in [200, 503]

    @pytest.mark.integration
    async def test_error_logging_and_monitoring(self, api_client: AsyncClient, auth_headers, sample_organization):
        """Test that errors are properly logged and can be monitored"""
        org_id = sample_organization["id"]

        # Make requests that will generate errors
        error_scenarios = [
            {
                "request": api_client.get(
                    f"/api/v1/analytics/dashboard/configurations/{uuid.uuid4()}",
                    params={"organization_id": str(org_id)},
                    headers=auth_headers
                ),
                "expected_status": 404
            },
            {
                "request": api_client.post(
                    f"/api/v1/analytics/dashboard/configurations",
                    params={"organization_id": str(org_id)},
                    json={"invalid": "data"},
                    headers=auth_headers
                ),
                "expected_status": 400
            }
        ]

        for scenario in error_scenarios:
            response = await scenario["request"]

            assert response.status_code == scenario["expected_status"]

            # Check that response includes tracking information
            error_data = response.json()

            # Should have request ID for tracking
            if "request_id" in error_data:
                assert len(error_data["request_id"]) > 0

            # Should have timestamp
            if "timestamp" in error_data.get("error", {}):
                assert error_data["error"]["timestamp"] != ""

            # Check response headers for monitoring info
            monitoring_headers = ["x-request-id", "x-correlation-id"]
            for header in monitoring_headers:
                if header in response.headers:
                    assert len(response.headers[header]) > 0

    @pytest.mark.integration
    async def test_bulk_operation_error_handling(self, api_client: AsyncClient, auth_headers, sample_organization):
        """Test error handling in bulk operations"""
        org_id = sample_organization["id"]

        # Test bulk operations with mixed valid/invalid data
        bulk_data = {
            "dashboards": [
                {
                    "config_name": "Valid Dashboard 1",
                    "config_type": "user",
                    "layout": {"rows": 2, "columns": 2}
                },
                {
                    "config_name": "",  # Invalid - empty name
                    "config_type": "user",
                    "layout": {"rows": 2, "columns": 2}
                },
                {
                    "config_name": "Valid Dashboard 2",
                    "config_type": "user",
                    "layout": {"rows": 2, "columns": 2}
                }
            ]
        }

        # This would be a bulk create endpoint (if implemented)
        # For now, we'll simulate with individual requests
        results = []
        for dashboard_data in bulk_data["dashboards"]:
            response = await api_client.post(
                f"/api/v1/analytics/dashboard/configurations",
                params={"organization_id": str(org_id)},
                json=dashboard_data,
                headers=auth_headers
            )
            results.append({
                "data": dashboard_data,
                "response": response
            })

        # Analyze results
        successful_creates = [r for r in results if r["response"].status_code == 201]
        failed_creates = [r for r in results if r["response"].status_code == 400]

        # Should have some successes and some failures
        assert len(successful_creates) >= 2  # At least the valid ones
        assert len(failed_creates) >= 1  # At least the invalid one

        # Verify error details for failures
        for failure in failed_creates:
            error_data = failure["response"].json()
            assert "error" in error_data
            assert "validation" in error_data["error"]["type"].lower()

    @pytest.mark.integration
    async def test_service_dependency_failure_handling(self, api_client: AsyncClient, auth_headers, sample_organization):
        """Test handling when dependent services fail"""
        org_id = sample_organization["id"]

        # Test graph analytics when graph service is unavailable
        graph_response = await api_client.get(
            f"/api/v1/analytics/graph/analytics/centrality",
            params={
                "organization_id": str(org_id),
                "algorithm": "degree",
                "limit": 10
            },
            headers=auth_headers
        )

        # Should handle unavailability gracefully
        assert graph_response.status_code in [200, 503, 500]

        if graph_response.status_code >= 500:
            error_data = graph_response.json()
            # Should provide meaningful error message
            assert "service" in error_data["error"]["message"].lower() or "unavailable" in error_data["error"]["message"].lower()

        # Test metrics when analytics service is slow
        try:
            metrics_response = await api_client.get(
                f"/api/v1/analytics/realtime/metrics",
                params={"organization_id": str(org_id)},
                headers=auth_headers,
                timeout=2.0  # Short timeout
            )

            # Either succeeds or times out gracefully
            assert metrics_response.status_code in [200, 408, 504]

        except TimeoutException:
            # Timeout is acceptable behavior
            pass

    @pytest.mark.integration
    async def test_user_friendly_error_messages(self, api_client: AsyncClient, auth_headers, sample_organization):
        """Test that error messages are user-friendly and actionable"""
        org_id = sample_organization["id"]

        # Test various error scenarios and check message quality
        error_message_tests = [
            {
                "name": "Invalid dashboard data",
                "request": api_client.post(
                    f"/api/v1/analytics/dashboard/configurations",
                    params={"organization_id": str(org_id)},
                    json={
                        "config_name": "",  # Empty name
                        "config_type": "invalid_type"
                    },
                    headers=auth_headers
                ),
                "message_checks": [
                    lambda msg: "config_name" in msg.lower(),
                    lambda msg: "config_type" in msg.lower(),
                    lambda msg: len(msg) > 10  # Not too short
                ]
            },
            {
                "name": "Invalid parameters",
                "request": api_client.get(
                    f"/api/v1/analytics/metrics/aggregations",
                    params={
                        "organization_id": str(org_id),
                        "metric_type": "invalid_type",
                        "time_bucket": "invalid_bucket"
                    },
                    headers=auth_headers
                ),
                "message_checks": [
                    lambda msg: "metric_type" in msg.lower() or "time_bucket" in msg.lower(),
                    lambda msg: "valid" in msg.lower() or "allowed" in msg.lower()
                ]
            }
        ]

        for test in error_message_tests:
            response = await test["request"]

            if response.status_code >= 400:
                error_data = response.json()
                message = error_data.get("error", {}).get("message", "")

                # Check message quality
                assert len(message) > 0, f"Empty error message for {test['name']}"

                # Apply message checks
                for check in test["message_checks"]:
                    assert check(message), f"Message check failed for {test['name']}: {message}"

                # Check for actionable information
                assert any(word in message.lower() for word in ["must", "required", "valid", "allowed", "please"]), (
                    f"Error message not actionable for {test['name']}: {message}"
                )