# Search Security Implementation Priority Guide

## Overview

This guide provides a prioritized implementation plan for the security improvements identified in the comprehensive audit. Tasks are organized by urgency and impact.

---

## 🔴 Critical Priority (Implement Immediately - Week 1)

### 1. Enable Search Query Sanitization

**File:** `backend/src/services/search/fulltext_search_service.py`

```python
# Add at the top of the file
from src.security.search_security import SearchQuerySanitizer, SearchSecurityError

# Modify the search method
def search(self, search_request: SearchQuery, user_id: str = None, organization_id: str = None, db: Session = None) -> SearchResponse:
    start_time = time.time()

    # NEW: Sanitize query before processing
    try:
        sanitized_query = SearchQuerySanitizer.sanitize(
            search_request.query,
            strict=True
        )
        search_request.query = sanitized_query
    except SearchSecurityError as e:
        logger.warning(f"Malicious query blocked: {e}")
        return SearchResponse(
            query=search_request.query,
            search_id=str(uuid.uuid4()),
            search_type=search_request.search_type,
            results=[],
            total_results=0,
            returned_results=0,
            search_time_ms=0,
            error="Query contains invalid characters"
        )
    
    # ... rest of the method
```

**Effort:** 30 minutes  
**Impact:** Prevents SQL injection attacks

---

### 2. Add XSS Sanitization to Search Results

**File:** `backend/src/services/search/fulltext_search_service.py`

```python
from src.security.search_security import SearchSnippetSanitizer

def _row_to_search_result(self, row, search_request: SearchQuery) -> Optional[SearchResult]:
    try:
        # Existing code...
        
        # NEW: Sanitize highlighted content
        highlighted_content = SearchSnippetSanitizer.sanitize(
            row.highlighted_content or "",
            preserve_highlights=True
        )
        
        # NEW: Sanitize title highlight
        highlighted_title = SearchSnippetSanitizer.sanitize(
            row.highlighted_title or "",
            preserve_highlights=True
        )
        
        # ... use sanitized content in result
```

**Effort:** 20 minutes  
**Impact:** Prevents XSS attacks through search results

---

### 3. Fix Error Message Information Leakage

**File:** `backend/src/api/search/search.py`

Replace all instances of:
```python
except Exception as e:
    logger.error(f"Error performing search: {e}")
    raise HTTPException(status_code=500, detail=str(e))
```

With:
```python
except Exception as e:
    request_id = str(uuid.uuid4())[:8]
    logger.error(f"Search error [{request_id}]: {type(e).__name__}: {str(e)}", exc_info=True)
    raise HTTPException(
        status_code=500,
        detail={
            "message": "Search operation failed",
            "request_id": request_id,
            "support": "Contact support with this request ID"
        }
    )
```

**Effort:** 15 minutes  
**Impact:** Prevents information disclosure

---

## 🟠 High Priority (Implement This Week - Week 2)

### 4. Add Rate Limiting to Search Endpoints

**File:** `backend/src/api/search/search.py`

```python
from src.security.search_security import rate_limit_config, extract_client_ip

# Add rate limiting dependency
async def check_search_rate_limit(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Rate limiting dependency for search endpoints"""
    from src.core.redis import redis_client
    
    client_ip = extract_client_ip(request)
    user_key = f"ratelimit:search:{current_user.id}"
    ip_key = f"ratelimit:search:ip:{client_ip}"
    
    # Check user rate limit
    user_count = await redis_client.incr(user_key)
    if user_count == 1:
        await redis_client.expire(user_key, 60)
    
    if user_count > rate_limit_config.requests_per_minute:
        ttl = await redis_client.ttl(user_key)
        raise HTTPException(
            status_code=429,
            detail={"message": "Rate limit exceeded", "retry_after": ttl},
            headers={"Retry-After": str(ttl)}
        )

# Update endpoint decorators
@router.post("/", response_model=SearchResponse)
async def search_documents(
    search_request: SearchQuery,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    _rate_limit: None = Depends(check_search_rate_limit),  # NEW
    db = Depends(get_db)
):
```

**Effort:** 1 hour  
**Impact:** Prevents DoS and enumeration attacks

---

### 5. Fix Neo4j Cypher Injection

**File:** `backend/src/services/search/search_service.py`

Replace the `graph_search` method with parameterized queries:

```python
async def graph_search(
    self,
    query: str,
    filters: Optional[SearchFilters] = None,
    limit: int = 20,
    organization_id: Optional[uuid.UUID] = None
) -> SearchComponentResult:
    start_time = time.time()

    try:
        # Sanitize and extract search terms
        sanitized_query = SearchQuerySanitizer.sanitize(query, strict=True)
        search_terms = [
            term.lower()[:50]  # Limit term length
            for term in sanitized_query.split()
            if len(term) >= 2
        ][:5]  # Limit number of terms

        with neo4j_driver.session() as session:
            # FIXED: Use parameterized query
            cypher_query = """
            MATCH (d:Document)
            WHERE d.organization_id = $org_id
            AND d.is_deleted = false
            AND ANY(term IN $terms WHERE toLower(d.title) CONTAINS term)
            OPTIONAL MATCH (d)-[:CONTAINS_ENTITY]->(e:Entity)
            WITH d, collect(e) as entities
            ORDER BY size(entities) DESC, d.created_at DESC
            LIMIT $limit
            RETURN d, entities
            """

            result = session.run(
                cypher_query,
                org_id=str(organization_id) if organization_id else "",
                terms=search_terms,  # Parameter, not interpolated!
                limit=limit
            )
            # ... rest of method
```

**Effort:** 45 minutes  
**Impact:** Prevents NoSQL injection

---

### 6. Enable Comprehensive Audit Logging

**File:** `backend/src/api/search/search.py`

```python
from src.security.search_security import audit_logger, extract_client_ip

# Update the search endpoint
@router.post("/", response_model=SearchResponse)
async def search_documents(
    search_request: SearchQuery,
    request: Request,  # NEW: Add Request
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    request_id = request.headers.get('X-Request-Id', str(uuid.uuid4())[:8])
    
    try:
        # ... existing search logic ...
        
        # NEW: Audit logging in background
        background_tasks.add_task(
            audit_logger.log_search,
            user_id=str(current_user.id),
            organization_id=str(current_user.organization_id),
            query=search_request.query,
            search_type=search_request.search_type.value,
            result_count=len(result.results),
            search_time_ms=result.search_time_ms,
            client_ip=extract_client_ip(request),
            user_agent=request.headers.get('user-agent', ''),
            request_id=request_id
        )
        
        return result
    except SearchSecurityError as e:
        # NEW: Log security violations
        audit_logger.log_security_violation(
            user_id=str(current_user.id),
            violation_type=e.violation_type,
            query_preview=search_request.query[:50],
            client_ip=extract_client_ip(request),
            details={'error': str(e)}
        )
        raise HTTPException(status_code=400, detail="Invalid search query")
```

**Effort:** 1 hour  
**Impact:** Enables security monitoring and forensics

---

## 🟡 Medium Priority (Implement This Month - Week 3-4)

### 7. Enhance Input Validation Schemas

Create new file: `backend/src/models/search_schemas_secure.py`

See the comprehensive implementation in the main audit document.

**Effort:** 2 hours  
**Impact:** Defense in depth for input validation

---

### 8. Add Frontend Sanitization

**File:** `frontend/src/utils/sanitization.ts`

```typescript
import DOMPurify from 'dompurify';

export const sanitizeSearchSnippet = (html: string): string => {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ['mark', 'b', 'strong', 'em'],
    ALLOWED_ATTR: [],
    KEEP_CONTENT: true,
  });
};

export const sanitizeSearchQuery = (query: string): string => {
  // Remove potentially dangerous characters
  return query
    .replace(/[<>&'"]/g, '')
    .replace(/javascript:/gi, '')
    .substring(0, 500);
};
```

**Install DOMPurify:**
```bash
cd frontend && npm install dompurify @types/dompurify
```

**Effort:** 1 hour  
**Impact:** Client-side XSS prevention

---

### 9. Implement Secure Cache Keys

**File:** `backend/src/services/search/search_service.py`

```python
import hmac
from src.core.config import settings

def generate_secure_cache_key(
    query: str,
    search_type: str,
    organization_id: str,
    filters: Optional[Dict] = None
) -> str:
    """Generate tamper-resistant cache key"""
    cache_data = {
        'q': query,
        't': search_type,
        'o': organization_id,
        'f': json.dumps(filters, sort_keys=True) if filters else ''
    }
    
    data_string = json.dumps(cache_data, sort_keys=True)
    
    # Use HMAC for tamper resistance
    signature = hmac.new(
        settings.CACHE_SECRET_KEY.encode(),
        data_string.encode(),
        hashlib.sha256
    ).hexdigest()[:16]
    
    return f"search:{signature}"
```

**Effort:** 30 minutes  
**Impact:** Prevents cache poisoning

---

## 🟢 Low Priority (Implement Next Sprint)

### 10. Add Security Headers to API Responses

Already implemented in `APISecurityMiddleware`, verify it's applied to all search endpoints.

### 11. Implement Request ID Correlation

Add `X-Request-Id` header generation and propagation across services.

### 12. Set Up Security Scanning in CI/CD

See `.github/workflows/security-scan.yml` in the main audit document.

---

## Implementation Checklist

### Week 1
- [ ] Deploy `search_security.py` module
- [ ] Enable query sanitization in fulltext search
- [ ] Enable query sanitization in hybrid search  
- [ ] Add XSS sanitization to search results
- [ ] Fix error message leakage

### Week 2
- [ ] Implement rate limiting
- [ ] Fix Neo4j/Cypher injection
- [ ] Enable audit logging
- [ ] Add security tests

### Week 3-4
- [ ] Deploy enhanced validation schemas
- [ ] Add frontend sanitization
- [ ] Implement secure cache keys
- [ ] Update documentation

### Month 2+
- [ ] Penetration testing
- [ ] Security training
- [ ] SOC integration
- [ ] Compliance preparation

---

## Testing Verification

After each implementation, run:

```bash
# Security tests
cd backend && pytest tests/security/ -v

# Specific search security tests
pytest tests/security/test_search_security.py -v

# Full security scan
bandit -r src/services/search src/api/search -ll

# Check for SQL injection patterns
semgrep --config p/sql-injection src/
```

---

## Rollback Plan

If issues arise:

1. **Query Sanitization:** Set `strict=False` to allow queries through with logging
2. **Rate Limiting:** Increase limits or disable temporarily
3. **Audit Logging:** Runs in background tasks, safe to disable
4. **XSS Sanitization:** Fall back to `html.escape()` for all content

---

## Contact

For security concerns or questions about this implementation:
- Create an issue with the `security` label
- Check the #security channel
- Review the full audit at `docs/security/SEARCH_SECURITY_AUDIT.md`
