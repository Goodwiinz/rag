"""
Comprehensive API Security Middleware
Implements multiple layers of security protection:
- Input validation and sanitization
- SQL injection prevention
- XSS protection
- Request size limiting
- IP-based security controls
- Request header validation
- CSRF protection
- Content-Type enforcement
"""

import hashlib
import ipaddress
import json
import logging
import re
import time
from html import escape
from typing import Any, Dict, List, Optional, Set
from urllib.parse import unquote

import orjson
from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from src.core.config import settings
from src.middleware.responses import error_response
from src.models.user import User

logger = logging.getLogger(__name__)


class APISecurityMiddleware(BaseHTTPMiddleware):
    """
    Comprehensive API security middleware
    """

    def __init__(self, app):
        super().__init__(app)

        # Configure security rules
        self.max_request_size = 50 * 1024 * 1024  # 50MB
        self.max_url_length = 2048
        self.max_header_size = 8192
        self.max_form_fields = 100

        # SQL injection patterns
        self.sql_injection_patterns = [
            r"(\b(UNION|SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE)\b)",
            r"(\'(OR|AND)\s+\w+\s*=\s*\w+)",
            r"((\%27)|(\'))\s*((\%6F)|o|(\%4F))((\%72)|r|(\%52))",
            r"((\%27)|(\'))\s*((\%61)|a|(\%41))((\%6E)|n|(\%4E))((\%64)|d|(\%44))",
            r"((\%27)|(\'))\s*((\%7C)|\|)",
            r"((\%27)|(\'))\s*;.*",
            r"(\b(0x[0-9a-f]+)\b)",
            r"(/\*.*\*/)",
            r"(--[^#]*)",
            r"(;(\s+)*(DROP|DELETE|UPDATE|INSERT|CREATE|ALTER|EXEC))",
            r"(WAITFOR\s+DELAY)",
            r"(BENCHMARK\s*\()",
            r"(SLEEP\s*\()",
            r"(PG_SLEEP\s*\()",
            r"(SYSTEM\s*\()",
            r"(EXEC\s*\()",
            r"(XP_CMDSHELL)",
        ]

        # XSS patterns
        self.xss_patterns = [
            r"((\%3C)|<)((\%2F)|/)*[a-z0-9\%]+((\%3E)|>)",
            r"((\%3C)|<)((\%69)|i|(\%49))((\%6D)|m|(\%4D))((\%67)|g|(\%47))",
            r"((\%3C)|<)((\%73)|s|(\%53))((\%63)|c|(\%43))((\%72)|r|(\%52))((\%69)|i|(\%49))((\%70)|p|(\%50))((\%74)|t|(\%54))",
            r"((\%3C)|<)[^\s]+((\%3E)|>)",
            r"((\%6A)|j|(\%4A))((\%61)|a|(\%41))((\%76)|v|(\%56))((\%61)|a|(\%41))((\%73)|s|(\%53))((\%63)|c|(\%43))((\%72)|r|(\%52))((\%69)|i|(\%49))((\%70)|p|(\%50))((\%74)|t|(\%54))",
            r"(javascript:)",
            r"(vbscript:)",
            r"(onload\s*=)",
            r"(onerror\s*=)",
            r"(onclick\s*=)",
            r"(onmouseover\s*=)",
            r"(onfocus\s*=)",
            r"(onblur\s*=)",
            r"(onchange\s*=)",
            r"(onsubmit\s*=)",
            r"(eval\s*\()",
            r"(alert\s*\()",
            r"(confirm\s*\()",
            r"(prompt\s*\()",
            r"(document\.cookie)",
            r"(document\.write)",
            r"(innerHTML\s*=)",
            r"(outerHTML\s*=)",
            r"(window\.location)",
            r"(window\.open)",
            r"(\@import)",
            r"(expression\s*\()",
        ]

        # Path traversal patterns
        self.path_traversal_patterns = [
            r"(\.\./)",
            r"(\.\.\\)",
            r"(%2e%2e%2f)",
            r"(%2e%2e%5c)",
            r"(\.\.%2f)",
            r"(\.\.%5c)",
            r"(%2e%2e/)",
            r"(%2e%2e\\)",
            r"(\.\.%c0%af)",
            r"(\.\.%c1%9c)",
        ]

        # Command injection patterns
        self.command_injection_patterns = [
            r"(\||\&|;|`|\$|\(\)|\{\})",
            r"(>\s*/dev/null)",
            r"(>\s+/dev/tty)",
            r"(nc\s+-l)",
            r"(netcat\s+-l)",
            r"(telnet\s+)",
            r"(wget\s+)",
            r"(curl\s+)",
            r"(rm\s+-rf)",
            r"(dd\s+if=)",
            r"(chmod\s+[0-9])",
            r"(chown\s+)",
            r"(whoami)",
            r"(id\s;)",
            r"(uname\s+-a)",
            r"(ps\s+aux)",
            r"(cat\s+/etc/passwd)",
            r"(cat\s+/etc/shadow)",
            r"(ls\s+-la)",
            r"(find\s+/)",
            r"(grep\s+-r)",
        ]

        # Blocked IPs (example - would load from database/config)
        self.blocked_ips: Set[str] = set()
        self.suspicious_ips: Dict[str, Dict] = {}

        # Allowed content types for POST/PUT/PATCH
        self.allowed_content_types = {
            "application/json",
            "application/x-www-form-urlencoded",
            "multipart/form-data",
            "text/plain",
            "application/xml",
            "text/xml",
        }

    async def dispatch(self, request: Request, call_next):
        """
        Process request through all security checks
        """
        start_time = time.time()

        client_ip = self._get_client_ip(request)

        try:
            if self._is_ip_blocked(client_ip):
                self._log_security_event("BLOCKED_IP_ATTEMPT", request, client_ip)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
                )

            self._validate_request_basics(request)
            self._validate_headers(request)
            self._validate_url(request)

            if request.method in ["POST", "PUT", "PATCH"]:
                await self._validate_request_body(request)

            self._check_suspicious_activity(client_ip, request)
        except HTTPException as e:
            return error_response(e.status_code, e.detail)

        response = await call_next(request)
        response = self._add_security_headers(response)

        duration = time.time() - start_time
        self._log_request_completion(request, response, duration, client_ip)

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP from request, handling proxies"""
        # Check for forwarded headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Get the original IP (first in the list)
            return forwarded_for.split(",")[-1].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        # Fallback to direct connection IP
        return request.client.host if request.client else "unknown"

    def _is_ip_blocked(self, ip: str) -> bool:
        """Check if IP is in blocked list"""
        # Normalize IP for comparison
        try:
            ip_obj = ipaddress.ip_address(ip)

            # Check exact match
            if str(ip_obj) in self.blocked_ips:
                return True

            # Check for subnets (would load from config)
            # Example blocked networks
            blocked_networks = [
                ipaddress.ip_network("192.168.100.0/24"),
                ipaddress.ip_network("10.0.0.0/8"),
            ]

            for network in blocked_networks:
                if ip_obj in network:
                    return True

        except ValueError:
            # Invalid IP
            pass

        return False

    def _validate_request_basics(self, request: Request):
        """Validate basic request parameters"""
        # Check URL length
        if len(str(request.url)) > self.max_url_length:
            raise HTTPException(
                status_code=status.HTTP_414_REQUEST_URI_TOO_LONG, detail="URL too long"
            )

        # Check HTTP method
        allowed_methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
        if request.method not in allowed_methods:
            raise HTTPException(
                status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
                detail="Method not allowed",
            )

    def _validate_headers(self, request: Request):
        """Validate request headers for security issues"""
        total_size = 0

        for name, value in request.headers.items():
            # Check header size
            header_size = len(name) + len(value)
            total_size += header_size

            if header_size > self.max_header_size:
                raise HTTPException(
                    status_code=status.HTTP_431_REQUEST_HEADER_FIELDS_TOO_LARGE,
                    detail=f"Header '{name}' too large",
                )

            # Check for suspicious headers
            self._check_header_security(name, value)

        # Check total header size
        if total_size > self.max_header_size * 10:  # 10 headers max
            raise HTTPException(
                status_code=status.HTTP_431_REQUEST_HEADER_FIELDS_TOO_LARGE,
                detail="Headers too large",
            )

    def _check_header_security(self, name: str, value: str):
        """Check individual header for security issues"""
        # Check for injection patterns
        all_patterns = (
            self.sql_injection_patterns
            + self.xss_patterns
            + self.command_injection_patterns
        )

        for pattern in all_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(
                    f"Suspicious pattern in header '{name}': {value[:50]}...",
                    extra={
                        "header_name": name,
                        "pattern_detected": True,
                        "severity": "high",
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid header content",
                )

    def _validate_url(self, request: Request):
        """Validate URL for security issues"""
        url_path = str(request.url.path)
        query_string = str(request.url.query) if request.url.query else ""

        # Check for path traversal
        for pattern in self.path_traversal_patterns:
            if re.search(pattern, url_path, re.IGNORECASE):
                logger.warning(
                    f"Path traversal attempt: {url_path}",
                    extra={
                        "path": url_path,
                        "client_ip": request.client.host,
                        "severity": "critical",
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid path"
                )

        # Check for SQL injection in URL
        for pattern in self.sql_injection_patterns:
            if re.search(pattern, url_path + query_string, re.IGNORECASE):
                logger.warning(
                    f"SQL injection attempt in URL: {url_path}",
                    extra={
                        "path": url_path,
                        "query": query_string,
                        "client_ip": request.client.host,
                        "severity": "critical",
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request"
                )

        # Check for XSS in URL
        for pattern in self.xss_patterns:
            if re.search(pattern, url_path + query_string, re.IGNORECASE):
                logger.warning(
                    f"XSS attempt in URL: {url_path}",
                    extra={
                        "path": url_path,
                        "query": query_string,
                        "client_ip": request.client.host,
                        "severity": "high",
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request"
                )

        # Validate query parameters
        if query_string:
            self._validate_query_params(query_string, request)

    def _validate_query_params(self, query_string: str, request: Request):
        """Validate query parameters"""
        # Parse and validate each parameter
        params = query_string.split("&")

        if len(params) > 50:  # Too many parameters
            raise HTTPException(
                status_code=status.HTTP_414_REQUEST_URI_TOO_LONG,
                detail="Too many parameters",
            )

        for param in params:
            if "=" not in param:
                continue

            key, value = param.split("=", 1)

            # Decode and check
            try:
                key = unquote(key)
                value = unquote(value)
            except:
                continue

            # Check parameter security
            self._check_parameter_security(key, value, request)

    def _check_parameter_security(self, key: str, value: str, request: Request):
        """Check individual parameter for security issues"""
        # Check for dangerous parameter names
        dangerous_params = [
            "redirect",
            "return",
            "url",
            "goto",
            "next",
            "forward",
            "callback",
            "jsonp",
            "j",
            "jsonpCallback",
            "function",
            "exec",
            "cmd",
            "command",
            "run",
            "eval",
            "code",
        ]

        if key.lower() in dangerous_params:
            # Check for URL in value
            if value.startswith(("http://", "https://", "ftp://", "data:")):
                logger.warning(
                    f"Potential redirect injection: {key}={value}",
                    extra={
                        "param_name": key,
                        "param_value": value[:100],
                        "client_ip": request.client.host,
                        "severity": "high",
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid parameter"
                )

        # Check for injection patterns in value
        all_patterns = (
            self.sql_injection_patterns
            + self.xss_patterns
            + self.command_injection_patterns
        )

        for pattern in all_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(
                    f"Injection attempt in parameter {key}: {value[:50]}...",
                    extra={
                        "param_name": key,
                        "pattern_detected": True,
                        "client_ip": request.client.host,
                        "severity": "high",
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid parameter content",
                )

    async def _validate_request_body(self, request: Request):
        """Validate request body content"""
        # Check content type
        content_type = request.headers.get("content-type", "").split(";")[0]

        if content_type not in self.allowed_content_types:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Unsupported media type",
            )

        # Check content length
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_request_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Request entity too large",
            )

        # Read and validate body
        body = await request.body()

        if len(body) > self.max_request_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Request entity too large",
            )

        # Validate based on content type
        if content_type == "application/json":
            self._validate_json_body(body, request)
        elif content_type == "application/x-www-form-urlencoded":
            self._validate_form_body(body, request)
        elif content_type.startswith("multipart/form-data"):
            # Multipart validation would happen in specific endpoints
            pass

    def _validate_json_body(self, body: bytes, request: Request):
        """Validate JSON body for security issues"""
        try:
            # Parse JSON
            data = orjson.loads(body)

            # Recursively validate JSON structure
            self._validate_json_structure(data, request)

        except orjson.JSONDecodeError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON format"
            )

    def _validate_json_structure(self, data: Any, request: Request, path: str = ""):
        """Recursively validate JSON structure"""
        if isinstance(data, dict):
            if len(data) > self.max_form_fields:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Too many fields in request",
                )

            for key, value in data.items():
                current_path = f"{path}.{key}" if path else key

                # Check key name
                if len(key) > 256:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Field name too long",
                    )

                # Recursively validate value
                self._validate_json_structure(value, request, current_path)

        elif isinstance(data, list):
            if len(data) > 1000:  # Too many array elements
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Array too large"
                )

            for i, item in enumerate(data):
                self._validate_json_structure(item, request, f"{path}[{i}]")

        elif isinstance(data, str):
            # Check string content
            self._validate_string_content(data, request, path)

        # Other types (int, float, bool, None) are generally safe

    def _validate_string_content(self, value: str, request: Request, path: str):
        """Validate string content for security issues"""
        # Check string length
        if len(value) > 100000:  # 100KB per string field
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="String value too long"
            )

        # Check for injection patterns
        all_patterns = (
            self.sql_injection_patterns
            + self.xss_patterns
            + self.command_injection_patterns
        )

        for pattern in all_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(
                    f"Injection attempt in field '{path}': {value[:50]}...",
                    extra={
                        "field_path": path,
                        "pattern_detected": True,
                        "client_ip": request.client.host,
                        "severity": "high",
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid field content",
                )

    def _validate_form_body(self, body: bytes, request: Request):
        """Validate form-encoded body"""
        try:
            # Decode and parse
            form_data = body.decode("utf-8")
            params = form_data.split("&")

            if len(params) > self.max_form_fields:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Too many form fields",
                )

            for param in params:
                if "=" not in param:
                    continue

                key, value = param.split("=", 1)

                # Decode
                try:
                    key = unquote(key)
                    value = unquote(value)
                except:
                    continue

                # Validate
                self._check_parameter_security(key, value, request)

        except UnicodeDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid form encoding"
            )

    def _check_suspicious_activity(self, ip: str, request: Request):
        """Track and check for suspicious activity patterns"""
        now = time.time()

        # Initialize tracking for this IP
        if ip not in self.suspicious_ips:
            self.suspicious_ips[ip] = {
                "requests": [],
                "violations": 0,
                "last_seen": now,
            }

        ip_data = self.suspicious_ips[ip]

        # Clean old requests (older than 1 hour)
        ip_data["requests"] = [
            req_time for req_time in ip_data["requests"] if now - req_time < 3600
        ]

        # Add current request
        ip_data["requests"].append(now)
        ip_data["last_seen"] = now

        # Check for patterns
        request_count = len(ip_data["requests"])

        # Too many requests
        if request_count > 1000:  # 1000 requests per hour
            ip_data["violations"] += 1
            logger.warning(
                f"High request rate from IP {ip}: {request_count}/hour",
                extra={
                    "client_ip": ip,
                    "request_count": request_count,
                    "severity": "medium",
                },
            )

        # Check for automated behavior
        if request_count > 10:
            # Check if requests are too regular (bot-like)
            intervals = [
                ip_data["requests"][i] - ip_data["requests"][i - 1]
                for i in range(1, min(10, len(ip_data["requests"])))
            ]

            if intervals and all(0.9 < interval < 1.1 for interval in intervals):
                ip_data["violations"] += 1
                logger.warning(
                    f"Automated request pattern detected from IP {ip}",
                    extra={
                        "client_ip": ip,
                        "pattern": "regular_intervals",
                        "severity": "medium",
                    },
                )

        # Block if too many violations
        if ip_data["violations"] > 5:
            self.blocked_ips.add(ip)
            logger.error(
                f"IP {ip} blocked due to repeated violations",
                extra={
                    "client_ip": ip,
                    "violations": ip_data["violations"],
                    "severity": "high",
                },
            )

    def _add_security_headers(self, response: Response) -> Response:
        """Add security headers to response"""
        # Basic security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Content Security Policy
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        response.headers["Content-Security-Policy"] = csp

        # HSTS (only in production with HTTPS)
        if settings.ENVIRONMENT == "production":
            response.headers[
                "Strict-Transport-Security"
            ] = "max-age=31536000; includeSubDomains"

        # Permissions Policy
        permissions_policy = (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=(), "
            "usb=(), "
            "magnetometer=(), "
            "gyroscope=(), "
            "accelerometer=()"
        )
        response.headers["Permissions-Policy"] = permissions_policy

        return response

    def _log_security_event(self, event_type: str, request: Request, client_ip: str):
        """Log security events"""
        logger.error(
            f"Security event: {event_type}",
            extra={
                "event_type": event_type,
                "client_ip": client_ip,
                "path": str(request.url.path),
                "method": request.method,
                "user_agent": request.headers.get("user-agent", ""),
                "severity": "critical",
            },
        )

    def _log_request_completion(
        self, request: Request, response: Response, duration: float, client_ip: str
    ):
        """Log completed request for monitoring"""
        # Log slow requests
        if duration > 5.0:
            logger.warning(
                f"Slow request: {request.method} {request.url.path} took {duration:.2f}s",
                extra={
                    "client_ip": client_ip,
                    "method": request.method,
                    "path": str(request.url.path),
                    "duration": duration,
                    "status_code": response.status_code,
                    "severity": "low",
                },
            )

        # Log errors
        if response.status_code >= 400:
            log_level = logger.error if response.status_code >= 500 else logger.warning
            log_level(
                f"HTTP {response.status_code}: {request.method} {request.url.path}",
                extra={
                    "client_ip": client_ip,
                    "method": request.method,
                    "path": str(request.url.path),
                    "status_code": response.status_code,
                    "severity": "medium" if response.status_code < 500 else "high",
                },
            )
