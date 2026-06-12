# Research UI components

These components power the research workflow surface in NOUS: project management, the five-step
literature-review pipeline, note-taking, data extraction, draft authoring, and linked chat threads.

## Key components

| File                          | What it does                                                                                                                  |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `ResearchPipeline.tsx`        | Top-level wizard container; orchestrates `PipelineStepper` + the five step components via `usePipelineStore`                  |
| `PipelineStepper.tsx`         | Horizontal stepper showing step states (active / completed / skipped / invalidated / upcoming)                                |
| `steps/CollectStep.tsx`       | Step 1 — confirms ≥1 document is present before the pipeline can advance                                                      |
| `steps/ExtractStep.tsx`       | Step 2 (skippable) — wraps `ExtractionMatrix` for structured data pull across docs                                            |
| `steps/CiteStep.tsx`          | Step 3 — renders and downloads bibliography (BibTeX / IEEE / APA / MLA) via `useProjectStore`                                 |
| `steps/DraftStep.tsx`         | Step 4 — composes `DraftGenerator`, `DraftViewer`, `DraftGenerationProgress`, and a collapsible RAG chat panel                |
| `steps/ExportStep.tsx`        | Step 5 (terminal) — multi-format export: draft (Markdown / LaTeX), CSV extraction, bibliography                               |
| `ProjectList.tsx`             | Grid/list toggle of all projects; delegates cards to `ProjectCard`                                                            |
| `ProjectCard.tsx`             | Single project card with status badge, action menu (archive / delete / restore)                                               |
| `ProjectListSkeleton.tsx`     | Pulse-animated loading placeholder for the project grid                                                                       |
| `ProjectHeader.tsx`           | Hero card shown at the top of a project page: name, type label, status badge, relative deadline                               |
| `ProjectDetail.tsx`           | Tab shell (Documents / Notes / Bibliography / Drafts) with slot for tab content                                               |
| `CreateProjectModal.tsx`      | Dialog for creating a new project (name, description, type, deadline)                                                         |
| `DocumentList.tsx`            | Searchable, sortable, filterable list of project documents with bulk-select and remove                                        |
| `ExtractionMatrix.tsx`        | Structured-extraction table — define columns, trigger extraction, display results via `scispaceService`                       |
| `ColumnEditor.tsx`            | Inline editor for adding / reordering extraction columns; ships six preset column definitions                                 |
| `CellCitation.tsx`            | Popover showing the source snippet and a colour-coded confidence indicator for an extraction cell                             |
| `NoteEditor.tsx`              | Markdown dialog editor (edit / preview modes) with tag management, document linking, and inline AI writing tools              |
| `NoteList.tsx`                | Pinned-first, tag-filtered list of project notes with pin / edit / delete actions                                             |
| `DraftGenerator.tsx`          | Form for configuring generation (themes, style, section count, abstract toggle); roving-tabindex style picker                 |
| `DraftGenerationProgress.tsx` | Polling progress indicator across six generation phases with elapsed timer and cancel                                         |
| `DraftViewer.tsx`             | Rendered Markdown draft with version history, selection-triggered `ToneToolbar` and `WriterToolbar`, export buttons           |
| `DraftComparison.tsx`         | Side-by-side diff of two draft versions with word-level change highlighting and stat deltas                                   |
| `DraftExportModal.tsx`        | Export dialog: format (Markdown / LaTeX), include-metadata toggle, download trigger                                           |
| `ToneToolbar.tsx`             | Floating selection toolbar for tone rewrites (academic / simplified / expanded / concise) via `scispaceService.rewriteText`   |
| `WriterToolbar.tsx`           | Floating cursor toolbar for AI completions, section generation, and outline requests via `scispaceService.writeText`          |
| `RewriteDiffView.tsx`         | Word-level diff between original and AI-rewritten text with accept / reject controls                                          |
| `InsertPreview.tsx`           | Preview card for AI-generated section content (confidence badge, section type label, accept / edit / discard)                 |
| `OutlineDialog.tsx`           | Dialog for generating a structured outline from project documents; inserts sections into the editor                           |
| `ProjectKnowledgeTree.tsx`    | Collapsible entity tree grouped by type, fetched from `/api/v1/kg/` via `api-client`; up to 500 entities / 1000 relationships |
| `ProjectChatTab.tsx`          | Chat threads tab; uses `useProjectChat` hook and `projectChatStore` to start, link, unlink, and save threads                  |
| `ThreadCard.tsx`              | Card for a linked chat thread with message count, last-active timestamp, navigate / unlink / save-to-note actions             |
| `StartChatModal.tsx`          | Dialog for opening a new thread seeded with an initial message                                                                |
| `LinkThreadModal.tsx`         | Dialog that searches existing workspace threads and links one to the project                                                  |
| `SaveToNoteModal.tsx`         | Dialog for converting a thread into a project note (title + include-citations toggle)                                         |
| `ResearchErrorBoundary.tsx`   | Class-based error boundary wrapping research subtrees; shows a recovery UI with reset and home actions                        |

## State and data flow

- **`usePipelineStore`** (`pipelineStore`) — pipeline step progression, completion, skip, and invalidation state.
- **`useProjectStore`** (`projectStore`) — project documents, notes, bibliography, draft list; calls `projectService`.
- **`useProjectChatStore`** + **`useProjectChat`** hook — thread list, link/unlink, save-to-note operations.
- **`projectService`** — REST calls for projects, documents, notes, drafts, bibliography, generation status.
- **`scispaceService`** — extraction matrix CRUD, `rewriteText`, `writeText`, `generateOutline`.
- **`api-client`** — raw axios wrapper used directly by `ProjectKnowledgeTree` for KG entity/relationship endpoints.
- **`workspaceService`** — thread search used by `LinkThreadModal`.

## Subdirectories

- **`steps/`** — the five pipeline step components (`CollectStep`, `ExtractStep`, `CiteStep`, `DraftStep`, `ExportStep`). Each is a self-contained step that receives navigation callbacks from `ResearchPipeline`.
- **`__tests__/`** — co-located unit, integration, and accessibility tests (Jest + Testing Library). Coverage includes `DraftGenerator` keyboard/roving-tabindex behaviour, `DraftViewer`, `NoteEditor`, `ProjectList`, debounce logic, agent-sync behaviour, and `WriterToolbar`.

## Accessibility notes

All interactive controls carry `aria-label`; `IconButton` usage requires one. The `DraftGenerator` style picker implements a roving `tabIndex` pattern (`ArrowLeft`/`ArrowRight` navigation). Colour-coded states (status badges, confidence dots) always pair the colour with a visible text label to meet WCAG 2.1 AA.
