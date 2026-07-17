# Chat store/hook guard mutation checks

Task 5.5 mutation-verifies the critical async-reconciliation and
single-flight guards identified in recon (`chatfe.guards`) — **7 guard groups**
(1, 2, 3, 4a, 4b, 5, 6) below, each with its own covering test. For each guard
below the check was: temporarily disable the guard on disk (comment it out),
run the named focused command and confirm it fails with the assertion shown,
restore the guard by editing back to the original text, confirm `git diff`
on the file is empty (byte-identical to HEAD), then rerun the command and
confirm it passes. No guard's source was left modified — see the commit for
this task, which touches tests and this doc only.

The deterministic interleaving harness (`frontend/src/test/concurrency/`, PR
"test: deterministic interleaving harness") will be the living successor to this
one-time manual verification once that PR lands — `pnpm test:mutants` will be the
automated spot-check that keeps these guards honest without hand-editing source.

The plan's literal Task 5.5 file list names two covering-test files:
`frontend/src/store/__tests__/chat-store-refresh.test.ts` (items 1 and 2 —
the stale-response and terminal-reconciliation guards) and
`frontend/src/hooks/__tests__/useChatSession.threadSwitchBleed.test.tsx`
(item 6 — the loading-skeleton gate that the thread-switch-bleed suite
exercises). Both files carry short doc comments pointing back to this file.
Items 3, 4a, 4b, and 5 mutation-verify the remaining guards recon's
`chatfe.guards` sweep located in `useChatStreaming.ts`, beyond the plan's
named-file scope.

Run from `frontend/`.

## 1. Stale-response rejection (REQUEST-IDENTITY)

- **Guard:** `src/store/chat/slices/messageSlice.ts:130-132` — post-fetch
  identity check inside `refreshMessages`:
  `if (newestPageRequests.get(threadId) !== request) { return false; }`.
  Drops a superseded newest-page response after a fast thread switch issues a
  second `refreshMessages` call for the same thread.
- **Covering test:** `src/store/__tests__/chat-store-refresh.test.ts` →
  `per-thread newest-page coordinator > aborts and supersedes an older
  newest-page request for the same thread`.
- **Command:**
  `pnpm exec vitest run --project unit src/store/__tests__/chat-store-refresh.test.ts -t "aborts and supersedes an older newest-page request"`
- **Mutation kills it with:**
  `AssertionError: expected [ 'm1' ] to deeply equal [ 'm2' ]` — the older
  (superseded) response is allowed to clobber the newer one's messages.

## 2. Expectation reconciliation (expectationMet)

- **Guard:** `src/store/chat/slices/messageSlice.ts:138-149` (build
  `expectationIds`/`expectationMet` from `persistedId`/`runtimeId`) and
  `:176` (`state.messageFreshness[threadId] = expectationMet ? 'fresh' :
  'stale';`). This is the core terminal-reconciliation correctness guard: a
  terminal turn whose expected message id is not yet in the fetched page
  must keep the thread `stale` (preserving the optimistic overlay) instead
  of flipping to `fresh` on an incomplete page.
- **Covering test:** `src/store/__tests__/chat-store-refresh.test.ts` →
  `per-thread newest-page coordinator > leaves freshness stale when the
  expected persisted or runtime row is missing`.
- **Command:**
  `pnpm exec vitest run --project unit src/store/__tests__/chat-store-refresh.test.ts -t "leaves freshness stale when the expected persisted or runtime row is missing"`
- **Mutation kills it with:**
  `AssertionError: expected 'fresh' to be 'stale'`.

## 3. Thread-scope turn gating (isTurnDisplayed)

- **Guard:** `src/hooks/chat/useChatStreaming.ts:389-391` — `runStreamTurn`
  snapshots `turnThreadId` and defines `isTurnDisplayed = () =>
  useChatStore.getState().currentThreadId === turnThreadId`, which gates
  every local `setMessages` call for the turn (committed content, error
  bubbles, etc.). Without it, a background turn's completion renders into
  whatever thread happens to be displayed after a mid-stream thread switch.
- **Covering test:**
  `src/hooks/__tests__/useChatStreaming.threadSwitch.test.tsx` → `useChatStreaming
  thread-switch guard > skips the final setMessages when the user switched
  threads mid-stream`.
- **Command:**
  `pnpm exec vitest run --project unit src/hooks/__tests__/useChatStreaming.threadSwitch.test.tsx -t "skips the final setMessages when the user switched threads mid-stream"`
- **Mutation kills it with:**
  `expect(params.setMessages).not.toHaveBeenCalled()` — `Number of calls: 1`
  (thread A's answer bled into thread B's displayed transcript).

## 4a. HITL confirm idempotency (confirmLockRef)

- **Guard:** `src/hooks/chat/useChatStreaming.ts:1162`
  (`if (confirmLockRef.current) return;`), set at `:1173`, released in the
  `finally` at `:1514`. Client-side belt against a synchronous double-click
  on Approve firing `streamConfirm` twice (the server also claims
  atomically — this is defense in depth, and the client-only ref is what
  this test isolates).
- **Covering test:**
  `src/hooks/__tests__/useChatStreaming.confirmToolSteps.test.tsx` →
  `useChatStreaming HITL confirm tool steps > CX1: a synchronous double-click
  on Approve only fires streamConfirm once`.
- **Command:**
  `pnpm exec vitest run --project unit src/hooks/__tests__/useChatStreaming.confirmToolSteps.test.tsx -t "CX1: a synchronous double-click on Approve only fires streamConfirm once"`
- **Mutation kills it with:**
  `AssertionError: expected "spy" to be called 1 times, but got 2 times`.

## 4b. HITL confirm thread-scope (confirmationBelongsToThread)

- **Guard:** `src/hooks/chat/useChatStreaming.ts:172-178` —
  `confirmationBelongsToThread(pending, displayedThreadId)` returns
  `pending.workspaceThreadId === (displayedThreadId ?? '')`. Checked before
  `streamConfirm` (`:1166-1172`) and gates every local `setMessages` in the
  confirm path via `isConfirmDisplayed()` (`:1179-1183`) — a stale click (or
  a confirmation belonging to a different thread) must not resume/render
  against the wrong thread's transcript.
- **Covering test:** `src/hooks/__tests__/confirmationScope.test.ts` — pure
  unit tests on the predicate itself (`rejects a different displayed
  thread`, `handles the new-chat (null thread) case`).
- **Command:**
  `pnpm exec vitest run --project unit src/hooks/__tests__/confirmationScope.test.ts`
- **Mutation kills it with:** two assertions flip from `false` to `true`
  (`AssertionError: expected true to be false`) — a mismatched-thread
  confirmation is wrongly reported as belonging to the displayed thread.

## 5. Submit single-flight (submitLockRef)

- **Guard:** `src/hooks/chat/useChatStreaming.ts:279` (`submitLockRef`
  declaration), checked at `:885` (`if (submitLockRef.current) return;`),
  set at `:890`, released at `:858`/`:1003`/`:1069`. Prevents a second
  `handleSubmit` call (fast double Enter/click) from firing a second
  `streamMessage` while the first turn is still in flight.
- **Covering test:** none existed for this guard specifically (the composer
  `isLoading`/`storeIsStreaming` content guard was covered indirectly, but
  no test exercised the synchronous-double-call race the ref exists for).
  **Added:** `src/hooks/__tests__/useChatStreaming.submitLock.test.tsx` →
  `useChatStreaming submit single-flight (submitLockRef) > a synchronous
  second handleSubmit call while the first is still in flight only fires
  streamMessage once`, mirroring the CX1 confirmLockRef test pattern.
- **Command:**
  `pnpm exec vitest run --project unit src/hooks/__tests__/useChatStreaming.submitLock.test.tsx`
- **Mutation kills it with:**
  `AssertionError: expected "spy" to be called 1 times, but got 2 times`.

## 6. Loading-skeleton gate (isThreadSwitchPending)

- **Guard:** `src/components/chat/shared/cloudMessageView.ts:197-209` —
  `isThreadSwitchPending` returns true only when the active thread's initial
  page is genuinely in flight (`loadingThreadId === activeThreadId`) and
  nothing is renderable yet (`localMessageCount === 0 && storeMessageCount
  === 0`). `useChatSession.ts` feeds this into the returned
  `isLoadingMessages`. This is the #1121-regression fix scope: an
  already-cached thread switch, or a local optimistic/streaming turn, must
  never blank the transcript behind a skeleton.
- **Covering test:**
  `src/hooks/__tests__/useChatSession.threadSwitchBleed.test.tsx` →
  `useChatSession thread-switch transcript bleed (I1) > clears thread A and
  waits for the single paginated store load on a cache miss`.
- **Command:**
  `pnpm exec vitest run --project unit src/hooks/__tests__/useChatSession.threadSwitchBleed.test.tsx -t "clears thread A and waits for the single paginated store load on a cache miss"`
- **Mutation kills it with:** `AssertionError: expected false to be true` on
  `expect(result.current.isLoadingMessages).toBe(true)`.
