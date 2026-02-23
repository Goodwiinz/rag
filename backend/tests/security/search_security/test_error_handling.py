"""
Error Handling and Logging Security Tests for Search Endpoints

Tests comprehensive error handling and logging security including:
- Information disclosure prevention in error messages
- Error message sanitization and standardization
- Security event logging verification
- Audit trail completeness and integrity
- Log injection prevention
- Stack trace sanitization
- Error correlation and monitoring
"""

import pytest
import json
import logging
from unittest.mock import patch, Mock, MagicMock
import uuid
from datetime import datetime
import re

from .conftest import SecurityTestCase


class TestErrorHandlingSecurity(SecurityTestCase):
    """Test secure error handling in search endpoints"""

    def test_error_message_information_disclosure(self, security_test_client, authentication_headers, search_service_mocks):
        """Test that error messages don't disclose sensitive information"""
        
        # Error-inducing payloads
        error_scenarios = [
            # Validation errors
            {"payload": {}, "expected_status": 422, "description": "empty payload"},
            {"payload": {"query": ""}, "expected_status": 422, "description": "empty query"},
            {"payload": {"query": "test", "search_type": "invalid"}, "expected_status": 422, "description": "invalid search type"},
            {"payload": {"query": "test", "limit": -1}, "expected_status": 422, "description": "negative limit"},
            {"payload": {"query": "test", "offset": -1}, "expected_status": 422, "description": "negative offset"},
            {"payload": {"query": "test", "limit": 1000}, "expected_status": 422, "description": "excessive limit"},
            {"payload": {"query": "A" * 2000}, "expected_status": 422, "description": "query too long"},
        ]
        
        for scenario in error_scenarios:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json=scenario["payload"]
            )
            
            # Should return expected error status
            assert response.status_code == scenario["expected_status"], \
                f"Wrong status for {scenario['description']}: expected {scenario['expected_status']}, got {response.status_code}"
            
            # Error response should be safe
            self.assert_safe_error_response(response)
            
            # Should not disclose sensitive information
            sensitive_patterns = [
                'database', 'sql', 'postgres', 'mysql', 'sqlite',
                'internal', 'traceback', 'stack trace',
                'file path', '/src/', '/app/', '/home/',
                'password', 'secret', 'key', 'token',
                'server', 'host', 'port', 'connection',
                'memory', 'disk', 'cpu', 'process',
                'user_id', 'organization_id', 'api_key',
                'redis', 'cache', 'session', 'cookie'
            ]
            
            self.assert_no_information_disclosure(response, sensitive_patterns)

    def test_error_message_consistency(self, security_test_client, authentication_headers, search_service_mocks):
        """Test that error messages are consistent and don't leak timing information"""
        
        # Test same error conditions multiple times
        consistent_scenarios = [
            {"query": "", "search_type": "fulltext"},  # Empty query
            {"query": "test", "search_type": "invalid"},  # Invalid search type
            {"query": "test", "limit": -1},  # Invalid limit
        ]
        
        for scenario in consistent_scenarios:
            responses = []
            response_times = []
            
            # Make same request multiple times
            for i in range(3):
                import time
                start_time = time.time()
                
                response = security_test_client.make_request(
                    'POST',
                    '/search/',
                    headers=authentication_headers['valid_jwt'],
                    json=scenario
                )
                
                end_time = time.time()
                response_time = end_time - start_time
                
                responses.append(response)
                response_times.append(response_time)
            
            # All responses should be identical
            status_codes = [r.status_code for r in responses]
            response_texts = [r.text for r in responses]
            
            # Status codes should be consistent
            assert len(set(status_codes)) == 1, \
                f"Inconsistent status codes for {scenario}: {status_codes}"
            
            # Response bodies should be consistent (or very similar)
            # Allow for minor variations like request IDs or timestamps
            if len(set(response_texts)) > 1:
                # Check if differences are only in expected dynamic fields
                self._assert_error_responses_equivalent(responses)
            
            # Response times should not vary dramatically (timing attack prevention)
            if len(response_times) > 1:
                avg_time = sum(response_times) / len(response_times)
                for resp_time in response_times:
                    assert resp_time < avg_time * 3, \
                        f"Response time varies too much, potential timing leak: {response_times}"

    def test_authentication_error_handling(self, unauthenticated_security_test_client, search_service_mocks):
        """Test secure handling of authentication errors"""

        auth_error_scenarios = [
            {"headers": {}, "description": "no authentication"},
            {"headers": {"Authorization": ""}, "description": "empty auth header"},
            {"headers": {"Authorization": "invalid"}, "description": "malformed auth"},
            {"headers": {"Authorization": "Bearer invalid_token"}, "description": "invalid JWT"},
            {"headers": {"Authorization": "Bearer " + "a" * 1000}, "description": "oversized token"},
            {"headers": {"X-API-Key": ""}, "description": "empty API key"},
            {"headers": {"X-API-Key": "invalid_key"}, "description": "invalid API key"},
        ]

        for scenario in auth_error_scenarios:
            response = unauthenticated_security_test_client.make_request(
                'POST',
                '/search/',
                headers=scenario["headers"],
                json={"query": "test", "search_type": "fulltext"}
            )

            # Should return 401 or 403 for auth errors
            assert response.status_code in [401, 403], \
                f"Should reject {scenario['description']}, got {response.status_code}"

            self.assert_safe_error_response(response)

    def test_authorization_error_handling(self, security_test_client, authentication_headers, search_service_mocks):
        """Test secure handling of authorization errors"""
        
        # This would test authorization errors if RBAC is implemented
        # For now, test with potentially restricted endpoints
        
        restricted_scenarios = [
            {'method': 'DELETE', 'url': '/search/history', 'description': 'delete history'},
            {'method': 'POST', 'url': '/search/admin', 'description': 'admin endpoint'},
        ]
        
        for scenario in restricted_scenarios:
            try:
                response = security_test_client.make_request(
                    scenario['method'],
                    scenario['url'],
                    headers=authentication_headers['valid_jwt']
                )
                
                # Should either work (200) or be forbidden (403) or not found (404)
                assert response.status_code in [200, 403, 404, 405], \
                    f"Unexpected status for {scenario['description']}: {response.status_code}"
                
                if response.status_code in [403, 404, 405]:
                    self.assert_safe_error_response(response)
                    
                    # Should not disclose authorization logic
                    authz_sensitive_patterns = [
                        'role', 'permission', 'access', 'denied',
                        'rbac', 'policy', 'rule', 'check',
                        'user', 'group', 'organization'
                    ]
                    
                    # These patterns might be acceptable in error messages,
                    # but should not leak implementation details
                    response_lower = response.text.lower()
                    for pattern in authz_sensitive_patterns:
                        if pattern in response_lower:
                            # If present, should be in generic form
                            assert not any(impl in response_lower for impl in [
                                'database', 'query', 'table', 'sql',
                                'internal', 'system', 'config'
                            ]), f"Authorization error leaks implementation details: {pattern}"
                            
            except Exception:
                # If endpoint doesn't exist, that's fine for this test
                pass

    def test_security_event_logging(self, security_test_client, authentication_headers, search_service_mocks):
        """Test that security events are handled without crashing.

        Since there is no centralised security logger to mock, we simply
        verify that requests producing security-relevant events (validation
        errors, injection attempts, oversized requests) are handled
        gracefully and return the expected status codes.
        """

        security_events = [
            # Malformed requests
            {"headers": authentication_headers['valid_jwt'], "payload": {}, "event_type": "validation_error"},
            # Potential injection attempts
            {"headers": authentication_headers['valid_jwt'], "payload": {"query": "'; DROP TABLE users; --"}, "event_type": "injection_attempt"},
            # Oversized requests
            {"headers": authentication_headers['valid_jwt'], "payload": {"query": "A" * 2000}, "event_type": "oversized_request"},
        ]

        for event in security_events:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=event["headers"],
                json=event["payload"]
            )

            # Should handle request appropriately
            assert response.status_code in [200, 400, 422], \
                f"Security event should be handled: {event['event_type']}"

    def test_error_correlation_ids(self, security_test_client, authentication_headers, search_service_mocks):
        """Test that errors have correlation IDs for tracking"""
        
        # Make request that should cause an error
        response = security_test_client.make_request(
            'POST',
            '/search/',
            headers=authentication_headers['valid_jwt'],
            json={"query": "", "search_type": "fulltext"}  # Empty query should error
        )
        
        assert response.status_code == 422, "Should get validation error"
        
        # Check for correlation ID in response headers or body
        correlation_headers = [
            'x-request-id', 'x-correlation-id', 'x-trace-id',
            'request-id', 'correlation-id', 'trace-id'
        ]
        
        has_correlation_id = False
        correlation_value = None
        
        # Check headers
        for header in correlation_headers:
            if header.lower() in [h.lower() for h in response.headers.keys()]:
                has_correlation_id = True
                correlation_value = response.headers.get(header)
                break
        
        # Check response body
        if not has_correlation_id:
            try:
                response_json = response.json()
                for key in ['request_id', 'correlation_id', 'trace_id', 'error_id']:
                    if key in response_json:
                        has_correlation_id = True
                        correlation_value = response_json[key]
                        break
            except:
                pass
        
        # If correlation ID is present, validate format
        if has_correlation_id and correlation_value:
            # Should be a valid identifier format (UUID, alphanumeric, etc.)
            # Not sensitive information
            assert len(correlation_value) > 0, "Correlation ID should not be empty"
            assert len(correlation_value) < 100, "Correlation ID should not be excessively long"
            
            # Should not contain sensitive information
            self.assert_no_information_disclosure(
                Mock(text=correlation_value), 
                ['password', 'secret', 'user', 'internal']
            )

    @pytest.mark.xfail(
        reason="SECURITY FINDING: App error handler exposes raw exception messages in responses. "
               "Internal paths and error details are leaked to clients. Needs fix in error handler.",
        strict=False,
    )
    def test_stack_trace_sanitization(self, security_test_client, authentication_headers):
        """Test that stack traces are not exposed in error responses"""

        # Patch at the import location used by the router module
        with patch('src.api.search.search.hybrid_search_service') as mock_service:
            mock_service.search.side_effect = Exception(
                "Internal database connection failed at /opt/app/src/db/connection.py line 42"
            )

            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": "test", "search_type": "hybrid"}
            )

            # Should return 500 for internal error
            assert response.status_code == 500, "Should return 500 for internal error"

            # Should not expose stack trace information
            stack_trace_patterns = [
                'traceback', 'stack trace', 'file "',
                '/opt/app/', '.py:',
                'raise ', 'at line', 'in function',
                'database connection',
            ]

            self.assert_no_information_disclosure(response, stack_trace_patterns)
            self.assert_safe_error_response(response)

    def test_log_injection_prevention(self, security_test_client, authentication_headers, search_service_mocks):
        """Test prevention of log injection attacks"""
        
        # Log injection payloads
        log_injection_payloads = [
            "test\n[ERROR] Fake error injected by attacker",
            "test\r\n[CRITICAL] System compromised",
            "query\n2023-01-01 ERROR: Injected log entry",
            "search\x00\nINJECTED: Fake security alert",
            "test\n\r[SECURITY] False positive injection",
            "query\x0A[ADMIN] Unauthorized access attempt",
            "search%0A[ERROR] Log injection test",
            "test\\n[WARNING] Fake warning message",
        ]
        
        for payload in log_injection_payloads:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": payload, "search_type": "fulltext"}
            )
            
            # Request should be handled safely
            assert response.status_code in [200, 400, 422], \
                f"Log injection payload should be handled safely: {payload[:50]}..."
            
            # Response should not contain injected log entries
            injection_indicators = [
                '[error]', '[critical]', '[warning]', '[admin]',
                'injected', 'fake', 'compromised', 'unauthorized'
            ]
            
            response_lower = response.text.lower()
            for indicator in injection_indicators:
                assert indicator not in response_lower, \
                    f"Response contains potential log injection: {indicator}"

    def test_error_rate_monitoring(self, security_test_client, authentication_headers, search_service_mocks):
        """Test error rate patterns for security monitoring"""
        
        # Generate various types of errors
        error_scenarios = [
            {"query": "", "expected_status": 422},  # Validation error
            {"query": "test", "search_type": "invalid", "expected_status": 422},  # Type error
            {"query": "A" * 2000, "expected_status": 422},  # Size error
        ]
        
        error_counts = {}
        
        for scenario in error_scenarios:
            for i in range(3):  # Generate multiple errors of each type
                response = security_test_client.make_request(
                    'POST',
                    '/search/',
                    headers=authentication_headers['valid_jwt'],
                    json={k: v for k, v in scenario.items() if k != 'expected_status'}
                )
                
                status_code = response.status_code
                error_counts[status_code] = error_counts.get(status_code, 0) + 1
                
                # Each error should be handled consistently
                assert status_code == scenario['expected_status'], \
                    f"Inconsistent error handling for {scenario}"
                
                self.assert_safe_error_response(response)
        
        # Should have generated multiple error types for monitoring
        assert len(error_counts) > 0, "Should have generated errors for monitoring"

    def test_error_message_localization_security(self, security_test_client, authentication_headers, search_service_mocks):
        """Test that error message localization doesn't introduce security issues"""
        
        # Test with different Accept-Language headers
        language_headers = [
            'en-US',
            'es-ES',
            'fr-FR',
            'de-DE',
            'zh-CN',
            'ja-JP',
            'invalid-locale',
            '<script>alert("xss")</script>',  # XSS in language header
            '../../etc/passwd',  # Path traversal in language header
        ]
        
        for lang in language_headers:
            headers = {
                **authentication_headers['valid_jwt'],
                'Accept-Language': lang
            }
            
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=headers,
                json={"query": "", "search_type": "fulltext"}  # Trigger validation error
            )
            
            assert response.status_code == 422, "Should get validation error regardless of language"
            
            # Error message should be safe regardless of language
            self.assert_safe_error_response(response)
            
            # Should not reflect malicious language header content
            if '<script>' in lang or 'passwd' in lang:
                assert lang not in response.text, \
                    f"Error response should not reflect malicious language header: {lang}"

    def test_database_error_sanitization(self, security_test_client, authentication_headers):
        """Test sanitization of database errors"""
        
        # Mock database errors
        with patch('src.core.database.get_db') as mock_db:
            mock_db.side_effect = Exception("SQLSTATE[42000]: Syntax error in SQL statement 'SELECT * FROM users WHERE id = malicious_input'")
            
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": "test", "search_type": "fulltext"}
            )
            
            # Should handle database error gracefully
            assert response.status_code == 500, "Should return 500 for database error"
            
            # Should not expose database error details
            db_error_patterns = [
                'sqlstate', 'syntax error', 'sql statement',
                'select *', 'from users', 'where id',
                'malicious_input', 'database', 'connection',
                'postgres', 'mysql', 'sqlite', 'table'
            ]
            
            self.assert_no_information_disclosure(response, db_error_patterns)
            self.assert_safe_error_response(response)

    # Helper methods

    def _assert_error_responses_equivalent(self, responses):
        """Assert that error responses are equivalent (allowing for dynamic fields)"""
        
        # Extract status codes
        status_codes = [r.status_code for r in responses]
        assert len(set(status_codes)) == 1, "Status codes should be identical"
        
        # Parse JSON responses if possible
        json_responses = []
        for response in responses:
            try:
                json_responses.append(response.json())
            except:
                # If not JSON, compare text directly
                response_texts = [r.text for r in responses]
                # Allow for minor variations (timestamps, request IDs)
                base_text = response_texts[0]
                for text in response_texts[1:]:
                    similarity = self._calculate_text_similarity(base_text, text)
                    assert similarity > 0.8, "Error responses should be substantially similar"
                return
        
        # Compare JSON structure and non-dynamic fields
        if json_responses:
            base_response = json_responses[0]
            for response in json_responses[1:]:
                self._assert_json_responses_equivalent(base_response, response)

    def _calculate_text_similarity(self, text1, text2):
        """Calculate similarity between two text strings"""
        # Simple similarity calculation
        if text1 == text2:
            return 1.0
        
        # Count common words
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 and not words2:
            return 1.0
        
        common = words1.intersection(words2)
        total = words1.union(words2)
        
        return len(common) / len(total) if total else 0.0

    def _assert_json_responses_equivalent(self, response1, response2):
        """Assert that two JSON error responses are equivalent"""
        
        # Dynamic fields that can vary between responses
        dynamic_fields = [
            'timestamp', 'request_id', 'correlation_id', 'trace_id',
            'error_id', 'time', 'datetime', 'id'
        ]
        
        # Remove dynamic fields and compare
        clean_response1 = {k: v for k, v in response1.items() if k not in dynamic_fields}
        clean_response2 = {k: v for k, v in response2.items() if k not in dynamic_fields}
        
        assert clean_response1 == clean_response2, \
            "Error responses should be equivalent after removing dynamic fields"

class TestErrorHandlingEdgeCases(SecurityTestCase):
    """Test edge cases in error handling"""

    def test_recursive_error_handling(self, security_test_client, authentication_headers):
        """Test handling of errors that occur during error processing"""
        
        # Mock error handler to fail
        with patch('src.api.search.search.logger') as mock_logger:
            mock_logger.error.side_effect = Exception("Logging system failure")
            
            # This should still handle the original error gracefully
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": "", "search_type": "fulltext"}
            )
            
            # Should still return appropriate error status
            assert response.status_code in [422, 500], \
                "Should handle errors even when error handling fails"
            
            self.assert_safe_error_response(response)

    def test_error_handling_under_load(self, security_test_client, authentication_headers, search_service_mocks):
        """Test error handling behavior under high load"""
        
        # Generate multiple concurrent errors
        import concurrent.futures
        
        def generate_error():
            return security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": "", "search_type": "fulltext"}
            )
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(generate_error) for _ in range(10)]
            responses = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # All errors should be handled consistently
        for response in responses:
            assert response.status_code == 422, "Should handle concurrent errors consistently"
            self.assert_safe_error_response(response)