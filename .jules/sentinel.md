## 2026-01-29 - Missing IP-Based Rate Limiting on Login
**Vulnerability:** The login endpoint was rate-limited only by email address, allowing an attacker to perform credential stuffing attacks or brute force attempts against multiple accounts from a single IP address without restriction.
**Learning:** `auth_rate_limiter` in `src.core.security` uses an in-memory dictionary where the key is the identifier passed to `is_allowed`. If only email is passed, the IP is ignored.
**Prevention:** Always include IP-based rate limiting on sensitive authentication endpoints (login, register, password reset) in addition to account-based limiting. Ensure rate limiters use composite keys or multiple checks if needed.

## 2026-02-14 - Insecure Client IP Resolution
**Vulnerability:** The application used `request.client.host` directly for rate limiting, which returns the IP address of the immediate connection. When deployed behind a load balancer or reverse proxy, this IP is always the proxy's IP, causing all users to share the same rate limit and enabling Denial of Service.
**Learning:** `request.client.host` is not reliable for client identification in proxy environments. `X-Forwarded-For` must be parsed, but only if the immediate peer is trusted.
**Prevention:** Use a secure `get_client_ip` utility that validates the proxy chain against a `TRUSTED_PROXIES` configuration before trusting `X-Forwarded-For` headers.
