"""
Search Security Module
Comprehensive security utilities for search functionality

This module implements defense-in-depth security measures for the search system:
- Query sanitization (SQL injection, XSS prevention)
- Rate limiting helpers
- Audit logging
- Input validation
"""

import re
import hashlib
import logging
import unicodedata
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from dataclasses import dataclass, field
import html
from functools import lru_cache

logger = logging.getLogger(__name__)

# =============================================================================
# Query Sanitization
# =============================================================================

class SearchQuerySanitizer:
    """
    Defense-in-depth search query sanitization.
    
    Implements multiple layers of protection:
    1. Length limits
    2. Unicode normalization
    3. Injection pattern detection
    4. Character allowlist
    5. Encoding validation
    """
    
    # Configuration
    MAX_QUERY_LENGTH = 500
    MAX_WORD_LENGTH = 50
    MIN_WORD_LENGTH = 2
    
    # SQL Injection patterns (compiled for performance)
    SQL_INJECTION_PATTERNS = [
        re.compile(r'\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b', re.I),
        re.compile(r"['\"]?\s*(or|and)\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+", re.I),
        re.compile(r'(--|#|/\*|\*/)', re.I),
        re.compile(r'(waitfor\s+delay|benchmark\s*\(|sleep\s*\(|pg_sleep\s*\()', re.I),
        re.compile(r'(system\s*\(|exec\s*\(|xp_cmdshell)', re.I),
        re.compile(r'(0x[0-9a-f]+)', re.I),
        re.compile(r';\s*(drop|delete|update|insert|create|alter|exec)', re.I),
        re.compile(r"('\s*(or|and)\s*')", re.I),
        re.compile(r'\bunion\s+all\s+select\b', re.I),
        re.compile(r'\bload_file\s*\(', re.I),
        re.compile(r'\binto\s+(outfile|dumpfile)\b', re.I),
        re.compile(r'\binformation_schema\b', re.I),
    ]
    
    # NoSQL/Cypher injection patterns
    NOSQL_INJECTION_PATTERNS = [
        re.compile(r'\$\w+', re.I),  # MongoDB operators
        re.compile(r'\{\s*\$', re.I),  # MongoDB query operators
        re.compile(r'(MATCH|CREATE|MERGE|DELETE|SET|REMOVE)\s*\(', re.I),  # Cypher
        re.compile(r'\bWHERE\s+\w+\s*=', re.I),
    ]
    
    # XSS patterns
    XSS_PATTERNS = [
        re.compile(r'<\s*script', re.I),
        re.compile(r'javascript\s*:', re.I),
        re.compile(r'on\w+\s*=', re.I),  # Event handlers
        re.compile(r'<\s*iframe', re.I),
        re.compile(r'<\s*object', re.I),
        re.compile(r'<\s*embed', re.I),
        re.compile(r'expression\s*\(', re.I),  # CSS expression
        re.compile(r'url\s*\(\s*["\']?\s*javascript', re.I),
    ]
    
    @classmethod
    def sanitize(
        cls,
        query: str,
        strict: bool = True,
        allow_wildcards: bool = False
    ) -> str:
        """
        Sanitize search query with multiple defense layers.
        
        Args:
            query: Raw user input
            strict: If True, reject suspicious queries entirely
            allow_wildcards: If True, allow * and ? for pattern matching
            
        Returns:
            Sanitized query string
            
        Raises:
            SearchSecurityError: If query contains malicious patterns (strict mode)
        """
        if not query:
            return ""
        
        original_query = query
        
        # Layer 1: Length check
        if len(query) > cls.MAX_QUERY_LENGTH:
            query = query[:cls.MAX_QUERY_LENGTH]
            logger.warning(f"Query truncated from {len(original_query)} to {cls.MAX_QUERY_LENGTH}")
        
        # Layer 2: Unicode normalization (prevents bypass via confusables)
        query = unicodedata.normalize('NFKC', query)
        
        # Layer 3: Check for injection patterns
        security_violations = cls._detect_injection_patterns(query)
        
        if security_violations:
            if strict:
                raise SearchSecurityError(
                    f"Query contains potentially malicious content: {security_violations}"
                )
            else:
                # Remove matched content
                for violation in security_violations:
                    pattern = violation['pattern']
                    query = pattern.sub('', query)
                logger.warning(f"Removed {len(security_violations)} security violations from query")
        
        # Layer 4: Character processing
        sanitized_words = []
        allowed_pattern = r'[\w\s\-]' if not allow_wildcards else r'[\w\s\-\*\?]'
        
        for word in query.split():
            # Remove characters not in allowlist
            clean_word = re.sub(f'[^{allowed_pattern[1:-1]}]', '', word)
            
            if cls.MIN_WORD_LENGTH <= len(clean_word) <= cls.MAX_WORD_LENGTH:
                sanitized_words.append(clean_word)
        
        result = ' '.join(sanitized_words).strip()
        
        # Log significant changes
        if result != original_query.strip():
            logger.info(
                f"Query sanitized: original_length={len(original_query)}, "
                f"result_length={len(result)}"
            )
        
        return result
    
    @classmethod
    def _detect_injection_patterns(cls, query: str) -> List[Dict[str, Any]]:
        """Detect injection patterns in query"""
        violations = []
        
        for pattern in cls.SQL_INJECTION_PATTERNS:
            match = pattern.search(query)
            if match:
                violations.append({
                    'type': 'sql_injection',
                    'pattern': pattern,
                    'match': match.group(),
                    'severity': 'high'
                })
        
        for pattern in cls.NOSQL_INJECTION_PATTERNS:
            match = pattern.search(query)
            if match:
                violations.append({
                    'type': 'nosql_injection',
                    'pattern': pattern,
                    'match': match.group(),
                    'severity': 'high'
                })
        
        for pattern in cls.XSS_PATTERNS:
            match = pattern.search(query)
            if match:
                violations.append({
                    'type': 'xss',
                    'pattern': pattern,
                    'match': match.group(),
                    'severity': 'medium'
                })
        
        return violations
    
    @classmethod
    def is_safe(cls, query: str) -> bool:
        """Quick check if query passes all safety checks"""
        try:
            cls.sanitize(query, strict=True)
            return True
        except SearchSecurityError:
            return False
    
    @classmethod
    def get_security_score(cls, query: str) -> int:
        """
        Calculate security risk score for a query.
        
        Returns:
            Score from 0 (safe) to 100 (extremely risky)
        """
        score = 0
        
        # Check length
        if len(query) > 200:
            score += 5
        if len(query) > 400:
            score += 10
        
        # Check for special character density
        special_chars = len(re.findall(r'[^\w\s]', query))
        char_ratio = special_chars / max(len(query), 1)
        if char_ratio > 0.2:
            score += 15
        if char_ratio > 0.4:
            score += 25
        
        # Check for injection patterns
        violations = cls._detect_injection_patterns(query)
        for violation in violations:
            if violation['severity'] == 'high':
                score += 50
            elif violation['severity'] == 'medium':
                score += 20
        
        # Check for encoding abuse
        if '\\x' in query or '\\u' in query or '%' in query:
            score += 10
        
        return min(score, 100)


# =============================================================================
# HTML/XSS Sanitization
# =============================================================================

class SearchSnippetSanitizer:
    """Sanitize search result snippets for safe display"""
    
    # Safe HTML tags for highlighting
    SAFE_TAGS = {'mark', 'b', 'strong', 'em', 'i'}
    
    # Pattern to match HTML tags
    HTML_TAG_PATTERN = re.compile(r'<\s*/?(\w+)[^>]*>', re.I)
    UNSAFE_CONTAINER_PATTERN = re.compile(
        r'<\s*(script|style|iframe|object|embed|svg|body)[^>]*>.*?<\s*/\s*\1\s*>',
        re.I | re.S,
    )
    UNSAFE_OPEN_TAG_PATTERN = re.compile(
        r'<\s*(script|style|iframe|object|embed|svg|body)[^>]*?/?>',
        re.I,
    )
    EVENT_HANDLER_PATTERN = re.compile(
        r'on\w+\s*=\s*(".*?"|\'.*?\'|[^\s>]+)',
        re.I | re.S,
    )
    PROTOCOL_PATTERN = re.compile(r'(javascript|vbscript|data)\s*:', re.I)
    ALERT_CALL_PATTERN = re.compile(r'alert\s*\([^)]*\)', re.I)
    
    @classmethod
    def sanitize(cls, snippet: str, preserve_highlights: bool = True) -> str:
        """
        Sanitize HTML snippet for safe rendering.
        
        Args:
            snippet: Raw HTML snippet
            preserve_highlights: Keep safe highlight tags
            
        Returns:
            Sanitized HTML
        """
        if not snippet:
            return ""
        
        if not preserve_highlights:
            # Strip all HTML
            return html.escape(re.sub(r'<[^>]+>', '', snippet))
        
        # Remove unsafe containers and obvious JS payloads before any escaping.
        cleaned = cls.UNSAFE_CONTAINER_PATTERN.sub('', snippet)
        cleaned = cls.UNSAFE_OPEN_TAG_PATTERN.sub('', cleaned)
        cleaned = cls.EVENT_HANDLER_PATTERN.sub('', cleaned)
        cleaned = cls.PROTOCOL_PATTERN.sub('', cleaned)
        cleaned = cls.ALERT_CALL_PATTERN.sub('', cleaned)
        cleaned = re.sub(r'(?i)\b(alert|javascript)\b', '', cleaned)

        # Remove unsafe tags while keeping safe ones
        def replace_tag(match):
            tag_name = match.group(1).lower()
            if tag_name in cls.SAFE_TAGS:
                return match.group(0)
            else:
                return ''
        
        cleaned = cls.HTML_TAG_PATTERN.sub(replace_tag, cleaned)
        
        # Escape any remaining dangerous content
        # But preserve our safe tags
        safe_tag_placeholder = {}
        for i, tag in enumerate(cls.SAFE_TAGS):
            open_placeholder = f"__SAFE_TAG_OPEN_{i}__"
            close_placeholder = f"__SAFE_TAG_CLOSE_{i}__"
            safe_tag_placeholder[f"<{tag}>"] = open_placeholder
            safe_tag_placeholder[f"</{tag}>"] = close_placeholder
            cleaned = cleaned.replace(f"<{tag}>", open_placeholder)
            cleaned = cleaned.replace(f"</{tag}>", close_placeholder)
        
        # Escape remaining content
        cleaned = html.escape(cleaned)
        
        # Restore safe tags
        for original, placeholder in safe_tag_placeholder.items():
            cleaned = cleaned.replace(html.escape(placeholder), original)
        
        # Remove any lingering escaped tag fragments from unsafe markup.
        cleaned = re.sub(r'&lt;/?[^&]+?&gt;', '', cleaned)
        return cleaned
    
    @classmethod
    def strip_all_html(cls, text: str) -> str:
        """Remove all HTML tags from text"""
        return html.escape(re.sub(r'<[^>]+>', '', text))


# =============================================================================
# Audit Logging
# =============================================================================

@dataclass
class SearchAuditEvent:
    """Structured audit event for search operations"""
    
    timestamp: datetime
    event_type: str
    user_id: str
    organization_id: str
    query_hash: str  # Privacy-preserving hash
    query_length: int
    search_type: str
    result_count: int
    search_time_ms: float
    client_ip: str
    user_agent: str
    request_id: str
    security_score: int = 0
    security_flags: Dict[str, bool] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'event_type': self.event_type,
            'user_id': self.user_id,
            'organization_id': self.organization_id,
            'query_hash': self.query_hash,
            'query_length': self.query_length,
            'search_type': self.search_type,
            'result_count': self.result_count,
            'search_time_ms': self.search_time_ms,
            'client_ip': self.client_ip,
            'user_agent': self.user_agent[:200] if self.user_agent else '',
            'request_id': self.request_id,
            'security_score': self.security_score,
            'security_flags': self.security_flags,
        }


class SearchAuditLogger:
    """Comprehensive search audit logging"""
    
    def __init__(self):
        self.logger = logging.getLogger('search.audit')
        self.security_logger = logging.getLogger('search.security')
    
    @staticmethod
    def hash_query(query: str) -> str:
        """Create privacy-preserving hash of query"""
        return hashlib.sha256(query.encode()).hexdigest()[:16]
    
    def log_search(
        self,
        user_id: str,
        organization_id: str,
        query: str,
        search_type: str,
        result_count: int,
        search_time_ms: float,
        client_ip: str,
        user_agent: str,
        request_id: str
    ) -> None:
        """Log search event with security context"""
        
        security_score = SearchQuerySanitizer.get_security_score(query)
        security_flags = {
            'high_risk': security_score > 50,
            'contains_special_chars': len(re.findall(r'[^\w\s]', query)) > 5,
            'long_query': len(query) > 300,
        }
        
        event = SearchAuditEvent(
            timestamp=datetime.utcnow(),
            event_type='SEARCH_PERFORMED',
            user_id=user_id,
            organization_id=organization_id,
            query_hash=self.hash_query(query),
            query_length=len(query),
            search_type=search_type,
            result_count=result_count,
            search_time_ms=search_time_ms,
            client_ip=client_ip,
            user_agent=user_agent,
            request_id=request_id,
            security_score=security_score,
            security_flags=security_flags
        )
        
        # Standard audit log
        self.logger.info(f"SEARCH_AUDIT: {event.to_dict()}")
        
        # Security log for high-risk queries
        if security_score > 30:
            self.security_logger.warning(
                f"HIGH_RISK_SEARCH: score={security_score}, "
                f"user={user_id}, ip={client_ip}"
            )
    
    def log_security_violation(
        self,
        user_id: str,
        violation_type: str,
        query_preview: str,
        client_ip: str,
        details: Dict[str, Any]
    ) -> None:
        """Log security violation for immediate attention"""
        
        self.security_logger.error(
            f"SECURITY_VIOLATION: type={violation_type}, "
            f"user={user_id}, ip={client_ip}, "
            f"query_preview='{query_preview[:50]}...'"
        )


# =============================================================================
# Exceptions
# =============================================================================

class SearchSecurityError(Exception):
    """Exception for search security violations"""
    
    def __init__(self, message: str, violation_type: str = "unknown"):
        self.message = message
        self.violation_type = violation_type
        super().__init__(self.message)


# =============================================================================
# Rate Limiting Helpers
# =============================================================================

@dataclass
class RateLimitConfig:
    """Configuration for rate limiting"""
    
    requests_per_minute: int = 60
    burst_limit: int = 10
    burst_window_seconds: int = 5
    
    # Endpoint-specific overrides
    endpoint_limits: Dict[str, int] = field(default_factory=lambda: {
        '/search/': 60,
        '/search/hybrid': 30,
        '/search/suggestions': 120,
        '/search/indexes/rebuild': 1,
        '/search/analytics': 10,
    })


def get_rate_limit_key(user_id: str, endpoint: str) -> str:
    """Generate rate limit key for user and endpoint"""
    return f"ratelimit:search:{user_id}:{endpoint}"


def get_ip_rate_limit_key(client_ip: str, endpoint: str) -> str:
    """Generate rate limit key for IP and endpoint"""
    return f"ratelimit:search:ip:{client_ip}:{endpoint}"


# =============================================================================
# Utility Functions
# =============================================================================

def extract_client_ip(request) -> str:
    """Extract client IP with proxy awareness"""
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        # First IP in chain is the original client
        return forwarded.split(',')[0].strip()
    
    real_ip = request.headers.get('X-Real-IP', '')
    if real_ip:
        return real_ip.strip()
    
    return request.client.host if request.client else 'unknown'


def mask_sensitive_data(data: Dict[str, Any], sensitive_fields: List[str]) -> Dict[str, Any]:
    """Mask sensitive fields in data dictionary"""
    masked = data.copy()
    
    for sensitive_field in sensitive_fields:
        if sensitive_field in masked and masked[sensitive_field]:
            value = str(masked[sensitive_field])
            if len(value) > 4:
                masked[sensitive_field] = value[:2] + '*' * (len(value) - 4) + value[-2:]
            else:
                masked[sensitive_field] = '*' * len(value)
    
    return masked


# =============================================================================
# Global Instances
# =============================================================================

# Create singleton instances for use throughout the application
search_sanitizer = SearchQuerySanitizer()
snippet_sanitizer = SearchSnippetSanitizer()
audit_logger = SearchAuditLogger()
rate_limit_config = RateLimitConfig()
