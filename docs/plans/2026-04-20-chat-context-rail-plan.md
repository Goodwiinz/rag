# Chat Context Rail Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a right-rail to the chat page with three stacked cards — Agent Activity (live tool-call checklist), Related Results, All-thread Citations — restoring the features deleted when `ContextPanel` was removed.

**Architecture:** New `<ContextRail>` container mounted in `chat/layout.tsx`; wraps a zustand-backed live agent-step store (`agentActivityStore`) driven by existing `onToolStart`/`onToolEnd` callbacks in `chat/page.tsx`; citation panels reuse existing `useCitationsForThread()` hook. Zero backend changes.

**Tech Stack:** React 18 + Next.js 15 (app router), TypeScript strict, Tailwind CSS with NOUS design tokens (`var(--nous-*)`), Jest + React Testing Library, Zustand 5.

**Design doc:** `docs/plans/2026-04-20-chat-context-rail-design.md`

**Branch:** `feat/chat-context-rail` (already created)

**Working tree caveat:** a parallel Claude session has uncommitted edits on `chat/layout.tsx`, `chat/page.tsx`, `design-system/page.tsx`, `nous-tokens.css`, and backend agent/azure files. **Do not stage or modify those files** except the minimal edits in Tasks 8 and 9 below (which are additive, single-line inserts). If a merge conflict emerges on `chat/layout.tsx`, pivot to Approach Y (mount in `chat/page.tsx`) — see design doc §Coordination.

---

## Task 1: Scaffold directories and path alias

**Files:**
- Modify: `frontend/tsconfig.json` — add explicit alias so panels can import `NousAgentStatusCard` cleanly
- Create: `frontend/src/components/context-rail/` (empty dir; created implicitly by later tasks)
- Create: `frontend/src/components/context-rail/__tests__/` (empty dir)

**Why this task exists:** `NousAgentStatusCard` lives at `frontend/app/components/nous/`, outside the `@/components/*` → `./src/components/*` alias in `tsconfig.json`. Adding a specific override lets new panels import it as `@/nous` without relative path soup.

**Step 1: Inspect current paths block**

Run: `grep -A 30 '"paths"' frontend/tsconfig.json`

Expected: existing mappings including `"@/components/*": ["./src/components/*"]`.

**Step 2: Add the alias**

Edit `frontend/tsconfig.json` — add this entry to the `paths` object (alphabetized placement near other `@/nous` or `@/types` entries is fine):

```json
"@/nous": ["./app/components/nous/index.ts"],
"@/nous/*": ["./app/components/nous/*"]
```

**Step 3: Verify the alias resolves**

Run: `cd frontend && npx tsc --noEmit --listFiles 2>&1 | head -20`

Expected: no errors; command exits 0 (ignore listFiles noise; we just care it type-checks).

**Step 4: Commit**

```bash
git add frontend/tsconfig.json
git commit -m "feat(chat): add @/nous path alias for design-system primitives" -m "Needed by the upcoming chat context rail so its panels can import NousAgentStatusCard without relative path traversal."
```

---

## Task 2: `agentActivityStore` — store with TDD

**Files:**
- Create: `frontend/src/stores/agentActivityStore.ts`
- Create: `frontend/src/stores/__tests__/agentActivityStore.test.ts`

**Step 1: Write the failing test file**

Create `frontend/src/stores/__tests__/agentActivityStore.test.ts`:

```ts
// @ts-nocheck
import { useAgentActivityStore } from '../agentActivityStore';

describe('agentActivityStore', () => {
  beforeEach(() => {
    useAgentActivityStore.setState({ runs: {}, currentThreadId: null });
  });

  const getRun = (threadId: string) =>
    useAgentActivityStore.getState().runs[threadId];

  it('startRun initializes a running run with empty steps', () => {
    useAgentActivityStore
      .getState()
      .startRun('t1', 'Literature synth', 'Reviewing Mamba-2');

    const run = getRun('t1');
    expect(run.state).toBe('running');
    expect(run.name).toBe('Literature synth');
    expect(run.task).toBe('Reviewing Mamba-2');
    expect(run.steps).toEqual([]);
  });

  it('pushToolStart appends an active step with a mapped label', () => {
    const { startRun, pushToolStart } = useAgentActivityStore.getState();
    startRun('t1', 'NOUS Agent', 'task');
    pushToolStart('t1', 'arxiv_search');

    const steps = getRun('t1').steps;
    expect(steps).toHaveLength(1);
    expect(steps[0].tool).toBe('arxiv_search');
    expect(steps[0].status).toBe('active');
    expect(steps[0].label).toBe('Search arXiv');
  });

  it('duplicate pushToolStart for same tool is de-duped while active', () => {
    const { startRun, pushToolStart } = useAgentActivityStore.getState();
    startRun('t1', 'NOUS Agent', 'task');
    pushToolStart('t1', 'arxiv_search');
    pushToolStart('t1', 'arxiv_search');
    expect(getRun('t1').steps).toHaveLength(1);
  });

  it('pushToolEnd flips matching active step to done', () => {
    const { startRun, pushToolStart, pushToolEnd } =
      useAgentActivityStore.getState();
    startRun('t1', 'NOUS Agent', 'task');
    pushToolStart('t1', 'arxiv_search');
    pushToolEnd('t1', 'arxiv_search', true);
    expect(getRun('t1').steps[0].status).toBe('done');
  });

  it('pushToolEnd with ok=false flips to error', () => {
    const { startRun, pushToolStart, pushToolEnd } =
      useAgentActivityStore.getState();
    startRun('t1', 'NOUS Agent', 'task');
    pushToolStart('t1', 'arxiv_search');
    pushToolEnd('t1', 'arxiv_search', false);
    expect(getRun('t1').steps[0].status).toBe('error');
  });

  it('pushToolEnd for unknown tool is ignored', () => {
    const { startRun, pushToolEnd } = useAgentActivityStore.getState();
    startRun('t1', 'NOUS Agent', 'task');
    pushToolEnd('t1', 'nothing_here', true);
    expect(getRun('t1').steps).toEqual([]);
  });

  it('finishRun transitions running → done', () => {
    const { startRun, finishRun } = useAgentActivityStore.getState();
    startRun('t1', 'NOUS Agent', 'task');
    finishRun('t1', 'done');
    expect(getRun('t1').state).toBe('done');
  });

  it('finishRun transitions running → error', () => {
    const { startRun, finishRun } = useAgentActivityStore.getState();
    startRun('t1', 'NOUS Agent', 'task');
    finishRun('t1', 'error');
    expect(getRun('t1').state).toBe('error');
  });

  it('runs are isolated per thread', () => {
    const { startRun, pushToolStart } = useAgentActivityStore.getState();
    startRun('t1', 'A', 'taskA');
    startRun('t2', 'B', 'taskB');
    pushToolStart('t1', 'arxiv_search');
    expect(getRun('t1').steps).toHaveLength(1);
    expect(getRun('t2').steps).toHaveLength(0);
    expect(getRun('t1').name).toBe('A');
    expect(getRun('t2').name).toBe('B');
  });

  it('startRun on existing thread replaces prior run', () => {
    const { startRun, pushToolStart } = useAgentActivityStore.getState();
    startRun('t1', 'A', 'first');
    pushToolStart('t1', 'arxiv_search');
    startRun('t1', 'A', 'second');
    expect(getRun('t1').task).toBe('second');
    expect(getRun('t1').steps).toEqual([]);
  });
});
```

**Step 2: Run test to confirm it fails**

Run: `cd frontend && npx jest src/stores/__tests__/agentActivityStore.test.ts`

Expected: **FAIL** with `Cannot find module '../agentActivityStore'`.

**Step 3: Implement the store**

Create `frontend/src/stores/agentActivityStore.ts`:

```ts
import { create } from 'zustand';
import { toolLabel } from '@/components/context-rail/toolLabels';

export type StepStatus = 'active' | 'done' | 'error';

export interface Step {
  id: string;
  tool: string;
  label: string;
  status: StepStatus;
  at: number;
}

export interface Run {
  threadId: string;
  name: string;
  task: string;
  steps: Step[];
  state: 'running' | 'done' | 'error';
  startedAt: number;
}

interface AgentActivityState {
  runs: Record<string, Run>;
  currentThreadId: string | null;
  startRun: (threadId: string, name: string, task: string) => void;
  pushToolStart: (threadId: string, tool: string) => void;
  pushToolEnd: (threadId: string, tool: string, ok: boolean) => void;
  finishRun: (threadId: string, state: 'done' | 'error') => void;
}

let seq = 0;
const nextId = () => `step-${Date.now()}-${++seq}`;

export const useAgentActivityStore = create<AgentActivityState>((set) => ({
  runs: {},
  currentThreadId: null,

  startRun: (threadId, name, task) =>
    set((s) => ({
      currentThreadId: threadId,
      runs: {
        ...s.runs,
        [threadId]: {
          threadId,
          name,
          task,
          steps: [],
          state: 'running',
          startedAt: Date.now(),
        },
      },
    })),

  pushToolStart: (threadId, tool) =>
    set((s) => {
      const run = s.runs[threadId];
      if (!run) return s;
      const existing = run.steps.find(
        (st) => st.tool === tool && st.status === 'active'
      );
      if (existing) return s;
      const step: Step = {
        id: nextId(),
        tool,
        label: toolLabel(tool),
        status: 'active',
        at: Date.now(),
      };
      return {
        runs: {
          ...s.runs,
          [threadId]: { ...run, steps: [...run.steps, step] },
        },
      };
    }),

  pushToolEnd: (threadId, tool, ok) =>
    set((s) => {
      const run = s.runs[threadId];
      if (!run) return s;
      const idx = run.steps.findIndex(
        (st) => st.tool === tool && st.status === 'active'
      );
      if (idx < 0) return s;
      const next = [...run.steps];
      next[idx] = { ...next[idx], status: ok ? 'done' : 'error' };
      return {
        runs: { ...s.runs, [threadId]: { ...run, steps: next } },
      };
    }),

  finishRun: (threadId, state) =>
    set((s) => {
      const run = s.runs[threadId];
      if (!run) return s;
      return {
        runs: { ...s.runs, [threadId]: { ...run, state } },
      };
    }),
}));
```

**Note:** this file imports `@/components/context-rail/toolLabels`, which doesn't exist yet. Create a stub so the test can run — Task 3 replaces it with the full table.

Create `frontend/src/components/context-rail/toolLabels.ts`:

```ts
export function toolLabel(tool: string): string {
  const known: Record<string, string> = {
    arxiv_search: 'Search arXiv',
  };
  return known[tool] ?? tool.replace(/_/g, ' ');
}
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npx jest src/stores/__tests__/agentActivityStore.test.ts`

Expected: **PASS** all 10 tests.

**Step 5: Commit**

```bash
git add frontend/src/stores/agentActivityStore.ts \
        frontend/src/stores/__tests__/agentActivityStore.test.ts \
        frontend/src/components/context-rail/toolLabels.ts
git commit -m "feat(chat): add agentActivityStore for live tool-call tracking" -m "Zustand store keyed by thread id. Holds a running/done/error run with appended active/done/error steps driven by tool_start and tool_end events."
```

---

## Task 3: `toolLabels` — full map with TDD

**Files:**
- Modify: `frontend/src/components/context-rail/toolLabels.ts`
- Create: `frontend/src/components/context-rail/__tests__/toolLabels.test.ts`

**Step 1: Write the failing test**

Create `frontend/src/components/context-rail/__tests__/toolLabels.test.ts`:

```ts
// @ts-nocheck
import { toolLabel } from '../toolLabels';

describe('toolLabel', () => {
  it.each([
    ['arxiv_search', 'Search arXiv'],
    ['arxiv_ingest', 'Ingest papers'],
    ['document_search', 'Search documents'],
    ['ingest_document', 'Ingest document'],
    ['create_draft', 'Draft synthesis'],
    ['create_note', 'Save note'],
    ['entity_search', 'Query entities'],
    ['kg_query', 'Query knowledge graph'],
    ['project_create', 'Create project'],
    ['compare_documents', 'Compare documents'],
    ['reflect', 'Reflect on progress'],
  ])('maps %s → %s', (tool, expected) => {
    expect(toolLabel(tool)).toBe(expected);
  });

  it('falls back to Title Case for unknown tools', () => {
    expect(toolLabel('foo_bar_baz')).toBe('Foo Bar Baz');
  });

  it('leaves single-word tools as Title Case', () => {
    expect(toolLabel('ponder')).toBe('Ponder');
  });
});
```

**Step 2: Run test to confirm partial failure**

Run: `cd frontend && npx jest src/components/context-rail/__tests__/toolLabels.test.ts`

Expected: **FAIL** — stub only has `arxiv_search` and does not Title-Case unknown tools.

**Step 3: Expand the map**

Replace `frontend/src/components/context-rail/toolLabels.ts` with:

```ts
const KNOWN_TOOLS: Record<string, string> = {
  arxiv_search: 'Search arXiv',
  arxiv_ingest: 'Ingest papers',
  document_search: 'Search documents',
  ingest_document: 'Ingest document',
  create_draft: 'Draft synthesis',
  create_note: 'Save note',
  entity_search: 'Query entities',
  kg_query: 'Query knowledge graph',
  project_create: 'Create project',
  compare_documents: 'Compare documents',
  reflect: 'Reflect on progress',
};

export function toolLabel(tool: string): string {
  if (KNOWN_TOOLS[tool]) return KNOWN_TOOLS[tool];
  return tool
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npx jest src/components/context-rail/__tests__/toolLabels.test.ts`

Expected: **PASS** all tests.

**Step 5: Commit**

```bash
git add frontend/src/components/context-rail/toolLabels.ts \
        frontend/src/components/context-rail/__tests__/toolLabels.test.ts
git commit -m "feat(chat): expand toolLabels map + Title-Case fallback"
```

---

## Task 4: `AgentActivityPanel` — render the store

**Files:**
- Create: `frontend/src/components/context-rail/AgentActivityPanel.tsx`
- Create: `frontend/src/components/context-rail/__tests__/AgentActivityPanel.test.tsx`

**Step 1: Write the failing test**

Create `frontend/src/components/context-rail/__tests__/AgentActivityPanel.test.tsx`:

```tsx
// @ts-nocheck
/* eslint-disable @typescript-eslint/no-explicit-any */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { AgentActivityPanel } from '../AgentActivityPanel';
import { useAgentActivityStore } from '@/stores/agentActivityStore';

describe('AgentActivityPanel', () => {
  beforeEach(() => {
    useAgentActivityStore.setState({ runs: {}, currentThreadId: null });
  });

  it('returns null when no run exists for the thread', () => {
    const { container } = render(<AgentActivityPanel threadId="t-missing" />);
    expect(container.firstChild).toBeNull();
  });

  it('renders name, task, and step labels during running state', () => {
    const store = useAgentActivityStore.getState();
    store.startRun('t1', 'Literature synth', 'Reviewing Mamba-2');
    store.pushToolStart('t1', 'arxiv_search');
    store.pushToolEnd('t1', 'arxiv_search', true);
    store.pushToolStart('t1', 'create_draft');

    render(<AgentActivityPanel threadId="t1" />);

    expect(screen.getByText('Literature synth')).toBeInTheDocument();
    expect(screen.getByText('Reviewing Mamba-2')).toBeInTheDocument();
    expect(screen.getByText('Search arXiv')).toBeInTheDocument();
    expect(screen.getByText('Draft synthesis')).toBeInTheDocument();
  });

  it('renders frozen list when run has finished', () => {
    const store = useAgentActivityStore.getState();
    store.startRun('t1', 'NOUS Agent', 'done task');
    store.pushToolStart('t1', 'arxiv_search');
    store.pushToolEnd('t1', 'arxiv_search', true);
    store.finishRun('t1', 'done');

    render(<AgentActivityPanel threadId="t1" />);

    expect(screen.getByText('Search arXiv')).toBeInTheDocument();
  });
});
```

**Step 2: Run to confirm failure**

Run: `cd frontend && npx jest src/components/context-rail/__tests__/AgentActivityPanel.test.tsx`

Expected: **FAIL** — `Cannot find module '../AgentActivityPanel'`.

**Step 3: Implement the panel**

Create `frontend/src/components/context-rail/AgentActivityPanel.tsx`:

```tsx
'use client';

import * as React from 'react';
import { NousAgentStatusCard, type AgentStep } from '@/nous';
import { useAgentActivityStore } from '@/stores/agentActivityStore';
import type { Step } from '@/stores/agentActivityStore';

interface AgentActivityPanelProps {
  threadId: string | null;
}

function toAgentStep(step: Step): AgentStep {
  return {
    label: step.label,
    status:
      step.status === 'done'
        ? 'done'
        : step.status === 'error'
          ? 'done'
          : 'active',
  };
}

export function AgentActivityPanel({ threadId }: AgentActivityPanelProps) {
  const run = useAgentActivityStore((s) =>
    threadId ? s.runs[threadId] : undefined
  );

  if (!run) return null;

  return (
    <section aria-label="Agent activity">
      <div
        className="text-[10px] uppercase tracking-wider mb-2 px-1"
        style={{
          color: 'var(--nous-fg-3)',
          fontFamily: 'var(--nous-font-ui)',
        }}
      >
        Agent Activity
      </div>
      <NousAgentStatusCard
        name={run.name}
        task={run.task}
        steps={run.steps.map(toAgentStep)}
      />
    </section>
  );
}
```

**Note on the `error → done` collapse:** `NousAgentStatusCard` only knows three visual statuses (`done | active | pending`). Error steps render with strike-through like `done` — semantic difference is preserved in the store but not in v1 visuals. Promotion path is adding an `error` variant to `NousAgentStatusCard` later.

**Step 4: Run test to verify it passes**

Run: `cd frontend && npx jest src/components/context-rail/__tests__/AgentActivityPanel.test.tsx`

Expected: **PASS** all 3 tests.

**Step 5: Commit**

```bash
git add frontend/src/components/context-rail/AgentActivityPanel.tsx \
        frontend/src/components/context-rail/__tests__/AgentActivityPanel.test.tsx
git commit -m "feat(chat): add AgentActivityPanel driven by agentActivityStore"
```

---

## Task 5: `RelatedResultsPanel` — top-5 related docs

**Files:**
- Create: `frontend/src/components/context-rail/RelatedResultsPanel.tsx`
- Create: `frontend/src/components/context-rail/__tests__/RelatedResultsPanel.test.tsx`

**Step 1: Write the failing test**

Create `frontend/src/components/context-rail/__tests__/RelatedResultsPanel.test.tsx`:

```tsx
// @ts-nocheck
/* eslint-disable @typescript-eslint/no-explicit-any */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { RelatedResultsPanel } from '../RelatedResultsPanel';

jest.mock('@/hooks', () => ({
  useCitationsForThread: jest.fn(),
}));

const { useCitationsForThread } = require('@/hooks');

describe('RelatedResultsPanel', () => {
  beforeEach(() => jest.clearAllMocks());

  it('renders empty state when no related results', () => {
    useCitationsForThread.mockReturnValue({
      allCitations: [],
      activeDocument: null,
      relatedResults: [],
    });
    render(<RelatedResultsPanel />);
    expect(screen.getByText(/no related results/i)).toBeInTheDocument();
  });

  it('renders populated list with titles and scores', () => {
    useCitationsForThread.mockReturnValue({
      allCitations: [],
      activeDocument: null,
      relatedResults: [
        { documentId: 'd1', title: 'Paper A', score: 0.82, source: 'arxiv' },
        { documentId: 'd2', title: 'Paper B', score: 0.55, source: 'upload' },
      ],
    });
    render(<RelatedResultsPanel />);
    expect(screen.getByText('Paper A')).toBeInTheDocument();
    expect(screen.getByText('Paper B')).toBeInTheDocument();
    expect(screen.getByText('82%')).toBeInTheDocument();
    expect(screen.getByText('55%')).toBeInTheDocument();
  });
});
```

**Step 2: Run to confirm failure**

Run: `cd frontend && npx jest src/components/context-rail/__tests__/RelatedResultsPanel.test.tsx`

Expected: **FAIL** with module-not-found.

**Step 3: Implement**

Create `frontend/src/components/context-rail/RelatedResultsPanel.tsx`:

```tsx
'use client';

import * as React from 'react';
import { FileText } from 'lucide-react';
import { useCitationsForThread } from '@/hooks';

function scoreColor(percent: number): string {
  if (percent >= 70) return 'var(--nous-terra)';
  if (percent >= 50) return 'var(--nous-corona)';
  return 'var(--nous-fg-3)';
}

export function RelatedResultsPanel() {
  const { relatedResults } = useCitationsForThread();

  return (
    <section aria-label="Related results">
      <div
        className="text-[10px] uppercase tracking-wider mb-2 px-1"
        style={{
          color: 'var(--nous-fg-3)',
          fontFamily: 'var(--nous-font-ui)',
        }}
      >
        Related Results
      </div>

      {relatedResults.length === 0 ? (
        <div
          className="rounded-xl border p-4 text-xs"
          style={{
            borderColor: 'var(--nous-border-1)',
            background: 'var(--nous-bg-2)',
            color: 'var(--nous-fg-3)',
            fontFamily: 'var(--nous-font-body)',
          }}
        >
          No related results yet. Ask a question to pull relevant documents.
        </div>
      ) : (
        <ul
          className="rounded-xl border p-2 space-y-1"
          style={{
            borderColor: 'var(--nous-border-1)',
            background: 'var(--nous-bg-2)',
          }}
        >
          {relatedResults.map((doc, idx) => {
            const pct = doc.score ? Math.round(doc.score * 100) : 0;
            return (
              <li
                key={doc.documentId || doc.externalReferenceId || idx}
                className="flex items-start gap-3 px-3 py-2 rounded-lg"
                style={{ fontFamily: 'var(--nous-font-body)' }}
              >
                <FileText
                  className="w-3.5 h-3.5 mt-0.5 shrink-0"
                  style={{ color: 'var(--nous-sol)' }}
                />
                <div className="flex-1 min-w-0">
                  <p
                    className="text-sm truncate"
                    style={{ color: 'var(--nous-fg-1)' }}
                    title={doc.title}
                  >
                    {doc.title || 'Untitled document'}
                  </p>
                  <p
                    className="text-[11px]"
                    style={{ color: scoreColor(pct) }}
                  >
                    {pct}% match
                  </p>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
```

**Step 4: Run to verify pass**

Run: `cd frontend && npx jest src/components/context-rail/__tests__/RelatedResultsPanel.test.tsx`

Expected: **PASS** both tests.

**Step 5: Commit**

```bash
git add frontend/src/components/context-rail/RelatedResultsPanel.tsx \
        frontend/src/components/context-rail/__tests__/RelatedResultsPanel.test.tsx
git commit -m "feat(chat): add RelatedResultsPanel reading useCitationsForThread"
```

---

## Task 6: `AllCitationsPanel` — thread-wide citation list

**Files:**
- Create: `frontend/src/components/context-rail/AllCitationsPanel.tsx`
- Create: `frontend/src/components/context-rail/__tests__/AllCitationsPanel.test.tsx`

**Step 1: Write the failing test**

Create `frontend/src/components/context-rail/__tests__/AllCitationsPanel.test.tsx`:

```tsx
// @ts-nocheck
/* eslint-disable @typescript-eslint/no-explicit-any */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { AllCitationsPanel } from '../AllCitationsPanel';

jest.mock('@/hooks', () => ({
  useCitationsForThread: jest.fn(),
}));

const { useCitationsForThread } = require('@/hooks');

describe('AllCitationsPanel', () => {
  beforeEach(() => jest.clearAllMocks());

  it('renders empty state when no citations', () => {
    useCitationsForThread.mockReturnValue({
      allCitations: [],
      activeDocument: null,
      relatedResults: [],
    });
    render(<AllCitationsPanel />);
    expect(screen.getByText(/no citations yet/i)).toBeInTheDocument();
  });

  it('renders title and a source label for each citation', () => {
    useCitationsForThread.mockReturnValue({
      allCitations: [
        { documentId: 'd1', title: 'Internal doc', score: 0.9, source: 'upload' },
        { externalReferenceId: 'e1', title: 'External paper', score: 0.6, source: 'arxiv' },
      ],
      activeDocument: null,
      relatedResults: [],
    });
    render(<AllCitationsPanel />);
    expect(screen.getByText('Internal doc')).toBeInTheDocument();
    expect(screen.getByText('External paper')).toBeInTheDocument();
    expect(screen.getByText(/2 sources/i)).toBeInTheDocument();
  });
});
```

**Step 2: Run to confirm failure**

Run: `cd frontend && npx jest src/components/context-rail/__tests__/AllCitationsPanel.test.tsx`

Expected: **FAIL**.

**Step 3: Implement**

Create `frontend/src/components/context-rail/AllCitationsPanel.tsx`:

```tsx
'use client';

import * as React from 'react';
import { BookOpen, FileText } from 'lucide-react';
import { useCitationsForThread } from '@/hooks';

export function AllCitationsPanel() {
  const { allCitations } = useCitationsForThread();

  return (
    <section aria-label="All thread citations">
      <div
        className="flex items-center justify-between mb-2 px-1"
        style={{ fontFamily: 'var(--nous-font-ui)' }}
      >
        <span
          className="text-[10px] uppercase tracking-wider"
          style={{ color: 'var(--nous-fg-3)' }}
        >
          Citations
        </span>
        {allCitations.length > 0 && (
          <span
            className="text-[10px]"
            style={{ color: 'var(--nous-fg-3)' }}
          >
            {allCitations.length} source{allCitations.length === 1 ? '' : 's'}
          </span>
        )}
      </div>

      {allCitations.length === 0 ? (
        <div
          className="rounded-xl border p-4 text-xs"
          style={{
            borderColor: 'var(--nous-border-1)',
            background: 'var(--nous-bg-2)',
            color: 'var(--nous-fg-3)',
            fontFamily: 'var(--nous-font-body)',
          }}
        >
          No citations yet. Citations from every message will collect here.
        </div>
      ) : (
        <ul
          className="rounded-xl border p-2 space-y-1"
          style={{
            borderColor: 'var(--nous-border-1)',
            background: 'var(--nous-bg-2)',
          }}
        >
          {allCitations.map((c, idx) => {
            const external = !c.documentId;
            const Icon = external ? BookOpen : FileText;
            return (
              <li
                key={c.id || c.documentId || c.externalReferenceId || idx}
                className="flex items-start gap-3 px-3 py-2 rounded-lg"
                style={{ fontFamily: 'var(--nous-font-body)' }}
              >
                <Icon
                  className="w-3.5 h-3.5 mt-0.5 shrink-0"
                  style={{
                    color: external
                      ? 'var(--nous-corona)'
                      : 'var(--nous-sol)',
                  }}
                />
                <div className="flex-1 min-w-0">
                  <p
                    className="text-sm truncate"
                    style={{ color: 'var(--nous-fg-1)' }}
                    title={c.title}
                  >
                    {c.title || 'Untitled source'}
                  </p>
                  {c.source && (
                    <p
                      className="text-[11px]"
                      style={{ color: 'var(--nous-fg-3)' }}
                    >
                      {c.source}
                    </p>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
```

**Step 4: Run to verify pass**

Run: `cd frontend && npx jest src/components/context-rail/__tests__/AllCitationsPanel.test.tsx`

Expected: **PASS**.

**Step 5: Commit**

```bash
git add frontend/src/components/context-rail/AllCitationsPanel.tsx \
        frontend/src/components/context-rail/__tests__/AllCitationsPanel.test.tsx
git commit -m "feat(chat): add AllCitationsPanel with thread-wide citation list"
```

---

## Task 7: `ContextRail` container + barrel export

**Files:**
- Create: `frontend/src/components/context-rail/ContextRail.tsx`
- Create: `frontend/src/components/context-rail/index.ts`

No test — this file is a pure composition with no branching logic. Integration is verified by the end-to-end smoke check in Task 10.

**Step 1: Create the container**

Create `frontend/src/components/context-rail/ContextRail.tsx`:

```tsx
'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';
import { AgentActivityPanel } from './AgentActivityPanel';
import { RelatedResultsPanel } from './RelatedResultsPanel';
import { AllCitationsPanel } from './AllCitationsPanel';

interface ContextRailProps {
  threadId: string | null;
  className?: string;
}

export function ContextRail({ threadId, className }: ContextRailProps) {
  return (
    <aside
      className={cn(
        'flex flex-col gap-4 overflow-y-auto px-4 py-4',
        className
      )}
      style={{
        background: 'var(--nous-bg-1)',
        fontFamily: 'var(--nous-font-ui)',
      }}
      aria-label="Chat context rail"
    >
      <AgentActivityPanel threadId={threadId} />
      <RelatedResultsPanel />
      <AllCitationsPanel />
    </aside>
  );
}
```

**Step 2: Barrel file**

Create `frontend/src/components/context-rail/index.ts`:

```ts
export { ContextRail } from './ContextRail';
export { AgentActivityPanel } from './AgentActivityPanel';
export { RelatedResultsPanel } from './RelatedResultsPanel';
export { AllCitationsPanel } from './AllCitationsPanel';
```

**Step 3: Type-check**

Run: `cd frontend && npm run type-check`

Expected: exit 0.

**Step 4: Commit**

```bash
git add frontend/src/components/context-rail/ContextRail.tsx \
        frontend/src/components/context-rail/index.ts
git commit -m "feat(chat): add ContextRail container stacking the three panels"
```

---

## Task 8: Wire agent stream callbacks into the store

**Files:**
- Modify: `frontend/app/(dashboard)/chat/page.tsx` — forward `onToolStart` / `onToolEnd` / `onDone` / `onError` into `agentActivityStore`; call `startRun` before streaming

**This task touches a file with parallel-session WIP.** Use targeted `Edit` calls only, do not stage unrelated modified lines.

**Step 1: Locate the stream call**

Run: `grep -n "streamMessage\|onToolStart\|onToolEnd" frontend/app/\(dashboard\)/chat/page.tsx | head -20`

Expected: hits around `700–710` for the existing callback wiring.

**Step 2: Read the surrounding 30 lines** to see exactly how current callbacks are passed.

Read lines `handleSubmit` → `streamMessage` block; confirm `currentThreadId` (or whatever variable names it uses) is in scope and `input` (the user message) is available.

**Step 3: Write a small derivation helper**

Add to `frontend/src/components/context-rail/index.ts`:

```ts
export function deriveAgentName(subgraph?: string): string {
  switch (subgraph) {
    case 'research': return 'Literature synth';
    case 'writing':  return 'Draft assistant';
    case 'data':     return 'Entity analyst';
    default:         return 'NOUS Agent';
  }
}

export function deriveTask(userMessage: string): string {
  const trimmed = userMessage.trim();
  if (trimmed.length <= 60) return trimmed;
  const head = trimmed.slice(0, 60);
  const lastSpace = head.lastIndexOf(' ');
  return (lastSpace > 30 ? head.slice(0, lastSpace) : head) + '…';
}
```

No test for these tiny string helpers — covered by `AgentActivityPanel` integration if needed.

**Step 4: Patch `chat/page.tsx`** with a minimal additive diff

Add at the top of `handleSubmit` (after `currentThreadId` is determined and before `streamMessage`):

```tsx
import { useAgentActivityStore } from '@/stores/agentActivityStore';
import { deriveAgentName, deriveTask } from '@/components/context-rail';

// …inside component body:
const agentActivity = useAgentActivityStore();

// …inside handleSubmit, right before streamMessage(…):
agentActivity.startRun(
  currentThreadId,
  deriveAgentName(/* subgraph not yet known; fallback */),
  deriveTask(input)
);
```

Add forwards inside the existing callback wiring at `streamMessage(…)`:

```tsx
onToolStart: (tool) => {
  agentActivity.pushToolStart(currentThreadId, tool);
  // …preserve existing onToolStart behavior
},
onToolEnd: (tool, result) => {
  agentActivity.pushToolEnd(currentThreadId, tool, !(result?.isError));
  // …preserve existing behavior
},
onDone: () => {
  agentActivity.finishRun(currentThreadId, 'done');
  // …preserve existing
},
onError: () => {
  agentActivity.finishRun(currentThreadId, 'error');
  // …preserve existing
},
```

> **Important:** do not **replace** the existing handlers — merge by calling both (existing side-effects first, then the store forwards) so nothing else breaks. If the existing code doesn't have `onStart`/`onDone`/`onError`, use the closest equivalent (`onRagContext` / `streamMessage.then/catch`) to call `startRun` and `finishRun`.

**Step 5: Type-check and verify no regressions**

Run: `cd frontend && npm run type-check`

Expected: exit 0.

Run: `cd frontend && npx jest src/components/context-rail src/stores/__tests__/agentActivityStore.test.ts`

Expected: **PASS** — the 3 suites from Tasks 2/3/4/5/6 still green.

**Step 6: Commit — stage only the two intended files**

```bash
git add frontend/app/\(dashboard\)/chat/page.tsx \
        frontend/src/components/context-rail/index.ts
git commit -m "feat(chat): forward agent stream events into agentActivityStore"
```

Run `git status` afterwards; confirm the parallel session's unrelated modified files are **still unstaged**.

---

## Task 9: Mount `<ContextRail>` in `chat/layout.tsx`

**Files:**
- Modify: `frontend/app/(dashboard)/chat/layout.tsx` — single render addition

**Step 1: Locate the children slot**

Run: `grep -n "children" frontend/app/\(dashboard\)/chat/layout.tsx`

Expected: the line where the layout renders `{children}` inside the main content flex container.

**Step 2: Read 10 lines around** to understand the existing container structure (flex, width, etc.).

**Step 3: Add the rail sibling**

Wrap `{children}` in a flex row so the rail sits to its right. Minimal diff:

```tsx
// imports:
import { ContextRail } from '@/components/context-rail';
import { useChatPersistence } from '@/hooks';

// inside component body, near existing hooks:
const { currentThreadId } = useChatPersistence();

// inside the JSX where {children} is rendered:
<div className="flex h-full w-full">
  <div className="flex-1 min-w-0">{children}</div>
  <ContextRail
    threadId={currentThreadId}
    className="hidden xl:flex shrink-0 w-[360px] border-l"
    // border-l uses --nous-border-1 via the component's own style
  />
</div>
```

> **Conflict note:** if the parallel session has already modified the children-rendering section, prefer inserting the `<ContextRail>` as an additional sibling *after* their new wrapper — do not remove anything they added.

**Step 4: Type-check**

Run: `cd frontend && npm run type-check`

Expected: exit 0.

**Step 5: Lint**

Run: `cd frontend && npm run lint`

Expected: no new errors introduced by the rail files (warnings in unrelated files are the parallel session's — ignore).

**Step 6: Commit**

```bash
git add frontend/app/\(dashboard\)/chat/layout.tsx
git commit -m "feat(chat): mount ContextRail in chat layout"
```

---

## Task 10: Full validation + manual smoke

**Step 1: Run the full test suite**

Run: `cd frontend && npm run test -- --testPathPattern='context-rail|agentActivityStore'`

Expected: all 5 test files **PASS**, ≥80% coverage on new files (check with `--coverage`).

**Step 2: Type-check + lint the whole frontend**

Run: `cd frontend && npm run type-check && npm run lint 2>&1 | tail -20`

Expected: type-check passes; lint output shows no new errors from rail files (warnings OK).

**Step 3: Start the dev server**

Run: `cd frontend && npm run dev`

In a second terminal, ensure backend is up (or point the frontend at `dev-app.gen-text.app` via env).

**Step 4: Manual smoke**

- Open `http://localhost:3000/chat` at ≥1280px wide.
- Confirm the right rail is visible; Agent Activity card hidden (no prior run).
- Create a new thread and ask "Search arxiv for Mamba-2 follow-ups" (or any query that triggers an agent tool).
- Watch Agent Activity card appear, show an active dot for the running tool, and tick steps off as tool events arrive.
- Verify Related Results and Citations populate as the stream returns RAG context.
- Refresh — card hidden again (session-only store, by design).
- Click a `[Doc N]` citation chip in a message — per-message `CitationPanel` still opens. Coexistence confirmed.
- Narrow the browser to < 1280px — rail disappears (breakpoint `xl:flex`).

**Step 5: Commit any test-run output or screenshots if captured**

```bash
# nothing to commit — validation only
```

**Step 6: Push + open PR**

Run:

```bash
git push -u origin feat/chat-context-rail
gh pr create --base develop --title "feat(chat): add right-rail with Agent Activity, Related Results, Citations" --body-file docs/plans/2026-04-20-chat-context-rail-design.md
```

---

## Rollback

All changes are additive on a dedicated branch. To revert:

```bash
git checkout develop
git branch -D feat/chat-context-rail
```

No database or backend changes. No deployed state to undo.

## References

- Design doc: `docs/plans/2026-04-20-chat-context-rail-design.md`
- Removed component (reference only): `git show develop:frontend/app/(dashboard)/chat/layout.tsx` (pre-deletion version)
- Design primitive: `frontend/app/components/nous/nous-agent-status-card.tsx`
- Hook: `frontend/src/hooks/useCitationsForThread.ts`
- Stream service: `frontend/src/services/agentChatService.ts` (`streamMessage` callbacks)
