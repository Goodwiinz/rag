## 2026-01-30 - Missing Rate Limiting on Login Endpoint

**Vulnerability:** The `/api/v1/auth/login` endpoint was not enforcing rate limiting, despite having logic to retrieve the client IP. The `auth_rate_limiter.is_allowed(client_ip)` check was missing.

**Learning:** The rate limiter was instantiated but not called. This suggests a copy-paste error or an oversight during implementation, where the intent (getting client IP) was present but the enforcement was missed.
Also, testing this endpoint proved difficult because the codebase has side effects on import (instantiating DB clients like Qdrant and Neo4j), which makes isolated unit testing challenging without extensive mocking.

**Prevention:**
1.  Ensure all sensitive endpoints (login, register, reset password) explicitly call the rate limiter.
2.  Implement architectural changes to avoid side effects on import (e.g., lazy initialization of clients), facilitating easier unit testing.
3.  Add integration tests that specifically target rate limiting behavior.

## 2026-02-04 - Missing Rate Limiting on Password Reset Endpoint

**Vulnerability:** The `/api/v1/auth/reset-password` endpoint was completely missing rate limiting. This allowed unauthenticated users to trigger unlimited password reset emails (DoS risk) and potential timing attacks to enumerate users.

**Learning:** While other auth endpoints had rate limiting logic (even if sometimes buggy), this one was missed entirely. It likely wasn't copy-pasted from the others or was added later without security review.
Testing required extensive mocking of `sys.modules` to bypass database connection side-effects during import.

**Prevention:**
1.  Standardize authentication endpoint implementation using a common base or decorator that enforces rate limiting by default.
2.  Audit all endpoints in `auth.py` to ensure consistency.
3.  Use automated security scanning to detect missing rate limits on sensitive endpoints.
