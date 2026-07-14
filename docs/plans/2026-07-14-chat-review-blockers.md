# Chat Review Blockers Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the three verified PR #1175 blockers without reintroducing stale thread state, redundant transcript loads, or inherited scroll position.

**Architecture:** Keep thread selection ownership at the existing synchronous `activeConversationIdRef` boundary. Reuse valid Zustand transcript pages instead of refreshing them implicitly, and scope transient scroll guards to `activeThreadId`. Preserve explicit cursor pagination and the existing message-load epoch for true cache misses.

**Tech Stack:** React 19, Next.js, Zustand, TypeScript, Vitest, Testing Library.

---

### Task 1: Protect newer selection from warm-start completion

**Files:**

- Modify: `frontend/src/hooks/chat/useChatSession.ts`
- Test: `frontend/src/hooks/__tests__/useChatSession.watchdog.test.tsx`

1. Add a deferred warm-start regression that selects a newly created thread before the persisted thread detail resolves.
2. Run the focused test and confirm it fails because the persisted thread replaces the newer selection.
3. Capture the active selection when initialization begins and only commit warm data if that selection still owns initialization.
4. Run the focused test and existing session lifecycle tests.

### Task 2: Reuse cached transcript pages

**Files:**

- Modify: `frontend/src/store/chat-store.ts`
- Test: `frontend/src/store/__tests__/chat-store-pagination.test.ts`

1. Add a regression showing `setCurrentThread` must not call `listMessages` when a valid cached page and pagination record exist.
2. Run the focused test and confirm the redundant request occurs.
3. Gate implicit initial loading on cache presence while preserving epoch cancellation and explicit `loadMessages` refresh behavior.
4. Run the store and session pagination tests.

### Task 3: Reset scroll guards on thread changes

**Files:**

- Modify: `frontend/src/components/chat/ChatMessageList.tsx`
- Test: `frontend/src/components/chat/__tests__/ChatMessageList.prepend.test.tsx`

1. Add a cached-switch regression that first places one thread in the scrolled-away state.
2. Run the focused test and confirm the next thread is not positioned.
3. Reset the scroll-away and older-page trigger state when `activeThreadId` changes.
4. Run message-list and virtualization regressions.

### Task 4: Verify and publish

**Files:**

- Modify: PR #1175 description only if validation details change.

1. Run the complete frontend test suite.
2. Run TypeScript, touched-file lint, and `git diff --check`.
3. Review the final diff against the three findings.
4. Commit, push, verify the PR head SHA, and report current checks.
