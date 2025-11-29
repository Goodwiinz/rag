"""
Data Validation Tests
Tests data integrity, validation, and consistency across the full stack
"""

import pytest
import asyncio
import uuid
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from httpx import AsyncClient

from conftest import (
    APIAssertions, create_auth_headers, wait_for_condition,
    sample_organization, sample_user, sample_dashboard, sample_report,
    sample_metrics_data
)


class TestDataValidationIntegration:
    """Test data validation and integrity across the system"""

    @pytest.mark.integration
    async def test_input_validation_on_create(self, api_client: AsyncClient, auth_headers, sample_organization):
        """Test input validation when creating resources"""
        org_id = sample_organization["id"]

        # Test dashboard creation with invalid data
        invalid_dashboard_cases = [
            {
                "name": "Empty name",
                "data": {
                    "config_name": "",  # Empty name should fail
                    "config_type": "user",
                    "layout": {}
                },
                "expected_error": "config_name"
            },
            {
                "name": "Invalid config type",
                "data": {
                    "config_name": "Test Dashboard",
                    "config_type": "invalid_type",  # Invalid enum value
                    "layout": {}
                },
                "expected_error": "config_type"
            },
            {
                "name": "Invalid refresh interval",
                "data": {
                    "config_name": "Test Dashboard",
                    "config_type": "user",
                    "layout": {},
                    "auto_refresh_interval_seconds": 30  # Too low (should be >= 60)
                },
                "expected_error": "auto_refresh_interval_seconds"
            },
            {
                "name": "Invalid layout structure",
                "data": {
                    "config_name": "Test Dashboard",
                    "config_type": "user",
                    "layout": "invalid_structure"  # Should be object
                },
                "expected_error": "layout"
            }
        ]

        for test_case in invalid_dashboard_cases:
            response = await api_client.post(
                f"/api/v1/analytics/dashboard/configurations",
                params={"organization_id": str(org_id)},
                json=test_case["data"],
                headers=auth_headers
            )

            assert response.status_code == 400, f"Expected validation error for {test_case['name']}"
            error_data = response.json()
            assert test_case["expected_error"] in str(error_data).lower()

        # Test report creation with invalid data
        invalid_report_cases = [
            {
                "name": "Missing required fields",
                "data": {
                    "report_description": "Missing report_name"
                },
                "expected_error": "report_name"
            },
            {
                "name": "Invalid output format",
                "data": {
                    "report_name": "Test Report",
                    "output_formats": ["invalid_format"]
                },
                "expected_error": "output_formats"
            }
        ]

        for test_case in invalid_report_cases:
            response = await api_client.post(
                f"/api/v1/analytics/reports",
                params={"organization_id": str(org_id)},
                json=test_case["data"],
                headers=auth_headers
            )

            assert response.status_code == 400, f"Expected validation error for {test_case['name']}"

    @pytest.mark.integration
    async def test_data_type_validation(self, api_client: AsyncClient, auth_headers, sample_organization):
        """Test data type validation for API inputs"""
        org_id = sample_organization["id"]

        # Test metrics aggregation endpoint with invalid data types
        invalid_metrics_cases = [
            {
                "name": "Invalid time bucket",
                "params": {
                    "organization_id": str(org_id),
                    "metric_type": "entity",
                    "time_bucket": "invalid_bucket",  # Should be hour, day, week, month
                    "start_time": datetime.utcnow().isoformat(),
                    "end_time": datetime.utcnow().isoformat()
                },
                "expected_error": "time_bucket"
            },
            {
                "name": "Invalid date format",
                "params": {
                    "organization_id": str(org_id),
                    "metric_type": "entity",
                    "time_bucket": "hour",
                    "start_time": "invalid-date",  # Invalid ISO format
                    "end_time": datetime.utcnow().isoformat()
                },
                "expected_error": "start_time"
            },
            {
                "name": "End time before start time",
                "params": {
                    "organization_id": str(org_id),
                    "metric_type": "entity",
                    "time_bucket": "hour",
                    "start_time": datetime.utcnow().isoformat(),
                    "end_time": (datetime.utcnow() - timedelta(hours=1)).isoformat()  # Earlier than start
                },
                "expected_error": "time_range"
            }
        ]

        for test_case in invalid_metrics_cases:
            response = await api_client.get(
                f"/api/v1/analytics/metrics/aggregations",
                params=test_case["params"],
                headers=auth_headers
            )

            assert response.status_code == 400, f"Expected validation error for {test_case['name']}"

    @pytest.mark.integration
    async def test_uuid_validation(self, api_client: AsyncClient, auth_headers, sample_organization):
        """Test UUID format validation"""
        org_id = sample_organization["id"]

        # Test cases with invalid UUIDs
        invalid_uuid_cases = [
            {
                "name": "Invalid UUID format",
                "uuid": "invalid-uuid-format",
                "endpoint": f"/api/v1/analytics/dashboard/configurations/invalid-uuid-format"
            },
            {
                "name": "Short UUID",
                "uuid": "123e4567-e89b-12d3",  # Too short
                "endpoint": f"/api/v1/analytics/dashboard/configurations/123e4567-e89b-12d3"
            },
            {
                "name": "Non-UUID characters",
                "uuid": "123e4567-g89b-12d3-a456-426614174000",  # Contains 'g'
                "endpoint": f"/api/v1/analytics/dashboard/configurations/123e4567-g89b-12d3-a456-426614174000"
            }
        ]

        for test_case in invalid_uuid_cases:
            response = await api_client.get(
                test_case["endpoint"],
                params={"organization_id": str(org_id)},
                headers=auth_headers
            )

            # Should return 400 (Bad Request) for invalid UUID format
            assert response.status_code == 400, f"Expected validation error for {test_case['name']}"

    @pytest.mark.integration
    async def test_numeric_validation(self, api_client: AsyncClient, auth_headers, sample_organization):
        """Test numeric value validation and constraints"""
        org_id = sample_organization["id"]

        # Test graph centrality endpoint with invalid numeric parameters
        invalid_numeric_cases = [
            {
                "name": "Negative limit",
                "params": {
                    "organization_id": str(org_id),
                    "algorithm": "degree",
                    "limit": -10  # Should be positive
                },
                "expected_error": "limit"
            },
            {
                "name": "Limit exceeds maximum",
                "params": {
                    "organization_id": str(org_id),
                    "algorithm": "degree",
                    "limit": 2000  # Exceeds max of 1000
                },
                "expected_error": "limit"
            },
            {
                "name": "Invalid refresh interval",
                "params": {
                    "organization_id": str(org_id),
                    "refresh_interval": 500  # Exceeds max of 300
                },
                "expected_error": "refresh_interval"
            }
        ]

        for test_case in invalid_numeric_cases:
            response = await api_client.get(
                f"/api/v1/analytics/graph/analytics/centrality",
                params=test_case["params"],
                headers=auth_headers
            )

            assert response.status_code == 400, f"Expected validation error for {test_case['name']}"

    @pytest.mark.integration
    async def test_string_length_validation(self, api_client: AsyncClient, auth_headers, sample_organization):
        """Test string length validation constraints"""
        org_id = sample_organization["id"]

        # Test cases with strings that exceed length limits
        long_string = "x" * 300  # 300 characters

        invalid_length_cases = [
            {
                "name": "Dashboard name too long",
                "data": {
                    "config_name": long_string,  # Exceeds typical 255 char limit
                    "config_type": "user",
                    "layout": {}
                },
                "expected_error": "config_name"
            },
            {
                "name": "Report name too long",
                "data": {
                    "report_name": long_string,
                    "report_definition": {"metrics": ["test"]}
                },
                "expected_error": "report_name"
            },
            {
                "name": "Alert name too long",
                "data": {
                    "alert_name": long_string,
                    "alert_type": "metric_threshold",
                    "alert_condition": {"metric": "test"},
                    "severity": "warning"
                },
                "expected_error": "alert_name"
            }
        ]

        for test_case in invalid_length_cases:
            if "dashboard" in test_case["name"]:
                response = await api_client.post(
                    f"/api/v1/analytics/dashboard/configurations",
                    params={"organization_id": str(org_id)},
                    json=test_case["data"],
                    headers=auth_headers
                )
            elif "report" in test_case["name"]:
                response = await api_client.post(
                    f"/api/v1/analytics/reports",
                    params={"organization_id": str(org_id)},
                    json=test_case["data"],
                    headers=auth_headers
                )
            elif "alert" in test_case["name"]:
                response = await api_client.post(
                    f"/api/v1/analytics/alerts",
                    params={"organization_id": str(org_id)},
                    json=test_case["data"],
                    headers=auth_headers
                )

            assert response.status_code == 400, f"Expected validation error for {test_case['name']}"

    @pytest.mark.integration
    async def test_json_structure_validation(self, api_client: AsyncClient, auth_headers, sample_organization):
        """Test JSON structure and schema validation"""
        org_id = sample_organization["id"]

        # Test cases with invalid JSON structures
        invalid_json_cases = [
            {
                "name": "Invalid dashboard layout",
                "data": {
                    "config_name": "Test Dashboard",
                    "config_type": "user",
                    "layout": {
                        "rows": "invalid",  # Should be integer
                        "columns": 4
                    }
                },
                "expected_error": "layout"
            },
            {
                "name": "Invalid widget position",
                "data": {
                    "config_name": "Test Dashboard",
                    "config_type": "user",
                    "layout": {
                        "rows": 3,
                        "columns": 4
                    },
                    "widgets": [
                        {
                            "position": {
                                "row": "invalid",  # Should be integer
                                "col": 0,
                                "width": 1,
                                "height": 1
                            }
                        }
                    ]
                },
                "expected_error": "widgets"
            },
            {
                "name": "Invalid alert condition",
                "data": {
                    "alert_name": "Test Alert",
                    "alert_type": "metric_threshold",
                    "alert_condition": "invalid_structure",  # Should be object
                    "severity": "warning"
                },
                "expected_error": "alert_condition"
            }
        ]

        for test_case in invalid_json_cases:
            response = await api_client.post(
                f"/api/v1/analytics/dashboard/configurations",
                params={"organization_id": str(org_id)},
                json=test_case["data"],
                headers=auth_headers
            )

            assert response.status_code == 400, f"Expected validation error for {test_case['name']}"

    @pytest.mark.integration
    async def test_data_consistency_validation(self, api_client: AsyncClient, auth_headers, sample_organization, test_db_session: AsyncSession):
        """Test data consistency between API and database"""
        org_id = sample_organization["id"]

        # 1. Create dashboard via API
        create_data = {
            "config_name": "Consistency Test Dashboard",
            "config_type": "user",
            "layout": {"rows": 2, "columns": 3},
            "widgets": [
                {
                    "type": "metric_card",
                    "position": {"row": 0, "col": 0, "width": 1, "height": 1},
                    "config": {"metric_id": "total_entities"}
                }
            ]
        }

        response = await api_client.post(
            f"/api/v1/analytics/dashboard/configurations",
            params={"organization_id": str(org_id)},
            json=create_data,
            headers=auth_headers
        )

        assert response.status_code == 201
        api_data = response.json()

        # 2. Verify data in database
        query = text("""
            SELECT config_name, config_type, layout, widgets, organization_id, created_at
            FROM dashboard_configurations
            WHERE id = :dashboard_id
        """)

        result = await test_db_session.execute(query, {"dashboard_id": api_data["id"]})
        db_record = result.fetchone()

        assert db_record is not None
        assert db_record["config_name"] == create_data["config_name"]
        assert db_record["config_type"] == create_data["config_type"]
        assert db_record["organization_id"] == org_id

        # Verify JSON fields are properly stored
        assert isinstance(db_record["layout"], dict)
        assert isinstance(db_record["widgets"], list)

        # 3. Update via API
        update_data = {
            "config_name": "Updated Consistency Test Dashboard",
            "layout": {"rows": 4, "columns": 4}
        }

        response = await api_client.put(
            f"/api/v1/analytics/dashboard/configurations/{api_data['id']}",
            params={"organization_id": str(org_id)},
            json=update_data,
            headers=auth_headers
        )

        assert response.status_code == 200
        updated_api_data = response.json()

        # 4. Verify update in database
        result = await test_db_session.execute(query, {"dashboard_id": api_data["id"]})
        updated_db_record = result.fetchone()

        assert updated_db_record["config_name"] == update_data["config_name"]
        assert updated_db_record["layout"]["rows"] == 4
        assert updated_db_record["layout"]["columns"] == 4

        # 5. Verify updated_at timestamp
        assert updated_db_record["created_at"] == db_record["created_at"]  # Should not change
        # updated_at should be more recent (implementation dependent)

    @pytest.mark.integration
    async def test_referential_integrity_validation(self, api_client: AsyncClient, auth_headers, sample_organization):
        """Test referential integrity constraints"""
        org_id = sample_organization["id"]

        # 1. Try to create dashboard for non-existent organization
        fake_org_id = uuid.uuid4()
        response = await api_client.post(
            f"/api/v1/analytics/dashboard/configurations",
            params={"organization_id": str(fake_org_id)},
            json={
                "config_name": "Test Dashboard",
                "config_type": "user"
            },
            headers=auth_headers
        )

        # Should fail due to foreign key constraint
        assert response.status_code in [400, 403, 404]

        # 2. Try to access non-existent dashboard
        fake_dashboard_id = uuid.uuid4()
        response = await api_client.get(
            f"/api/v1/analytics/dashboard/configurations/{fake_dashboard_id}",
            params={"organization_id": str(org_id)},
            headers=auth_headers
        )

        assert response.status_code == 404

        # 3. Try to update non-existent dashboard
        response = await api_client.put(
            f"/api/v1/analytics/dashboard/configurations/{fake_dashboard_id}",
            params={"organization_id": str(org_id)},
            json={"config_name": "Updated"},
            headers=auth_headers
        )

        assert response.status_code == 404

        # 4. Try to delete non-existent dashboard
        response = await api_client.delete(
            f"/api/v1/analytics/dashboard/configurations/{fake_dashboard_id}",
            params={"organization_id": str(org_id)},
            headers=auth_headers
        )

        assert response.status_code == 404

    @pytest.mark.integration
    async def test_data_sanitization(self, api_client: AsyncClient, auth_headers, sample_organization):
        """Test data sanitization and security"""
        org_id = sample_organization["id"]

        # Test cases with potentially malicious input
        malicious_inputs = [
            {
                "name": "SQL injection attempt",
                "config_name": "'; DROP TABLE dashboard_configurations; --",
                "description": "<script>alert('xss')</script>"
            },
            {
                "name": "XSS attempt in widget",
                "config_name": "Safe Dashboard",
                "widgets": [
                    {
                        "type": "text",
                        "content": "<img src=x onerror=alert('xss')>",
                        "title": "Safe Title"
                    }
                ]
            },
            {
                "name": "Path traversal attempt",
                "config_name": "../../../etc/passwd",
                "description": "Config with path traversal"
            }
        ]

        for malicious_input in malicious_inputs:
            response = await api_client.post(
                f"/api/v1/analytics/dashboard/configurations",
                params={"organization_id": str(org_id)},
                json=malicious_input,
                headers=auth_headers
            )

            if response.status_code == 201:
                # If creation succeeds, verify data was sanitized
                created_data = response.json()

                # Check that HTML/script tags were removed or escaped
                assert "<script>" not in created_data.get("description", "")
                assert "javascript:" not in created_data.get("description", "")
                assert "../" not in created_data.get("config_name", "")

            elif response.status_code == 400:
                # Input was rejected, which is also acceptable
                pass

    @pytest.mark.integration
    async def test_numeric_precision_validation(self, api_client: AsyncClient, auth_headers, sample_organization):
        """Test numeric precision and scale validation"""
        org_id = sample_organization["id"]

        # Test cases with high precision numbers
        precision_cases = [
            {
                "name": "High precision decimal",
                "data": {
                    "alert_name": "Precision Test Alert",
                    "alert_type": "metric_threshold",
                    "alert_condition": {
                        "metric": "test_metric",
                        "threshold": 123456789.123456789  # High precision decimal
                    },
                    "severity": "warning"
                }
            },
            {
                "name": "Very large number",
                "data": {
                    "alert_name": "Large Number Alert",
                    "alert_type": "metric_threshold",
                    "alert_condition": {
                        "metric": "test_metric",
                        "threshold": 999999999999999999  # Very large integer
                    },
                    "severity": "warning"
                }
            },
            {
                "name": "Very small number",
                "data": {
                    "alert_name": "Small Number Alert",
                    "alert_type": "metric_threshold",
                    "alert_condition": {
                        "metric": "test_metric",
                        "threshold": 0.0000000001  # Very small decimal
                    },
                    "severity": "warning"
                }
            }
        ]

        for test_case in precision_cases:
            response = await api_client.post(
                f"/api/v1/analytics/alerts",
                params={"organization_id": str(org_id)},
                json=test_case["data"],
                headers=auth_headers
            )

            # Should either accept with proper rounding/truncation or reject with validation error
            assert response.status_code in [201, 400]

            if response.status_code == 201:
                # If accepted, verify the number was stored appropriately
                alert_data = response.json()
                threshold = alert_data.get("alert_condition", {}).get("threshold")
                assert threshold is not None

    @pytest.mark.integration
    async def test_timezone_and_date_validation(self, api_client: AsyncClient, auth_headers, sample_organization):
        """Test timezone handling and date validation"""
        org_id = sample_organization["id"]

        # Test various date/time formats
        date_test_cases = [
            {
                "name": "Valid ISO datetime",
                "start_time": "2024-01-01T00:00:00Z",
                "end_time": "2024-01-31T23:59:59Z",
                "should_succeed": True
            },
            {
                "name": "Invalid datetime format",
                "start_time": "2024-01-01 00:00:00",  # Missing 'T'
                "end_time": "2024-01-31T23:59:59Z",
                "should_succeed": False
            },
            {
                "name": "Future date",
                "start_time": (datetime.utcnow() + timedelta(days=30)).isoformat() + "Z",
                "end_time": (datetime.utcnow() + timedelta(days=60)).isoformat() + "Z",
                "should_succeed": True  # Future dates might be allowed
            },
            {
                "name": "Very old date",
                "start_time": "1900-01-01T00:00:00Z",
                "end_time": "1900-12-31T23:59:59Z",
                "should_succeed": False  # Likely too old
            }
        ]

        for test_case in date_test_cases:
            response = await api_client.get(
                f"/api/v1/analytics/metrics/aggregations",
                params={
                    "organization_id": str(org_id),
                    "metric_type": "entity",
                    "time_bucket": "day",
                    "start_time": test_case["start_time"],
                    "end_time": test_case["end_time"]
                },
                headers=auth_headers
            )

            if test_case["should_succeed"]:
                assert response.status_code in [200, 404], f"Expected success for {test_case['name']}"
            else:
                assert response.status_code == 400, f"Expected validation error for {test_case['name']}"

    @pytest.mark.integration
    async def test_concurrent_data_validation(self, api_client: AsyncClient, auth_headers, sample_organization):
        """Test data validation under concurrent conditions"""
        org_id = sample_organization["id"]

        # Create multiple requests with the same data to test uniqueness constraints
        dashboard_name = "Concurrent Test Dashboard"

        async def create_dashboard():
            return await api_client.post(
                f"/api/v1/analytics/dashboard/configurations",
                params={"organization_id": str(org_id)},
                json={
                    "config_name": dashboard_name,
                    "config_type": "user",
                    "layout": {"rows": 2, "columns": 2}
                },
                headers=auth_headers
            )

        # Make concurrent requests
        tasks = [create_dashboard() for _ in range(5)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Analyze results
        success_count = sum(1 for r in responses if not isinstance(r, Exception) and r.status_code == 201)
        conflict_count = sum(1 for r in responses if not isinstance(r, Exception) and r.status_code == 409)
        error_count = sum(1 for r in responses if isinstance(r, Exception))

        # At least one should succeed
        assert success_count >= 1, "At least one dashboard creation should succeed"

        # If uniqueness constraints are enforced, others should get conflict errors
        if success_count > 1:
            # Multiple succeeded - uniqueness might not be enforced on names
            pass
        else:
            # Only one succeeded - others should get conflict or validation errors
            assert conflict_count + error_count >= 4, "Other requests should fail due to constraints"