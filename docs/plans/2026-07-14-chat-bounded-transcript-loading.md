# Bounded Chat Transcript Loading Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make every `/chat` restore and thread-selection path load only thread metadata plus a bounded newest-message page, while preserving correct URL ownership, cursor pagination, and scroll anchoring.

**Architecture:** `GET /api/v2/threads/{thread_id}` remains the metadata lookup, called explicitly with `include_messages=false`. The Zustand chat store remains the only transcript network loader through `GET /api/v2/threads/{thread_id}/messages`; React-local conversation state is a projection of its bounded pages. URL intent wins over persisted selection during initialization, and message cursors use a stable `(created_at, id)` ordering so equal timestamps cannot skip rows.

**Tech Stack:** Next.js 16, React 18, Zustand 5, TypeScript, Vitest/Testing Library, FastAPI, SQLAlchemy async, PostgreSQL, pytest.

---

## Audit findings this plan closes

1. **P1 — known-open:** `workspaceService.getThread()` omits `include_messages=false`, while the backend defaults to `true` and `ChatService.get_thread()` eagerly loads every message, citation, attachment, and related document. Warm restore and uncached URL restore therefore remain O(thread size).
2. **P1 — new:** initialization does not prioritize `?thread=` when that thread is outside the first 50 sidebar rows. Cold initialization first selects and loads the newest unrelated thread; warm initialization first loads the persisted thread. Only after initialization does the URL effect fetch the requested thread.
3. **P2 — new:** warm/URL detail paths put a full transcript in React-local conversation state but bypass the store's `messages` and `messagePagination` records. Revisiting that thread starts a bounded store load alongside the fuller local cache, so the rendered transcript and `hasMore` state can describe different datasets.
4. **P2 — new:** `before_id` pagination filters only `created_at < cursor.created_at` and orders only by `created_at`. Two rows with the same timestamp straddle the cursor ambiguously; rows tied with the boundary can be skipped permanently.

## Non-goals

- Do not redesign streaming, HITL confirmation, or server-canonical persistence.
- Do not remove the React-local `messages` projection in this PR.
- Do not change the public backend default for `include_messages`; make the frontend contract explicit to avoid an unreviewed API compatibility break.
- Do not change the 50-message initial page or 100-message older-page sizes.

### Task 1: Add an explicit metadata-only frontend thread-detail contract

**Files:**

- Create: `frontend/src/services/__tests__/workspaceService.threadDetail.test.ts`
- Modify: `frontend/src/services/workspaceService.ts:150-152`

**Step 1: Write the failing service test**

Mock `api.get`, call `workspaceService.getThread('thread-1', { includeMessages: false })`, and pin the request URL:

```ts
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "@/services/api-client";
import { workspaceService } from "@/services/workspaceService";

vi.mock("@/services/api-client", () => ({
  api: { get: vi.fn() },
}));

describe("workspaceService.getThread", () => {
  beforeEach(() => vi.clearAllMocks());

  it("can request metadata without transcript rows", async () => {
    vi.mocked(api.get).mockResolvedValue({ id: "thread-1", messages: [] });

    await workspaceService.getThread("thread-1", { includeMessages: false });

    expect(api.get).toHaveBeenCalledWith(
      "/api/v2/threads/thread-1?include_messages=false",
    );
  });
});
```

**Step 2: Run the test and verify RED**

Run:

```bash
corepack pnpm --dir frontend exec vitest run src/services/__tests__/workspaceService.threadDetail.test.ts
```

Expected: FAIL because `getThread` does not accept the option and the current request is `/api/v2/threads/thread-1`.

**Step 3: Add the explicit option while preserving existing callers until they migrate**

```ts
async getThread(
  threadId: string,
  options: { includeMessages?: boolean } = {}
): Promise<ThreadDetail> {
  const params = new URLSearchParams({
    include_messages: String(options.includeMessages ?? true),
  });
  return api.get<ThreadDetail>(
    `${API_PREFIX}/threads/${threadId}?${params.toString()}`
  );
}
```

Add a second assertion that `{ includeMessages: true }` produces `include_messages=true`. Tasks 3 and 4 migrate both `/chat` callers to explicit `false`; keeping the service default compatible avoids an intermediate commit that silently empties warm transcripts before the store migration lands.

**Step 4: Run the service test and verify GREEN**

Run the command from Step 2.

Expected: 2 tests PASS.

**Step 5: Commit**

```bash
git add frontend/src/services/workspaceService.ts frontend/src/services/__tests__/workspaceService.threadDetail.test.ts
git commit -m "feat(chat): support metadata-only thread details"
```

### Task 2: Make URL selection authoritative during initialization

**Files:**

- Create: `frontend/src/hooks/__tests__/useChatSession.boundedRestore.test.tsx`
- Modify: `frontend/src/hooks/chat/useChatSession.ts:397-429`
- Modify: `frontend/src/hooks/chat/useChatSession.ts:526-552`

**Step 1: Write failing cold-restore tests**

In an authenticated hook harness, return a first sidebar page containing `thread-newest` while `useSearchParams()` returns `thread-old`. Assert:

```ts
expect(chatStoreMocks.setCurrentThread).not.toHaveBeenCalledWith(
  "thread-newest",
);
expect(workspaceMocks.getThread).toHaveBeenCalledWith("thread-old", {
  includeMessages: false,
});
```

Add the empty-sidebar variant: `listThreads()` returns `threads: []`, but the URL target still triggers its metadata lookup after initialization.

**Step 2: Run the tests and verify RED**

```bash
corepack pnpm --dir frontend exec vitest run src/hooks/__tests__/useChatSession.boundedRestore.test.tsx
```

Expected: the first test shows `thread-newest` was selected first; the empty-sidebar test never calls `getThread` because the URL effect is gated by `conversations.length === 0`.

**Step 3: Stop selecting a fallback when an unresolved URL target exists**

Restructure `loadThreadsFromDb()`:

```ts
if (isNewChat && !threadFromUrl) {
  // existing new-chat reset
} else if (threadFromUrl) {
  const urlConversation = uiConversations.find((c) => c.id === threadFromUrl);
  if (urlConversation) {
    setActiveConversationId(urlConversation.id);
    activeConversationIdRef.current = urlConversation.id;
    setMessages([]);
    setCurrentThread(urlConversation.id);
  } else {
    // Leave selection empty. The URL metadata effect owns this target.
    setActiveConversationId(null);
    activeConversationIdRef.current = null;
    setMessages([]);
    setCurrentThread(null);
  }
} else if (uiConversations.length > 0) {
  const selectedConversation = uiConversations[0];
  setActiveConversationId(selectedConversation.id);
  activeConversationIdRef.current = selectedConversation.id;
  setMessages(selectedConversation.messages);
  setCurrentThread(selectedConversation.id);
}
```

Change the URL effect's initial guard from:

```ts
if (conversationsRef.current.length === 0 || isInitializing) return;
```

to:

```ts
if (isInitializing) return;
```

**Step 4: Make warm restore choose the URL before persisted state**

```ts
const requestedThreadId = searchParamsRef.current.get("thread");
const restoreThreadId = isNewChat
  ? null
  : (requestedThreadId ?? useChatStore.getState().currentThreadId);
```

Use `restoreThreadId` everywhere the warm path currently uses `persistedThreadId`.
Warm initialization is the sole owner while `isInitializing` is true: if the
URL target is outside the sidebar page, this path performs exactly one
metadata-only lookup and one bounded store load before the URL effect can run.
After warm state commits, the URL effect sees the already-active conversation
and performs no second request.

**Step 5: Run the focused hook tests and verify GREEN**

```bash
corepack pnpm --dir frontend exec vitest run \
  src/hooks/__tests__/useChatSession.boundedRestore.test.tsx \
  src/hooks/__tests__/useChatSession.urlSync.test.tsx
```

Expected: the URL target is the only selected target, including when the first sidebar page is empty.

**Step 6: Commit**

```bash
git add frontend/src/hooks/chat/useChatSession.ts frontend/src/hooks/__tests__/useChatSession.boundedRestore.test.tsx
git commit -m "fix(chat): prioritize URL thread during restore"
```

### Task 3: Route warm restore through the bounded store loader

**Files:**

- Modify: `frontend/src/hooks/chat/useChatSession.ts:545-617`
- Modify: `frontend/src/hooks/__tests__/useChatSession.boundedRestore.test.tsx`
- Modify: `frontend/src/hooks/__tests__/useChatSession.watchdog.test.tsx:99-172`
- Modify: `frontend/src/components/chat/shared/threadConversationState.ts:1-52`
- Modify: `frontend/src/components/chat/shared/__tests__/threadConversationState.test.ts`

**Step 1: Add a failing bounded-warm test**

Seed a persisted thread with `message_count: 1000`. Make `listThreads()` include that thread, and mock the store's `loadMessages()` to seed only 50 rows plus pagination. Assert:

```ts
expect(workspaceMocks.getThread).not.toHaveBeenCalled();
expect(chatStoreMocks.loadMessages).toHaveBeenCalledWith("thread-old");
expect(result.current.displayedMessages).toHaveLength(50);
expect(result.current.messagePagination?.["thread-old"]).toMatchObject({
  hasMore: true,
  loadedCount: 50,
});
```

Also assert the late warm-start race still leaves a newer first-send selection untouched.

**Step 2: Run the bounded-warm and watchdog tests and verify RED**

```bash
corepack pnpm --dir frontend exec vitest run \
  src/hooks/__tests__/useChatSession.boundedRestore.test.tsx \
  src/hooks/__tests__/useChatSession.watchdog.test.tsx
```

Expected: current warm restore calls `getThread()` and maps its entire `messages` array.

**Step 3: Start the canonical message-page load in parallel**

For a warm candidate, replace the full-detail promise with the store action:

```ts
const warmDataPromise = Promise.all([
  workspaceService.listThreads(persistedConvId, {
    page: 1,
    limit: THREADS_PAGE_SIZE,
  }),
  useChatStore.getState().loadMessages(restoreThreadId),
]).catch(() => null);
```

After the response arrives, read the bounded page from the store:

```ts
const page = useChatStore.getState().messages[restoreThreadId] ?? [];
const restoredMessages = mapStoreMessagesToChatMessages(page);
```

Do not read or map `threadDetail.messages` anywhere in initialization.

**Step 4: Resolve metadata only when the target is outside the sidebar page**

```ts
let restoreThread = threadListResponse.threads.find(
  (thread) => thread.id === restoreThreadId,
);
if (!restoreThread) {
  restoreThread = await workspaceService.getThread(restoreThreadId, {
    includeMessages: false,
  });
}
```

Re-check `activeConversationIdRef.current === selectionAtInitializationStart` after this fallback lookup before applying state.

Build conversation state from metadata and `restoredMessages`, then call `setCurrentThread(restoreThreadId)`. Because the store page already exists, this is a cache hit and must not refetch.

**Step 5: Generalize the conversation upsert helper to metadata plus an explicit bounded page**

Replace its implicit `thread.messages.map(...)` contract with:

```ts
export function upsertConversationFromThread<T extends ConversationStateItem>(
  conversations: T[],
  thread: Thread,
  messages: ConversationStateMessage[] = [],
): T[] {
  const nextConversation = {
    id: thread.id,
    title: thread.title || "New Chat",
    messages,
    createdAt: new Date(thread.created_at).getTime(),
    updatedAt: new Date(thread.updated_at).getTime(),
    threadId: thread.id,
    conversationId: thread.conversation_id,
    // Store-backed pages are ascending for display, so the final row is newest.
    previewText:
      messages[messages.length - 1]?.content ??
      thread.last_message_preview ??
      thread.summary ??
      undefined,
    messageCount: thread.message_count,
  } as T;
  // retain the existing replace-or-prepend logic
}
```

**Step 6: Run tests and verify GREEN**

Run the command from Step 2 plus:

```bash
corepack pnpm --dir frontend exec vitest run \
  src/components/chat/shared/__tests__/threadConversationState.test.ts \
  src/store/__tests__/chat-store-pagination.test.ts
```

Expected: all tests PASS and warm restore renders at most 50 rows.

**Step 7: Commit**

```bash
git add \
  frontend/src/hooks/chat/useChatSession.ts \
  frontend/src/hooks/__tests__/useChatSession.boundedRestore.test.tsx \
  frontend/src/hooks/__tests__/useChatSession.watchdog.test.tsx \
  frontend/src/components/chat/shared/threadConversationState.ts \
  frontend/src/components/chat/shared/__tests__/threadConversationState.test.ts
git commit -m "fix(chat): bound warm transcript restoration"
```

### Task 4: Route uncached URL restoration through metadata plus store pagination

**Files:**

- Modify: `frontend/src/hooks/chat/useChatSession.ts:283-361`
- Modify: `frontend/src/hooks/__tests__/useChatSession.urlSync.test.tsx:139-188`
- Modify: `frontend/src/hooks/__tests__/useChatSession.boundedRestore.test.tsx`

**Step 1: Write the failing URL-detail test**

Resolve `getThread()` with metadata whose legacy `messages` field deliberately contains 1,000 rows. Assert the hook:

```ts
expect(workspaceMocks.getThread).toHaveBeenCalledWith("thread-A", {
  includeMessages: false,
});
expect(chatStoreMocks.setCurrentThread).toHaveBeenCalledWith("thread-A");
expect(result.current.messages).toEqual([]);
```

Then seed a 50-row store page and assert exactly those 50 become displayed.

**Step 2: Run the test and verify RED**

```bash
corepack pnpm --dir frontend exec vitest run \
  src/hooks/__tests__/useChatSession.urlSync.test.tsx \
  src/hooks/__tests__/useChatSession.boundedRestore.test.tsx
```

Expected: current code calls `getThread('thread-A')`, maps `threadDetail.messages`, and mutates `currentThreadId` directly.

**Step 3: Apply metadata, then select through the store action**

```ts
const thread = await workspaceService.getThread(threadFromUrl, {
  includeMessages: false,
});
if (
  cancelled ||
  activeConversationIdRef.current !== activeThreadAtRequestStart
) {
  return;
}

setConversations((previous) =>
  upsertConversationFromThread(previous, thread, []),
);
setActiveConversationId(thread.id);
activeConversationIdRef.current = thread.id;
setMessages([]);
setCurrentThread(thread.id);
```

Delete the direct `useChatStore.setState({ currentThreadId: ... })` path. This ensures the message-load epoch, loading flags, bounded page, and pagination record are all established by one action.

**Step 4: Preserve stale-response ownership**

Keep the existing `cancelled` flag and `activeThreadAtRequestStart` comparison. Extend the test so a sidebar selection to B occurs while metadata for A is pending; resolving A must neither select A nor call `setCurrentThread('thread-A')`.

**Step 5: Run tests and verify GREEN**

Run the command from Step 2.

Expected: URL restoration fetches metadata only, then exactly one bounded message page via the store.

**Step 6: Commit**

```bash
git add frontend/src/hooks/chat/useChatSession.ts frontend/src/hooks/__tests__/useChatSession.urlSync.test.tsx frontend/src/hooks/__tests__/useChatSession.boundedRestore.test.tsx
git commit -m "fix(chat): paginate uncached URL restoration"
```

### Task 5: Make message cursors total-order safe

**Files:**

- Modify: `backend/tests/api/threads/test_messages_order_param.py:17-105`
- Modify: `backend/src/services/threads/chat_service.py:1118-1157`

**Step 1: Write the equal-timestamp regression test**

Seed three messages in one thread with the same `created_at` and deterministic UUIDs. Fetch a newest-first first page of two, then fetch before the second row:

```py
async def test_before_id_does_not_skip_equal_timestamp_rows(
    db_session, thread_factory, user_factory
):
    user = await user_factory()
    thread = await thread_factory(user=user)
    timestamp = datetime.utcnow()
    rows = []
    for value in (1, 2, 3):
        message = ChatMessage(
            id=UUID(int=value),
            thread_id=thread.id,
            user_id=user.id,
            role=MessageRole.USER,
            content=f"msg-{value}",
            created_at=timestamp,
            updated_at=timestamp,
        )
        db_session.add(message)
        rows.append(message)
    await db_session.commit()

    service = ChatService(db_session)
    first, _ = await service.list_messages(
        thread.id, user.id, limit=2, order="desc"
    )
    second, _ = await service.list_messages(
        thread.id, user.id, limit=2, before_id=first[-1].id, order="desc"
    )

    assert [row.id for row in first + second] == [
        UUID(int=3), UUID(int=2), UUID(int=1)
    ]
```

Register the inserted IDs with the existing cleanup fixture conventions.

**Step 2: Run the test and verify RED**

```bash
pytest backend/tests/api/threads/test_messages_order_param.py \
  -c backend/pytest.ini -q
```

Expected: the second page is empty because the current condition excludes every row tied on `created_at`.

**Step 3: Add the UUID tie-breaker to filtering and ordering**

```py
if before_msg:
    base_conditions.append(
        or_(
            ChatMessage.created_at < before_msg.created_at,
            and_(
                ChatMessage.created_at == before_msg.created_at,
                ChatMessage.id < before_msg.id,
            ),
        )
    )

if order == "asc":
    ordering = (ChatMessage.created_at.asc(), ChatMessage.id.asc())
else:
    ordering = (ChatMessage.created_at.desc(), ChatMessage.id.desc())

stmt = (
    select(ChatMessage)
    # existing options and conditions
    .order_by(*ordering)
    .offset(offset)
    .limit(limit)
)
```

The cursor still means “strictly older”; the ID only provides a stable order among equal timestamps.

**Step 4: Run the backend pagination tests and verify GREEN**

```bash
pytest \
  backend/tests/api/threads/test_messages_order_param.py \
  backend/tests/api/threads/test_messages_before_id_scoping.py \
  -c backend/pytest.ini -q
```

Expected: equal timestamps paginate without gaps; existing ordering and cross-thread cursor scoping remain green.

**Step 5: Commit**

```bash
git add backend/src/services/threads/chat_service.py backend/tests/api/threads/test_messages_order_param.py
git commit -m "fix(chat): stabilize message cursor ordering"
```

### Task 6: Verify the complete loading contract

**Files:**

- Verify only; no production edits expected.

**Step 1: Run the focused frontend regression set**

```bash
corepack pnpm --dir frontend exec vitest run \
  src/services/__tests__/workspaceService.threadDetail.test.ts \
  src/hooks/__tests__/useChatSession.boundedRestore.test.tsx \
  src/hooks/__tests__/useChatSession.urlSync.test.tsx \
  src/hooks/__tests__/useChatSession.watchdog.test.tsx \
  src/hooks/__tests__/useChatSession.threadSwitchBleed.test.tsx \
  src/store/__tests__/chat-store-pagination.test.ts \
  src/components/chat/__tests__/ChatMessageList.prepend.test.tsx \
  src/components/chat/__tests__/VirtualizedMessageList.pagination.test.tsx
```

Expected: PASS.

**Step 2: Mutation-check the ownership guards**

Temporarily neutralize each guard separately and prove its test fails:

- warm `selectionAtInitializationStart` comparison;
- URL `activeThreadAtRequestStart` comparison;
- store `messageLoadEpoch` comparison.

Restore each guard immediately. Do not commit mutations.

**Step 3: Run static and broad frontend verification**

```bash
corepack pnpm --dir frontend exec tsc --noEmit
corepack pnpm --dir frontend exec eslint \
  src/services/workspaceService.ts \
  src/hooks/chat/useChatSession.ts \
  src/components/chat/shared/threadConversationState.ts
corepack pnpm --dir frontend exec vitest run
```

Expected: TypeScript PASS, ESLint 0 errors, full frontend suite PASS.

**Step 4: Run backend verification**

```bash
ruff check \
  backend/src/services/threads/chat_service.py \
  backend/tests/api/threads/test_messages_order_param.py
black --check --line-length 88 \
  backend/src/services/threads/chat_service.py \
  backend/tests/api/threads/test_messages_order_param.py
isort --check-only --line-length 88 \
  backend/src/services/threads/chat_service.py \
  backend/tests/api/threads/test_messages_order_param.py
mypy backend/src --ignore-missing-imports
pytest \
  backend/tests/api/threads/test_messages_order_param.py \
  backend/tests/api/threads/test_messages_before_id_scoping.py \
  backend/tests/api/threads/test_thread_list_preview.py \
  -c backend/pytest.ini -q
```

Expected: Ruff, Black, isort, and the pagination tests PASS. The repository's
MyPy lane is currently non-blocking and has pre-existing errors; record its
result and require no new error on the changed cursor lines. If this worktree
still lacks pytest, run this in the repo's provisioned backend environment or
CI; do not claim backend verification from static inspection alone.

**Step 5: Perform the separate authenticated browser gate**

Against the exact deployed commit:

1. Seed or identify a thread with at least 1,000 messages and another thread outside the first 50 sidebar rows.
2. Open `/chat?thread=<large-thread>` with a different persisted thread in local storage.
3. In DevTools Network, verify no thread-detail request returns transcript rows and every detail request contains `include_messages=false`.
4. Verify the initial message request is `limit=50&order=desc` and only those 50 rows render.
5. Load older once; verify `limit=100&order=desc&before_id=<oldest-visible-id>` and stable viewport anchoring.
6. Rapidly alternate two threads 24 times at roughly 45 ms; assert no `pageerror`, no wrong transcript, and no full-detail transcript request.
7. Reload the direct URL and confirm the requested thread—not the persisted fallback—owns the first transcript displayed.

Record the deployment hash and browser result in the PR description; keep this release gate separate from unit-test claims.

**Step 6: Run final diff review**

```bash
git diff --check
coderabbit review --agent --base develop
```

Expected: no whitespace errors and no unresolved Critical/Warning findings.
