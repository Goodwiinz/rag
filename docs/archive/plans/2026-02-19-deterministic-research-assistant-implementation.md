# Deterministic Research Assistant Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a hybrid-deterministic research assistant path that produces reproducible, evidence-grounded responses with explicit failure modes.

**Architecture:** Route semantic chat to deterministic hybrid retrieval, then produce structured responses through rule-based synthesis and confidence gating. Add trace metadata so decisions can be audited and replayed. Keep optional narrative summarization out of the authoritative deterministic core.

**Tech Stack:** Next.js 15 + TypeScript frontend, FastAPI backend, hybrid search services (full-text/vector/graph), Jest, Pytest.

---

### Task 1: Add deterministic response contract (frontend types)

**Files:**
- Modify: `frontend/src/types/search.ts`
- Test: `frontend/src/components/chat/shared/__tests__/messageViewModel.test.ts`

**Step 1: Write the failing test**

Add a test asserting deterministic fields exist in mapped assistant messages (`claims`, `confidence`, `coverage`, `decisionTraceId`) when present in API response.

```typescript
it('preserves deterministic metadata fields from search result', () => {
  // expect message deterministic metadata to be available for UI rendering
});
```

**Step 2: Run test to verify it fails**

Run: `npm test -- src/components/chat/shared/__tests__/messageViewModel.test.ts`
Expected: FAIL because fields do not exist yet.

**Step 3: Write minimal implementation**

Add deterministic metadata types to `SearchAnswer` and view model interfaces in `frontend/src/types/search.ts` and `frontend/src/components/chat/shared/messageViewModel.ts`.

**Step 4: Run test to verify it passes**

Run: `npm test -- src/components/chat/shared/__tests__/messageViewModel.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/types/search.ts frontend/src/components/chat/shared/messageViewModel.ts frontend/src/components/chat/shared/__tests__/messageViewModel.test.ts
git commit -m "feat: add deterministic metadata contract for search responses"
```

### Task 2: Enforce deterministic hybrid-first routing

**Files:**
- Modify: `frontend/src/services/searchService.ts`
- Test: `frontend/src/services/__tests__/searchService.test.ts`

**Step 1: Write the failing test**

Add tests for deterministic routing behavior:
- primary request uses `/search/hybrid` with `search_type: 'hybrid'`
- fallback on 404 uses `/search/` with `search_type: 'fulltext'`

**Step 2: Run test to verify it fails**

Run: `npm test -- src/services/__tests__/searchService.test.ts`
Expected: FAIL if routing logic diverges.

**Step 3: Write minimal implementation**

Implement hybrid-first call path in `searchService.search()` and preserve fallback behavior.

**Step 4: Run test to verify it passes**

Run: `npm test -- src/services/__tests__/searchService.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/services/searchService.ts frontend/src/services/__tests__/searchService.test.ts
git commit -m "fix: make semantic chat retrieval deterministic hybrid-first"
```

### Task 3: Add backend deterministic answer schema and trace object

**Files:**
- Modify: `backend/src/models/search_schemas.py`
- Modify: `backend/src/api/search/search.py`
- Test: `backend/tests/api/search/test_search_deterministic_response.py` (create)

**Step 1: Write the failing test**

Create API test asserting `/search/hybrid` returns deterministic payload fields:
- `answer_type`
- `claims[]`
- `confidence`
- `coverage`
- `decision_trace_id`

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/api/search/test_search_deterministic_response.py -v`
Expected: FAIL due to missing fields.

**Step 3: Write minimal implementation**

Extend `SearchResponse`-related models (or response envelope) with optional deterministic fields. In `search.py`, populate placeholder deterministic metadata from retrieval results.

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/api/search/test_search_deterministic_response.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/models/search_schemas.py backend/src/api/search/search.py backend/tests/api/search/test_search_deterministic_response.py
git commit -m "feat: add deterministic metadata fields to search responses"
```

### Task 4: Implement deterministic fusion + tie-break rules

**Files:**
- Modify: `backend/src/services/search/hybrid_search_service.py`
- Test: `backend/tests/services/search/test_hybrid_deterministic_ranking.py` (create)

**Step 1: Write the failing test**

Create a ranking test with fixed mock candidates from vector/full-text/graph, asserting exact final order and stable tie-break behavior.

```python
def test_hybrid_ranking_is_stable_for_equal_scores():
    # arrange candidates with equal fused score
    # assert deterministic order by source_quality, updated_at, document_id
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/services/search/test_hybrid_deterministic_ranking.py -v`
Expected: FAIL before deterministic tie-break is implemented.

**Step 3: Write minimal implementation**

Add fixed weighted fusion and explicit tie-break ordering in `hybrid_search_service.py`.

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/services/search/test_hybrid_deterministic_ranking.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/services/search/hybrid_search_service.py backend/tests/services/search/test_hybrid_deterministic_ranking.py
git commit -m "feat: enforce deterministic hybrid fusion and tie-break ordering"
```

### Task 5: Add confidence gate and deterministic failure modes

**Files:**
- Modify: `backend/src/services/search/hybrid_search_service.py`
- Modify: `backend/src/api/search/search.py`
- Test: `backend/tests/api/search/test_search_failure_modes.py` (create)

**Step 1: Write the failing test**

Add tests for low-evidence and conflicting-evidence behavior:
- returns `INSUFFICIENT_EVIDENCE` when source coverage threshold fails
- returns `CONFLICTING_EVIDENCE` when top claims disagree by rule

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/api/search/test_search_failure_modes.py -v`
Expected: FAIL before gate exists.

**Step 3: Write minimal implementation**

Implement deterministic gate checks and explicit status outputs in search response.

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/api/search/test_search_failure_modes.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/services/search/hybrid_search_service.py backend/src/api/search/search.py backend/tests/api/search/test_search_failure_modes.py
git commit -m "feat: add deterministic evidence gating and failure modes"
```

### Task 6: Surface deterministic trace and quality signals in UI

**Files:**
- Modify: `frontend/app/(dashboard)/search/page.tsx`
- Modify: `frontend/src/components/chat/shared/TerminalChatBubble.tsx`
- Modify: `frontend/src/components/chat/shared/messageViewModel.ts`
- Test: `frontend/src/components/chat/shared/__tests__/messageViewModel.test.ts`

**Step 1: Write the failing test**

Add tests that mapped messages expose deterministic status (`confidence`, `coverage`, failure code, trace id).

**Step 2: Run test to verify it fails**

Run: `npm test -- src/components/chat/shared/__tests__/messageViewModel.test.ts`
Expected: FAIL for missing UI-bound fields.

**Step 3: Write minimal implementation**

Render evidence badge and trace indicator in bubble footer; display deterministic failure message blocks when present.

**Step 4: Run test to verify it passes**

Run: `npm test -- src/components/chat/shared/__tests__/messageViewModel.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/app/(dashboard)/search/page.tsx frontend/src/components/chat/shared/TerminalChatBubble.tsx frontend/src/components/chat/shared/messageViewModel.ts frontend/src/components/chat/shared/__tests__/messageViewModel.test.ts
git commit -m "feat: expose deterministic evidence quality and trace metadata in search chat UI"
```

### Task 7: Determinism replay verification and documentation

**Files:**
- Create: `backend/tests/integration/test_search_replay_determinism.py`
- Modify: `docs/architecture/` (add deterministic retrieval note)
- Modify: `docs/guides/` (add operator runbook for deterministic mode)

**Step 1: Write the failing test**

Create integration test that runs same query twice against a fixed fixture snapshot and expects identical deterministic output hash.

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/integration/test_search_replay_determinism.py -v`
Expected: FAIL until output normalization and trace stability are complete.

**Step 3: Write minimal implementation**

Normalize dynamic fields for deterministic mode (or separate replay hash fields) so reproducibility checks are stable.

**Step 4: Run tests and full verification**

Run:
- `pytest backend/tests/api/search/test_search_deterministic_response.py backend/tests/services/search/test_hybrid_deterministic_ranking.py backend/tests/api/search/test_search_failure_modes.py backend/tests/integration/test_search_replay_determinism.py -v`
- `npm test -- src/services/__tests__/searchService.test.ts src/components/chat/shared/__tests__/messageViewModel.test.ts`
- `cd frontend && npm run type-check`

Expected: all pass.

**Step 5: Commit**

```bash
git add backend/tests/integration/test_search_replay_determinism.py docs/architecture docs/guides
git commit -m "test: add deterministic replay verification and operator documentation"
```

## Implementation Rules

- Use @superpowers:test-driven-development for every behavior change.
- Use @superpowers:verification-before-completion before claiming any task success.
- Keep commits small and isolated to each task.
- Do not bundle unrelated refactors.
- Keep deterministic path authoritative; optional narrative mode must not mutate deterministic claims/citations.
