## 2026-01-29 - Missing IP-Based Rate Limiting on Login
**Vulnerability:** The login endpoint was rate-limited only by email address, allowing an attacker to perform credential stuffing attacks or brute force attempts against multiple accounts from a single IP address without restriction.
**Learning:** `auth_rate_limiter` in `src.core.security` uses an in-memory dictionary where the key is the identifier passed to `is_allowed`. If only email is passed, the IP is ignored.
**Prevention:** Always include IP-based rate limiting on sensitive authentication endpoints (login, register, password reset) in addition to account-based limiting. Ensure rate limiters use composite keys or multiple checks if needed.

## 2026-02-12 - Invalid SQL Bind Parameter in Interval
**Vulnerability:** The code used `INTERVAL ':days days'` in a SQL query with SQLAlchemy. Bind parameters cannot be used inside string literals or interval strings in PostgreSQL. This results in syntax errors or the parameter being ignored.
**Learning:** Avoid constructing SQL fragments that require string interpolation for parameters. Perform date/time calculations in Python and pass the resulting datetime object as a parameter.
**Prevention:** Use standard bind parameters (e.g., `:cutoff_date`) and prepare the data in the application layer.

## 2026-02-12 - Async/Sync Database Session Mismatch
**Vulnerability:** `FullTextSearchService` is a synchronous service but was importing and using the asynchronous `get_db` generator with `next()`, which causes runtime errors.
**Learning:** Verify whether database dependencies (`get_db`) are async or sync when importing them into services.
**Prevention:** Use explicit naming (e.g. `get_db_sync` vs `get_db`) and type hints to distinguish between synchronous and asynchronous database session generators.
