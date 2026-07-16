# Frontend Store Race-Pattern Sweep Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Also use the audit-ledger skill (ledger below) and superpowers:test-driven-development for every fix.

**Goal:** Apply the Codex-verified race-pattern toolkit (request-identity tokens, guarded exits, single-flight settle-clearing) from PR #1221 and the wiki research (`Research: Async race patterns in UI state stores`, brain vault) to every remaining NOUS frontend store.

**Architecture:** Each fix follows the pattern proven in `frontend/src/store/chat/slices/threadSlice.ts` (PR #1221, commit `e0e97cf8`): a module-scope `Map<key, object>` of unique request tokens outside Zustand/Immer state, token installed at request start, ownership checked before every shared-state write (success, catch, finally), entry deleted on settle only by the latest owner. Behavior changes each get a test that FAILS against the unfixed code (verify by stashing the source fix — "stash-verify").

**Tech Stack:** Next.js 16 / TypeScript strict, Zustand (+ Immer on some stores), vitest (`--project unit`), ESLint + coverage ratchets (`scripts/ci/check_frontend_quality.mjs`, `check_frontend_coverage.mjs`).

**Prerequisite:** PR #1221 must be merged first (all checks green as of 2026-07-16). Phase A edits the same files.

**Ledger:** Create `~/.audit-ledgers/rag/frontend-store-race-sweep-2026-07-16.md` with one row per task ID below (RS-A1, RS-B1, RS-B2, RS-C1…RS-C4) before starting. Claim rows per the audit-ledger skill — parallel sessions must not double-fix.

**Worktree discipline:** Branch off `origin/develop` (local develop is a diverged fork — never use it). One PR per phase. Frontend commands run from `frontend/` after `pnpm install --frozen-lockfile` at the worktree root — a fresh worktree has NO node_modules, and a global PATH `tsc` will silently false-pass without them (verified 2026-07-16).

---

## Phase A — chat-store parity (finish what #1221 scoped out)

### Task A1: `loadConversations` request-token + stale-404 guard

`conversationSlice.loadConversations` has the identical A→B→A supersession race and unconditional 404 recovery that `loadThreads` had (Codex finding 1 / CS6). Mirror the `loadThreads` fix exactly.

**Files:**
- Modify: `frontend/src/store/chat/slices/conversationSlice.ts` (the `loadConversations` action)
- Test: `frontend/src/store/__tests__/chat-store-cache-cleanup.test.ts` (extend)

**Step 1: Write the failing tests** (mirror the two `loadThreads` tests added in `e0e97cf8` — "drops a superseded same-conversation response" and "ignores a superseded 404 even when still current", adapted to workspaces):

```ts
describe('loadConversations request identity', () => {
  beforeEach(() => {
    act(() => { useChatStore.getState().reset(); });
    vi.clearAllMocks();
  });

  it('drops a superseded same-workspace response instead of overwriting the newer list', async () => {
    let resolveStale!: (v: unknown) => void;
    let resolveFresh!: (v: unknown) => void;
    (workspaceService.listConversations as ReturnType<typeof vi.fn>)
      .mockReturnValueOnce(new Promise((r) => { resolveStale = r; }))
      .mockReturnValueOnce(new Promise((r) => { resolveFresh = r; }));

    const stale = useChatStore.getState().loadConversations('ws-1');
    const fresh = useChatStore.getState().loadConversations('ws-1');
    resolveFresh({ conversations: [makeConversation('conv-new', 'ws-1')], total: 1, page: 1, limit: 50, has_more: false });
    await act(async () => { await fresh; });
    resolveStale({ conversations: [makeConversation('conv-old', 'ws-1')], total: 1, page: 1, limit: 50, has_more: false });
    await act(async () => { await stale; });

    expect(useChatStore.getState().conversations['ws-1'].map((c) => c.id)).toEqual(['conv-new']);
  });

  it('ignores a late 404 for a superseded workspace load (no stale-data recovery)', async () => {
    useChatStore.setState({ currentWorkspaceId: 'ws-1', workspaces: [makeWorkspace('ws-1')] });
    let rejectStale!: (r: unknown) => void;
    let resolveFresh!: (v: unknown) => void;
    (workspaceService.listConversations as ReturnType<typeof vi.fn>)
      .mockReturnValueOnce(new Promise((_, rej) => { rejectStale = rej; }))
      .mockReturnValueOnce(new Promise((r) => { resolveFresh = r; }));

    const stale = useChatStore.getState().loadConversations('ws-1');
    const fresh = useChatStore.getState().loadConversations('ws-1');
    resolveFresh({ conversations: [], total: 0, page: 1, limit: 50, has_more: false });
    await act(async () => { await fresh; });
    rejectStale(Object.assign(new Error('Not Found'), { response: { status: 404 } }));
    await act(async () => { await stale; });

    expect(useChatStore.getState().currentWorkspaceId).toBe('ws-1');
    expect(useChatStore.getState().workspaces).toHaveLength(1);
    expect(workspaceService.getOrCreateDefaultWorkspace).not.toHaveBeenCalled();
  });
});
```

**Step 2: Run to verify both fail** — `pnpm exec vitest run --project unit src/store/__tests__/chat-store-cache-cleanup.test.ts`. Expected: first test gets `['conv-old']` (stale clobber), second fires recovery.

**Step 3: Implement** in `conversationSlice.ts` — copy the exact structure from `threadSlice.ts`:

```ts
// Same rationale as threadSlice's loadThreadsRequestTokens — see that comment.
const loadConversationsRequestTokens = new Map<string, object>();

loadConversations: async (workspaceId) => {
  const requestToken = {};
  loadConversationsRequestTokens.set(workspaceId, requestToken);
  set((state) => { state.isLoadingConversations = true; state.error = null; });
  try {
    const response = await workspaceService.listConversations(workspaceId);
    if (loadConversationsRequestTokens.get(workspaceId) !== requestToken) return;
    /* existing success set() body unchanged (list replace + reverse-index rebuild) */
  } catch (error) {
    if (loadConversationsRequestTokens.get(workspaceId) !== requestToken) return;
    /* existing catch body; inside the 404 branch, additionally skip recovery when
       get().currentWorkspaceId !== workspaceId (mirror loadThreads' guard, clearing
       isLoadingConversations only) */
  } finally {
    if (loadConversationsRequestTokens.get(workspaceId) === requestToken) {
      loadConversationsRequestTokens.delete(workspaceId);
    }
  }
},
```

**Step 4: Run tests — both pass.** Then stash-verify: `git stash push -- frontend/src/store/chat/slices/conversationSlice.ts`, re-run (expect exactly these 2 failures), `git stash pop`.

**Step 5: Commit** — `fix(chat-store): request-token guard for loadConversations (parity with loadThreads)`.

---

## Phase B — pipelineStore (unguarded single-slot store)

### Task B1: `fetchPipeline` stale-response guard

`frontend/src/store/pipelineStore.ts:33` — single `pipeline` slot parameterized by `projectId`, zero guards: switch project A→B while A's fetch is slow → B's view shows A's pipeline. Also the catch sets a global error for a superseded request.

**Files:**
- Modify: `frontend/src/store/pipelineStore.ts:33-43`
- Test: Create `frontend/src/store/__tests__/pipelineStore.race.test.ts`

**Step 1: Failing test** — two deferred `scispaceService.getPipeline` mocks; fetch for `proj-a`, then `proj-b`; resolve B then A; assert `pipeline.project_id === 'proj-b'` (or whatever id field the Pipeline type carries — check `scispaceService` types first) and that a late rejection of A leaves `error` null.

**Step 2: Verify it fails** (A's payload wins on old code).

**Step 3: Implement** — this store has ONE slot, so a single module-scope token (no Map needed):

```ts
let pipelineRequestToken: object | null = null;

fetchPipeline: async (projectId: string) => {
  const requestToken = {};
  pipelineRequestToken = requestToken;
  set({ loading: true, error: null });
  try {
    const pipeline = await scispaceService.getPipeline(projectId);
    if (pipelineRequestToken !== requestToken) return;
    set({ pipeline, loading: false });
  } catch (err) {
    if (pipelineRequestToken !== requestToken) return;
    const message = err instanceof Error ? err.message : 'Failed to load pipeline';
    set({ error: message, loading: false });
  }
},
```

**Step 4: Tests pass + stash-verify. Step 5: Commit.**

### Task B2: audit the pipeline mutation actions (`advanceStep`/`skipStep`/`goToStep`/`updateStepData`/`resetPipeline`)

Each does `get().pipeline` → service call → `set` — read-modify-write against a slot `fetchPipeline` can swap mid-flight. Audit each: if the service response carries the canonical pipeline, commit only when the response's project matches the current slot (existence ≠ identity — the CS7 lesson). Write the ledger row with the verdict per action; fix only confirmed races (YAGNI on the rest, note why). Template = B1's token check.

---

## Phase C — audits with verdicts (fix only what's confirmed)

Each task ends with a ledger row: CONFIRMED+fixed, or REFUTED with one-line invariant evidence (the PR #1221 triage format).

### Task C1: agentChatStore exit-guard + controller-placement audit

**Files:** `frontend/src/store/agentChatStore.ts` (1068 lines; existing generation guard around line 97), tests in `src/store/__tests__/agentChatStore*.test.ts`.

Check three things against the toolkit:
1. Every `catch`/`finally` that writes shared state checks the generation/ownership (the CS4 class — an unguarded catch is the same bug as an unguarded commit).
2. `_abortController` lives IN Zustand state (line 29). Verify the store has no `persist`/Immer interaction that proxies or serializes it; if it does, move to module scope (the requestCoordinator pattern). If it provably doesn't, REFUTE with evidence and leave it.
3. Mutation-verify any race test you touch (delete the guard → test must fail; see `nous-mutation-verified-race-tests` in the brain vault — a passing race test proves nothing until mutation-killed, and vitest can serve mock/real to sibling calls).

### Task C2: projectStore single-flight settle-clearing

**Files:** `frontend/src/store/projectStore.ts` (module-scope `inflightProjectFetch`, ~line 32), `src/store/__tests__/projectStore.fetchProject-dedup.test.ts`.

Verify `inflightProjectFetch` is cleared on rejection AND fulfillment (`finally`), and that a caller arriving with a *different* id doesn't inherit the old flight. If the rejection path retains the promise, every later caller inherits the failure — write the failing test (dedup'd call after a rejected first call must issue a NEW request), fix with `finally`, stash-verify.

### Task C3: citationStore fetch slot audit

**Files:** `frontend/src/store/citationStore.ts:34` (`fetchCitationsForMessage`).

Determine whether citations are keyed per-message (Record) or a single slot. Single slot + message switching = the pipelineStore bug → apply B1's fix shape. Per-message Record with no cross-message overwrite → REFUTE and close the row.

### Task C4: projectChatStore mutation actions

**Files:** `frontend/src/store/projectChatStore.ts:133-330`.

`fetchProjectThreads` is already seq-guarded (leave it; never-reset counter is safe — do NOT "upgrade" it to delete-on-settle without switching to tokens, that's the recycling trap). Audit `startChatFromProject` / `linkThreadToProject` / `unlinkThreadFromProject` / `saveThreadToNote`: do they commit from the response (correct) or from requested inputs (the CS5 class)? Do their catch blocks write errors into per-project slots that a newer request owns?

---

## Phase D — close-out (after each phase's PR, and finally)

1. Full gauntlet from `frontend/`: `pnpm type-check` → `pnpm exec vitest run --project unit` → ESLint report + `node ../scripts/ci/check_frontend_quality.mjs --report <json> --base origin/develop` **after committing** (the ratchet resolves changed files from committed diffs — untracked test files are invisible to it) → `pnpm test:coverage` + `node ../scripts/ci/check_frontend_coverage.mjs coverage/coverage-summary.json`.
2. One PR per phase off `origin/develop`, titled `fix(stores): …`, body listing ledger IDs with verdicts.
3. Update the ledger rows to `pr`/`merged` as they move; log REFUTED verdicts so future sweeps don't re-audit (the tenancy-sweep convention).
4. After the last phase: update the brain-vault page `request-identity-guard` with anything the sweep contradicts or refines.
