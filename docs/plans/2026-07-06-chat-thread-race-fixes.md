# /chat Thread-Race & Scroll Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix three verified bugs on /chat: (1) mid-stream thread switch corrupts the visible transcript, (2) a stale HITL confirmation banner can act on / block the wrong thread, (3) "load older messages" jumps the scroll position.

**Architecture:** All three are frontend-only fixes. Bug 1 is fixed at the root in `useChatStreaming.ts` with a per-turn thread guard around every `setMessages` call in the async stream continuation (the store-side persistence is already thread-scoped, so no data is lost — we only stop clobbering the wrong view). Bug 2 is fixed by scoping the pending-confirmation UI gate to its owning thread in `page.tsx` plus a defensive guard in `handleConfirmation`. Bug 3 is fixed with scroll-offset compensation on prepend in both message-list components.

**Tech Stack:** Next.js 15 (app router), React 18, Zustand, react-window (`VariableSizeList`), vitest + @testing-library/react. Frontend lives in `frontend/`; run all npm/npx commands from `frontend/`.

**Worktree/branch:** Work in a fresh git worktree on a new branch cut from `develop` (e.g. `fix/chat-thread-race-scroll`). PRs target `develop`. Never `git pull/checkout/reset` in the main repo; stage files path-explicitly; `git fetch` before push.

**Verification baseline (repo gotchas):**
- `npm run validate` is red pre-existing (eslint config crash + agentChatStore timeouts). Verify with `npx tsc --noEmit` + targeted `npx vitest run <file>` instead.
- Never hardcode hex colors; no changes here need colors anyway.
- `IconButton` requires `aria-label` (not touched here, but if you add buttons).

---

## Background: the three bugs (read this before Task 1)

**Bug 1 — mid-stream thread switch corrupts the transcript (critical).**
`handleSubmit` in `frontend/src/hooks/chat/useChatStreaming.ts` closes over `newMessages` (snapshot of thread A's messages, line ~332) and calls `setMessages([...newMessages, ...])` in its stream callbacks/continuation (lines ~665, ~705, ~779, ~790, ~843). `setMessages` is the React state setter for *whatever thread is currently displayed* — it is not thread-scoped. The sidebar `onSelect` handlers (`frontend/app/(dashboard)/chat/page.tsx:842-848` and `:868-873`) and `startNewChat` (`:378-390`) switch threads immediately without aborting the stream. So: send in thread A → click thread B → A's completion overwrites B's just-loaded messages with A's stale array + A's answer.

The correct fix is a guard, not an abort: `activeConversationIdRef` (a `MutableRefObject<string | null>` passed into the hook, always updated synchronously on every thread switch — see page.tsx:844, :870, :380 and the hook's own line ~382) tells us the currently-viewed thread at any instant. Capture the turn's thread id after thread creation, and skip every local `setMessages` when the user has navigated away. Server-side persistence (backend rows in server-canonical mode; `addMessageToStore(currentThreadId, …)` otherwise) is already keyed by thread id and stays untouched, so the answer is still there when the user returns to thread A.

**Bug 2 — stale HITL confirmation acts on / blocks the wrong thread (important).**
The Approve/Deny banner (`page.tsx:1017-1107`) renders whenever `pendingConfirmation` is set, regardless of which thread is displayed. Worse, `pendingConfirmation` also feeds `isRunning`/`isSendDisabled` (`page.tsx:886-887`) and `ChatInput isLoading` (`:1115`), so a pending confirmation on thread A **disables the input on every thread**. And `handleConfirmation` (`useChatStreaming.ts:917-1057`) snapshots `confirmMessages = [...messages]` — the *currently displayed* thread's messages — so approving from thread B injects A's tool result into B's transcript.

Fix: derive `activeConfirmation` in page.tsx (the pending confirmation only when its `workspaceThreadId` matches the displayed thread) and use it for the banner + all gating; add a defensive thread-match guard at the top of `handleConfirmation`. `pendingConfirmation` state itself stays put, so returning to thread A re-shows the banner.

**Bug 3 — "load older" scroll jump (important).**
`loadOlderMessages` (`frontend/src/store/chat-store.ts:1110-1187`) prepends the older batch (`state.messages[threadId] = [...newMessages, ...existing]`). Neither list compensates: `ChatMessageList.tsx` (native scroll) never restores `scrollTop` after `scrollHeight` grows above the viewport, and `VirtualizedMessageList.tsx` never adjusts the scroll offset after indices shift (it also never calls `resetAfterIndex(0)` after a prepend, so react-window's cached offsets go stale). Both components already *detect* prepend correctly (length grew AND tail id unchanged — see the `isNewMessage` comments in both files); we reuse that detection.

---

### Task 1: Test for the thread-switch guard (Bug 1)

**Files:**
- Create: `frontend/src/hooks/__tests__/useChatStreaming.threadSwitch.test.tsx`

**Step 1: Write the failing test**

The existing `useChatStreaming.citations.test.ts` only tests exported pure functions — this test actually renders the hook with mocked services. The key trick: mock `agentChatService.streamMessage` so the test controls when the stream "completes", switch the thread (mutate `activeConversationIdRef.current` + swap the `messages`/`setMessages` the hook sees) while it's in flight, then resolve and assert the stale write was skipped.

```tsx
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';

// ---- Mocks ----
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

const streamMessageMock = vi.fn();
vi.mock('@/services/agentChatService', () => ({
  agentChatService: {
    streamMessage: (...args: unknown[]) => streamMessageMock(...args),
    streamConfirm: vi.fn(),
  },
}));

vi.mock('@/services/workspaceService', () => ({
  workspaceService: {
    createThread: vi.fn(),
    createMessage: vi.fn().mockResolvedValue({ id: 'db-msg-1' }),
    listMessages: vi.fn(),
  },
}));

import { useChatStreaming } from '@/hooks/chat/useChatStreaming';

function makeParams(overrides: Partial<Parameters<typeof useChatStreaming>[0]> = {}) {
  const activeConversationIdRef = { current: 'thread-A' as string | null };
  return {
    messages: [
      { role: 'user', content: 'earlier question', timestamp: 1 },
    ] as ChatPageMessage[],
    setMessages: vi.fn(),
    conversations: [],
    setConversations: vi.fn(),
    activeConversationId: 'thread-A',
    setActiveConversationId: vi.fn(),
    activeConversationIdRef,
    dbConversation: null, // no thread creation path; thread-A already exists
    isAuthenticated: true,
    setCurrentThread: vi.fn(),
    addMessageToStore: vi.fn(),
    enableRAG: false,
    ...overrides,
  };
}

describe('useChatStreaming thread-switch guard', () => {
  beforeEach(() => {
    streamMessageMock.mockReset();
  });

  it('skips the final setMessages when the user switched threads mid-stream', async () => {
    // streamMessage resolves only when the test says so, after emitting tokens.
    let finishStream!: () => void;
    streamMessageMock.mockImplementation(
      (_req: unknown, callbacks: { onToken: (t: string) => void; onDone: (p?: unknown) => void }) =>
        new Promise<void>((resolve) => {
          callbacks.onToken('hello from thread A');
          callbacks.onDone({});
          finishStream = resolve;
        })
    );

    const params = makeParams();
    const { result } = renderHook(() => useChatStreaming(params));

    let submitPromise!: Promise<void>;
    act(() => {
      submitPromise = result.current.handleSubmit('question for thread A');
    });

    // Simulate the sidebar switching to thread B while the stream is in flight
    // (page.tsx onSelect mutates the ref synchronously).
    params.activeConversationIdRef.current = 'thread-B';
    params.setMessages.mockClear(); // ignore the optimistic user-bubble write

    await act(async () => {
      finishStream();
      await submitPromise;
    });

    // The guard must prevent thread A's completion from writing into the
    // currently-displayed (thread B) message state.
    expect(params.setMessages).not.toHaveBeenCalled();
  });

  it('still commits the final message when the thread did NOT change', async () => {
    streamMessageMock.mockImplementation(
      (_req: unknown, callbacks: { onToken: (t: string) => void; onDone: (p?: unknown) => void }) => {
        callbacks.onToken('answer');
        callbacks.onDone({});
        return Promise.resolve();
      }
    );

    const params = makeParams();
    const { result } = renderHook(() => useChatStreaming(params));

    await act(async () => {
      await result.current.handleSubmit('question');
    });

    // Last setMessages call must contain the assistant answer.
    const calls = params.setMessages.mock.calls;
    const lastArg = calls[calls.length - 1][0] as ChatPageMessage[];
    expect(lastArg[lastArg.length - 1]).toMatchObject({
      role: 'assistant',
      content: 'answer',
    });
  });
});
```

Notes for the implementer:
- The hook also imports `useChatStore`, `useAgentActivityStore`, `useProjectStore` — these are real Zustand stores and work in vitest without mocking (they're plain JS). If any store import pulls in something jsdom-hostile, mock that module the same way.
- If `crypto.randomUUID` is missing in the test env, stub it: `vi.stubGlobal('crypto', { randomUUID: () => 'test-uuid' })`.
- Adjust mock shapes if the actual service signatures differ — read `frontend/src/services/agentChatService.ts` first.

**Step 2: Run the test to verify it fails**

Run (from `frontend/`): `npx vitest run src/hooks/__tests__/useChatStreaming.threadSwitch.test.tsx`
Expected: FAIL — first test fails because `setMessages` IS called (no guard exists yet). Second test should pass already (it pins current behavior).

**Step 3: Commit the failing test**

```bash
git add frontend/src/hooks/__tests__/useChatStreaming.threadSwitch.test.tsx
git commit -m "test(chat): pin thread-switch mid-stream clobbering (failing)"
```

---

### Task 2: Implement the thread-switch guard (Bug 1)

**Files:**
- Modify: `frontend/src/hooks/chat/useChatStreaming.ts`

**Step 1: Capture the turn's thread id and add the guard helper**

In `handleSubmit`, immediately after the thread-creation block ends (after line ~394, before `try {`), the ref now holds the thread this turn belongs to (for a newly created thread, line ~382 already set `activeConversationIdRef.current = newConv.id`). Add:

```ts
      // The thread this turn belongs to, snapshotted after thread creation.
      // Every local setMessages below must be gated on the user still viewing
      // this thread: setMessages writes to whatever thread is CURRENTLY
      // displayed, and the sidebar switches threads without aborting the
      // stream. Store/back-end persistence is thread-scoped already, so a
      // skipped local write is not lost — it reappears when the user returns.
      const turnThreadId = activeConversationIdRef.current;
      const isTurnDisplayed = () =>
        activeConversationIdRef.current === turnThreadId;
```

**Step 2: Gate every `setMessages` in the stream continuation**

Wrap each of these call sites with `if (isTurnDisplayed())`:

1. `onError` callback (~line 665): `setMessages([...newMessages, errorMsg]);` → `if (isTurnDisplayed()) setMessages([...newMessages, errorMsg]);`
2. Empty-content path (~line 705): same treatment for `setMessages([...newMessages, emptyResponseMessage]);`
3. Final commit (~line 779): `setMessages(finalMessages);` → `if (isTurnDisplayed()) setMessages(finalMessages);`
4. Server-canonical id reconcile (~line 790): `setMessages([...newMessages, finalAssistantMessage]);` → gate the `setMessages` only (keep the `finalAssistantMessage.id = …` assignment unconditional — the object is also referenced by `finalMessages` used in `setConversations`).
5. Catch block (~line 843): gate the `setMessages([...newMessages, { role: 'assistant', content: errorMessage, … }]);` call.

Do NOT gate:
- `setConversations` (~line 827) — it maps by `conv.id === currentConversationId`, already thread-scoped and correct.
- Any `useChatStore.setState({ isStreaming: false, … })` cleanup — global streaming flags must always be cleared.
- The persistence branch (`workspaceService.createMessage` + `addMessageToStore`) — thread-scoped by `currentThreadId`, must run regardless of what's displayed.

Known accepted limitation (do not fix here): the global streaming bubble/flags still render on whatever thread is displayed while a background turn streams. Add a `// ponytail:` comment on the guard noting per-thread streaming state as the upgrade path.

**Step 3: Run the test to verify it passes**

Run: `npx vitest run src/hooks/__tests__/useChatStreaming.threadSwitch.test.tsx`
Expected: PASS (both tests).

**Step 4: Type-check**

Run: `npx tsc --noEmit`
Expected: no NEW errors (compare against a pre-change run if unsure).

**Step 5: Commit**

```bash
git add frontend/src/hooks/chat/useChatStreaming.ts
git commit -m "fix(chat): gate stream-completion setMessages on the turn's thread"
```

---

### Task 3: Scope the HITL confirmation to its owning thread (Bug 2)

**Files:**
- Modify: `frontend/src/hooks/chat/useChatStreaming.ts` (helper + guard)
- Modify: `frontend/app/(dashboard)/chat/page.tsx` (derive `activeConfirmation`, swap usages)
- Create: `frontend/src/hooks/__tests__/confirmationScope.test.ts`

**Step 1: Write the failing test for the helper**

```ts
import { describe, expect, it } from 'vitest';
import { confirmationBelongsToThread } from '@/hooks/chat/useChatStreaming';
import type { PendingConfirmation } from '@/hooks/chat/useChatStreaming';

const pending = (workspaceThreadId: string): PendingConfirmation => ({
  threadId: 'agent-thread-1',
  workspaceThreadId,
  confirmation: {},
});

describe('confirmationBelongsToThread', () => {
  it('matches when the displayed thread owns the confirmation', () => {
    expect(confirmationBelongsToThread(pending('t-1'), 't-1')).toBe(true);
  });
  it('rejects a different displayed thread', () => {
    expect(confirmationBelongsToThread(pending('t-1'), 't-2')).toBe(false);
  });
  it('handles the new-chat (null thread) case', () => {
    expect(confirmationBelongsToThread(pending(''), null)).toBe(true);
    expect(confirmationBelongsToThread(pending('t-1'), null)).toBe(false);
  });
  it('rejects null confirmations', () => {
    expect(confirmationBelongsToThread(null, 't-1')).toBe(false);
  });
});
```

**Step 2: Run it to verify it fails**

Run: `npx vitest run src/hooks/__tests__/confirmationScope.test.ts`
Expected: FAIL — `confirmationBelongsToThread` is not exported.

**Step 3: Implement the helper + guard in the hook**

In `useChatStreaming.ts`, next to the `PendingConfirmation` interface (~line 95):

```ts
/**
 * A pending HITL confirmation may only be rendered/actioned on the thread it
 * belongs to — actioning it elsewhere injects the resumed turn's messages
 * into whatever thread happens to be displayed. workspaceThreadId is '' when
 * the turn started before any thread existed (new chat), which matches a
 * null displayed-thread id.
 */
export function confirmationBelongsToThread(
  pending: PendingConfirmation | null,
  displayedThreadId: string | null
): boolean {
  if (!pending) return false;
  return pending.workspaceThreadId === (displayedThreadId ?? '');
}
```

Then at the top of `handleConfirmation` (~line 918), after the `if (!pendingConfirmation) return;`:

```ts
      // Defense in depth — the page hides the banner on foreign threads, but
      // a stale click must never resume a confirmation against the wrong
      // thread's transcript.
      if (
        !confirmationBelongsToThread(
          pendingConfirmation,
          activeConversationIdRef.current
        )
      )
        return;
```

(`activeConversationIdRef` is already destructured in the hook. Add it to `handleConfirmation`'s dependency array if eslint asks — refs are stable so it's a no-op.)

**Step 4: Scope the page-level gating**

In `page.tsx`, right after the `useChatStreaming(...)` destructuring (search for `pendingConfirmation,` in the destructure), derive:

```ts
  // Only the thread that owns the pending confirmation shows the banner or
  // has its input locked — pendingConfirmation itself survives navigation so
  // returning to the owning thread re-shows it.
  const activeConfirmation = confirmationBelongsToThread(
    pendingConfirmation,
    activeConversationId
  )
    ? pendingConfirmation
    : null;
```

Import `confirmationBelongsToThread` from `@/hooks/chat/useChatStreaming`.

Replace these `pendingConfirmation` usages with `activeConfirmation`:
- `isRunning={isLoading || storeIsStreaming || !!pendingConfirmation}` (~line 886)
- `isSendDisabled={!!pendingConfirmation}` (~line 887)
- The banner condition `{pendingConfirmation && (` (~line 1017) and the `extractToolCall(pendingConfirmation.confirmation)` inside it (~line 1043)
- `isLoading={isLoading || storeIsStreaming || !!pendingConfirmation}` on `ChatInput` (~line 1115)

Grep for any other `pendingConfirmation` reads in page.tsx (e.g. a focus-management effect on `approveRef`) and switch render-gating ones to `activeConfirmation`; leave the raw value only where the code genuinely needs "a confirmation exists anywhere" (there likely is no such place).

**Step 5: Run tests + type-check**

Run: `npx vitest run src/hooks/__tests__/confirmationScope.test.ts && npx tsc --noEmit`
Expected: PASS, no new type errors.

**Step 6: Commit**

```bash
git add frontend/src/hooks/chat/useChatStreaming.ts "frontend/app/(dashboard)/chat/page.tsx" frontend/src/hooks/__tests__/confirmationScope.test.ts
git commit -m "fix(chat): scope HITL confirmation banner and input lock to owning thread"
```

---

### Task 4: Scroll compensation on prepend — native list (Bug 3a)

**Files:**
- Modify: `frontend/src/components/chat/ChatMessageList.tsx`
- Create: `frontend/src/components/chat/__tests__/ChatMessageList.prepend.test.tsx`

**Step 1: Write the failing test**

jsdom has no layout, so the test defines `scrollHeight` on the container manually and checks that `scrollTop` is adjusted by the delta after a prepend rerender.

```tsx
import { describe, expect, it, vi, beforeAll } from 'vitest';
import { render } from '@testing-library/react';
import { ChatMessageList } from '@/components/chat/ChatMessageList';
import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';

beforeAll(() => {
  // jsdom lacks these
  Element.prototype.scrollIntoView = vi.fn();
  if (!('ResizeObserver' in globalThis)) {
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      }
    );
  }
});

const msg = (id: string, role: 'user' | 'assistant'): ChatPageMessage => ({
  id,
  role,
  content: `content ${id}`,
  timestamp: 1,
});

const baseProps = {
  activeThreadId: 't-1',
  isLoading: false,
  storeIsStreaming: false,
  storeStreamingContent: '',
  streamingTimestamp: 0,
  onRegenerate: vi.fn(),
  onCitationClick: vi.fn(),
  hasMore: true,
  isLoadingOlder: false,
  onLoadOlder: vi.fn(),
};

describe('ChatMessageList prepend scroll compensation', () => {
  it('offsets scrollTop by the scrollHeight delta when older messages are prepended', () => {
    const initial = [msg('m3', 'user'), msg('m4', 'assistant')];
    const { container, rerender } = render(
      <ChatMessageList {...baseProps} messages={initial} />
    );

    const scroller = container.querySelector(
      '[aria-label="Conversation transcript"]'
    ) as HTMLElement;
    expect(scroller).toBeTruthy();

    // Simulate layout: current content is 1000px tall, user sits at 100px.
    let scrollHeight = 1000;
    Object.defineProperty(scroller, 'scrollHeight', {
      configurable: true,
      get: () => scrollHeight,
    });
    scroller.scrollTop = 100;

    // Trigger a rerender so the layout effect records the 1000px baseline
    // (the effect also runs on mount, but scrollHeight was 0 then).
    rerender(<ChatMessageList {...baseProps} messages={[...initial]} />);

    // Prepend two older messages; the DOM "grows" to 1600px.
    scrollHeight = 1600;
    rerender(
      <ChatMessageList
        {...baseProps}
        messages={[msg('m1', 'user'), msg('m2', 'assistant'), ...initial]}
      />
    );

    // 100 + (1600 - 1000) = 700: the messages the user was reading stay put.
    expect(scroller.scrollTop).toBe(700);
  });

  it('does not touch scrollTop on an appended message', () => {
    const initial = [msg('m1', 'user')];
    const { container, rerender } = render(
      <ChatMessageList {...baseProps} messages={initial} />
    );
    const scroller = container.querySelector(
      '[aria-label="Conversation transcript"]'
    ) as HTMLElement;
    let scrollHeight = 500;
    Object.defineProperty(scroller, 'scrollHeight', {
      configurable: true,
      get: () => scrollHeight,
    });
    scroller.scrollTop = 100;
    rerender(<ChatMessageList {...baseProps} messages={[...initial]} />);

    scrollHeight = 800;
    rerender(
      <ChatMessageList
        {...baseProps}
        messages={[...initial, msg('m2', 'assistant')]}
      />
    );
    expect(scroller.scrollTop).toBe(100); // append → auto-scroll handles it, not us
  });
});
```

**Step 2: Run it to verify it fails**

Run: `npx vitest run src/components/chat/__tests__/ChatMessageList.prepend.test.tsx`
Expected: FAIL — first test gets `scrollTop === 100` (no compensation exists).

**Step 3: Implement**

In `ChatMessageList.tsx`:

1. Add `useLayoutEffect` to the React import.
2. After the `prevLastIdRef` declaration (~line 80), add:

```ts
  const prevFirstIdRef = useRef<string | undefined>(messages[0]?.id);
  const prevScrollHeightRef = useRef(0);
```

3. After the `isNewMessage` computation (~line 90), add the compensation layout effect. It must run BEFORE the passive effect that updates `prevMessageCountRef`/`prevLastIdRef` (layout effects always do):

```ts
  // Prepending an older page grows the content above the viewport; without
  // compensation the messages the user is reading jump down by the added
  // height. Detect prepend (length grew, tail id unchanged, head id changed)
  // and restore the visual anchor by the scrollHeight delta. Layout effect so
  // the correction lands before paint — no flicker.
  useLayoutEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    const firstId = messages[0]?.id;
    const isPrepend =
      messages.length > prevMessageCountRef.current &&
      currentLastId === prevLastIdRef.current &&
      firstId !== prevFirstIdRef.current;
    if (isPrepend) {
      container.scrollTop +=
        container.scrollHeight - prevScrollHeightRef.current;
    }
    prevScrollHeightRef.current = container.scrollHeight;
    prevFirstIdRef.current = firstId;
  }, [messages, currentLastId]);
```

**Step 4: Run the test to verify it passes**

Run: `npx vitest run src/components/chat/__tests__/ChatMessageList.prepend.test.tsx`
Expected: PASS (both tests).

**Step 5: Commit**

```bash
git add frontend/src/components/chat/ChatMessageList.tsx frontend/src/components/chat/__tests__/ChatMessageList.prepend.test.tsx
git commit -m "fix(chat): preserve scroll anchor when older messages are prepended"
```

---

### Task 5: Scroll compensation on prepend — virtualized list (Bug 3b)

**Files:**
- Modify: `frontend/src/components/chat/VirtualizedMessageList.tsx`

**Step 1: Implement (test after — react-window in jsdom is fiddly; see Step 3)**

In `VirtualizedMessageList.tsx`:

1. Add `useLayoutEffect` to the React import.
2. Track the live scroll offset — extend `handleScroll` (~line 200):

```ts
  const lastScrollOffsetRef = useRef(0);
  const handleScroll = useCallback(
    ({ scrollOffset }: { scrollOffset: number }) => {
      lastScrollOffsetRef.current = scrollOffset;
      // ... existing body unchanged ...
    },
    [onLoadOlder, hasMore, isLoadingOlder, messages.length]
  );
```

3. After the `isNewMessage` block (~line 194), add:

```ts
  const prevFirstIdRef = useRef<string | undefined>(messages[0]?.id);
  // On prepend the indices shift by the added count: react-window's cached
  // offsets are stale (heights are id-keyed and survive, but offsets are
  // positional) and the current pixel offset now points at different rows.
  // Reset the offset cache and shift the scroll position by the estimated
  // height of the new rows so the visible messages stay anchored.
  // ponytail: unmeasured new rows use DEFAULT_ROW_HEIGHT, so the anchor can
  // be off by (actual - 120)px per row until measurement lands; store real
  // heights from the API response if this is ever noticeable.
  useLayoutEffect(() => {
    const firstId = messages[0]?.id;
    const prevCount = prevMessageCountRef.current;
    const isPrepend =
      messages.length > prevCount &&
      currentLastId === prevLastIdRef.current &&
      firstId !== prevFirstIdRef.current;
    if (isPrepend && listRef.current) {
      const added = messages.length - prevCount;
      listRef.current.resetAfterIndex(0);
      let delta = 0;
      for (let i = 0; i < added; i++) delta += getItemSize(i);
      listRef.current.scrollTo(lastScrollOffsetRef.current + delta);
    }
    prevFirstIdRef.current = firstId;
  }, [messages, currentLastId, getItemSize]);
```

**Step 2: Type-check**

Run: `npx tsc --noEmit`
Expected: no new errors. (`resetAfterIndex` and `scrollTo` are both on `VariableSizeList`.)

**Step 3: Test**

Attempt a jsdom test mirroring Task 4's pattern: render `VirtualizedMessageList` with 10 messages (ids `m10`…`m19`), fire a `scroll` event on react-window's outer element (the `.nous-scrollbar` div inside the container) to set `scrollTarget`, then rerender with 3 prepended messages and assert the outer element's `scrollTop` grew by `3 * 120` (DEFAULT_ROW_HEIGHT, since unmeasured). react-window drives `scrollTop` in jsdom, so this generally works; stub `ResizeObserver` as in Task 4.

If react-window's internals make this flaky after ~20 minutes of effort, STOP: delete the flaky test, and instead add a plain unit test for the delta math by extracting it:

```ts
export function prependScrollDelta(
  addedCount: number,
  getItemSize: (index: number) => number
): number {
  let delta = 0;
  for (let i = 0; i < addedCount; i++) delta += getItemSize(i);
  return delta;
}
```

…and call it from the layout effect. Test the pure function. Do not burn time fighting react-window in jsdom.

**Step 4: Run whatever test you landed + full targeted suite**

Run: `npx vitest run src/components/chat/ src/hooks/__tests__/useChatStreaming.threadSwitch.test.tsx src/hooks/__tests__/confirmationScope.test.ts`
Expected: PASS. Also confirm no pre-existing chat component tests broke: `npx vitest run src/components/chat/__tests__/`.

**Step 5: Commit**

```bash
git add frontend/src/components/chat/VirtualizedMessageList.tsx frontend/src/components/chat/__tests__/
git commit -m "fix(chat): anchor virtualized list scroll across older-message prepend"
```

---

### Task 6: Final verification + PR

**Step 1: Full targeted verification**

From `frontend/`:

```bash
npx tsc --noEmit
npx vitest run src/hooks/__tests__/ src/components/chat/__tests__/ src/store/__tests__/chat-store-streaming.test.ts
```

Expected: type-check clean (no new errors vs develop), all listed tests pass. Do NOT run `npm run validate` — it is red pre-existing (eslint config crash + agentChatStore timeouts); do not try to fix that here.

**Step 2: Push and open a PR**

```bash
git fetch origin
git push -u origin fix/chat-thread-race-scroll
```

Open a PR targeting `develop` titled `fix(chat): thread-switch transcript races + prepend scroll anchor`. Body: summarize the three bugs (use the Background section above), note the two accepted limitations (global streaming bubble still shows across threads — per-thread streaming state is the upgrade path; virtualized prepend anchor uses estimated heights until rows measure). End the body with:

```
🤖 Generated with [Claude Code](https://claude.com/claude-code)
```
