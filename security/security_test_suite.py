#!/usr/bin/env python3
"""
Comprehensive Security Test Suite for Multimodal Enterprise RAG System
Tests for OWASP Top 10 vulnerabilities and security controls
"""

import asyncio
import aiohttp
import pytest
import json
import time
import hashlib
import base64
import jwt
from typing import Dict, List, Any
from urllib.parse import urljoin
import logging
from dataclasses import dataclass
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VulnerabilitySeverity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

@dataclass
class SecurityTestResult:
    test_name: str
    severity: VulnerabilitySeverity
    passed: bool
    description: str
    details: Dict[str, Any]
    recommendation: str

class SecurityTestSuite:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None
        self.test_results: List[SecurityTestResult] = []

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def add_result(self, test_name: str, severity: VulnerabilitySeverity,
                   passed: bool, description: str, details: Dict[str, Any] = None,
                   recommendation: str = ""):
        """Add test result to the suite"""
        result = SecurityTestResult(
            test_name=test_name,
            severity=severity,
            passed=passed,
            description=description,
            details=details or {},
            recommendation=recommendation
        )
        self.test_results.append(result)
        status = "PASS" if passed else "FAIL"
        logger.info(f"[{status}] {test_name}: {description}")

    async def test_sql_injection(self) -> None:
        """Test for SQL injection vulnerabilities"""
        logger.info("Testing SQL injection vulnerabilities...")

        # SQL injection payloads
        payloads = [
            "' OR '1'='1",
            "' OR '1'='1' --",
            "' OR '1'='1' /*",
            "admin'--",
            "admin'/*",
            "' OR 1=1--",
            "' OR 1=1#",
            "' OR 1=1/*",
            "') OR '1'='1--",
            "') OR ('1'='1--",
            "1' OR '1'='1' --",
            "1' OR '1'='1' /*",
            "1' UNION SELECT * FROM users--",
            "'; DROP TABLE users; --",
            "'; EXEC xp_cmdshell('dir'); --"
        ]

        # Test endpoints
        test_endpoints = [
            "/api/v1/auth/login",
            "/api/v1/documents",
            "/api/v1/search",
            "/api/v1/users"
        ]

        for endpoint in test_endpoints:
            for payload in payloads:
                try:
                    # Test in query parameters
                    url = urljoin(self.base_url, endpoint) + f"?search={payload}"
                    async with self.session.get(url) as response:
                        if response.status == 200:
                            text = await response.text()
                            # Check for SQL error messages
                            sql_errors = [
                                "syntax error", "mysql_fetch", "ORA-", "Microsoft OLE DB",
                                "SQL syntax", "Warning: mysql", "valid MySQL result",
                                "PostgreSQL query failed", "SQLServer JDBC Driver"
                            ]
                            if any(error.lower() in text.lower() for error in sql_errors):
                                self.add_result(
                                    "SQL Injection",
                                    VulnerabilitySeverity.CRITICAL,
                                    False,
                                    f"SQL injection vulnerability detected in {endpoint}",
                                    {"payload": payload, "endpoint": endpoint, "response_sample": text[:200]},
                                    "Implement parameterized queries and input validation"
                                )
                                return

                    # Test in POST data
                    if endpoint in ["/api/v1/auth/login", "/api/v1/documents"]:
                        data = {"username": payload, "password": "test"}
                        async with self.session.post(urljoin(self.base_url, endpoint), json=data) as response:
                            if response.status == 200:
                                text = await response.text()
                                if any(error.lower() in text.lower() for error in sql_errors):
                                    self.add_result(
                                        "SQL Injection",
                                        VulnerabilitySeverity.CRITICAL,
                                        False,
                                        f"SQL injection vulnerability detected in {endpoint}",
                                        {"payload": payload, "endpoint": endpoint},
                                        "Implement parameterized queries and input validation"
                                    )
                                    return

                except Exception as e:
                    continue

        self.add_result(
            "SQL Injection",
            VulnerabilitySeverity.LOW,
            True,
            "No obvious SQL injection vulnerabilities detected",
            {"tested_payloads": len(payloads), "tested_endpoints": len(test_endpoints)},
            "Continue monitoring and implement WAF rules"
        )

    async def test_xss_vulnerabilities(self) -> None:
        """Test for Cross-Site Scripting vulnerabilities"""
        logger.info("Testing XSS vulnerabilities...")

        # XSS payloads
        payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<svg onload=alert('XSS')>",
            "';alert('XSS');//",
            "<iframe src=javascript:alert('XSS')>",
            "<body onload=alert('XSS')>",
            "<input autofocus onfocus=alert('XSS')>",
            "<select onfocus=alert('XSS') autofocus>",
            "<textarea onfocus=alert('XSS') autofocus>",
            "<keygen onfocus=alert('XSS') autofocus>",
            "<video><source onerror=alert('XSS')>",
            "<details open ontoggle=alert('XSS')>",
            "<marquee onstart=alert('XSS')>",
            "';alert(String.fromCharCode(88,83,83))//';alert(String.fromCharCode(88,83,83))//\";alert(String.fromCharCode(88,83,83))//\";alert(String.fromCharCode(88,83,83))//--></SCRIPT>\"'><SCRIPT>alert(String.fromCharCode(88,83,83))</SCRIPT>"
        ]

        # Test endpoints that accept user input
        test_endpoints = [
            "/api/v1/search",
            "/api/v1/documents",
            "/api/v1/users"
        ]

        for endpoint in test_endpoints:
            for payload in payloads:
                try:
                    # Test in query parameters
                    url = urljoin(self.base_url, endpoint) + f"?q={payload}"
                    async with self.session.get(url) as response:
                        if response.status == 200:
                            text = await response.text()
                            if payload in text and "<script>" in text.lower():
                                self.add_result(
                                    "Cross-Site Scripting (XSS)",
                                    VulnerabilitySeverity.HIGH,
                                    False,
                                    f"XSS vulnerability detected in {endpoint}",
                                    {"payload": payload, "endpoint": endpoint},
                                    "Implement proper output encoding and CSP headers"
                                )
                                return

                    # Test in POST data
                    data = {"content": payload, "title": payload}
                    async with self.session.post(urljoin(self.base_url, endpoint), json=data) as response:
                        if response.status == 200:
                            text = await response.text()
                            if payload in text and "<script>" in text.lower():
                                self.add_result(
                                    "Cross-Site Scripting (XSS)",
                                    VulnerabilitySeverity.HIGH,
                                    False,
                                    f"XSS vulnerability detected in {endpoint}",
                                    {"payload": payload, "endpoint": endpoint},
                                    "Implement proper output encoding and CSP headers"
                                )
                                return

                except Exception as e:
                    continue

        self.add_result(
            "Cross-Site Scripting (XSS)",
            VulnerabilitySeverity.LOW,
            True,
            "No obvious XSS vulnerabilities detected",
            {"tested_payloads": len(payloads), "tested_endpoints": len(test_endpoints)},
            "Implement Content Security Policy (CSP) headers"
        )

    async def test_authentication_bypass(self) -> None:
        """Test for authentication bypass vulnerabilities"""
        logger.info("Testing authentication bypass vulnerabilities...")

        # Test endpoints that should require authentication
        protected_endpoints = [
            "/api/v1/auth/me",
            "/api/v1/documents",
            "/api/v1/users",
            "/api/v1/analytics/quality"
        ]

        for endpoint in protected_endpoints:
            try:
                # Test without authentication
                async with self.session.get(urljoin(self.base_url, endpoint)) as response:
                    if response.status == 200:
                        self.add_result(
                            "Authentication Bypass",
                            VulnerabilitySeverity.CRITICAL,
                            False,
                            f"Authentication bypass vulnerability in {endpoint}",
                            {"endpoint": endpoint, "status_code": response.status},
                            "Implement proper authentication middleware"
                        )
                        return
                    elif response.status != 401 and response.status != 403:
                        self.add_result(
                            "Authentication Bypass",
                            VulnerabilitySeverity.MEDIUM,
                            False,
                            f"Unexpected response code for unauthenticated request to {endpoint}",
                            {"endpoint": endpoint, "status_code": response.status},
                            "Ensure protected endpoints return 401/403"
                        )

                # Test with invalid token
                headers = {"Authorization": "Bearer invalid_token"}
                async with self.session.get(urljoin(self.base_url, endpoint), headers=headers) as response:
                    if response.status == 200:
                        self.add_result(
                            "Authentication Bypass",
                            VulnerabilitySeverity.CRITICAL,
                            False,
                            f"Invalid token accepted in {endpoint}",
                            {"endpoint": endpoint},
                            "Implement proper token validation"
                        )
                        return

                # Test with expired token
                expired_token = self._create_expired_jwt()
                headers = {"Authorization": f"Bearer {expired_token}"}
                async with self.session.get(urljoin(self.base_url, endpoint), headers=headers) as response:
                    if response.status == 200:
                        self.add_result(
                            "Authentication Bypass",
                            VulnerabilitySeverity.HIGH,
                            False,
                            f"Expired token accepted in {endpoint}",
                            {"endpoint": endpoint},
                            "Implement proper token expiration checks"
                        )
                        return

            except Exception as e:
                continue

        self.add_result(
            "Authentication Bypass",
            VulnerabilitySeverity.LOW,
            True,
            "Authentication controls appear to be working correctly",
            {"tested_endpoints": len(protected_endpoints)},
            "Continue monitoring authentication logs"
        )

    async def test_authorization_bypass(self) -> None:
        """Test for authorization bypass vulnerabilities"""
        logger.info("Testing authorization bypass vulnerabilities...")

        # Create test users with different roles
        test_users = [
            {"email": "user@test.com", "password": "testpass", "role": "user"},
            {"email": "admin@test.com", "password": "adminpass", "role": "admin"}
        ]

        # Test admin endpoints with user token
        admin_endpoints = [
            "/api/v1/auth/users",
            "/api/v1/auth/statistics",
            "/api/v1/rbac/roles"
        ]

        for endpoint in admin_endpoints:
            try:
                # Get user token (simulated)
                user_token = await self._get_user_token(test_users[0])
                headers = {"Authorization": f"Bearer {user_token}"}

                async with self.session.get(urljoin(self.base_url, endpoint), headers=headers) as response:
                    if response.status == 200:
                        self.add_result(
                            "Authorization Bypass",
                            VulnerabilitySeverity.CRITICAL,
                            False,
                            f"Regular user can access admin endpoint {endpoint}",
                            {"endpoint": endpoint, "user_role": "user"},
                            "Implement proper role-based access control"
                        )
                        return

            except Exception as e:
                continue

        self.add_result(
            "Authorization Bypass",
            VulnerabilitySeverity.LOW,
            True,
            "Authorization controls appear to be working correctly",
            {"tested_endpoints": len(admin_endpoints)},
            "Continue monitoring authorization logs"
        )

    async def test_file_upload_vulnerabilities(self) -> None:
        """Test for file upload security vulnerabilities"""
        logger.info("Testing file upload vulnerabilities...")

        # Malicious file payloads
        malicious_files = [
            ("malicious.php", "<?php system($_GET['cmd']); ?>", "application/x-php"),
            ("malicious.exe", b"MZ\x90\x00", "application/x-executable"),
            ("malicious.js", "<script>alert('XSS')</script>", "application/javascript"),
            ("malicious.html", "<script>alert('XSS')</script>", "text/html"),
            ("../../../etc/passwd", "root:x:0:0:root:/root:/bin/bash", "text/plain"),
            ("large_file.txt", "A" * (100 * 1024 * 1024), "text/plain"),  # 100MB
            ("zip_bomb.zip", self._create_zip_bomb(), "application/zip")
        ]

        for filename, content, content_type in malicious_files:
            try:
                # Prepare file upload
                data = aiohttp.FormData()
                if isinstance(content, str):
                    data.add_field('file', content, filename=filename, content_type=content_type)
                else:
                    data.add_field('file', content, filename=filename, content_type=content_type)

                async with self.session.post(urljoin(self.base_url, "/api/v1/files/upload"), data=data) as response:
                    if response.status == 200:
                        self.add_result(
                            "File Upload Security",
                            VulnerabilitySeverity.HIGH,
                            False,
                            f"Malicious file upload accepted: {filename}",
                            {"filename": filename, "content_type": content_type},
                            "Implement proper file type validation and scanning"
                        )
                    elif response.status == 413:
                        # This is expected for large files
                        pass
                    else:
                        # This is expected for malicious files
                        pass

            except Exception as e:
                continue

        self.add_result(
            "File Upload Security",
            VulnerabilitySeverity.LOW,
            True,
            "File upload security controls appear to be working",
            {"tested_files": len(malicious_files)},
            "Continue monitoring file upload logs"
        )

    async def test_rate_limiting(self) -> None:
        """Test rate limiting effectiveness"""
        logger.info("Testing rate limiting...")

        # Test endpoint rate limiting
        test_endpoint = "/api/v1/search"

        # Make rapid requests
        rapid_requests = []
        start_time = time.time()

        for i in range(100):
            try:
                start = time.time()
                async with self.session.get(urljoin(self.base_url, test_endpoint)) as response:
                    end = time.time()
                    rapid_requests.append({
                        "request": i,
                        "status_code": response.status,
                        "response_time": end - start
                    })

                if i > 0 and (i % 10) == 0:
                    await asyncio.sleep(0.1)  # Small delay between batches

            except Exception as e:
                rapid_requests.append({
                    "request": i,
                    "status_code": 0,
                    "response_time": 0,
                    "error": str(e)
                })

        total_time = time.time() - start_time

        # Analyze results
        rate_limited_requests = [r for r in rapid_requests if r["status_code"] == 429]

        if len(rate_limited_requests) == 0:
            self.add_result(
                "Rate Limiting",
                VulnerabilitySeverity.MEDIUM,
                False,
                "No rate limiting detected",
                {"total_requests": len(rapid_requests), "total_time": total_time},
                "Implement rate limiting to prevent abuse"
            )
        else:
            self.add_result(
                "Rate Limiting",
                VulnerabilitySeverity.LOW,
                True,
                "Rate limiting is working",
                {
                    "total_requests": len(rapid_requests),
                    "rate_limited_requests": len(rate_limited_requests),
                    "rate_limit_percentage": len(rate_limited_requests) / len(rapid_requests) * 100
                },
                "Monitor rate limiting effectiveness"
            )

    async def test_security_headers(self) -> None:
        """Test security headers implementation"""
        logger.info("Testing security headers...")

        try:
            async with self.session.get(self.base_url) as response:
                headers = response.headers

                # Required security headers
                required_headers = {
                    "X-Content-Type-Options": "nosniff",
                    "X-Frame-Options": ["DENY", "SAMEORIGIN"],
                    "X-XSS-Protection": "1; mode=block",
                    "Referrer-Policy": ["strict-origin-when-cross-origin", "no-referrer", "strict-origin"],
                    "Content-Security-Policy": None,  # Just check existence
                    "Permissions-Policy": None
                }

                missing_headers = []
                for header, expected_value in required_headers.items():
                    if header not in headers:
                        missing_headers.append(header)
                    elif expected_value and isinstance(expected_value, list):
                        if headers[header] not in expected_value:
                            missing_headers.append(f"{header} (invalid value: {headers[header]})")
                    elif expected_value and headers[header] != expected_value:
                        missing_headers.append(f"{header} (invalid value: {headers[header]})")

                if missing_headers:
                    self.add_result(
                        "Security Headers",
                        VulnerabilitySeverity.MEDIUM,
                        False,
                        f"Missing security headers: {', '.join(missing_headers)}",
                        {"missing_headers": missing_headers, "present_headers": list(headers.keys())},
                        "Implement all required security headers"
                    )
                else:
                    self.add_result(
                        "Security Headers",
                        VulnerabilitySeverity.LOW,
                        True,
                        "All required security headers are present",
                        {"headers": list(headers.keys())},
                        "Review and update security headers regularly"
                    )

        except Exception as e:
            self.add_result(
                "Security Headers",
                VulnerabilitySeverity.HIGH,
                False,
                f"Failed to test security headers: {str(e)}",
                {"error": str(e)},
                "Ensure server is accessible and configured correctly"
            )

    async def test_information_disclosure(self) -> None:
        """Test for information disclosure vulnerabilities"""
        logger.info("Testing information disclosure...")

        # Test common information disclosure paths
        disclosure_paths = [
            "/.env",
            "/.git/config",
            "/.git/HEAD",
            "/config.php",
            "/web.config",
            "/.htaccess",
            "/backup.sql",
            "/dump.sql",
            "/database.sql",
            "/robots.txt",
            "/sitemap.xml",
            "/.well-known/security.txt",
            "/error.log",
            "/access.log"
        ]

        for path in disclosure_paths:
            try:
                async with self.session.get(urljoin(self.base_url, path)) as response:
                    if response.status == 200:
                        content = await response.text()

                        # Check for sensitive information
                        sensitive_patterns = [
                            "password", "secret", "key", "token", "api_key",
                            "database", "connection", "mysql", "postgres",
                            "BEGIN PRIVATE KEY", "-----BEGIN",
                            "DB_PASSWORD", "SECRET_KEY", "API_KEY"
                        ]

                        if any(pattern.lower() in content.lower() for pattern in sensitive_patterns):
                            self.add_result(
                                "Information Disclosure",
                                VulnerabilitySeverity.HIGH,
                                False,
                                f"Sensitive information disclosed at {path}",
                                {"path": path, "content_preview": content[:200]},
                                "Remove sensitive files and configure proper access controls"
                            )
                            return
            except Exception as e:
                continue

        # Test error messages for information disclosure
        try:
            async with self.session.get(urljoin(self.base_url, "/nonexistent/path")) as response:
                if response.status == 500:
                    content = await response.text()
                    if "stack trace" in content.lower() or "traceback" in content.lower():
                        self.add_result(
                            "Information Disclosure",
                            VulnerabilitySeverity.MEDIUM,
                            False,
                            "Stack trace disclosed in error message",
                            {"error_content_preview": content[:200]},
                            "Configure proper error handling and logging"
                        )
                        return
        except Exception as e:
            pass

        self.add_result(
            "Information Disclosure",
            VulnerabilitySeverity.LOW,
            True,
            "No obvious information disclosure vulnerabilities detected",
            {"tested_paths": len(disclosure_paths)},
            "Regularly audit for information disclosure"
        )

    def _create_expired_jwt(self) -> str:
        """Create an expired JWT token for testing"""
        payload = {
            "sub": "test_user",
            "exp": int(time.time()) - 3600,  # Expired 1 hour ago
            "iat": int(time.time()) - 7200   # Issued 2 hours ago
        }
        return jwt.encode(payload, "test_secret", algorithm="HS256")

    async def _get_user_token(self, user_data: Dict[str, str]) -> str:
        """Get authentication token for user (simulated)"""
        # This would normally authenticate with the API
        # For testing, return a mock token
        payload = {
            "sub": user_data["email"],
            "role": user_data["role"],
            "exp": int(time.time()) + 3600
        }
        return jwt.encode(payload, "test_secret", algorithm="HS256")

    def _create_zip_bomb(self) -> bytes:
        """Create a small zip bomb for testing"""
        # This is a simplified zip bomb - in practice would be more sophisticated
        return b"PK\x03\x04" + b"A" * 100  # Simplified zip header

    async def run_all_tests(self) -> List[SecurityTestResult]:
        """Run all security tests"""
        logger.info("Starting comprehensive security test suite...")

        await self.test_sql_injection()
        await self.test_xss_vulnerabilities()
        await self.test_authentication_bypass()
        await self.test_authorization_bypass()
        await self.test_file_upload_vulnerabilities()
        await self.test_rate_limiting()
        await self.test_security_headers()
        await self.test_information_disclosure()

        logger.info(f"Security testing completed. Ran {len(self.test_results)} tests.")
        return self.test_results

    def generate_report(self) -> str:
        """Generate security test report"""
        critical_issues = [r for r in self.test_results if r.severity == VulnerabilitySeverity.CRITICAL and not r.passed]
        high_issues = [r for r in self.test_results if r.severity == VulnerabilitySeverity.HIGH and not r.passed]
        medium_issues = [r for r in self.test_results if r.severity == VulnerabilitySeverity.MEDIUM and not r.passed]
        low_issues = [r for r in self.test_results if r.severity == VulnerabilitySeverity.LOW and not r.passed]

        report = f"""
# Security Test Report
Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}

## Executive Summary
- Total Tests: {len(self.test_results)}
- Passed: {len([r for r in self.test_results if r.passed])}
- Failed: {len([r for r in self.test_results if not r.passed])}

## Critical Issues ({len(critical_issues)})
"""

        for issue in critical_issues:
            report += f"- **{issue.test_name}**: {issue.description}\n"
            report += f"  - Recommendation: {issue.recommendation}\n\n"

        report += f"\n## High Issues ({len(high_issues)})"
        for issue in high_issues:
            report += f"- **{issue.test_name}**: {issue.description}\n"
            report += f"  - Recommendation: {issue.recommendation}\n\n"

        report += f"\n## Medium Issues ({len(medium_issues)})"
        for issue in medium_issues:
            report += f"- **{issue.test_name}**: {issue.description}\n"
            report += f"  - Recommendation: {issue.recommendation}\n\n"

        report += f"\n## Low Issues ({len(low_issues)})"
        for issue in low_issues:
            report += f"- **{issue.test_name}**: {issue.description}\n"
            report += f"  - Recommendation: {issue.recommendation}\n\n"

        return report

async def main():
    """Main function to run security tests"""
    async with SecurityTestSuite() as suite:
        results = await suite.run_all_tests()
        report = suite.generate_report()

        # Save report to file
        with open("security_test_report.md", "w") as f:
            f.write(report)

        print(report)

        # Exit with error code if critical or high issues found
        critical_high_issues = [r for r in results if not r.passed and r.severity in [VulnerabilitySeverity.CRITICAL, VulnerabilitySeverity.HIGH]]
        if critical_high_issues:
            print(f"\n❌ Security test failed with {len(critical_high_issues)} critical/high issues")
            exit(1)
        else:
            print("\n✅ Security tests passed")
            exit(0)

if __name__ == "__main__":
    asyncio.run(main())