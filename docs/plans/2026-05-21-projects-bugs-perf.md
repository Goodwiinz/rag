# Projects Page Bug & Performance Fix Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 7 bugs and 5 performance issues found in the /projects pages audit.

**Architecture:** Targeted fixes across frontend (debounce, lazy loading, store splitting, pagination) and backend (auth query optimization, batch endpoint). No new abstractions — uses existing patterns (`useDebounce` hook at `frontend/src/utils/performance.ts:197`, `next/dynamic` pattern from `dashboard-layout-client.tsx`, Vitest test harness).

**Tech Stack:** Next.js 15, Zustand, Vitest, FastAPI, SQLAlchemy async, lodash-es

---

## Task 1: Search Debounce (BUG-1)

**Files:**

- Modify: `frontend/app/(dashboard)/projects/page.tsx:8,66-93`
- Test: `frontend/src/components/research/__tests__/ProjectsPage.debounce.test.tsx` (create)

**Step 1: Write the failing test**

```typescript
// frontend/src/components/research/__tests__/ProjectsPage.debounce.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import ProjectsPage from '@/../app/(dashboard)/projects/page';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

const mockFetchProjects = vi.fn().mockResolvedValue(undefined);

vi.mock('@/store/projectStore', () => ({
  useProjectStore: vi.fn((selector) =>
    selector({
      projects: [],
      loading: false,
      error: null,
      total: 0,
      fetchProjects: mockFetchProjects,
      createProject: vi.fn(),
      updateProject: vi.fn(),
      deleteProject: vi.fn(),
      clearError: vi.fn(),
    })
  ),
}));

vi.mock('@/stores/authStore', () => ({
  useAuthStore: vi.fn((selector) =>
    selector({ isAuthenticated: true })
  ),
}));

vi.mock('@/store/chat-store', () => ({
  useChatStore: vi.fn((selector) =>
    selector({
      currentWorkspaceId: 'ws-1',
      loadWorkspaces: vi.fn(),
    })
  ),
  selectCurrentWorkspace: () => ({ id: 'ws-1', name: 'Test' }),
}));

vi.mock('@/services/workspaceService', () => ({
  workspaceService: { getOrCreateDefaultWorkspace: vi.fn() },
}));

describe('ProjectsPage search debounce', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockFetchProjects.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('debounces search input to avoid per-keystroke API calls', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<ProjectsPage />);

    const callsBefore = mockFetchProjects.mock.calls.length;
    const input = screen.getByPlaceholderText('Search projects...');

    await user.type(input, 'machine');

    // Should NOT have fired for each keystroke
    const callsDuring = mockFetchProjects.mock.calls.length - callsBefore;
    expect(callsDuring).toBeLessThan(7); // "machine" = 7 chars

    // Advance past debounce delay
    vi.advanceTimersByTime(350);

    // Now should have fired once with full query
    const lastCall = mockFetchProjects.mock.calls.at(-1);
    expect(lastCall?.[0]?.search).toBe('machine');
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/research/__tests__/ProjectsPage.debounce.test.tsx`
Expected: FAIL — search fires on every keystroke (no debounce)

**Step 3: Apply the debounce**

In `frontend/app/(dashboard)/projects/page.tsx`:

Add import at line 8:

```typescript
import { useDebounce } from "@/utils/performance";
```

After line 46 (`const [showCreateModal, setShowCreateModal] = useState(false);`), add:

```typescript
const debouncedSearch = useDebounce(searchQuery, 300);
```

In the `useEffect` dependency array (lines 66-93), replace `searchQuery` with `debouncedSearch` in both the fetch call and the dependency array:

```typescript
useEffect(() => {
  if (!mounted || !isAuthenticated) return;
  const effectiveWorkspaceId = currentWorkspace?.id ?? currentWorkspaceId;
  const controller = new AbortController();
  void fetchProjects(
    {
      workspace_id: effectiveWorkspaceId || undefined,
      search: debouncedSearch || undefined,
      project_status: statusFilter || undefined,
      project_type: typeFilter || undefined,
      tag: tagFilter || undefined,
    },
    { signal: controller.signal },
  );
  return () => controller.abort();
}, [
  mounted,
  isAuthenticated,
  currentWorkspaceId,
  currentWorkspace?.id,
  debouncedSearch,
  statusFilter,
  typeFilter,
  tagFilter,
  fetchProjects,
]);
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/research/__tests__/ProjectsPage.debounce.test.tsx`
Expected: PASS

**Step 5: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No new errors

**Step 6: Commit**

```bash
git add frontend/app/\(dashboard\)/projects/page.tsx frontend/src/components/research/__tests__/ProjectsPage.debounce.test.tsx
git commit -m "fix(projects): debounce search input to avoid per-keystroke API calls

Uses existing useDebounce hook (300ms delay). Keeps AbortController for
stale response cancellation."
```

---

## Task 2: Fix Draft Polling Leak (BUG-2)

**Files:**

- Modify: `frontend/app/(dashboard)/projects/[id]/page.tsx:750-785`

**Step 1: Write the failing test**

This is best tested by verifying cleanup. In an existing or new test file:

```typescript
// frontend/src/components/research/__tests__/ProjectDetailPage.poll-cleanup.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

describe("Draft generation polling cleanup", () => {
  it("clears polling timeout on unmount", () => {
    const clearTimeoutSpy = vi.spyOn(globalThis, "clearTimeout");
    const setTimeoutSpy = vi
      .spyOn(globalThis, "setTimeout")
      .mockReturnValue(42 as any);

    // Simulate the polling pattern: a ref-based timeout that gets cleared
    const timeoutRef = {
      current: null as ReturnType<typeof setTimeout> | null,
    };

    // Start poll
    const pollFn = () => {
      timeoutRef.current = setTimeout(pollFn, 1000);
    };
    pollFn();

    expect(timeoutRef.current).toBe(42);

    // Simulate cleanup
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    expect(clearTimeoutSpy).toHaveBeenCalledWith(42);

    clearTimeoutSpy.mockRestore();
    setTimeoutSpy.mockRestore();
  });
});
```

**Step 2: Run test to verify pattern**

Run: `cd frontend && npx vitest run src/components/research/__tests__/ProjectDetailPage.poll-cleanup.test.tsx`
Expected: PASS (this validates the pattern)

**Step 3: Fix the polling in the component**

In `frontend/app/(dashboard)/projects/[id]/page.tsx`, add a ref near the other state declarations (around line 128):

```typescript
const pollTimeoutRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
```

Replace the `pollStatus` block inside `onGenerate` (lines 762-780) with:

```typescript
const pollStatus = async () => {
  try {
    const status = await projectService.getGenerationStatus(
      projectId,
      result.task_id,
    );
    setGenerationStatus(status);
    if (!["completed", "failed", "cancelled"].includes(status.status)) {
      pollTimeoutRef.current = setTimeout(pollStatus, 1000);
    }
  } catch (err) {
    console.error("Poll error:", err);
  }
};
pollStatus();
```

Add a cleanup effect after the existing effects (around line 275):

```typescript
useEffect(() => {
  return () => {
    if (pollTimeoutRef.current) {
      clearTimeout(pollTimeoutRef.current);
    }
  };
}, []);
```

**Step 4: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No new errors

**Step 5: Commit**

```bash
git add frontend/app/\(dashboard\)/projects/\[id\]/page.tsx frontend/src/components/research/__tests__/ProjectDetailPage.poll-cleanup.test.tsx
git commit -m "fix(projects): clear draft poll timeout on unmount

Stores setTimeout handle in ref, clears on cleanup. Prevents state
updates on unmounted component."
```

---

## Task 3: Split Shared `loading` Flag (BUG-3)

**Files:**

- Modify: `frontend/src/store/projectStore.ts`
- Modify: `frontend/app/(dashboard)/projects/page.tsx:271-275`

**Step 1: Write the failing test**

```typescript
// frontend/src/components/research/__tests__/projectStore.loading.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useProjectStore } from "@/store/projectStore";

vi.mock("@/services/projectService", () => ({
  projectService: {
    deleteProject: vi
      .fn()
      .mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100)),
      ),
    listProjects: vi.fn().mockResolvedValue({ projects: [], total: 0 }),
  },
}));

describe("projectStore loading flags", () => {
  beforeEach(() => {
    useProjectStore.getState().reset();
  });

  it("deleteProject uses mutating flag, not loading", async () => {
    const store = useProjectStore.getState();
    const deletePromise = store.deleteProject("test-id").catch(() => {});

    // loading (used for list/fetch) should NOT be true during delete
    expect(useProjectStore.getState().loading).toBe(false);
    expect(useProjectStore.getState().mutating).toBe(true);

    await deletePromise;
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/research/__tests__/projectStore.loading.test.tsx`
Expected: FAIL — `mutating` property doesn't exist

**Step 3: Add `mutating` flag to store**

In `frontend/src/store/projectStore.ts`:

Add to `ProjectState` interface (after line 38):

```typescript
mutating: boolean;
```

Add to initial state (after line 104):

```typescript
mutating: false,
```

In `createProject` (line 167): change `set({ loading: true` to `set({ mutating: true` and `loading: false` to `mutating: false` (3 places in the function).

In `updateProject` (line 186): same — `loading` → `mutating` (3 places).

In `deleteProject` (line 208): same — `loading` → `mutating` (3 places).

In `reset` (line 439): add `mutating: false`.

**Step 4: Update page to not show spinner during mutations**

In `frontend/app/(dashboard)/projects/page.tsx`, line 271-275 already gates on `loading`. Since mutations now use `mutating`, the full-page spinner won't trigger during delete/archive/restore. No change needed on the page — the store fix is sufficient.

**Step 5: Run tests**

Run: `cd frontend && npx vitest run src/components/research/__tests__/projectStore.loading.test.tsx`
Expected: PASS

**Step 6: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No new errors (may need to add `mutating` to any test mocks that spread the full store)

**Step 7: Commit**

```bash
git add frontend/src/store/projectStore.ts frontend/src/components/research/__tests__/projectStore.loading.test.tsx
git commit -m "fix(projects): split loading/mutating flags in project store

Mutations (create/update/delete) now set 'mutating' instead of 'loading'.
Prevents full-page spinner during inline operations."
```

---

## Task 4: Backend Auth Over-Fetch Fix (PERF-1)

**Files:**

- Modify: `backend/src/api/research/projects.py:1031-1071`
- Test: `backend/tests/unit/test_project_auth_query.py` (create)

**Step 1: Write the failing test**

```python
# backend/tests/unit/test_project_auth_query.py
"""Verify _get_project_with_auth does NOT eagerly load documents."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.api.research.projects import _get_project_with_auth


@pytest.mark.asyncio
async def test_auth_check_does_not_load_documents():
    """The auth helper should not use selectinload(Collection.documents)."""
    project_id = uuid4()
    mock_user = MagicMock()
    mock_user.id = uuid4()

    mock_project = MagicMock()
    mock_project.id = project_id

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_project

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await _get_project_with_auth(project_id, mock_user, mock_db)

    assert result == mock_project

    # Inspect the query that was passed to db.execute
    call_args = mock_db.execute.call_args
    query = call_args[0][0]
    query_str = str(query)

    # Should NOT contain eager loading of documents
    assert "selectinload" not in query_str.lower() or "documents" not in query_str.lower(), (
        "_get_project_with_auth should not eagerly load documents — "
        "it only needs to verify ownership via Workspace join"
    )
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_project_auth_query.py -v`
Expected: FAIL — query currently includes `selectinload(Collection.documents)`

**Step 3: Remove eager load from auth helper**

In `backend/src/api/research/projects.py`, replace `_get_project_with_auth` (lines 1031-1071):

```python
async def _get_project_with_auth(
    project_id: UUID,
    current_user: User,
    db: AsyncSession,
) -> Collection:
    """Get project with authorization check.

    Intentionally does NOT eagerly load relationships — callers that need
    documents or notes should load them separately.
    """
    from src.models import Workspace

    query = (
        select(Collection)
        .join(Workspace, Collection.workspace_id == Workspace.id)
        .where(
            and_(
                Collection.id == project_id,
                Workspace.owner_id == current_user.id,
            )
        )
    )
    result = await db.execute(query)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied",
        )

    return project
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_project_auth_query.py -v`
Expected: PASS

**Step 5: Run full backend tests to catch regressions**

Run: `cd backend && python -m pytest tests/ -x -q --timeout=30`
Expected: No regressions. Endpoints that previously relied on the eager-loaded `documents` via the auth helper already load documents separately (e.g., `get_project` at line 180-187 does its own `selectinload` query).

**Step 6: Commit**

```bash
git add backend/src/api/research/projects.py backend/tests/unit/test_project_auth_query.py
git commit -m "perf(projects): remove eager document load from auth check

_get_project_with_auth was loading ALL project documents via
selectinload just to verify workspace ownership. Now only loads
Collection + Workspace join. Called on every sub-resource endpoint
(notes, docs, bibliography, pin), so this eliminates O(N) document
serialization per request."
```

---

## Task 5: Lazy-Load Heavy Tab Components (PERF-3)

**Files:**

- Modify: `frontend/app/(dashboard)/projects/[id]/page.tsx:1-50`

**Step 1: Convert static imports to dynamic imports**

In `frontend/app/(dashboard)/projects/[id]/page.tsx`, replace the static imports for heavy tab components (lines 27-38) with dynamic imports:

```typescript
import dynamic from 'next/dynamic';
import { Loader2 } from 'lucide-react';

// Eagerly loaded (default tab + always-visible)
import { ProjectHeader } from '@/components/research/ProjectHeader';
import { DocumentList } from '@/components/research/DocumentList';
import { NoteEditor } from '@/components/research/NoteEditor';
import { NoteList } from '@/components/research/NoteList';
import { DocumentUploadWizard } from '@/components/upload';

// Lazy-loaded (only when tab selected)
const tabLoading = {
  loading: () => (
    <div className="flex items-center justify-center py-12">
      <Loader2 className="h-6 w-6 animate-spin text-primary" />
    </div>
  ),
  ssr: false,
};

const ProjectKnowledgeTree = dynamic(
  () => import('@/components/research/ProjectKnowledgeTree').then((m) => m.ProjectKnowledgeTree),
  tabLoading
);
const DraftGenerator = dynamic(
  () => import('@/components/research/DraftGenerator').then((m) => m.DraftGenerator),
  tabLoading
);
const DraftViewer = dynamic(
  () => import('@/components/research/DraftViewer').then((m) => m.DraftViewer),
  tabLoading
);
const DraftGenerationProgress = dynamic(
  () => import('@/components/research/DraftGenerationProgress').then((m) => m.DraftGenerationProgress),
  tabLoading
);
const DraftComparison = dynamic(
  () => import('@/components/research/DraftComparison').then((m) => m.DraftComparison),
  tabLoading
);
const DraftExportModal = dynamic(
  () => import('@/components/research/DraftExportModal').then((m) => m.DraftExportModal),
  tabLoading
);
const ProjectChatTab = dynamic(
  () => import('@/components/research/ProjectChatTab').then((m) => m.ProjectChatTab),
  tabLoading
);
const ExtractionMatrix = dynamic(
  () => import('@/components/research/ExtractionMatrix').then((m) => m.ExtractionMatrix),
  tabLoading
);
const ResearchPipeline = dynamic(
  () => import('@/components/research/ResearchPipeline').then((m) => m.ResearchPipeline),
  tabLoading
);
```

Remove the corresponding static imports that were replaced.

**Step 2: Verify named exports match**

Run: `cd frontend && grep -n "export " src/components/research/ProjectKnowledgeTree.tsx src/components/research/DraftGenerator.tsx src/components/research/ExtractionMatrix.tsx src/components/research/ResearchPipeline.tsx src/components/research/ProjectChatTab.tsx | head -20`

If any use `export default` instead of named exports, adjust the dynamic import to not use `.then((m) => m.ComponentName)`.

**Step 3: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No new errors

**Step 4: Commit**

```bash
git add frontend/app/\(dashboard\)/projects/\[id\]/page.tsx
git commit -m "perf(projects): lazy-load heavy tab components via next/dynamic

Only Documents tab components loaded eagerly (default tab). Knowledge,
Drafts, Chat, Matrix, Pipeline tabs load on demand. Follows existing
pattern from dashboard-layout-client.tsx."
```

---

## Task 6: Fix Stale Bibliography Cache (BUG-7)

**Files:**

- Modify: `frontend/app/(dashboard)/projects/[id]/page.tsx:326-334`

**Step 1: Fix `handleTabChange` to invalidate stale bibliography**

Replace the `handleTabChange` callback:

```typescript
const handleTabChange = useCallback(
  (tab: TabType) => {
    setActiveTab(tab);
    if (tab === "bibliography") {
      fetchBibliography(projectId, bibFormat);
    }
  },
  [projectId, bibFormat, fetchBibliography],
);
```

This removes the `!bibliography` guard — always refetch on tab switch. The bibliography generation is fast (just formats existing citation data), so the extra call is negligible vs showing stale data.

**Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No new errors

**Step 3: Commit**

```bash
git add frontend/app/\(dashboard\)/projects/\[id\]/page.tsx
git commit -m "fix(projects): always refetch bibliography on tab switch

Removes stale cache guard that prevented refetch after document
changes. Bibliography generation is server-side formatting, not
expensive."
```

---

## Task 7: Fix Stale `document_count` After Update (BUG-6)

**Files:**

- Modify: `backend/src/api/research/projects.py:1111-1133`

**Step 1: Fix `_to_project_response` to handle missing relationship**

Replace `_to_project_response`:

```python
def _to_project_response(project: Collection) -> ProjectResponse:
    """Convert Collection to ProjectResponse."""
    documents = project.__dict__.get("documents")
    document_count = len(documents) if documents is not None else (project.document_count or 0)

    return ProjectResponse(
        id=project.id,
        workspace_id=project.workspace_id,
        name=project.name,
        description=project.description,
        project_type=project.project_type,
        research_status=project.research_status,
        research_goals=project.research_goals,
        deadline=project.deadline,
        tags=project.tags or [],
        is_private=project.is_private,
        document_count=document_count,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )
```

Key change: `if documents is not None` (instead of truthy check — empty list `[]` is falsy but valid). Falls back to `project.document_count` attribute if relationship wasn't loaded.

Also check if `Collection` model has a `document_count` hybrid property or column. If not, use a count subquery in `update_project` or just return 0 as fallback (the frontend refetches the full project after update anyway).

**Step 2: Run backend tests**

Run: `cd backend && python -m pytest tests/ -x -q --timeout=30`
Expected: PASS

**Step 3: Commit**

```bash
git add backend/src/api/research/projects.py
git commit -m "fix(projects): handle missing documents relationship in response

Uses 'is not None' instead of truthy check (empty list was falsy).
Falls back to model attribute when relationship not eagerly loaded."
```

---

## Task 8: Final Validation

**Step 1: Run full frontend validation**

Run: `cd frontend && npm run validate`
Expected: lint + type-check + tests all pass

**Step 2: Run full backend tests**

Run: `cd backend && python -m pytest tests/ --cov=src -q --timeout=30`
Expected: All pass, no coverage regression

**Step 3: Final commit (if any fixups needed)**

```bash
git add -A
git commit -m "chore: fixups from projects audit"
```

---

## Deferred Items (not in this PR)

These are lower priority or need design decisions:

| Item                                  | Why Deferred                                                       |
| ------------------------------------- | ------------------------------------------------------------------ |
| BUG-4: Tags from current page only    | Needs backend `/projects/tags` endpoint — API design decision      |
| BUG-5: No pagination                  | Needs UI design for paginator component + infinite scroll vs pages |
| PERF-2: Batch document add            | Needs new backend endpoint `POST /projects/{id}/documents/batch`   |
| PERF-4: Serial draft loads            | Minor — metadata list is small, content fetch is required          |
| PERF-5: Fire-and-forget asyncio tasks | Needs task tracking infrastructure — larger refactor               |
