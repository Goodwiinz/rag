## 2026-01-29 - Missing IP-Based Rate Limiting on Login
**Vulnerability:** The login endpoint was rate-limited only by email address, allowing an attacker to perform credential stuffing attacks or brute force attempts against multiple accounts from a single IP address without restriction.
**Learning:** `auth_rate_limiter` in `src.core.security` uses an in-memory dictionary where the key is the identifier passed to `is_allowed`. If only email is passed, the IP is ignored.
**Prevention:** Always include IP-based rate limiting on sensitive authentication endpoints (login, register, password reset) in addition to account-based limiting. Ensure rate limiters use composite keys or multiple checks if needed.

## 2026-02-09 - User Enumeration via Timing Attack
**Vulnerability:** The authentication logic in `authenticate_user` returned early if a user was not found, before verifying the password hash. This allowed attackers to distinguish between valid and invalid email addresses by measuring the response time (valid users take longer due to bcrypt verification).
**Learning:** `bcrypt` verification is intentionally slow. Skipping it for non-existent users creates a measurable timing difference.
**Prevention:** Always perform a constant-time password verification (using a dummy hash if necessary) even if the user is not found, to ensure the response time is indistinguishable.
