"""
Search Endpoint Security Test Suite

A comprehensive security testing framework for search endpoints covering:
- Input validation and sanitization
- Authentication and authorization security
- SQL injection prevention
- XSS (Cross-Site Scripting) protection
- Rate limiting and abuse prevention
- Error handling and information disclosure prevention

This module provides extensive security testing for all search-related endpoints
in the RAG system, ensuring robust security posture against common attack vectors.

Usage:
    # Run all search security tests
    pytest tests/security/search_security/ -v
    
    # Run specific test category
    pytest tests/security/search_security/test_input_validation.py -v
    
    # Run with coverage
    pytest tests/security/search_security/ --cov=src/api/search --cov-report=html
    
    # Run in parallel
    pytest tests/security/search_security/ -n auto

Test Categories:
    1. Input Validation (test_input_validation.py)
    2. Authentication & Authorization (test_auth_security.py)
    3. SQL Injection Prevention (test_sql_injection.py)
    4. XSS Protection (test_xss_protection.py)
    5. Rate Limiting (test_rate_limiting.py)
    6. Error Handling (test_error_handling.py)

Security Principles Tested:
    - Defense in depth
    - Fail securely
    - Least privilege
    - Complete mediation
    - Security through obscurity avoidance
    - Input validation and output encoding
    - Separation of duties
"""

__version__ = "1.0.0"
__author__ = "Security Testing Team"

# Test configuration constants
TEST_TIMEOUT = 30  # seconds
MAX_TEST_REQUESTS = 100
RATE_LIMIT_TEST_WINDOW = 60  # seconds

# Security test markers
SECURITY_CRITICAL = "security_critical"
PERFORMANCE_INTENSIVE = "performance_intensive"
REQUIRES_ISOLATION = "requires_isolation"

# Common security patterns to test against
COMMON_XSS_PATTERNS = [
    "<script>alert('xss')</script>",
    "<img src=x onerror=alert('xss')>",
    "javascript:alert('xss')",
    "<svg onload=alert('xss')>",
]

COMMON_SQL_INJECTION_PATTERNS = [
    "'; DROP TABLE users; --",
    "' OR '1'='1",
    "' UNION SELECT * FROM users --",
    "; INSERT INTO logs VALUES('injected'); --",
]

COMMON_PATH_TRAVERSAL_PATTERNS = [
    "../../../etc/passwd",
    "..\\..\\..\\windows\\system32\\drivers\\etc\\hosts",
    "....//....//....//etc/passwd",
]

# Test utilities
def get_test_suite_info():
    """Get information about the test suite"""
    return {
        "version": __version__,
        "test_categories": 6,
        "total_test_methods": "150+",
        "coverage_areas": [
            "Input validation",
            "Authentication security",
            "Authorization controls",
            "SQL injection prevention",
            "XSS protection",
            "Rate limiting",
            "Error handling",
            "Information disclosure prevention",
            "Session management",
            "Audit logging",
        ]
    }

def get_security_test_markers():
    """Get available pytest markers for security tests"""
    return {
        SECURITY_CRITICAL: "Tests critical security vulnerabilities that must pass",
        PERFORMANCE_INTENSIVE: "Tests that may take longer due to load simulation",
        REQUIRES_ISOLATION: "Tests that need isolated environment to avoid interference",
    }

# Export all test classes for external use
from .test_input_validation import TestSearchInputValidation
from .test_auth_security import TestSearchAuthenticationSecurity, TestSearchAuthorizationSecurity
from .test_sql_injection import TestSQLInjectionPrevention
from .test_xss_protection import TestXSSProtection
from .test_rate_limiting import TestRateLimiting, TestRateLimitingEdgeCases
from .test_error_handling import TestErrorHandlingSecurity, TestErrorHandlingEdgeCases

__all__ = [
    "TestSearchInputValidation",
    "TestSearchAuthenticationSecurity", 
    "TestSearchAuthorizationSecurity",
    "TestSQLInjectionPrevention",
    "TestXSSProtection",
    "TestRateLimiting",
    "TestRateLimitingEdgeCases",
    "TestErrorHandlingSecurity",
    "TestErrorHandlingEdgeCases",
    "get_test_suite_info",
    "get_security_test_markers",
    "COMMON_XSS_PATTERNS",
    "COMMON_SQL_INJECTION_PATTERNS",
    "COMMON_PATH_TRAVERSAL_PATTERNS",
]