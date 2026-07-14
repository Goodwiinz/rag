# Rapid Thread-Switch Hydration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Keep the selected `/chat` transcript populated after rapid uncached thread switches and make the loading transition explicit without remounting a hydrated runtime on normal message updates.

**Architecture:** Extend the existing thread-scoped `ChatRuntimeProvider` key with a two-state hydration phase. The provider remounts once when a selected thread changes from empty/loading to populated, then keeps the same instance for streaming, appends, retries, and pagination. Preserve the current skeleton and add a semantic loading status.

**Tech Stack:** Next.js App Router, React, TypeScript, assistant-ui external-store runtime, Vitest, Testing Library, in-app browser verification.

---

### Task 1: Remount the runtime at the hydration boundary

**Files:**
- Modify: `frontend/src/components/chat/__tests__/ChatPage.threadSelect.test.tsx:150-172`
- Modify: `frontend/app/(dashboard)/chat/page.tsx:921-931`

**Step 1: Write the failing test**

Add a page-level lifecycle regression after the existing thread-change test:

```tsx
it('remounts an empty thread runtime once when its transcript hydrates', () => {
  const emptySession = {
    ...mockUseChatSession.mock.results[0]?.value,
    isLoadingMessages: true,
    displayedMessages: [],
  };
  mockUseChatSession.mockReturnValue(emptySession);

  const { rerender } = render(<ChatPage />);
  const emptyRuntime = screen.getByTestId('chat-runtime');

  mockUseChatSession.mockReturnValue({
    ...emptySession,
    isLoadingMessages: false,
    displayedMessages: [
      { role: 'assistant', content: 'Hydrated transcript', timestamp: 2 },
    ],
  });
  rerender(<ChatPage />);

  const hydratedRuntime = screen.getByTestId('chat-runtime');
  expect(hydratedRuntime).not.toBe(emptyRuntime);

  mockUseChatSession.mockReturnValue({
    ...emptySession,
    isLoadingMessages: false,
    displayedMessages: [
      { role: 'assistant', content: 'Hydrated transcript', timestamp: 2 },
      { role: 'user', content: 'Same thread append', timestamp: 3 },
    ],
  });
  rerender(<ChatPage />);

  expect(screen.getByTestId('chat-runtime')).toBe(hydratedRuntime);
});
```

**Step 2: Run the test to verify it fails**

Run:

```bash
corepack pnpm --dir frontend exec vitest run src/components/chat/__tests__/ChatPage.threadSelect.test.tsx
```

Expected: FAIL because the current key is only `activeThreadId`, so the empty and hydrated provider DOM nodes are identical.

**Step 3: Implement the minimal lifecycle key**

Immediately before the main page return, derive a stable phase:

```tsx
const runtimeHydrationPhase =
  displayedMessages.length > 0 ? 'hydrated' : 'empty';
```

Update the provider key:

```tsx
<ChatRuntimeProvider
  key={`${activeThreadId ?? 'new'}:${runtimeHydrationPhase}`}
```

Do not include message count, loading flags, or message IDs in the key. Those would remount the runtime during normal same-thread activity.

**Step 4: Run the focused lifecycle tests**

Run:

```bash
corepack pnpm --dir frontend exec vitest run src/components/chat/__tests__/ChatPage.threadSelect.test.tsx src/components/chat/__tests__/ChatMessageList.threadSwitch.test.tsx src/components/chat/aui/__tests__/AuiMessage.test.tsx src/components/chat/aui/__tests__/ChatRuntimeProvider.test.tsx
```

Expected: 4 files pass, including the new empty-to-hydrated remount and existing same-thread/thread-change invariants.

**Step 5: Commit**

```bash
git add 'frontend/app/(dashboard)/chat/page.tsx' frontend/src/components/chat/__tests__/ChatPage.threadSelect.test.tsx
git commit -m "fix(chat): hydrate runtime after rapid switches"
```

### Task 2: Make transcript loading an honest UI state

**Files:**
- Modify: `frontend/src/components/chat/__tests__/ChatPage.threadSelect.test.tsx`
- Modify: `frontend/app/(dashboard)/chat/page.tsx:60-88`

**Step 1: Write the failing accessibility test**

Add a test that renders an active loading session and asserts the loading state is visible and announced:

```tsx
it('announces the transcript loading state', () => {
  mockUseChatSession.mockReturnValue({
    ...mockUseChatSession.mock.results[0]?.value,
    isLoadingMessages: true,
    displayedMessages: [],
  });

  render(<ChatPage />);

  expect(
    screen.getByRole('status', { name: 'Loading conversation' })
  ).toBeInTheDocument();
  expect(screen.getByText('Loading conversation')).toBeVisible();
});
```

**Step 2: Run the test to verify it fails**

Run:

```bash
corepack pnpm --dir frontend exec vitest run src/components/chat/__tests__/ChatPage.threadSelect.test.tsx
```

Expected: FAIL because `TranscriptSkeleton` has `aria-busy` and an `aria-label`, but no `status` role or visible loading copy.

**Step 3: Implement the semantic loading status**

Update the skeleton root and add a restrained caption before the rows:

```tsx
<div
  className="mx-auto max-w-(--nous-chat-col) space-y-8 p-6"
  role="status"
  aria-live="polite"
  aria-busy="true"
  aria-label="Loading conversation"
>
  <p className="nous-caption text-(--nous-fg-3)">
    Loading conversation
  </p>
```

Keep the existing bubble skeletons and motion behavior unchanged.

**Step 4: Run the focused test**

Run:

```bash
corepack pnpm --dir frontend exec vitest run src/components/chat/__tests__/ChatPage.threadSelect.test.tsx
```

Expected: all tests in the file pass.

**Step 5: Commit**

```bash
git add 'frontend/app/(dashboard)/chat/page.tsx' frontend/src/components/chat/__tests__/ChatPage.threadSelect.test.tsx
git commit -m "polish(chat): clarify transcript loading"
```

### Task 3: Verify the final branch and live rapid-switch behavior

**Files:**
- Verify: `frontend/app/(dashboard)/chat/page.tsx`
- Verify: `frontend/src/components/chat/__tests__/ChatPage.threadSelect.test.tsx`

**Step 1: Run the full frontend suite**

Run:

```bash
corepack pnpm --dir frontend test -- --run
```

Expected: all frontend test files pass; existing intentional skips remain skips.

**Step 2: Run static verification**

Run:

```bash
corepack pnpm --dir frontend exec tsc --noEmit
corepack pnpm --dir frontend exec eslint 'app/(dashboard)/chat/page.tsx' 'src/components/chat/__tests__/ChatPage.threadSelect.test.tsx'
git diff --check
```

Expected: TypeScript and diff checks pass; lint reports zero errors, with only existing warnings if any.

**Step 3: Request independent review**

Review the complete diff from `6ff58a5e` through the implementation head. Resolve every concrete critical or important finding before publishing.

**Step 4: Push and wait for the Vercel preview**

Push `codex/fix-chat-first-send-race`, confirm PR #1175 points at the new head, and wait until the Vercel status is `success`.

**Step 5: Run authenticated browser acceptance**

On the exact PR preview revision:

1. Reload `/chat` so non-active transcripts are uncached.
2. Alternate two real sidebar threads at rapid cadence, ending on a known four-message thread.
3. Confirm there is no `pageerror` or global error screen.
4. Confirm URL, active sidebar row, and header identify the same final thread.
5. Confirm the transcript contains that thread's persisted messages without requiring a slow reselect.
6. Confirm a subsequent same-thread message update does not remount or blank the transcript.

Expected: the final transcript hydrates on the first rapid-switch sequence and remains visible.
