# Cloud Chat Store Ownership Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the Zustand chat store the single owner of cloud chat message lifecycle state after streaming begins, while keeping thread creation, model selection, and local-model behavior in the page.

**Architecture:** Keep the current conservative split: `page.tsx` still bootstraps threads and owns UI state, but the cloud streaming path stops rehydrating page-local messages from store after completion. Instead, the page renders a store-backed message view for cloud threads, while the store remains responsible for SSE state and authoritative persisted message reloads.

**Tech Stack:** Next.js App Router, React, Zustand, TypeScript, Jest, SSE fetch streaming

---

### Task 1: Extract a shared cloud message mapper

**Files:**
- Create: `frontend/src/components/chat/shared/cloudMessageView.ts`
- Test: `frontend/src/components/chat/shared/__tests__/cloudMessageView.test.ts`

**Step 1: Write the failing test**

```ts
import { mapStoreMessagesToChatMessages } from '../cloudMessageView';

describe('mapStoreMessagesToChatMessages', () => {
  it('maps persisted store messages into chat page message shape', () => {
    const result = mapStoreMessagesToChatMessages([
      {
        id: 'm-1',
        role: 'assistant',
        content: 'Answer',
        created_at: '2026-03-09T12:00:00Z',
        citations: [{ document_title: 'Doc 1', score: 0.8 }],
      } as any,
    ]);

    expect(result[0].role).toBe('assistant');
    expect(result[0].content).toBe('Answer');
    expect(result[0].citations?.[0].title).toBe('Doc 1');
  });
});
```

**Step 2: Run test to verify it fails**

Run: `npm test --workspace=frontend -- --runTestsByPath src/components/chat/shared/__tests__/cloudMessageView.test.ts`
Expected: FAIL because `cloudMessageView` does not exist yet

**Step 3: Write minimal implementation**

Create `cloudMessageView.ts` with:

```ts
import { MessageRole, type ChatMessage } from '@/types/workspace';
import { normalizeCitation } from '@/utils/citationNormalizer';

export interface ChatPageMessage {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  citations?: ReturnType<typeof normalizeCitation>[];
}

export function mapStoreMessagesToChatMessages(
  messages: ChatMessage[]
): ChatPageMessage[] {
  return messages.map((dbMsg) => ({
    id: dbMsg.id,
    role: dbMsg.role === MessageRole.USER ? 'user' : 'assistant',
    content: dbMsg.content,
    timestamp: new Date(dbMsg.created_at).getTime(),
    citations: dbMsg.citations?.map(normalizeCitation),
  }));
}
```

**Step 4: Run test to verify it passes**

Run: `npm test --workspace=frontend -- --runTestsByPath src/components/chat/shared/__tests__/cloudMessageView.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/components/chat/shared/cloudMessageView.ts frontend/src/components/chat/shared/__tests__/cloudMessageView.test.ts
git commit -m "refactor: extract cloud chat message mapper"
```

### Task 2: Add a failing regression test for cloud render handoff

**Files:**
- Modify: `frontend/src/components/chat/shared/__tests__/SearchPageChatMode.test.tsx` or create `frontend/src/components/chat/shared/__tests__/ChatCloudOwnership.test.tsx`
- Reference: `frontend/app/(dashboard)/chat/page.tsx`

**Step 1: Write the failing test**

Write a focused test that models:

- store has persisted messages for a thread
- cloud streaming has completed
- rendered message list uses store-backed persisted messages, not stale local copies

Prefer a narrow extracted helper if page-level mounting is too expensive.

Example target behavior:

```ts
expect(displayedMessages).toEqual(storeMappedMessages);
expect(displayedMessages).not.toEqual(localMessagesFallback);
```

**Step 2: Run test to verify it fails**

Run: `npm test --workspace=frontend -- --runTestsByPath src/components/chat/shared/__tests__/ChatCloudOwnership.test.tsx`
Expected: FAIL because the selector/handoff behavior is not implemented yet

**Step 3: Keep the failing test minimal**

If mounting the full page is fragile, extract a pure selection helper first and
test that instead of forcing a broad integration test.

**Step 4: Re-run to confirm stable RED**

Run: `npm test --workspace=frontend -- --runTestsByPath src/components/chat/shared/__tests__/ChatCloudOwnership.test.tsx`
Expected: FAIL for the intended reason

**Step 5: Commit**

```bash
git add frontend/src/components/chat/shared/__tests__/ChatCloudOwnership.test.tsx
git commit -m "test: add cloud chat ownership regression"
```

### Task 3: Extract cloud display-message selection from page

**Files:**
- Modify: `frontend/app/(dashboard)/chat/page.tsx`
- Modify: `frontend/src/components/chat/shared/cloudMessageView.ts`
- Test: `frontend/src/components/chat/shared/__tests__/ChatCloudOwnership.test.tsx`

**Step 1: Write minimal page helper usage**

Add a derived value in `page.tsx` similar to:

```ts
const activeStoreThreadMessages =
  currentThreadIdFromStore && storeMessages[currentThreadIdFromStore]
    ? mapStoreMessagesToChatMessages(storeMessages[currentThreadIdFromStore])
    : [];
```

Add a small selector for displayed messages:

```ts
const displayedMessages =
  currentModel?.isCloud && currentThreadIdFromStore
    ? activeStoreThreadMessages
    : messages;
```

**Step 2: Remove the page’s post-stream message remap**

Delete or reduce the cloud-only block in `handleSubmit()` that:

- reads `useChatStore.getState().messages[currentThreadId]`
- maps them into `Message[]`
- writes them back into local page state

Keep only the fallback for empty store messages if absolutely necessary.

**Step 3: Make rendering use `displayedMessages`**

Update the conversation list rendering to iterate over `displayedMessages`
instead of the page-local `messages` for cloud mode.

**Step 4: Run regression test**

Run: `npm test --workspace=frontend -- --runTestsByPath src/components/chat/shared/__tests__/ChatCloudOwnership.test.tsx src/components/chat/shared/__tests__/cloudMessageView.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/app/\(dashboard\)/chat/page.tsx frontend/src/components/chat/shared/cloudMessageView.ts frontend/src/components/chat/shared/__tests__/ChatCloudOwnership.test.tsx frontend/src/components/chat/shared/__tests__/cloudMessageView.test.ts
git commit -m "refactor: make store authoritative for cloud chat messages"
```

### Task 4: Preserve virtual streaming message behavior

**Files:**
- Modify: `frontend/app/(dashboard)/chat/page.tsx`
- Test: `frontend/src/components/chat/shared/__tests__/ChatCloudOwnership.test.tsx`

**Step 1: Write failing test for virtual bubble handoff**

Add a test proving:

- while `storeIsStreaming` is true, the virtual assistant message is rendered
- once persisted messages are available and streaming stops, only persisted messages remain

**Step 2: Run test to verify it fails**

Run: `npm test --workspace=frontend -- --runTestsByPath src/components/chat/shared/__tests__/ChatCloudOwnership.test.tsx`
Expected: FAIL because current handoff is not yet enforced cleanly

**Step 3: Adjust rendering logic minimally**

Use:

- `displayedMessages.length`
- `storeIsStreaming`

to ensure the virtual bubble is additive during streaming and removed after the
store-backed persisted list is present.

**Step 4: Run test to verify it passes**

Run: `npm test --workspace=frontend -- --runTestsByPath src/components/chat/shared/__tests__/ChatCloudOwnership.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/app/\(dashboard\)/chat/page.tsx frontend/src/components/chat/shared/__tests__/ChatCloudOwnership.test.tsx
git commit -m "fix: clean up cloud streaming handoff rendering"
```

### Task 5: Add regression coverage for first-message duplication boundary

**Files:**
- Modify: `frontend/src/components/chat/shared/__tests__/threadCreation.test.ts`
- Modify: `frontend/src/components/chat/shared/__tests__/ChatCloudOwnership.test.tsx`

**Step 1: Add assertion for new-thread cloud path**

Extend tests so the cloud send path proves:

- thread creation payload does not contain `initial_message`
- first persisted user message comes from the streaming endpoint path only

**Step 2: Run failing test if needed**

Run: `npm test --workspace=frontend -- --runTestsByPath src/components/chat/shared/__tests__/threadCreation.test.ts src/components/chat/shared/__tests__/ChatCloudOwnership.test.tsx`
Expected: Either RED for the new assertion or confirm existing green coverage is sufficient

**Step 3: Implement minimal test/helper updates**

Only add code if the current tests cannot express the boundary cleanly.

**Step 4: Run test to verify it passes**

Run: `npm test --workspace=frontend -- --runTestsByPath src/components/chat/shared/__tests__/threadCreation.test.ts src/components/chat/shared/__tests__/ChatCloudOwnership.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/components/chat/shared/__tests__/threadCreation.test.ts frontend/src/components/chat/shared/__tests__/ChatCloudOwnership.test.tsx
git commit -m "test: cover first cloud message ownership boundary"
```

### Task 6: Full targeted verification

**Files:**
- Verify only

**Step 1: Run targeted frontend test suite**

Run:

```bash
npm test --workspace=frontend -- --runTestsByPath \
  src/components/chat/shared/__tests__/cloudMessageView.test.ts \
  src/components/chat/shared/__tests__/ChatCloudOwnership.test.tsx \
  src/components/chat/shared/__tests__/threadCreation.test.ts \
  src/components/chat/shared/__tests__/TerminalChatBubble.test.tsx
```

Expected: PASS, zero failing suites

**Step 2: Run type check**

Run:

```bash
npm run type-check --workspace=frontend
```

Expected: exit code 0

**Step 3: Review diff for accidental local-model changes**

Run:

```bash
git diff -- frontend/app/\(dashboard\)/chat/page.tsx frontend/src/store/chat-store.ts frontend/src/components/chat/shared
```

Expected: only cloud-path ownership and test changes

**Step 4: Commit final verification-ready state**

```bash
git add frontend/app/\(dashboard\)/chat/page.tsx frontend/src/components/chat/shared
git commit -m "refactor: consolidate cloud chat message ownership in store"
```

**Step 5: Optional manual smoke check**

Run the app and verify:

- first GPT-4o message in a new thread appears once
- streaming response transitions cleanly to persisted messages
- citations still render correctly

---
