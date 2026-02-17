# Review Findings Remediation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the four review findings (DB session bug, diagnostics auth gap, merge-job tenant validation gap, and concurrency-unsafe search weight mutation) without regressions.

**Architecture:** Keep API behavior stable except for explicit security hardening on diagnostics endpoints and merge-job validation. Refactor hybrid-search diagnostics to use per-request local weights instead of mutable shared service state. Add focused unit/API tests that reproduce each bug and verify fixed behavior.

**Tech Stack:** FastAPI, SQLAlchemy (sync + async sessions), Pydantic, pytest, unittest.mock

---

### Task 1: Fix Background RAG Evaluation DB Session Handling (P1)

**Files:**
- Modify: `backend/src/api/research/chat.py`
- Modify: `backend/tests/unit/api/test_research_chat_context.py`

**Step 1: Add a failing test for background evaluation DB acquisition**

Add a unit test for `_background_evaluate_rag` that patches:
- `src.api.research.chat.get_db_sync` (or equivalent imported symbol)
- `src.services.evaluation.rag_evaluation_service.rag_evaluation_service.run_rag_triad_evaluation`
- `src.services.diagnostics.diagnostics_store.diagnostics_store.update_trace_evaluation`

Verify:
- Function does not raise.
- Evaluation service is called with a DB session-like object.
- Trace evaluation update is called with expected score fields.

**Step 2: Run the targeted test and confirm failure on current code**

Run:
```bash
backend/venv/bin/python -m pytest backend/tests/unit/api/test_research_chat_context.py -q
```

Expected failure: runtime error path from `next(get_db())` using async generator.

**Step 3: Implement DB-session fix in `_background_evaluate_rag`**

Use sync DB dependency for this background coroutine code path:
- Replace `from src.core.database import get_db` + `next(get_db())`
- With `from src.core.database import get_db_sync` + `next(get_db_sync())`
- Keep explicit close in `finally`.

**Step 4: Re-run test and confirm pass**

Run:
```bash
backend/venv/bin/python -m pytest backend/tests/unit/api/test_research_chat_context.py -q
```

**Step 5: Commit**

```bash
git add backend/src/api/research/chat.py backend/tests/unit/api/test_research_chat_context.py
git commit -m "fix: use sync db session in background rag evaluation"
```

---

### Task 2: Enforce Auth on Diagnostics Endpoints (P1)

**Files:**
- Modify: `backend/src/api/diagnostics/retrieval_diagnostics.py`
- Modify: `backend/tests/unit/api/test_diagnostics_endpoints.py`

**Step 1: Add auth regression tests for diagnostics endpoints**

In diagnostics API tests, add:
- unauthenticated request to `/api/v1/diagnostics/traces` returns auth failure (401/403 based on app middleware).
- authenticated/admin override path returns success for existing endpoint tests.

Use dependency overrides for `get_current_user` or `require_admin` in test setup to avoid JWT complexity.

**Step 2: Run diagnostics test subset and confirm auth test fails pre-fix**

Run:
```bash
backend/venv/bin/python -m pytest backend/tests/unit/api/test_diagnostics_endpoints.py -q
```

Expected failure: unauthenticated request currently succeeds.

**Step 3: Add router-level auth dependency**

In `retrieval_diagnostics.py`:
- Import `Depends` and auth dependency from `src.core.dependencies` (recommend `require_admin`; minimum `get_current_user`).
- Set router dependencies:
```python
router = APIRouter(
    prefix="/diagnostics",
    tags=["diagnostics"],
    dependencies=[Depends(require_admin)],
)
```

**Step 4: Update existing endpoint tests for authenticated context**

Because endpoints become protected, adjust existing tests to inject dependency override in fixture or per-test patch so current success assertions remain valid under authenticated access.

**Step 5: Re-run diagnostics tests**

Run:
```bash
backend/venv/bin/python -m pytest backend/tests/unit/api/test_diagnostics_endpoints.py -q
```

**Step 6: Commit**

```bash
git add backend/src/api/diagnostics/retrieval_diagnostics.py backend/tests/unit/api/test_diagnostics_endpoints.py
git commit -m "fix: require auth for diagnostics endpoints"
```

---

### Task 3: Validate Merge Job Entity IDs Against Caller Organization (P1)

**Files:**
- Modify: `backend/src/api/search/knowledge_graph.py`
- Create: `backend/tests/unit/api/test_knowledge_graph_merge_jobs.py`

**Step 1: Add failing tests for cross-tenant merge input**

Create API-level unit tests for `/api/v1/knowledge-graph/merge-jobs`:
- returns 403/404 when any submitted entity ID resolves outside caller org.
- returns 202 when all entities map to documents in caller org.

Mock:
- `knowledge_graph_service.get_entity` to return `EntityResponse` with `source_document_id`.
- DB query for `Document` ownership by org.
- Celery `.apply_async` to avoid real queue execution.

**Step 2: Run the new tests and confirm failure pre-fix**

Run:
```bash
backend/venv/bin/python -m pytest backend/tests/unit/api/test_knowledge_graph_merge_jobs.py -q
```

Expected failure: endpoint currently queues arbitrary IDs.

**Step 3: Implement pre-queue ownership validation**

In `create_merge_job`:
- Collect all unique entity IDs in `request.groups` (including `suggested_primary` and each group member).
- Resolve each ID via `knowledge_graph_service.get_entity`.
- Reject missing entities with 404.
- Extract `source_document_id` from each entity; reject missing source document references with 422 (cannot validate ownership safely).
- Query `Document` for all source IDs filtered by `organization_id == current_user.organization_id` and `is_deleted == False`.
- If any source docs are not found in caller org, reject with 403.
- Only create/queue job after passing validation.

**Step 4: Re-run merge-job tests**

Run:
```bash
backend/venv/bin/python -m pytest backend/tests/unit/api/test_knowledge_graph_merge_jobs.py -q
```

**Step 5: Commit**

```bash
git add backend/src/api/search/knowledge_graph.py backend/tests/unit/api/test_knowledge_graph_merge_jobs.py
git commit -m "fix: enforce org ownership validation for merge jobs"
```

---

### Task 4: Remove Shared-State Weight Mutation in Diagnostics Search (P2)

**Files:**
- Modify: `backend/src/services/search/hybrid_search_service.py`
- Modify: `backend/tests/unit/services/test_hybrid_search_diagnostics.py`

**Step 1: Add/adjust tests to enforce non-mutation**

Update diagnostics service tests so they assert:
- `weights_override` affects only that call’s fusion/trace weights.
- `service.fulltext_weight/vector_weight/knowledge_graph_weight` are never mutated.
- behavior remains correct on error fallback paths.

**Step 2: Run current diagnostics service tests and confirm mismatch**

Run:
```bash
backend/venv/bin/python -m pytest backend/tests/unit/services/test_hybrid_search_diagnostics.py -q
```

Expected: tests currently model temporary mutation + restore pattern.

**Step 3: Refactor to per-request local weights**

In `search_with_diagnostics`:
- Compute `effective_weights` dict from defaults + optional override.
- Do not assign to `self.*_weight`.
- Pass `effective_weights` into fusion logic (either via new argument to `_fuse_search_results` or local fusion helper call path).
- Set `trace.fusion.weights_used` from `effective_weights`.
- Remove mutable-restore `finally` branch.

If `_fuse_search_results` currently reads `self.*_weight`, update it to accept optional weights and use those for score fusion.

**Step 4: Re-run diagnostics service tests**

Run:
```bash
backend/venv/bin/python -m pytest backend/tests/unit/services/test_hybrid_search_diagnostics.py -q
```

**Step 5: Commit**

```bash
git add backend/src/services/search/hybrid_search_service.py backend/tests/unit/services/test_hybrid_search_diagnostics.py
git commit -m "fix: make diagnostics weight experiments concurrency-safe"
```

---

### Task 5: Full Verification and Integration Check

**Files:**
- No new files; run verification and inspect diffs.

**Step 1: Run targeted suite for all touched areas**

Run:
```bash
backend/venv/bin/python -m pytest \
  backend/tests/unit/api/test_research_chat_context.py \
  backend/tests/unit/api/test_diagnostics_endpoints.py \
  backend/tests/unit/api/test_knowledge_graph_merge_jobs.py \
  backend/tests/unit/services/test_hybrid_search_diagnostics.py \
  -q
```

**Step 2: Optional broader safety run**

Run:
```bash
backend/venv/bin/python -m pytest backend/tests/unit/api backend/tests/unit/services -q
```

**Step 3: Review diff quality and risks**

Run:
```bash
git status --short
git diff -- backend/src/api/research/chat.py \
  backend/src/api/diagnostics/retrieval_diagnostics.py \
  backend/src/api/search/knowledge_graph.py \
  backend/src/services/search/hybrid_search_service.py \
  backend/tests/unit/api/test_research_chat_context.py \
  backend/tests/unit/api/test_diagnostics_endpoints.py \
  backend/tests/unit/api/test_knowledge_graph_merge_jobs.py \
  backend/tests/unit/services/test_hybrid_search_diagnostics.py
```

**Step 4: Squash/organize commits as needed and prepare PR summary**

Include:
- fixed runtime bug in background evaluation
- diagnostics endpoints now protected
- merge jobs now enforce tenant ownership pre-queue
- diagnostics experiments now concurrency-safe

