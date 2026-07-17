# Codex Chat Findings Fixes — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the four surviving findings from the 2026-07-09 Codex review of `/chat` loading + messages (ledger: `~/.audit-ledgers/rag/codex-chat-loading-review-2026-07-09.md`): CX1 double-confirm tool re-execution (P0), CX2 submit-array duality (P1), CX5 global streaming-state thread bleed (P2), CX8 sidebar 50-thread cap (P2); plus a bounded verify for CX6.

**Architecture:** One tight PR per finding, sequenced by severity, each in its own worktree branched off `origin/develop` (NEVER local `develop` — it is ~88 commits behind) and pushed early. CX1 reuses the existing Redis NX lock helper (`_acquire_lock`, `backend/src/core/caching.py:265`) keyed on the interrupt checkpoint id already derived in the confirm generator — the same anchor #1065 uses for resume dedup. CX2 makes the submit path read the same reconciled array the user sees (`displayedMessages`). CX5 adds a `streamingThreadId` store field and gates live-stream UI on it (composer stays globally blocked — single-flight streaming is an invariant, see the existing `ponytail:` comment in `runStreamTurn`). CX8 uses the backend's existing `offset` pagination.

**Tech Stack:** FastAPI + Redis (backend), Next.js 15 + zustand + vitest (frontend), pytest.

**Every line-number below refers to `origin/develop`**, verified 2026-07-09. Re-grep before editing; don't trust the stale local checkout.

**All updates to the audit ledger:** after each PR opens/merges, update the row's Status/PR columns in `~/.audit-ledgers/rag/codex-chat-loading-review-2026-07-09.md` per the audit-ledger skill (claim by ID before branching).

---

## Grounded facts (verified on origin/develop — do not re-derive)

- `POST /confirm/{job_id}` (job path) claims atomically: `compare_and_set_status(job_id, "awaiting_confirmation", "running")` — `backend/src/api/agent/execute.py:391-416`, impl `backend/src/services/agent/job_store.py:244` (Redis WATCH/MULTI). It is **job-keyed**; the SSE confirm path has no job record, so it can't be reused directly.
- `stream_confirm_event_generator` (`backend/src/api/agent/streaming.py:950`) does ownership + snapshot checks, derives `resume_ckpt_id` (`:1040-1052`), then resumes via `Command(resume=...)` (`:1090`) with **no claim** — two concurrent POSTs both resume ⇒ destructive tool runs twice.
- Redis NX lock helper exists: `_acquire_lock(client, lock_key, ttl)` / `_release_lock` — `backend/src/core/caching.py:265-272`.
- `handleSubmit` builds the POSTed history from the **local** `messages` useState (`frontend/src/hooks/chat/useChatStreaming.ts:797`, payload map `:897`), while the page renders `displayedMessages = selectDisplayedMessages({localMessages, storeMessages})` (`frontend/src/hooks/chat/useChatSession.ts:129`; store wins when ≥ local length). Threads are listed with `messages: []` (lazy-loaded), so a switch to a not-yet-lazy-loaded thread does `setMessages([])` (`useChatSession.ts:225`) while the store fills the transcript ⇒ display full, submit sends only the new turn. The store→local sync effect (`:199`) updates `conversations`, **not** `messages`.
- Streaming state is global: `useChatStore.setState({ isStreaming: true, streamingContent: '', streamingSteps: [], ... })` in `runStreamTurn` (`useChatStreaming.ts:406`), with an existing `ponytail:` comment (`:376`) naming per-thread streaming state as the upgrade path. Local message writes are already gated by `isTurnDisplayed()`.
- Sidebar: `workspaceService.listThreads(conversationId, { limit: 50 })` hardcoded 3× (`useChatSession.ts:295,435,525`), `has_more`/total discarded. Backend already paginates: `limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)` (`backend/src/api/threads/threads.py:272-273`).
- CX6 surface: `GET /threads/{thread_id}` has `include_messages: bool = Query(True)` (`threads.py:429`) and the frontend warm/cold-load paths consume `threadDetail.messages` in full (`useChatSession.ts:255,455-471`).

---

## PR 1 — CX1: atomic claim on /stream/confirm (P0, backend only, independent)

Branch: `fix/hitl-stream-confirm-claim` off `origin/develop`, own worktree, push after first commit.

### Task 1.1: Claim ledger row

Set CX1 `Status=claimed`, `Owner=<session>` in the ledger BEFORE branching.

### Task 1.2: Write the failing test — double confirm resumes once

**Files:**
- Test: `backend/tests/agent/test_stream_confirm_claim.py` (new)
- Reference for fixtures: `backend/tests/agent/test_streaming_resume.py` (existing patterns for faking the graph/checkpointer in `stream_confirm_event_generator`)

**Step 1: Write the failing test**

```python
"""Double-POST /stream/confirm must resume the graph exactly once (CX1).

The job confirm endpoint has a CAS (execute.py:409); the SSE confirm path
had none — two concurrent confirms both issued Command(resume=...) and a
destructive HITL tool could execute twice.
"""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_concurrent_stream_confirms_resume_once(
    stream_confirm_harness,  # build per existing test_streaming_resume.py fixtures
):
    """Two overlapping confirm generators for the same interrupt: exactly one
    reaches graph.astream_events; the loser yields an error frame and stops."""
    harness = stream_confirm_harness
    resume_calls = []

    async def fake_astream_events(*a, **k):
        resume_calls.append(1)
        yield {"event": "on_chat_model_stream", "data": {}}

    harness.graph.astream_events = fake_astream_events

    async def drain(gen):
        return [frame async for frame in gen]

    out1, out2 = await asyncio.gather(
        drain(harness.make_confirm_generator()),
        drain(harness.make_confirm_generator()),
    )

    assert len(resume_calls) == 1
    loser = out1 if len(out1) < len(out2) else out2
    assert any("already in progress" in f.lower() for f in loser)


@pytest.mark.asyncio
async def test_claim_released_on_pre_resume_failure(stream_confirm_harness):
    """If the winner fails BEFORE the graph starts streaming, the claim is
    released so a legit retry is not locked out for the full TTL."""
    harness = stream_confirm_harness
    harness.graph.astream_events = AsyncMock(side_effect=RuntimeError("boom"))

    _ = [f async for f in harness.make_confirm_generator()]
    # Retry must be able to claim again
    frames = [f async for f in harness.make_confirm_generator()]
    assert not any("already in progress" in f.lower() for f in frames)
```

The harness fixture: build it in this test file (copy the minimal fake graph +
`current_snapshot` construction from `test_streaming_resume.py`; the snapshot's
`config["configurable"]["checkpoint_id"]` must be a fixed value so both
generators derive the same claim key). Patch `src.core.caching`'s redis client
with `fakeredis.aioredis` if the suite already uses it, else an in-memory fake
implementing `set(nx=True, ex=...)` / `delete`.

**Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/agent/test_stream_confirm_claim.py -v` (use main-repo venv per repo convention)
Expected: FAIL — both generators resume (`len(resume_calls) == 2`), no "already in progress" frame exists.

### Task 1.3: Implement the claim

**Files:**
- Modify: `backend/src/api/agent/streaming.py` (confirm generator, after the ownership check ~`:1035`, around the existing `resume_ckpt_id` derivation `:1040-1052`)

**Step 3: Minimal implementation**

Insert after `resume_ckpt_id` is derived, before `config`/`resume_input` are built:

```python
        # CX1: atomically claim this interrupt before resuming. The job
        # confirm endpoint has a CAS (execute.py compare_and_set_status);
        # this SSE path had none — two concurrent confirms both issued
        # Command(resume=...) and a destructive tool could run twice.
        # Claim key is anchored to the interrupt checkpoint (same anchor as
        # the #1065 resume-dedup cmid): a nested confirm re-parks on a NEW
        # checkpoint, so its key rotates and the next confirm still works.
        confirm_claim_key = None
        if resume_ckpt_id:
            from src.core.caching import _acquire_lock, _release_lock, get_redis_client

            redis_client = await get_redis_client()  # match caching.py's accessor name
            if redis_client is not None:
                confirm_claim_key = (
                    f"hitl-confirm-claim:{request_body.thread_id}:{resume_ckpt_id}"
                )
                # TTL > the 300s stream timeout so a live winner can't lose
                # its claim mid-run; a crashed winner unblocks after TTL.
                if not await _acquire_lock(redis_client, confirm_claim_key, ttl=330):
                    yield await emitter.emit(
                        "error",
                        {"error": "Confirmation already in progress"},
                    )
                    return
            # ponytail: Redis down → no claim (single-worker in-memory CAS
            # like job_store._cas_in_memory is the upgrade if this bites).
```

And in the error path that runs when the resume fails **before any graph event
was emitted** (wrap the `graph.astream_events` startup — the existing `try` that
closes `confirm_event_iter` at `:1285` shows where the iterator lives): release
the claim so a retry isn't locked out:

```python
            if confirm_claim_key and not events_started:
                await _release_lock(redis_client, confirm_claim_key)
```

(`events_started = False` before the event loop; set `True` on first iteration.)

Notes for the implementer:
- Verify the actual redis accessor name in `backend/src/core/caching.py` (grep `def get_redis` / how `_acquire_lock` callers obtain `client`) — reuse it, do not build a new connection.
- Do NOT release the lock on success — the checkpoint advances, and a post-done retry already lands in the "no pending interrupt" path; TTL handles cleanup.
- `resume_ckpt_id is None` fallback: proceed unclaimed (matches the existing cmid fallback philosophy at `:1063-1080`) — log a warning.

**Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/agent/test_stream_confirm_claim.py tests/agent/test_streaming_resume.py -v`
Expected: PASS (new tests + no regression in existing confirm/resume tests).

**Step 5: Commit + push**

```bash
git add backend/src/api/agent/streaming.py backend/tests/agent/test_stream_confirm_claim.py
git commit -m "fix(agent): atomic claim on /stream/confirm — double-Approve can no longer resume a destructive tool twice (CX1)"
git push -u origin fix/hitl-stream-confirm-claim
```

### Task 1.4: Client-side double-click guard (belt)

**Files:**
- Modify: `frontend/src/hooks/chat/useChatStreaming.ts` — `handleConfirmation` (~`:948` area; grep `handleConfirmation` for the exact site)
- Test: extend the existing `useChatStreaming.confirmToolSteps` test file

**Step 1: failing test** — call `handleConfirmation` twice synchronously; assert `agentChatService.streamConfirm` (mock) called once.
**Step 2:** run, expect FAIL (called twice).
**Step 3:** guard with the existing `submitLockRef` idiom (reuse the ref pattern from `handleSubmit:784`, or a dedicated `confirmLockRef` reset in `finally`).

⚠️ Test-assert gotcha (wiki `nous-aui-full-retirement-mocked-setter-tests`): do not assert on `setMessages.mock.calls` order — filter to committed state (`Array.isArray` arg, exclude `isStreaming`/`pendingApproval` markers).

**Step 4:** `cd frontend && npx vitest run src/hooks/chat/__tests__ --silent` + `npm run type-check` → PASS.
**Step 5:** commit, push. Open PR → ledger `Status=pr, PR=#NNNN`.

### Task 1.5: PR + review

PR targets `develop` on GitHub (`Goodwiinz/rag`), body cites CX1 + failure scenario. Run `/code-review` per repo discipline. Regression tests are mandatory here (destructive-tool path).

---

## PR 2 — CX2: submit what the user sees (P1, frontend)

Branch: `fix/chat-submit-displayed-history` off `origin/develop`, own worktree.

### Task 2.1: Claim CX2 in ledger

### Task 2.2: VERIFY the torn-submit repro (plan-gate — do this before any fix)

**Step 1: Write the repro test (this is also the regression test):**

Test: `frontend/src/hooks/chat/__tests__/useChatStreaming.submitHistory.test.ts` (new; copy mock scaffolding from the existing useChatStreaming tests)

```typescript
// CX2: page renders selectDisplayedMessages(local, store) but handleSubmit
// POSTs from the local array. Store-populated + local-empty (the lazy-load
// window after a thread switch) must still send full history.
it('sends store-backed history when local messages are empty', async () => {
  // store: 2 committed messages for thread T; local `messages` prop: []
  // (mirror useChatSession: threads list seeds conversations with messages: [])
  const { handleSubmit } = renderStreamingHook({
    messages: [],                    // local
    displayedMessages: storeBacked2, // what the user sees
  });
  await handleSubmit('follow-up');
  const payload = streamMessageMock.mock.calls[0][0];
  expect(payload.messages).toHaveLength(3); // 2 history + new turn
});
```

**Step 2: Run it** — `npx vitest run src/hooks/chat/__tests__/useChatStreaming.submitHistory.test.ts`
Expected: FAIL with `payload.messages` length 1 → repro CONFIRMED. If it unexpectedly PASSES, stop: update ledger CX2 → `INVALID (repro failed)`, close the PR branch, done.

### Task 2.3: Fix — build history from `displayedMessages`

**Files:**
- Modify: `frontend/src/hooks/chat/useChatStreaming.ts` — hook already… **check the hook's input props (`:184,222`)**: `messages` is passed in from the page. `displayedMessages` already exists in `useChatSession` (`:129`) and is already destructured on the page (`page.tsx:115`).
- Modify: `frontend/app/(dashboard)/chat/page.tsx:~140` — pass `displayedMessages` into `useChatStreaming`.

**Step 3: Minimal implementation**

In `useChatStreaming` props add `displayedMessages: ChatPageMessage[]`; in `handleSubmit` (`:797`):

```typescript
      // CX2: build the turn from the RECONCILED view (local ∪ store) — the
      // local array is empty during the lazy-load window after a thread
      // switch, and submitting from it silently dropped the whole history.
      const history = displayedMessages;
      const newMessages = [...history, userMessage];
```

Keep the rollback path (`:859 setMessages(messages)`) writing the pre-submit **local** array — rolling back to `history` would materialize store messages into local state as a side effect; unnecessary.

Also mirror in `handleRegenerate`/`confirmMessages` (`:1091`) ONLY if they exhibit the same duality — grep `[...messages` in the file and check each site against its render source; don't blanket-replace.

**Step 4:** run the new test + full chat hook suite: `npx vitest run src/hooks/chat --silent && npm run type-check`
Expected: PASS. (Known pre-existing red in the broader `npm run validate` — verify via tsc + targeted vitest only, per repo memory.)

**Step 5: Commit, push, PR, ledger.**

Note for the PR body: this is display-parity, not a behavior change once `AGENT_SERVER_SIDE_HISTORY` Phase F ships (client will send only the newest turn) — CX2 is the correct interim fix because the full-history resend is load-bearing today (B2 Phase F/C TODO).

---

## PR 3 — CX5: thread-scope the live-stream UI (P2, frontend)

Branch: `fix/chat-streaming-thread-scope` off `origin/develop`, own worktree.

**Design decision (small on purpose):** keep the single-flight invariant — one stream at a time, composer blocked globally while any stream runs (the abort controller, RAF refs, and stop path in `useChatStreaming` all assume one run; making streams concurrent is NOT in scope). The bug is only that thread B *renders* A's live output. Fix = record which thread owns the live stream and gate the streaming-derived UI on it. This is exactly the upgrade path the existing `ponytail:` comment (`useChatStreaming.ts:376-378`) names.

### Task 3.1: Claim CX5 in ledger

### Task 3.2: failing test — store records the owning thread

Test: extend the chat store / useChatStreaming tests.

```typescript
it('stamps streamingThreadId for the turn thread and clears it on end', async () => {
  const { handleSubmit } = renderStreamingHook({ activeThreadId: 'T1', ... });
  const p = handleSubmit('hi');
  expect(useChatStore.getState().streamingThreadId).toBe('T1');
  await p;
  expect(useChatStore.getState().streamingThreadId).toBeNull();
});
```

Run → FAIL (`streamingThreadId` undefined).

### Task 3.3: implement

**Files:**
- Modify: `frontend/src/store/chatStore.ts` — add `streamingThreadId: string | null` (initial `null`) next to `isStreaming`.
- Modify: `frontend/src/hooks/chat/useChatStreaming.ts:406` — include `streamingThreadId: turnThreadId` in the streaming `setState`; add `streamingThreadId: null` to the `finally` cleanup (`:763-771`) and every early-exit `setState` that clears `isStreaming`.
- Modify the render gates — find every consumer of live streaming state and gate on `streamingThreadId === activeThreadId`:
  - `frontend/src/components/chat/ChatMessageList.tsx:333` (per Codex — typing/streaming indicator)
  - the ContextRail/citations panels reading `streamingCitations`/`streamingSteps` (grep `streamingContent\|streamingCitations\|streamingSteps\|isRetrievingRag` in `frontend/src` and audit each consumer; components that already render only inside the turn thread's placeholder need no change)

Composer: leave `storeIsStreaming` block as-is (global single-flight). Optional copy tweak "waiting for response in another thread…" — skip unless trivial.

### Task 3.4: run targeted tests + tsc → PASS → commit/push/PR/ledger

**Browser verify required before merge** (jsdom can't reproduce cross-thread render bleed — wiki lesson from #1096/#1098): send in thread A, switch to B mid-stream on the dev deploy; B must show no live tokens/citations; return to A shows the stream. Verify the deployed bundle hash flipped (`curl -s goodwiinz.tech/login | grep dpl_`) before concluding anything from the live site.

---

## PR 4 — CX8: sidebar thread pagination (P2, frontend only)

Branch: `fix/chat-sidebar-thread-pagination` off `origin/develop`, own worktree.

Backend needs nothing: `limit/offset` already exist (`threads.py:272-273`). Check `ThreadListResponse` for `total`/`has_more` (grep `class ThreadListResponse` in `backend/src/api/threads`) — it feeds the "has more" signal; if only `total`, derive `hasMore = offset + threads.length < total`.

### Task 4.1: Claim CX8 in ledger

### Task 4.2: failing test

`useChatSession` test: mock `listThreads` returning 50 threads + `total: 120`; assert hook exposes `hasMoreThreads === true` and `loadMoreThreads()` calls `listThreads(convId, { limit: 50, offset: 50 })` and **appends** (no dedupe loss, no replacement).

### Task 4.3: implement

**Files:**
- Modify: `frontend/src/hooks/chat/useChatSession.ts` — after each of the three `listThreads` sites (`:295,435,525`) record `threadsTotal`/`threadsOffset` state; add `loadMoreThreads` callback (fetch next offset, `setConversations(prev => [...prev, ...mapped])` minus ids already present); export `{ hasMoreThreads, loadMoreThreads }`.
- Modify: `frontend/src/components/chat/ChatSidebar.tsx` — render a "Show older threads" button at list end when `hasMoreThreads` (must not break the `React.memo` fix from #1083 — pass a stable callback, no inline arrow).
- Modify: `frontend/app/(dashboard)/chat/page.tsx` — thread the two new props.

Skipped: infinite scroll/virtualized sidebar — a button is enough at 50/page; add when someone actually pages 3+ times.

### Task 4.4: vitest + tsc → commit/push/PR/ledger

---

## Task 5 — CX6: bounded verify only (no fix yet)

Not a PR. In the CX2 worktree (read-only step):

1. `git grep -n "include_messages" origin/develop -- backend/src/services/threads/chat_service.py` and read `get_thread` — does it load ALL messages (unbounded `selectinload`/query)?
2. Count the consumers: `git grep -n "getThread(" origin/develop -- frontend/src` — warm start (`useChatSession.ts:437`) + URL cold load (`:242`).
3. Update ledger CX6: if unbounded → `open (verified: get_thread loads full transcript; fix = messages_limit Query param defaulting 100 + service slice, frontend already paginates older)`; if already capped → `INVALID`.

Decision pre-made: if a fix is warranted it is a `messages_limit: int = Query(100, ge=1, le=500)` param on `GET /threads/{thread_id}` slicing to the LAST N — frontend unchanged (`loadOlderMessages` already covers history). One small backend PR, TDD same shape as PR 1.

---

## Sequencing & constraints

| Order | PR | Finding | Sev | Depends on |
|-------|----|---------|-----|-----------|
| 1 | fix/hitl-stream-confirm-claim | CX1 | P0 | — |
| 2 | fix/chat-submit-displayed-history | CX2 | P1 | — (parallel-safe with PR 1: disjoint files) |
| 3 | fix/chat-streaming-thread-scope | CX5 | P2 | after PR 2 merges (both touch useChatStreaming.ts — avoid conflict) |
| 4 | fix/chat-sidebar-thread-pagination | CX8 | P2 | — (parallel-safe: useChatSession/ChatSidebar) |
| 5 | CX6 verify | CX6 | P2? | anytime |

- Worktrees: `git worktree add ../rag-cx1 -b fix/hitl-stream-confirm-claim origin/develop` (own worktree + push early — repo convention after the lost-commits incident).
- CX9 is NOT planned here: it is the standing "PR 4 cleanup" / B2 Phase F decision (see `~/.audit-ledgers/rag/chat-perf-persistence-2026-07-08.md` B2 row).
- Tests: backend `cd backend && .venv/bin/pytest tests/agent/ -v`; frontend `npx vitest run <targeted> && npm run type-check` (full `npm run validate` is pre-existing red — don't gate on it).
- Merge flow: `/nous-merge-loop` once PRs are green.
