"""
Security Testing Suite for RAG Search Endpoint

This module provides comprehensive security testing covering:
- Input Validation (SQL Injection, XSS, Command Injection, etc.)
- Authentication Mechanisms (JWT, API Keys, Sessions)
- Authorization Scopes (RBAC, Multi-tenancy, IDOR)
- Rate Limiting (Enforcement, Bypass Prevention)
- Error Handling (Information Disclosure Prevention)
- Logging and Auditing (Security Event Logging)

Usage:
    # Run all tests
    pytest tests/security/ -v
    
    # Run specific test file
    pytest tests/security/test_search_security.py -v
    
    # Run as standalone script
    python tests/security/test_search_security.py
"""

from .test_search_security import (
    TestInputValidation,
    TestAuthentication,
    TestAuthorization,
    TestRateLimiting,
    TestErrorHandling,
    TestLoggingAuditing,
    SecurityTestRunner,
    TestConfig,
    TestUser,
)

__all__ = [
    "TestInputValidation",
    "TestAuthentication",
    "TestAuthorization",
    "TestRateLimiting",
    "TestErrorHandling",
    "TestLoggingAuditing",
    "SecurityTestRunner",
    "TestConfig",
    "TestUser",
]
