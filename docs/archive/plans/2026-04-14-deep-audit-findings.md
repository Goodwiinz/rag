# Deep Audit Findings — Services, Models, Dependencies, Infrastructure

**Date:** 2026-04-14
**Scope:** Backend services layer, database models, NPM dependencies, infrastructure (pending)

---

## 1. NPM Dependency Vulnerabilities

**23 vulnerabilities: 2 critical, 16 high, 4 moderate, 1 low**

| Package                                 | Severity | Issue                                                 |
| --------------------------------------- | -------- | ----------------------------------------------------- |
| `axios <=1.14.0`                        | Critical | SSRF / credential leakage                             |
| `handlebars 4.0.0-4.7.8`                | Critical | Prototype pollution                                   |
| `follow-redirects <=1.15.11`            | High     | Auth header leak on cross-domain redirect             |
| `lodash <=4.17.23`                      | High     | Prototype pollution + code injection via `_.template` |
| `lodash-es <=4.17.23`                   | High     | Same as lodash                                        |
| `hono <=4.12.11`                        | High     | Unspecified                                           |
| `ajv <6.14.0 / >=7.0.0-alpha.0 <8.18.0` | High     | ReDoS with `$data` option                             |
| `brace-expansion`                       | High     | Zero-step sequence DoS (3 instances)                  |
| `express-rate-limit 8.2.0-8.2.1`        | High     | IPv4-mapped IPv6 bypass                               |
| `flatted <=3.4.1`                       | High     | Unbounded recursion DoS                               |
| `markdown-it 13.0.0-14.1.0`             | Moderate | ReDoS                                                 |

**Fix:** `npm audit fix` for auto-fixable, manual upgrades for breaking changes.

---

## 2. Backend Services Layer (14 findings)

### P1 — Security Critical (4)

| #   | File:Line                                       | Issue                                                                                                 |
| --- | ----------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| S1  | `services/processing/processing_service.py:103` | Race condition in document status updates — concurrent requests create duplicate processing jobs      |
| S2  | `services/search/search_service.py:426`         | Missing org scoping in `graph_search()` — org_id defaults to empty string, cross-tenant Neo4j leakage |
| S3  | `services/agent/graph.py:651`                   | Tool arguments from LLM unpacked without validation — malicious payloads possible                     |
| S4  | `services/documents/file_service.py:296`        | Path traversal in `generate_file_path()` — org_id with `../` escapes upload dir                       |

### P2 — Bugs (10)

| #   | File:Line                   | Issue                                                                                    |
| --- | --------------------------- | ---------------------------------------------------------------------------------------- |
| S5  | `processing_service.py:155` | Document stuck in PENDING when Celery queue fails — no status rollback                   |
| S6  | `processing_service.py:257` | PDF fitz.open() resource leak — no finally/context manager                               |
| S7  | `search_service.py:256`     | Qdrant connection error not caught — no fallback to keyword search                       |
| S8  | `search_service.py:737`     | Cache key uses `hash()` (non-deterministic) without user_id — cross-user cache collision |
| S9  | `agent/graph.py:785`        | `tool_executions` state grows unbounded — memory leak in long conversations              |
| S10 | `agent/graph.py:775`        | Error count resets on any success — agent loops on alternating fail/succeed              |
| S11 | `file_service.py:141`       | magic.from_buffer() failure silently falls back to extension — unsafe type detection     |
| S12 | `file_service.py:202`       | File size validation before upload only — chunked upload bypasses check                  |
| S13 | `websocket_manager.py:225`  | WebSocket connection leak on auth failure                                                |
| S14 | `websocket_manager.py:530`  | Channel name not validated — protocol injection                                          |

---

## 3. Database Models (18 findings)

### P1 — Missing ON DELETE (affects 6 models, 14 ForeignKeys)

| Model           | FK Column                        | Current     | Fix      |
| --------------- | -------------------------------- | ----------- | -------- |
| `document.py`   | `organization_id`                | No ondelete | CASCADE  |
| `document.py`   | `uploaded_by_user_id`            | No ondelete | SET NULL |
| `user.py`       | `organization_id`                | No ondelete | SET NULL |
| `entity.py`     | `document_id`                    | No ondelete | CASCADE  |
| `entity.py`     | `organization_id`                | No ondelete | CASCADE  |
| `processing.py` | `document_id`                    | No ondelete | CASCADE  |
| `processing.py` | `organization_id`                | No ondelete | CASCADE  |
| `processing.py` | `created_by_user_id`             | No ondelete | SET NULL |
| `search.py`     | `user_id`                        | No ondelete | CASCADE  |
| `search.py`     | `organization_id`                | No ondelete | CASCADE  |
| `search.py`     | `document_id` (SearchResult)     | No ondelete | CASCADE  |
| `search.py`     | `search_query_id` (SearchResult) | No ondelete | CASCADE  |
| `thread.py`     | `created_by_id`                  | No ondelete | SET NULL |
| `entity.py`     | entity_relationships association | No ondelete | CASCADE  |

### P2 — Missing Indexes (6 models)

| Model           | Missing Index                   | Query Pattern                     |
| --------------- | ------------------------------- | --------------------------------- |
| `thread.py`     | `(conversation_id, status)`     | Thread listing with status filter |
| `thread.py`     | `(conversation_id, created_at)` | Thread ordering                   |
| `processing.py` | `(status, created_at)`          | Processing queue                  |
| `processing.py` | `(job_type, organization_id)`   | Job monitoring                    |
| `entity.py`     | `(organization_id, name)`       | Entity search                     |
| `workspace.py`  | `(owner_id, is_archived)`       | Workspace listing                 |

### P3 — Constraints

| Model          | Issue                                                                                                           |
| -------------- | --------------------------------------------------------------------------------------------------------------- |
| `workspace.py` | `WorkspaceMember` unique_together not enforced at DB level — need `UniqueConstraint('workspace_id', 'user_id')` |

---

## 4. Infrastructure (7 findings)

### P1 — Secrets Exposure (2)

| #   | File:Line                                                                 | Issue                                                                        |
| --- | ------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| I1  | `infrastructure/helm/knowledge-graph-analytics/values-production.yaml:71` | Hardcoded Supabase JWT anon key in production helm values — committed to git |
| I2  | `frontend/.env.local:3`                                                   | Same Supabase anon key exposed locally                                       |

**Action:** Rotate the Supabase anon key in the Supabase dashboard immediately. Move to ExternalSecrets.

### P2 — Docker / K8s (4)

| #   | File:Line                                                       | Issue                                                                                              |
| --- | --------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| I3  | `backend/docker/Dockerfile:40-46`                               | Dev dependencies (`requirements.dev.txt`) installed in production image — increases attack surface |
| I4  | `backend/src/core/config.py:73`                                 | Missing DATABASE_URL validation at startup in production                                           |
| I5  | `infrastructure/kubernetes/secrets.yaml`                        | Secret structure in git (placeholders, but still exposes schema)                                   |
| I6  | `infrastructure/kubernetes/base/backend/network-policy.yaml:92` | Egress allows 0.0.0.0/0 on port 8080 — overly broad                                                |

### P3 — Hardening (3)

| #   | File:Line                 | Issue                                                        |
| --- | ------------------------- | ------------------------------------------------------------ |
| I7  | `backend/src/main.py:293` | Wildcard TrustedHost `*.gen-text.app` — allows any subdomain |
| I8  | `frontend/nginx.conf:41`  | CSP has `'unsafe-inline'` and `http:` — too permissive       |
| I9  | `frontend/nginx.conf`     | Missing HSTS header (`Strict-Transport-Security`)            |

### Positive findings

- CORS properly configured (explicit origins, no wildcards)
- JWT secret validation enforced in production
- Neo4j password validation enforced in production
- K8s security context: non-root, capability dropping, read-only rootfs
- Network policies implemented with namespace isolation
- ExternalSecrets operator configured (but not consistently used)

---

## Recommended Fix Priority

### EMERGENCY — Rotate Secrets

0. **Rotate Supabase anon key** (I1, I2) — do this in Supabase dashboard NOW, then update ExternalSecrets

### Immediate — Security (service layer P1s)

1. **Path traversal in file_service** (S4) — validate org_id is UUID format
2. **Graph search org scoping** (S2) — require non-null org_id, raise if missing
3. **Processing race condition** (S1) — add `SELECT ... FOR UPDATE` row locking
4. **NPM critical vulnerabilities** — `npm audit fix`, manual upgrade axios + handlebars

### Short-term — Data Integrity

5. **Add ON DELETE to all ForeignKeys** — one Alembic migration, 14 FKs
6. **Add missing composite indexes** — one Alembic migration, 6 indexes
7. **Cache key fix** (S8) — include user_id, use hashlib.md5 instead of hash()
8. **Document stuck in PENDING** (S5) — set status to FAILED on queue failure

### Medium-term — Hardening

9. **Tool argument validation** (S3) — Pydantic schema per tool before execution
10. **NPM high vulnerabilities** — upgrade lodash, follow-redirects, ajv, etc.
11. **Resource leaks** (S6, S9, S13) — fitz context manager, tool_executions pruning, WS cleanup
12. **Dev deps out of prod Docker** (I3) — separate builder from prod in Dockerfile
13. **DATABASE_URL validation** (I4) — add startup check in config.py
14. **CSP + HSTS headers** (I8, I9) — tighten nginx.conf
15. **File size re-validation** (S12) — check actual size after write
