# Chat Sidebar Preview Loading Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Render the latest persisted transcript excerpt in every `/chat` sidebar row before selection while ensuring an uncached thread selection uses one paginated message-loading path.

**Architecture:** Extend the existing paginated thread-list contract with a bounded `last_message_preview` selected by a correlated SQL subquery, so the sidebar receives previews in the same request as thread metadata. Keep the Zustand paginated message store as the uncached-selection source of truth and remove the parallel full-detail transcript fetch from the selection effect.

**Tech Stack:** FastAPI, Pydantic, async SQLAlchemy, PostgreSQL, Next.js, React, Zustand, pytest, Vitest.

---

### Task 1: Add the thread-list preview contract

**Files:**
- Modify: `backend/src/schemas/chat.py`
- Modify: `backend/src/api/threads/workspaces.py`
- Test: `backend/tests/api/threads/test_thread_list_preview.py`

**Steps:**
1. Add a failing route-level test proving the standalone list query returns the newest non-deleted message as a bounded `last_message_preview` without loading every thread transcript.
2. Run the focused pytest and confirm it fails because the response contract/query lacks the field.
3. Add the optional response field and a reusable correlated preview expression used by both workspace-scoped and standalone list routes.
4. Pass each selected preview into `_thread_to_response` and rerun the focused pytest.

### Task 2: Render list previews before selection

**Files:**
- Modify: `frontend/src/types/workspace.ts`
- Modify: `frontend/src/hooks/chat/useChatSession.ts`
- Test: `frontend/src/hooks/__tests__/useChatSession.sidebarPagination.test.tsx`
- Delete: `frontend/src/components/chat/shared/threadPreviewHydration.ts`
- Delete: `frontend/src/components/chat/shared/__tests__/threadPreviewHydration.test.ts`

**Steps:**
1. Add failing hook tests showing first-page and appended threads map `last_message_preview` into `previewText` before any thread detail request.
2. Run the focused Vitest test and confirm the preview assertions fail.
3. Add the TypeScript contract field and map it in the shared thread-to-conversation adapter.
4. Remove the unused N+1 preview hydrator and its isolated test.
5. Rerun the focused sidebar/session tests.

### Task 3: Remove the duplicate uncached transcript fetch

**Files:**
- Modify: `frontend/src/hooks/chat/useChatSession.ts`
- Test: `frontend/src/hooks/__tests__/useChatSession.threadSwitchBleed.test.tsx`

**Steps:**
1. Replace the old cache-miss test with a failing test proving the hook waits for the active thread's Zustand page and never calls `getThread` for a list-known thread.
2. Run the test and confirm the current full-detail fallback is called.
3. Make the active-thread effect consume the store page only; retain immediate stale-transcript clearing and store epoch protection.
4. Rerun thread-switch, loading-scope, URL-sync, and pagination tests.

### Task 4: Verify and publish

**Steps:**
1. Run focused backend and frontend tests.
2. Run the full frontend suite, TypeScript, touched-file lint, backend formatting/lint checks, and `git diff --check`.
3. Commit and push the existing `codex/fix-chat-first-send-race` branch.
4. Wait for the Vercel deployment, reload the authenticated preview, and verify unopened sidebar rows already contain transcript excerpts and rapid switching still ends on a populated transcript.
5. Update PR #1175 with the contract, performance impact, and live acceptance result.
