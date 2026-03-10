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

## 2026-02-10 - Critical Authorization Bypass in API Key Search

**Vulnerability:** API keys created by administrators were not scoped to their organization. When performing a search via `authenticated_hybrid_search`, the `organization_id` was explicitly set to `None`, bypassing the organization filter in `fulltext_search_service`. This allowed any API key holder to search across ALL organizations (IDOR / Multi-tenancy Isolation Failure).

**Learning:** Explicitly passing `None` as a filter value (`organization_id=None`) must be carefully reviewed. In this codebase, `None` often means "no filter" (i.e., "all data"), which is dangerous in a multi-tenant system. API keys were assumed to be "global" or controlled by some other permission mechanism that didn't exist.

**Prevention:**
1.  Always associate API keys with an `organization_id` upon creation.
2.  Enforce organization scoping at the API entry point by extracting the organization ID from the authenticated credential (token or API key).
3.  Avoid "superuser" defaults (like `organization_id=None`) in business logic services unless explicitly intended for system admin features.

## 2026-05-24 - Critical Authorization Logic Inversion

**Vulnerability:** The `bulk_delete_documents` endpoint contained inverted logic: `if current_user.has_permission(UserRole.ADMIN): raise Forbidden`. This blocked administrators from performing the action while allowing unauthorized users to bypass the check. A similar issue existed in `reprocess_document`.

**Learning:** Manual permission checks using `if` statements are prone to logic errors (missing `not`). The absence of comprehensive negative test cases (testing that unauthorized users are BLOCKED) allowed this critical vulnerability to persist.

**Prevention:**
1.  Use a declarative permission system (decorators or middleware) where intent is clearer (e.g., `@require_role(UserRole.ADMIN)`).
2.  Mandate negative test cases for all authorization logic.
3.  Perform code reviews specifically targeting authorization logic for double negatives or inverted conditions.

## 2024-05-22 - [Rate Limiting IP Spoofing]
**Vulnerability:** Rate limiting relied on `request.client.host`, which returns the load balancer's IP in production, causing global rate limiting instead of per-user.
**Learning:** In containerized environments with reverse proxies (Traefik/Nginx), the real client IP is in `X-Forwarded-For`. The last IP in this list is the only one guaranteed to be the connecting client (added by the trusted proxy).
**Prevention:** Use a centralized `get_client_ip` utility that parses `X-Forwarded-For` (taking the last entry) before falling back to `request.client.host`.

## 2024-05-18 - [API Key IDOR Vulnerability]
**Vulnerability:** Insecure Direct Object Reference (IDOR) found in API Key management endpoints (`backend/src/api/auth/api_keys.py`).
**Learning:** Endpoints restricted by role decorators like `Depends(require_admin)` do not automatically scope database queries to the user's tenant/organization. Relying solely on role checks is insufficient for tenant isolation.
**Prevention:** In SQLAlchemy queries for tenant-isolated models, always explicitly append `.filter(Model.organization_id == str(current_user.organization_id))` regardless of whether the user holds admin privileges.
