# Fix Plan — 5 Critical Code Quality Issues

## Context

A code-reviewer audit of the NOUS Multimodal RAG backend (~230K LOC) surfaced **5 critical defects** that would ship silently to production. Three Explore agents verified each finding against current code. The dominant pattern is **silent failure**: tenant isolation is bypassed without logging, JWT signs with a known secret if env vars aren't set, and an async-generator misuse swallows itself in a broad `except Exception`. None of these would page on-call — they would just degrade security.

This plan fixes all 5 in a single coherent security hardening sprint, reusing existing utilities (`AsyncSessionLocal`, `tenant_context_manager`, `RelationshipType` enum, `query_graph` adapter) wherever they exist rather than introducing parallel implementations.

**Open design decisions** (flagged inline; user can redirect at ExitPlanMode):

- **Multi-tenancy scope**: Default approach parses JWT inline in `_extract_tenant_info` (smallest diff, makes tenant validation actually work). Alternative: add new AuthMiddleware.
- **Bundling**: Default is single PR with 5 atomic commits. Alternative: split by risk area.

---

## Fix 1 — CRITICAL-1: Cypher Injection in KnowledgeGraphTool

**File:** `backend/src/services/search/multi_agent_search_service.py:147-169`

**Problem:** `entity_name` and `relationship_type` are interpolated into Cypher via f-strings. Attacker-controlled input can run `DETACH DELETE` to wipe the graph.

**Fix:**

1. Replace f-string Cypher with parameterized queries — Neo4j driver supports `session.run(query, params)` natively (already used elsewhere in `knowledge_graph_service.py:304`).
2. Validate `relationship_type` against the existing `RelationshipType` enum at `backend/src/models/graph.py` (8 valid values: WORKS_FOR, KNOWS, RELATED_TO, LOCATED_IN, PART_OF, MENTIONED_IN, APPEARS_WITH, CREATED_BY) before any string interpolation.
3. Prefer routing through the existing safe `knowledge_graph_service.query_graph()` adapter at `knowledge_graph_service.py:1870-1893` which doesn't execute raw Cypher.

**Reuse:** `RelationshipType` enum, `query_graph()` adapter — both already exist.

---

## Fix 2 — HIGH-5 (bundled with Fix 1): Tenant Leak in SearchTool

**File:** `backend/src/services/search/multi_agent_search_service.py:119-120`

**Problem:** `SearchTool._run()` hardcodes `user_id="multi_agent_user"`, `organization_id="default_org"`. Every CrewAI search bypasses tenant filtering — cross-org data leak.

**Constraint:** CrewAI `BaseTool` (`name`, `description`, `_run()` only) does NOT support Pydantic field injection or `RunnableConfig` like LangGraph does. Tools cannot accept context via the agent prompt mechanism.

**Fix:** Construct per-request `SearchTool` instances bound to the current tenant. In `MultiAgentSearchOrchestrator.orchestrate_search` (which already receives `user_id` and `organization_id` at line 322-323), instantiate the tool with bound context:

```python
class SearchTool(BaseTool):
    name: str = "hybrid_search"
    description: str = "..."
    _user_id: str = PrivateAttr()
    _organization_id: str = PrivateAttr()

    def __init__(self, user_id: str, organization_id: str, **data):
        super().__init__(**data)
        self._user_id = user_id
        self._organization_id = organization_id

    def _run(self, query: str, max_results: int = 10) -> str:
        return hybrid_search_service.search(
            search_request=...,
            user_id=self._user_id,
            organization_id=self._organization_id,
        )
```

Apply the same pattern to `KnowledgeGraphTool` for consistency.

**Bonus (MEDIUM-5):** While in this file, fix the `_extract_search_results` stub at lines 777-801 that always returns `[]`. Parse the JSON output that `SearchTool._run()` already serializes (line 134) back into `SearchResult` objects.

---

## Fix 3 — CRITICAL-2: Async Generator Misuse + Connection Leak

**File:** `backend/src/middleware/multi_tenancy.py:117`

**Problem:** `db = next(get_db())` calls `next()` on an async generator (`get_db()` is `async def ... yield session` per `core/database.py:122-125`). Raises `TypeError` at runtime, swallowed by broad `except Exception` at line 141 → every tenant validation throws `PermissionDeniedException` masking the real bug. Session is also never closed (leak).

Additionally, the body uses sync ORM API (`db.query(Organization)`) on what should be `AsyncSession` — would raise `MissingGreenlet` even if the generator issue were fixed.

**Fix:** Replace lines 112-146 with proper async pattern using existing `AsyncSessionLocal` (already imported and used correctly across the codebase, e.g., `services/research/extraction_matrix_service.py`):

```python
async def _validate_tenant_access(self, organization_id: str, request: Request) -> bool:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Organization).where(
                Organization.id == organization_id,
                Organization.is_active == True,
            )
        )
        organization = result.scalars().first()
        if not organization:
            raise PermissionDeniedException(...)
    return True
```

**Reuse:** `AsyncSessionLocal` from `core/database.py:108-110`.

---

## Fix 4 — CRITICAL-4: Tenant Context Not Cleared on Exception

**File:** `backend/src/middleware/multi_tenancy.py:41-75`

**Problem:** `_clear_tenant_context()` is only called on the success path (line 64). Exceptions leave `tenant_context`, `user_context`, `role_context` ContextVars set — under load they leak across requests sharing the same task.

**Fix:** Wrap context-setting in `try/finally`. Even better, the file already defines a correct `tenant_context_manager` context manager at lines 255-270 that uses `ContextVar.reset(token)` properly. Refactor `dispatch` to use it:

```python
async def dispatch(self, request, call_next):
    if self._should_skip_tenant_validation(request):
        return await call_next(request)

    tenant_info = await self._extract_tenant_info(request)
    if not tenant_info:
        return await call_next(request)  # No user info, skip silently

    with tenant_context_manager(
        organization_id=tenant_info["organization_id"],
        user_id=tenant_info["user_id"],
        user_role=tenant_info["role"],
    ):
        await self._validate_tenant_access(...)
        return await call_next(request)
```

`tenant_context_manager` already uses `try/finally` with `ContextVar.reset()` — the gold-standard pattern. **Reuses existing code instead of writing new cleanup logic.**

---

## Fix 5 — CRITICAL-3: Register MultiTenancyMiddleware + JWT Tenant Extraction

**Files:**

- `backend/src/main.py` (register middleware)
- `backend/src/middleware/multi_tenancy.py:85-110` (`_extract_tenant_info`)

**Problem:** `MultiTenancyMiddleware` is defined but never imported or registered. Even if registered, `_extract_tenant_info` reads `request.state.user` which **no other middleware populates** (verified — zero `request.state.user =` matches across the codebase). The `get_current_user_token` dependency returns `organization_id=None` on its `TokenData`.

**Recommended approach (smallest viable):** Modify `_extract_tenant_info` to parse the JWT directly using the existing `verify_token()` from `core/security.py`. This avoids introducing a new auth middleware.

```python
async def _extract_tenant_info(self, request: Request) -> Optional[Dict]:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    try:
        token_data = verify_token(token)  # existing function in core/security.py
    except Exception:
        return None
    # Extract org_id from token payload (Supabase: app_metadata.organization_id)
    organization_id = token_data.organization_id  # may need to read raw payload
    if not organization_id:
        return None
    return {
        "organization_id": str(organization_id),
        "user_id": str(token_data.user_id),
        "role": token_data.role or "user",
    }
```

Then in `main.py`, add after CORS, before `AnalyticsRateLimitMiddleware` (order matters — tenant context must be set before rate limiting reads it):

```python
from src.middleware.multi_tenancy import MultiTenancyMiddleware
app.add_middleware(MultiTenancyMiddleware)
```

**Note:** If `User.organization_id` isn't currently embedded in JWT claims, we have two sub-options:

- **5a (faster):** Look up user in DB to fetch `organization_id` (one extra query per request — acceptable with caching).
- **5b (better long-term):** Add `organization_id` to JWT claims at issuance in `services/core/auth.py`. Tokens issued before the change need refresh.

Default to **5a with TODO marker for 5b** — avoids breaking existing tokens.

**Reuse:** `verify_token()` from `core/security.py`, `tenant_context_manager` from Fix 4.

---

## Fix 6 — CRITICAL-5: Hardcoded JWT Secret Allowlist Bypass

**File:** `backend/src/core/config.py:148-176`

**Problem:** Two distinct bugs:

1. **Line 153:** Validator pre-checks `v == "dev-jwt-persistent-secret-key-32chars!"` and returns it without further validation. Any production deployment that copies this exact string from `docker-compose.development.yml` bypasses the production check.
2. **Line 173:** When `JWT_SECRET_KEY` is unset/weak in development, the validator returns the hardcoded string as fallback. Combined with `docker-compose.prod.yml` **not setting `JWT_SECRET_KEY` at all** (verified), production silently signs JWTs with the public dev secret.

**Fix:** Mirror the existing correct `SECRET_KEY` validator pattern at `config.py:122-146` (no allowlist, raises in prod, generates random in dev):

```python
@field_validator("JWT_SECRET_KEY", mode="before")
@classmethod
def validate_jwt_secret_key(cls, v, info):
    weak_patterns = [
        "change-in-production", "your-secret", "changeme",
        "jwt-secret", "dev-jwt-persistent",
    ]
    is_weak = not v or any(p in (v or "").lower() for p in weak_patterns)
    env = os.getenv("ENVIRONMENT", "development")

    if is_weak:
        if env in ("production", "staging"):
            raise ValueError(
                "JWT_SECRET_KEY must be set to a strong value in production/staging. "
                "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(48))'"
            )
        return _generate_dev_secret("jwt")  # reuse existing helper from SECRET_KEY validator
    if len(v) < 32:
        raise ValueError("JWT_SECRET_KEY must be at least 32 characters")
    return v
```

**Also fix `docker-compose.prod.yml`:** Add `JWT_SECRET_KEY: ${JWT_SECRET_KEY}` to the backend service environment so env var is actually wired through. Without this, the validator's new prod check will fire (correct behavior) and prevent broken deployments — but the deploy will fail until the env var is set, which is the desired fail-loud outcome.

**Reuse:** `_generate_dev_secret()` helper used by SECRET_KEY validator.

---

## Critical Files Modified

| File                                                        | Fixes                | Approx LOC change |
| ----------------------------------------------------------- | -------------------- | ----------------- |
| `backend/src/services/search/multi_agent_search_service.py` | F1, F2, M5           | ~80               |
| `backend/src/middleware/multi_tenancy.py`                   | F3, F4, F5 (extract) | ~50               |
| `backend/src/main.py`                                       | F5 (register)        | ~3                |
| `backend/src/core/config.py`                                | F6                   | ~15               |
| `docker-compose.prod.yml`                                   | F6                   | ~1                |

**Total: 5 files, ~150 LOC changed.**

---

## Verification

### Per-fix unit tests (new)

1. **Fix 1**: `tests/security/test_cypher_injection.py` — Pass `entity_name="x' DETACH DELETE (n) //"`, assert it's parameterized (no Cypher executed). Pass `relationship_type="INVALID_TYPE"`, assert validation rejection.

2. **Fix 2**: `tests/services/test_multi_agent_tenant_isolation.py` — Spin up two orgs, verify SearchTool bound to org A cannot return docs from org B.

3. **Fix 3**: `tests/middleware/test_multi_tenancy_middleware.py::test_validate_tenant_access_uses_async_session` — Assert no `TypeError` raised when `_validate_tenant_access` runs; assert connection is closed (mock `AsyncSessionLocal`).

4. **Fix 4**: `tests/middleware/test_multi_tenancy_middleware.py::test_context_cleared_on_exception` — Trigger exception in `call_next`, assert `tenant_context.get(None) is None` after.

5. **Fix 5**: `tests/middleware/test_multi_tenancy_middleware.py::test_jwt_extraction` — Send request with valid Bearer token, assert tenant context is set; with invalid token, assert request proceeds with no context.

6. **Fix 6**: `tests/core/test_config.py::test_jwt_secret_rejected_in_production` — Set `ENVIRONMENT=production` + weak `JWT_SECRET_KEY`, assert `ValueError`. Test allowlist string also rejected.

### End-to-end verification

```bash
# Start dev stack
docker-compose -f docker-compose.development.yml up -d

# Run test suite (security + middleware focus)
cd backend && pytest tests/security/ tests/middleware/ tests/core/test_config.py -v

# Manual smoke: confirm tenant isolation works
# 1. Login as user from Org A → save JWT
# 2. POST /api/v1/search with body referencing doc owned by Org B
# 3. Assert empty/filtered results

# Manual smoke: confirm JWT secret check fires in prod
ENVIRONMENT=production JWT_SECRET_KEY="dev-jwt-persistent-secret-key-32chars!" \
  python -c "from src.core.config import settings; print(settings.JWT_SECRET_KEY)"
# Expect: ValueError

# Regression: ensure normal dev startup still works
ENVIRONMENT=development python -c "from src.core.config import settings; assert settings.JWT_SECRET_KEY"
# Expect: success, secret generated
```

### CI integration

Add to `.github/workflows/ci.yml`:

- Run new `tests/security/` directory in the existing test job.
- No new infrastructure needed; uses existing PostgreSQL service container.

---

## Commit Strategy (default)

Single PR, 5 atomic commits — easier to review as one security hardening sprint:

1. `fix(search): parameterize Cypher queries in KnowledgeGraphTool (CRIT-1, HIGH-5)` — F1 + F2 + M5
2. `fix(middleware): use AsyncSessionLocal in tenant validation (CRIT-2)` — F3
3. `fix(middleware): clear tenant context via try/finally (CRIT-4)` — F4
4. `fix(middleware): register multi-tenancy middleware with JWT extraction (CRIT-3)` — F5
5. `fix(config): remove JWT secret allowlist bypass (CRIT-5)` — F6

Each commit independently revertible. Tests added in same commit as each fix.

---

## Out of Scope (Documented Follow-ups)

- The 8 HIGH-priority and 10 MEDIUM-priority issues from the original review (event-loop blocking, sync I/O in async paths, X-Forwarded-For ordering, etc.) — separate sprint.
- Adding a dedicated `AuthMiddleware` (alternative scope choice 5b) — defer until a use case beyond multi-tenancy needs `request.state.user` populated.
- Replacing the broad `except Exception` blocks (2,163 occurrences) with structured exception handling — separate refactor.
- The 158 empty function bodies and 7 `NotImplementedError` markers — backlog grooming.
