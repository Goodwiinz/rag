# Frontend Bug Audit — Codex Review Findings

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all P1/P2 bugs found by systematic Codex review of all 30 frontend pages.

**Architecture:** Fixes span 6 areas — chat, auth, documents, research-engine, analytics, entities. Most are contract mismatches between frontend and backend (wrong URLs, field names, missing handlers).

**Date:** 2026-04-14

**Status Legend:** FIXED = already applied on `develop` branch | OPEN = still needs implementation | DEFERRED = requires backend changes, separate PR

---

## Already Fixed (this session)

| #   | Area            | Fix                                                                                                                               | File                                                                                                   | Status                            |
| --- | --------------- | --------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | --------------------------------- | ----- |
| 1   | Documents       | Query params: `page_size`→`size`, `status`→`processing_status`, `file_type`→`document_type`                                       | `frontend/src/hooks/useDocuments.ts`                                                                   | FIXED                             |
| 2   | Documents       | Filter/pagination changes now trigger refetch                                                                                     | `frontend/src/hooks/useDocuments.ts`                                                                   | FIXED                             |
| 3   | Documents       | Retry URL: `/retry` and `/retry-processing` → `/reprocess`                                                                        | `useDocuments.ts`, `page.tsx`, `enhancedDocumentService.ts`, `enhancedDocumentService.v2.ts`, `api.ts` | FIXED                             |
| 4   | Documents       | Detail sidebar uses correct fallback: `document_type`→`file_type`, `file_size_bytes`→`file_size`, `created_at`→`upload_timestamp` | `frontend/app/(dashboard)/documents/[id]/page.tsx`                                                     | FIXED                             |
| 5   | Backend         | `to_dict()` missing `"retrying": "processing"` mapping                                                                            | `backend/src/models/document.py:285`                                                                   | FIXED                             |
| 6   | Backend         | Status filter accepts both frontend (`queued`/`indexed`) and backend (`pending`/`completed`) values                               | `backend/src/api/documents/documents.py:243`                                                           | FIXED                             |
| 7   | Types           | Added `processing_retry_count?: number` to Document interface                                                                     | `frontend/src/types/document.ts`                                                                       | FIXED                             |
| 8   | Research Engine | Stripped double `/api/v1` prefix from service BASE                                                                                | `frontend/src/services/researchEngineService.ts:3`                                                     | FIXED                             |
| 9   | Analytics       | `PerformanceApiService.basePath` → `/analytics/performance`                                                                       | `frontend/src/services/documentAnalyticsApi.ts:476`                                                    | FIXED                             |
| 10  | Analytics       | `UserBehaviorApiService.basePath` → `/analytics/behavior`                                                                         | `frontend/src/services/documentAnalyticsApi.ts:400`                                                    | FIXED                             |
| 11  | Auth            | Reset-password: added Supabase `PASSWORD_RECOVERY` session recovery + expired link UI                                             | `frontend/app/(auth)/reset-password/page.tsx`                                                          | FIXED                             |
| 12  | Entities        | `Entity.position` type: `{start, end}` → `[number, number]                                                                        | null`                                                                                                  | `frontend/src/types/entity.ts:58` | FIXED |
| 13  | Entities        | `EntityResponse.position` type aligned to `[number, number]                                                                       | null`                                                                                                  | `frontend/src/types/entity.ts:91` | FIXED |
| 14  | Documents       | Tables/crop UI gated to PDF-only documents                                                                                        | `frontend/app/(dashboard)/documents/[id]/page.tsx:662`                                                 | FIXED                             |
| 15  | Documents       | Content preview fallback chain: `content_summary → content_preview → description`                                                 | `frontend/app/(dashboard)/documents/[id]/page.tsx:527`                                                 | FIXED                             |
| 16  | Documents       | `file_type` normalized from `document_type` for ProcessingStatus component                                                        | `frontend/app/(dashboard)/documents/[id]/page.tsx:93`                                                  | FIXED                             |

---

## Open P1 Bugs (broken functionality)

### Task 1: Chat — normal sends don't pass thread_id

**Files:**

- Modify: `frontend/src/services/agentChatService.ts` — `onTrace` callback already in interface (confirmed)
- Modify: `frontend/app/(dashboard)/chat/page.tsx:658-725`

**Problem:** `agentThreadMapRef` is only populated from the confirmation path. The backend sends `thread_id` in a `trace` SSE event early in the stream, but the chat page has no `onTrace` handler. Without it, every send creates a new agent thread, losing prior context.

**Fix:**
Add `onTrace` handler in the `streamMessage` callbacks block (~line 685):

```typescript
onTrace: (threadId) => {
  if (currentThreadId) {
    agentThreadMapRef.current[currentThreadId] = threadId;
  }
  setAgentThreadId(threadId);
},
```

---

### Task 2: Chat — HITL confirmation is a dead end

**Files:**

- Modify: `frontend/app/(dashboard)/chat/page.tsx:702-716, 850+`

**Problem:** `onConfirmation` stores `threadId` but never populates `pendingConfirmation` state (which is already declared but unused). No confirm UI renders. No call to `agentChatService.streamConfirm()`.

**Fix:**

1. In `onConfirmation` callback (~line 702), populate `pendingConfirmation`:

```typescript
onConfirmation: (threadId, confirmation) => {
  if (currentThreadId) {
    agentThreadMapRef.current[currentThreadId] = threadId;
  }
  setAgentThreadId(threadId);
  setPendingConfirmation({
    threadId,
    workspaceThreadId: currentThreadId || '',
    confirmation,
  });
},
```

2. Add `handleConfirmation` function:

```typescript
const handleConfirmation = async (confirmed: boolean) => {
  if (!pendingConfirmation) return;
  setIsConfirming(true);
  let confirmContent = "";
  await agentChatService.streamConfirm(
    { thread_id: pendingConfirmation.threadId, confirmed },
    {
      onToken: (content) => {
        confirmContent += content;
      },
      onDone: () => {
        const msg = {
          role: "assistant",
          content: confirmContent,
          timestamp: Date.now(),
        };
        setMessages((prev) => [...prev, msg]);
      },
      onError: (error) => {
        console.error("[Agent] Confirm error:", error);
      },
    },
  );
  setPendingConfirmation(null);
  setIsConfirming(false);
};
```

3. Render inline confirmation banner between message list and chat input when `pendingConfirmation` is non-null. APPROVE / DENY buttons. Disable chat input while pending.

---

### Task 3: Chat — stream failures append blank assistant turn

**Files:**

- Modify: `frontend/app/(dashboard)/chat/page.tsx:670-730`

**Problem:** `onError` only logs. Execution continues and appends empty `assistantContent` as a message.

**Fix:**
Add flags before `streamMessage` call:

```typescript
let streamHadError = false;
let streamHadConfirmation = false;
```

In `onError`:

```typescript
onError: (error) => {
  streamHadError = true;
  const errorMsg = { role: 'assistant', content: `⚠ Stream error: ${error}`, timestamp: Date.now() };
  setMessages(prev => [...prev, errorMsg]);
},
```

In `onConfirmation`, also set `streamHadConfirmation = true`.

After `streamMessage` resolves (~line 720):

```typescript
if (streamHadError || streamHadConfirmation) return;
if (!assistantContent.trim()) return; // guard empty content
```

---

### Task 4: Research Engine — blueprint can't reopen after reload

**Files:**

- Modify: `frontend/app/(dashboard)/research-engine/projects/[id]/blueprint/page.tsx`

**Problem:** `BlueprintEditor` expects `proj.blueprint_id` but backend `ProjectResponse` doesn't include it. No project-scoped "get blueprint" endpoint exists.

**Fix:** Requires backend route addition — `GET /research-engine/projects/{id}/blueprint`. Lower priority, defer to separate PR.

---

### Task 5: Research Engine — evidence-graph endpoint doesn't exist

**Files:**

- `frontend/app/(dashboard)/research-engine/projects/[id]/graph/page.tsx`

**Problem:** `EvidenceMap` requests `/research-engine/projects/{id}/evidence-graph` but no backend route exists. Silently shows empty graph.

**Fix:** Requires backend route implementation. Defer to separate PR.

---

### Task 6: Research Engine — resume can't reconnect SSE stream

**Files:**

- Modify: `frontend/app/(dashboard)/research-engine/runs/[id]/page.tsx`

**Problem:** After `POST /runs/{id}/resume`, run status is still `paused`. Page only opens SSE for `pending`/`running`, so stream never reconnects.

**Fix:** After resume API call, immediately change local status to `running` or add `paused` to the SSE connection conditions.

---

## Open P2 Bugs (likely bug / data loss)

### Task 7: Chat — dual persistence splits state

**File:** `frontend/app/(dashboard)/chat/page.tsx:733`

Saves turns via `/api/v2/messages` even though `/api/v1/agent/stream` already persists to agent threads. Remove the v2 message save or reconcile.

---

### Task 8: Documents list — error state never rendered

**File:** `frontend/app/(dashboard)/documents/page.tsx:22`

`error` from `useDocuments` is destructured but never displayed. Add error banner.

---

### Task 9: Documents list — multimodal type defaults to PDF

**File:** `frontend/src/hooks/useDocuments.ts:58`

`normalizeFileType` allowlist missing `multimodal`. Add it or change default from `'pdf'` to the raw value.

---

### Task 10: Documents upload — no 'queued' status in local state

**File:** `frontend/app/(dashboard)/documents/upload/page.tsx:53`

`UploadedFile.status` is `'pending' | 'uploading' | 'processing' | 'completed' | 'failed'` — no `'queued'`. Fresh uploads jump to `processing` before backend work starts.

---

### Task 11: Research Engine — save creates duplicate blueprints

**File:** `frontend/app/(dashboard)/research-engine/projects/[id]/blueprint/page.tsx`

`handleSave()` always POSTs `createBlueprint()`. No update endpoint. Each save creates a new record.

---

### Task 12: Research Engine — step history lost on refresh

**File:** `frontend/app/(dashboard)/research-engine/runs/[id]/page.tsx`

Steps only render from live SSE events. Never loads persisted steps from `GET /runs/{id}/steps` on mount.

---

### Task 13: Projects — load failures misreported as "not found"

**File:** `frontend/app/(dashboard)/projects/[id]/page.tsx:130-135`

Parallel doc/note fetches clear shared store error, masking auth/network failures as 404.

---

### Task 14: Dashboard — hardcoded mock data + falsy-zero bug

**File:** `frontend/app/(dashboard)/dashboard/page.tsx:230,307,314`

All stats except document count are fake. `stats.documents || '12,543'` treats 0 as falsy. Use `??`.

---

### Task 15: Settings — hardcoded account info

**File:** `frontend/app/(dashboard)/settings/page.tsx:48-79`

Always renders "Admin", "Default Research Workspace" regardless of actual user/org from API.

---

### Task 16: Diagnostics — no admin role guard

**File:** `frontend/app/(dashboard)/diagnostics/page.tsx:8`

Backend requires admin. Frontend shows page to all users (403 on API calls for non-admins).

---

### Task 17: Entities — RelationshipType enum mismatch

**File:** `frontend/src/types/entity.ts:24-41`

8 frontend-only types don't exist in backend, 9 backend types missing from frontend. Add missing backend types.

---

### Task 18: Search — document_type mapping uses legacy extensions

**File:** `frontend/src/services/searchService.ts:80-89`

Backend sends `text`/`image`/`audio` but service maps through old extension list and falls back to `'txt'`. Add backend types to allowlist.

---

### Task 19: Auth — verify-email always shows success

**File:** `frontend/app/(auth)/verify-email/page.tsx`

Unconditionally shows "Identity Verified" and redirects. Never checks if email was actually confirmed.

---

### Task 20: Auth — register org field required vs optional

**File:** `frontend/app/(auth)/register/page.tsx:~248`

Organization `<input>` has `required` but type contract says optional. Decide and align.

---

## Recommended Fix Order

1. **Chat P1s (Tasks 1-3)** — highest user impact, chat is core feature
2. **Documents list error display (Task 8)** — quick win
3. **Research Engine resume (Task 6)** — quick frontend fix
4. **Dashboard falsy-zero (Task 14)** — one-line fix
5. **Entities RelationshipType (Task 17)** — type alignment
6. **Remaining P2s** — address in follow-up PRs

---

## Verification

After implementing fixes:

```bash
# Type-check
cd frontend && npx tsc --noEmit

# Run tests
cd frontend && npm test -- --runInBand

# Manual smoke test on dev
# 1. Chat: send multiple messages, verify thread context preserved
# 2. Chat: trigger a destructive tool, verify confirmation banner appears
# 3. Documents: filter by status, verify list updates
# 4. Research Engine: open any page, verify no 404 in network tab
# 5. Analytics: open dashboard, verify data loads (not all zeros)
```
