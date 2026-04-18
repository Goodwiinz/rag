# Backend Security & Bug Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all 11 P1 bugs and the highest-priority P2 bugs found by Codex audit of the backend API layer.

**Architecture:** Surgical fixes — no refactors, no new endpoints. Each task targets one bug or a cluster of related bugs in a single file. Fix, test, commit.

**Tech Stack:** FastAPI, SQLAlchemy (async), PostgreSQL, Pydantic

---

### Task 1: Uncomment encryption permission decorators

**Files:**

- Modify: `backend/src/api/security/encryption.py:174,219,265,335,375,412,445`

**Step 1: Uncomment all `@require_permission` decorators**

Find every line matching `# @require_permission(` and uncomment it. There are 7 occurrences:

```python
# Line 174: before encrypt_user_profile
@require_permission(["encryption:manage"])

# Line 219: before decrypt_user_profile
@require_permission(["encryption:manage"])

# Line 265: before encrypt_org_profile
@require_permission(["encryption:manage"])

# Line 335: before rotate_encryption_keys
@require_permission(["encryption:manage"])

# Line 375: before get_encryption_status
@require_permission(["encryption:read"])

# Line 412: before validate_encryption_integrity
@require_permission(["encryption:manage"])

# Line 445: before get_audit_logs
@require_permission(["encryption:audit"])
```

**Step 2: Remove `content_manager` from PII access role check**

At line 190-192, change:

```python
# BEFORE
if request.user_id != current_user.id and current_user.role.value not in [
    "admin",
    "content_manager",
]:

# AFTER
if request.user_id != current_user.id and current_user.role.value != "admin":
```

Apply same change to decrypt endpoint (~line 240) if same pattern exists.

**Step 3: Add org-scoping to encrypt/decrypt endpoints**

After the role check at line 190, add org verification:

```python
# Verify target user belongs to same organization
if request.user_id != current_user.id:
    target_user = db.query(User).filter(User.id == request.user_id).first()
    if not target_user or str(target_user.organization_id) != str(current_user.organization_id):
        raise HTTPException(status_code=404, detail="User not found")
```

**Step 4: Verify fix**

Run: `cd backend && python -c "from src.api.security.encryption import router; print('OK')"`
Expected: OK (no import errors)

**Step 5: Commit**

```bash
git add backend/src/api/security/encryption.py
git commit -m "fix(security): restore encryption permission decorators, restrict PII access to admin"
```

---

### Task 2: Fix delete_file NameError — add missing db parameter

**Files:**

- Modify: `backend/src/api/documents/files.py:268-272`

**Step 1: Add `db` and `organization` to function signature**

```python
# BEFORE (line 268-272)
@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    file_service: FileService = Depends(get_file_service),
):

# AFTER
@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
    file_service: FileService = Depends(get_file_service),
):
```

**Step 2: Add org-scoping to the query**

```python
# BEFORE (line 277)
stmt = select(Document).where(Document.id == file_id, Document.is_deleted == False)

# AFTER
stmt = select(Document).where(
    Document.id == file_id,
    Document.organization_id == organization.id,
    Document.is_deleted == False,
)
```

**Step 3: Verify fix**

Run: `cd backend && python -c "from src.api.documents.files import router; print('OK')"`

**Step 4: Commit**

```bash
git add backend/src/api/documents/files.py
git commit -m "fix(documents): add missing db param to delete_file, add org scoping"
```

---

### Task 3: Fix cross-tenant IDOR in files.py endpoints

**Files:**

- Modify: `backend/src/api/documents/files.py`

**Step 1: Fix get_file_info, download_file, get_file_content, get_file_metadata**

For each endpoint that fetches a single document by ID, ensure the query includes org scoping:

```python
# Add organization_id filter to every single-document query
stmt = select(Document).where(
    Document.id == file_id,
    Document.organization_id == organization.id,
    Document.is_deleted == False,
)
```

Remove the `is_public` bypass that allows cross-org access. If public document sharing is needed, it should go through a separate public API.

**Step 2: Fix update_file_metadata — add org check**

Add `organization: Organization = Depends(get_current_organization)` to the function signature and filter by `organization_id` in the query.

**Step 3: Fix reprocess_file — add org check**

Same pattern — add org dependency and filter.

**Step 4: Commit**

```bash
git add backend/src/api/documents/files.py
git commit -m "fix(documents): add org scoping to all single-document file endpoints"
```

---

### Task 4: Fix broken auth check in user_behavior.py

**Files:**

- Modify: `backend/src/api/quality/user_behavior.py:174-176,213`

**Step 1: Fix self-comparison bug**

```python
# BEFORE (line 174-176)
if current_user.role not in [UserRole.ADMIN] and str(
    current_user.organization_id
) != str(current_user.organization_id):

# AFTER — look up target user's org instead
if current_user.role not in [UserRole.ADMIN]:
    # Verify target user belongs to same organization
    db = next(get_db())
    try:
        target_user = db.query(User).filter(User.id == user_id).first()
        if not target_user or str(target_user.organization_id) != str(current_user.organization_id):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
    finally:
        db.close()
```

**Step 2: Fix uppercase ADMIN role check**

```python
# BEFORE (line 213)
and current_user.role.value not in ["ADMIN"]

# AFTER
and current_user.role.value not in ["admin"]
```

**Step 3: Commit**

```bash
git add backend/src/api/quality/user_behavior.py
git commit -m "fix(quality): fix broken auth check — compare target user org, lowercase role"
```

---

### Task 5: Fix metrics.py missing imports — 5 crashing endpoints

**Files:**

- Modify: `backend/src/api/analytics/metrics.py:1-20`

**Step 1: Add missing imports**

After the existing imports (line 10), add:

```python
from sqlalchemy import select, and_, or_
from src.core.database import get_async_session, get_db
from src.models.analytics_event import AnalyticsMetric  # verify actual model location
```

Note: The model may live at a different path. Search for `class AnalyticsMetric` in the backend:

```bash
grep -r "class AnalyticsMetric" backend/src/
```

If the model doesn't exist, these endpoints are dead code — mark them as such with a `# TODO: dead endpoint` comment and move on.

**Step 2: Also check for AnalyticsKPI import**

```bash
grep -r "class AnalyticsKPI" backend/src/
```

Add the import if found.

**Step 3: Fix `status` variable shadowing (line 401)**

Rename the local variable:

```python
# BEFORE
status = metrics_service._determine_kpi_status(...)

# AFTER
kpi_status = metrics_service._determine_kpi_status(...)
```

Update all references to `status` that refer to the KPI status (not `fastapi.status`).

**Step 4: Verify**

Run: `cd backend && python -c "from src.api.analytics.metrics import router; print('OK')"`

**Step 5: Commit**

```bash
git add backend/src/api/analytics/metrics.py
git commit -m "fix(analytics): add missing imports to metrics endpoints, fix status shadowing"
```

---

### Task 6: Fix compliance.py missing imports + status shadowing

**Files:**

- Modify: `backend/src/api/security/compliance.py:1-20,310`

**Step 1: Add missing SQLAlchemy imports**

```python
# Add to imports (after line 20)
from sqlalchemy import desc, func, and_
```

**Step 2: Fix status param shadowing**

Rename the query parameter in the two affected endpoints:

```python
# BEFORE
status: Optional[str] = Query(None, ...)

# AFTER
compliance_status: Optional[str] = Query(None, ...)
```

Update all references within those endpoints from `status` (the param) to `compliance_status`.

**Step 3: Verify**

Run: `cd backend && python -c "from src.api.security.compliance import router; print('OK')"`

**Step 4: Commit**

```bash
git add backend/src/api/security/compliance.py
git commit -m "fix(compliance): add missing sqlalchemy imports, fix status param shadowing"
```

---

### Task 7: Fix WebSocket v1 token-in-URL

**Files:**

- Modify: `backend/src/api/realtime/websocket.py:47-70`

**Step 1: Change from query param to Sec-WebSocket-Protocol header**

```python
# BEFORE (line 47-50)
@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    organization_id: Optional[str] = Query(None),
):

# AFTER
@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
):
    # Extract token from Sec-WebSocket-Protocol header (project convention)
    protocols = websocket.headers.get("sec-websocket-protocol", "")
    token = None
    organization_id = None
    for protocol in protocols.split(","):
        protocol = protocol.strip()
        if protocol.startswith("access_token."):
            token = protocol.replace("access_token.", "", 1)
        elif protocol.startswith("org."):
            organization_id = protocol.replace("org.", "", 1)
```

Check `websocket_v2.py` to see how it handles auth — match the same pattern for consistency.

**Step 2: Accept the protocol in the handshake**

```python
# When accepting, specify the sub-protocol
await websocket.accept(subprotocol="access_token")
```

**Step 3: Commit**

```bash
git add backend/src/api/realtime/websocket.py
git commit -m "fix(websocket): migrate v1 auth from URL query params to Sec-WebSocket-Protocol"
```

---

### Task 8: Fix research engine resume no-op

**Files:**

- Modify: `backend/src/api/research_engine/runs.py:~250`

**Step 1: Set status to RUNNING after resume**

```python
# BEFORE
run.status = RunStatus.PAUSED.value  # Keep resumed runs in PAUSED

# AFTER
run.status = RunStatus.RUNNING.value
```

**Step 2: Commit**

```bash
git add backend/src/api/research_engine/runs.py
git commit -m "fix(research-engine): set run status to RUNNING on resume"
```

---

### Task 9: Fix broadcast endpoint missing admin check

**Files:**

- Modify: `backend/src/api/realtime/websocket_v2.py:~267`

**Step 1: Add admin role check**

```python
# Add after current_user dependency
if current_user.role.value != "admin":
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only administrators can broadcast messages",
    )
```

**Step 2: Commit**

```bash
git add backend/src/api/realtime/websocket_v2.py
git commit -m "fix(websocket): restrict broadcast endpoint to admin role"
```

---

### Task 10: Fix remaining org-scoping gaps (batch)

**Files:**

- Modify: `backend/src/api/documents/table_extraction.py:50,87`
- Modify: `backend/src/api/documents/integrity.py:48,110`
- Modify: `backend/src/api/documents/processing.py:60`

**Step 1: For each file, change user-only filter to org filter**

Pattern — replace:

```python
Document.uploaded_by_user_id == current_user.id
```

With:

```python
Document.organization_id == organization.id
```

And add `organization: Organization = Depends(get_current_organization)` to each endpoint signature.

Import `get_current_organization` from `src.core.dependencies` if not already imported.

**Step 2: Commit**

```bash
git add backend/src/api/documents/table_extraction.py \
      backend/src/api/documents/integrity.py \
      backend/src/api/documents/processing.py
git commit -m "fix(documents): add org scoping to table_extraction, integrity, and processing endpoints"
```

---

### Task 11: Remove debug endpoint

**Files:**

- Modify: `backend/src/api/documents/files.py`

**Step 1: Find and remove the `/files/debug-auth` endpoint**

Search for `debug-auth` or `debug_auth` in the file and remove the entire endpoint function.

**Step 2: Commit**

```bash
git add backend/src/api/documents/files.py
git commit -m "fix(security): remove debug-auth endpoint from production"
```

---

## Deferred to Next Sprint

| #   | Issue                                      | Why Deferred                                                   |
| --- | ------------------------------------------ | -------------------------------------------------------------- |
| D11 | Upload progress in process memory          | Needs Redis or shared store — architectural change             |
| D12 | Unauthenticated upload WebSocket           | Needs auth pattern decision for WebSocket                      |
| S3  | Double Qdrant RPC in vectors.py            | Performance, not security                                      |
| S14 | Unbounded search_analytics_store           | Memory leak but needs design for eviction                      |
| T4  | Sync/async session misuse (multiple files) | Large refactor across api_keys, thread_search, document_upload |

---

## Verification

After all tasks complete:

```bash
# Import check — all fixed modules load
cd backend && python -c "
from src.api.security.encryption import router; print('encryption OK')
from src.api.security.compliance import router; print('compliance OK')
from src.api.documents.files import router; print('files OK')
from src.api.analytics.metrics import router; print('metrics OK')
from src.api.quality.user_behavior import router; print('user_behavior OK')
"

# Run existing tests
cd backend && pytest tests/ -v --tb=short -x

# Security smoke tests
# 1. Non-admin user → POST /encryption/profiles/user → expect 403
# 2. User in Org A → GET /documents/files/{org-b-doc-id} → expect 404
# 3. Non-admin user → POST /realtime/broadcast → expect 403
# 4. Any user → GET /quality/user-behavior/users/{other-user}/behavior → expect 403
```
