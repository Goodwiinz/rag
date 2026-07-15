# Chat Terminal Reconciliation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Keep every just-sent `/chat` turn visible and correctly attached to its thread without a browser reload, including normal completion, navigation, pagination, HITL, stop, error, and resume paths.

**Architecture:** PostgreSQL remains the canonical persisted transcript. Zustand becomes the single owner of selected-thread identity and canonical message-page freshness; React-local messages are limited to optimistic or explicitly local-only projections for the selected thread. Every message receives a stable client/runtime ID before first render, while the database ID remains a separate API identity. All newest-page reads for a thread share one abortable, generation-guarded coordinator, and every stream lifecycle reconciles its snapshotted owning thread through that coordinator.

**Tech Stack:** Next.js 16, React 18, Zustand 5 with Immer, assistant-ui 0.14.26, TypeScript, Vitest/Testing Library, Playwright, FastAPI, Pydantic, PostgreSQL, pytest.

---

## Why this design

Current production evidence shows that the user and assistant rows were persisted before refresh, but the active agent stream only updated React-local state. The canonical Zustand page remained stale. A later state reset could therefore expose the stale page until a full reload.

The deeper audit found four amplifiers:

1. `currentThreadId`, `activeConversationId`, `activeConversationIdRef`, and the URL can temporarily disagree.
2. Main-stream completion mutates `finalAssistantMessage.id` after first render.
3. `selectDisplayedMessages()` treats array length as freshness and falls back to role/content matching for id-less messages.
4. `loadMessages()` uses one global epoch, so unrelated thread selections invalidate each other while same-thread initial loads and terminal refreshes have no shared request ordering.

The revised plan follows these current primary-source constraints:

- React: avoid duplicated state and treat rendered state as immutable: <https://react.dev/learn/choosing-the-state-structure> and <https://react.dev/learn/updating-objects-in-state>
- assistant-ui: keep `currentThreadId` synchronized with the external store and use stable message IDs: <https://www.assistant-ui.com/docs/runtimes/concepts/threads> and <https://www.assistant-ui.com/docs/runtimes/custom/external-store>
- Zustand: replace arrays/objects instead of mutating existing snapshots: <https://zustand.docs.pmnd.rs/learn/guides/immutable-state-and-merging>
- Targeted invalidation: preserve optimistic data, cancel superseded reads, then background-refetch the exact resource: <https://tanstack.com/query/latest/docs/framework/react/guides/query-invalidation> and <https://tanstack.com/query/latest/docs/reference/QueryClient>

## Confirmed findings this plan closes

1. **P1:** Successful main-stream turns do not update or refresh `chat-store.messages`.
2. **P1:** Switching away and back can clear the completed local turn while `setCurrentThread()` reuses the stale cached page.
3. **P1:** A turn completed while another thread is displayed is server-persisted but not guaranteed to appear when the user returns.
4. **P2:** A longer stale/paginated store array can replace a shorter local array containing a newer optimistic tail.
5. **P2:** Assistant UI can retain a temporary/index-derived identity because an already-rendered message object is mutated with the persisted ID.
6. **P2:** Normal completion, confirmation, stop, error, and resume do not share one reconciliation policy.
7. **Coverage gap:** no test covers send -> complete -> switch away -> switch back without reload.

## Calibrated uncertainty

The exact same-tab event that cleared the local projection in the reported six-message thread was not captured because the authenticated production session could not be replayed. Pagination cannot be the sole incident trigger for that short thread. The implementation is not considered verified until the same-thread and switch-away/back browser regressions pass against an authenticated environment and DOM presence is distinguished from scroll position.

## State and identity contracts

### Thread identity

- `useChatStore.currentThreadId` is the only selected-thread state.
- URL navigation, sidebar selection, new-chat creation, initialization, and command navigation all call the same store action.
- Components may derive `activeThreadId`; they must not maintain a second selected-thread state or ref.
- A stream snapshots `turnThreadId` once. Background completion always reconciles that ID, never whichever thread is currently selected.

### Message identity

```ts
interface ChatPageMessage {
  id?: string;          // persisted chat_messages.id; API actions only
  runtimeId: string;    // stable client_message_id, or persisted id for legacy rows
  source: 'canonical' | 'optimistic' | 'local-only';
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  // existing provenance fields
}
```

- Generate the user `client_message_id` before creating the optimistic user message.
- Derive the assistant runtime ID with the same UUIDv5 contract as the backend: `uuidv5('nous-assistant:' + userClientMessageId, uuidv5.URL)`.
- Expose `client_message_id` on `ChatMessageResponse` so hydration recreates the same runtime identity.
- React keys, assistant-ui IDs, tool-call IDs, and boundary reset keys use `runtimeId`.
- Feedback/delete APIs continue to use persisted `id`.
- Persisted mapping sets `source: 'canonical'`; pending turns use `optimistic`; non-persisted error/status bubbles use `local-only`.
- `local-only` messages are never included in a later agent-history request.
- Never match messages by role/content and never change `runtimeId` after first render.

### Freshness and reads

```ts
type MessageFreshness = 'fresh' | 'stale' | 'refreshing';

interface RefreshExpectation {
  persistedId?: string;
  runtimeId?: string;
  diagnostic?: {
    terminalReason: string;
    localCount: number;
    completedInBackground: boolean;
  };
}
```

- Starting a server write marks that thread `stale`.
- A newest-page request changes it to `refreshing` without hiding cached or optimistic content.
- A response becomes `fresh` only if it is the latest per-thread request and contains any expected persisted/runtime ID.
- Failure, cancellation by a newer request, or a missing expected row leaves the thread `stale`.
- Initial load and terminal refresh use the same per-thread request coordinator.
- Older-page cursor loads remain separate but merge by persisted ID and cannot decide freshness for the newest page.

## Non-goals

- Do not reintroduce client-side database persistence.
- Do not extend the deprecated v2 `streamMessage` path.
- Do not migrate the whole chat cache to TanStack Query in this bug-fix series; apply the same invalidation/cancellation semantics inside the existing Zustand owner.
- Do not redesign transcript virtualization or thread-list pagination.
- Do not infer data loss from scroll position; assert message identity in state and DOM.

### Task 1: Pin the incident and related failures before implementation

**Files:**

- Create: `frontend/src/components/chat/__tests__/ChatPage.turnPersistence.test.tsx`
- Create: `frontend/src/hooks/__tests__/useChatStreaming.storeReconciliation.test.tsx`
- Modify: `frontend/src/hooks/__tests__/useChatStreaming.threadSwitch.test.tsx`

**Step 1: Write the same-thread failing test**

Seed thread A with a cached persisted pair, send `Find recent arXiv papers on retrieval-augmented generation`, emit `onToken`, then emit `onDone`. Assert the optimistic user and committed assistant remain in the rendered transcript before and after canonical reconciliation.

**Step 2: Write the switch-away/back failing test**

Complete a turn on A, select B, then return to A without reloading. Assert the new user and assistant runtime IDs are present.

**Step 3: Write the background-completion failing test**

Start on A, switch to B before `onDone`, complete A, return to A, and assert B never receives A's local writes while A still reconciles.

**Step 4: Run the tests and verify RED**

```bash
corepack pnpm@10.18.2 --dir frontend exec vitest run \
  src/components/chat/__tests__/ChatPage.turnPersistence.test.tsx \
  src/hooks/__tests__/useChatStreaming.storeReconciliation.test.tsx \
  src/hooks/__tests__/useChatStreaming.threadSwitch.test.tsx
```

Expected: failures demonstrate missing store reconciliation, stale cached revisit, and length/content-based replacement.

Do not commit Task 1 alone. Keep these tests red until the corresponding implementation tasks turn them green.

### Task 2: Make client/runtime identity survive persistence and reload

**Files:**

- Modify: `backend/src/schemas/chat.py:368-395`
- Create: `backend/tests/unit/schemas/test_chat_message_response.py`
- Modify generated: `backend/openapi.json`
- Modify generated: `frontend/src/types/generated/api.d.ts`
- Modify: `frontend/src/types/workspace.ts:249-278`
- Modify: `frontend/src/components/chat/shared/cloudMessageView.ts:96-170`
- Modify: `frontend/src/hooks/chat/useChatStreaming.ts:808-950`
- Modify: `frontend/src/components/chat/aui/convertMessage.ts:107-153`
- Modify: `frontend/src/components/chat/ChatMessageList.tsx:227-304`
- Modify: `frontend/src/components/chat/aui/AuiMessage.tsx:455-500`
- Modify: `frontend/src/components/chat/shared/__tests__/cloudMessageView.test.ts`
- Modify: `frontend/src/components/chat/aui/__tests__/convertMessage.test.ts`
- Create: `frontend/src/test/chatMessageFactory.ts`
- Modify test fixtures: `frontend/src/components/chat/aui/__tests__/AuiMessage.test.tsx`
- Modify test fixtures: `frontend/src/components/chat/aui/__tests__/ChatRuntimeProvider.test.tsx`
- Modify test fixtures: `frontend/src/components/chat/__tests__/ChatMessageList.loadOlder.test.tsx`
- Modify test fixtures: `frontend/src/components/chat/__tests__/ChatMessageList.prepend.test.tsx`
- Modify test fixtures: `frontend/src/components/chat/__tests__/ChatMessageList.threadSwitch.test.tsx`
- Modify test fixtures: `frontend/src/hooks/__tests__/useChatStreaming.auiApproval.test.tsx`
- Modify test fixtures: `frontend/src/hooks/__tests__/useChatStreaming.auiPlaceholder.test.tsx`
- Modify test fixtures: `frontend/src/hooks/__tests__/useChatStreaming.canonical.test.tsx`
- Modify test fixtures: `frontend/src/hooks/__tests__/useChatStreaming.confirmToolSteps.test.tsx`
- Modify test fixtures: `frontend/src/hooks/__tests__/useChatStreaming.doneToolExecutions.test.tsx`
- Modify test fixtures: `frontend/src/hooks/__tests__/useChatStreaming.resume.test.tsx`
- Modify test fixtures: `frontend/src/hooks/__tests__/useChatStreaming.threadScope.test.tsx`
- Modify test fixtures: `frontend/src/hooks/__tests__/useChatStreaming.threadSwitch.test.tsx`
- Modify test fixtures: `frontend/src/hooks/chat/__tests__/useChatStreaming.submitHistory.test.ts`

**Step 1: Write the backend response-schema test**

Construct `ChatMessageResponse.model_validate()` from an object containing `client_message_id` and assert `model_dump(mode='json')` returns the UUID string. Add a null/legacy case.

**Step 2: Run the backend test and verify RED**

```bash
uv run pytest backend/tests/unit/schemas/test_chat_message_response.py \
  -c backend/pytest.ini -q
```

Expected: FAIL because `ChatMessageResponse` does not expose the field.

**Step 3: Expose the persisted client ID**

Add to `ChatMessageResponse`:

```py
client_message_id: Optional[UUID] = None
```

Regenerate contracts; do not hand-edit generated files:

```bash
uv run python scripts/ci/generate_openapi.py
corepack pnpm@10.18.2 --dir frontend generate:api-types
```

Add `client_message_id?: string | null` to the handwritten `ChatMessage` compatibility interface if it does not alias the generated schema yet.

**Step 4: Add stable runtime IDs to UI messages**

Make `runtimeId` required in production `ChatPageMessage` construction. Persisted mapping uses:

```ts
runtimeId: dbMsg.client_message_id ?? dbMsg.id
source: 'canonical'
```

Move `turnClientMessageId = crypto.randomUUID()` before the optimistic user object is created. Import `v5 as uuidv5` from `uuid` and derive the assistant runtime ID before creating the streaming placeholder.

Mark optimistic user/assistant messages with `source: 'optimistic'`. Give error, empty-response, and confirmation-failure bubbles their own stable runtime ID plus `source: 'local-only'`. Filter `local-only` rows out when building the next agent request history.

Add a shared `makeChatPageMessage()` test factory and migrate every typed `ChatPageMessage` fixture listed above. Do not weaken the production interface to optional merely to preserve old tests.

**Step 5: Keep database and runtime identities separate**

- `convertMessage().id = message.runtimeId`
- list keys and `MessageByIndexBoundary.resetKey` use `runtimeId`
- tool-call and approval IDs use `runtimeId`
- feedback/delete actions keep using `message.id`
- done payload sets only persisted `id`; it never changes `runtimeId`

Replace every in-place message mutation with a new object/array.

**Step 6: Run focused tests and verify GREEN**

```bash
uv run pytest backend/tests/unit/schemas/test_chat_message_response.py \
  -c backend/pytest.ini -q
corepack pnpm@10.18.2 --dir frontend exec vitest run \
  src/components/chat/shared/__tests__/cloudMessageView.test.ts \
  src/components/chat/aui/__tests__/convertMessage.test.ts \
  src/hooks/__tests__/useChatStreaming.canonical.test.tsx
corepack pnpm@10.18.2 --dir frontend type-check
```

**Step 7: Commit**

```bash
git add backend/src/schemas/chat.py backend/tests/unit/schemas/test_chat_message_response.py \
  backend/openapi.json frontend/src/types/generated/api.d.ts \
  frontend/src/types/workspace.ts frontend/src/components/chat/shared/cloudMessageView.ts \
  frontend/src/hooks/chat/useChatStreaming.ts frontend/src/components/chat/aui/convertMessage.ts \
  frontend/src/components/chat/ChatMessageList.tsx frontend/src/components/chat/aui/AuiMessage.tsx \
  frontend/src/components/chat/shared/__tests__/cloudMessageView.test.ts \
  frontend/src/components/chat/aui/__tests__/convertMessage.test.ts \
  frontend/src/hooks/__tests__/useChatStreaming.canonical.test.tsx frontend/src/test/chatMessageFactory.ts \
  frontend/src/components/chat/aui/__tests__/AuiMessage.test.tsx \
  frontend/src/components/chat/aui/__tests__/ChatRuntimeProvider.test.tsx \
  frontend/src/components/chat/__tests__/ChatMessageList.loadOlder.test.tsx \
  frontend/src/components/chat/__tests__/ChatMessageList.prepend.test.tsx \
  frontend/src/components/chat/__tests__/ChatMessageList.threadSwitch.test.tsx \
  frontend/src/hooks/__tests__/useChatStreaming.auiApproval.test.tsx \
  frontend/src/hooks/__tests__/useChatStreaming.auiPlaceholder.test.tsx \
  frontend/src/hooks/__tests__/useChatStreaming.confirmToolSteps.test.tsx \
  frontend/src/hooks/__tests__/useChatStreaming.doneToolExecutions.test.tsx \
  frontend/src/hooks/__tests__/useChatStreaming.resume.test.tsx \
  frontend/src/hooks/__tests__/useChatStreaming.threadScope.test.tsx \
  frontend/src/hooks/__tests__/useChatStreaming.threadSwitch.test.tsx \
  frontend/src/hooks/chat/__tests__/useChatStreaming.submitHistory.test.ts
git commit -m "fix(chat): preserve stable message runtime ids"
```

### Task 3: Make Zustand the only selected-thread authority

**Files:**

- Modify: `frontend/src/hooks/chat/useChatSession.ts:50-220`
- Modify: `frontend/src/hooks/chat/useChatSession.ts:281-430`
- Modify: `frontend/src/hooks/chat/useChatSession.ts:489-811`
- Modify: `frontend/src/hooks/chat/useChatStreaming.ts:183-250`
- Modify: `frontend/src/hooks/chat/useChatStreaming.ts:363-400`
- Modify: `frontend/app/(dashboard)/chat/page.tsx:90-200`
- Modify: `frontend/app/(dashboard)/chat/page.tsx:348-405`
- Modify: `frontend/app/(dashboard)/chat/page.tsx:724-780`
- Modify: `frontend/src/hooks/__tests__/useChatSession.urlSync.test.tsx`
- Modify: `frontend/src/hooks/__tests__/useChatSession.boundedRestore.test.tsx`
- Modify: `frontend/src/components/chat/__tests__/ChatPage.threadSelect.test.tsx`
- Modify: `frontend/src/hooks/__tests__/useChatStreaming.threadSwitch.test.tsx`

**Step 1: Add failing selection-authority tests**

Assert that sidebar, URL, command navigation, new-chat, initialization, and new-thread creation each change only `useChatStore.currentThreadId`. Add a test proving a stale URL detail response cannot replace a newer store selection.

**Step 2: Run selection tests and verify RED**

```bash
corepack pnpm@10.18.2 --dir frontend exec vitest run \
  src/hooks/__tests__/useChatSession.urlSync.test.tsx \
  src/hooks/__tests__/useChatSession.boundedRestore.test.tsx \
  src/components/chat/__tests__/ChatPage.threadSelect.test.tsx \
  src/hooks/__tests__/useChatStreaming.threadSwitch.test.tsx
```

**Step 3: Remove duplicate selected-thread state**

Delete `activeConversationId` state, `setActiveConversationId`, and `activeConversationIdRef`. Derive:

```ts
const activeThreadId = useChatStore((state) => state.currentThreadId);
```

Use `setCurrentThread()` for every selection path. Conversation metadata may be looked up from `activeThreadId`; it must not own selection.

**Step 4: Make stream ownership store-based**

Snapshot `turnThreadId` when a run begins. Gate selected-thread-only local writes with:

```ts
const isTurnDisplayed = () =>
  useChatStore.getState().currentThreadId === turnThreadId;
```

All persistence and refresh actions still target `turnThreadId` when false.

**Step 5: Run tests and verify GREEN**

Run the Step 2 command plus `src/hooks/__tests__/useChatStreaming.threadScope.test.tsx`.

**Step 6: Commit**

```bash
git add frontend/src/hooks/chat/useChatSession.ts frontend/src/hooks/chat/useChatStreaming.ts \
  'frontend/app/(dashboard)/chat/page.tsx' frontend/src/hooks/__tests__/useChatSession.urlSync.test.tsx \
  frontend/src/hooks/__tests__/useChatSession.boundedRestore.test.tsx \
  frontend/src/components/chat/__tests__/ChatPage.threadSelect.test.tsx \
  frontend/src/hooks/__tests__/useChatStreaming.threadSwitch.test.tsx \
  frontend/src/hooks/__tests__/useChatStreaming.threadScope.test.tsx
git commit -m "refactor(chat): centralize active thread selection"
```

### Task 4: Make API cancellation composable

**Files:**

- Modify: `frontend/src/services/api-client.ts:90-175`
- Create: `frontend/src/services/__tests__/api-client.abort.test.ts`
- Modify: `frontend/src/services/workspaceService.ts:209-233`
- Modify: `frontend/src/services/__tests__/workspaceService.cache.test.ts`

**Step 1: Write caller-abort tests**

Pin that a caller-provided `AbortSignal` reaches `fetch`, aborting it stops retries, and timeout aborts still produce the existing timeout error. A caller abort must not be mislabeled as a timeout.

**Step 2: Run and verify RED**

```bash
corepack pnpm@10.18.2 --dir frontend exec vitest run \
  src/services/__tests__/api-client.abort.test.ts \
  src/services/__tests__/api-client.long-timeout.test.ts
```

Expected: the API client currently replaces the caller signal with its timeout controller.

**Step 3: Compose timeout and caller signals**

Use `AbortSignal.any([callerSignal, timeoutController.signal])` where supported by the project targets, or a tested cleanup helper that relays both signals. In the catch path, distinguish `callerSignal.aborted` from `timeoutController.signal.aborted` and never retry an explicit cancellation.

**Step 4: Thread the signal through message listing**

Add `signal?: AbortSignal` to `workspaceService.listMessages()` options and pass it as the second argument to `api.get`.

**Step 5: Run and verify GREEN**

Run the Step 2 command plus `src/services/__tests__/workspaceService.cache.test.ts`.

**Step 6: Commit**

```bash
git add frontend/src/services/api-client.ts frontend/src/services/__tests__/api-client.abort.test.ts \
  frontend/src/services/workspaceService.ts frontend/src/services/__tests__/workspaceService.cache.test.ts
git commit -m "fix(api): preserve caller cancellation signals"
```

### Task 5: Add one per-thread newest-page coordinator and freshness contract

**Files:**

- Modify: `frontend/src/store/chat-store.ts:125-170`
- Modify: `frontend/src/store/chat-store.ts:291-500`
- Modify: `frontend/src/store/chat-store.ts:1084-1230`
- Create: `frontend/src/store/__tests__/chat-store-refresh.test.ts`
- Modify: `frontend/src/store/__tests__/chat-store-pagination.test.ts`

**Step 1: Write failing coordinator tests**

Pin these cases:

1. A newer newest-page request for A aborts and supersedes the older A request.
2. A request for B does not cancel or invalidate A.
3. An initial load and a terminal refresh for A participate in the same generation order.
4. A stale cached page remains renderable while refreshing.
5. A response missing `expected.persistedId` or `expected.runtimeId` leaves A stale.
6. A successful expected-row response marks A fresh.
7. Refreshing the latest 50 preserves already-loaded older rows and de-duplicates overlap by persisted ID.
8. Reset, deletion, clear, and FIFO eviction abort and remove the thread's request/freshness bookkeeping.

**Step 2: Run and verify RED**

```bash
corepack pnpm@10.18.2 --dir frontend exec vitest run \
  src/store/__tests__/chat-store-refresh.test.ts \
  src/store/__tests__/chat-store-pagination.test.ts
```

**Step 3: Add the coordinator**

Keep controllers outside Immer state:

```ts
const newestPageRequests = new Map<
  string,
  { generation: number; controller: AbortController }
>();
```

Both `loadMessages()` and `refreshMessages()` call one internal newest-page function. Abort only the previous request for the same thread, and check the generation before committing.

**Step 4: Add explicit store actions**

```ts
messageFreshness: Record<string, MessageFreshness>;
markMessagesStale(threadId: string): void;
refreshMessages(
  threadId: string,
  expected?: RefreshExpectation
): Promise<boolean>;
```

Selecting a cached fresh thread makes no request. Selecting cached stale data renders it immediately and starts a background refresh without showing the uncached skeleton.

**Step 5: Merge the newest page without collapsing older history**

Extract a pure helper. Retain cached rows strictly older than the canonical page boundary, replace the overlapping newest segment, de-duplicate by persisted ID, sort with the existing `(created_at, id)` contract, and rebuild reverse indexes. `loadOlderMessages()` cannot mark the newest page fresh.

**Step 6: Run and verify GREEN**

Run the Step 2 command.

**Step 7: Commit**

```bash
git add frontend/src/store/chat-store.ts frontend/src/store/__tests__/chat-store-refresh.test.ts \
  frontend/src/store/__tests__/chat-store-pagination.test.ts
git commit -m "fix(chat): coordinate per-thread transcript refresh"
```

### Task 6: Reconcile every stream lifecycle through the owning thread

**Files:**

- Modify: `frontend/src/hooks/chat/useChatStreaming.ts:363-790`
- Modify: `frontend/src/hooks/chat/useChatStreaming.ts:808-1065`
- Modify: `frontend/src/hooks/chat/useChatStreaming.ts:1077-1375`
- Modify: `frontend/src/hooks/__tests__/useChatStreaming.storeReconciliation.test.tsx`
- Modify: `frontend/src/hooks/__tests__/useChatStreaming.resume.test.tsx`
- Modify: `frontend/src/hooks/__tests__/useChatStreaming.confirmToolSteps.test.tsx`
- Modify: `frontend/src/hooks/__tests__/useChatStreaming.canonical.test.tsx`

**Step 1: Mark stale before server persistence can begin**

After the real thread ID exists and before starting the agent request, call `markMessagesStale(turnThreadId)`.

**Step 2: Reconcile normal completion with an expected row**

After `done`, call:

```ts
refreshMessages(turnThreadId, {
  persistedId: doneIds.assistant_message_id ?? undefined,
  runtimeId: doneIds.client_message_id ?? assistantRuntimeId,
});
```

Do this even when the user is viewing another thread. Keep local rendering gated to the current selection.

**Step 3: Reconcile non-normal paths**

- confirmation pause/error: expect the user runtime ID already persisted before graph execution;
- confirm/deny completion and stream resume: expect the assistant persisted/runtime ID;
- nested confirmation: reconcile the already-persisted user turn but keep the run pending;
- stop/abort: perform an opportunistic refresh for the deterministic assistant runtime ID; remain stale if the row has not landed yet;
- network error: reconcile the durable user row and retain the local error bubble as non-persisted UI state.

**Step 4: Remove object mutation**

Create the final assistant object immutably with both identities before its first committed render. Delete the two-pass `setMessages()` and `finalAssistantMessage.id = ...` path.

**Step 5: Run and verify GREEN**

```bash
corepack pnpm@10.18.2 --dir frontend exec vitest run \
  src/hooks/__tests__/useChatStreaming.storeReconciliation.test.tsx \
  src/hooks/__tests__/useChatStreaming.threadSwitch.test.tsx \
  src/hooks/__tests__/useChatStreaming.resume.test.tsx \
  src/hooks/__tests__/useChatStreaming.confirmToolSteps.test.tsx \
  src/hooks/__tests__/useChatStreaming.canonical.test.tsx
```

**Step 6: Commit**

```bash
git add frontend/src/hooks/chat/useChatStreaming.ts frontend/src/hooks/__tests__/useChatStreaming.storeReconciliation.test.tsx \
  frontend/src/hooks/__tests__/useChatStreaming.threadSwitch.test.tsx \
  frontend/src/hooks/__tests__/useChatStreaming.resume.test.tsx \
  frontend/src/hooks/__tests__/useChatStreaming.confirmToolSteps.test.tsx \
  frontend/src/hooks/__tests__/useChatStreaming.canonical.test.tsx
git commit -m "fix(chat): reconcile every terminal stream state"
```

### Task 7: Replace length/content heuristics with runtime-ID overlay merging

**Files:**

- Modify: `frontend/src/components/chat/shared/cloudMessageView.ts:173-360`
- Modify: `frontend/src/components/chat/shared/__tests__/cloudMessageView.test.ts`
- Modify: `frontend/src/hooks/chat/useChatSession.ts:160-280`
- Modify: `frontend/src/hooks/chat/chatTypes.ts`
- Modify: `frontend/src/hooks/__tests__/useChatSession.loadingScope.test.tsx`
- Modify: `frontend/src/hooks/__tests__/useChatSession.threadSwitchBleed.test.tsx`

**Step 1: Make canonical-plus-overlay merging explicit**

Map persisted messages to runtime IDs, merge matching local provenance by `runtimeId`, then retain unmatched optimistic messages only while the thread is stale/refreshing. A fresh canonical page removes optimistic overlays; explicit `local-only` status/error bubbles remain until retry, next send, or thread change and are never posted as agent history.

First write the failing cases for equal-length divergent tails, a 100-row stale store page versus a newer 52-row local tail, repeated identical prompts, and canonical replacement of one optimistic runtime ID. Run `cloudMessageView.test.ts` and verify RED before changing the selector.

Delete:

- `storeMessages.length >= localMessages.length` freshness logic;
- role/content fallback matching;
- any equal-length special case.

**Step 2: Stop using conversation metadata as a transcript cache**

Remove success-path writes that copy full message arrays into `conversations`. Conversation rows retain title, preview, count, and timestamps. The selected thread's canonical page lives in Zustand; React-local `messages` is only its optimistic overlay.

Do not introduce a third message cache.

**Step 3: Update the selector tests**

Assert:

- repeated identical prompts remain distinct by runtime ID;
- pagination cannot erase a newer optimistic tail;
- a canonical row removes its matching optimistic overlay;
- a failed/missing expected refresh keeps the overlay;
- a fresh page removes stale optimistic overlay data but retains explicit `local-only` error UI;
- the next submitted agent history excludes every `local-only` row.

**Step 4: Run and verify GREEN**

```bash
corepack pnpm@10.18.2 --dir frontend exec vitest run \
  src/components/chat/shared/__tests__/cloudMessageView.test.ts \
  src/hooks/__tests__/useChatSession.loadingScope.test.tsx \
  src/hooks/__tests__/useChatSession.threadSwitchBleed.test.tsx \
  src/hooks/__tests__/useChatSession.urlSync.test.tsx
```

**Step 5: Commit**

```bash
git add frontend/src/components/chat/shared/cloudMessageView.ts \
  frontend/src/components/chat/shared/__tests__/cloudMessageView.test.ts \
  frontend/src/hooks/chat/useChatSession.ts frontend/src/hooks/chat/chatTypes.ts \
  frontend/src/hooks/__tests__/useChatSession.loadingScope.test.tsx \
  frontend/src/hooks/__tests__/useChatSession.threadSwitchBleed.test.tsx \
  frontend/src/hooks/__tests__/useChatSession.urlSync.test.tsx
git commit -m "fix(chat): merge transcript state by stable identity"
```

### Task 8: Pin Assistant UI and page-level handoff behavior

**Files:**

- Modify: `frontend/src/components/chat/aui/__tests__/ChatRuntimeProvider.test.tsx`
- Modify: `frontend/src/components/chat/aui/__tests__/AuiMessage.test.tsx`
- Modify: `frontend/src/components/chat/__tests__/ChatPage.turnPersistence.test.tsx`
- Modify: `frontend/src/components/chat/__tests__/ChatPage.threadSelect.test.tsx`

**Step 1: Test the runtime transition**

Rerender persisted history -> optimistic user/assistant -> canonical rows. Assert the user never leaves the assistant-ui sequence, the assistant runtime ID stays constant, the persisted ID becomes available to API actions, and the out-of-bounds boundary recovers.

**Step 2: Test same-count thread replacement**

Switch between same-length threads with different runtime IDs. Assert the row subtree remounts for a different thread but not for an append on the same thread.

**Step 3: Turn the Task 1 page tests GREEN**

Verify same-thread completion, switch-away/back, background completion, pagination during a dirty turn, HITL pause, and stopped partial response.

**Step 4: Run focused UI tests**

```bash
corepack pnpm@10.18.2 --dir frontend exec vitest run \
  src/components/chat/aui/__tests__/ChatRuntimeProvider.test.tsx \
  src/components/chat/aui/__tests__/AuiMessage.test.tsx \
  src/components/chat/__tests__/ChatMessageList.threadSwitch.test.tsx \
  src/components/chat/__tests__/ChatPage.turnPersistence.test.tsx \
  src/components/chat/__tests__/ChatPage.threadSelect.test.tsx
```

**Step 5: Commit**

```bash
git add frontend/src/components/chat/aui/__tests__/ChatRuntimeProvider.test.tsx \
  frontend/src/components/chat/aui/__tests__/AuiMessage.test.tsx \
  frontend/src/components/chat/__tests__/ChatPage.turnPersistence.test.tsx \
  frontend/src/components/chat/__tests__/ChatPage.threadSelect.test.tsx
git commit -m "test(chat): cover live-to-canonical transcript handoff"
```

### Task 9: Add invariant diagnostics and authenticated browser proof

**Files:**

- Modify: `frontend/src/hooks/chat/useChatStreaming.ts`
- Modify: `frontend/src/store/chat-store.ts`
- Create: `frontend/e2e/nous-flows/chat-terminal-reconciliation.spec.ts`
- Reuse: `frontend/e2e/fixtures/test-data.fixture.ts`

**Step 1: Add low-noise invariant diagnostics**

Emit one structured warning only when terminal reconciliation fails or an identity contract is violated. Include thread ID, terminal reason, freshness, local/store counts, expected persisted/runtime IDs, request generation, and whether completion occurred in the background. Never log message content, citations, tool arguments, tokens, or authorization data.

**Step 2: Write the authenticated Playwright regression**

Using a disposable seeded thread:

1. send the incident prompt;
2. wait for the assistant terminal marker;
3. assert user and assistant runtime IDs remain in the DOM;
4. navigate to another thread and back without reload;
5. assert the same IDs remain;
6. reload once and assert the hydrated runtime IDs and persisted IDs match the pre-reload view;
7. repeat with completion while another thread is selected.

Assert DOM presence separately from viewport visibility.

**Step 3: Run the focused browser spec**

```bash
corepack pnpm@10.18.2 --dir frontend test:e2e -- \
  e2e/nous-flows/chat-terminal-reconciliation.spec.ts --project=chromium
```

Expected: all scenarios pass without `page.reload()` as a recovery action.

**Step 4: Commit**

```bash
git add frontend/src/hooks/chat/useChatStreaming.ts frontend/src/store/chat-store.ts \
  frontend/e2e/nous-flows/chat-terminal-reconciliation.spec.ts
git commit -m "test(chat): verify transcript reconciliation in browser"
```

### Task 10: Full verification and rollout guard

**Step 1: Verify generated contracts are current**

```bash
uv run python scripts/ci/generate_openapi.py --check
corepack pnpm@10.18.2 --dir frontend generate:api-types
git diff --exit-code -- backend/openapi.json frontend/src/types/generated/api.d.ts
```

**Step 2: Run backend focused and unit tests**

```bash
uv run pytest \
  backend/tests/unit/schemas/test_chat_message_response.py \
  backend/tests/unit/api/test_agent_streaming_done_ids.py \
  backend/tests/unit/api/test_agent_streaming_confirm_persistence.py \
  -c backend/pytest.ini -q
```

**Step 3: Run frontend static checks**

```bash
corepack pnpm@10.18.2 --dir frontend type-check
corepack pnpm@10.18.2 --dir frontend lint
```

**Step 4: Run the complete frontend unit suite**

```bash
corepack pnpm@10.18.2 --dir frontend test
```

**Step 5: Run authenticated browser verification**

Run the Task 9 spec, then the configured chat/nous-flow Playwright group. Verify the deployed build hash before interpreting browser results.

**Step 6: Production smoke test**

Use a disposable thread and verify normal completion, switch-away/back, background completion, confirmation pause, and stop. Confirm no reconciliation warning, abort/retry loop, cross-thread write, duplicate message, or older-history collapse.

**Step 7: Rollback criteria**

Roll back if:

- a newest-page request loop appears;
- older loaded history collapses;
- runtime IDs change across terminal handoff or reload;
- a background thread writes into the selected transcript;
- canonical rows duplicate optimistic messages;
- message-list traffic grows beyond one targeted reconciliation per terminal event, excluding explicit stale retry.

## Required implementation order

1. Red incident tests.
2. Stable runtime identity contract.
3. Single selected-thread authority.
4. Caller cancellation support.
5. Per-thread newest-page coordinator/freshness.
6. Stream lifecycle reconciliation.
7. Runtime-ID overlay merge and removal of transcript-cache duplication.
8. Assistant UI and page regressions.
9. Authenticated browser proof and diagnostics.
10. Full verification.

Tasks 3, 5, 6, and 7 form one deployable correctness unit. Do not deploy an intermediate state that clears the local transcript before the canonical store can prove freshness.
