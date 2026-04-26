# Backend Bug Audit — Codex Review Findings

**Goal:** Fix all P1/P2 bugs found by systematic Codex review of the backend API layer (85 files, 15 modules).

**Date:** 2026-04-14

**Coverage:** 4 of 5 audit groups completed. Agent + Streaming module needs manual review (Codex limit hit).

**Status Legend:** OPEN = needs fix | DEFERRED = needs architectural decision or separate PR

---

## P1 Bugs — Broken Functionality / Security Critical (11 total)

### Auth + Security (3)

| #   | File:Line                     | Issue                                                                                                                             |
| --- | ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| A1  | `security/encryption.py:155+` | All `@require_permission` decorators commented out — any authenticated user can encrypt/decrypt PII, rotate keys, read audit logs |
| A2  | `security/encryption.py:168`  | `content_manager` role can decrypt SSNs, passports, bank accounts — should be admin-only                                          |
| A3  | `auth/cli_auth.py:47`         | Rate limiter uses shared `"unknown"` bucket for proxy clients — bypasses per-IP limiting                                          |

### Documents + Files (4)

| #   | File:Line                 | Issue                                                                                                                                               |
| --- | ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | `documents/files.py:278`  | `delete_file` uses undefined `db` variable — NameError on every call, endpoint completely broken                                                    |
| D2  | `documents/files.py:187+` | `is_public` documents bypass org check — cross-tenant data leak via 4 endpoints (get_file_info, download_file, get_file_content, get_file_metadata) |
| D3  | `documents/files.py:250`  | `update_file_metadata` no org check — admin in Org B can modify Org A documents                                                                     |
| D4  | `documents/files.py:340`  | `reprocess_file` no org scoping — cross-tenant reprocessing                                                                                         |

### Search + Analytics (2)

| #   | File:Line                             | Issue                                                                                                                              |
| --- | ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| S1  | `quality/user_behavior.py:174`        | Broken auth: `current_user.organization_id != current_user.organization_id` always false — any user views any user's behavior data |
| S2  | `analytics/metrics.py:66,190,330,384` | 5 endpoints crash with NameError — `get_async_session`, `select`, `AnalyticsMetric`, `AnalyticsKPI` never imported                 |

### Threads + Research (2)

| #   | File:Line                     | Issue                                                                                               |
| --- | ----------------------------- | --------------------------------------------------------------------------------------------------- |
| T1  | `realtime/websocket.py:50`    | WebSocket v1 accepts token in URL query params — violates security policy, tokens logged by proxies |
| T2  | `research_engine/runs.py:250` | Resume endpoint is a no-op — sets status to PAUSED (same value), run never actually resumes         |

---

## P2 Bugs — Likely Bug / Data Issue (32 total)

### Auth + Security (7)

| #   | File:Line                         | Issue                                                                                         |
| --- | --------------------------------- | --------------------------------------------------------------------------------------------- |
| A4  | `auth/cli_auth.py:93`             | Raw Supabase access token returned in `/approve` response body and stored in pollable session |
| A5  | `auth/api_keys.py`                | Sync DB calls (`db.query`, `db.commit`) in async endpoints — blocks event loop or crashes     |
| A6  | `auth/tenant_management.py:139+`  | No cross-tenant IDOR check — admin of Org A can read/modify Org B                             |
| A7  | `security/rbac_management.py:266` | Raw SQL string in role update (parameterized but fragile)                                     |
| A8  | `security/compliance.py:316+`     | `desc`, `func`, `and_` not imported — endpoints crash with NameError                          |
| A9  | `security/compliance.py:310`      | `status` param shadows `fastapi.status` module                                                |
| A10 | `security/encryption.py:168`      | No org-scoping on encrypt/decrypt — cross-tenant PII modification                             |

### Documents + Files (13)

| #   | File:Line                          | Issue                                                               |
| --- | ---------------------------------- | ------------------------------------------------------------------- |
| D5  | `documents/files.py:160`           | Broad `except` swallows 403/413 as 400, leaks `str(e)`              |
| D6  | `documents/files.py:180`           | LIKE pattern not escaped — wildcard injection in search             |
| D7  | `documents/files.py`               | Route ordering: `/files/stats` may be shadowed by `/{file_id}`      |
| D8  | `documents/documents.py`           | Same LIKE escaping issue                                            |
| D9  | `documents/documents.py`           | `DocumentResponse` returns raw enum values, frontend expects mapped |
| D10 | `documents/documents.py`           | Returns `uploaded_by_user_id`, frontend expects `user_id`           |
| D11 | `documents/document_upload.py:175` | Sync `Session` in async endpoints — blocks event loop               |
| D12 | `documents/document_upload.py`     | Upload progress in process memory — broken in multi-worker          |
| D13 | `documents/document_upload.py:295` | WebSocket progress endpoint has no authentication                   |
| D14 | `documents/table_extraction.py:50` | Missing org scoping, uses `uploaded_by_user_id` only                |
| D15 | `documents/table_extraction.py:60` | `file_path` used without path traversal validation                  |
| D16 | `documents/integrity.py:48`        | Missing org scoping, uses `uploaded_by_user_id` only                |
| D17 | `documents/processing.py:60`       | `start_document_processing` no org scoping                          |

### Search + Analytics (12)

| #   | File:Line                        | Issue                                                              |
| --- | -------------------------------- | ------------------------------------------------------------------ |
| S3  | `search/vectors.py:109`          | Double `get_collection_stats()` per collection — 2x Qdrant RPCs    |
| S4  | `search/vectors.py:44`           | `str(e)` in 500 responses leaks internal details (15+ occurrences) |
| S5  | `analytics/metrics.py:67`        | No org-scoping on metrics — any user sees all orgs                 |
| S6  | `analytics/metrics.py:228`       | `ingest_batch_values` accepts unbounded list — no size limit       |
| S7  | `analytics/metrics.py:349`       | N+1: `_calculate_kpi_value()` per KPI in loop                      |
| S8  | `analytics/metrics.py:401`       | `status` variable shadows `fastapi.status`                         |
| S9  | `quality/user_behavior.py:39`    | Manual `db = next(get_db())` — `UnboundLocalError` in finally      |
| S10 | `quality/user_behavior.py:213`   | Role check uses `"ADMIN"` uppercase but enum may be lowercase      |
| S11 | `quality/user_behavior.py:369`   | N+1: 400 sequential `analyze_user_behavior` calls                  |
| S12 | `quality/quality_metrics.py:119` | `limit` allows 10,000 rows with no pagination                      |
| S13 | `quality/quality_metrics.py:319` | Dashboard makes 5 sequential service calls, no parallelism         |
| S14 | `search/search.py:329`           | In-memory `search_analytics_store` grows unbounded — memory leak   |

### Threads + Research (10)

| #   | File:Line                      | Issue                                                                          |
| --- | ------------------------------ | ------------------------------------------------------------------------------ |
| T3  | `realtime/websocket_v2.py:267` | Broadcast endpoint missing admin check — any user can broadcast to any channel |
| T4  | `threads/thread_search.py:69`  | Sync `Session` in async endpoints                                              |
| T5  | `threads/thread_search.py:299` | LIKE wildcard injection in search suggestions                                  |
| T6  | `threads/stream.py:37`         | `_active_streams` in-memory set — broken in multi-worker                       |
| T7  | `threads/workspaces.py:131`    | `list_workspaces` doesn't filter soft-deleted memberships                      |
| T8  | `research_engine/runs.py:310`  | SSE generator uses `Depends(get_db)` session — may close mid-stream            |
| T9  | `research_engine/runs.py:340`  | `db.refresh(run)` race condition with concurrent pause                         |
| T10 | `research/citations.py:210`    | Pagination done in Python, not SQL — loads all citations into memory           |
| T11 | `research/citations.py:143`    | No access control on citation creation — user A can reference user B's data    |
| T12 | `arxiv/core.py:95`             | No auth or rate limiting on ArXiv search proxy endpoint                        |

---

## NOT YET AUDITED

### Agent + Streaming (Codex limit hit — manual review needed)

| File                     | Focus Areas                                               |
| ------------------------ | --------------------------------------------------------- |
| `agent/execute.py`       | Auth, tool execution security, timeout handling           |
| `agent/streaming.py`     | SSE resource leaks, error event handling, HITL flow       |
| `agent/jobs.py`          | Job state management, auth                                |
| `agent/tools_impl.py`    | Command injection, path traversal in tool implementations |
| `agent/tool_helpers.py`  | Input validation                                          |
| `agent/trace_context.py` | Data exposure in trace payloads                           |

---

## P3 Bugs (26 total — not listed individually)

Key themes:

- `/health` endpoints with no auth (6 occurrences)
- `datetime.utcnow()` naive datetime inconsistency (5 occurrences)
- `str(e)` in error responses leaking internals (8 occurrences)
- Debug endpoint exposed in production (`/files/debug-auth`)
- Missing `await` on async session calls
- `asyncio.get_event_loop()` deprecated usage

---

## Recommended Fix Priority

### Immediate (security-critical)

1. **Encryption permission bypass (A1, A2)** — uncomment `@require_permission` decorators, remove `content_manager` from PII access
2. **Cross-tenant IDOR cluster (D2, D3, D4, A6, A10)** — add org-scoping to all file/tenant/encryption endpoints
3. **Broken auth check (S1)** — fix `user_behavior.py:174` self-comparison
4. **WebSocket token in URL (T1)** — migrate to `Sec-WebSocket-Protocol` header auth

### High (broken endpoints)

5. **delete_file NameError (D1)** — add `db: AsyncSession = Depends(get_db)` to function signature
6. **metrics.py missing imports (S2)** — add `get_async_session`, `select`, model imports
7. **compliance.py missing imports (A8)** — add `desc`, `func`, `and_` imports
8. **Resume no-op (T2)** — set status to RUNNING after resume

### Medium (data integrity + performance)

9. **Sync/async misuse (A5, D11, T4)** — migrate to async session or mark endpoints as sync
10. **Broadcast admin check (T3)** — add role verification
11. **Unauthenticated WebSocket (D13)** — add auth to upload progress WebSocket
12. **N+1 queries (S7, S11, S3)** — batch KPI calculation, user behavior analysis, collection stats
13. **LIKE escaping (D6, D8, T5)** — escape `%` and `_` in user search input

### Low (hardening)

14. **Remove debug endpoint (D7/files.py:375)**
15. **Cap unbounded queries (S6, S12, S14)**
16. **ArXiv rate limiting (T12)**
17. **Citation access control (T11)**

---

## Verification

After implementing fixes:

```bash
# Run backend tests
cd backend && pytest tests/ -v --tb=short

# Check for import errors
cd backend && python -c "from src.api.analytics.metrics import router; print('OK')"
cd backend && python -c "from src.api.security.compliance import router; print('OK')"

# Security smoke test
# 1. Try accessing encryption endpoints as non-admin user — should get 403
# 2. Try listing documents from different org — should get 404
# 3. Try WebSocket v1 with Sec-WebSocket-Protocol instead of query param
# 4. Try user_behavior endpoint as user from different org — should get 403
```
