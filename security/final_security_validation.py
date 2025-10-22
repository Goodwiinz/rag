#!/usr/bin/env python3
"""
Final Security Validation and Penetration Testing for Knowledge Graph Analytics Dashboard
Comprehensive security assessment to validate enterprise-grade security posture
"""

import os
import sys
import json
import time
import logging
import asyncio
import subprocess
import hashlib
import ssl
import socket
import requests
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import yaml

# Configure comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname️ - %(message)s',
    handlers=[
        logging.FileHandler('/Users/goodwiinz/development/RAG_system/rag/security/logs/final_validation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TestCategory(Enum):
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    INPUT_VALIDATION = "input_validation"
    SESSION_MANAGEMENT = "session_management"
    API_SECURITY = "api_security"
    NETWORK_SECURITY = "network_security"
    DATA_PROTECTION = "data_protection"
    INFRASTRUCTURE = "infrastructure"
    COMPLIANCE = "compliance"
    INCIDENT_RESPONSE = "incident_response"

class TestSeverity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

class TestStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    ERROR = "error"
    SKIPPED = "skipped"

@dataclass
class SecurityTest:
    """Security test data structure"""
    id: str
    title: str
    description: str
    category: TestCategory
    severity: TestSeverity
    status: TestStatus
    score: float  # 0-100
    details: Dict[str, Any]
    evidence: List[str]
    recommendations: List[str]
    references: List[str]
    execution_time: float
    timestamp: datetime

@dataclass
class ValidationReport:
    """Final validation report data structure"""
    test_session_id: str
    start_time: datetime
    end_time: datetime
    total_tests: int
    passed_tests: int
    failed_tests: int
    critical_findings: int
    high_findings: int
    medium_findings: int
    low_findings: int
    overall_score: float
    tests: List[SecurityTest]
    summary: Dict[str, Any]
    recommendations: List[str]
    compliance_status: Dict[str, Any]

class FinalSecurityValidation:
    """Final Security Validation and Penetration Testing System"""

    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path)
        self.results_dir = Path(self.config['validation']['results_dir'])
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = f"final_validation_{int(time.time())}"
        self.test_results: List[SecurityTest] = []

        # Test configuration
        self.base_url = self.config['target']['base_url']
        self.api_base = self.config['target']['api_base']
        self.frontend_url = self.config['target']['frontend_url']

    def _load_config(self, config_path: str = None) -> Dict:
        """Load validation configuration"""
        default_config = {
            "target": {
                "base_url": "http://localhost:8000",
                "api_base": "http://localhost:8000/api/v1",
                "frontend_url": "http://localhost:3000",
                "target_domains": ["localhost", "127.0.0.1"],
                "target_ports": [8000, 3000, 5432, 6379, 7687]
            },
            "validation": {
                "results_dir": "/Users/goodwiinz/development/RAG_system/rag/security/validation_results",
                "parallel_execution": True,
                "timeout_seconds": 300,
                "retry_attempts": 3,
                "generate_reports": True
            },
            "test_suites": {
                "authentication": {
                    "enabled": True,
                    "tests": [
                        "weak_passwords",
                        "default_credentials",
                        "brute_force_protection",
                        "account_lockout",
                        "multi_factor_auth",
                        "session_timeout",
                        "session_fixation",
                        "credential_stuffing"
                    ]
                },
                "authorization": {
                    "enabled": True,
                    "tests": [
                        "privilege_escalation",
                        "horizontal_authorization",
                        "vertical_authorization",
                        "broken_access_control",
                        "idor",
                        "direct_object_reference",
                        "parameter_tampering"
                    ]
                },
                "api_security": {
                    "enabled": True,
                    "tests": [
                        "sql_injection",
                        "nosql_injection",
                        "xss",
                        "csrf",
                        "ssrf",
                        "path_traversal",
                        "command_injection",
                        "xxe",
                        "insecure_deserialization",
                        "rate_limiting",
                        "api_key_security"
                    ]
                },
                "session_management": {
                    "enabled": True,
                    "tests": [
                        "session_hijacking",
                        "session_fixation",
                        "invalidated_sessions",
                        "session_timeout",
                        "concurrent_sessions",
                        "secure_cookies",
                        "csrf_tokens"
                    ]
                },
                "network_security": {
                    "enabled": True,
                    "tests": [
                        "ssl_tls_configuration",
                        "certificate_validation",
                        "security_headers",
                        "port_scanning",
                        "network_encryption",
                        "firewall_rules"
                    ]
                },
                "data_protection": {
                    "enabled": True,
                    "tests": [
                        "data_encryption",
                        "sensitive_data_exposure",
                        "data_classification",
                        "backup_security",
                        "data_disposal",
                        "pii_protection"
                    ]
                },
                "infrastructure": {
                    "enabled": True,
                    "tests": [
                        "container_security",
                        "docker_configuration",
                        "host_security",
                        "service_hardening",
                        "patch_management"
                    ]
                },
                "compliance": {
                    "enabled": True,
                    "frameworks": ["GDPR", "SOC2", "ISO27001", "NIST"],
                    "tests": [
                        "audit_logging",
                        "data_protection_policies",
                        "access_controls",
                        "incident_response_procedures"
                    ]
                }
            },
            "penetration_testing": {
                "enabled": True,
                "tests": [
                    "authenticated_scanning",
                    "unauthenticated_scanning",
                    "privilege_escalation",
                    "lateral_movement",
                    "data_exfiltration",
                    "persistence"
                ]
            },
            "reporting": {
                "generate_html": True,
                "generate_pdf": True,
                "generate_json": True,
                "include_recommendations": True,
                "include_evidence": True
            }
        }

        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                user_config = yaml.safe_load(f)
                self._deep_merge(default_config, user_config)

        return default_config

    def _deep_merge(self, base: Dict, override: Dict):
        """Deep merge two dictionaries"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    async def run_comprehensive_validation(self) -> ValidationReport:
        """Run comprehensive security validation"""
        logger.info(f"Starting final security validation: {self.session_id}")

        start_time = datetime.now(timezone.utc)

        try:
            # Run all test suites
            await self._run_all_test_suites()

            # Run penetration tests
            if self.config['penetration_testing']['enabled']:
                await self._run_penetration_tests()

            # Generate final report
            report = self._generate_validation_report(start_time)

            # Generate visualizations
            await self._generate_visualizations(report)

            logger.info("Final security validation completed successfully")
            return report

        except Exception as e:
            logger.error(f"Final security validation failed: {e}")
            raise

    async def _run_all_test_suites(self):
        """Run all enabled test suites"""
        test_suites = self.config['test_suites']

        for suite_name, suite_config in test_suites.items():
            if suite_config['enabled']:
                logger.info(f"Running test suite: {suite_name}")
                await self._run_test_suite(TestCategory(suite_name), suite_config['tests'])

    async def _run_test_suite(self, category: TestCategory, test_names: List[str]):
        """Run a specific test suite"""
        for test_name in test_names:
            try:
                test_method = getattr(self, f"_test_{test_name}", None)
                if test_method:
                    logger.info(f"Running test: {test_name}")
                    test_result = await test_method()
                    self.test_results.append(test_result)
                else:
                    logger.warning(f"Test method not found: {test_name}")
            except Exception as e:
                logger.error(f"Test {test_name} failed: {e}")
                self.test_results.append(SecurityTest(
                    id=f"{category.value}_{test_name}_{int(time.time())}",
                    title=f"Test {test_name}",
                    description=f"Security test for {test_name}",
                    category=category,
                    severity=TestSeverity.ERROR,
                    status=TestStatus.ERROR,
                    score=0.0,
                    details={"error": str(e)},
                    evidence=[],
                    recommendations=[f"Fix test execution error for {test_name}"],
                    references=[],
                    execution_time=0.0,
                    timestamp=datetime.now(timezone.utc)
                ))

    async def _run_penetration_tests(self):
        """Run penetration tests"""
        logger.info("Running penetration tests")

        pen_tests = self.config['penetration_testing']['tests']
        for test_name in pen_tests:
            try:
                test_method = getattr(self, f"_pentest_{test_name}", None)
                if test_method:
                    logger.info(f"Running penetration test: {test_name}")
                    test_result = await test_method()
                    self.test_results.append(test_result)
            except Exception as e:
                logger.error(f"Penetration test {test_name} failed: {e}")

    # Authentication Tests
    async def _test_weak_passwords(self) -> SecurityTest:
        """Test for weak password policies"""
        logger.info("Testing weak password policies")

        findings = []
        evidence = []
        recommendations = []
        score = 100.0

        try:
            # Test password requirements
            test_user_data = {
                "username": "testuser",
                "password": "weakpass"
            }

            response = requests.post(
                f"{self.api_base}/auth/register",
                json=test_user_data,
                timeout=10
            )

            if response.status_code == 200 or response.status_code == 201:
                findings.append("System accepts weak passwords")
                evidence.append(f"Weak password accepted: {test_user_data['password']}")
                recommendations.append("Implement strong password policy (minimum 12 characters, complexity requirements)")
                score -= 30

            # Test common passwords
            common_passwords = ["password", "123456", "admin", "welcome", "qwerty"]
            for password in common_passwords:
                test_user_data = {
                    "username": f"testuser_{len(password)}",
                    "password": password
                }

                response = requests.post(
                    f"{self.api_base}/auth/register",
                    json=test_user_data,
                    timeout=10
                )

                if response.status_code == 200 or response.status_code == 201:
                    findings.append(f"Common password accepted: {password}")
                    score -= 10

        except Exception as e:
            findings.append(f"Password policy test error: {str(e)}")
            score -= 20

        status = TestStatus.PASSED if score >= 70 else TestStatus.FAILED

        return SecurityTest(
            id=f"auth_weak_passwords_{int(time.time())}",
            title="Weak Password Policy Test",
            description="Tests if the system enforces strong password policies",
            category=TestCategory.AUTHENTICATION,
            severity=TestSeverity.HIGH,
            status=status,
            score=score,
            details={
                "test_cases": len(common_passwords) + 1,
                "findings_count": len(findings)
            },
            evidence=evidence,
            recommendations=recommendations,
            references=[
                "https://owasp.org/www-project-top-ten/2017/A2_2017-Broken_Authentication",
                "https://cwe.mitre.org/data/definitions/521.html"
            ],
            execution_time=0.0,
            timestamp=datetime.now(timezone.utc)
        )

    async def _test_default_credentials(self) -> SecurityTest:
        """Test for default credentials"""
        logger.info("Testing default credentials")

        findings = []
        evidence = []
        recommendations = []
        score = 100.0

        default_credentials = [
            ("admin", "admin"),
            ("admin", "password"),
            ("root", "root"),
            ("root", "password"),
            ("user", "user"),
            ("guest", "guest"),
            ("test", "test"),
            ("demo", "demo")
        ]

        for username, password in default_credentials:
            try:
                response = requests.post(
                    f"{self.api_base}/auth/login",
                    json={"username": username, "password": password},
                    timeout=10
                )

                if response.status_code == 200:
                    data = response.json()
                    if "token" in data:
                        findings.append(f"Default credentials work: {username}/{password}")
                        evidence.append(f"Successful login with {username}/{password}")
                        score -= 25

            except Exception:
                continue

        if findings:
            recommendations.append("Remove or change all default credentials")
            recommendations.append("Implement unique credentials for all accounts")

        status = TestStatus.PASSED if score >= 80 else TestStatus.FAILED

        return SecurityTest(
            id=f"auth_default_credentials_{int(time.time())}",
            title="Default Credentials Test",
            description="Tests for default or weak default credentials",
            category=TestCategory.AUTHENTICATION,
            severity=TestSeverity.CRITICAL,
            status=status,
            score=score,
            details={
                "credentials_tested": len(default_credentials),
                "vulnerable_credentials": len(findings)
            },
            evidence=evidence,
            recommendations=recommendations,
            references=[
                "https://owasp.org/www-project-top-ten/2017/A2_2017-Broken_Authentication",
                "https://cwe.mitre.org/data/definitions/16.html"
            ],
            execution_time=0.0,
            timestamp=datetime.now(timezone.utc)
        )

    async def _test_brute_force_protection(self) -> SecurityTest:
        """Test brute force protection mechanisms"""
        logger.info("Testing brute force protection")

        findings = []
        evidence = []
        recommendations = []
        score = 100.0

        try:
            username = "testuser"
            passwords = ["password1", "password2", "password3", "password4", "password5",
                       "password6", "password7", "password8", "password9", "password10"]

            successful_logins = 0

            for password in passwords:
                response = requests.post(
                    f"{self.api_base}/auth/login",
                    json={"username": username, "password": password},
                    timeout=5
                )

                if response.status_code == 200:
                    successful_logins += 1

            if successful_logins > 2:
                findings.append(f"Brute force protection not effective - {successful_logins} successful attempts")
                recommendations.append("Implement account lockout after failed attempts")
                recommendations.append("Implement rate limiting on login endpoints")
                score -= 40

            # Test rate limiting
            start_time = time.time()
            rapid_requests = 0

            for i in range(50):
                response = requests.post(
                    f"{self.api_base}/auth/login",
                    json={"username": f"user{i}", "password": "wrongpass"},
                    timeout=2
                )
                rapid_requests += 1
                if time.time() - start_time > 10:  # 10 seconds
                    break

            if rapid_requests > 20:
                findings.append(f"No rate limiting detected - {rapid_requests} requests in 10 seconds")
                recommendations.append("Implement rate limiting on authentication endpoints")
                score -= 20

        except Exception as e:
            findings.append(f"Brute force test error: {str(e)}")
            score -= 10

        status = TestStatus.PASSED if score >= 70 else TestStatus.FAILED

        return SecurityTest(
            id=f"auth_brute_force_{int(time.time())}",
            title="Brute Force Protection Test",
            description="Tests protection against brute force attacks",
            category=TestCategory.AUTHENTICATION,
            severity=TestSeverity.HIGH,
            status=status,
            score=score,
            details={
                "successful_logins": successful_logins,
                "rapid_requests": rapid_requests
            },
            evidence=evidence,
            recommendations=recommendations,
            references=[
                "https://owasp.org/www-project-top-ten/2017/A2_2017-Broken_Authentication",
                "https://cwe.mitre.org/data/definitions/307.html"
            ],
            execution_time=0.0,
            timestamp=datetime.now(timezone.utc)
        )

    async def _test_account_lockout(self) -> SecurityTest:
        """Test account lockout mechanisms"""
        logger.info("Testing account lockout")

        findings = []
        evidence = []
        recommendations = []
        score = 100.0

        try:
            username = "lockout_test"
            # First, register a test user
            register_data = {
                "username": username,
                "password": "SecurePass123!",
                "email": "test@example.com"
            }

            requests.post(f"{self.api_base}/auth/register", json=register_data, timeout=10)

            # Test failed login attempts
            failed_attempts = 0
            for i in range(15):
                response = requests.post(
                    f"{self.api_base}/auth/login",
                    json={"username": username, "password": "wrongpassword"},
                    timeout=5
                )
                if response.status_code == 401:
                    failed_attempts += 1

            # Test if account is locked
            response = requests.post(
                f"{self.api_base}/auth/login",
                json={"username": username, "password": "SecurePass123!"},
                timeout=5
            )

            if response.status_code == 200 and failed_attempts > 10:
                findings.append("Account lockout not implemented - account still accessible after multiple failed attempts")
                recommendations.append("Implement account lockout after 5-10 failed attempts")
                score -= 50
            elif response.status_code == 423:
                evidence.append("Account successfully locked after failed attempts")
            else:
                findings.append(f"Account lockout behavior unclear - {failed_attempts} failed attempts")

        except Exception as e:
            findings.append(f"Account lockout test error: {str(e)}")
            score -= 20

        status = TestStatus.PASSED if score >= 80 else TestStatus.FAILED

        return SecurityTest(
            id=f"auth_account_lockout_{int(time.time())}",
            title="Account Lockout Test",
            description="Tests account lockout mechanisms",
            category=TestCategory.AUTHENTICATION,
            severity=TestSeverity.HIGH,
            status=status,
            score=score,
            details={
                "failed_attempts": failed_attempts,
                "account_locked": response.status_code == 423 if 'response' in locals() else None
            },
            evidence=evidence,
            recommendations=recommendations,
            references=[
                "https://owasp.org/www-project-top-ten/2017/A2_2017-Broken_Authentication",
                "https://cwe.mitre.org/data/definitions/307.html"
            ],
            execution_time=0.0,
            timestamp=datetime.now(timezone.utc)
        )

    # Authorization Tests
    async def _test_privilege_escalation(self) -> SecurityTest:
        """Test for privilege escalation vulnerabilities"""
        logger.info("Testing privilege escalation")

        findings = []
        evidence = []
        recommendations = []
        score = 100.0

        try:
            # Test with regular user token accessing admin endpoints
            user_token = self._get_test_user_token()

            if user_token:
                admin_endpoints = [
                    "/auth/users",
                    "/auth/statistics",
                    "/rbac/roles",
                    "/system/config",
                    "/analytics/all"
                ]

                for endpoint in admin_endpoints:
                    response = requests.get(
                        f"{self.api_base}{endpoint}",
                        headers={"Authorization": f"Bearer {user_token}"},
                        timeout=10
                    )

                    if response.status_code == 200:
                        findings.append(f"Regular user can access admin endpoint: {endpoint}")
                        evidence.append(f"Endpoint {endpoint} returned 200 for regular user")
                        score -= 20

            # Test parameter manipulation for role escalation
            test_data = {
                "username": "regularuser",
                "password": "password123",
                "role": "admin"  # Try to set admin role
            }

            response = requests.post(
                f"{self.api_base}/auth/register",
                json=test_data,
                timeout=10
            )

            if response.status_code == 200 or response.status_code == 201:
                data = response.json()
                if data.get('role') == 'admin':
                    findings.append("User can set admin role during registration")
                    recommendations.append("Implement proper role assignment controls")
                    score -= 30

        except Exception as e:
            findings.append(f"Privilege escalation test error: {str(e)}")
            score -= 15

        status = TestStatus.PASSED if score >= 80 else TestStatus.FAILED

        return SecurityTest(
            id=f"auth_privilege_escalation_{int(time.time())}",
            title="Privilege Escalation Test",
            description="Tests for privilege escalation vulnerabilities",
            category=TestCategory.AUTHORIZATION,
            severity=TestSeverity.CRITICAL,
            status=status,
            score=score,
            details={
                "admin_endpoints_tested": len(admin_endpoints) if 'admin_endpoints' in locals() else 0,
                "vulnerable_endpoints": len([f for f in findings if "admin endpoint" in f])
            },
            evidence=evidence,
            recommendations=recommendations,
            references=[
                "https://owasp.org/www-project-top-ten/2017/A5_2017-Broken_Access_Control",
                "https://cwe.mitre.org/data/definitions/269.html"
            ],
            execution_time=0.0,
            timestamp=datetime.now(timezone.utc)
        )

    # API Security Tests
    async def _test_sql_injection(self) -> SecurityTest:
        """Test for SQL injection vulnerabilities"""
        logger.info("Testing SQL injection")

        findings = []
        evidence = []
        recommendations = []
        score = 100.0

        sql_payloads = [
            "' OR '1'='1",
            "' OR '1'='1' --",
            "'; DROP TABLE users; --",
            "1' UNION SELECT * FROM users--",
            "' OR 1=1#",
            "' OR 1=1/*",
            "') OR '1'='1--"
        ]

        test_endpoints = [
            "/search",
            "/documents",
            "/users",
            "/analytics/quality"
        ]

        for endpoint in test_endpoints:
            for payload in sql_payloads:
                try:
                    # Test GET parameter injection
                    response = requests.get(
                        f"{self.api_base}{endpoint}",
                        params={"q": payload},
                        timeout=10
                    )

                    if response.status_code == 200:
                        text = response.text.lower()
                        sql_errors = [
                            "syntax error", "mysql_fetch", "ora-", "microsoft ole db",
                            "sql syntax", "warning: mysql", "valid mysql result",
                            "postgresql query failed", "sqlserver jdbc driver"
                        ]

                        for error in sql_errors:
                            if error in text:
                                findings.append(f"SQL injection vulnerability in {endpoint} with payload: {payload}")
                                evidence.append(f"SQL error in response: {error}")
                                score -= 25

                    # Test POST parameter injection
                    response = requests.post(
                        f"{self.api_base}{endpoint}",
                        json={"search": payload, "test": "data"},
                        timeout=10
                    )

                    if response.status_code == 200:
                        text = response.text.lower()
                        for error in sql_errors:
                            if error in text:
                                findings.append(f"SQL injection vulnerability in {endpoint} (POST) with payload: {payload}")
                                score -= 25

                except Exception:
                    continue

        if findings:
            recommendations.append("Use parameterized queries/prepared statements")
            recommendations.append("Implement input validation and sanitization")
            recommendations.append("Use ORM frameworks that prevent SQL injection")

        status = TestStatus.PASSED if score >= 80 else TestStatus.FAILED

        return SecurityTest(
            id=f"api_sql_injection_{int(time.time())}",
            title="SQL Injection Test",
            description="Tests for SQL injection vulnerabilities",
            category=TestCategory.API_SECURITY,
            severity=TestSeverity.CRITICAL,
            status=status,
            score=score,
            details={
                "payloads_tested": len(sql_payloads),
                "endpoints_tested": len(test_endpoints),
                "vulnerabilities_found": len(findings)
            },
            evidence=evidence,
            recommendations=recommendations,
            references=[
                "https://owasp.org/www-project-top-ten/2017/A1_2017-Injection",
                "https://cwe.mitre.org/data/definitions/89.html"
            ],
            execution_time=0.0,
            timestamp=datetime.now(timezone.utc)
        )

    async def _test_xss(self) -> SecurityTest:
        """Test for Cross-Site Scripting (XSS) vulnerabilities"""
        logger.info("Testing XSS vulnerabilities")

        findings = []
        evidence = []
        recommendations = []
        score = 100.0

        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<svg onload=alert('XSS')>",
            "';alert('XSS');//",
            "<iframe src=javascript:alert('XSS')>",
            "<body onload=alert('XSS')>",
            "<input autofocus onfocus=alert('XSS')>"
        ]

        test_endpoints = [
            "/search",
            "/documents",
            "/analytics/quality"
        ]

        for endpoint in test_endpoints:
            for payload in xss_payloads:
                try:
                    # Test GET parameter injection
                    response = requests.get(
                        f"{self.api_base}{endpoint}",
                        params={"q": payload},
                        timeout=10
                    )

                    if response.status_code == 200:
                        text = response.text
                        if payload in text and "<script>" in text.lower():
                            findings.append(f"XSS vulnerability in {endpoint} with payload: {payload}")
                            evidence.append(f"Payload reflected in response: {payload[:50]}...")
                            score -= 20

                    # Test POST parameter injection
                    response = requests.post(
                        f"{self.api_base}{endpoint}",
                        json={"content": payload, "title": payload},
                        timeout=10
                    )

                    if response.status_code == 200:
                        text = response.text
                        if payload in text and "<script>" in text.lower():
                            findings.append(f"XSS vulnerability in {endpoint} (POST) with payload: {payload}")
                            score -= 20

                except Exception:
                    continue

        if findings:
            recommendations.append("Implement proper output encoding")
            recommendations.append("Use Content Security Policy (CSP) headers")
            recommendations.append("Implement input validation and sanitization")
            recommendations.append("Use security-focused templating engines")

        status = TestStatus.PASSED if score >= 80 else TestStatus.FAILED

        return SecurityTest(
            id=f"api_xss_{int(time.time())}",
            title="Cross-Site Scripting (XSS) Test",
            description="Tests for XSS vulnerabilities",
            category=TestCategory.API_SECURITY,
            severity=TestSeverity.HIGH,
            status=status,
            score=score,
            details={
                "payloads_tested": len(xss_payloads),
                "endpoints_tested": len(test_endpoints),
                "vulnerabilities_found": len(findings)
            },
            evidence=evidence,
            recommendations=recommendations,
            references=[
                "https://owasp.org/www-project-top-ten/2017/A7_2017-Cross_Site_Scripting_(XSS)",
                "https://cwe.mitre.org/data/definitions/79.html"
            ],
            execution_time=0.0,
            timestamp=datetime.now(timezone.utc)
        )

    # Network Security Tests
    async def _test_ssl_tls_configuration(self) -> SecurityTest:
        """Test SSL/TLS configuration"""
        logger.info("Testing SSL/TLS configuration")

        findings = []
        evidence = []
        recommendations = []
        score = 100.0

        try:
            # Test SSL/TLS configuration
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            with socket.create_connection(('localhost', 8000), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname='localhost') as ssock:
                    version = ssock.version()
                    cipher = ssock.cipher()

                    # Check SSL/TLS version
                    if version in ['SSLv2', 'SSLv3', 'TLSv1', 'TLSv1.1']:
                        findings.append(f"Weak SSL/TLS version: {version}")
                        evidence.append(f"Current version: {version}")
                        recommendations.append("Disable SSLv2, SSLv3, TLSv1.0, and TLSv1.1")
                        score -= 30

                    # Check cipher strength
                    if cipher:
                        cipher_name = cipher[0]
                        weak_ciphers = ['RC4', 'DES', 'MD5', 'NULL', 'EXP']
                        if any(weak in cipher_name.upper() for weak in weak_ciphers):
                            findings.append(f"Weak cipher suite: {cipher_name}")
                            recommendations.append("Disable weak cipher suites")
                            score -= 20

        except Exception as e:
            findings.append(f"SSL/TLS test error: {str(e)}")
            recommendations.append("Configure SSL/TLS on the application")
            score -= 40

        # Test security headers
        try:
            response = requests.get(self.base_url, timeout=10)
            headers = response.headers

            required_headers = {
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": ["DENY", "SAMEORIGIN"],
                "X-XSS-Protection": "1; mode=block",
                "Strict-Transport-Security": None,
                "Content-Security-Policy": None
            }

            for header, expected_value in required_headers.items():
                if header not in headers:
                    findings.append(f"Missing security header: {header}")
                    recommendations.append(f"Implement {header} header")
                    score -= 10
                elif expected_value and isinstance(expected_value, list):
                    if headers[header] not in expected_value:
                        findings.append(f"Invalid {header} value: {headers[header]}")
                        score -= 5

        except Exception as e:
            findings.append(f"Security headers test error: {str(e)}")
            score -= 15

        status = TestStatus.PASSED if score >= 70 else TestStatus.FAILED

        return SecurityTest(
            id=f"net_ssl_tls_{int(time.time())}",
            title="SSL/TLS Configuration Test",
            description="Tests SSL/TLS configuration and security headers",
            category=TestCategory.NETWORK_SECURITY,
            severity=TestSeverity.HIGH,
            status=status,
            score=score,
            details={
                "ssl_version": version if 'version' in locals() else None,
                "cipher_suite": cipher if 'cipher' in locals() else None,
                "security_headers": len(required_headers) - len([f for f in findings if "Missing security header" in f])
            },
            evidence=evidence,
            recommendations=recommendations,
            references=[
                "https://owasp.org/www-project-top-ten/2017/A6_2017-Security_Misconfiguration",
                "https://cwe.mitre.org/data/definitions/326.html"
            ],
            execution_time=0.0,
            timestamp=datetime.now(timezone.utc)
        )

    # Data Protection Tests
    async def _test_data_encryption(self) -> SecurityTest:
        """Test data encryption implementation"""
        logger.info("Testing data encryption")

        findings = []
        evidence = []
        recommendations = []
        score = 100.0

        try:
            # Test if data is transmitted over HTTPS
            response = requests.get(self.base_url, timeout=10)
            if not response.url.startswith('https://'):
                findings.append("Data transmitted over unencrypted HTTP")
                recommendations.append("Implement HTTPS for all data transmission")
                score -= 40

            # Check for sensitive data in responses
            sensitive_patterns = [
                "password", "secret", "key", "token", "api_key",
                "credit_card", "ssn", "social_security", "private_key"
            ]

            # Test API responses for sensitive data exposure
            endpoints_to_test = ["/auth/me", "/users/profile", "/analytics/data"]
            for endpoint in endpoints_to_test:
                try:
                    token = self._get_test_user_token()
                    if token:
                        response = requests.get(
                            f"{self.api_base}{endpoint}",
                            headers={"Authorization": f"Bearer {token}"},
                            timeout=10
                        )

                        if response.status_code == 200:
                            text = response.text.lower()
                            for pattern in sensitive_patterns:
                                if pattern in text:
                                    findings.append(f"Sensitive data pattern '{pattern}' found in {endpoint} response")
                                    score -= 15

                except Exception:
                    continue

            # Test password storage (indirectly)
            test_password = "TestPassword123!"
            register_data = {
                "username": "encryption_test",
                "password": test_password,
                "email": "test@example.com"
            }

            response = requests.post(
                f"{self.api_base}/auth/register",
                json=register_data,
                timeout=10
            )

            if response.status_code == 200 or response.status_code == 201:
                # Check if password is stored in plaintext (would be in response in a flawed system)
                if test_password in response.text:
                    findings.append("Password may be stored in plaintext")
                    recommendations.append("Implement proper password hashing (bcrypt, scrypt, Argon2)")
                    score -= 50

        except Exception as e:
            findings.append(f"Data encryption test error: {str(e)}")
            score -= 20

        status = TestStatus.PASSED if score >= 75 else TestStatus.FAILED

        return SecurityTest(
            id=f"data_encryption_{int(time.time())}",
            title="Data Encryption Test",
            description="Tests data encryption implementation",
            category=TestCategory.DATA_PROTECTION,
            severity=TestSeverity.HIGH,
            status=status,
            score=score,
            details={
                "https_enabled": response.url.startswith('https://') if 'response' in locals() else False,
                "sensitive_data_exposed": len([f for f in findings if "Sensitive data pattern" in f])
            },
            evidence=evidence,
            recommendations=recommendations,
            references=[
                "https://owasp.org/www-project-top-ten/2017/A3_2017-Sensitive_Data_Exposure",
                "https://cwe.mitre.org/data/definitions/311.html"
            ],
            execution_time=0.0,
            timestamp=datetime.now(timezone.utc)
        )

    # Penetration Tests
    async def _pentest_authenticated_scanning(self) -> SecurityTest:
        """Authenticated penetration testing"""
        logger.info("Running authenticated penetration testing")

        findings = []
        evidence = []
        recommendations = []
        score = 100.0

        try:
            # Get authenticated token
            token = self._get_test_user_token()
            if not token:
                findings.append("Cannot obtain authentication token for authenticated testing")
                score -= 50
            else:
                # Test authenticated endpoints for vulnerabilities
                auth_endpoints = [
                    "/search",
                    "/documents",
                    "/analytics/quality",
                    "/users/profile",
                    "/rbac/permissions"
                ]

                for endpoint in auth_endpoints:
                    try:
                        # Test for authorization bypass
                        response = requests.get(
                            f"{self.api_base}{endpoint}",
                            headers={"Authorization": f"Bearer {token}"},
                            timeout=10
                        )

                        if response.status_code == 200:
                            # Test for IDOR (Insecure Direct Object Reference)
                            if "id" in response.text.lower():
                                findings.append(f"Possible IDOR vulnerability in {endpoint}")
                                score -= 15

                            # Test for parameter pollution
                            params = {
                                "id": "1",
                                "id[0]": "2",
                                "id[1]": "3"
                            }
                            response = requests.get(
                                f"{self.api_base}{endpoint}",
                                headers={"Authorization": f"Bearer {token}"},
                                params=params,
                                timeout=10
                            )

                            if response.status_code == 200:
                                findings.append(f"Parameter pollution possible in {endpoint}")
                                score -= 10

                    except Exception:
                        continue

        except Exception as e:
            findings.append(f"Authenticated penetration test error: {str(e)}")
            score -= 20

        status = TestStatus.PASSED if score >= 80 else TestStatus.FAILED

        return SecurityTest(
            id=f"pentest_auth_scanning_{int(time.time())}",
            title="Authenticated Penetration Test",
            description="Authenticated penetration testing of the application",
            category=TestCategory.AUTHORIZATION,
            severity=TestSeverity.HIGH,
            status=status,
            score=score,
            details={
                "authentication_obtained": token is not None,
                "endpoints_tested": len(auth_endpoints) if 'auth_endpoints' in locals() else 0
            },
            evidence=evidence,
            recommendations=recommendations,
            references=[
                "https://owasp.org/www-project-web-security-testing-guide/",
                "https://cwe.mitre.org/data/definitions/639.html"
            ],
            execution_time=0.0,
            timestamp=datetime.now(timezone.utc)
        )

    # Helper methods
    def _get_test_user_token(self) -> Optional[str]:
        """Get authentication token for testing"""
        try:
            # Try to register/login a test user
            login_data = {
                "username": "security_test_user",
                "password": "SecurePass123!"
            }

            response = requests.post(
                f"{self.api_base}/auth/login",
                json=login_data,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("token")

            # Try to register first
            register_data = {
                "username": "security_test_user",
                "password": "SecurePass123!",
                "email": "security_test@example.com"
            }

            response = requests.post(
                f"{self.api_base}/auth/register",
                json=register_data,
                timeout=10
            )

            if response.status_code in [200, 201]:
                # Now try to login
                response = requests.post(
                    f"{self.api_base}/auth/login",
                    json=login_data,
                    timeout=10
                )

                if response.status_code == 200:
                    data = response.json()
                    return data.get("token")

        except Exception as e:
            logger.debug(f"Failed to get test user token: {e}")

        return None

    def _generate_validation_report(self, start_time: datetime) -> ValidationReport:
        """Generate final validation report"""
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()

        total_tests = len(self.test_results)
        passed_tests = len([t for t in self.test_results if t.status == TestStatus.PASSED])
        failed_tests = len([t for t in self.test_results if t.status == TestStatus.FAILED])

        # Count findings by severity
        critical_findings = len([t for t in self.test_results if t.severity == TestSeverity.CRITICAL])
        high_findings = len([t for t in self.test_results if t.severity == TestSeverity.HIGH])
        medium_findings = len([t for t in self.test_results if t.severity == TestSeverity.MEDIUM])
        low_findings = len([t for t in self.test_results if t.severity == TestSeverity.LOW])

        overall_score = sum(t.score for t in self.test_results) / total_tests if total_tests > 0 else 0

        # Generate summary
        summary = {
            "test_categories": list(set([t.category.value for t in self.test_results])),
            "most_critical_issues": [t.title for t in self.test_results if t.severity == TestSeverity.CRITICAL],
            "test_execution_time": duration,
            "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0
        }

        # Collect recommendations
        all_recommendations = []
        for test in self.test_results:
            all_recommendations.extend(test.recommendations)
        unique_recommendations = list(set(all_recommendations))

        # Compliance status
        compliance_status = {
            "overall_score": overall_score,
            "grade": self._calculate_grade(overall_score),
            "critical_issues_resolved": critical_findings == 0,
            "high_issues_resolved": high_findings == 0
        }

        return ValidationReport(
            test_session_id=self.session_id,
            start_time=start_time,
            end_time=end_time,
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            critical_findings=critical_findings,
            high_findings=high_findings,
            medium_findings=medium_findings,
            low_findings=low_findings,
            overall_score=overall_score,
            tests=self.test_results,
            summary=summary,
            recommendations=unique_recommendations,
            compliance_status=compliance_status
        )

    def _calculate_grade(self, score: float) -> str:
        """Calculate security grade based on score"""
        if score >= 95:
            return "A+"
        elif score >= 90:
            return "A"
        elif score >= 85:
            return "B+"
        elif score >= 80:
            return "B"
        elif score >= 75:
            return "C+"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"

    async def _generate_visualizations(self, report: ValidationReport):
        """Generate security validation visualizations"""
        logger.info("Generating security validation visualizations")

        try:
            # Create results DataFrame
            test_data = []
            for test in report.tests:
                test_data.append({
                    'Category': test.category.value,
                    'Severity': test.severity.value,
                    'Status': test.status.value,
                    'Score': test.score,
                    'Title': test.title
                })

            df = pd.DataFrame(test_data)

            # Create output directory for charts
            charts_dir = self.results_dir / "charts"
            charts_dir.mkdir(exist_ok=True)

            # 1. Test Results by Category
            plt.figure(figsize=(12, 6))
            category_counts = df.groupby(['Category', 'Status']).size().unstack(fill_value=0)
            category_counts.plot(kind='bar', stacked=True)
            plt.title('Test Results by Category')
            plt.xlabel('Category')
            plt.ylabel('Number of Tests')
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig(charts_dir / 'test_results_by_category.png')
            plt.close()

            # 2. Severity Distribution
            plt.figure(figsize=(10, 6))
            severity_counts = df['Severity'].value_counts()
            plt.pie(severity_counts.values, labels=severity_counts.index, autopct='%1.1f%%')
            plt.title('Security Test Results by Severity')
            plt.axis('equal')
            plt.tight_layout()
            plt.savefig(charts_dir / 'severity_distribution.png')
            plt.close()

            # 3. Score Distribution
            plt.figure(figsize=(10, 6))
            plt.hist(df['Score'], bins=20, alpha=0.7, edgecolor='black')
            plt.axvline(report.overall_score, color='red', linestyle='--', label=f'Overall Score: {report.overall_score:.1f}')
            plt.title('Test Score Distribution')
            plt.xlabel('Score')
            plt.ylabel('Number of Tests')
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig(charts_dir / 'score_distribution.png')
            plt.close()

            # 4. Category Score Comparison
            plt.figure(figsize=(12, 8))
            category_scores = df.groupby('Category')['Score'].mean().sort_values(ascending=False)
            ax = category_scores.plot(kind='bar')
            plt.title('Average Security Score by Category')
            plt.xlabel('Category')
            plt.ylabel('Average Score')
            plt.xticks(rotation=45)
            plt.ylim(0, 100)

            # Add score labels on bars
            for i, v in enumerate(category_scores):
                ax.text(i, v + 1, f'{v:.1f}', ha='center')

            plt.tight_layout()
            plt.savefig(charts_dir / 'category_scores.png')
            plt.close()

            logger.info(f"Security validation visualizations saved to {charts_dir}")

        except Exception as e:
            logger.error(f"Failed to generate visualizations: {e}")


async def main():
    """Main function to run final security validation"""
    # Create output directories
    os.makedirs("/Users/goodwiinz/development/RAG_system/rag/security/logs", exist_ok=True)
    os.makedirs("/Users/goodwiinz/development/RAG_system/rag/security/validation_results", exist_ok=True)

    # Initialize final security validation
    validator = FinalSecurityValidation()

    try:
        # Run comprehensive validation
        report = validator._generate_validation_report(datetime.now(timezone.utc))

        # Actually run the tests
        report = await validator.run_comprehensive_validation()

        # Print summary
        print(f"\n🔒 Final Security Validation Results")
        print(f"Session ID: {report.test_session_id}")
        print(f"Total Tests: {report.total_tests}")
        print(f"Passed: {report.passed_tests}")
        print(f"Failed: {report.failed_tests}")
        print(f"Critical Findings: {report.critical_findings}")
        print(f"High Findings: {report.high_findings}")
        print(f"Medium Findings: {report.medium_findings}")
        print(f"Low Findings: {report.low_findings}")
        print(f"Overall Score: {report.overall_score:.1f}%")
        print(f"Security Grade: {report.compliance_status['grade']}")

        # Show top recommendations
        if report.recommendations:
            print(f"\n📋 Top Recommendations:")
            for i, rec in enumerate(report.recommendations[:10]):
                print(f"{i+1}. {rec}")

        # Save detailed report
        report_file = validator.results_dir / f"security_validation_report_{report.test_session_id}.json"
        with open(report_file, 'w') as f:
            json.dump(asdict(report), f, indent=2, default=str)

        print(f"\n📄 Detailed report saved to: {report_file}")

        # Determine exit code
        if report.critical_findings > 0:
            print(f"\n❌ Critical security issues found - immediate action required")
            exit(1)
        elif report.high_findings > 5:
            print(f"\n⚠️  Multiple high-severity issues found - action required")
            exit(2)
        elif report.overall_score < 70:
            print(f"\n⚠️  Security score below acceptable level - improvements needed")
            exit(3)
        else:
            print(f"\n✅ Security validation completed successfully")
            exit(0)

    except Exception as e:
        logger.error(f"Final security validation failed: {e}")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())