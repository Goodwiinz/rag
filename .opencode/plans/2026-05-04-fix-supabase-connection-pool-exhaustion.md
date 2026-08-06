# Fix Supabase Connection Pool Exhaustion

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate `MaxClientsInSessionMode: max clients reached` errors by reducing per-request DB connection usage, tuning pool sizes, and adding retry resilience.

**Architecture:** Reduce the multi-tenancy middleware from 2 DB sessions per request to 1 by attaching the validated session to `request.state`, then tuning SQLAlchemy pool defaults for Supabase's session-mode limits. Add exponential-backoff retry for transient pool exhaustion. Switch Supabase to transaction-mode pooler URL as the infrastructure fix.

**Tech Stack:** FastAPI, SQLAlchemy asyncpg, Supabase (PgBouncer session-mode), Kubernetes/Helm, ArgoCD

---

## Background

Current connection math (dev, 1 backend replica, 2 gunicorn workers):
- Each worker: async pool_size=5 + max_overflow=5 = 10 async connections
- Sync pool: 2 + 3 = 5 sync connections
- Multi-tenancy middleware opens **another** `AsyncSessionLocal()` before the endpoint's `get_db()` → **2 async sessions per authenticated request**
- 1 backend pod × 2 workers × 10 async = 20 async slots on boot
- Add celery worker (1 replica, concurrency=2) = another ~10 async slots
- Add init containers (wait-for-postgres + migrations) = 2+ more on every deploy
- Supabase Nano session-mode limit = **15 total connections** → saturated immediately

---

### Task 1: Attach validated DB session to request.state in middleware

**Files:**
- Modify: `backend/src/middleware/multi_tenancy.py:36-63`
- Test: `backend/tests/unit/middleware/test_multi_tenancy.py` (create if missing)

**Step 1: Write failing test**

```python
# backend/tests/unit/middleware/test_multi_tenancy.py
import pytest
from fastapi import FastAPI, Request
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch

from src.middleware.multi_tenancy import MultiTenancyMiddleware


@pytest.mark.asyncio
async def test_middleware_attaches_db_session_to_request_state():
    """Middleware should reuse its db session and attach it to request.state"""
    app = FastAPI()
    app.add_middleware(MultiTenancyMiddleware)

    captured_state = {}

    @app.get("/test")
    async def test_endpoint(request: Request):
        captured_state["has_db"] = hasattr(request.state, "db")
        captured_state["db_closed"] = request.state.db.is_active is False
        return {"ok": True}

    async with AsyncClient(app=app, base_url="http://test") as ac:
        with patch(
            "src.middleware.multi_tenancy.AsyncSessionLocal",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(is_active=True)), __aexit__=AsyncMock(return_value=False)),
        ):
            await ac.get("/test", headers={"Authorization": "Bearer fake"})

    assert captured_state.get("has_db") is True
```

Run: `pytest backend/tests/unit/middleware/test_multi_tenancy.py -v`
Expected: FAIL with `AttributeError: 'State' object has no attribute 'db'`

**Step 2: Implement session attachment**

Modify `backend/src/middleware/multi_tenancy.py`:

```python
# In dispatch(), after successful tenant validation:
            async with AsyncSessionLocal() as db:
                tenant_info = await self._extract_tenant_info(request, db)
                if not tenant_info:
                    return await call_next(request)
                await self._validate_tenant_access(
                    tenant_info["organization_id"], db
                )
                # Attach the validated session so endpoints can reuse it
                request.state.db = db
                with tenant_context_manager(...):
                    request.state.tenant_id = ...
                    return await call_next(request)
```

**Step 3: Update get_db() to reuse request.state.db when present**

Modify `backend/src/core/database.py`:

```python
async def get_db(request: Request) -> AsyncSession:
    """Get database session (asynchronous). Reuses middleware session if available."""
    existing = getattr(request.state, "db", None)
    if existing is not None:
        yield existing
        return
    async with AsyncSessionLocal() as session:
        yield session
```

> **Note:** FastAPI `Depends(get_db)` must accept `Request` param. FastAPI injects `Request` automatically when the dependency signature includes it.

Run: `pytest backend/tests/unit/middleware/test_multi_tenancy.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add backend/src/middleware/multi_tenancy.py backend/src/core/database.py backend/tests/unit/middleware/test_multi_tenancy.py
git commit -m "fix: reuse middleware db session in endpoints to halve connection usage"
```

---

### Task 2: Add connection retry with backoff for pool exhaustion

**Files:**
- Create: `backend/src/core/db_retry.py`
- Modify: `backend/src/core/database.py` (import and wrap engine creation)
- Test: `backend/tests/unit/core/test_db_retry.py`

**Step 1: Write failing test**

```python
# backend/tests/unit/core/test_db_retry.py
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import OperationalError

from src.core.db_retry import retry_on_pool_exhaustion


@pytest.mark.asyncio
async def test_retry_on_pool_exhaustion_retries_three_times():
    call_count = 0

    @retry_on_pool_exhaustion(max_retries=3, base_delay=0.01)
    async def flaky_connect():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise OperationalError("max clients reached", None, None)
        return "ok"

    result = await flaky_connect()
    assert result == "ok"
    assert call_count == 3
```

Run: `pytest backend/tests/unit/core/test_db_retry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.core.db_retry'`

**Step 2: Implement retry decorator**

```python
# backend/src/core/db_retry.py
import asyncio
import functools
import logging
from typing import Callable, TypeVar

from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)
T = TypeVar("T")


def retry_on_pool_exhaustion(max_retries: int = 3, base_delay: float = 0.5):
    """Retry on transient DB pool exhaustion (max clients reached)."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            for attempt in range(1, max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except OperationalError as e:
                    msg = str(e).lower()
                    if "max clients" not in msg and "pool" not in msg:
                        raise
                    if attempt == max_retries:
                        logger.error("DB pool exhausted after %d retries", max_retries)
                        raise
                    delay = base_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "DB pool exhausted (attempt %d/%d), retrying in %.2fs...",
                        attempt, max_retries, delay
                    )
                    await asyncio.sleep(delay)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except OperationalError as e:
                    msg = str(e).lower()
                    if "max clients" not in msg and "pool" not in msg:
                        raise
                    if attempt == max_retries:
                        logger.error("DB pool exhausted after %d retries", max_retries)
                        raise
                    delay = base_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "DB pool exhausted (attempt %d/%d), retrying in %.2fs...",
                        attempt, max_retries, delay
                    )
                    asyncio.run(asyncio.sleep(delay))

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator
```

**Step 3: Apply to get_db and get_db_sync**

Modify `backend/src/core/database.py`:

```python
from src.core.db_retry import retry_on_pool_exhaustion

@retry_on_pool_exhaustion(max_retries=3, base_delay=0.5)
async def get_db(request: Request) -> AsyncSession:
    ...

@retry_on_pool_exhaustion(max_retries=3, base_delay=0.5)
def get_db_sync() -> Session:
    ...
```

Run: `pytest backend/tests/unit/core/test_db_retry.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add backend/src/core/db_retry.py backend/src/core/database.py backend/tests/unit/core/test_db_retry.py
git commit -m "feat: add exponential backoff retry for db pool exhaustion"
```

---

### Task 3: Tune DB pool sizes for Supabase session-mode limits

**Files:**
- Modify: `backend/src/core/database.py:96-97,126-127`
- Modify: `infrastructure/helm/knowledge-graph-analytics/values-dev.yaml:134`
- Modify: `infrastructure/helm/knowledge-graph-analytics/values-staging.yaml`
- Modify: `infrastructure/helm/knowledge-graph-analytics/values-production.yaml`

**Step 1: Reduce default pool sizes**

Modify `backend/src/core/database.py`:

```python
# Sync engine (used by init containers, migrations, background tasks)
pool_size=_env_int("DB_SYNC_POOL_SIZE", 1),       # was 2
max_overflow=_env_int("DB_SYNC_MAX_OVERFLOW", 1),  # was 3

# Async engine (hot path)
pool_size=_env_int("DB_ASYNC_POOL_SIZE", 3),       # was 5
max_overflow=_env_int("DB_ASYNC_MAX_OVERFLOW", 2), # was 5
```

**Step 2: Add env vars to dev Helm values**

Add to `infrastructure/helm/knowledge-graph-analytics/values-dev.yaml` under `backend.env`:

```yaml
    - name: DB_ASYNC_POOL_SIZE
      value: "3"
    - name: DB_ASYNC_MAX_OVERFLOW
      value: "2"
    - name: DB_SYNC_POOL_SIZE
      value: "1"
    - name: DB_SYNC_MAX_OVERFLOW
      value: "1"
```

**Step 3: Add same env vars to staging and production values**

Staging: `infrastructure/helm/knowledge-graph-analytics/values-staging.yaml`
Production: `infrastructure/helm/knowledge-graph-analytics/values-production.yaml`

Use conservative values (staging same as dev; prod may need higher but still within Supabase limits — if using Small=25, set async pool to 5 with max_overflow 3).

**Step 4: Commit**

```bash
git add backend/src/core/database.py infrastructure/helm/knowledge-graph-analytics/values-dev.yaml infrastructure/helm/knowledge-graph-analytics/values-staging.yaml infrastructure/helm/knowledge-graph-analytics/values-production.yaml
git commit -m "config: reduce default db pool sizes to fit supabase session-mode limits"
```

---

### Task 4: Switch Supabase DB URL to transaction-mode pooler

**Files:**
- Modify: `infrastructure/helm/knowledge-graph-analytics/values-dev.yaml` (comment only)
- Infisical secret: `database-credentials` or `supabase-credentials`

**Step 1: Verify Supabase transaction-mode URL**

In Supabase dashboard → Project Settings → Database → Connection Pooling:
- Session mode URL: `postgresql://...pooler.supabase.com:6543/postgres`
- Transaction mode URL: `postgresql://...pooler.supabase.com:6543/postgres` (Supavisor uses the same host but transaction mode is typically indicated by a different port or parameter)

Actually, Supabase Supavisor provides:
- Session mode URL: Port `6543`
- Transaction mode URL: Port `6543` with `?pgbouncer=true`? No.

Correct Supavisor URLs (check your Supabase dashboard):
- **Session pooler**: `postgresql://postgres.[project_ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres`
- **Transaction pooler**: `postgresql://postgres.[project_ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres` — but with `?pgbouncer=true`? No, that's for the old PgBouncer.

Actually, the **transaction pooler** in Supabase is available at:
`postgresql://postgres.[project_ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres` with **no additional params needed** for the new Supavisor transaction pool (it auto-detects). But some ORMs need `?pgbouncer=true` or `?prepareThreshold=0`.

Wait — the old PgBouncer (session mode) URL is at `*.pooler.supabase.com:6543`. The **new Supavisor** provides both modes. The transaction mode URL in Supabase Dashboard is usually shown separately.

**Action:** Log into Supabase Dashboard → your project → Database → Connection Pooling. Copy the **Transaction pooler** connection string. Update the `SUPABASE_DB_URL` or `DATABASE_URL` in Infisical (or whichever secret manager provides `database-credentials`).

**Important:** For SQLAlchemy + asyncpg with a transaction pooler, keep:
```python
connect_args={
    "prepared_statement_cache_size": 0,
    "statement_cache_size": 0,
}
```
(already set). Also add `?ssl=require` if needed.

**Step 2: Update secret and rollout**

If using Infisical (as the Helm chart suggests):
1. Update the secret in Infisical dev environment.
2. ArgoCD will sync automatically, OR force sync:
   ```bash
   kubectl rollout restart deployment/nous-dev-knowledge-graph-analytics-backend -n rag-dev
   kubectl rollout restart deployment/nous-dev-knowledge-graph-analytics-celery-worker -n rag-dev
   ```

**Step 3: Verify**

Watch logs for 5 minutes:
```bash
BACKEND=$(kubectl get pod -n rag-dev -l app.kubernetes.io/component=backend -o jsonpath='{.items[0].metadata.name}')
kubectl logs -n rag-dev $BACKEND -f | grep -iE "ERROR|pool|max clients"
```

Expected: No new `MaxClientsInSessionMode` errors.

**Step 4: Commit (documentation only)**

Add a comment to `values-dev.yaml` above the backend env section:

```yaml
    # Database pool sizing: tuned for Supabase session-mode (Nano=15, Small=25).
    # If switching to Supavisor transaction-mode pooler, these can be increased.
```

```bash
git add infrastructure/helm/knowledge-graph-analytics/values-dev.yaml
git commit -m "docs: note supabase pool limits and transaction-mode option"
```

---

### Task 5: Remove redundant DB lookups in middleware (embed org_id in JWT)

**Files:**
- Modify: `backend/src/core/security.py` (JWT issuance)
- Modify: `backend/src/middleware/multi_tenancy.py` (skip DB lookup if org_id in JWT)
- Test: `backend/tests/unit/middleware/test_multi_tenancy.py`

**Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_middleware_skips_db_when_org_id_in_jwt():
    """If JWT contains organization_id, middleware should not query DB."""
    ...
```

Run: `pytest backend/tests/unit/middleware/test_multi_tenancy.py::test_middleware_skips_db_when_org_id_in_jwt -v`
Expected: FAIL

**Step 2: Modify JWT creation to embed organization_id**

In `backend/src/core/security.py`, wherever JWTs are created (login, refresh, register), add `organization_id` to the payload claims.

**Step 3: Modify middleware to use JWT org_id first**

```python
async def _extract_tenant_info(self, request: Request, db: Optional[AsyncSession] = None):
    ...
    token_data = verify_token(token)
    if not token_data or not token_data.user_id:
        return None
    # Fast path: org_id embedded in JWT
    if getattr(token_data, "organization_id", None):
        return {
            "organization_id": str(token_data.organization_id),
            "user_id": str(token_data.user_id),
            "role": token_data.role or "user",
        }
    # Fallback: DB lookup (existing code)
    ...
```

Run: `pytest backend/tests/unit/middleware/test_multi_tenancy.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add backend/src/core/security.py backend/src/middleware/multi_tenancy.py backend/tests/unit/middleware/test_multi_tenancy.py
git commit -m "perf: embed organization_id in jwt to skip db lookup in middleware"
```

---

### Task 6: Verification — confirm fix in Sentry + cluster

**Step 1: Trigger a deploy**

```bash
# If ArgoCD auto-syncs on develop branch push
git push origin develop

# Or force rollout if secret change is manual
kubectl rollout restart deployment/nous-dev-knowledge-graph-analytics-backend -n rag-dev
kubectl rollout restart deployment/nous-dev-knowledge-graph-analytics-celery-worker -n rag-dev
```

**Step 2: Monitor Sentry for 30 minutes**

Check that these issue titles stop appearing:
- `MaxClientsInSessionMode: max clients reached`
- `Multi-tenancy middleware error: MaxClientsInSessionMode`
- `Failed to get error rate: MaxClientsInSessionMode`

Sentry query:
```
search_issues(organizationSlug='goodwiinz-uk', query='MaxClientsInSessionMode', statsPeriod='1h')
```

**Step 3: Verify zero new events on top issues**

Get latest events on the top 3 issues to confirm they are stale:
```
search_issue_events(issueId='JAVASCRIPT-NEXTJS-5', organizationSlug='goodwiinz-uk', query='-1h')
```

Expected: 0 results or timestamps from before the deploy.

---

## Summary of Changes

| Task | What | Impact |
|------|------|--------|
| 1 | Reuse middleware DB session in endpoints | -50% connections per request |
| 2 | Exponential backoff retry | Eliminates user-visible 500s on transient pool spikes |
| 3 | Reduce default pool sizes | Fits within Supabase Nano (15) limits |
| 4 | Switch to transaction-mode pooler | Removes hard session-mode cap entirely |
| 5 | Embed org_id in JWT | Eliminates 1-2 DB queries per request |

**Total connection reduction:** From ~20-30 async connections (per backend pod) down to ~6-10.

---

## Rollback Plan

If transaction-mode pooler causes prepared-statement issues (some asyncpg features may break):
1. Revert the secret back to session-mode URL.
2. Increase Supabase plan from Nano → Small (25 connections) or Medium (50).
3. Reduce `celeryWorker.replicaCount` and `backend.replicaCount` temporarily.
