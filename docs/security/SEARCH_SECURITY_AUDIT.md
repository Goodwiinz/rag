# Search Functionality Security Audit & Improvement Plan

**Version:** 1.0  
**Date:** June 2025  
**Author:** Security Subagent  
**Classification:** Internal - Security Sensitive

---

## Executive Summary

This document provides a comprehensive security audit of the RAG system's search functionality, identifying vulnerabilities across multiple layers and presenting a defense-in-depth improvement strategy. The audit covers backend services, API endpoints, frontend components, and database interactions.

### Key Findings Summary

| Risk Level | Count | Status |
|------------|-------|--------|
| 🔴 Critical | 2 | Partially Mitigated |
| 🟠 High | 5 | Mitigation In Progress |
| 🟡 Medium | 8 | Planned |
| 🟢 Low | 4 | Backlog |

---

## Part 1: Vulnerability Identification

### 1.1 Critical Vulnerabilities

#### VULN-001: SQL Injection in Fulltext Search (PARTIALLY MITIGATED)
**Location:** `backend/src/services/search/fulltext_search_service.py`  
**Risk Level:** 🔴 CRITICAL  
**Status:** Partially mitigated with parameterized queries, but gaps remain

**Description:**
The `_prepare_search_terms` method performs regex-based cleaning but does not fully prevent advanced SQL injection attacks:

```python
def _prepare_search_terms(self, query: str) -> str:
    cleaned = re.sub(r'[^\w\s]', ' ', query.lower())
    words = [word.strip() for word in cleaned.split() if len(word.strip()) >= self.min_query_length]
    return ' & '.join(words)  # PostgreSQL tsquery format
```

**Attack Vectors:**
1. Unicode bypass: `\u0027OR\u00271\u0027=\u00271` could bypass regex
2. Nested encoding: Double URL-encoded payloads
3. PostgreSQL-specific: `plainto_tsquery` function manipulation

**Evidence:**
- Branch `fix/sql-injection-search-analytics-10752204432655736267` indicates prior discovery
- Raw SQL string construction in `_build_search_query` method

---

#### VULN-002: Missing Authentication on Search Endpoints (FIXED)
**Location:** `backend/src/api/search/search.py`  
**Risk Level:** 🔴 CRITICAL  
**Status:** Fixed in commit `89fa461`

**Description:**
Previously exposed `/public/hybrid` endpoint allowed unauthenticated search access, potentially exposing sensitive documents.

**Current Mitigation:**
```python
@router.post("/authenticated/hybrid", response_model=SearchResponse)
async def authenticated_hybrid_search(
    search_request: SearchQuery,
    api_key_data: tuple = Depends(get_api_key_data),  # ✅ Now requires auth
    ...
)
```

**Residual Risk:** 
- Legacy clients may still attempt public access
- Need to monitor for unauthorized access attempts

---

### 1.2 High-Risk Vulnerabilities

#### VULN-003: Cross-Site Scripting (XSS) via Search Snippets
**Location:** Multiple - Backend highlights, Frontend rendering  
**Risk Level:** 🟠 HIGH

**Description:**
Search results include highlighted snippets with HTML markup:

```python
# Backend - fulltext_search_service.py
self.highlight_pre_tag = "<mark>"
self.highlight_post_tag = "</mark>"

# SQL template allows HTML injection
ts_headline('english', coalesce(d.content_text, ''), plainto_tsquery(:query),
    'StartSel={self.highlight_pre_tag}, StopSel={self.highlight_post_tag}...')
```

**Attack Scenario:**
1. Attacker uploads document containing `<script>alert('XSS')</script>`
2. User searches for "script"
3. PostgreSQL's `ts_headline` returns highlighted content with malicious script
4. Frontend renders unsanitized HTML

**Frontend Risk (searchService.ts):**
```typescript
// No explicit sanitization before rendering
snippet: r.content_preview || '',  // Could contain XSS payload
```

---

#### VULN-004: Information Disclosure via Error Messages
**Location:** `backend/src/api/search/search.py`  
**Risk Level:** 🟠 HIGH

**Description:**
Error handling exposes internal exception details:

```python
except Exception as e:
    logger.error(f"Error performing search: {e}")
    raise HTTPException(status_code=500, detail=str(e))  # ❌ Exposes stack trace
```

**Risks:**
- Database schema information leakage
- Service architecture exposure
- Aids reconnaissance for further attacks

---

#### VULN-005: Insufficient Rate Limiting on Search Endpoints
**Location:** `backend/src/api/search/search.py`  
**Risk Level:** 🟠 HIGH

**Description:**
Main search endpoints lack explicit rate limiting, enabling:
- Denial of Service (DoS) attacks
- Resource exhaustion
- Search-based enumeration attacks

**Current State:**
- Password reset has rate limiting (commit `290418a`)
- Search endpoints only have global API middleware rate limiting
- No per-user or per-query rate limiting

---

#### VULN-006: Insecure Direct Object Reference (IDOR) in Document Reindex
**Location:** `backend/src/api/search/search.py` - `reindex_document` endpoint  
**Risk Level:** 🟠 HIGH

**Description:**
Document ID validation relies solely on organization check:

```python
document = db.query(Document).filter(
    Document.id == document_id,
    Document.organization_id == current_user.organization_id,  # ✅ Org check
    Document.is_deleted == False
).first()
```

**Gap:** Does not verify user has explicit access to specific document (folder-level permissions, sharing status, etc.)

---

#### VULN-007: Knowledge Graph Query Injection
**Location:** `backend/src/services/search/search_service.py` - `graph_search` method  
**Risk Level:** 🟠 HIGH

**Description:**
Neo4j Cypher queries are built with string interpolation:

```python
for word in query_words[:3]:
    entity_conditions.append(f"toLower(d.title) CONTAINS '{word}'")
# Direct string interpolation without parameterization
```

**Attack Vector:**
```
Query: "test' OR 1=1 --"
Result: "toLower(d.title) CONTAINS 'test' OR 1=1 --'"
```

---

### 1.3 Medium-Risk Vulnerabilities

#### VULN-008: Excessive Data Exposure in Search Results
**Location:** `backend/src/services/search/fulltext_search_service.py`  
**Risk Level:** 🟡 MEDIUM

**Description:**
Search results return more data than necessary:
- Full metadata objects including internal IDs
- User IDs in `uploaded_by_user_id`
- Processing status details

---

#### VULN-009: Missing Input Validation on Filter Parameters
**Location:** `backend/src/models/search_schemas.py`  
**Risk Level:** 🟡 MEDIUM

**Description:**
Filter parameters lack comprehensive validation:
- No maximum limit on array sizes (tags, document_types)
- Date range validation allows unreasonable ranges
- File size filters allow negative values

---

#### VULN-010: Cache Poisoning Vulnerability
**Location:** `backend/src/services/search/search_service.py`  
**Risk Level:** 🟡 MEDIUM

**Description:**
Search results are cached without proper key isolation:

```python
cache_key = f"search:{hash(json.dumps(cache_data, sort_keys=True))}"
```

**Risks:**
- Hash collisions could return wrong results
- Malicious queries could poison cache for legitimate users

---

#### VULN-011: Insufficient Logging and Audit Trail
**Location:** Multiple search services  
**Risk Level:** 🟡 MEDIUM

**Description:**
Current logging lacks:
- Complete audit trail of sensitive searches
- Search query content for forensic analysis
- User action correlation

---

#### VULN-012: WebSocket Security Gaps
**Location:** `frontend/src/services/searchService.ts`  
**Risk Level:** 🟡 MEDIUM

**Description:**
WebSocket connection lacks validation:

```typescript
createSearchWebSocket(sessionId: string, onMessage: (update) => void): WebSocket {
    const ws = apiClient.createWebSocket(`${this.basePath}/stream/${sessionId}`);
    // No explicit auth token validation
    // No origin validation
}
```

---

#### VULN-013: Timing Attack on Search Analytics
**Location:** `backend/src/api/search/search.py` - `get_search_analytics`  
**Risk Level:** 🟡 MEDIUM

**Description:**
Different response times for existing vs non-existing organizations could reveal organization enumeration.

---

#### VULN-014: Vector Search Score Threshold Too Low
**Location:** `backend/src/services/search/hybrid_search_service.py`  
**Risk Level:** 🟡 MEDIUM

**Description:**
```python
score_threshold=0.2  # Lowered to 0.2 for more results
```
Low threshold increases risk of:
- Returning irrelevant/unintended documents
- Cross-organization data leakage in edge cases

---

#### VULN-015: Missing Content-Security-Policy for Search API
**Location:** API response headers  
**Risk Level:** 🟡 MEDIUM

**Description:**
While CSP is set in `APISecurityMiddleware`, JSON responses may not enforce proper content-type handling client-side.

---

### 1.4 Low-Risk Vulnerabilities

#### VULN-016: Verbose Debug Information in Dev Mode
**Risk Level:** 🟢 LOW

FastAPI docs exposed in dev: `/docs`, `/redoc`

#### VULN-017: Outdated Dependencies with Known CVEs
**Risk Level:** 🟢 LOW

Need periodic dependency audit.

#### VULN-018: Missing Request ID Correlation
**Risk Level:** 🟢 LOW

Search requests lack unique correlation IDs for distributed tracing.

#### VULN-019: Suboptimal Error Recovery
**Risk Level:** 🟢 LOW

Fallback mechanisms don't log sufficiently for security analysis.

---

## Part 2: Mitigation Strategies

### 2.1 Immediate Actions (Week 1-2)

#### M-001: Enhanced SQL Injection Prevention

**Implementation:**
```python
# backend/src/security/search_sanitization.py

import re
from typing import Optional
import unicodedata

class SearchQuerySanitizer:
    """Defense-in-depth search query sanitization"""
    
    # Allowlist of safe characters
    SAFE_CHARS = re.compile(r'^[a-zA-Z0-9\s\-_\.]+$')
    
    # Known SQL injection patterns
    INJECTION_PATTERNS = [
        r"(\bunion\b|\bselect\b|\binsert\b|\bupdate\b|\bdelete\b|\bdrop\b)",
        r"(--|#|/\*|\*/|;)",
        r"(\bor\b\s+\d+\s*=\s*\d+)",
        r"(\band\b\s+\d+\s*=\s*\d+)",
        r"(0x[0-9a-fA-F]+)",
        r"(\bexec\b|\bexecute\b)",
        r"(\bwaitfor\b|\bsleep\b|\bpg_sleep\b)",
    ]
    
    MAX_QUERY_LENGTH = 500
    MAX_WORD_LENGTH = 50
    MIN_WORD_LENGTH = 2
    
    @classmethod
    def sanitize(cls, query: str, strict: bool = True) -> str:
        """
        Sanitize search query with multiple defense layers.
        
        Args:
            query: Raw user input
            strict: If True, reject suspicious queries entirely
            
        Returns:
            Sanitized query string
            
        Raises:
            ValueError: If query contains injection patterns (strict mode)
        """
        if not query:
            return ""
        
        # Layer 1: Length check
        if len(query) > cls.MAX_QUERY_LENGTH:
            query = query[:cls.MAX_QUERY_LENGTH]
        
        # Layer 2: Unicode normalization (prevent bypass)
        query = unicodedata.normalize('NFKC', query)
        
        # Layer 3: Check for injection patterns
        query_lower = query.lower()
        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, query_lower, re.IGNORECASE):
                if strict:
                    raise ValueError("Query contains potentially malicious content")
                else:
                    # Remove matched content
                    query = re.sub(pattern, '', query, flags=re.IGNORECASE)
        
        # Layer 4: Character allowlist
        sanitized_words = []
        for word in query.split():
            # Remove non-alphanumeric (except allowed punctuation)
            clean_word = re.sub(r'[^\w\s\-]', '', word)
            
            if cls.MIN_WORD_LENGTH <= len(clean_word) <= cls.MAX_WORD_LENGTH:
                sanitized_words.append(clean_word)
        
        return ' '.join(sanitized_words).strip()
    
    @classmethod
    def is_safe(cls, query: str) -> bool:
        """Check if query passes all safety checks"""
        try:
            cls.sanitize(query, strict=True)
            return True
        except ValueError:
            return False
```

---

#### M-002: XSS Prevention for Search Snippets

**Backend (Python):**
```python
# backend/src/utils/html_sanitizer.py

import html
import bleach
from typing import List, Optional

class SearchSnippetSanitizer:
    """Sanitize search snippets to prevent XSS"""
    
    # Allowed tags for highlighting
    ALLOWED_TAGS: List[str] = ['mark', 'b', 'strong', 'em']
    ALLOWED_ATTRIBUTES: dict = {}
    
    @classmethod
    def sanitize_snippet(cls, snippet: str, preserve_highlights: bool = True) -> str:
        """
        Sanitize HTML snippet while preserving legitimate highlights.
        
        Args:
            snippet: Raw HTML snippet from search
            preserve_highlights: Keep <mark> tags for highlighting
            
        Returns:
            Sanitized HTML safe for rendering
        """
        if not snippet:
            return ""
        
        if preserve_highlights:
            # Use bleach to strip dangerous tags while keeping highlights
            return bleach.clean(
                snippet,
                tags=cls.ALLOWED_TAGS,
                attributes=cls.ALLOWED_ATTRIBUTES,
                strip=True
            )
        else:
            # Strip all HTML
            return html.escape(bleach.clean(snippet, tags=[], strip=True))
    
    @classmethod
    def encode_for_json(cls, text: str) -> str:
        """Encode text for safe JSON response"""
        # Escape characters that could break JSON or enable XSS
        return html.escape(text, quote=True)
```

**Frontend (TypeScript):**
```typescript
// frontend/src/utils/sanitization.ts

import DOMPurify from 'dompurify';

export const sanitizeSearchSnippet = (snippet: string): string => {
  // Configure DOMPurify to allow only safe tags
  return DOMPurify.sanitize(snippet, {
    ALLOWED_TAGS: ['mark', 'b', 'strong', 'em'],
    ALLOWED_ATTR: [],
    KEEP_CONTENT: true,
  });
};

// Use in React component
const SearchSnippet: React.FC<{ html: string }> = ({ html }) => (
  <span 
    dangerouslySetInnerHTML={{ 
      __html: sanitizeSearchSnippet(html) 
    }} 
  />
);
```

---

#### M-003: Secure Error Handling

```python
# backend/src/utils/error_handling.py

from fastapi import HTTPException
from typing import Optional
import logging
import uuid

logger = logging.getLogger(__name__)

class SearchSecurityError(Exception):
    """Base exception for search security issues"""
    pass

def create_safe_error_response(
    exception: Exception,
    request_id: Optional[str] = None,
    include_details: bool = False
) -> HTTPException:
    """
    Create safe error response without leaking internal details.
    
    Args:
        exception: Original exception
        request_id: Correlation ID for debugging
        include_details: Include error details (dev mode only)
        
    Returns:
        HTTPException with safe message
    """
    # Generate request ID if not provided
    if not request_id:
        request_id = str(uuid.uuid4())[:8]
    
    # Log full exception for debugging
    logger.error(
        f"Search error [request_id={request_id}]: {type(exception).__name__}: {str(exception)}",
        exc_info=True,
        extra={
            'request_id': request_id,
            'exception_type': type(exception).__name__,
        }
    )
    
    # Map exception types to safe messages
    error_messages = {
        'ValueError': 'Invalid search parameters',
        'SQLAlchemyError': 'Search service temporarily unavailable',
        'TimeoutError': 'Search request timed out',
        'ConnectionError': 'Search service connection failed',
    }
    
    exception_name = type(exception).__name__
    safe_message = error_messages.get(exception_name, 'Search operation failed')
    
    return HTTPException(
        status_code=500,
        detail={
            'message': safe_message,
            'request_id': request_id,
            'support_url': '/help/search-errors'
        }
    )
```

---

### 2.2 Short-Term Actions (Week 3-4)

#### M-004: Rate Limiting for Search Endpoints

```python
# backend/src/middleware/search_rate_limiter.py

from fastapi import Request, HTTPException
from datetime import datetime, timedelta
from typing import Dict, Optional
import asyncio
import redis.asyncio as redis

class SearchRateLimiter:
    """Intelligent rate limiting for search endpoints"""
    
    def __init__(
        self,
        redis_url: str,
        default_limit: int = 60,
        window_seconds: int = 60,
        burst_limit: int = 10,
        burst_window_seconds: int = 5
    ):
        self.redis = redis.from_url(redis_url)
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self.burst_limit = burst_limit
        self.burst_window_seconds = burst_window_seconds
        
        # Different limits by endpoint sensitivity
        self.endpoint_limits = {
            '/search/': 60,
            '/search/hybrid': 30,
            '/search/suggestions': 120,
            '/search/indexes/rebuild': 1,  # Admin only, very limited
            '/search/analytics': 10,
        }
    
    async def check_rate_limit(
        self,
        request: Request,
        user_id: str,
        endpoint: str
    ) -> bool:
        """
        Check if request should be rate limited.
        
        Returns:
            True if request is allowed, raises HTTPException if limited
        """
        # Get client IP for anonymous/backup tracking
        client_ip = self._get_client_ip(request)
        
        # Create rate limit keys
        user_key = f"ratelimit:search:{user_id}:{endpoint}"
        ip_key = f"ratelimit:search:ip:{client_ip}:{endpoint}"
        burst_key = f"ratelimit:burst:{user_id}:{endpoint}"
        
        # Get endpoint-specific limit
        limit = self.endpoint_limits.get(endpoint, self.default_limit)
        
        # Check burst limit first (short window)
        burst_count = await self.redis.incr(burst_key)
        if burst_count == 1:
            await self.redis.expire(burst_key, self.burst_window_seconds)
        
        if burst_count > self.burst_limit:
            raise HTTPException(
                status_code=429,
                detail={
                    'message': 'Too many requests in short period',
                    'retry_after': self.burst_window_seconds
                },
                headers={'Retry-After': str(self.burst_window_seconds)}
            )
        
        # Check standard rate limit
        pipe = self.redis.pipeline()
        pipe.incr(user_key)
        pipe.expire(user_key, self.window_seconds)
        pipe.incr(ip_key)
        pipe.expire(ip_key, self.window_seconds)
        
        results = await pipe.execute()
        user_count = results[0]
        ip_count = results[2]
        
        if user_count > limit:
            remaining = await self.redis.ttl(user_key)
            raise HTTPException(
                status_code=429,
                detail={
                    'message': f'Rate limit exceeded. Max {limit} requests per minute.',
                    'retry_after': remaining
                },
                headers={'Retry-After': str(remaining)}
            )
        
        # IP-based limit (higher, for shared IPs)
        if ip_count > limit * 3:
            remaining = await self.redis.ttl(ip_key)
            raise HTTPException(
                status_code=429,
                detail={'message': 'IP rate limit exceeded', 'retry_after': remaining},
                headers={'Retry-After': str(remaining)}
            )
        
        return True
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP with proxy awareness"""
        forwarded = request.headers.get('X-Forwarded-For')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.client.host if request.client else 'unknown'
```

---

#### M-005: Neo4j/Cypher Injection Prevention

```python
# backend/src/services/search/secure_graph_search.py

from neo4j import GraphDatabase
from typing import List, Dict, Any, Optional
import re

class SecureGraphSearch:
    """Secure Neo4j search with parameterized queries"""
    
    UNSAFE_PATTERNS = [
        r"'",  # Single quotes
        r"\\",  # Backslashes
        r"\$",  # Variables
        r"\{",  # Parameter injection
        r"//",  # Comments
        r"--",  # SQL-style comments
        r"MATCH|CREATE|MERGE|DELETE|SET|REMOVE",  # Cypher keywords
    ]
    
    def __init__(self, driver):
        self.driver = driver
    
    def sanitize_search_term(self, term: str) -> str:
        """Sanitize search term for safe Cypher usage"""
        if not term:
            return ""
        
        # Remove any characters that could be used for injection
        sanitized = re.sub(r'[^\w\s\-]', '', term)
        
        # Length limit
        return sanitized[:100].strip().lower()
    
    async def search_documents(
        self,
        query: str,
        organization_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Secure document search using parameterized Cypher.
        
        All user input is passed as parameters, never interpolated.
        """
        # Sanitize and split query
        search_terms = [
            self.sanitize_search_term(term)
            for term in query.split()
            if term.strip()
        ][:5]  # Limit number of terms
        
        # Build parameterized query (no string interpolation!)
        cypher_query = """
        MATCH (d:Document)
        WHERE d.organization_id = $org_id
        AND d.is_deleted = false
        AND (
            ANY(term IN $search_terms WHERE toLower(d.title) CONTAINS term)
            OR ANY(term IN $search_terms WHERE toLower(d.content_preview) CONTAINS term)
        )
        OPTIONAL MATCH (d)-[:CONTAINS_ENTITY]->(e:Entity)
        WITH d, collect(e) as entities
        ORDER BY size(entities) DESC, d.created_at DESC
        LIMIT $limit
        RETURN d, entities
        """
        
        with self.driver.session() as session:
            result = session.run(
                cypher_query,
                org_id=organization_id,  # Parameter, not interpolated
                search_terms=search_terms,  # Parameter list
                limit=limit
            )
            
            return [self._process_record(record) for record in result]
    
    def _process_record(self, record) -> Dict[str, Any]:
        """Process Neo4j record into safe dict"""
        doc = record['d']
        entities = record['entities']
        
        return {
            'document_id': doc.get('id'),
            'title': doc.get('title', ''),
            'entities': [e.get('name', '') for e in entities[:10]],
            'entity_count': len(entities)
        }
```

---

### 2.3 Medium-Term Actions (Month 2)

#### M-006: Comprehensive Audit Logging

```python
# backend/src/services/search/search_audit_service.py

import json
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
import logging

@dataclass
class SearchAuditEvent:
    """Structured audit event for search operations"""
    timestamp: datetime
    event_type: str
    user_id: str
    organization_id: str
    session_id: str
    query_hash: str  # Hash of query for privacy
    query_length: int
    search_type: str
    result_count: int
    search_time_ms: float
    filters_applied: Dict[str, Any]
    client_ip: str
    user_agent: str
    request_id: str
    security_flags: Dict[str, bool]
    
class SearchAuditService:
    """Comprehensive search audit logging"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.audit_logger = logging.getLogger('search.audit')
        
        # Configure structured logging
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - AUDIT - %(message)s'
        ))
        self.audit_logger.addHandler(handler)
        self.audit_logger.setLevel(logging.INFO)
    
    def log_search(
        self,
        user_id: str,
        organization_id: str,
        query: str,
        search_type: str,
        result_count: int,
        search_time_ms: float,
        request: Any,
        filters: Optional[Dict] = None,
        security_flags: Optional[Dict] = None
    ) -> None:
        """Log search event with comprehensive metadata"""
        
        event = SearchAuditEvent(
            timestamp=datetime.utcnow(),
            event_type='SEARCH_PERFORMED',
            user_id=user_id,
            organization_id=organization_id,
            session_id=self._get_session_id(request),
            query_hash=self._hash_query(query),
            query_length=len(query),
            search_type=search_type,
            result_count=result_count,
            search_time_ms=search_time_ms,
            filters_applied=filters or {},
            client_ip=self._get_client_ip(request),
            user_agent=request.headers.get('user-agent', '')[:200],
            request_id=self._get_request_id(request),
            security_flags=security_flags or {}
        )
        
        # Log to structured audit log
        self.audit_logger.info(json.dumps(asdict(event), default=str))
        
        # If security flags indicate issues, escalate
        if security_flags and any(security_flags.values()):
            self._escalate_security_event(event)
    
    def log_security_violation(
        self,
        user_id: str,
        violation_type: str,
        query: str,
        details: Dict[str, Any],
        request: Any
    ) -> None:
        """Log security violation for immediate attention"""
        
        event = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': 'SECURITY_VIOLATION',
            'violation_type': violation_type,
            'user_id': user_id,
            'query_preview': query[:50] + '...' if len(query) > 50 else query,
            'details': details,
            'client_ip': self._get_client_ip(request),
            'user_agent': request.headers.get('user-agent', '')[:100],
        }
        
        self.audit_logger.warning(f"SECURITY_VIOLATION: {json.dumps(event)}")
        self._escalate_security_event(event)
    
    def _hash_query(self, query: str) -> str:
        """Create privacy-preserving hash of query"""
        return hashlib.sha256(query.encode()).hexdigest()[:16]
    
    def _get_client_ip(self, request) -> str:
        forwarded = request.headers.get('X-Forwarded-For', '')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.client.host if request.client else 'unknown'
    
    def _get_session_id(self, request) -> str:
        return request.headers.get('X-Session-Id', 'unknown')
    
    def _get_request_id(self, request) -> str:
        return request.headers.get('X-Request-Id', 'unknown')
    
    def _escalate_security_event(self, event: Any) -> None:
        """Escalate security events to monitoring system"""
        # TODO: Integrate with SIEM/alerting system
        self.logger.warning(f"Security event escalated: {event}")
```

---

#### M-007: Enhanced Input Validation Schema

```python
# backend/src/models/search_schemas_secure.py

from pydantic import BaseModel, Field, validator, root_validator
from typing import List, Optional
from datetime import datetime, timedelta
from enum import Enum

class SecureSearchQuery(BaseModel):
    """Validated search query with security constraints"""
    
    query: str = Field(
        ...,
        min_length=2,
        max_length=500,
        description="Search query text"
    )
    
    search_type: str = Field(
        default="hybrid",
        regex="^(hybrid|fulltext|vector|knowledge_graph)$"
    )
    
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum results to return"
    )
    
    offset: int = Field(
        default=0,
        ge=0,
        le=10000,
        description="Pagination offset"
    )
    
    filters: Optional['SecureSearchFilters'] = None
    include_snippets: bool = True
    
    @validator('query')
    def validate_query(cls, v):
        """Additional query validation"""
        import re
        
        # Check for excessive special characters
        special_char_ratio = len(re.findall(r'[^\w\s]', v)) / max(len(v), 1)
        if special_char_ratio > 0.3:
            raise ValueError("Query contains too many special characters")
        
        # Check for repeated characters (potential DoS)
        if re.search(r'(.)\1{10,}', v):
            raise ValueError("Query contains excessive repeated characters")
        
        return v.strip()


class SecureSearchFilters(BaseModel):
    """Validated search filters"""
    
    document_types: Optional[List[str]] = Field(
        default=None,
        max_items=10
    )
    
    tags: Optional[List[str]] = Field(
        default=None,
        max_items=20
    )
    
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    
    file_size_min: Optional[int] = Field(
        default=None,
        ge=0,
        le=10_000_000_000  # 10GB max
    )
    
    file_size_max: Optional[int] = Field(
        default=None,
        ge=0,
        le=10_000_000_000
    )
    
    @validator('document_types', each_item=True)
    def validate_document_type(cls, v):
        allowed_types = {'pdf', 'text', 'markdown', 'docx', 'xlsx', 'image', 'audio', 'video'}
        if v.lower() not in allowed_types:
            raise ValueError(f"Invalid document type: {v}")
        return v.lower()
    
    @validator('tags', each_item=True)
    def validate_tag(cls, v):
        if len(v) > 100:
            raise ValueError("Tag too long")
        if not v.strip():
            raise ValueError("Tag cannot be empty")
        return v.strip()
    
    @root_validator
    def validate_date_range(cls, values):
        date_from = values.get('date_from')
        date_to = values.get('date_to')
        
        if date_from and date_to:
            if date_from > date_to:
                raise ValueError("date_from must be before date_to")
            
            # Prevent unreasonably large date ranges
            if (date_to - date_from) > timedelta(days=365 * 10):
                raise ValueError("Date range cannot exceed 10 years")
        
        if date_from and date_from > datetime.now():
            raise ValueError("date_from cannot be in the future")
        
        return values
    
    @root_validator
    def validate_file_size_range(cls, values):
        size_min = values.get('file_size_min')
        size_max = values.get('file_size_max')
        
        if size_min is not None and size_max is not None:
            if size_min > size_max:
                raise ValueError("file_size_min must be less than file_size_max")
        
        return values
```

---

## Part 3: Defense-in-Depth Strategy

### 3.1 Security Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                    Layer 7: Application Security                 │
│  • Input validation (Pydantic schemas)                          │
│  • XSS prevention (DOMPurify + bleach)                          │
│  • CSRF tokens                                                   │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Layer 6: API Security                         │
│  • Rate limiting (per-user, per-IP, per-endpoint)               │
│  • Request size limits                                           │
│  • Content-Type enforcement                                      │
│  • Security headers (CSP, HSTS, etc.)                           │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Layer 5: Authentication & Authorization       │
│  • JWT token validation                                          │
│  • API key authentication                                        │
│  • Role-based access control                                     │
│  • Organization isolation                                        │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Layer 4: Search-Specific Security            │
│  • Query sanitization (SQLi, NoSQLi)                            │
│  • Search scope validation                                       │
│  • Result filtering by permissions                               │
│  • Cohere reranking (security scoring)                          │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Layer 3: Data Access Control                  │
│  • Document-level permissions                                    │
│  • Collection access control                                     │
│  • Field-level encryption                                        │
│  • Query result masking                                          │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Layer 2: Database Security                    │
│  • Parameterized queries only                                    │
│  • Database user with minimum privileges                         │
│  • Connection encryption (TLS 1.2+)                             │
│  • Query logging and analysis                                    │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Layer 1: Infrastructure Security              │
│  • Network segmentation                                          │
│  • Firewall rules                                                │
│  • DDoS protection                                               │
│  • Intrusion detection                                           │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Security Controls Matrix

| Control | Layer | Implementation | Testing |
|---------|-------|----------------|---------|
| Input Validation | Application | Pydantic schemas | Unit tests |
| SQL Injection Prevention | Search | Parameterized queries | SAST/DAST |
| XSS Prevention | Application | Bleach + DOMPurify | Browser testing |
| Authentication | API | JWT + API Keys | Integration tests |
| Authorization | Search | RBAC + Org isolation | Authorization tests |
| Rate Limiting | API | Redis-based | Load tests |
| Encryption | Data | Field-level (Fernet) | Crypto tests |
| Audit Logging | All | Structured JSON | Log analysis |

---

## Part 4: Long-Term Security Roadmap

### Phase 1: Foundation (Month 1-2)

- [x] Remove unauthenticated endpoints
- [ ] Implement query sanitization layer
- [ ] Add XSS prevention for snippets
- [ ] Enhance error handling
- [ ] Deploy rate limiting

### Phase 2: Hardening (Month 3-4)

- [ ] Field-level encryption for sensitive search data
- [ ] Complete audit logging implementation
- [ ] Security-focused unit test suite
- [ ] Penetration testing
- [ ] Security awareness training for dev team

### Phase 3: Advanced Protection (Month 5-6)

- [ ] Machine learning-based anomaly detection
- [ ] Real-time threat intelligence integration
- [ ] Automated security scanning in CI/CD
- [ ] Bug bounty program launch
- [ ] SOC integration for monitoring

### Phase 4: Compliance & Certification (Month 7-12)

- [ ] SOC 2 Type II preparation
- [ ] GDPR compliance audit
- [ ] Security documentation update
- [ ] Third-party security audit
- [ ] Continuous compliance monitoring

---

## Part 5: Security Testing Strategy

### 5.1 Test Coverage Requirements

```python
# tests/security/test_search_security_comprehensive.py

import pytest
from fastapi.testclient import TestClient

class TestSearchSecuritySuite:
    """Comprehensive security test suite for search functionality"""
    
    # SQL Injection Tests
    @pytest.mark.parametrize("payload", [
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
    ])
    def test_sql_injection_prevention(self, client, payload, auth_token):
        """Test SQL injection prevention"""
        response = client.post(
            "/search/",
            json={"query": payload},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        # Should either sanitize or reject, not execute
        assert response.status_code in [200, 400]
        
        if response.status_code == 200:
            # Should not return unexpected data
            assert "password" not in str(response.json()).lower()
            assert "users" not in str(response.json()).lower()
    
    # XSS Tests
    @pytest.mark.parametrize("payload", [
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert('XSS')>",
        "<svg onload=alert('XSS')>",
        "javascript:alert('XSS')",
        "<body onload=alert('XSS')>",
        "'-alert('XSS')-'",
        "<iframe src='javascript:alert(1)'>",
    ])
    def test_xss_prevention(self, client, payload, auth_token):
        """Test XSS prevention in search results"""
        response = client.post(
            "/search/",
            json={"query": payload},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        # Check response doesn't contain executable scripts
        response_text = str(response.json())
        assert "<script>" not in response_text
        assert "javascript:" not in response_text
        assert "onerror=" not in response_text
        assert "onload=" not in response_text
    
    # Authorization Tests
    def test_cross_organization_isolation(self, client, auth_token_org_a, auth_token_org_b):
        """Verify users cannot search across organizations"""
        # Create document in org A
        # Search from org B should not find it
        pass
    
    def test_rate_limiting(self, client, auth_token):
        """Test rate limiting enforcement"""
        responses = []
        for _ in range(100):
            response = client.post(
                "/search/",
                json={"query": "test"},
                headers={"Authorization": f"Bearer {auth_token}"}
            )
            responses.append(response.status_code)
        
        # Should have some 429 responses
        assert 429 in responses, "Rate limiting not enforced"
    
    # Input Validation Tests
    @pytest.mark.parametrize("limit", [-1, 0, 1001, "abc"])
    def test_invalid_limit_rejected(self, client, limit, auth_token):
        """Test invalid limit values are rejected"""
        response = client.post(
            "/search/",
            json={"query": "test", "limit": limit},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 422  # Validation error
    
    # Authentication Tests
    def test_unauthenticated_access_denied(self, client):
        """Test unauthenticated requests are rejected"""
        response = client.post("/search/", json={"query": "test"})
        assert response.status_code == 401
    
    def test_invalid_token_rejected(self, client):
        """Test invalid JWT tokens are rejected"""
        response = client.post(
            "/search/",
            json={"query": "test"},
            headers={"Authorization": "Bearer invalid_token_here"}
        )
        assert response.status_code == 401
```

### 5.2 Automated Security Scanning

```yaml
# .github/workflows/security-scan.yml

name: Security Scan

on:
  push:
    paths:
      - 'backend/src/services/search/**'
      - 'backend/src/api/search/**'
  pull_request:
    paths:
      - 'backend/src/services/search/**'
      - 'backend/src/api/search/**'
  schedule:
    - cron: '0 0 * * *'  # Daily

jobs:
  security-scan:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Run Bandit (Python SAST)
        uses: PyCQA/bandit-action@v1
        with:
          path: 'backend/src/services/search'
          level: medium
          confidence: medium
          
      - name: Run Semgrep
        uses: returntocorp/semgrep-action@v1
        with:
          config: >-
            p/python
            p/security-audit
            p/sql-injection
            p/xss
            
      - name: Run SQLi Detection
        run: |
          pip install sqlmap
          python scripts/security/detect_sql_patterns.py
          
      - name: Run Dependency Check
        uses: dependency-check/Dependency-Check_Action@main
        with:
          project: 'RAG Search'
          path: '.'
          format: 'HTML'
          
      - name: Upload Results
        uses: actions/upload-artifact@v4
        with:
          name: security-reports
          path: reports/
```

---

## Appendix A: Security Checklist

### Pre-Deployment Checklist

- [ ] All search endpoints require authentication
- [ ] Rate limiting configured and tested
- [ ] Input validation schemas deployed
- [ ] XSS sanitization implemented
- [ ] Error messages don't leak internal details
- [ ] Audit logging enabled
- [ ] Security headers configured
- [ ] HTTPS enforced
- [ ] Database connections use TLS
- [ ] Neo4j queries use parameters

### Code Review Security Checklist

- [ ] No string interpolation in SQL/Cypher
- [ ] User input always validated before use
- [ ] Sensitive data encrypted at rest
- [ ] Proper error handling (no stack traces to client)
- [ ] Authorization checks on all endpoints
- [ ] Rate limiting considered for new endpoints
- [ ] Logging includes security context

---

## Appendix B: Incident Response

### Search Security Incident Playbook

1. **Detection**
   - Alert from rate limiting (429 spike)
   - Anomalous search patterns
   - Failed auth attempts
   - Injection detection triggers

2. **Containment**
   - Block offending IP
   - Revoke compromised tokens
   - Enable strict mode
   - Increase rate limits temporarily

3. **Investigation**
   - Review audit logs
   - Analyze query patterns
   - Check for data exfiltration
   - Document timeline

4. **Recovery**
   - Clear poisoned caches
   - Reset affected sessions
   - Update security rules
   - Deploy patches

5. **Post-Incident**
   - Root cause analysis
   - Update detection rules
   - Improve prevention
   - Document lessons learned

---

*This document should be reviewed and updated quarterly or after any significant security incident.*
