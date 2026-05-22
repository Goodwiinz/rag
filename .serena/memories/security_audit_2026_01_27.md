# Security Audit Summary (2026-01-27)

Bandit v1.9.3 scan: 145K LOC, 187 issues (21 High, 49 Medium, 117 Low)

## Critical (P1) — Fixed
- **GOO-152**: Jinja2 XSS → enabled autoescape (export_service.py)
- **GOO-153**: XXE in ArXiv XML → switched to defusedxml
- **GOO-154**: Pickle RCE → added HMAC-SHA256 signatures (caching.py)

## High (P2) — Linear tracked
- **GOO-155**: MD5 usage (21 instances) — use SHA-256/Blake2b for security-critical
- **GOO-156**: Network binding 0.0.0.0 (11 services) — env-based config for prod

## Medium (P3)
- **GOO-157**: Hardcoded /tmp paths — use tempfile module

## Other Linear Issues (from reviews)
- GOO-62: Shell injection in verify-fix.sh
- GOO-63-67: Various parser, WebSocket, schema issues
- GOO-68-74: Credential leaks, validation, config issues

See Linear project "Goodwiinz" for current status of all issues.
