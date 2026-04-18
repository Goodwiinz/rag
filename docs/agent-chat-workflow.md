# Global Agent Chat — Workflow Documentation

## Overview

The Global Agent Chat is an AI research assistant available on every page of the RAG System. It auto-detects page context, retrieves relevant documents via RAG, persists conversations, and supports both a compact floating panel and an expanded sidebar with thread history.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (Next.js)                                         │
│                                                             │
│  SidebarLayout                                              │
│  └── GlobalAgentChat (mounted once, every dashboard page)   │
│      ├── AgentFAB         (floating button, bottom-right)   │
│      ├── AgentPanel       (compact 400×560px panel)         │
│      └── AgentSidebar     (full-height, thread list + chat) │
│                                                             │
│  Hooks:                                                     │
│  ├── usePageContext       (auto-detect current page)        │
│  └── useAgentChatStore    (Zustand state management)        │
│                                                             │
│  Service:                                                   │
│  └── agentChatService     (API client for /agent/*)         │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  Backend (FastAPI)                                          │
│                                                             │
│  /api/v1/agent/                                             │
│  ├── POST /execute        (chat + RAG + persist)            │
│  ├── GET  /threads        (list agent threads)              │
│  ├── GET  /threads/{id}/messages  (thread messages)         │
│  └── GET  /health         (health check)                    │
│                                                             │
│  Persistence:                                               │
│  ├── Thread       (rag_document_scope={"source":"agent"})   │
│  ├── ChatMessage  (user + assistant messages)               │
│  └── Conversation (parent container)                        │
└─────────────────────────────────────────────────────────────┘
```

## UI Modes

### 1. Closed (default)

- Only the **FAB button** (Bot icon) is visible, fixed bottom-right
- Unread badge appears when assistant responds while closed
- Open with click or **Cmd+K** / **Ctrl+K**

### 2. Panel Mode

- 400×560px floating panel above the FAB
- Contains: header, context bar, message list, input
- Header actions: New thread (+), Clear, Expand, Close
- Context bar shows auto-detected page (e.g., "Documents", "Project: My Project")
- Mobile: full-screen with backdrop overlay

### 3. Sidebar Mode

- Full-height 420px right sidebar
- **Left pane**: Thread list with search, grouped by date
- **Right pane**: Chat area (context bar + messages + input)
- Header actions: Collapse (back to panel), Close
- Threads load from `/api/v1/agent/threads`

## Message Flow

```
User types message → Enter or Send button
        │
        ▼
┌─ agentChatStore.sendMessage() ────────────────────────┐
│  1. Validate: non-empty, not already streaming        │
│  2. Create user AgentMessage, push to messages[]      │
│  3. Clear input, set isStreaming = true               │
│  4. Build API payload (filter to user/assistant only) │
│  5. Call agentChatService.execute()                   │
└───────────────────────┬───────────────────────────────┘
                        │
                        ▼
┌─ POST /api/v1/agent/execute ──────────────────────────┐
│  1. Build system prompt with page context             │
│  2. RAG retrieval (hybrid search, org-scoped)         │
│     └── Appends [Doc N] context to system prompt      │
│  3. Call Azure OpenAI (gpt-4o)                        │
│  4. Persist to database:                              │
│     ├── Create Thread + Conversation (first message)  │
│     ├── Or reuse existing Thread (follow-up)          │
│     ├── Save user ChatMessage                         │
│     └── Save assistant ChatMessage                    │
│  5. Return response with citations + thread_id        │
└───────────────────────┬───────────────────────────────┘
                        │
                        ▼
┌─ agentChatStore (response handling) ──────────────────┐
│  1. Create assistant AgentMessage with:               │
│     ├── content (AI response text)                    │
│     ├── citations (from retrieved_contexts)           │
│     └── toolExecutions (from tool_executions)         │
│  2. Push to messages[], set isStreaming = false        │
│  3. Set activeThreadId from response                  │
│  4. If panel closed → set hasUnread = true            │
└───────────────────────────────────────────────────────┘
```

## Context Detection

The `usePageContext` hook reads the current route and provides structured context to the agent.

| Route               | Context Type  | Extra Data             |
| ------------------- | ------------- | ---------------------- |
| `/` or `/dashboard` | `overview`    | —                      |
| `/projects/[id]`    | `project`     | projectId, projectName |
| `/documents`        | `documents`   | —                      |
| `/arxiv`            | `arxiv`       | —                      |
| `/chat`             | `chat`        | —                      |
| `/research`         | `research`    | —                      |
| `/analytics`        | `analytics`   | —                      |
| `/entities`         | `entities`    | —                      |
| `/diagnostics`      | `diagnostics` | —                      |
| `/settings`         | `settings`    | —                      |
| `/upload`           | `upload`      | —                      |
| Other               | `unknown`     | —                      |

Context is injected into the LLM system prompt so the agent knows what page the user is viewing.

## Thread Persistence

### How Threads Are Created

1. User sends first message → backend creates:
   - **Workspace** lookup (user's existing workspace)
   - **Conversation** (container, title: "Agent Chat")
   - **Thread** (title: first 80 chars of message, `rag_document_scope = {"source": "agent"}`)
2. Thread ID returned to frontend → stored as `activeThreadId`
3. Follow-up messages reuse the same thread via `thread_id` parameter

### How Threads Are Identified

Agent threads are distinguished from regular Chat page threads by the JSONB marker:

```json
rag_document_scope = {"source": "agent"}
```

The `GET /threads` endpoint filters on this marker, so the agent sidebar only shows agent-created conversations.

### Thread Lifecycle

```
New message (no activeThreadId)
    → Create Thread + Conversation
    → Save user + assistant messages
    → Return thread_id

Follow-up message (has activeThreadId)
    → Lookup existing Thread
    → Save user + assistant messages
    → Increment message_count
    → Update last_message_at

Sidebar: select thread
    → GET /threads/{id}/messages
    → Load all messages into store

New thread button (+)
    → Clear activeThreadId + messages
    → Next message creates new Thread
```

## API Reference

### POST /api/v1/agent/execute

Execute an agent chat completion with RAG.

**Request:**

```json
{
  "messages": [
    { "role": "user", "content": "What papers discuss transformers?" }
  ],
  "page_context": {
    "type": "documents",
    "project_id": null
  },
  "model": "gpt-4o",
  "use_rag": true,
  "max_context_docs": 5,
  "thread_id": "optional-uuid"
}
```

**Constraints:**

- `role`: must be `"user"` or `"assistant"` (prevents prompt injection)
- `model`: must be `"gpt-4o"` or `"gpt-4o-mini"`
- `content`: max 32,000 characters
- `messages`: max 50 messages

**Response:**

```json
{
  "message": { "role": "assistant", "content": "Based on your documents..." },
  "model": "gpt-4o",
  "usage": {
    "prompt_tokens": 1200,
    "completion_tokens": 150,
    "total_tokens": 1350
  },
  "finish_reason": "stop",
  "timestamp": "2026-03-16T20:00:00Z",
  "rag_enabled": true,
  "retrieved_contexts": [
    {
      "document_id": "uuid",
      "title": "Document Title",
      "content": "Relevant excerpt...",
      "score": 0.87
    }
  ],
  "tool_executions": null,
  "thread_id": "uuid",
  "conversation_id": "uuid"
}
```

### GET /api/v1/agent/threads

List agent-created threads for the current user.

**Response:**

```json
{
  "threads": [
    {
      "id": "uuid",
      "title": "What papers discuss transformers?",
      "created_at": "2026-03-16T20:00:00Z",
      "updated_at": "2026-03-16T20:05:00Z",
      "message_count": 4,
      "last_message_at": "2026-03-16T20:05:00Z",
      "source_project_id": null
    }
  ],
  "total": 1
}
```

### GET /api/v1/agent/threads/{thread_id}/messages

Get all messages for a specific agent thread.

**Response:**

```json
{
  "messages": [
    {
      "id": "uuid",
      "role": "user",
      "content": "What papers discuss transformers?",
      "created_at": "2026-03-16T20:00:00Z",
      "tool_name": null,
      "tool_call_id": null,
      "citations": null
    },
    {
      "id": "uuid",
      "role": "assistant",
      "content": "Based on your documents [Doc 1]...",
      "created_at": "2026-03-16T20:00:02Z",
      "citations": [
        {
          "document_id": "uuid",
          "document_title": "Paper Title",
          "snippet": "..."
        }
      ]
    }
  ],
  "total": 2
}
```

## Frontend Components

| Component           | File                                          | Purpose                                                            |
| ------------------- | --------------------------------------------- | ------------------------------------------------------------------ |
| `GlobalAgentChat`   | `components/agent-chat/GlobalAgentChat.tsx`   | Root: mounts FAB + panel/sidebar, keyboard shortcuts, context sync |
| `AgentFAB`          | `components/agent-chat/AgentFAB.tsx`          | Floating action button with unread badge                           |
| `AgentPanel`        | `components/agent-chat/AgentPanel.tsx`        | Compact panel: header + context + messages + input                 |
| `AgentPanelHeader`  | `components/agent-chat/AgentPanelHeader.tsx`  | Panel header with new/clear/expand/close buttons                   |
| `AgentContextBar`   | `components/agent-chat/AgentContextBar.tsx`   | Shows auto-detected page context                                   |
| `AgentMessageList`  | `components/agent-chat/AgentMessageList.tsx`  | Scrollable message list with empty state                           |
| `AgentMessageItem`  | `components/agent-chat/AgentMessageItem.tsx`  | Individual message bubble (user/assistant)                         |
| `ToolExecutionCard` | `components/agent-chat/ToolExecutionCard.tsx` | Expandable card showing tool call results                          |
| `AgentInput`        | `components/agent-chat/AgentInput.tsx`        | Auto-resizing textarea with send button                            |
| `AgentSidebar`      | `components/agent-chat/AgentSidebar.tsx`      | Expanded mode: thread list + chat area                             |
| `AgentThreadList`   | `components/agent-chat/AgentThreadList.tsx`   | Thread list with loading/empty states                              |

## State Management

**Store:** `useAgentChatStore` (Zustand + Immer)

| State Field      | Type                               | Description                |
| ---------------- | ---------------------------------- | -------------------------- |
| `uiMode`         | `'closed' \| 'panel' \| 'sidebar'` | Current UI mode            |
| `activeThreadId` | `string \| null`                   | Active conversation thread |
| `threads`        | `AgentThread[]`                    | Thread list for sidebar    |
| `messages`       | `AgentMessage[]`                   | Messages in current thread |
| `isStreaming`    | `boolean`                          | Whether AI is responding   |
| `inputValue`     | `string`                           | Current input text         |
| `hasUnread`      | `boolean`                          | Unread notification badge  |
| `pageContext`    | `PageContext`                      | Auto-detected page context |

## Keyboard Shortcuts

| Shortcut           | Action              |
| ------------------ | ------------------- |
| `Cmd+K` / `Ctrl+K` | Toggle agent panel  |
| `Escape`           | Close panel/sidebar |
| `Enter`            | Send message        |
| `Shift+Enter`      | New line in input   |

## Security

- **Auth required**: All endpoints use `Depends(get_current_user)`
- **Role validation**: Only `"user"` and `"assistant"` roles accepted (prevents system prompt injection)
- **Model allowlist**: Only `"gpt-4o"` and `"gpt-4o-mini"` accepted
- **Input limits**: 32K chars per message, 50 messages max
- **Org-scoped RAG**: Search filtered by `user_id` and `organization_id`
- **Thread ownership**: Thread listing and message retrieval verify ownership through Workspace → Conversation → Thread chain
- **IDOR prevention**: Thread access checks user ownership before returning data

## Database Schema

```
Workspace (owner_id → User)
└── Conversation (workspace_id, title="Agent Chat")
    └── Thread (conversation_id, rag_document_scope={"source":"agent"})
        ├── ChatMessage (role=USER, content, user_id)
        ├── ChatMessage (role=ASSISTANT, content, model_name)
        └── ChatMessage (role=TOOL, tool_name, tool_call_id)  [future]
```

No new tables — reuses existing chat schema with the `{"source": "agent"}` marker to distinguish agent threads.

## Files

### Frontend

- `frontend/app/(dashboard)/layout.tsx` — Mounts `GlobalAgentChat` globally
- `frontend/src/components/agent-chat/*.tsx` — 11 UI components
- `frontend/src/hooks/usePageContext.ts` — Page context detection
- `frontend/src/store/agentChatStore.ts` — Zustand store
- `frontend/src/services/agentChatService.ts` — API client
- `frontend/src/types/agent-chat.ts` — TypeScript types

### Backend

- `backend/src/api/agent/__init__.py` — Module init
- `backend/src/api/agent/execute.py` — All endpoints + schemas
- `backend/src/main.py` — Router registration (`app.include_router(agent_router)`)
