## 2026-01-29 - Missing IP-Based Rate Limiting on Login
**Vulnerability:** The login endpoint was rate-limited only by email address, allowing an attacker to perform credential stuffing attacks or brute force attempts against multiple accounts from a single IP address without restriction.
**Learning:** `auth_rate_limiter` in `src.core.security` uses an in-memory dictionary where the key is the identifier passed to `is_allowed`. If only email is passed, the IP is ignored.
**Prevention:** Always include IP-based rate limiting on sensitive authentication endpoints (login, register, password reset) in addition to account-based limiting. Ensure rate limiters use composite keys or multiple checks if needed.
