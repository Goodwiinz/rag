"""
Input Validation Security Tests for Search Endpoints

Tests comprehensive input validation including:
- Query parameter validation
- Payload size limits  
- Character encoding tests
- Parameter type validation
- Boundary value testing
- Malformed data handling
"""

import pytest
import json
from typing import Dict, Any, List
from unittest.mock import patch
import uuid

from .conftest import SecurityTestCase


class TestSearchInputValidation(SecurityTestCase):
    """Test input validation for all search endpoints"""

    def test_query_length_validation(self, security_test_client, authentication_headers, search_service_mocks):
        """Test query length limits are enforced"""
        
        # Test minimum length (should fail for empty or too short)
        invalid_queries = ["", " ", "a"]
        
        for query in invalid_queries:
            response = security_test_client.make_request(
                'POST', 
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": query, "search_type": "fulltext"}
            )
            assert response.status_code == 422, f"Should reject short query: '{query}'"
            self.assert_safe_error_response(response)
        
        # Test maximum length (should fail for overly long queries)
        long_query = "a" * 1001  # Exceeds max_length=1000
        response = security_test_client.make_request(
            'POST',
            '/search/',
            headers=authentication_headers['valid_jwt'], 
            json={"query": long_query, "search_type": "fulltext"}
        )
        assert response.status_code == 422, "Should reject overly long query"
        self.assert_safe_error_response(response)
        
        # Test valid length
        valid_query = "a" * 500  # Within limits
        response = security_test_client.make_request(
            'POST',
            '/search/',
            headers=authentication_headers['valid_jwt'],
            json={"query": valid_query, "search_type": "fulltext"}
        )
        assert response.status_code == 200, "Should accept valid length query"

    def test_search_type_validation(self, security_test_client, authentication_headers, search_service_mocks):
        """Test search_type parameter validation"""
        
        # Valid search types should be accepted
        valid_types = ["fulltext", "semantic", "hybrid", "graph"]
        
        for search_type in valid_types:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": "test", "search_type": search_type}
            )
            assert response.status_code == 200, f"Should accept valid search_type: {search_type}"
        
        # Invalid search types should be rejected
        invalid_types = ["invalid", "sql", "script", "", None, 123, [], {}]
        
        for search_type in invalid_types:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": "test", "search_type": search_type}
            )
            assert response.status_code == 422, f"Should reject invalid search_type: {search_type}"
            self.assert_safe_error_response(response)

    def test_pagination_parameter_validation(self, security_test_client, authentication_headers, search_service_mocks):
        """Test limit and offset parameter validation"""
        
        # Test limit validation
        # Valid limits
        valid_limits = [1, 20, 50, 100]
        for limit in valid_limits:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": "test", "limit": limit}
            )
            assert response.status_code == 200, f"Should accept valid limit: {limit}"
        
        # Invalid limits
        invalid_limits = [0, -1, 101, 1000, "invalid", None, [], {}]
        for limit in invalid_limits:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": "test", "limit": limit}
            )
            assert response.status_code == 422, f"Should reject invalid limit: {limit}"
            self.assert_safe_error_response(response)
        
        # Test offset validation
        # Valid offsets
        valid_offsets = [0, 10, 100, 1000]
        for offset in valid_offsets:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": "test", "offset": offset}
            )
            assert response.status_code == 200, f"Should accept valid offset: {offset}"
        
        # Invalid offsets
        invalid_offsets = [-1, -100, "invalid", None, [], {}]
        for offset in invalid_offsets:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": "test", "offset": offset}
            )
            assert response.status_code == 422, f"Should reject invalid offset: {offset}"
            self.assert_safe_error_response(response)

    def test_malicious_character_validation(self, security_test_client, authentication_headers, malicious_payloads, search_service_mocks):
        """Test handling of malicious characters in query parameters"""
        
        # Test various categories of malicious payloads
        for category, payloads in malicious_payloads.items():
            for payload in payloads:
                response = security_test_client.make_request(
                    'POST',
                    '/search/',
                    headers=authentication_headers['valid_jwt'],
                    json={"query": payload, "search_type": "fulltext"}
                )
                
                # Should either sanitize and process (200) or reject safely (4xx)
                assert response.status_code in [200, 400, 422], \
                    f"Malicious payload should be handled safely: {category} - {payload[:50]}"
                
                if response.status_code != 200:
                    self.assert_safe_error_response(response)
                
                # Ensure malicious content is not reflected in response
                self.assert_no_information_disclosure(response, [payload])

    def test_unicode_and_encoding_validation(self, security_test_client, authentication_headers, search_service_mocks):
        """Test handling of various unicode and encoding attacks"""
        
        unicode_payloads = [
            "test\u202e",  # Right-to-left override
            "test\u2066",  # Left-to-right isolate
            "test\ufeff",  # Zero width no-break space
            "test\u200d",  # Zero width joiner
            "test\x00query",  # Null byte
            "test\r\nquery",  # CRLF injection attempt
            "test\x08query",  # Backspace
            "test\x7fquery",  # DEL character
            "ğǘëŕÿ",  # Accented characters
            "测试查询",  # Chinese characters
            "テストクエリ",  # Japanese characters
            "тестовый запрос",  # Cyrillic characters
            "🔍🚀💻",  # Emojis
        ]
        
        for payload in unicode_payloads:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": payload, "search_type": "fulltext"}
            )
            
            # Should handle unicode safely
            assert response.status_code in [200, 400, 422], \
                f"Unicode payload should be handled safely: {repr(payload)}"
            
            if response.status_code != 200:
                self.assert_safe_error_response(response)

    def test_json_payload_validation(self, security_test_client, authentication_headers, search_service_mocks):
        """Test JSON payload structure validation"""
        
        # Test malformed JSON
        malformed_payloads = [
            '{"query": "test"',  # Missing closing brace
            '{"query": "test", }',  # Trailing comma
            '{"query": "test", "invalid": }',  # Missing value
            '{"query": "test", "limit": "invalid"}',  # Wrong type
            '{"query": "test", "search_type": ["array"]}',  # Wrong type
        ]
        
        for payload in malformed_payloads:
            response = security_test_client.client.post(
                '/search/',
                headers=authentication_headers['valid_jwt'],
                content=payload,
                headers={**authentication_headers['valid_jwt'], 'Content-Type': 'application/json'}
            )
            assert response.status_code == 422, f"Should reject malformed JSON: {payload}"
            self.assert_safe_error_response(response)

    def test_content_type_validation(self, security_test_client, authentication_headers, search_service_mocks):
        """Test Content-Type header validation"""
        
        # Test invalid content types
        invalid_content_types = [
            'text/plain',
            'application/xml',
            'application/x-www-form-urlencoded',
            'multipart/form-data',
            'text/html',
            'application/javascript'
        ]
        
        for content_type in invalid_content_types:
            response = security_test_client.client.post(
                '/search/',
                headers={
                    **authentication_headers['valid_jwt'],
                    'Content-Type': content_type
                },
                content='{"query": "test"}'
            )
            assert response.status_code in [400, 422, 415], \
                f"Should reject invalid content type: {content_type}"

    def test_suggestions_parameter_validation(self, security_test_client, authentication_headers, search_service_mocks):
        """Test search suggestions endpoint parameter validation"""
        
        # Test query parameter validation
        # Too short query
        response = security_test_client.make_request(
            'GET',
            '/search/suggestions?q=a',
            headers=authentication_headers['valid_jwt']
        )
        assert response.status_code == 422, "Should reject too short suggestion query"
        
        # Too long query
        long_query = "a" * 101
        response = security_test_client.make_request(
            'GET',
            f'/search/suggestions?q={long_query}',
            headers=authentication_headers['valid_jwt']
        )
        assert response.status_code == 422, "Should reject too long suggestion query"
        
        # Invalid limit values
        invalid_limits = [-1, 0, 21, 100]
        for limit in invalid_limits:
            response = security_test_client.make_request(
                'GET',
                f'/search/suggestions?q=test&limit={limit}',
                headers=authentication_headers['valid_jwt']
            )
            assert response.status_code == 422, f"Should reject invalid limit: {limit}"

    def test_history_endpoint_validation(self, security_test_client, authentication_headers, search_service_mocks):
        """Test search history endpoints parameter validation"""
        
        # Test GET history with invalid limit
        invalid_limits = [-1, 0, 101, 1000]
        for limit in invalid_limits:
            response = security_test_client.make_request(
                'GET',
                f'/search/history?limit={limit}',
                headers=authentication_headers['valid_jwt']
            )
            assert response.status_code == 422, f"Should reject invalid history limit: {limit}"
        
        # Test POST history with invalid data
        invalid_queries = ["", " " * 1000]
        for query in invalid_queries:
            response = security_test_client.make_request(
                'POST',
                '/search/history',
                headers=authentication_headers['valid_jwt'],
                json={"query": query}
            )
            assert response.status_code == 422, f"Should reject invalid history query: '{query}'"

    def test_filter_parameter_validation(self, security_test_client, authentication_headers, search_service_mocks):
        """Test search filter parameter validation"""
        
        # Test invalid date formats
        invalid_dates = [
            "invalid-date",
            "2023-13-01",  # Invalid month
            "2023-02-30",  # Invalid day
            "2023/01/01",  # Wrong format
            "01-01-2023",  # Wrong format
            "2023-1-1",    # Missing zero padding
        ]
        
        for date in invalid_dates:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={
                    "query": "test",
                    "filters": {
                        "date_from": date
                    }
                }
            )
            assert response.status_code == 422, f"Should reject invalid date format: {date}"
        
        # Test invalid file size values
        invalid_sizes = [-1, "invalid", [], {}]
        for size in invalid_sizes:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={
                    "query": "test",
                    "filters": {
                        "file_size_min": size
                    }
                }
            )
            assert response.status_code == 422, f"Should reject invalid file size: {size}"

    def test_nested_object_validation(self, security_test_client, authentication_headers, search_service_mocks):
        """Test validation of nested objects in search requests"""
        
        # Test deeply nested malicious payloads
        nested_payloads = [
            {
                "query": "test",
                "filters": {
                    "tags": ["'; DROP TABLE documents; --"],
                    "organization_id": "<script>alert('xss')</script>"
                }
            },
            {
                "query": "test",
                "filters": {
                    "document_types": ["../../../etc/passwd"],
                    "uploaded_by_user_id": "' OR '1'='1"
                }
            },
            {
                "query": "test",
                "filters": {
                    "tags": ["test", "valid", "'; DROP TABLE users; --"],
                }
            }
        ]
        
        for payload in nested_payloads:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json=payload
            )
            
            # Should sanitize or reject safely
            assert response.status_code in [200, 400, 422], \
                "Nested malicious payload should be handled safely"
            
            if response.status_code != 200:
                self.assert_safe_error_response(response)

    def test_request_size_limits(self, security_test_client, authentication_headers, search_service_mocks):
        """Test request payload size limits"""
        
        # Create oversized payloads
        oversized_payloads = [
            {
                "query": "A" * 10000,  # Very long query
                "search_type": "fulltext"
            },
            {
                "query": "test",
                "filters": {
                    "tags": ["tag"] * 1000,  # Many tags
                }
            },
            {
                "query": "test",
                "search_type": "fulltext",
                "extra_field": "X" * 50000  # Large extra field
            }
        ]
        
        for payload in oversized_payloads:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json=payload
            )
            
            # Should reject oversized payloads
            assert response.status_code in [413, 422, 400], \
                "Oversized payload should be rejected"
            self.assert_safe_error_response(response)

    def test_parameter_type_coercion_attacks(self, security_test_client, authentication_headers, search_service_mocks):
        """Test parameter type coercion attack vectors"""
        
        # Test type confusion attacks
        type_confusion_payloads = [
            {"query": 123},  # Number instead of string
            {"query": []},   # Array instead of string
            {"query": {}},   # Object instead of string
            {"query": True}, # Boolean instead of string
            {"query": None}, # Null instead of string
            {"limit": "10"}, # String instead of number
            {"offset": []},  # Array instead of number
            {"search_type": 123}, # Number instead of string
            {"filters": "invalid"}, # String instead of object
        ]
        
        for payload in type_confusion_payloads:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json=payload
            )
            assert response.status_code == 422, \
                f"Should reject type confusion payload: {payload}"
            self.assert_safe_error_response(response)

    def test_boundary_value_validation(self, security_test_client, authentication_headers, search_service_mocks):
        """Test boundary values for all numeric parameters"""
        
        # Test exact boundary values for limit
        boundary_limits = [1, 100]  # Min and max allowed
        for limit in boundary_limits:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": "test", "limit": limit}
            )
            assert response.status_code == 200, f"Should accept boundary limit: {limit}"
        
        # Test exact boundary values for offset
        response = security_test_client.make_request(
            'POST',
            '/search/',
            headers=authentication_headers['valid_jwt'],
            json={"query": "test", "offset": 0}  # Minimum allowed
        )
        assert response.status_code == 200, "Should accept minimum offset"
        
        # Test integer overflow attempts
        overflow_values = [2**31, 2**63, float('inf'), -2**31-1]
        for value in overflow_values:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": "test", "limit": value}
            )
            assert response.status_code == 422, f"Should reject overflow value: {value}"

    def test_empty_and_null_validation(self, security_test_client, authentication_headers, search_service_mocks):
        """Test handling of empty and null values"""
        
        # Test empty payload
        response = security_test_client.make_request(
            'POST',
            '/search/',
            headers=authentication_headers['valid_jwt'],
            json={}
        )
        assert response.status_code == 422, "Should reject empty payload"
        
        # Test null values in required fields
        null_payloads = [
            {"query": None, "search_type": "fulltext"},
            {"query": "test", "search_type": None},
        ]
        
        for payload in null_payloads:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json=payload
            )
            assert response.status_code == 422, f"Should reject null values: {payload}"
            self.assert_safe_error_response(response)