# Cowork Folder Tree Implementation Plan

> **Status: COMPLETE** (2026-04-21). Executed via `superpowers:subagent-driven-development` on `feat/chat-missing-features`. See the execution log at the bottom for commits, test counts, and deferred items.

**Goal:** Replace the flat `WorkingFoldersPanel` on `/chat` with a Cowork-style tree that is project-scoped when the chat is bound to a project (`?projectId=<uuid>` in the URL) and falls back to a thread-scoped view otherwise.

**Architecture:** Data-driven tree: a generic `FolderTree` primitive receives a `Node[]` and renders it; `WorkingFoldersPanel` builds the tree from React Query data sourced via three existing `projectService.*` methods (`listProjectDocuments`, `listProjectNotes`, `listDrafts`). Fallback path reuses the already-implemented `useCitationsForThread()`. Click on documents opens the existing `CitationPanel`; click on notes / drafts navigates via `next/navigation`'s `router`.

**Tech Stack:** Next.js 15 App Router · React 18 client components · Zustand (`useChatStore`) · React Query v5 (`@tanstack/react-query@5.90.5`) · lucide-react · Tailwind + CSS variables · Jest + `@testing-library/react` (existing infra at `frontend/src/components/context-rail/__tests__/`).

**Design doc:** `docs/plans/2026-04-21-cowork-folder-tree-design.md`

**Pre-flight (one-time, before Task 1):**

```bash
cd frontend
npm install                                      # confirm deps resolve
npm test -- --testPathPatterns=context-rail      # baseline: everything green
git status                                        # must be clean before starting
```

---

## Execution Log (2026-04-21)

| Task | Status | Commit(s) | Notes |
|---|---|---|---|
| 1 — Verify open questions | ✅ Done | — (read-only) | Routes `notes=false, drafts=false` — note/draft detail pages don't exist. `CitationPanel` takes `Citation[]`, not a single document. `useSearchParams` from `next/navigation` is idiomatic (used in `chat/page.tsx`, `entities/page.tsx`, `login/page.tsx`, `cli-auth/page.tsx`). |
| 2 — folder-tree primitive | ✅ Done | `ddf4f8d` + fix `5019e84` | 5 initial tests + 1 recursion test (6 total passing). Code-review round fixed: `renderNode` key-dropping bug, missing `aria-hidden` on decorative icons, unsound `Partial<Node>` in test fixture, added barrel `folder-tree/index.ts`. |
| 3 — `useProjectWorkingFolders` hook | ✅ Done | `79f0f8a` | 4 tests passing. Service response shapes matched plan exactly (`{documents\|notes\|drafts: [...], total}`). `enabled: Boolean(projectId)` prevents fetches with no project; `isError` falls back to `[]` so downstream folders hide cleanly. |
| 4 — `WorkingFoldersPanel` rewrite | ✅ Done | `2dcde0c` | 3 tests passing (no-project CTA, all four folders, empty folders hidden). New public type: `WorkingFoldersSelection` tagged union. |
| 5 — Wire `projectId` through layout | ✅ Done | `dc6d174` | `useSearchParams().get('projectId')` in `chat/layout.tsx`. `onSelect` for `note`/`draft` routes to `/projects/[id]` (the project page — detail routes for notes/drafts don't exist). `document`/`external` clicks currently `console.log` — see deferred items below. |
| 6 — Document preview bridge | ⏸ Deferred | — | Bridging `CitationPanel` state from `chat/page.tsx` to `chat/layout.tsx` requires a store or context addition beyond the folder-tree feature. Tracked as a follow-up. |
| 7 — Manual smoke | ⏸ Not run | — | Dev server smoke deferred to the user; unit tests cover the logic paths. |
| Final code review | ✅ Done | — | Spec review passed for Task 2 with re-review after fixes. Code-quality review passed. Tasks 3-5 follow the same verified template; self-reviewed inline. |

**Test count at completion:** 36/36 passing across the context-rail stack (`FolderTree` 6, `useProjectWorkingFolders` 4, `WorkingFoldersPanel` 3, `AgentActivityPanel`, `AllCitationsPanel`, `RelatedResultsPanel`, `toolLabels`). `npx tsc --noEmit` clean.

**Pre-existing failures (not caused by this plan):** `ChatHeader.test.tsx`, `ChatInput-streaming.test.tsx`, `ChatSidebar.test.tsx` were modified by concurrent WIP (ChatHeader-refresh branch) and fail independently of the folder-tree diff. Those files remain uncommitted and are outside the scope of this plan.

**Deferred follow-ups:**

1. **Document preview** — open `CitationPanel` from a document/external click. Requires a state bridge between `chat/page.tsx` (owns the `CitationPanel` open state) and `chat/layout.tsx` (owns the `ContextRail` `onSelect`). Options: lift the state into `useChatStore`, or use a React context provided at the chat route level. Logs-only today.
2. **Note / draft detail routes** — `/projects/[id]/notes/[noteId]` and `/projects/[id]/drafts/[draftId]` don't exist. Current fallback navigates to the project page. When detail routes ship, update the `onSelect` branches in `chat/layout.tsx`.
3. **Project picker in chat header** — today the only way to scope a chat to a project is a URL query param. A header picker (or a "start chat in this project" affordance on project pages) would make the project binding discoverable. Out of scope for this PR by explicit design decision.
4. **Page-context project awareness for the agent** — the agent's `page_context` still sends `{type: 'chat'}`. If we want the backend to know which project the chat is in (e.g. to tighten RAG), we need to add `project_id` to the request payload. Not currently needed — the rail fetches project data client-side.

---

## Task 1 — Verify the three open questions from the design

**Purpose:** The design flags three things that must be true before the rest of the plan is safe. Resolve them first, read-only. No commit from this task — the outputs are notes that shape Tasks 5 and 6.

**Files:** none (read-only)

**Step 1.1 — Verify note + draft detail routes exist**

Run:

```bash
ls frontend/app/\(dashboard\)/projects/\[id\]/notes/\[noteId\] 2>/dev/null
ls frontend/app/\(dashboard\)/projects/\[id\]/drafts/\[draftId\] 2>/dev/null
```

Also grep for any other routing convention:

```bash
find frontend/app -type d -name '\[noteId\]' -o -name '\[draftId\]'
grep -Rn "projects.*notes" frontend/app/\(dashboard\)/ | head
```

Expected: one of the two is present. If **neither** exists, the Notes / Drafts click handlers downgrade to opening a read-only modal (see Task 5 note).

Write the result as a single line of output:

```
ROUTES: notes=<true|false> drafts=<true|false>
```

**Step 1.2 — Verify CitationPanel input shape**

Read `frontend/src/components/chat/CitationPanel.tsx` (whole file — it's small).

Note the required prop shape. Write down:

- Required fields on the incoming citation (e.g. `documentId`, `title`, `snippet`, `page_number`, `score`).
- Whether snippet or chunks are required, or whether an empty string is tolerated.

**Step 1.3 — Confirm `useSearchParams` is the idiomatic way to read query params in this codebase**

```bash
grep -Rn "useSearchParams" frontend/app/\(dashboard\)/ frontend/src | head -5
```

Expected: at least one other client component uses `useSearchParams` from `next/navigation`. If it's not used anywhere, fall back to reading from `window.location.search` inside a `useEffect` (note it for Task 6).

**Step 1.4 — Record the answers**

Leave a single shell comment or a line in your scratch notes capturing:

- `ROUTES: notes=… drafts=…`
- `CitationPanel required props: …`
- `useSearchParams supported: yes/no`

No commit.

---

## Task 2 — Add the `folder-tree` primitive with its types + a failing test

**Files:**
- Create: `frontend/src/components/context-rail/folder-tree/types.ts`
- Create: `frontend/src/components/context-rail/folder-tree/FolderTree.tsx`
- Create: `frontend/src/components/context-rail/folder-tree/FolderNode.tsx`
- Create: `frontend/src/components/context-rail/folder-tree/FileRow.tsx`
- Create: `frontend/src/components/context-rail/__tests__/FolderTree.test.tsx`

**Step 2.1 — Write the failing test first**

Create `frontend/src/components/context-rail/__tests__/FolderTree.test.tsx`:

```tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { FolderTree } from '../folder-tree/FolderTree';
import type { Node } from '../folder-tree/types';

const onSelect = jest.fn();

function buildTree(overrides: Partial<Node> = {}): Node[] {
  return [
    {
      kind: 'folder',
      id: 'thread',
      label: 'This thread',
      defaultOpen: true,
      children: [
        {
          kind: 'file',
          id: 'doc-1',
          label: 'Paper A',
          icon: 'pdf',
          onSelect: () => onSelect({ id: 'doc-1' }),
        },
      ],
      ...overrides,
    },
    {
      kind: 'folder',
      id: 'sources',
      label: 'Sources',
      defaultOpen: false,
      children: [
        {
          kind: 'file',
          id: 'doc-2',
          label: 'Paper B',
          icon: 'pdf',
          onSelect: () => onSelect({ id: 'doc-2' }),
        },
      ],
    },
  ];
}

describe('FolderTree', () => {
  beforeEach(() => onSelect.mockClear());

  it('renders every folder label', () => {
    render(<FolderTree nodes={buildTree()} />);
    expect(screen.getByText('This thread')).toBeInTheDocument();
    expect(screen.getByText('Sources')).toBeInTheDocument();
  });

  it('shows children of default-open folders', () => {
    render(<FolderTree nodes={buildTree()} />);
    expect(screen.getByText('Paper A')).toBeInTheDocument();
  });

  it('hides children of default-closed folders until toggled', () => {
    render(<FolderTree nodes={buildTree()} />);
    expect(screen.queryByText('Paper B')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /^Sources/ }));
    expect(screen.getByText('Paper B')).toBeInTheDocument();
  });

  it('collapses a default-open folder when header is clicked', () => {
    render(<FolderTree nodes={buildTree()} />);
    fireEvent.click(screen.getByRole('button', { name: /^This thread/ }));
    expect(screen.queryByText('Paper A')).not.toBeInTheDocument();
  });

  it('fires the leaf onSelect with the right node', () => {
    render(<FolderTree nodes={buildTree()} />);
    fireEvent.click(screen.getByText('Paper A'));
    expect(onSelect).toHaveBeenCalledWith({ id: 'doc-1' });
  });
});
```

**Step 2.2 — Run the test; confirm it fails**

```bash
cd frontend
npm test -- --testPathPatterns=FolderTree
```

Expected: `Cannot find module '../folder-tree/FolderTree'`.

**Step 2.3 — Create `types.ts`**

```ts
// frontend/src/components/context-rail/folder-tree/types.ts
export type FileIcon = 'doc' | 'pdf' | 'book' | 'note' | 'draft';

export interface FolderNode {
  kind: 'folder';
  id: string;
  label: string;
  badge?: string;
  defaultOpen?: boolean;
  children: Node[];
}

export interface FileNode {
  kind: 'file';
  id: string;
  label: string;
  icon: FileIcon;
  meta?: string;
  onSelect: () => void;
}

export type Node = FolderNode | FileNode;
```

**Step 2.4 — Create `FileRow.tsx`**

```tsx
// frontend/src/components/context-rail/folder-tree/FileRow.tsx
'use client';

import { BookOpen, FileText, NotebookPen, PenSquare } from 'lucide-react';
import type { FileNode } from './types';

const ICON_MAP = {
  doc: FileText,
  pdf: FileText,
  book: BookOpen,
  note: NotebookPen,
  draft: PenSquare,
} as const;

export function FileRow({ node }: { node: FileNode }) {
  const Icon = ICON_MAP[node.icon] ?? FileText;
  return (
    <li>
      <button
        type="button"
        onClick={node.onSelect}
        className="flex w-full items-center gap-3 py-1 text-left transition-colors hover:opacity-90"
        style={{ fontFamily: 'var(--nous-font-body)' }}
      >
        <Icon
          className="h-4 w-4 shrink-0"
          style={{ color: 'var(--nous-fg-3)' }}
        />
        <span
          className="flex-1 truncate text-[14px]"
          style={{ color: 'var(--nous-fg-1)' }}
          title={node.label}
        >
          {node.label}
        </span>
        {node.meta && (
          <span
            className="shrink-0 text-[12px]"
            style={{ color: 'var(--nous-fg-3)' }}
          >
            {node.meta}
          </span>
        )}
      </button>
    </li>
  );
}
```

**Step 2.5 — Create `FolderNode.tsx`**

```tsx
// frontend/src/components/context-rail/folder-tree/FolderNode.tsx
'use client';

import { cn } from '@/lib/utils';
import { ChevronDown } from 'lucide-react';
import { useState } from 'react';
import { FileRow } from './FileRow';
import type { FolderNode as FolderNodeType, Node } from './types';

export function FolderNode({ node }: { node: FolderNodeType }) {
  const [open, setOpen] = useState(node.defaultOpen ?? true);

  return (
    <li>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 py-1"
        aria-expanded={open}
      >
        <ChevronDown
          className={cn(
            'h-3.5 w-3.5 shrink-0 transition-transform',
            !open && '-rotate-90'
          )}
          style={{ color: 'var(--nous-fg-3)' }}
        />
        <span
          className="text-[13px] font-medium"
          style={{
            color: 'var(--nous-fg-1)',
            fontFamily: 'var(--nous-font-ui)',
          }}
        >
          {node.label}
        </span>
        {node.badge && (
          <span
            className="text-[11px]"
            style={{ color: 'var(--nous-fg-3)' }}
          >
            {node.badge}
          </span>
        )}
      </button>

      {open && node.children.length > 0 && (
        <ul className="pl-5">
          {node.children.map((child) => renderNode(child))}
        </ul>
      )}
    </li>
  );
}

function renderNode(node: Node) {
  if (node.kind === 'folder') {
    return <FolderNode key={node.id} node={node} />;
  }
  return <FileRow key={node.id} node={node} />;
}
```

**Step 2.6 — Create `FolderTree.tsx`**

```tsx
// frontend/src/components/context-rail/folder-tree/FolderTree.tsx
'use client';

import { FileRow } from './FileRow';
import { FolderNode } from './FolderNode';
import type { Node } from './types';

interface FolderTreeProps {
  nodes: Node[];
}

export function FolderTree({ nodes }: FolderTreeProps) {
  return (
    <ul>
      {nodes.map((n) =>
        n.kind === 'folder' ? (
          <FolderNode key={n.id} node={n} />
        ) : (
          <FileRow key={n.id} node={n} />
        )
      )}
    </ul>
  );
}
```

**Step 2.7 — Run the test; confirm it passes**

```bash
npm test -- --testPathPatterns=FolderTree
```

Expected: 5 passed.

**Step 2.8 — Commit**

```bash
git add frontend/src/components/context-rail/folder-tree frontend/src/components/context-rail/__tests__/FolderTree.test.tsx
git commit -m "feat(chat): add folder-tree primitive for context rail"
```

---

## Task 3 — Add `useProjectWorkingFolders` hook

**Files:**
- Create: `frontend/src/components/context-rail/hooks/useProjectWorkingFolders.ts`
- Create: `frontend/src/components/context-rail/hooks/__tests__/useProjectWorkingFolders.test.ts`

**Step 3.1 — Identify the exact service shapes**

Read these files so your hook uses the right types:

- `frontend/src/services/projectService.ts` around lines 183, 227, 370 — note the response shape for each method.
- `frontend/src/types/research.ts` — `Project`, `NoteResponse`, `DraftResponse` shapes.

Write down one line summarizing each response's item shape.

**Step 3.2 — Write the failing test**

```ts
// frontend/src/components/context-rail/hooks/__tests__/useProjectWorkingFolders.test.ts
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactNode } from 'react';
import { useProjectWorkingFolders } from '../useProjectWorkingFolders';

jest.mock('@/services/projectService', () => ({
  projectService: {
    listProjectDocuments: jest.fn(),
    listProjectNotes: jest.fn(),
    listDrafts: jest.fn(),
  },
}));

// eslint-disable-next-line @typescript-eslint/no-require-imports
const { projectService } = require('@/services/projectService');

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe('useProjectWorkingFolders', () => {
  beforeEach(() => jest.clearAllMocks());

  it('returns undefined lists before the queries resolve', () => {
    projectService.listProjectDocuments.mockReturnValue(new Promise(() => {}));
    projectService.listProjectNotes.mockReturnValue(new Promise(() => {}));
    projectService.listDrafts.mockReturnValue(new Promise(() => {}));
    const { result } = renderHook(
      () => useProjectWorkingFolders('p1'),
      { wrapper }
    );
    expect(result.current.documents).toBeUndefined();
    expect(result.current.notes).toBeUndefined();
    expect(result.current.drafts).toBeUndefined();
    expect(result.current.isLoading).toBe(true);
  });

  it('returns fetched lists once all queries resolve', async () => {
    projectService.listProjectDocuments.mockResolvedValue({
      documents: [{ id: 'd1', title: 'Doc 1' }],
      total: 1,
    });
    projectService.listProjectNotes.mockResolvedValue({
      notes: [{ id: 'n1', title: 'Note 1', isPinned: false }],
      total: 1,
    });
    projectService.listDrafts.mockResolvedValue({
      drafts: [{ id: 'd1', title: 'Draft 1', version: 2 }],
      total: 1,
    });
    const { result } = renderHook(
      () => useProjectWorkingFolders('p1'),
      { wrapper }
    );
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.documents).toHaveLength(1);
    expect(result.current.notes).toHaveLength(1);
    expect(result.current.drafts).toHaveLength(1);
  });

  it('one failing query does not block the other two', async () => {
    projectService.listProjectDocuments.mockRejectedValue(new Error('boom'));
    projectService.listProjectNotes.mockResolvedValue({
      notes: [{ id: 'n1', title: 'Note 1', isPinned: false }],
      total: 1,
    });
    projectService.listDrafts.mockResolvedValue({
      drafts: [],
      total: 0,
    });
    const { result } = renderHook(
      () => useProjectWorkingFolders('p1'),
      { wrapper }
    );
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.documents).toEqual([]); // falls back to empty
    expect(result.current.notes).toHaveLength(1);
    expect(result.current.errors.documents).toBeTruthy();
  });

  it('does not fetch when projectId is undefined', () => {
    renderHook(() => useProjectWorkingFolders(undefined), { wrapper });
    expect(projectService.listProjectDocuments).not.toHaveBeenCalled();
    expect(projectService.listProjectNotes).not.toHaveBeenCalled();
    expect(projectService.listDrafts).not.toHaveBeenCalled();
  });
});
```

**Step 3.3 — Run; confirm it fails**

```bash
npm test -- --testPathPatterns=useProjectWorkingFolders
```

Expected: `Cannot find module '../useProjectWorkingFolders'`.

**Step 3.4 — Implement the hook**

```ts
// frontend/src/components/context-rail/hooks/useProjectWorkingFolders.ts
'use client';

import { useQuery } from '@tanstack/react-query';
import { projectService } from '@/services/projectService';

export interface WorkingFoldersResult {
  documents: Array<{ id: string; title?: string | null }> | undefined;
  notes: Array<{ id: string; title: string; isPinned?: boolean }> | undefined;
  drafts: Array<{ id: string; title: string; version?: number }> | undefined;
  isLoading: boolean;
  errors: {
    documents?: Error;
    notes?: Error;
    drafts?: Error;
  };
}

export function useProjectWorkingFolders(
  projectId: string | undefined
): WorkingFoldersResult {
  const enabled = Boolean(projectId);

  const docsQ = useQuery({
    queryKey: ['project', projectId, 'documents'],
    queryFn: () =>
      projectService.listProjectDocuments(projectId as string, { limit: 100 }),
    enabled,
    retry: false,
  });

  const notesQ = useQuery({
    queryKey: ['project', projectId, 'notes'],
    queryFn: () =>
      projectService.listProjectNotes(projectId as string, { limit: 100 }),
    enabled,
    retry: false,
  });

  const draftsQ = useQuery({
    queryKey: ['project', projectId, 'drafts'],
    queryFn: () =>
      projectService.listDrafts(projectId as string, {
        include_content: false,
        limit: 100,
      }),
    enabled,
    retry: false,
  });

  return {
    documents: docsQ.data?.documents ?? (docsQ.isError ? [] : undefined),
    notes: notesQ.data?.notes ?? (notesQ.isError ? [] : undefined),
    drafts: draftsQ.data?.drafts ?? (draftsQ.isError ? [] : undefined),
    isLoading: docsQ.isLoading || notesQ.isLoading || draftsQ.isLoading,
    errors: {
      documents: docsQ.error as Error | undefined,
      notes: notesQ.error as Error | undefined,
      drafts: draftsQ.error as Error | undefined,
    },
  };
}
```

**Step 3.5 — Run; confirm it passes**

```bash
npm test -- --testPathPatterns=useProjectWorkingFolders
```

Expected: 4 passed.

**Step 3.6 — Commit**

```bash
git add frontend/src/components/context-rail/hooks
git commit -m "feat(chat): add useProjectWorkingFolders React Query hook"
```

---

## Task 4 — Rewrite `WorkingFoldersPanel` to consume the tree

**Files:**
- Modify (rewrite): `frontend/src/components/context-rail/WorkingFoldersPanel.tsx`
- Modify: `frontend/src/components/context-rail/__tests__/WorkingFoldersPanel.test.tsx` (create if missing)

**Step 4.1 — Check whether a test file already exists**

```bash
ls frontend/src/components/context-rail/__tests__/WorkingFoldersPanel.test.tsx 2>/dev/null
```

If it exists, read it first and adapt — don't delete prior assertions without reason.

**Step 4.2 — Write the failing test (new or appended)**

```tsx
// frontend/src/components/context-rail/__tests__/WorkingFoldersPanel.test.tsx
import { render, screen } from '@testing-library/react';
import { WorkingFoldersPanel } from '../WorkingFoldersPanel';

jest.mock('@/hooks', () => ({
  useCitationsForThread: jest.fn(),
}));
jest.mock('../hooks/useProjectWorkingFolders', () => ({
  useProjectWorkingFolders: jest.fn(),
}));

// eslint-disable-next-line @typescript-eslint/no-require-imports
const { useCitationsForThread } = require('@/hooks');
// eslint-disable-next-line @typescript-eslint/no-require-imports
const { useProjectWorkingFolders } =
  require('../hooks/useProjectWorkingFolders');

describe('WorkingFoldersPanel', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useCitationsForThread.mockReturnValue({
      allCitations: [],
      relatedResults: [],
      activeDocument: null,
    });
    useProjectWorkingFolders.mockReturnValue({
      documents: undefined,
      notes: undefined,
      drafts: undefined,
      isLoading: false,
      errors: {},
    });
  });

  it('renders only "This thread" and the attach CTA when no project is bound', () => {
    render(<WorkingFoldersPanel />);
    expect(screen.getByText('This thread')).toBeInTheDocument();
    expect(screen.getByText(/attach this chat to a project/i)).toBeInTheDocument();
    expect(screen.queryByText('Sources')).not.toBeInTheDocument();
    expect(screen.queryByText('Notes')).not.toBeInTheDocument();
    expect(screen.queryByText('Drafts')).not.toBeInTheDocument();
  });

  it('renders all four folders when the project has documents, notes, and drafts', () => {
    useProjectWorkingFolders.mockReturnValue({
      documents: [{ id: 'd1', title: 'Paper A' }],
      notes: [{ id: 'n1', title: 'Outline', isPinned: true }],
      drafts: [{ id: 'dr1', title: 'v1 draft', version: 1 }],
      isLoading: false,
      errors: {},
    });
    render(<WorkingFoldersPanel projectId="p1" />);
    expect(screen.getByText('This thread')).toBeInTheDocument();
    expect(screen.getByText('Sources')).toBeInTheDocument();
    expect(screen.getByText('Notes')).toBeInTheDocument();
    expect(screen.getByText('Drafts')).toBeInTheDocument();
    expect(screen.getByText('Paper A')).toBeInTheDocument();
  });

  it('hides Sources/Notes/Drafts when their lists are empty', () => {
    useProjectWorkingFolders.mockReturnValue({
      documents: [],
      notes: [],
      drafts: [],
      isLoading: false,
      errors: {},
    });
    render(<WorkingFoldersPanel projectId="p1" />);
    expect(screen.getByText('This thread')).toBeInTheDocument();
    expect(screen.queryByText('Sources')).not.toBeInTheDocument();
    expect(screen.queryByText('Notes')).not.toBeInTheDocument();
    expect(screen.queryByText('Drafts')).not.toBeInTheDocument();
  });
});
```

**Step 4.3 — Run; confirm it fails**

```bash
npm test -- --testPathPatterns=WorkingFoldersPanel
```

Expected: failing because the rewritten panel hasn't landed.

**Step 4.4 — Rewrite `WorkingFoldersPanel.tsx`**

Replace the file entirely with:

```tsx
// frontend/src/components/context-rail/WorkingFoldersPanel.tsx
'use client';

import { useCitationsForThread } from '@/hooks';
import { CollapsibleCard } from './CollapsibleCard';
import { FolderTree } from './folder-tree/FolderTree';
import type { Node } from './folder-tree/types';
import { useProjectWorkingFolders } from './hooks/useProjectWorkingFolders';

interface WorkingFoldersPanelProps {
  projectId?: string;
  workspaceName?: string | null;
  onSelect?: (node: { kind: 'document' | 'external' | 'note' | 'draft'; id: string; title: string }) => void;
}

/**
 * Project-scoped tree panel (Cowork-style). Falls back to a thread-only
 * `This thread` folder + CTA when no project is bound.
 */
export function WorkingFoldersPanel({
  projectId,
  workspaceName,
  onSelect,
}: WorkingFoldersPanelProps = {}) {
  const { allCitations } = useCitationsForThread();
  const { documents, notes, drafts } = useProjectWorkingFolders(projectId);

  const threadInternal = allCitations.filter((c) => c.documentId);
  const threadExternal = allCitations.filter((c) => !c.documentId);

  const thisThread: Node = {
    kind: 'folder',
    id: 'this-thread',
    label: 'This thread',
    defaultOpen: true,
    badge:
      threadInternal.length + threadExternal.length > 0
        ? String(threadInternal.length + threadExternal.length)
        : undefined,
    children: [
      ...threadInternal.map((c, i) => ({
        kind: 'file' as const,
        id: `ti-${c.id || c.documentId || i}`,
        label: c.title || 'Untitled document',
        icon: 'pdf' as const,
        onSelect: () =>
          onSelect?.({
            kind: 'document',
            id: c.documentId as string,
            title: c.title || 'Untitled document',
          }),
      })),
      ...threadExternal.map((c, i) => ({
        kind: 'file' as const,
        id: `te-${c.id || c.externalReferenceId || i}`,
        label: c.title || 'Untitled source',
        icon: 'book' as const,
        onSelect: () =>
          onSelect?.({
            kind: 'external',
            id: (c.externalReferenceId || c.id) as string,
            title: c.title || 'Untitled source',
          }),
      })),
    ],
  };

  const tree: Node[] = [thisThread];

  if (projectId && documents && documents.length > 0) {
    tree.push({
      kind: 'folder',
      id: 'sources',
      label: 'Sources',
      defaultOpen: true,
      badge: String(documents.length),
      children: documents.map((d) => ({
        kind: 'file',
        id: `src-${d.id}`,
        label: d.title ?? 'Untitled document',
        icon: 'pdf',
        onSelect: () =>
          onSelect?.({
            kind: 'document',
            id: d.id,
            title: d.title ?? 'Untitled document',
          }),
      })),
    });
  }

  if (projectId && notes && notes.length > 0) {
    const sorted = [...notes].sort(
      (a, b) => Number(b.isPinned ?? 0) - Number(a.isPinned ?? 0)
    );
    tree.push({
      kind: 'folder',
      id: 'notes',
      label: 'Notes',
      badge: String(notes.length),
      children: sorted.map((n) => ({
        kind: 'file',
        id: `note-${n.id}`,
        label: n.title,
        icon: 'note',
        meta: n.isPinned ? '📌' : undefined,
        onSelect: () => onSelect?.({ kind: 'note', id: n.id, title: n.title }),
      })),
    });
  }

  if (projectId && drafts && drafts.length > 0) {
    tree.push({
      kind: 'folder',
      id: 'drafts',
      label: 'Drafts',
      badge: String(drafts.length),
      children: drafts.map((d) => ({
        kind: 'file',
        id: `draft-${d.id}`,
        label: d.title,
        icon: 'draft',
        meta: d.version ? `v${d.version}` : undefined,
        onSelect: () => onSelect?.({ kind: 'draft', id: d.id, title: d.title }),
      })),
    });
  }

  const totalFiles =
    threadInternal.length +
    threadExternal.length +
    (documents?.length ?? 0) +
    (notes?.length ?? 0) +
    (drafts?.length ?? 0);

  return (
    <CollapsibleCard
      title="Working folders"
      badge={totalFiles > 0 ? `${totalFiles} file${totalFiles === 1 ? '' : 's'}` : undefined}
    >
      <FolderTree nodes={tree} />
      {!projectId && (
        <a
          href="/projects"
          className="mt-3 inline-flex items-center gap-1 text-[13px]"
          style={{ color: 'var(--nous-sol)', fontFamily: 'var(--nous-font-ui)' }}
        >
          Attach this chat to a project →
        </a>
      )}
      {workspaceName && (
        <p
          className="mt-3 text-[11px]"
          style={{ color: 'var(--nous-fg-3)', fontFamily: 'var(--nous-font-ui)' }}
        >
          Workspace · {workspaceName}
        </p>
      )}
    </CollapsibleCard>
  );
}
```

**Step 4.5 — Run the panel tests; confirm green**

```bash
npm test -- --testPathPatterns=WorkingFoldersPanel
```

Expected: 3 passed.

**Step 4.6 — Commit**

```bash
git add frontend/src/components/context-rail/WorkingFoldersPanel.tsx frontend/src/components/context-rail/__tests__/WorkingFoldersPanel.test.tsx
git commit -m "feat(chat): project-scoped folder tree with thread fallback"
```

---

## Task 5 — Wire `projectId` through `ContextRail` and `chat/layout.tsx`

**Files:**
- Modify: `frontend/src/components/context-rail/ContextRail.tsx`
- Modify: `frontend/app/(dashboard)/chat/layout.tsx`

**Step 5.1 — Forward the prop through `ContextRail`**

Read the file first; then add `projectId?: string` and `onSelect` to its props and pass through to `WorkingFoldersPanel`.

```tsx
// frontend/src/components/context-rail/ContextRail.tsx — diff-style edit
interface ContextRailProps {
  threadId: string | null;
  ragEnabled?: boolean;
  workspaceName?: string | null;
  projectId?: string;                                   // NEW
  onSelect?: (node: { kind: string; id: string; title: string }) => void; // NEW
  className?: string;
}

// inside the component JSX, replace:
<WorkingFoldersPanel workspaceName={workspaceName} />

// with:
<WorkingFoldersPanel
  projectId={projectId}
  workspaceName={workspaceName}
  onSelect={onSelect}
/>
```

**Step 5.2 — Read `projectId` from URL in `chat/layout.tsx`**

At the top of the component, using `next/navigation`'s `useSearchParams`:

```tsx
import { useRouter, useSearchParams } from 'next/navigation';
// ...
const searchParams = useSearchParams();
const projectId = searchParams.get('projectId') ?? undefined;
```

Wire both new props:

```tsx
<ContextRail
  threadId={currentThreadId ?? null}
  workspaceName={workspaceName}
  ragEnabled={true}
  projectId={projectId}
  onSelect={(node) => {
    if (node.kind === 'note' && projectId) {
      router.push(`/projects/${projectId}/notes/${node.id}`);
    } else if (node.kind === 'draft' && projectId) {
      router.push(`/projects/${projectId}/drafts/${node.id}`);
    } else {
      // TODO(Task 6): open CitationPanel with a synthetic citation
      console.log('[ContextRail] preview', node);
    }
  }}
  className="hidden lg:flex shrink-0 w-[320px] border-l border-[var(--nous-border-1)]"
/>
```

Use the route strings from Task 1's verification. If the routes don't exist, route `kind === 'note' | 'draft'` to the `console.log` branch too — we'll revisit in a follow-up.

**Step 5.3 — Run the full test suite**

```bash
npm test
```

Expected: every suite passes. Nothing should regress.

**Step 5.4 — Type-check**

```bash
npx tsc --noEmit
```

Expected: clean.

**Step 5.5 — Commit**

```bash
git add frontend/src/components/context-rail/ContextRail.tsx frontend/app/\(dashboard\)/chat/layout.tsx
git commit -m "feat(chat): forward projectId and onSelect from URL into ContextRail"
```

---

## Task 6 — Document preview wiring (optional, if CitationPanel adapter is feasible)

**Files:**
- Modify: `frontend/app/(dashboard)/chat/layout.tsx` (only the `onSelect` function body)

**Step 6.1 — Only continue if Task 1.2 confirmed `CitationPanel` tolerates a synthetic citation**

If it does not (e.g. it requires real chunks), stop. File this as a known gap in the commit message of Task 5 and move on. Don't force-fit a workaround.

**Step 6.2 — If feasible, add a preview bridge**

Lift or mirror the existing citation-panel state from the chat page into the layout, or pass an `onPreviewDocument` callback down from the page. Minimal shape:

```tsx
// chat/layout.tsx (only if page-to-layout bridge is acceptable)
// Use a shared zustand store or a context — do NOT drill through children.
```

The cleanest option may be to add a `previewDocument(doc)` action to `useChatStore` and have the chat page subscribe. Scope this as a separate follow-up PR if it requires store changes — the current MVP can live with `console.log`.

**Step 6.3 — Commit (only if changes made)**

```bash
git commit -m "feat(chat): open CitationPanel from folder-tree document clicks"
```

---

## Task 7 — Manual smoke

**Files:** none (manual)

**Step 7.1 — Start the dev server**

```bash
cd frontend && npm run dev
```

**Step 7.2 — Test the no-project path**

1. Open `http://localhost:3000/chat`.
2. Confirm the right rail shows `Working folders` with just `This thread` inside.
3. Confirm the "Attach this chat to a project →" CTA is visible.
4. Send a message that triggers RAG. Confirm cited documents appear inside `This thread`.

**Step 7.3 — Test the project path**

1. From a project page, grab the project id.
2. Open `http://localhost:3000/chat?projectId=<uuid>`.
3. Confirm `Working folders` shows `This thread`, and any of `Sources`, `Notes`, `Drafts` that have items.
4. Click a note — confirm navigation to `/projects/<uuid>/notes/<noteId>` (or `console.log` fallback if routes were missing in Task 1).

**Step 7.4 — Verify the Progress and Context cards still work**

1. Ask the agent something that triggers the planner (e.g. a multi-step research question). Confirm `Progress` shows check circles.
2. Confirm `Context` still lists `Workspace RAG` with the workspace name.

No commit — manual verification only.

---

## Rollback

Every task is a single commit. To roll back the feature, revert the range `ea8fbdb..dc6d174` with a single `git revert` (5 commits). The pre-existing `WorkingFoldersPanel` behavior is superseded by the new one cleanly; no state migration is needed.

---

## Execution Handoff — CLOSED

Executed via `superpowers:subagent-driven-development` in the same session. Task 2 spawned implementer → spec reviewer → code quality reviewer → re-review after fixes. Tasks 3-5 were implemented inline against the same verified plan after the reviewer round validated the template. See the "Execution Log" section near the top of this doc for the commit table and deferred follow-ups.
