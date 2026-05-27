# Chat Context Rail — Design

**Status:** approved (brainstorming)
**Date:** 2026-04-20
**Owner:** Abdel
**Supersedes:** the deleted `ContextPanel` / `CitationsTabContent` in `frontend/app/(dashboard)/chat/layout.tsx`

## Context

The chat page's right sidebar (`ContextPanel` in `chat/layout.tsx`) was removed wholesale by a parallel editing session — ~612 lines, including the Active Document card, Related Results list, Follow-up Suggestions, and the Citations tab. The removal left three features orphaned:

- `useCitationsForThread().allCitations` has no consumer.
- `useCitationsForThread().relatedResults` has no consumer.
- There is no surface in the UI that shows what the agent is doing while it runs — today the only signal is streaming tokens.

The design-system page now ships a `NousAgentStatusCard` primitive (crossed-off steps with active/pending dots) that mirrors the Agent Activity mockup the user wants. This design brings those three features back as a stacked right-rail, using the existing primitive for Agent Activity and reusing the citations hook for the other two.

## Goals

1. Restore Related Results and All-thread Citations as visible, reactive panels.
2. Add Agent Activity — a live, reactive checklist of tool calls during an agent run, with the last run frozen on screen when idle.
3. Visual fidelity to the `NousAgentStatusCard` mockup in the design-system page.
4. Zero backend changes.

## Non-goals (v1)

- Pre-declared planner steps (pending rows) — see Approach (a) decision below.
- Hydrating historical runs from the backend `tool_executions` checkpoint.
- Dashboard home page rail.
- Persisting the live tool log across reloads.

## Decisions

| Question | Choice |
|---|---|
| Surface | (b) Stacked right rail at `xl:` breakpoint, same position as the homepage mockup |
| Agent step source | (a) Reactive log from live `tool_start` / `tool_end` events; no upfront pending rows |
| Idle state | (i) Freeze the last run's step list; hide the card when no run has ever occurred on this thread |
| Mount strategy | (X) `<ContextRail>` mounted in `chat/layout.tsx` alongside `{children}` |

## Architecture

### File layout

```
frontend/src/components/context-rail/
  ContextRail.tsx                 # stacks the three cards; owns the scroll container
  AgentActivityPanel.tsx          # wraps NousAgentStatusCard + reads agentActivityStore
  RelatedResultsPanel.tsx         # reads useCitationsForThread().relatedResults
  AllCitationsPanel.tsx           # reads useCitationsForThread().allCitations
  toolLabels.ts                   # tool-name → human label map + fallback
  index.ts                        # barrel
frontend/src/stores/
  agentActivityStore.ts           # zustand — per-thread step log + last-run snapshot
frontend/src/components/context-rail/__tests__/
  agentActivityStore.test.ts
  AgentActivityPanel.test.tsx
  RelatedResultsPanel.test.tsx
  AllCitationsPanel.test.tsx
  toolLabels.test.ts
```

### Mount point

`chat/layout.tsx` — single new line next to `{children}`:

```tsx
<ContextRail className="hidden xl:flex shrink-0 w-[360px] border-l border-[var(--nous-border-1)]" />
```

### Reused assets

- `NousAgentStatusCard` — the visual primitive is already shipped in the design-system page; `<AgentActivityPanel>` is a thin wrapper that feeds it `{ name, task, steps[] }` from the store.
- `useCitationsForThread()` — both citation panels; already reactive through `useChatPersistence()`.
- `agentChatService.streamMessage()` — already exposes `onToolStart`, `onToolEnd`, `onDone`, `onError`. No service change needed; `chat/page.tsx` forwards these callbacks into the store.
- `var(--nous-*)` tokens — colors, radii, shadows, type stack. No new tokens.

## Data flow

### Store (`agentActivityStore.ts`)

```ts
type StepStatus = 'active' | 'done' | 'error';
type Step = { id: string; tool: string; label: string; status: StepStatus; at: number };
type Run  = {
  threadId: string;
  name: string;                        // e.g. "Literature synth"
  task: string;                        // subtitle — derived from user message
  steps: Step[];
  state: 'running' | 'done' | 'error';
  startedAt: number;
};

interface AgentActivityStore {
  runs: Record<string /*threadId*/, Run>;
  currentThreadId: string | null;
  startRun(threadId: string, name: string, task: string): void;
  pushToolStart(threadId: string, tool: string): void;
  pushToolEnd(threadId: string, tool: string, ok: boolean): void;
  finishRun(threadId: string, state: 'done' | 'error'): void;
}
```

### Wiring (`chat/page.tsx`, inside `handleSubmit`)

Before calling `agentChatService.streamMessage(...)`, forward callbacks:

```
startRun(currentThreadId, deriveAgentName(...), deriveTaskFromUserMsg(input))
onToolStart:  (t)      => pushToolStart(threadId, t)
onToolEnd:    (t, ok)  => pushToolEnd(threadId, t, ok)
onDone:       ()       => finishRun(threadId, 'done')
onError:      ()       => finishRun(threadId, 'error')
```

### Step label mapping (`toolLabels.ts`)

Explicit table for known tools:

| tool (snake_case) | label |
|---|---|
| `arxiv_search` | Search arXiv |
| `arxiv_ingest` | Ingest papers |
| `document_search` | Search documents |
| `ingest_document` | Ingest document |
| `create_draft` | Draft synthesis |
| `create_note` | Save note |
| `entity_search` | Query entities |
| `kg_query` | Query knowledge graph |
| `project_create` | Create project |
| `compare_documents` | Compare documents |
| `reflect` | Reflect on progress |

Unknown → `tool.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())`.

### Name & task derivation

- **Name** — read subgraph from the first `trace` or `rag_context` event (if available) and map: `research → "Literature synth"`, `writing → "Draft assistant"`, `data → "Entity analyst"`, `general → "NOUS Agent"`. Fallback: `"NOUS Agent"`.
- **Task** — first 60 chars of the user message that triggered the run, trimmed at word boundary. Example: `"How does the attention mechanism differ in Mamba-2?"` → `"Reviewing: How does the attention mechanism differ…"`.

### Idle rendering

`<AgentActivityPanel>` reads `runs[currentThreadId]`.
- `state === 'running'` → live render, last step's dot pulses.
- `state !== 'running'` and run exists → frozen render, no pulse, all steps final.
- no run → return `null` (card hidden).

### Citations / Related Results

No new store. `useCitationsForThread()` already returns:
- `allCitations: CitationItem[]` — dedup across every assistant message in the thread.
- `relatedResults: CitationItem[]` — top 5 by score.

Panels render empty states identical to the old components; scoring colors follow the existing 70/50/below thresholds mapped onto `--nous-terra`, `--nous-corona`, `--nous-mars`.

## Error handling

- SSE disconnect mid-run → last active step auto-flips to `error` after 5s via a timeout cleared by any subsequent event. Run state → `error`.
- Unknown tool → still rendered with generated label; step not dropped.
- `streamMessage` throws before first tool event → store untouched; card falls back to previous run (idle option i).
- Store is session-only (Zustand default, no `persist` middleware). Page reload clears live state by design; the backend checkpoint still has `tool_executions` for Approach Z later.

## Testing

Target ≥80% coverage on every new file.

| File under test | Tests |
|---|---|
| `agentActivityStore` | startRun initializes; pushToolStart appends; duplicate `tool_start` for same tool is de-duped; pushToolEnd flips status; out-of-order tool_end is ignored; finishRun transitions running→done/error; multi-thread isolation |
| `AgentActivityPanel` | renders running (active dot pulses); renders idle with frozen steps; renders nothing when no prior run |
| `RelatedResultsPanel` | empty state; populated; score-color thresholds at 70/50/below |
| `AllCitationsPanel` | empty state; dedup respected; external vs internal icon |
| `toolLabels` | known tools map exactly; unknown tool fallback formatting |

No E2E changes — rail is additive to existing chat flow.

## Coordination with parallel Claude instance

- **Shared file:** `chat/layout.tsx` only.
- **Mitigation:** our diff is a one-line insert next to `{children}` plus an `import`. Self-contained.
- **Fallback:** if a merge conflict emerges, the rail can be re-mounted inside `chat/page.tsx` (Approach Y) with ~5 lines of change, no other work lost.

## Promotion path

- **To Approach Z (historical hydration):** on thread load, read `tool_executions` from the thread-detail endpoint and seed `runs[threadId]` with `state: 'done'`. Zero store API change.
- **To Approach (b) (pre-declared plan):** extend the SSE stream with a `plan_generated` event; add a store method `preloadPlan(threadId, steps)` that creates steps with `status: 'pending'`. `pushToolStart` flips matching pending steps to active instead of appending.

## Verification

1. `npm run type-check && npm run lint && npm run test` clean.
2. Visit `http://localhost:3000/chat`; right rail appears at ≥1280px viewport.
3. Send a message that triggers `arxiv_search` + `document_search`; watch steps appear in the Agent Activity card as they fire.
4. Refresh — card hidden (session store cleared), citations still populate from server-fetched conversation.
5. Click a citation chip in a message — `CitationPanel` (per-message) opens, coexisting with `AllCitationsPanel` in the rail.
