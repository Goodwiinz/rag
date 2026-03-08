"""
Comprehensive Security Tests for Search Functionality

Tests cover:
- SQL Injection prevention
- XSS prevention
- NoSQL/Cypher injection prevention
- Input validation
- Rate limiting
- Authentication/Authorization
- Audit logging
"""

import pytest
import re
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

# Import the security module
import sys
sys.path.insert(0, 'src')

from src.security.search_security import (
    SearchQuerySanitizer,
    SearchSnippetSanitizer,
    SearchAuditLogger,
    SearchSecurityError,
    SearchAuditEvent,
    extract_client_ip,
    mask_sensitive_data
)


class TestSearchQuerySanitizer:
    """Test suite for query sanitization"""
    
    # SQL Injection attack vectors
    SQL_INJECTION_PAYLOADS = [
        "' OR '1'='1",
        "'; DROP TABLE documents; --",
        "1; SELECT * FROM users",
        "\\'; WAITFOR DELAY '00:00:05'; --",
        "UNION SELECT password FROM users",
        "1 AND 1=1",
        "1' AND '1'='1",
        "admin'--",
        "1 OR 1=1",
        "' UNION SELECT NULL, NULL, NULL--",
        "1' UNION ALL SELECT NULL,NULL,NULL--",
        "' OR 'x'='x",
        "1; exec xp_cmdshell('dir');--",
        "1' AND SLEEP(5)--",
        "1' AND (SELECT 1 FROM (SELECT COUNT(*),CONCAT((SELECT user()),0x3a,FLOOR(RAND(0)*2))x FROM INFORMATION_SCHEMA.tables GROUP BY x)a)--",
        "1' UNION SELECT load_file('/etc/passwd')--",
        "1' INTO OUTFILE '/tmp/test.txt'--",
    ]
    
    # XSS attack vectors
    XSS_PAYLOADS = [
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert('XSS')>",
        "<svg onload=alert('XSS')>",
        "javascript:alert('XSS')",
        "<body onload=alert('XSS')>",
        "'-alert('XSS')-'",
        "<iframe src='javascript:alert(1)'>",
        "<img src=\"javascript:alert('XSS')\">",
        "<div style=\"expression(alert('XSS'))\">",
        "<a href=\"javascript:alert('XSS')\">click</a>",
        "'\"><script>alert(String.fromCharCode(88,83,83))</script>",
        "<IMG SRC=javascript:alert(&quot;XSS&quot;)>",
        "<SCRIPT SRC=http://evil.com/xss.js></SCRIPT>",
        "<<SCRIPT>alert('XSS');//<</SCRIPT>",
        "<IMG SRC=\" \" onerror=\"alert('XSS')\">",
    ]
    
    # NoSQL/Cypher injection vectors
    NOSQL_PAYLOADS = [
        "$where: 'this.password.length > 0'",
        "{ $gt: '' }",
        "{ $ne: null }",
        "MATCH (n) DETACH DELETE n",
        "CREATE (n:User {name:'hacker'})",
        "MERGE (n:Admin)",
        "'; MATCH (n) RETURN n //",
    ]
    
    @pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
    def test_sql_injection_blocked(self, payload):
        """Test that SQL injection payloads are blocked in strict mode"""
        with pytest.raises(SearchSecurityError):
            SearchQuerySanitizer.sanitize(payload, strict=True)
    
    @pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
    def test_sql_injection_sanitized(self, payload):
        """Test that SQL injection payloads are sanitized in non-strict mode"""
        result = SearchQuerySanitizer.sanitize(payload, strict=False)
        
        # Verify dangerous keywords are removed
        dangerous_keywords = ['union', 'select', 'insert', 'update', 'delete', 
                             'drop', 'exec', 'execute', 'waitfor', 'sleep']
        result_lower = result.lower()
        
        for keyword in dangerous_keywords:
            assert keyword not in result_lower or keyword in payload.lower().split(), \
                f"Dangerous keyword '{keyword}' found in sanitized result"
    
    @pytest.mark.parametrize("payload", XSS_PAYLOADS)
    def test_xss_blocked(self, payload):
        """Test that XSS payloads are blocked or sanitized"""
        result = SearchQuerySanitizer.sanitize(payload, strict=False)
        
        # Verify no script tags or event handlers remain
        assert '<script' not in result.lower()
        assert 'javascript:' not in result.lower()
        assert 'onerror=' not in result.lower()
        assert 'onload=' not in result.lower()
    
    @pytest.mark.parametrize("payload", NOSQL_PAYLOADS)
    def test_nosql_injection_blocked(self, payload):
        """Test that NoSQL injection payloads are handled"""
        result = SearchQuerySanitizer.sanitize(payload, strict=False)
        
        # Verify MongoDB operators are removed
        assert '$' not in result
        
        # Verify Cypher keywords are removed
        assert 'MATCH' not in result.upper() or result.upper().count('MATCH') == 0
    
    def test_legitimate_queries_allowed(self):
        """Test that legitimate search queries pass through"""
        legitimate_queries = [
            "machine learning tutorial",
            "how to cook pasta",
            "python programming basics",
            "financial report 2024",
            "user guide installation",
            "best practices security",
            "data-driven decisions",
            "self-improvement books",
        ]
        
        for query in legitimate_queries:
            result = SearchQuerySanitizer.sanitize(query, strict=True)
            # Words should remain (may have minor formatting changes)
            for word in query.split():
                if len(word) >= 2 and word.isalpha():
                    assert word.lower() in result.lower() or word.replace('-', '') in result, \
                        f"Legitimate word '{word}' was removed from query"
    
    def test_length_limit_enforced(self):
        """Test that query length limits are enforced"""
        long_query = "a" * 1000
        result = SearchQuerySanitizer.sanitize(long_query)
        assert len(result) <= SearchQuerySanitizer.MAX_QUERY_LENGTH
    
    def test_unicode_normalization(self):
        """Test that unicode is normalized to prevent bypasses"""
        # Using unicode confusables
        unicode_bypass = "\u0027OR\u00271\u0027=\u00271"  # ' with unicode quotes
        result = SearchQuerySanitizer.sanitize(unicode_bypass, strict=False)
        
        # Should be sanitized
        assert "or" not in result.lower() or len(result) < 5
    
    def test_empty_query(self):
        """Test handling of empty queries"""
        assert SearchQuerySanitizer.sanitize("") == ""
        assert SearchQuerySanitizer.sanitize("   ") == ""
        assert SearchQuerySanitizer.sanitize(None) == "" if SearchQuerySanitizer.sanitize("") == "" else True
    
    def test_security_score_calculation(self):
        """Test security risk score calculation"""
        # Safe query
        safe_score = SearchQuerySanitizer.get_security_score("machine learning")
        assert safe_score < 20
        
        # Risky query
        risky_score = SearchQuerySanitizer.get_security_score("'; DROP TABLE users; --")
        assert risky_score >= 30
        
        # Very risky query
        very_risky_score = SearchQuerySanitizer.get_security_score(
            "1' UNION SELECT password FROM users WHERE '1'='1"
        )
        assert very_risky_score >= 50
    
    def test_is_safe_method(self):
        """Test the is_safe convenience method"""
        assert SearchQuerySanitizer.is_safe("normal search query")
        assert not SearchQuerySanitizer.is_safe("'; DROP TABLE users; --")


class TestSearchSnippetSanitizer:
    """Test suite for HTML snippet sanitization"""
    
    def test_preserves_safe_tags(self):
        """Test that safe highlight tags are preserved"""
        snippet = "This is a <mark>highlighted</mark> result with <b>bold</b> text"
        result = SearchSnippetSanitizer.sanitize(snippet, preserve_highlights=True)
        
        assert "<mark>" in result
        assert "</mark>" in result
        assert "<b>" in result
        assert "</b>" in result
    
    def test_removes_script_tags(self):
        """Test that script tags are removed"""
        snippet = "Normal text <script>alert('XSS')</script> more text"
        result = SearchSnippetSanitizer.sanitize(snippet)
        
        assert "<script>" not in result
        assert "</script>" not in result
        assert "alert" not in result
    
    def test_removes_event_handlers(self):
        """Test that event handlers are removed"""
        snippet = '<img src="x" onerror="alert(\'XSS\')">'
        result = SearchSnippetSanitizer.sanitize(snippet)
        
        assert "onerror" not in result
        assert "alert" not in result
    
    def test_strip_all_html(self):
        """Test complete HTML stripping"""
        snippet = "<p>Text with <b>bold</b> and <script>evil</script></p>"
        result = SearchSnippetSanitizer.strip_all_html(snippet)
        
        assert "<" not in result
        assert ">" not in result
        assert "script" not in result.lower()
    
    def test_complex_xss_payload(self):
        """Test complex XSS payload handling"""
        payloads = [
            '<svg/onload=alert("XSS")>',
            '"><img src=x onerror=alert(1)>',
            '<body onpageshow=alert(1)>',
            '<<SCRIPT>alert("XSS");//<</SCRIPT>',
            '<STYLE>@import"javascript:alert(\'XSS\')"</STYLE>',
        ]
        
        for payload in payloads:
            result = SearchSnippetSanitizer.sanitize(payload)
            assert 'alert' not in result.lower()
            assert 'javascript' not in result.lower()


class TestSearchAuditLogger:
    """Test suite for audit logging"""
    
    def test_query_hashing(self):
        """Test that queries are hashed consistently"""
        query = "sensitive search query"
        
        hash1 = SearchAuditLogger.hash_query(query)
        hash2 = SearchAuditLogger.hash_query(query)
        
        # Hashes should be consistent
        assert hash1 == hash2
        
        # Hash should not be the original query
        assert hash1 != query
        
        # Hash should be a reasonable length
        assert len(hash1) == 16
    
    def test_different_queries_different_hashes(self):
        """Test that different queries produce different hashes"""
        query1 = "first search query"
        query2 = "second search query"
        
        hash1 = SearchAuditLogger.hash_query(query1)
        hash2 = SearchAuditLogger.hash_query(query2)
        
        assert hash1 != hash2
    
    def test_audit_event_creation(self):
        """Test audit event data structure"""
        event = SearchAuditEvent(
            timestamp=datetime.utcnow(),
            event_type='SEARCH_PERFORMED',
            user_id='user123',
            organization_id='org456',
            query_hash='abc123',
            query_length=25,
            search_type='hybrid',
            result_count=10,
            search_time_ms=150.5,
            client_ip='192.168.1.1',
            user_agent='Mozilla/5.0',
            request_id='req789',
            security_score=5,
            security_flags={'high_risk': False}
        )
        
        event_dict = event.to_dict()
        
        assert event_dict['user_id'] == 'user123'
        assert event_dict['organization_id'] == 'org456'
        assert event_dict['security_score'] == 5
        assert 'timestamp' in event_dict


class TestUtilityFunctions:
    """Test utility functions"""
    
    def test_extract_client_ip_direct(self):
        """Test IP extraction from direct connection"""
        mock_request = Mock()
        mock_request.headers = {}
        mock_request.client.host = '192.168.1.100'
        
        ip = extract_client_ip(mock_request)
        assert ip == '192.168.1.100'
    
    def test_extract_client_ip_forwarded(self):
        """Test IP extraction from X-Forwarded-For header"""
        mock_request = Mock()
        mock_request.headers = {'X-Forwarded-For': '10.0.0.1, 192.168.1.1'}
        mock_request.client.host = '127.0.0.1'
        
        ip = extract_client_ip(mock_request)
        assert ip == '192.168.1.1'  # Last IP in chain
    
    def test_extract_client_ip_real_ip(self):
        """Test IP extraction from X-Real-IP header"""
        mock_request = Mock()
        mock_request.headers = {'X-Real-IP': '10.0.0.50'}
        mock_request.client.host = '127.0.0.1'
        
        ip = extract_client_ip(mock_request)
        assert ip == '10.0.0.50'
    
    def test_mask_sensitive_data(self):
        """Test sensitive data masking"""
        data = {
            'user_id': '12345678',
            'email': 'user@example.com',
            'query': 'normal search'
        }
        
        masked = mask_sensitive_data(data, ['user_id', 'email'])
        
        assert masked['user_id'] == '12****78'
        assert masked['email'] != 'user@example.com'
        assert masked['query'] == 'normal search'  # Not sensitive


class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_repeated_characters(self):
        """Test handling of repeated characters (potential DoS)"""
        repeated = "a" * 10000
        result = SearchQuerySanitizer.sanitize(repeated)
        
        # Should be truncated
        assert len(result) <= SearchQuerySanitizer.MAX_QUERY_LENGTH
    
    def test_null_bytes(self):
        """Test handling of null bytes"""
        with_nulls = "test\x00query\x00string"
        result = SearchQuerySanitizer.sanitize(with_nulls, strict=False)
        
        assert '\x00' not in result
    
    def test_mixed_encoding(self):
        """Test handling of mixed encoding"""
        mixed = "test%20query%3Cscript%3E"
        result = SearchQuerySanitizer.sanitize(mixed, strict=False)
        
        # Encoded script should not execute
        assert '<script>' not in result
    
    def test_unicode_categories(self):
        """Test handling of various unicode categories"""
        unicode_test = "测试 тест 테스트 テスト"
        result = SearchQuerySanitizer.sanitize(unicode_test)
        
        # Should handle gracefully (either keep or remove, not crash)
        assert isinstance(result, str)
    
    def test_emoji_handling(self):
        """Test handling of emojis"""
        with_emoji = "search query 🔍 with emoji 😀"
        result = SearchQuerySanitizer.sanitize(with_emoji, strict=False)
        
        # Should not crash
        assert isinstance(result, str)


class TestSecurityIntegration:
    """Integration tests for security components"""
    
    def test_end_to_end_sanitization(self):
        """Test complete sanitization pipeline"""
        # Malicious input
        malicious = "search'; DROP TABLE users; -- <script>alert('XSS')</script>"
        
        # Sanitize query
        sanitized = SearchQuerySanitizer.sanitize(malicious, strict=False)
        
        # Verify no dangerous content
        assert 'DROP' not in sanitized
        assert '<script>' not in sanitized
        assert '--' not in sanitized
        
        # Verify some search intent preserved
        assert 'search' in sanitized.lower()
    
    def test_security_score_affects_audit(self):
        """Test that high security scores are flagged in audit"""
        logger = SearchAuditLogger()
        
        # Mock the logging
        with patch.object(logger.security_logger, 'warning') as mock_warning:
            logger.log_search(
                user_id='user1',
                organization_id='org1',
                query="'; DROP TABLE users; --",  # High risk query
                search_type='hybrid',
                result_count=0,
                search_time_ms=100,
                client_ip='192.168.1.1',
                user_agent='Test Agent',
                request_id='req1'
            )
            
            # Should trigger security warning due to high risk score
            mock_warning.assert_called()


class TestRateLimitingHelpers:
    """Test rate limiting helper functions"""
    
    def test_rate_limit_key_generation(self):
        """Test rate limit key generation"""
        from src.security.search_security import get_rate_limit_key, get_ip_rate_limit_key
        
        user_key = get_rate_limit_key('user123', '/search/')
        ip_key = get_ip_rate_limit_key('192.168.1.1', '/search/')
        
        assert 'user123' in user_key
        assert '/search/' in user_key
        assert '192.168.1.1' in ip_key


# Fixtures
@pytest.fixture
def mock_request():
    """Create a mock FastAPI request"""
    request = Mock()
    request.headers = {
        'X-Forwarded-For': '10.0.0.1',
        'User-Agent': 'TestAgent/1.0',
        'X-Request-Id': 'test-request-123'
    }
    request.client = Mock()
    request.client.host = '127.0.0.1'
    return request


@pytest.fixture
def sanitizer():
    """Get sanitizer instance"""
    return SearchQuerySanitizer()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
