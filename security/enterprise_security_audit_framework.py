#!/usr/bin/env python3
"""
Enterprise Security Audit Framework for Knowledge Graph Analytics Dashboard
Comprehensive security assessment and compliance validation system
"""

import asyncio
import aiohttp
import json
import time
import hashlib
import base64
import jwt
import ssl
import subprocess
import re
import os
import sys
import yaml
import csv
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import logging
import ipaddress
import xml.etree.ElementTree as ET
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
import requests
import packaging.version
import bandit
import safety
import semgrep

# Configure comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/goodwiinz/development/RAG_system/rag/security/logs/audit.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ComplianceFramework(Enum):
    GDPR = "gdpr"
    SOC2 = "soc2"
    HIPAA = "hipaa"
    ISO27001 = "iso27001"
    NIST = "nist"
    PCI_DSS = "pci_dss"

class VulnerabilitySeverity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

class AssetType(Enum):
    FRONTEND = "frontend"
    BACKEND = "backend"
    DATABASE = "database"
    INFRASTRUCTURE = "infrastructure"
    API = "api"
    WEBSOCKET = "websocket"
    FILESYSTEM = "filesystem"

@dataclass
class SecurityFinding:
    """Security finding data structure"""
    id: str
    title: str
    description: str
    severity: VulnerabilitySeverity
    asset_type: AssetType
    component: str
    vulnerability_type: str
    cwe_id: Optional[str] = None
    cvss_score: Optional[float] = None
    compliance_impact: Optional[List[ComplianceFramework]] = None
    remediation: str = ""
    evidence: Dict[str, Any] = None
    discovered_at: datetime = None
    false_positive: bool = False

@dataclass
class SecurityMetrics:
    """Security metrics for dashboard"""
    total_findings: int = 0
    critical_findings: int = 0
    high_findings: int = 0
    medium_findings: int = 0
    low_findings: int = 0
    info_findings: int = 0
    assets_scanned: int = 0
    compliance_score: float = 0.0
    risk_score: float = 0.0

class SecurityAuditFramework:
    """Enterprise Security Audit Framework"""

    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path)
        self.findings: List[SecurityFinding] = []
        self.metrics = SecurityMetrics()
        self.session = None
        self.scan_start_time = None
        self.scan_id = f"scan_{int(time.time())}"

        # Initialize security tools
        self.tools_config = self.config.get('tools', {})
        self.compliance_requirements = self.config.get('compliance', {})

    def _load_config(self, config_path: str = None) -> Dict:
        """Load security configuration"""
        default_config = {
            "target_system": {
                "base_url": "http://localhost:8000",
                "frontend_url": "http://localhost:3000",
                "api_endpoints": [
                    "/api/v1/auth",
                    "/api/v1/documents",
                    "/api/v1/search",
                    "/api/v1/analytics"
                ]
            },
            "scan_scope": {
                "web_application": True,
                "api_security": True,
                "infrastructure": True,
                "code_analysis": True,
                "dependency_scan": True,
                "compliance_check": True
            },
            "compliance": {
                "frameworks": ["GDPR", "SOC2", "ISO27001"],
                "requirements": {
                    "data_encryption": True,
                    "access_control": True,
                    "audit_logging": True,
                    "data_protection": True
                }
            },
            "tools": {
                "bandit": {"enabled": True, "confidence": "medium"},
                "safety": {"enabled": True},
                "semgrep": {"enabled": True, "config": "auto"},
                "ssl_check": {"enabled": True},
                "dependency_check": {"enabled": True}
            },
            "reporting": {
                "output_dir": "/Users/goodwiinz/development/RAG_system/rag/security/reports",
                "formats": ["json", "html", "pdf", "csv"],
                "include_evidence": True
            }
        }

        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                user_config = yaml.safe_load(f)
                default_config.update(user_config)

        return default_config

    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(ssl=False)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    def add_finding(self, finding: SecurityFinding):
        """Add security finding to results"""
        if not finding.discovered_at:
            finding.discovered_at = datetime.now(timezone.utc)

        # Check for duplicates
        duplicate = self._find_duplicate(finding)
        if duplicate:
            logger.debug(f"Duplicate finding skipped: {finding.title}")
            return

        self.findings.append(finding)
        self._update_metrics()

        logger.info(f"[{finding.severity.value.upper()}] {finding.title}: {finding.description}")

    def _find_duplicate(self, finding: SecurityFinding) -> Optional[SecurityFinding]:
        """Check for duplicate findings"""
        for existing in self.findings:
            if (existing.title == finding.title and
                existing.component == finding.component and
                existing.asset_type == finding.asset_type):
                return existing
        return None

    def _update_metrics(self):
        """Update security metrics"""
        self.metrics.total_findings = len(self.findings)
        self.metrics.critical_findings = len([f for f in self.findings if f.severity == VulnerabilitySeverity.CRITICAL])
        self.metrics.high_findings = len([f for f in self.findings if f.severity == VulnerabilitySeverity.HIGH])
        self.metrics.medium_findings = len([f for f in self.findings if f.severity == VulnerabilitySeverity.MEDIUM])
        self.metrics.low_findings = len([f for f in self.findings if f.severity == VulnerabilitySeverity.LOW])
        self.metrics.info_findings = len([f for f in self.findings if f.severity == VulnerabilitySeverity.INFO])

        # Calculate risk score (weighted by severity)
        risk_weights = {
            VulnerabilitySeverity.CRITICAL: 10,
            VulnerabilitySeverity.HIGH: 5,
            VulnerabilitySeverity.MEDIUM: 2,
            VulnerabilitySeverity.LOW: 1,
            VulnerabilitySeverity.INFO: 0.1
        }

        total_risk = sum(risk_weights[f.severity] for f in self.findings)
        max_possible_risk = len(self.findings) * 10  # Assuming all could be critical
        self.metrics.risk_score = (total_risk / max_possible_risk * 100) if max_possible_risk > 0 else 0

        # Calculate compliance score
        self._calculate_compliance_score()

    def _calculate_compliance_score(self):
        """Calculate compliance score based on findings"""
        if not self.findings:
            self.metrics.compliance_score = 100.0
            return

        # Penalize score based on severity
        penalties = {
            VulnerabilitySeverity.CRITICAL: 25,
            VulnerabilitySeverity.HIGH: 15,
            VulnerabilitySeverity.MEDIUM: 8,
            VulnerabilitySeverity.LOW: 3,
            VulnerabilitySeverity.INFO: 1
        }

        total_penalty = sum(penalties[f.severity] for f in self.findings)
        self.metrics.compliance_score = max(0, 100 - total_penalty)

    async def run_comprehensive_audit(self) -> SecurityMetrics:
        """Run comprehensive security audit"""
        self.scan_start_time = datetime.now(timezone.utc)
        logger.info(f"Starting comprehensive security audit: {self.scan_id}")

        try:
            # Web Application Security
            if self.config['scan_scope']['web_application']:
                await self._scan_web_application_security()

            # API Security
            if self.config['scan_scope']['api_security']:
                await self._scan_api_security()

            # Infrastructure Security
            if self.config['scan_scope']['infrastructure']:
                await self._scan_infrastructure_security()

            # Code Analysis
            if self.config['scan_scope']['code_analysis']:
                await self._analyze_source_code()

            # Dependency Security
            if self.config['scan_scope']['dependency_scan']:
                await self._scan_dependencies()

            # Compliance Check
            if self.config['scan_scope']['compliance_check']:
                await self._check_compliance()

            # Generate report
            await self._generate_reports()

            logger.info(f"Security audit completed. Found {len(self.findings)} findings.")
            return self.metrics

        except Exception as e:
            logger.error(f"Security audit failed: {e}")
            raise

    async def _scan_web_application_security(self):
        """Scan web application security"""
        logger.info("Scanning web application security...")

        # TLS/SSL Configuration
        await self._check_tls_configuration()

        # Security Headers
        await self._check_security_headers()

        # Authentication & Session Management
        await self._check_authentication()

        # Authorization & Access Control
        await self._check_authorization()

        # Input Validation
        await self._check_input_validation()

        # Cross-Site Scripting (XSS)
        await self._check_xss_protection()

        # Cross-Site Request Forgery (CSRF)
        await self._check_csrf_protection()

        # File Upload Security
        await self._check_file_upload_security()

        # Error Handling
        await self._check_error_handling()

    async def _scan_api_security(self):
        """Scan API security"""
        logger.info("Scanning API security...")

        # API Authentication
        await self._check_api_authentication()

        # API Authorization
        await self._check_api_authorization()

        # API Rate Limiting
        await self._check_api_rate_limiting()

        # API Input Validation
        await self._check_api_input_validation()

        # API Documentation Security
        await self._check_api_documentation_security()

        # WebSocket Security
        await self._check_websocket_security()

    async def _scan_infrastructure_security(self):
        """Scan infrastructure security"""
        logger.info("Scanning infrastructure security...")

        # Docker Security
        await self._check_docker_security()

        # Database Security
        await self._check_database_security()

        # Network Security
        await self._check_network_security()

        # Secrets Management
        await self._check_secrets_management()

        # Logging and Monitoring
        await self._check_logging_monitoring()

    async def _analyze_source_code(self):
        """Analyze source code for security vulnerabilities"""
        logger.info("Analyzing source code...")

        # Static Analysis with Bandit
        await self._run_bandit_scan()

        # Static Analysis with Semgrep
        await self._run_semgrep_scan()

        # Secrets Detection
        await self._detect_secrets_in_code()

        # Code Quality Security
        await self._check_code_quality_security()

    async def _scan_dependencies(self):
        """Scan dependencies for vulnerabilities"""
        logger.info("Scanning dependencies...")

        # Python Dependencies with Safety
        await self._run_safety_scan()

        # Node.js Dependencies
        await self._scan_nodejs_dependencies()

        # Outdated Packages
        await self._check_outdated_packages()

        # License Compliance
        await self._check_license_compliance()

    async def _check_compliance(self):
        """Check compliance requirements"""
        logger.info("Checking compliance requirements...")

        for framework in self.compliance_requirements.get('frameworks', []):
            try:
                compliance_enum = ComplianceFramework(framework.lower())
                await self._check_compliance_framework(compliance_enum)
            except ValueError:
                logger.warning(f"Unknown compliance framework: {framework}")

    async def _check_tls_configuration(self):
        """Check TLS/SSL configuration"""
        try:
            base_url = self.config['target_system']['base_url']
            parsed = urlparse(base_url)

            # SSL/TLS Configuration Check
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            with socket.create_connection((parsed.hostname, parsed.port or 443), timeout=10) as sock:
                with ssl_context.wrap_socket(sock, server_hostname=parsed.hostname) as ssock:
                    cipher = ssock.cipher()
                    version = ssock.version()

                    # Check SSL/TLS version
                    if version in ['SSLv2', 'SSLv3', 'TLSv1', 'TLSv1.1']:
                        self.add_finding(SecurityFinding(
                            id=f"tls_weak_version_{self.scan_id}",
                            title="Weak TLS/SSL Version Detected",
                            description=f"Weak SSL/TLS version {version} is in use",
                            severity=VulnerabilitySeverity.HIGH,
                            asset_type=AssetType.INFRASTRUCTURE,
                            component="tls_configuration",
                            vulnerability_type="weak_crypto",
                            cwe_id="CWE-327",
                            cvss_score=7.5,
                            remediation="Upgrade to TLS 1.2 or higher",
                            evidence={"version": version, "cipher": cipher}
                        ))

                    # Check cipher strength
                    if cipher and any(weak in cipher[0].lower() for weak in ['rc4', 'des', 'md5', 'null']):
                        self.add_finding(SecurityFinding(
                            id=f"tls_weak_cipher_{self.scan_id}",
                            title="Weak Cipher Suite Detected",
                            description=f"Weak cipher suite {cipher[0]} is in use",
                            severity=VulnerabilitySeverity.MEDIUM,
                            asset_type=AssetType.INFRASTRUCTURE,
                            component="tls_configuration",
                            vulnerability_type="weak_crypto",
                            cwe_id="CWE-326",
                            cvss_score=5.3,
                            remediation="Disable weak cipher suites and use strong encryption",
                            evidence={"cipher": cipher}
                        ))

        except Exception as e:
            logger.warning(f"TLS configuration check failed: {e}")

    async def _check_security_headers(self):
        """Check security headers"""
        try:
            base_url = self.config['target_system']['base_url']
            async with self.session.get(base_url) as response:
                headers = response.headers

                # Required security headers
                required_headers = {
                    "X-Content-Type-Options": "nosniff",
                    "X-Frame-Options": ["DENY", "SAMEORIGIN"],
                    "X-XSS-Protection": "1; mode=block",
                    "Referrer-Policy": ["strict-origin-when-cross-origin", "no-referrer", "strict-origin"],
                    "Content-Security-Policy": None,  # Just check existence
                    "Permissions-Policy": None,
                    "Strict-Transport-Security": None
                }

                missing_headers = []
                for header, expected_value in required_headers.items():
                    if header not in headers:
                        missing_headers.append(header)
                        severity = VulnerabilitySeverity.MEDIUM if header in ["Content-Security-Policy", "Strict-Transport-Security"] else VulnerabilitySeverity.LOW

                        self.add_finding(SecurityFinding(
                            id=f"missing_header_{header}_{self.scan_id}",
                            title=f"Missing Security Header: {header}",
                            description=f"Security header {header} is missing",
                            severity=severity,
                            asset_type=AssetType.FRONTEND,
                            component="security_headers",
                            vulnerability_type="missing_security_header",
                            remediation=f"Implement {header} header",
                            evidence={"missing_header": header}
                        ))
                    elif expected_value and isinstance(expected_value, list):
                        if headers[header] not in expected_value:
                            missing_headers.append(f"{header} (invalid value)")
                            self.add_finding(SecurityFinding(
                                id=f"invalid_header_{header}_{self.scan_id}",
                                title=f"Invalid Security Header Value: {header}",
                                description=f"Security header {header} has invalid value: {headers[header]}",
                                severity=VulnerabilitySeverity.LOW,
                                asset_type=AssetType.FRONTEND,
                                component="security_headers",
                                vulnerability_type="invalid_security_header",
                                remediation=f"Set {header} to appropriate value",
                                evidence={"header": header, "value": headers[header], "expected": expected_value}
                            ))

        except Exception as e:
            logger.warning(f"Security headers check failed: {e}")

    async def _check_authentication(self):
        """Check authentication mechanisms"""
        # Test authentication endpoints
        auth_endpoints = [
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/refresh"
        ]

        for endpoint in auth_endpoints:
            try:
                url = urljoin(self.config['target_system']['base_url'], endpoint)

                # Test endpoint exists and responds appropriately
                async with self.session.post(url, json={"test": "data"}) as response:
                    if response.status == 200:
                        # Check if authentication is actually required
                        data = await response.json()
                        if "token" in data or "access_token" in data:
                            # Check token strength
                            await self._check_jwt_strength(url, data)

            except Exception as e:
                logger.debug(f"Authentication check for {endpoint} failed: {e}")

    async def _check_jwt_strength(self, auth_url: str, auth_response: Dict):
        """Check JWT token strength and security"""
        token = auth_response.get("token") or auth_response.get("access_token")
        if not token:
            return

        try:
            # Decode JWT without verification (just to check structure)
            decoded = jwt.decode(token, options={"verify_signature": False})

            # Check token expiration
            if 'exp' not in decoded:
                self.add_finding(SecurityFinding(
                    id=f"jwt_no_expiration_{self.scan_id}",
                    title="JWT Token Without Expiration",
                    description="JWT token does not have expiration claim",
                    severity=VulnerabilitySeverity.HIGH,
                    asset_type=AssetType.BACKEND,
                    component="authentication",
                    vulnerability_type="weak_token",
                    cwe_id="CWE-613",
                    remediation="Add expiration claim to JWT tokens",
                    evidence={"token_claims": list(decoded.keys())}
                ))

            # Check token issued time
            if 'iat' not in decoded:
                self.add_finding(SecurityFinding(
                    id=f"jwt_no_issued_at_{self.scan_id}",
                    title="JWT Token Without Issued At",
                    description="JWT token does not have issued at claim",
                    severity=VulnerabilitySeverity.MEDIUM,
                    asset_type=AssetType.BACKEND,
                    component="authentication",
                    vulnerability_type="weak_token",
                    remediation="Add issued at claim to JWT tokens",
                    evidence={"token_claims": list(decoded.keys())}
                ))

            # Check for sensitive data in token
            sensitive_claims = ['password', 'secret', 'key', 'token']
            found_sensitive = [claim for claim in sensitive_claims if claim in str(decoded).lower()]
            if found_sensitive:
                self.add_finding(SecurityFinding(
                    id=f"jwt_sensitive_data_{self.scan_id}",
                    title="Sensitive Data in JWT Token",
                    description=f"JWT token contains sensitive data: {found_sensitive}",
                    severity=VulnerabilitySeverity.HIGH,
                    asset_type=AssetType.BACKEND,
                    component="authentication",
                    vulnerability_type="information_disclosure",
                    remediation="Remove sensitive data from JWT tokens",
                    evidence={"sensitive_claims": found_sensitive}
                ))

        except Exception as e:
            logger.debug(f"JWT strength check failed: {e}")

    async def _run_bandit_scan(self):
        """Run Bandit static analysis security scanner"""
        try:
            # Scan backend Python code
            backend_path = "/Users/goodwiinz/development/RAG_system/rag/backend/src"
            if os.path.exists(backend_path):
                result = subprocess.run([
                    sys.executable, "-m", "bandit", "-r", backend_path,
                    "-f", "json", "-o", f"/tmp/bandit_{self.scan_id}.json"
                ], capture_output=True, text=True)

                if result.returncode == 0:
                    with open(f"/tmp/bandit_{self.scan_id}.json", 'r') as f:
                        bandit_results = json.load(f)

                    for issue in bandit_results.get('results', []):
                        severity_map = {
                            'high': VulnerabilitySeverity.HIGH,
                            'medium': VulnerabilitySeverity.MEDIUM,
                            'low': VulnerabilitySeverity.LOW
                        }

                        self.add_finding(SecurityFinding(
                            id=f"bandit_{issue['test_id']}_{issue['filename'].replace('/', '_')}_{self.scan_id}",
                            title=f"Bandit: {issue['test_name']}",
                            description=issue['issue_text'],
                            severity=severity_map.get(issue['issue_severity'], VulnerabilitySeverity.MEDIUM),
                            asset_type=AssetType.BACKEND,
                            component=issue['filename'],
                            vulnerability_type="static_analysis",
                            cwe_id=issue.get('cwe_id'),
                            cvss_score=issue.get('issue_cwe', {}).get('cvss_score'),
                            remediation=issue.get('issue_cwe', {}).get('remediation', ''),
                            evidence={
                                "line_number": issue['line_number'],
                                "line_range": issue['line_range'],
                                "code": issue['code']
                            }
                        ))

        except Exception as e:
            logger.warning(f"Bandit scan failed: {e}")

    async def _run_safety_scan(self):
        """Run Safety dependency vulnerability scanner"""
        try:
            # Check for dependency vulnerabilities
            requirements_files = [
                "/Users/goodwiinz/development/RAG_system/rag/requirements.txt",
                "/Users/goodwiinz/development/RAG_system/rag/backend/requirements.txt"
            ]

            for req_file in requirements_files:
                if os.path.exists(req_file):
                    result = subprocess.run([
                        sys.executable, "-m", "safety", "check", "--file", req_file,
                        "--json", "--output", f"/tmp/safety_{self.scan_id}.json"
                    ], capture_output=True, text=True)

                    if result.returncode == 0:
                        try:
                            with open(f"/tmp/safety_{self.scan_id}.json", 'r') as f:
                                safety_results = json.load(f)

                            for vuln in safety_results:
                                self.add_finding(SecurityFinding(
                                    id=f"safety_{vuln['package']}_{self.scan_id}",
                                    title=f"Dependency Vulnerability: {vuln['package']}",
                                    description=f"Vulnerability found in {vuln['package']} version {vuln['installed_version']}: {vuln['advisory']}",
                                    severity=VulnerabilitySeverity.HIGH if vuln['vulnerability_id'].startswith('CVE') else VulnerabilitySeverity.MEDIUM,
                                    asset_type=AssetType.BACKEND,
                                    component=f"dependencies:{vuln['package']}",
                                    vulnerability_type="dependency_vulnerability",
                                    cwe_id=vuln.get('cve'),
                                    remediation=f"Upgrade {vuln['package']} to {vuln['analyzed_version'] or 'latest secure version'}",
                                    evidence=vuln
                                ))
                        except (FileNotFoundError, json.JSONDecodeError):
                            logger.warning(f"Safety results not available for {req_file}")

        except Exception as e:
            logger.warning(f"Safety scan failed: {e}")

    async def _generate_reports(self):
        """Generate security audit reports"""
        output_dir = Path(self.config['reporting']['output_dir'])
        output_dir.mkdir(parents=True, exist_ok=True)

        # JSON Report
        if 'json' in self.config['reporting']['formats']:
            await self._generate_json_report(output_dir)

        # HTML Report
        if 'html' in self.config['reporting']['formats']:
            await self._generate_html_report(output_dir)

        # CSV Report
        if 'csv' in self.config['reporting']['formats']:
            await self._generate_csv_report(output_dir)

        # Executive Summary
        await self._generate_executive_summary(output_dir)

    async def _generate_json_report(self, output_dir: Path):
        """Generate JSON security report"""
        report_data = {
            "scan_id": self.scan_id,
            "scan_start": self.scan_start_time.isoformat(),
            "scan_end": datetime.now(timezone.utc).isoformat(),
            "metrics": asdict(self.metrics),
            "findings": [asdict(finding) for finding in self.findings],
            "configuration": self.config
        }

        # Convert datetime objects to strings for JSON serialization
        for finding in report_data['findings']:
            if finding.get('discovered_at'):
                finding['discovered_at'] = finding['discovered_at'].isoformat()

        report_path = output_dir / f"security_report_{self.scan_id}.json"
        with open(report_path, 'w') as f:
            json.dump(report_data, f, indent=2)

        logger.info(f"JSON report generated: {report_path}")

    async def _generate_html_report(self, output_dir: Path):
        """Generate HTML security report"""
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Security Audit Report - {self.scan_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .header {{ background-color: #f4f4f4; padding: 20px; border-radius: 5px; }}
        .metrics {{ display: flex; gap: 20px; margin: 20px 0; }}
        .metric {{ background-color: #e9ecef; padding: 15px; border-radius: 5px; text-align: center; }}
        .critical {{ background-color: #dc3545; color: white; }}
        .high {{ background-color: #fd7e14; color: white; }}
        .medium {{ background-color: #ffc107; color: black; }}
        .low {{ background-color: #28a745; color: white; }}
        .finding {{ border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; }}
        .finding-title {{ font-weight: bold; font-size: 1.1em; margin-bottom: 5px; }}
        .finding-description {{ margin-bottom: 10px; }}
        .finding-evidence {{ background-color: #f8f9fa; padding: 10px; border-radius: 3px; font-family: monospace; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Security Audit Report</h1>
        <p><strong>Scan ID:</strong> {self.scan_id}</p>
        <p><strong>Generated:</strong> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
    </div>

    <div class="metrics">
        <div class="metric">
            <h3>Total Findings</h3>
            <h2>{self.metrics.total_findings}</h2>
        </div>
        <div class="metric critical">
            <h3>Critical</h3>
            <h2>{self.metrics.critical_findings}</h2>
        </div>
        <div class="metric high">
            <h3>High</h3>
            <h2>{self.metrics.high_findings}</h2>
        </div>
        <div class="metric medium">
            <h3>Medium</h3>
            <h2>{self.metrics.medium_findings}</h2>
        </div>
        <div class="metric low">
            <h3>Low</h3>
            <h2>{self.metrics.low_findings}</h2>
        </div>
    </div>

    <div class="metrics">
        <div class="metric">
            <h3>Compliance Score</h3>
            <h2>{self.metrics.compliance_score:.1f}%</h2>
        </div>
        <div class="metric">
            <h3>Risk Score</h3>
            <h2>{self.metrics.risk_score:.1f}</h2>
        </div>
    </div>

    <h2>Security Findings</h2>
"""

        # Group findings by severity
        for severity in [VulnerabilitySeverity.CRITICAL, VulnerabilitySeverity.HIGH,
                        VulnerabilitySeverity.MEDIUM, VulnerabilitySeverity.LOW, VulnerabilitySeverity.INFO]:
            severity_findings = [f for f in self.findings if f.severity == severity]
            if severity_findings:
                html_content += f"<h3>{severity.value.title()} Issues ({len(severity_findings)})</h3>"
                for finding in severity_findings:
                    severity_class = severity.value.lower()
                    html_content += f"""
    <div class="finding {severity_class}">
        <div class="finding-title">{finding.title}</div>
        <div class="finding-description">{finding.description}</div>
        <p><strong>Component:</strong> {finding.component}</p>
        <p><strong>Type:</strong> {finding.vulnerability_type}</p>
        <p><strong>Remediation:</strong> {finding.remediation}</p>
        {f'<div class="finding-evidence"><strong>Evidence:</strong><br>{json.dumps(finding.evidence, indent=2)}</div>' if finding.evidence else ''}
    </div>
"""

        html_content += """
</body>
</html>
"""

        report_path = output_dir / f"security_report_{self.scan_id}.html"
        with open(report_path, 'w') as f:
            f.write(html_content)

        logger.info(f"HTML report generated: {report_path}")

    async def _generate_csv_report(self, output_dir: Path):
        """Generate CSV security report"""
        report_path = output_dir / f"security_report_{self.scan_id}.csv"

        with open(report_path, 'w', newline='') as csvfile:
            fieldnames = ['id', 'title', 'description', 'severity', 'asset_type', 'component',
                         'vulnerability_type', 'cwe_id', 'cvss_score', 'remediation', 'discovered_at']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for finding in self.findings:
                writer.writerow({
                    'id': finding.id,
                    'title': finding.title,
                    'description': finding.description,
                    'severity': finding.severity.value,
                    'asset_type': finding.asset_type.value,
                    'component': finding.component,
                    'vulnerability_type': finding.vulnerability_type,
                    'cwe_id': finding.cwe_id or '',
                    'cvss_score': finding.cvss_score or '',
                    'remediation': finding.remediation,
                    'discovered_at': finding.discovered_at.isoformat() if finding.discovered_at else ''
                })

        logger.info(f"CSV report generated: {report_path}")

    async def _generate_executive_summary(self, output_dir: Path):
        """Generate executive summary report"""
        summary_content = f"""
# Security Audit Executive Summary

**Scan ID:** {self.scan_id}
**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
**System:** Knowledge Graph Analytics Dashboard

## Overall Security Posture

- **Compliance Score:** {self.metrics.compliance_score:.1f}%
- **Risk Score:** {self.metrics.risk_score:.1f}/100
- **Total Findings:** {self.metrics.total_findings}

## Findings Summary

| Severity | Count | Impact |
|----------|-------|---------|
| Critical | {self.metrics.critical_findings} | Immediate action required |
| High | {self.metrics.high_findings} | Action required within 7 days |
| Medium | {self.metrics.medium_findings} | Action required within 30 days |
| Low | {self.metrics.low_findings} | Action required within 90 days |

## Key Risk Areas

"""

        # Group findings by vulnerability type
        vulnerability_counts = {}
        for finding in self.findings:
            if finding.vulnerability_type not in vulnerability_counts:
                vulnerability_counts[finding.vulnerability_type] = 0
            vulnerability_counts[finding.vulnerability_type] += 1

        # Sort by count
        sorted_vulnerabilities = sorted(vulnerability_counts.items(), key=lambda x: x[1], reverse=True)

        for vuln_type, count in sorted_vulnerabilities[:5]:  # Top 5
            summary_content += f"- **{vuln_type.replace('_', ' ').title()}:** {count} findings\n"

        summary_content += f"""
## Recommendations

1. **Immediate Actions (Critical Findings)**
   - Address all {self.metrics.critical_findings} critical findings immediately
   - Implement emergency patches where needed
   - Consider temporary mitigations

2. **Short-term Actions (High Findings)**
   - Address all {self.metrics.high_findings} high findings within 7 days
   - Prioritize authentication and authorization issues
   - Update vulnerable dependencies

3. **Medium-term Improvements (Medium/Low Findings)**
   - Address {self.metrics.medium_findings} medium findings within 30 days
   - Implement security headers and hardening measures
   - Enhance monitoring and logging

4. **Long-term Security Strategy**
   - Establish regular security scanning schedule
   - Implement security CI/CD integration
   - Conduct periodic penetration testing
   - Enhance security awareness and training

## Compliance Status

"""

        compliance_frameworks = self.compliance_requirements.get('frameworks', [])
        for framework in compliance_frameworks:
            score = self.metrics.compliance_score
            status = "Compliant" if score >= 90 else "Partial Compliance" if score >= 70 else "Non-Compliant"
            summary_content += f"- **{framework}:** {status} ({score:.1f}%)\n"

        summary_content += f"""
---
*Report generated by Enterprise Security Audit Framework*
"""

        report_path = output_dir / f"executive_summary_{self.scan_id}.md"
        with open(report_path, 'w') as f:
            f.write(summary_content)

        logger.info(f"Executive summary generated: {report_path}")

async def main():
    """Main function to run security audit"""
    # Create output directories
    os.makedirs("/Users/goodwiinz/development/RAG_system/rag/security/logs", exist_ok=True)
    os.makedirs("/Users/goodwiinz/development/RAG_system/rag/security/reports", exist_ok=True)

    async with SecurityAuditFramework() as framework:
        metrics = await framework.run_comprehensive_audit()

        print(f"\n🔍 Security Audit Complete")
        print(f"📊 Total Findings: {metrics.total_findings}")
        print(f"🚨 Critical: {metrics.critical_findings}")
        print(f"⚠️  High: {metrics.high_findings}")
        print(f"🔶 Medium: {metrics.medium_findings}")
        print(f"🔵 Low: {metrics.low_findings}")
        print(f"📈 Compliance Score: {metrics.compliance_score:.1f}%")
        print(f"🎯 Risk Score: {metrics.risk_score:.1f}/100")

        # Exit with appropriate code based on findings
        if metrics.critical_findings > 0:
            print("\n❌ Critical security issues found - immediate action required")
            exit(1)
        elif metrics.high_findings > 0:
            print("\n⚠️  High security issues found - action required within 7 days")
            exit(2)
        else:
            print("\n✅ Security audit completed successfully")
            exit(0)

if __name__ == "__main__":
    asyncio.run(main())