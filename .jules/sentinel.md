## 2026-01-29 - Missing IP-Based Rate Limiting on Login
**Vulnerability:** The login endpoint was rate-limited only by email address, allowing an attacker to perform credential stuffing attacks or brute force attempts against multiple accounts from a single IP address without restriction.
**Learning:** `auth_rate_limiter` in `src.core.security` uses an in-memory dictionary where the key is the identifier passed to `is_allowed`. If only email is passed, the IP is ignored.
**Prevention:** Always include IP-based rate limiting on sensitive authentication endpoints (login, register, password reset) in addition to account-based limiting. Ensure rate limiters use composite keys or multiple checks if needed.

## 2024-05-22 - [IP Spoofing via X-Forwarded-For]
**Vulnerability:** Implementing IP detection by taking the *first* IP in `X-Forwarded-For` when behind a trusted proxy allows attackers to spoof their IP by sending a fake header, as proxies typically append the real IP to the end.
**Learning:** Standard proxies like Nginx and AWS ALB append the client IP to the existing `X-Forwarded-For` header. Trusting the first IP (`[0]`) assumes the header was replaced or the chain is fully trusted, which is often not the case for the initial value.
**Prevention:** When traversing `X-Forwarded-For` behind a trusted proxy (that appends), trust the **last** IP (`[-1]`) in the list as the one added by the trusted proxy.
