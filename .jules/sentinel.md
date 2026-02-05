## 2026-01-30 - Missing Rate Limiting on Login Endpoint

**Vulnerability:** The `/api/v1/auth/login` endpoint was not enforcing rate limiting, despite having logic to retrieve the client IP. The `auth_rate_limiter.is_allowed(client_ip)` check was missing.

**Learning:** The rate limiter was instantiated but not called. This suggests a copy-paste error or an oversight during implementation, where the intent (getting client IP) was present but the enforcement was missed.
Also, testing this endpoint proved difficult because the codebase has side effects on import (instantiating DB clients like Qdrant and Neo4j), which makes isolated unit testing challenging without extensive mocking.

**Prevention:**
1.  Ensure all sensitive endpoints (login, register, reset password) explicitly call the rate limiter.
2.  Implement architectural changes to avoid side effects on import (e.g., lazy initialization of clients), facilitating easier unit testing.
3.  Add integration tests that specifically target rate limiting behavior.
## 2026-02-04 - Unauthenticated Full Database Access via Public Search Endpoint

**Vulnerability:** A "public" endpoint `/api/v1/search/public/hybrid` was exposed for "evaluation purposes". It called `hybrid_search_service.search` with `organization_id=None`. The underlying services (`FullTextSearchService`) interpreted `organization_id=None` as "no filter", effectively returning documents from ALL organizations to unauthenticated users.

**Learning:** "Test" or "Evaluation" endpoints that bypass security controls must NEVER be included in the main application router, especially if they are not guarded by authentication or compile flags. Service layer methods should be defensive: `organization_id=None` should probably raise an error or return nothing, rather than everything, unless explicitly intended (e.g., `ignore_org_filter=True`).

**Prevention:**
1.  Remove all "public" evaluation endpoints from production code.
2.  Audit service methods to ensure `None` parameters do not default to "allow all". Default to "deny all" (return empty list) if a required context filter is missing.
3.  Implement strict separation of test/evaluation routes, possibly using a separate router that is not included in the main app unless a specific env var (e.g. `ENABLE_TEST_ROUTES`) is set.
