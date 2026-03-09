# Chat UI Remaining Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the 3 remaining issues from the chat UI/UX consistency deep review: AbortController for search cancellation, exit animations on AnimatePresence children, and functional sidebar search filtering.

**Architecture:** Thread `AbortSignal` through `searchService.search()` so the HALT button actually cancels in-flight HTTP requests. Add `exit` props to `motion.div` children inside `AnimatePresence` in both `/chat` and `/search`. Wire the sidebar search input to filter conversations by title.

**Tech Stack:** Next.js App Router, React, TypeScript, Axios (supports `signal` via `AxiosRequestConfig`), framer-motion `AnimatePresence`.

---

### Task 1: Add AbortController Support to Search Service and Search Page

**Problem:** The HALT button in `/search` calls `onStop={() => setIsLoading(false)}` which only hides the loading indicator. The HTTP request to `/search/hybrid` continues in the background, and when it resolves, it appends a stale assistant message to the conversation.

**Files:**

- Modify: `frontend/src/services/searchService.ts` (add optional `signal` param to `search()`)
- Modify: `frontend/app/(dashboard)/search/page.tsx` (create `AbortController`, pass signal, abort on stop)

**Step 1: Add `signal` parameter to `SearchService.search()`**

In `frontend/src/services/searchService.ts`, modify the `search` method signature to accept an optional `AbortSignal`:

```typescript
// Change line 129 from:
async search(request: SearchRequest): Promise<APIResponse<SearchResult>> {
// To:
async search(request: SearchRequest, signal?: AbortSignal): Promise<APIResponse<SearchResult>> {
```

Then pass `signal` to both `apiClient.post` calls inside the method:

```typescript
// Line ~154: primary search call — change from:
const response = (await apiClient.post(
  this.searchPrimaryPath,
  backendRequest
)) as { ... };
// To:
const response = (await apiClient.post(
  this.searchPrimaryPath,
  backendRequest,
  signal ? { signal } : undefined
)) as { ... };

// Line ~176: fallback search call — same pattern:
const fallbackResponse = (await apiClient.post(
  this.searchFallbackPath,
  { ...backendRequest, search_type: 'fulltext' },
  signal ? { signal } : undefined
)) as { ... };
```

**Step 2: Wire AbortController in search page**

In `frontend/app/(dashboard)/search/page.tsx`:

Add an `abortControllerRef` and update `runSearch` to create a new controller per request, and update `onStop` to abort it.

```typescript
// After the composerRef line (~34), add:
const abortControllerRef = useRef<AbortController | null>(null);

// Inside runSearch, before the try block (~134), add:
abortControllerRef.current?.abort();
const controller = new AbortController();
abortControllerRef.current = controller;

// Pass signal to searchService.search (~136):
const response = await searchService.search(request, controller.signal);

// In the catch block (~162), add abort detection before appending error message:
} catch (err: any) {
  if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') {
    return; // User cancelled — don't append error message
  }
  const msg = toErrorMessage(err);
  setMessages((prev) => [
    ...prev,
    {
      role: 'assistant',
      content: msg,
      timestamp: Date.now(),
    },
  ]);

// Update the onStop handler on TerminalChatComposer (~266):
// Change from:
onStop={() => setIsLoading(false)}
// To:
onStop={() => {
  abortControllerRef.current?.abort();
  setIsLoading(false);
}}
```

**Step 3: Run type-check to verify**

Run: `npm --prefix frontend run type-check`
Expected: 0 errors

**Step 4: Commit**

```bash
git add frontend/src/services/searchService.ts frontend/app/(dashboard)/search/page.tsx
git commit -m "fix(search): abort HTTP request when user clicks HALT"
```

---

### Task 2: Add Exit Animations to AnimatePresence Children

**Problem:** Both `/chat` and `/search` wrap message lists in `<AnimatePresence>` but the `motion.div` children have no `exit` prop. Without `exit`, `AnimatePresence` does nothing useful — elements just vanish. This matters when the streaming message disappears (it should fade out gracefully when streaming completes).

**Files:**

- Modify: `frontend/app/(dashboard)/chat/page.tsx` (add `exit` prop to both `motion.div` blocks)
- Modify: `frontend/app/(dashboard)/search/page.tsx` (wrap messages in `motion.div` with entry/exit)

**Step 1: Add exit animation to chat page motion.div children**

In `frontend/app/(dashboard)/chat/page.tsx`:

```tsx
// Line ~1985: the message map motion.div — add exit prop:
<motion.div
  key={message.id || `msg-${index}`}
  initial={{ opacity: 0, y: 20, scale: 0.98 }}
  animate={{ opacity: 1, y: 0, scale: 1 }}
  exit={{ opacity: 0, transition: { duration: 0.2 } }}
  transition={{
    duration: 0.4,
    delay: Math.min(index * 0.03, 0.3),
    ease: [0.25, 0.46, 0.45, 0.94],
  }}
>

// Line ~2020: the streaming message motion.div — add exit prop:
<motion.div
  key="streaming-message"
  initial={{ opacity: 0, y: 20, scale: 0.98 }}
  animate={{ opacity: 1, y: 0, scale: 1 }}
  exit={{ opacity: 0, y: -10, transition: { duration: 0.2 } }}
  transition={{ duration: 0.3 }}
>
```

**Step 2: Add motion.div wrappers with exit to search page**

In `frontend/app/(dashboard)/search/page.tsx`, the `TerminalChatBubble` components inside `AnimatePresence` are rendered directly (no `motion.div` wrapper). Wrap them:

```tsx
// Line ~226-240: change from:
{messages.map((message, idx) => (
  <TerminalChatBubble
    key={message.id || `search-msg-${idx}`}
    ...
  />
))}
// To:
{messages.map((message, idx) => (
  <motion.div
    key={message.id || `search-msg-${idx}`}
    initial={{ opacity: 0, y: 12 }}
    animate={{ opacity: 1, y: 0 }}
    exit={{ opacity: 0, transition: { duration: 0.2 } }}
    transition={{ duration: 0.3, delay: Math.min(idx * 0.03, 0.3) }}
  >
    <TerminalChatBubble
      message={message}
      index={idx}
      ...
    />
  </motion.div>
))}

// Line ~242-254: the loading bubble — wrap similarly:
{isLoading && (
  <motion.div
    key="search-loading-message"
    initial={{ opacity: 0, y: 12 }}
    animate={{ opacity: 1, y: 0 }}
    exit={{ opacity: 0, y: -10, transition: { duration: 0.2 } }}
    transition={{ duration: 0.3 }}
  >
    <TerminalChatBubble
      message={{
        role: 'assistant',
        content: '',
        timestamp: Date.now(),
      }}
      index={messages.length}
      isTyping={true}
      modelName="SEMANTIC-RAG"
    />
  </motion.div>
)}
```

Note: `motion` is already imported in search/page.tsx.

**Step 3: Run type-check to verify**

Run: `npm --prefix frontend run type-check`
Expected: 0 errors

**Step 4: Commit**

```bash
git add frontend/app/(dashboard)/chat/page.tsx frontend/app/(dashboard)/search/page.tsx
git commit -m "fix(chat): add exit animations to AnimatePresence children"
```

---

### Task 3: Wire Sidebar Search Input to Filter Conversations

**Problem:** The search input in `ChatSidebar.tsx` renders a text input with placeholder "Search Logs..." but has no `value`, `onChange`, or filtering logic. Users can type into it but nothing happens.

**Files:**

- Modify: `frontend/src/components/chat/ChatSidebar.tsx` (add search state and filter logic)

**Step 1: Add search state and filtering**

In `frontend/src/components/chat/ChatSidebar.tsx`:

```tsx
// Add useState import (line 1 area — check if already imported from react):
// Currently no react imports exist. Add:
import { useState } from 'react';

// Inside ChatSidebar function body, before the return:
const [searchQuery, setSearchQuery] = useState('');

const filteredConversations = searchQuery.trim()
  ? conversations.filter((conv) =>
      conv.title.toLowerCase().includes(searchQuery.toLowerCase())
    )
  : conversations;

// Update the <input> element (~line 60-65):
// Change from:
<input
  type="text"
  placeholder="Search Logs..."
  className="w-full bg-[var(--terminal-surface)] border border-[var(--terminal-border)] rounded py-1.5 pl-9 pr-3 text-xs text-[var(--terminal-text)] placeholder-[var(--terminal-text-dim)]/70 focus:outline-none focus:border-[var(--phosphor-green)]/30 transition-colors"
  style={{ fontFamily: "'JetBrains Mono', monospace" }}
/>
// To:
<input
  type="text"
  placeholder="Search Logs..."
  value={searchQuery}
  onChange={(e) => setSearchQuery(e.target.value)}
  className="w-full bg-[var(--terminal-surface)] border border-[var(--terminal-border)] rounded py-1.5 pl-9 pr-3 text-xs text-[var(--terminal-text)] placeholder-[var(--terminal-text-dim)]/70 focus:outline-none focus:border-[var(--phosphor-green)]/30 transition-colors"
  style={{ fontFamily: "'JetBrains Mono', monospace" }}
/>

// Update conversations.map to use filteredConversations (~line 101):
// Change from:
{conversations.map((conv) => {
// To:
{filteredConversations.map((conv) => {

// Update the count badge (~line 96):
// Change from:
{conversations.length}
// To:
{filteredConversations.length}
```

**Step 2: Run type-check to verify**

Run: `npm --prefix frontend run type-check`
Expected: 0 errors

**Step 3: Run all shared component tests**

Run: `npm --prefix frontend test -- --watch=false --runInBand src/components/chat/shared/__tests__/`
Expected: 9 tests pass

**Step 4: Commit**

```bash
git add frontend/src/components/chat/ChatSidebar.tsx
git commit -m "feat(chat): wire sidebar search input to filter conversations"
```

---

### Task 4: Final Verification

**Step 1: Run full test suite for chat components**

Run:

```bash
npm --prefix frontend test -- --watch=false --runInBand src/components/chat/shared/__tests__/
```

Expected: 9 tests, all PASS

**Step 2: Run type-check**

Run:

```bash
npm --prefix frontend run type-check
```

Expected: 0 errors

**Step 3: Run lint**

Run:

```bash
npm --prefix frontend run lint
```

Expected: No blocking errors (pre-existing warnings acceptable)

**Step 4: Manual verification checklist**

- [ ] `/search`: HALT button cancels the in-flight request (no stale message appears)
- [ ] `/search`: Loading bubble fades out smoothly when search completes
- [ ] `/chat`: Streaming message fades out when streaming finishes
- [ ] `/chat`: Messages animate in with entry animation
- [ ] Sidebar: Typing in "Search Logs..." filters conversation list by title
- [ ] Sidebar: Clearing search shows all conversations again
- [ ] Sidebar: Count badge reflects filtered count

## Skill References

- Use `@verification-before-completion` before reporting done.
