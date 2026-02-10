## 2026-01-30 - Missing Rate Limiting on Login Endpoint

**Vulnerability:** The `/api/v1/auth/login` endpoint was not enforcing rate-limiting, despite having logic to retrieve the client IP. The `auth_rate_limiter.is_allowed(client_ip)` check was missing.

**Learning:** The rate limiter was instantiated but not called. This suggests a copy-paste error or an oversight during implementation, where the intent (getting client IP) was present but the enforcement was missed.
Also, testing this endpoint proved difficult because the codebase has side effects on import (instantiating DB clients like Qdrant and Neo4j), which makes isolated unit testing challenging without extensive mocking.

**Prevention:**
1.  Ensure all sensitive endpoints (login, register, reset password) explicitly call the rate-limiter.
2.  Implement architectural changes to avoid side effects on import (e.g., lazy initialization of clients), facilitating easier unit testing.
3.  Add integration tests that specifically target rate limiting behavior.

## 2026-01-29 - Missing IP-Based Rate Limiting on Login

**Vulnerability:** The login endpoint was rate-limited only by email address, allowing an attacker to perform credential stuffing attacks or brute force attempts against multiple accounts from a single IP address without restriction.

**Learning:** `auth_rate_limiter` in `src.core.security` uses an in-memory dictionary where the key is the identifier passed to `is_allowed`. If only email is passed, the IP is ignored.

**Prevention:** Always include IP-based rate limiting on sensitive authentication endpoints (login, register, password reset) in addition to account-based limiting. Ensure rate limiters use composite keys or multiple checks if needed.

## 2026-02-09 - User Enumeration via Timing Attack

**Vulnerability:** The authentication logic in `authenticate_user` returned early if a user was not found, before verifying the password hash. This allowed attackers to distinguish between valid and invalid email addresses by measuring the response time (valid users take longer due to bcrypt verification).

**Learning:** `bcrypt` verification is intentionally slow. Skipping it for non-existent users creates a measurable timing difference.

**Prevention:** Always perform a constant-time password verification (using a dummy hash if necessary) even if the user is not found, to ensure the response time is indistinguishable.

## 2025-02-18 - Missing Rate-Limiting on Password Reset

**Vulnerability:** The `/api/v1/auth/reset-password` endpoint lacked rate-limiting, similar to the previous login endpoint issue.

**Learning:** Authentication endpoints are inconsistently protected. The `auth_rate_limiter` exists but manual application is error-prone. The integration testing environment is fragile due to circular imports, forcing the use of isolated unit tests that avoid importing `src.main`.

**Prevention:** Consider using a decorator or middleware for rate-limiting sensitive auth endpoints to ensure consistent application, rather than manual checks in each controller. Refactor codebase to remove circular dependencies to enable robust integration testing.
