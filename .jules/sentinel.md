## 2024-05-23 - Authentication Timing Attack
**Vulnerability:** User enumeration via timing attack in `AuthService.authenticate_user`.
**Learning:** Short-circuiting logic (`if not user or ...`) prevented password verification for non-existent users, causing a significant response time difference compared to valid users (due to bcrypt hashing cost).
**Prevention:** Always perform a password verification step with the same computational cost (using a pre-calculated dummy hash) regardless of whether the user exists.
