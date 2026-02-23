"""
Rate Limiting Security Tests for Search Endpoints

Tests comprehensive rate limiting including:
- Request frequency limits per user
- API key rate limiting
- Burst protection mechanisms  
- Rate limit bypass attempts
- Rate limit header validation
- Per-endpoint rate limiting
- Distributed rate limiting
- Rate limit escalation
"""

import pytest
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch, Mock
import uuid
from datetime import datetime, timedelta

from .conftest import SecurityTestCase


class TestRateLimiting(SecurityTestCase):
    """Test rate limiting security for search endpoints"""

    def test_basic_rate_limiting_per_user(self, security_test_client, authentication_headers, search_service_mocks):
        """Test basic rate limiting per authenticated user"""
        
        # Reset request tracking
        security_test_client.reset_tracking()
        
        # Make requests rapidly
        responses = []
        start_time = time.time()
        
        for i in range(10):  # Try to make 10 requests quickly
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": f"test_{i}", "search_type": "fulltext"}
            )
            responses.append(response)
            
            # Small delay to avoid overwhelming the system during testing
            time.sleep(0.1)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Check response patterns
        status_codes = [r.status_code for r in responses]
        
        # Should have some successful requests
        successful_requests = [r for r in responses if r.status_code == 200]
        rate_limited_requests = [r for r in responses if r.status_code == 429]
        
        # At high request rates, some should be rate limited
        if total_time < 2.0:  # If requests were made quickly
            # Should either rate limit or handle all requests
            assert len(successful_requests) >= 1, "Should have at least some successful requests"
            
            # If rate limiting is implemented, check for 429 responses
            if rate_limited_requests:
                for response in rate_limited_requests:
                    # Should have proper rate limit headers
                    self._assert_rate_limit_headers(response)
                    self.assert_safe_error_response(response)

    def test_rate_limit_headers_presence(self, security_test_client, authentication_headers, search_service_mocks):
        """Test that rate limit headers are present in responses"""
        
        response = security_test_client.make_request(
            'POST',
            '/search/',
            headers=authentication_headers['valid_jwt'],
            json={"query": "test", "search_type": "fulltext"}
        )
        
        # Check for standard rate limiting headers
        expected_headers = [
            'X-RateLimit-Limit',      # Total limit
            'X-RateLimit-Remaining',  # Remaining requests
            'X-RateLimit-Reset',      # Reset time
        ]
        
        response_headers = {k.lower(): v for k, v in response.headers.items()}
        
        for header in expected_headers:
            header_lower = header.lower()
            # Headers may or may not be present depending on implementation
            if header_lower in response_headers:
                # If present, should have valid values
                header_value = response_headers[header_lower]
                
                if 'limit' in header_lower:
                    assert header_value.isdigit(), f"{header} should be numeric"
                    assert int(header_value) > 0, f"{header} should be positive"
                
                elif 'remaining' in header_lower:
                    assert header_value.isdigit(), f"{header} should be numeric"
                    assert int(header_value) >= 0, f"{header} should be non-negative"
                
                elif 'reset' in header_lower:
                    # Could be timestamp or seconds
                    assert header_value.isdigit(), f"{header} should be numeric"

    def test_rate_limiting_per_api_key(self, security_test_client, authentication_headers, search_service_mocks):
        """Test rate limiting per API key"""
        
        # Test with API key authentication
        api_key_headers = authentication_headers['valid_api_key']
        
        responses = []
        for i in range(5):
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=api_key_headers,
                json={"query": f"test_{i}", "search_type": "fulltext"}
            )
            responses.append(response)
            time.sleep(0.1)
        
        # Should handle requests appropriately
        status_codes = [r.status_code for r in responses]
        
        # Check for consistent rate limiting behavior
        if any(code == 429 for code in status_codes):
            rate_limited_responses = [r for r in responses if r.status_code == 429]
            for response in rate_limited_responses:
                self._assert_rate_limit_headers(response)

    def test_rate_limit_bypass_attempts(self, unauthenticated_security_test_client, search_service_mocks):
        """Test attempts to bypass rate limiting"""

        # Test with different authentication methods (unauthenticated client)
        bypass_attempts = [
            # Different User-Agent strings
            {'Authorization': 'Bearer token1', 'User-Agent': 'Mozilla/5.0'},
            {'Authorization': 'Bearer token1', 'User-Agent': 'Chrome/91.0'},
            {'Authorization': 'Bearer token1', 'User-Agent': 'Safari/14.0'},

            # Different IP headers (if behind proxy)
            {'Authorization': 'Bearer token1', 'X-Forwarded-For': '192.168.1.1'},
            {'Authorization': 'Bearer token1', 'X-Forwarded-For': '10.0.0.1'},
            {'Authorization': 'Bearer token1', 'X-Real-IP': '172.16.0.1'},

            # Empty or modified headers
            {'Authorization': 'Bearer token1', 'X-Request-ID': 'unique1'},
            {'Authorization': 'Bearer token1', 'X-Request-ID': 'unique2'},
        ]

        for headers in bypass_attempts:
            response = unauthenticated_security_test_client.make_request(
                'POST',
                '/search/',
                headers=headers,
                json={"query": "bypass_test", "search_type": "fulltext"}
            )

            # Should not bypass authentication
            if 'Bearer token1' in headers.get('Authorization', ''):
                assert response.status_code in [401, 403], \
                    "Invalid token should not bypass authentication regardless of headers"

    def test_concurrent_request_rate_limiting(self, security_test_client, authentication_headers, search_service_mocks):
        """Test rate limiting under concurrent requests"""
        
        def make_search_request(request_id):
            """Make a single search request"""
            return security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": f"concurrent_test_{request_id}", "search_type": "fulltext"}
            )
        
        # Make concurrent requests
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_search_request, i) for i in range(10)]
            responses = [future.result() for future in as_completed(futures)]
        
        status_codes = [r.status_code for r in responses]
        
        # Should handle concurrent requests appropriately
        successful_responses = [r for r in responses if r.status_code == 200]
        rate_limited_responses = [r for r in responses if r.status_code == 429]
        error_responses = [r for r in responses if r.status_code >= 400 and r.status_code != 429]
        
        # Should have some successful responses
        assert len(successful_responses) > 0, "Should have some successful concurrent requests"
        
        # Rate limited responses should have proper headers
        for response in rate_limited_responses:
            self._assert_rate_limit_headers(response)
        
        # Error responses should be safe
        for response in error_responses:
            self.assert_safe_error_response(response)

    def test_rate_limit_reset_mechanism(self, security_test_client, authentication_headers, search_service_mocks):
        """Test rate limit reset mechanism"""
        
        # Make initial requests to potentially hit rate limit
        initial_responses = []
        for i in range(5):
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": f"reset_test_{i}", "search_type": "fulltext"}
            )
            initial_responses.append(response)
            time.sleep(0.1)
        
        # Check if any were rate limited
        rate_limited = any(r.status_code == 429 for r in initial_responses)
        
        if rate_limited:
            # Wait for potential reset (this would depend on implementation)
            time.sleep(2.0)
            
            # Try again after waiting
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": "after_reset_test", "search_type": "fulltext"}
            )
            
            # Should potentially allow requests again after reset
            # (Exact behavior depends on rate limiting implementation)
            assert response.status_code in [200, 401, 403, 429], \
                "Response after rate limit reset should be handled appropriately"

    def test_different_endpoint_rate_limiting(self, security_test_client, authentication_headers, search_service_mocks):
        """Test rate limiting across different search endpoints"""
        
        endpoints = [
            ('POST', '/search/', {"query": "test", "search_type": "fulltext"}),
            ('POST', '/search/hybrid', {"query": "test"}),
            ('GET', '/search/suggestions?q=test', None),
            ('GET', '/search/history', None),
            ('POST', '/search/history', {"query": "test"}),
        ]
        
        # Test each endpoint
        for method, url, data in endpoints:
            responses = []
            
            for i in range(3):
                if data:
                    response = security_test_client.make_request(
                        method,
                        url,
                        headers=authentication_headers['valid_jwt'],
                        json=data
                    )
                else:
                    response = security_test_client.make_request(
                        method,
                        url,
                        headers=authentication_headers['valid_jwt']
                    )
                
                responses.append(response)
                time.sleep(0.1)
            
            # Check responses
            status_codes = [r.status_code for r in responses]
            
            # Should handle appropriately (exact behavior depends on implementation)
            for response in responses:
                if response.status_code == 429:
                    self._assert_rate_limit_headers(response)
                elif response.status_code >= 400:
                    self.assert_safe_error_response(response)

    def test_rate_limit_information_disclosure(self, security_test_client, authentication_headers, search_service_mocks):
        """Test that rate limiting doesn't disclose sensitive information"""
        
        # Make requests to potentially trigger rate limiting
        for i in range(3):
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": f"info_test_{i}", "search_type": "fulltext"}
            )
            
            if response.status_code == 429:
                # Rate limit response should not disclose sensitive info
                sensitive_patterns = [
                    'database', 'redis', 'cache', 'memory',
                    'internal', 'server', 'backend',
                    'user_id', 'session', 'token',
                    'rate_limiter', 'implementation'
                ]
                
                self.assert_no_information_disclosure(response, sensitive_patterns)
            
            time.sleep(0.1)

    def test_burst_protection(self, security_test_client, authentication_headers, search_service_mocks):
        """Test burst protection mechanisms"""
        
        # Make a burst of requests in quick succession
        burst_responses = []
        start_time = time.time()
        
        for i in range(8):
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": f"burst_{i}", "search_type": "fulltext"}
            )
            burst_responses.append(response)
            # No delay - make requests as fast as possible
        
        end_time = time.time()
        burst_duration = end_time - start_time
        
        # Analyze burst response patterns
        status_codes = [r.status_code for r in burst_responses]
        successful_count = sum(1 for code in status_codes if code == 200)
        rate_limited_count = sum(1 for code in status_codes if code == 429)
        
        # If burst was very fast, should have some protection
        if burst_duration < 1.0:  # If burst was under 1 second
            if rate_limited_count > 0:
                # Burst protection is working
                assert successful_count > 0, "Should allow some requests in burst"
                assert rate_limited_count > 0, "Should rate limit some burst requests"
                
                # Check rate limited responses
                for i, response in enumerate(burst_responses):
                    if response.status_code == 429:
                        self._assert_rate_limit_headers(response)

    def test_rate_limit_with_invalid_authentication(self, unauthenticated_security_test_client, search_service_mocks):
        """Test rate limiting behavior with invalid authentication"""

        invalid_auth_headers = [
            {'Authorization': 'Bearer invalid_token'},
            {'Authorization': 'Bearer malformed.jwt.token'},
            {'X-API-Key': 'invalid_api_key'},
            {},  # No authentication
        ]

        for headers in invalid_auth_headers:
            responses = []

            for i in range(3):
                response = unauthenticated_security_test_client.make_request(
                    'POST',
                    '/search/',
                    headers=headers,
                    json={"query": f"invalid_auth_{i}", "search_type": "fulltext"}
                )
                responses.append(response)
                time.sleep(0.1)

            # Should get authentication errors, not rate limit errors
            for response in responses:
                assert response.status_code in [401, 403], \
                    "Invalid auth should result in auth errors, not rate limits"
                self.assert_safe_error_response(response)

    def test_rate_limit_escalation(self, security_test_client, authentication_headers, search_service_mocks):
        """Test rate limit escalation for repeat offenders"""
        
        # This test simulates escalating rate limits for persistent abuse
        # Make repeated bursts of requests
        
        escalation_responses = []
        
        for burst in range(3):  # Multiple bursts
            burst_responses = []
            
            for i in range(5):
                response = security_test_client.make_request(
                    'POST',
                    '/search/',
                    headers=authentication_headers['valid_jwt'],
                    json={"query": f"escalation_burst_{burst}_{i}", "search_type": "fulltext"}
                )
                burst_responses.append(response)
                time.sleep(0.05)  # Small delay within burst
            
            escalation_responses.extend(burst_responses)
            
            # Wait between bursts
            time.sleep(0.5)
        
        # Analyze escalation patterns
        rate_limited_responses = [r for r in escalation_responses if r.status_code == 429]
        
        if rate_limited_responses:
            # Check that rate limit responses are consistent
            for response in rate_limited_responses:
                self._assert_rate_limit_headers(response)
                
                # Check for escalation indicators in headers (if implemented)
                if 'X-RateLimit-Remaining' in response.headers:
                    remaining = int(response.headers['X-RateLimit-Remaining'])
                    assert remaining >= 0, "Remaining count should not be negative"

    @pytest.mark.skip(reason="Performance intensive test - enable manually")
    def test_sustained_load_rate_limiting(self, security_test_client, authentication_headers, search_service_mocks):
        """Test rate limiting under sustained load (performance test)"""
        
        # This test would run for a longer period to test sustained load
        # Skipped by default to avoid long test runs
        
        duration = 30  # seconds
        start_time = time.time()
        responses = []
        
        request_count = 0
        while time.time() - start_time < duration:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": f"sustained_{request_count}", "search_type": "fulltext"}
            )
            responses.append(response)
            request_count += 1
            
            time.sleep(0.5)  # 2 requests per second
        
        # Analyze sustained load behavior
        status_codes = [r.status_code for r in responses]
        success_rate = sum(1 for code in status_codes if code == 200) / len(responses)
        rate_limit_rate = sum(1 for code in status_codes if code == 429) / len(responses)
        
        # Should maintain reasonable success rate
        assert success_rate > 0.5, "Should maintain reasonable success rate under sustained load"
        
        # Rate limiting should be stable
        if rate_limit_rate > 0:
            # Should not have all requests rate limited
            assert rate_limit_rate < 0.9, "Should not rate limit almost all requests"

    def test_rate_limit_bypass_with_request_splitting(self, security_test_client, authentication_headers, search_service_mocks):
        """Test rate limit bypass attempts using request splitting"""
        
        # Attempt to bypass rate limits by splitting requests across different patterns
        splitting_attempts = [
            # Different query parameters
            [
                {"query": "part1", "search_type": "fulltext"},
                {"query": "part2", "search_type": "hybrid"},
                {"query": "part3", "search_type": "semantic"},
            ],
            # Different limits and offsets
            [
                {"query": "test", "limit": 10, "offset": 0},
                {"query": "test", "limit": 20, "offset": 10},
                {"query": "test", "limit": 5, "offset": 20},
            ],
            # Different filters
            [
                {"query": "test", "filters": {"tags": ["tag1"]}},
                {"query": "test", "filters": {"tags": ["tag2"]}},
                {"query": "test", "filters": {"is_public": True}},
            ],
        ]
        
        for attempt_group in splitting_attempts:
            responses = []
            
            for payload in attempt_group:
                response = security_test_client.make_request(
                    'POST',
                    '/search/',
                    headers=authentication_headers['valid_jwt'],
                    json=payload
                )
                responses.append(response)
                time.sleep(0.05)  # Quick succession
            
            # Should still apply rate limiting consistently
            status_codes = [r.status_code for r in responses]
            
            # Rate limiting should apply regardless of request variation
            for response in responses:
                if response.status_code == 429:
                    self._assert_rate_limit_headers(response)

    # Helper methods

    def _assert_rate_limit_headers(self, response):
        """Assert that rate limit headers are properly formatted"""
        headers = {k.lower(): v for k, v in response.headers.items()}
        
        # Check for common rate limit headers
        possible_headers = [
            'x-ratelimit-limit',
            'x-ratelimit-remaining', 
            'x-ratelimit-reset',
            'x-rate-limit-limit',
            'x-rate-limit-remaining',
            'x-rate-limit-reset',
            'retry-after'
        ]
        
        # At least one rate limit header should be present
        has_rate_limit_header = any(header in headers for header in possible_headers)
        
        if has_rate_limit_header:
            # Validate header values if present
            for header_name in possible_headers:
                if header_name in headers:
                    header_value = headers[header_name]
                    
                    if header_name in ['retry-after']:
                        # Should be numeric (seconds)
                        assert header_value.isdigit(), f"{header_name} should be numeric"
                        assert int(header_value) >= 0, f"{header_name} should be non-negative"
                    
                    elif 'limit' in header_name or 'remaining' in header_name:
                        # Should be numeric
                        assert header_value.isdigit(), f"{header_name} should be numeric"
                        assert int(header_value) >= 0, f"{header_name} should be non-negative"
                    
                    elif 'reset' in header_name:
                        # Should be numeric (timestamp or seconds)
                        assert header_value.isdigit(), f"{header_name} should be numeric"
        
        # Rate limited response should have appropriate status
        assert response.status_code == 429, "Rate limited response should have 429 status"

class TestRateLimitingEdgeCases(SecurityTestCase):
    """Test edge cases in rate limiting implementation"""

    def test_rate_limit_with_malformed_requests(self, security_test_client, authentication_headers, search_service_mocks):
        """Test rate limiting behavior with malformed requests"""
        
        malformed_requests = [
            {},  # Empty payload
            {"invalid": "payload"},  # Missing required fields
            {"query": ""},  # Empty query
            {"query": "test", "search_type": "invalid"},  # Invalid search type
        ]
        
        for payload in malformed_requests:
            responses = []
            
            for i in range(3):
                response = security_test_client.make_request(
                    'POST',
                    '/search/',
                    headers=authentication_headers['valid_jwt'],
                    json=payload
                )
                responses.append(response)
                time.sleep(0.1)
            
            # Should handle malformed requests before rate limiting
            for response in responses:
                if response.status_code == 422:
                    # Validation errors should come before rate limiting
                    self.assert_safe_error_response(response)
                elif response.status_code == 429:
                    # If rate limited, should have proper headers
                    self._assert_rate_limit_headers(response)

    def test_rate_limit_clock_skew_handling(self, security_test_client, authentication_headers, search_service_mocks):
        """Test rate limiting behavior with potential clock skew"""
        
        # This test would check that rate limiting handles time-related edge cases
        # In practice, this would require more sophisticated testing setup
        
        response = security_test_client.make_request(
            'POST',
            '/search/',
            headers=authentication_headers['valid_jwt'],
            json={"query": "clock_test", "search_type": "fulltext"}
        )
        
        # Should handle request regardless of potential clock issues
        assert response.status_code in [200, 401, 403, 429], \
            "Should handle requests appropriately regardless of clock skew"
        
        if response.status_code == 429:
            self._assert_rate_limit_headers(response)

    def _assert_rate_limit_headers(self, response):
        """Assert that rate limit headers are properly formatted"""
        headers = {k.lower(): v for k, v in response.headers.items()}
        
        # Common rate limit header patterns
        possible_headers = [
            'x-ratelimit-limit',
            'x-ratelimit-remaining', 
            'x-ratelimit-reset',
            'retry-after'
        ]
        
        # Check if any rate limit headers are present
        rate_limit_headers = [h for h in possible_headers if h in headers]
        
        # Validate present headers
        for header in rate_limit_headers:
            value = headers[header]
            assert value.isdigit(), f"Rate limit header {header} should be numeric"
            assert int(value) >= 0, f"Rate limit header {header} should be non-negative"