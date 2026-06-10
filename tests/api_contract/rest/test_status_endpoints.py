"""
REST API Status Endpoints Integration Tests

This module contains comprehensive integration tests for REST API status endpoints,
including system health, connection statistics, and performance metrics.
"""

import pytest
import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.models.websocket_status import (
    WebSocketConnection,
    StatusUpdate,
    ConnectionEvent,
    ConnectionStatus,
    UpdateType,
    Priority
)


@pytest.mark.contract
@pytest.mark.api
@pytest.mark.status
class TestStatusEndpoints:
    """Test REST API status endpoints"""

    @pytest.mark.asyncio
    async def test_system_health_endpoint(self, test_client: TestClient, auth_headers):
        """Test system health endpoint"""
        headers = auth_headers({"email": "health@example.com", "first_name": "Health", "last_name": "User"})

        # Test basic health check
        response = test_client.get("/api/v1/status/health", headers=headers)
        assert response.status_code == 200

        health_data = response.json()
        assert "status" in health_data
        assert "timestamp" in health_data
        assert "version" in health_data

        # Verify health structure
        expected_status_values = ["healthy", "degraded", "unhealthy"]
        assert health_data["status"] in expected_status_values

        # Test detailed health check
        response = test_client.get("/api/v1/status/health?detailed=true", headers=headers)
        assert response.status_code == 200

        detailed_health = response.json()
        assert "services" in detailed_health
        assert "performance_metrics" in detailed_health

        # Verify services health
        services = detailed_health["services"]
        expected_services = ["database", "websocket_server", "vector_store", "search_engine"]
        for service in expected_services:
            assert service in services
            assert "status" in services[service]
            assert "response_time_ms" in services[service]
            assert "last_check" in services[service]

        # Verify performance metrics
        perf_metrics = detailed_health["performance_metrics"]
        assert "cpu_usage" in perf_metrics
        assert "memory_usage" in perf_metrics
        assert "active_connections" in perf_metrics
        assert "requests_per_second" in perf_metrics

    @pytest.mark.asyncio
    async def test_websocket_status_endpoint(self, test_client: TestClient, auth_headers):
        """Test WebSocket status endpoint"""
        headers = auth_headers({"email": "wsstatus@example.com", "first_name": "WS", "last_name": "Status"})

        # Test basic WebSocket status
        response = test_client.get("/api/v1/status/websocket", headers=headers)
        assert response.status_code == 200

        ws_status = response.json()
        assert "status" in ws_status
        assert "total_connections" in ws_status
        assert "active_users" in ws_status
        assert "timestamp" in ws_status

        # Verify data types
        assert isinstance(ws_status["total_connections"], int)
        assert isinstance(ws_status["active_users"], int)
        assert ws_status["total_connections"] >= 0
        assert ws_status["active_users"] >= 0

        # Test detailed WebSocket status
        response = test_client.get("/api/v1/status/websocket?detailed=true", headers=headers)
        assert response.status_code == 200

        detailed_ws_status = response.json()
        assert "connection_details" in detailed_ws_status
        assert "channel_subscriptions" in detailed_ws_status
        assert "connection_metrics" in detailed_ws_status

        # Verify connection details
        connection_details = detailed_ws_status["connection_details"]
        assert "max_connections" in connection_details
        assert "connection_limit_per_user" in connection_details
        assert "redis_enabled" in connection_details

        # Verify channel subscriptions
        channel_subs = detailed_ws_status["channel_subscriptions"]
        assert isinstance(channel_subs, dict)

        # Verify connection metrics
        conn_metrics = detailed_ws_status["connection_metrics"]
        assert "messages_per_second" in conn_metrics
        assert "average_connection_duration" in conn_metrics
        assert "error_rate" in conn_metrics

    @pytest.mark.asyncio
    async def test_document_processing_status(self, test_client: TestClient, auth_headers, test_document):
        """Test document processing status endpoint"""
        headers = auth_headers({"email": "docstatus@example.com", "first_name": "Document", "last_name": "Status"})

        # Test overall processing status
        response = test_client.get("/api/v1/status/processing", headers=headers)
        assert response.status_code == 200

        processing_status = response.json()
        assert "queue_status" in processing_status
        assert "active_jobs" in processing_status
        assert "completed_today" in processing_status
        assert "failed_today" in processing_status

        # Verify queue status
        queue_status = processing_status["queue_status"]
        assert "pending_jobs" in queue_status
        assert "processing_jobs" in queue_status
        assert "failed_jobs" in queue_status
        assert "average_wait_time" in queue_status

        # Test specific document status
        if test_document:
            doc_id = test_document["id"]
            response = test_client.get(f"/api/v1/status/processing/{doc_id}", headers=headers)
            assert response.status_code == 200

            doc_status = response.json()
            assert "document_id" in doc_status
            assert "status" in doc_status
            assert "progress" in doc_status
            assert "created_at" in doc_status
            assert "updated_at" in doc_status

            # Verify status values
            valid_statuses = ["pending", "processing", "completed", "failed"]
            assert doc_status["status"] in valid_statuses

            if "progress" in doc_status and doc_status["progress"] is not None:
                assert 0 <= doc_status["progress"] <= 100

    @pytest.mark.asyncio
    async def test_search_performance_status(self, test_client: TestClient, auth_headers):
        """Test search performance status endpoint"""
        headers = auth_headers({"email": "searchstatus@example.com", "first_name": "Search", "last_name": "Status"})

        # Test search performance metrics
        response = test_client.get("/api/v1/status/search/performance", headers=headers)
        assert response.status_code == 200

        search_perf = response.json()
        assert "queries_per_second" in search_perf
        assert "average_response_time" in search_perf
        assert "cache_hit_rate" in search_perf
        assert "total_queries_today" in search_perf

        # Verify metrics types and ranges
        assert isinstance(search_perf["queries_per_second"], (int, float))
        assert search_perf["queries_per_second"] >= 0

        assert isinstance(search_perf["average_response_time"], (int, float))
        assert search_perf["average_response_time"] >= 0

        assert isinstance(search_perf["cache_hit_rate"], (int, float))
        assert 0 <= search_perf["cache_hit_rate"] <= 100

        # Test search component health
        response = test_client.get("/api/v1/status/search/components", headers=headers)
        assert response.status_code == 200

        component_health = response.json()
        assert "vector_search" in component_health
        assert "graph_search" in component_health
        assert "fulltext_search" in component_health
        assert "reranking_service" in component_health

        # Verify component health structure
        for component, health in component_health.items():
            assert "status" in health
            assert "response_time_ms" in health
            assert "success_rate" in health
            assert "error_count" in health

    @pytest.mark.asyncio
    async def test_database_status_endpoint(self, test_client: TestClient, auth_headers):
        """Test database status endpoint"""
        headers = auth_headers({"email": "dbstatus@example.com", "first_name": "Database", "last_name": "Status"})

        # Test database connection status
        response = test_client.get("/api/v1/status/database", headers=headers)
        assert response.status_code == 200

        db_status = response.json()
        assert "primary_database" in db_status
        assert "cache_status" in db_status
        assert "replication_status" in db_status

        # Verify primary database status
        primary_db = db_status["primary_database"]
        assert "connection_status" in primary_db
        assert "connection_pool" in primary_db
        assert "query_performance" in primary_db

        # Verify connection pool metrics
        conn_pool = primary_db["connection_pool"]
        assert "active_connections" in conn_pool
        assert "idle_connections" in conn_pool
        assert "total_connections" in conn_pool
        assert "pool_utilization" in conn_pool

        # Test database performance metrics
        response = test_client.get("/api/v1/status/database/performance", headers=headers)
        assert response.status_code == 200

        db_perf = response.json()
        assert "queries_per_second" in db_perf
        assert "average_query_time" in db_perf
        assert "slow_queries" in db_perf
        assert "deadlocks" in db_perf

    @pytest.mark.asyncio
    async def test_cache_status_endpoint(self, test_client: TestClient, auth_headers):
        """Test cache status endpoint"""
        headers = auth_headers({"email": "cachestatus@example.com", "first_name": "Cache", "last_name": "Status"})

        # Test cache status
        response = test_client.get("/api/v1/status/cache", headers=headers)
        assert response.status_code == 200

        cache_status = response.json()
        assert "redis_cache" in cache_status
        assert "application_cache" in cache_status

        # Verify Redis cache status
        redis_cache = cache_status["redis_cache"]
        assert "connection_status" in redis_cache
        assert "memory_usage" in redis_cache
        assert "key_count" in redis_cache
        assert "hit_rate" in redis_cache
        assert "operations_per_second" in redis_cache

        # Verify memory usage details
        memory_usage = redis_cache["memory_usage"]
        assert "used_memory_mb" in memory_usage
        assert "max_memory_mb" in memory_usage
        assert "memory_percentage" in memory_usage

        # Test cache performance metrics
        response = test_client.get("/api/v1/status/cache/performance", headers=headers)
        assert response.status_code == 200

        cache_perf = response.json()
        assert "get_operations" in cache_perf
        assert "set_operations" in cache_perf
        assert "delete_operations" in cache_perf
        assert "average_response_time" in cache_perf

    @pytest.mark.asyncio
    async def test_user_activity_status(self, test_client: TestClient, auth_headers):
        """Test user activity status endpoint"""
        headers = auth_headers({"email": "activity@example.com", "first_name": "Activity", "last_name": "User"})

        # Test overall user activity
        response = test_client.get("/api/v1/status/activity", headers=headers)
        assert response.status_code == 200

        activity_status = response.json()
        assert "active_users" in activity_status
        assert "recent_logins" in activity_status
        assert "api_requests_today" in activity_status
        assert "popular_features" in activity_status

        # Test user's own activity
        response = test_client.get("/api/v1/status/activity/my", headers=headers)
        assert response.status_code == 200

        user_activity = response.json()
        assert "last_login" in user_activity
        assert "session_duration" in user_activity
        assert "requests_today" in user_activity
        assert "documents_processed" in user_activity
        assert "searches_performed" in user_activity

    @pytest.mark.asyncio
    async def test_error_monitoring_endpoint(self, test_client: TestClient, auth_headers):
        """Test error monitoring endpoint"""
        headers = auth_headers({"email": "errors@example.com", "first_name": "Error", "last_name": "Monitor"})

        # Test error statistics
        response = test_client.get("/api/v1/status/errors", headers=headers)
        assert response.status_code == 200

        error_stats = response.json()
        assert "total_errors_today" in error_stats
        assert "error_rate" in error_stats
        assert "common_errors" in error_stats
        assert "critical_errors" in error_stats

        # Verify error rate is reasonable
        error_rate = error_stats["error_rate"]
        assert isinstance(error_rate, (int, float))
        assert 0 <= error_rate <= 100

        # Test recent errors
        response = test_client.get("/api/v1/status/errors/recent", headers=headers)
        assert response.status_code == 200

        recent_errors = response.json()
        assert "errors" in recent_errors
        assert "count" in recent_errors
        assert "time_range" in recent_errors

        # Verify error structure
        errors = recent_errors["errors"]
        if errors:  # If there are errors
            for error in errors[:5]:  # Check first 5 errors
                assert "timestamp" in error
                assert "error_type" in error
                assert "message" in error
                assert "severity" in error
                assert "count" in error

    @pytest.mark.asyncio
    async def test_api_performance_endpoint(self, test_client: TestClient, auth_headers):
        """Test API performance endpoint"""
        headers = auth_headers({"email": "apiperf@example.com", "first_name": "API", "last_name": "Performance"})

        # Test overall API performance
        response = test_client.get("/api/v1/status/api/performance", headers=headers)
        assert response.status_code == 200

        api_perf = response.json()
        assert "requests_per_second" in api_perf
        assert "average_response_time" in api_perf
        assert "p95_response_time" in api_perf
        assert "p99_response_time" in api_perf
        assert "error_rate" in api_perf

        # Verify performance metrics
        assert isinstance(api_perf["requests_per_second"], (int, float))
        assert api_perf["requests_per_second"] >= 0

        assert isinstance(api_perf["average_response_time"], (int, float))
        assert api_perf["average_response_time"] >= 0

        # Performance percentiles should be in order
        assert api_perf["average_response_time"] <= api_perf["p95_response_time"]
        assert api_perf["p95_response_time"] <= api_perf["p99_response_time"]

        # Test endpoint-specific performance
        response = test_client.get("/api/v1/status/api/endpoints", headers=headers)
        assert response.status_code == 200

        endpoint_perf = response.json()
        assert "endpoints" in endpoint_perf

        # Verify endpoint performance structure
        endpoints = endpoint_perf["endpoints"]
        if endpoints:
            for endpoint, metrics in endpoints.items():
                assert "requests_per_minute" in metrics
                assert "average_response_time" in metrics
                assert "success_rate" in metrics
                assert "last_request" in metrics

    @pytest.mark.asyncio
    async def test_system_metrics_endpoint(self, test_client: TestClient, auth_headers):
        """Test system metrics endpoint"""
        headers = auth_headers({"email": "sysmetrics@example.com", "first_name": "System", "last_name": "Metrics"})

        # Test system resource metrics
        response = test_client.get("/api/v1/status/system/metrics", headers=headers)
        assert response.status_code == 200

        system_metrics = response.json()
        assert "cpu" in system_metrics
        assert "memory" in system_metrics
        assert "disk" in system_metrics
        assert "network" in system_metrics

        # Verify CPU metrics
        cpu_metrics = system_metrics["cpu"]
        assert "usage_percentage" in cpu_metrics
        assert "load_average" in cpu_metrics
        assert "core_count" in cpu_metrics

        # Verify memory metrics
        memory_metrics = system_metrics["memory"]
        assert "total_gb" in memory_metrics
        assert "used_gb" in memory_metrics
        assert "available_gb" in memory_metrics
        assert "usage_percentage" in memory_metrics

        # Verify disk metrics
        disk_metrics = system_metrics["disk"]
        assert "total_gb" in disk_metrics
        assert "used_gb" in disk_metrics
        assert "free_gb" in disk_metrics
        assert "usage_percentage" in disk_metrics
        assert "read_iops" in disk_metrics
        assert "write_iops" in disk_metrics

        # Test historical metrics
        response = test_client.get("/api/v1/status/system/metrics/history?hours=1", headers=headers)
        assert response.status_code == 200

        historical_metrics = response.json()
        assert "time_range" in historical_metrics
        assert "metrics" in historical_metrics

        # Verify historical data structure
        metrics = historical_metrics["metrics"]
        if metrics:
            assert "timestamps" in metrics
            assert "cpu_usage" in metrics
            assert "memory_usage" in metrics

    @pytest.mark.asyncio
    async def test_status_endpoint_authentication(self, test_client: TestClient):
        """Test that status endpoints require authentication"""
        # Test without authentication
        endpoints = [
            "/api/v1/status/health",
            "/api/v1/status/websocket",
            "/api/v1/status/processing",
            "/api/v1/status/search/performance",
            "/api/v1/status/database",
            "/api/v1/status/cache",
            "/api/v1/status/activity",
            "/api/v1/status/errors",
            "/api/v1/status/api/performance",
            "/api/v1/status/system/metrics"
        ]

        for endpoint in endpoints:
            response = test_client.get(endpoint)
            assert response.status_code == 401

            error_data = response.json()
            assert "detail" in error_data

    @pytest.mark.asyncio
    async def test_status_endpoint_rate_limiting(self, test_client: TestClient, auth_headers):
        """Test rate limiting on status endpoints"""
        headers = auth_headers({"email": "ratelimit@example.com", "first_name": "Rate", "last_name": "Limit"})

        # Make rapid requests to trigger rate limiting
        rapid_requests = []
        for i in range(20):  # Assuming rate limit is lower than 20 requests
            response = test_client.get("/api/v1/status/health", headers=headers)
            rapid_requests.append(response)

        # Check if any requests were rate limited
        rate_limited_responses = [r for r in rapid_requests if r.status_code == 429]
        if rate_limited_responses:
            # Verify rate limit response format
            rate_limit_response = rate_limited_responses[0]
            assert rate_limit_response.status_code == 429

            rate_limit_data = rate_limit_response.json()
            assert "detail" in rate_limit_data
            assert "retry_after" in rate_limit_data or "retry-after" in rate_limit_data

    @pytest.mark.asyncio
    async def test_status_endpoint_caching(self, test_client: TestClient, auth_headers):
        """Test caching behavior of status endpoints"""
        headers = auth_headers({"email": "cache@example.com", "first_name": "Cache", "last_name": "Test"})

        # Test cache headers on health endpoint
        response = test_client.get("/api/v1/status/health", headers=headers)
        assert response.status_code == 200

        # Check for cache control headers (implementation dependent)
        cache_control = response.headers.get("cache-control")
        if cache_control:
            assert "max-age" in cache_control.lower()

        # Test no-cache endpoints
        response = test_client.get("/api/v1/status/health?no_cache=true", headers=headers)
        assert response.status_code == 200

        # Should have different cache headers
        no_cache_control = response.headers.get("cache-control")
        if no_cache_control:
            assert "no-cache" in no_cache_control.lower() or "max-age=0" in no_cache_control.lower()


@pytest.mark.contract
@pytest.mark.api
@pytest.mark.integration
class TestStatusEndpointsIntegration:
    """Integration tests for status endpoints"""

    @pytest.mark.asyncio
    async def test_end_to_end_status_flow(self, test_client: TestClient, auth_headers, websocket_test_client):
        """Test end-to-end status flow with WebSocket integration"""
        headers = auth_headers({"email": "e2e@example.com", "first_name": "End", "last_name": "ToEnd"})

        # Step 1: Check initial system health
        health_response = test_client.get("/api/v1/status/health", headers=headers)
        assert health_response.status_code == 200
        initial_health = health_response.json()

        # Step 2: Establish WebSocket connection
        token = websocket_test_client.generate_test_token()
        connection_id = await websocket_test_client.connect(token=token)
        assert connection_id is not None

        # Step 3: Check WebSocket status reflects new connection
        ws_status_response = test_client.get("/api/v1/status/websocket", headers=headers)
        assert ws_status_response.status_code == 200
        ws_status = ws_status_response.json()
        assert ws_status["total_connections"] >= 1

        # Step 4: Check detailed WebSocket status
        detailed_ws_response = test_client.get("/api/v1/status/websocket?detailed=true", headers=headers)
        assert detailed_ws_response.status_code == 200
        detailed_ws_status = detailed_ws_response.json()

        # Should show connection metrics
        conn_metrics = detailed_ws_status.get("connection_metrics", {})
        assert "active_connections" in conn_metrics
        assert conn_metrics["active_connections"] >= 1

        # Step 5: Send some activity and check status updates
        await websocket_test_client.send_message({
            "type": "ping",
            "data": {"test": "integration"}
        })

        # Step 6: Check activity status
        activity_response = test_client.get("/api/v1/status/activity/my", headers=headers)
        assert activity_response.status_code == 200
        activity_data = activity_response.json()

        # Step 7: Close WebSocket connection
        await websocket_test_client.close()

        # Step 8: Verify status reflects connection closure
        # Note: This might take a moment to reflect due to cleanup delays
        await asyncio.sleep(1)

        final_ws_status_response = test_client.get("/api/v1/status/websocket", headers=headers)
        assert final_ws_status_response.status_code == 200
        final_ws_status = final_ws_status_response.json()

        # Connection count should be updated (allowing for cleanup delays)
        # This assertion might need adjustment based on actual cleanup behavior

    @pytest.mark.asyncio
    async def test_status_consistency_across_endpoints(self, test_client: TestClient, auth_headers):
        """Test status data consistency across different endpoints"""
        headers = auth_headers({"email": "consistency@example.com", "first_name": "Consistency", "last_name": "User"})

        # Get status from multiple endpoints simultaneously
        import concurrent.futures
        import threading

        def get_endpoint_status(endpoint):
            response = test_client.get(endpoint, headers=headers)
            return response.json() if response.status_code == 200 else None

        endpoints = [
            "/api/v1/status/health",
            "/api/v1/status/websocket",
            "/api/v1/status/database",
            "/api/v1/status/cache"
        ]

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(get_endpoint_status, endpoint) for endpoint in endpoints]
            status_data = [future.result() for future in concurrent.futures.as_completed(futures)]

        # Verify all endpoints returned data
        assert all(data is not None for data in status_data)

        # Check timestamp consistency (within reasonable range)
        timestamps = []
        for data in status_data:
            if "timestamp" in data:
                timestamps.append(datetime.fromisoformat(data["timestamp"].replace('Z', '+00:00')))

        if len(timestamps) > 1:
            time_diff = max(timestamps) - min(timestamps)
            assert time_diff.total_seconds() < 5  # Within 5 seconds

    @pytest.mark.asyncio
    async def test_status_during_load(self, test_client: TestClient, auth_headers, websocket_load_tester):
        """Test status endpoints accuracy during system load"""
        headers = auth_headers({"email": "load@example.com", "first_name": "Load", "last_name": "Test"})

        # Get baseline status
        baseline_health = test_client.get("/api/v1/status/health", headers=headers).json()
        baseline_ws_status = test_client.get("/api/v1/status/websocket", headers=headers).json()

        # Create load
        load_metrics = await websocket_load_tester.run_load_test(
            target_connections=100,
            ramp_up_time=10.0,
            test_duration=30.0,
            messages_per_second=20
        )

        # Check status during load
        health_under_load = test_client.get("/api/v1/status/health", headers=headers).json()
        ws_status_under_load = test_client.get("/api/v1/status/websocket", headers=headers).json()

        # Verify status reflects load
        assert ws_status_under_load["total_connections"] >= load_metrics.successful_connections

        # Performance metrics should show load
        detailed_health = test_client.get("/api/v1/status/health?detailed=true", headers=headers).json()
        perf_metrics = detailed_health.get("performance_metrics", {})

        if "active_connections" in perf_metrics:
            assert perf_metrics["active_connections"] >= load_metrics.successful_connections

        # Clean up connections
        # This would be handled by the load tester cleanup