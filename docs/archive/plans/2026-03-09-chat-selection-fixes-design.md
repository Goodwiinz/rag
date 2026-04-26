# Chat Conversation Selection Fixes

**Date**: 2026-03-09
**Scope**: Fix 4 bugs in conversation selection and new session logic
**Files**: `ChatSidebar.tsx`, `page.tsx` (chat), `chat-store.ts`

## Fix 1: Dual ID Matching Confusion

**File**: `frontend/src/components/chat/ChatSidebar.tsx:118`
**Problem**: `conv.id === activeId || conv.threadId === activeId` — both fields always contain the same thread ID. If they diverge, active highlighting could break.
**Fix**: Remove `threadId` from `SidebarConversation` interface. Simplify active check to `conv.id === activeId`.

## Fix 2: No Loading Indicator on Conversation Switch

**File**: `frontend/app/(dashboard)/chat/page.tsx` (lazy-load effect ~line 1402)
**Problem**: Clicking a conversation triggers an API fetch with no visual feedback. On slow networks, UI appears frozen.
**Fix**: Add `isLoadingMessages` state. Set `true` before fetch, `false` after. Show a loading skeleton in the message area.

## Fix 3: Streaming Race Condition

**File**: `frontend/app/(dashboard)/chat/page.tsx:1676-1678`
**Problem**: `storeStopStreaming()` clears the virtual streaming message. If store `loadMessages()` hasn't populated `messages[threadId]` yet, there's a brief flash.
**Fix**: Before calling `storeStopStreaming()`, verify local messages have been set. If store messages are empty, retry reading from store with a short delay before clearing streaming state.

## Fix 5: SessionStorage Stale State

**File**: `frontend/app/(dashboard)/chat/page.tsx` (multiple locations)
**Problem**: `sessionStorage.setItem('activeThreadId', id)` persists if page closes during fetch, causing incorrect selection on next load.
**Fix**: Store a JSON object `{ threadId, timestamp }` instead of a plain string. On read, expire entries older than 30 seconds. Clear stale entries during initialization.
