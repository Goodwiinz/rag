# Cowork-style Working-Folders Tree — Design

**Date:** 2026-04-21
**Branch:** `feat/chat-missing-features`
**Status:** Approved — ready for implementation planning.

## 1. Problem

The right rail on `/chat` (`frontend/app/(dashboard)/chat/layout.tsx`) shows a flat `Working folders` panel that's a single two-group list of citations. Users wanted the Cowork shape: a tree of named folders that each independently expand and collapse, with a clear "working context" at the top. NOUS has no OS-style folders; the closest real data hierarchy in the system is a Project and its linked documents, notes, and drafts. We'll expose that as the tree.

## 2. Goals / non-goals

**In scope**
- Replace `WorkingFoldersPanel` with a tree keyed on whether the current chat is project-bound.
- Four top-level folder slots: `This thread`, `Sources`, `Notes`, `Drafts`.
- `This thread` is always rendered. `Sources` / `Notes` / `Drafts` are rendered only when the project has items in them.
- Mixed click behavior: documents open the existing `CitationPanel`; notes and drafts navigate to their route.
- React Query for the three list fetches.
- Graceful fallback when the chat is not in a project (only `This thread` + a "Attach to a project" CTA).

**Out of scope (explicit)**
- Creating / renaming / deleting folders. NOUS has no Folder object; we're presenting a view over existing data.
- Multi-select, drag-to-reorder, per-item right-click menus.
- Live refresh mid-chat when a note or draft is created elsewhere. A page re-render is enough.
- Persisting expand/collapse state across sessions.
- A project picker in the chat header. If the page has no `projectId` in its URL, it simply falls back.
- Modifying `page_context` sent to the agent backend. The rail reads project data from the workspace API; the agent does not need to know.

## 3. Verified facts (ground truth before designing)

- `projectService.listProjectDocuments(projectId, {skip, limit})` → `GET /projects/{id}/documents`. `frontend/src/services/projectService.ts:183`, backend `backend/src/api/research/projects.py:298`. Documents are joined via a `project_documents` table.
- `projectService.listProjectNotes(projectId, {skip, limit, pinned_only})` → `GET /projects/{id}/notes`. `projectService.ts:227`.
- `projectService.listDrafts(projectId, {include_content, skip, limit})` → `GET /projects/{id}/drafts`. `projectService.ts:370`. Drafts include content by default; we pass `include_content: false`.
- `projectService.getProject(id)` returns metadata + counters only (`document_count`, `note_count`, `draft_count`). No aggregated lists.
- Frontend uses React Query v5 (`@tanstack/react-query@5.90.5`). New fetches use `useQuery`.
- The chat page sends `page_context: {type: 'chat'}`. It has no project awareness today. `usePageContext()` only builds project context on `/projects/:id/*` routes.
- Existing `CitationPanel` takes a `Citation`, not a `Document`. A thin adapter will convert.

## 4. User-driven decisions (resolved via multiple-choice)

| Decision | Choice |
|---|---|
| What are "folders"? | Project-scoped |
| Always in a project? | Sometimes — fallback to thread-scoped when not |
| Top-level shape | Three fixed + one conditional (hide empty `Sources` / `Notes` / `Drafts`; `This thread` always on) |
| Click behavior | Mixed — sources → preview panel, notes / drafts → navigate |

## 5. Components

```
src/components/context-rail/
  WorkingFoldersPanel.tsx        rewritten — routes project-bound vs fallback
  folder-tree/
    FolderTree.tsx               root <ul>, owns expand/collapse map
    FolderNode.tsx               one folder row, recursive for children
    FileRow.tsx                  leaf row — icon, title, click handler
    types.ts                     Node = Folder | File discriminated union
  hooks/
    useProjectWorkingFolders.ts  composes three useQuery calls
```

- The tree UI is data-driven: `WorkingFoldersPanel` builds `Node[]` and hands it to `FolderTree`. `FolderTree` does not know about projects, documents, notes, or drafts.
- `useProjectWorkingFolders(projectId)` returns `{documents, notes, drafts, isLoading, errors}`. Each fetch is independent; one failing does not block the others.

### Node shape

```ts
type Node = FolderNode | FileNode;

interface FolderNode {
  kind: 'folder';
  id: string;                 // stable expand/collapse key
  label: string;              // "This thread" | "Sources" | …
  badge?: string;             // "3 files" | "42" — optional
  defaultOpen?: boolean;
  children: Node[];
}

interface FileNode {
  kind: 'file';
  id: string;
  label: string;
  icon: 'doc' | 'pdf' | 'book' | 'note' | 'draft';
  meta?: string;              // e.g. "v2", "pinned", "82% match"
  onSelect: () => void;       // parent wires this
}
```

## 6. Tree shape

**Project-bound:**
```
Working folders                                         [badge: total file count]
├─ This thread              (always, even if empty — matches Cowork's empty Documents)
│    ├─ <docs cited in messages with a documentId>
│    └─ <external sources cited (arXiv, web)>
├─ Sources                  (rendered only if documents.length > 0)
│    └─ <project-linked documents>
├─ Notes                    (rendered only if notes.length > 0)
│    └─ <note titles — pinned notes first, a pin glyph on the row>
└─ Drafts                   (rendered only if drafts.length > 0)
     └─ <draft titles with "v{version}" in the meta>
```

**No-project fallback:**
```
Working folders
├─ This thread              (current citations + attachments)
└─ [CTA] Attach this chat to a project →
```

- Dedupe: a document cited in messages AND present in `Sources` is shown only under `Sources`, with a small "↗ in thread" glyph on the row. `This thread` is reserved for items that don't appear elsewhere in the tree.
- Default expansions: `This thread` open; `Sources` open; `Notes` and `Drafts` collapsed. Same defaults on every render; no persistence.

## 7. Data flow

1. `WorkingFoldersPanel` reads `projectId` from the URL search param (`useSearchParams().get('projectId')`) — no new routing.
2. If `projectId` is present: `useProjectWorkingFolders(projectId)` fires three `useQuery` calls in parallel. `useCitationsForThread()` is still used to populate `This thread`.
3. If `projectId` is absent: skip the project queries entirely; `This thread` is sourced only from `useCitationsForThread()`.
4. Panel assembles `Node[]` and renders `<FolderTree>`.

## 8. Click behavior (per user decision: mixed)

| Node kind | Click |
|---|---|
| Internal document | Adapter converts `Document → Citation`; opens existing `CitationPanel`. |
| External source | `CitationPanel` in external-doc mode (arXiv/web link out). |
| Note | `router.push('/projects/[id]/notes/[noteId]')` — contingent on route existing; verify in the plan. |
| Draft | `router.push('/projects/[id]/drafts/[draftId]')` — same. |
| Folder header | Toggle expand/collapse. No other action. |

The panel exposes a single `onSelect(node: FileNode)` callback. `layout.tsx` wires it, giving the chat page control over whether to open preview or navigate.

## 9. Error handling

- Each of the three project queries is independent. If one fails, its folder is omitted and a `console.warn` fires. We don't surface inline error states in the MVP — a missing folder is less disruptive than a flash of error chrome.
- No project + no thread citations → `This thread` empty + CTA. Panel never hides, so the user can always find it.
- A document with no title → row label falls back to `'Untitled document'`. A draft with no title → `'Draft v{n}'`.

## 10. Testing

**Unit**
- `WorkingFoldersPanel.test.tsx`:
  - project-bound → renders all four folders when all three project lists are non-empty.
  - project-bound → hides `Sources` / `Notes` / `Drafts` when they're empty; `This thread` stays.
  - no-project → renders only `This thread` + CTA.
  - Mock `useProjectWorkingFolders` so tests never hit the network.
- `FolderTree.test.tsx`:
  - Expand/collapse toggles visibility of children.
  - Default-open folders render their children on first render.
  - `onSelect` fires with the correct node when a leaf is clicked.
- `useProjectWorkingFolders.test.ts`:
  - Returns shape `{documents, notes, drafts, isLoading, errors}`.
  - A failing query leaves the other two untouched.

**No new E2E.** The existing chat E2E covers the rail's presence; the tree's behavior is unit-tested.

## 11. Files to create / modify

| Status | Path |
|---|---|
| new | `frontend/src/components/context-rail/folder-tree/types.ts` |
| new | `frontend/src/components/context-rail/folder-tree/FolderTree.tsx` |
| new | `frontend/src/components/context-rail/folder-tree/FolderNode.tsx` |
| new | `frontend/src/components/context-rail/folder-tree/FileRow.tsx` |
| new | `frontend/src/components/context-rail/hooks/useProjectWorkingFolders.ts` |
| rewrite | `frontend/src/components/context-rail/WorkingFoldersPanel.tsx` |
| modify | `frontend/src/components/context-rail/ContextRail.tsx` (forward `projectId` prop) |
| modify | `frontend/app/(dashboard)/chat/layout.tsx` (read `projectId` from URL, pass down, wire `onSelect`) |
| new | `frontend/src/components/context-rail/__tests__/FolderTree.test.tsx` |
| modify | `frontend/src/components/context-rail/__tests__/WorkingFoldersPanel.test.tsx` (if present) or new |
| new | `frontend/src/components/context-rail/hooks/__tests__/useProjectWorkingFolders.test.ts` |

## 12. Open questions the implementation plan must verify

- **Route existence.** Do `/projects/[id]/notes/[noteId]` and `/projects/[id]/drafts/[draftId]` exist? If not, the note/draft click behavior downgrades to opening a minimal read-only preview in `CitationPanel`. Verify in the first task.
- **`CitationPanel → Document` adapter.** Confirm `CitationPanel` can accept a synthetic citation (title + documentId, empty snippet). If it requires real chunks, the adapter fetches one via an existing documents endpoint.
- **`useSearchParams` vs. Next router version.** App Router uses `next/navigation`'s `useSearchParams`; confirm in the first task that this is what other client components are doing.
