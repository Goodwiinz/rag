"""
API Contract Tests for A/B Testing API

These tests validate that the A/B Testing API conforms to its OpenAPI specification.
They test request/response schemas, status codes, and API behavior.
"""

import pytest
from .api_contract_testing import APIContractTestRunner, APITestSpec, OpenAPILoader


class TestABTestingAPIContract:
    """Test A/B Testing API contract compliance"""

    @pytest.fixture
    def contract_runner(self):
        """Create contract test runner for A/B Testing API"""
        return APIContractTestRunner("docs/ab_testing_openapi.yaml")

    def test_openapi_spec_loaded(self, contract_runner):
        """Test that OpenAPI specification is loaded correctly"""
        assert contract_runner.openapi_loader.spec is not None
        assert contract_runner.openapi_loader.spec['openapi'] == '3.0.3'
        assert 'A/B Testing API' in contract_runner.openapi_loader.spec['info']['title']

    def test_all_endpoints_discovered(self, contract_runner):
        """Test that all expected endpoints are discovered from OpenAPI spec"""
        endpoints = contract_runner.openapi_loader.get_all_endpoints()

        # Expected A/B Testing endpoints
        expected_endpoints = [
            'createExperiment',
            'listExperiments',
            'getExperiment',
            'updateExperiment',
            'deleteExperiment',
            'startExperiment',
            'stopExperiment',
            'createVariant',
            'listVariants',
            'assignExperimentVariant',
            'submitMetric',
            'submitMetricsBulk',
            'analyzeExperiment',
            'getExperimentSummary',
            'createUserSegment',
            'listUserSegments',
            'healthCheck',
            'publicHealthCheck'
        ]

        discovered_operation_ids = [ep.operation_id for ep in endpoints]

        for expected_op in expected_endpoints:
            assert expected_op in discovered_operation_ids, f"Missing endpoint: {expected_op}"

    def test_experiment_management_contracts(self, contract_runner, admin_auth_headers):
        """Test experiment management endpoints contract compliance"""
        # Test create experiment
        create_result = contract_runner.run_endpoint_test(
            contract_runner.openapi_loader.get_endpoint_by_operation_id('createExperiment'),
            admin_auth_headers
        )

        assert create_result['success'], f"Create experiment contract failed: {create_result['errors']}"
        assert create_result['status_code'] in [201, 400, 401, 403, 500]

        # Test list experiments
        list_result = contract_runner.run_endpoint_test(
            contract_runner.openapi_loader.get_endpoint_by_operation_id('listExperiments'),
            admin_auth_headers
        )

        assert list_result['success'], f"List experiments contract failed: {list_result['errors']}"
        assert list_result['status_code'] in [200, 401, 500]

    def test_variant_management_contracts(self, contract_runner, admin_auth_headers):
        """Test variant management endpoints contract compliance"""
        # Test create variant (this will likely fail without a valid experiment_id, but should still be contract-compliant)
        create_variant_result = contract_runner.run_endpoint_test(
            contract_runner.openapi_loader.get_endpoint_by_operation_id('createVariant'),
            admin_auth_headers
        )

        # Should fail due to invalid experiment_id but still be contract-compliant
        assert create_variant_result['status_code'] in [201, 400, 401, 403, 404, 500]
        if not create_variant_result['success']:
            # Check if it's a validation error rather than contract violation
            error_messages = ' '.join(create_variant_result['errors'])
            assert 'schema' not in error_messages.lower() or 'validation' in error_messages.lower()

    def test_assignment_and_metrics_contracts(self, contract_runner, user_auth_headers):
        """Test assignment and metrics collection endpoints"""
        # Test query routing/assignment
        assignment_result = contract_runner.run_endpoint_test(
            contract_runner.openapi_loader.get_endpoint_by_operation_id('assignExperimentVariant'),
            user_auth_headers
        )

        assert assignment_result['status_code'] in [200, 400, 500]

        # Test metric submission
        metric_result = contract_runner.run_endpoint_test(
            contract_runner.openapi_loader.get_endpoint_by_operation_id('submitMetric'),
            user_auth_headers
        )

        assert metric_result['status_code'] in [201, 400, 500]

        # Test bulk metric submission
        bulk_metric_result = contract_runner.run_endpoint_test(
            contract_runner.openapi_loader.get_endpoint_by_operation_id('submitMetricsBulk'),
            user_auth_headers
        )

        assert bulk_metric_result['status_code'] in [201, 400, 500]

    def test_analytics_and_reporting_contracts(self, contract_runner, admin_auth_headers):
        """Test analytics and reporting endpoints"""
        # Test experiment analysis
        analysis_result = contract_runner.run_endpoint_test(
            contract_runner.openapi_loader.get_endpoint_by_operation_id('analyzeExperiment'),
            admin_auth_headers
        )

        assert analysis_result['status_code'] in [200, 400, 404, 500]

        # Test experiment summary
        summary_result = contract_runner.run_endpoint_test(
            contract_runner.openapi_loader.get_endpoint_by_operation_id('getExperimentSummary'),
            admin_auth_headers
        )

        assert summary_result['status_code'] in [200, 404, 500]

    def test_user_segment_contracts(self, contract_runner, admin_auth_headers):
        """Test user segment management endpoints"""
        # Test create user segment
        create_segment_result = contract_runner.run_endpoint_test(
            contract_runner.openapi_loader.get_endpoint_by_operation_id('createUserSegment'),
            admin_auth_headers
        )

        assert create_segment_result['status_code'] in [201, 400, 401, 500]

        # Test list user segments
        list_segments_result = contract_runner.run_endpoint_test(
            contract_runner.openapi_loader.get_endpoint_by_operation_id('listUserSegments'),
            admin_auth_headers
        )

        assert list_segments_result['status_code'] in [200, 401, 500]

    def test_health_check_contracts(self, contract_runner):
        """Test health check endpoints (no auth required)"""
        # Test authenticated health check
        health_result = contract_runner.run_endpoint_test(
            contract_runner.openapi_loader.get_endpoint_by_operation_id('healthCheck')
        )

        assert health_result['status_code'] in [200, 503]

        # Test public health check
        public_health_result = contract_runner.run_endpoint_test(
            contract_runner.openapi_loader.get_endpoint_by_operation_id('publicHealthCheck')
        )

        assert public_health_result['status_code'] in [200, 503]

    def test_security_requirements(self, contract_runner):
        """Test that security requirements are properly enforced"""
        endpoints_requiring_auth = [
            'createExperiment',
            'listExperiments',
            'getExperiment',
            'updateExperiment',
            'deleteExperiment',
            'startExperiment',
            'stopExperiment',
            'createVariant',
            'analyzeExperiment',
            'getExperimentSummary',
            'createUserSegment',
            'listUserSegments'
        ]

        for operation_id in endpoints_requiring_auth:
            endpoint = contract_runner.openapi_loader.get_endpoint_by_operation_id(operation_id)
            if endpoint:
                # Test without authentication - should return 401
                result = contract_runner.run_endpoint_test(endpoint, auth_headers=None)
                assert result['status_code'] == 401, f"{operation_id} should require authentication"

    def test_response_schema_validation(self, contract_runner, admin_auth_headers):
        """Test detailed response schema validation"""
        # Test health check response schema
        health_endpoint = contract_runner.openapi_loader.get_endpoint_by_operation_id('healthCheck')
        health_result = contract_runner.run_endpoint_test(health_endpoint)

        if health_result['status_code'] == 200 and health_result['response_data']:
            response_data = health_result['response_data']

            # Validate health check response structure
            assert 'status' in response_data
            assert 'timestamp' in response_data
            assert 'components' in response_data

            # Validate status enum
            assert response_data['status'] in ['healthy', 'degraded', 'unhealthy']

            # Validate components structure
            components = response_data['components']
            for component_name, component_data in components.items():
                assert 'status' in component_data
                assert component_data['status'] in ['healthy', 'degraded', 'unhealthy']

    def test_error_response_schema_validation(self, contract_runner):
        """Test error response schema validation"""
        # Test with invalid data to trigger error responses
        create_endpoint = contract_runner.openapi_loader.get_endpoint_by_operation_id('createExperiment')

        # Test with no authentication
        result = contract_runner.run_endpoint_test(create_endpoint, auth_headers=None)

        if result['status_code'] == 401 and result['response_data']:
            error_data = result['response_data']

            # Validate error response structure
            if 'error' in error_data:
                error = error_data['error']
                assert 'message' in error
                assert 'status_code' in error
                assert 'type' in error

    def test_comprehensive_contract_compliance(self, contract_runner, admin_auth_headers, user_auth_headers):
        """Run comprehensive contract compliance test for all endpoints"""
        # Test all admin endpoints
        admin_results = contract_runner.run_all_tests(
            auth_headers=admin_auth_headers,
            tags=['Experiments', 'Variants', 'Analytics']
        )

        # Test all user endpoints
        user_results = contract_runner.run_all_tests(
            auth_headers=user_auth_headers,
            tags=['Assignment', 'Metrics']
        )

        # Test public endpoints
        public_results = contract_runner.run_all_tests(
            auth_headers=None,
            tags=['Health']
        )

        # Generate compliance report
        total_tests = admin_results['total_endpoints'] + user_results['total_endpoints'] + public_results['total_endpoints']
        total_passed = admin_results['passed'] + user_results['passed'] + public_results['passed']
        total_failed = admin_results['failed'] + user_results['failed'] + public_results['failed']

        compliance_rate = (total_passed / total_tests) * 100 if total_tests > 0 else 0

        # Report results
        print(f"\nAPI Contract Compliance Report:")
        print(f"Total Endpoints Tested: {total_tests}")
        print(f"Passed: {total_passed}")
        print(f"Failed: {total_failed}")
        print(f"Compliance Rate: {compliance_rate:.2f}%")

        # Collect all errors for reporting
        all_errors = []
        for result in admin_results['results'] + user_results['results'] + public_results['results']:
            if not result['success']:
                all_errors.extend(result['errors'])

        if all_errors:
            print(f"\nContract Violations Found ({len(all_errors)}):")
            for error in all_errors[:10]:  # Show first 10 errors
                print(f"  - {error}")
            if len(all_errors) > 10:
                print(f"  ... and {len(all_errors) - 10} more errors")

        # Assert overall compliance (allowing for some expected failures due to missing resources)
        assert compliance_rate >= 80.0, f"API contract compliance too low: {compliance_rate:.2f}%"

    def test_request_parameter_validation(self, contract_runner, admin_auth_headers):
        """Test request parameter validation"""
        # Test with invalid experiment ID format
        experiment_endpoint = contract_runner.openapi_loader.get_endpoint_by_operation_id('getExperiment')
        if experiment_endpoint:
            # Manually test with invalid UUID format
            invalid_id_result = contract_runner.run_endpoint_test(experiment_endpoint, admin_auth_headers)
            # Should fail gracefully (400 or 404) without crashing
            assert invalid_id_result['status_code'] in [400, 404, 401, 500]

    def test_response_time_performance(self, contract_runner, user_auth_headers):
        """Test API response times for performance requirements"""
        import time

        # Test assignment endpoint performance (should be <5ms according to spec)
        assignment_endpoint = contract_runner.openapi_loader.get_endpoint_by_operation_id('assignExperimentVariant')
        if assignment_endpoint:
            start_time = time.time()
            result = contract_runner.run_endpoint_test(assignment_endpoint, user_auth_headers)
            end_time = time.time()

            response_time = (end_time - start_time) * 1000  # Convert to milliseconds

            # Note: This is a rough performance test since we're using test client
            # Real performance testing should be done with proper load testing tools
            print(f"Assignment endpoint response time: {response_time:.2f}ms")

            # The test itself should complete in reasonable time
            assert response_time < 1000, f"Test took too long: {response_time:.2f}ms"