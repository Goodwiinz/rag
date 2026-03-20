# Global Agent Chat — Workflow Documentation

## Overview

The Global Agent Chat is an AI research assistant available on every page of the RAG System. It uses a **LangGraph StateGraph** with intent-based routing to specialized subgraphs (research, writing, data analysis). It auto-detects page context, retrieves relevant documents via hybrid RAG search, executes domain-specific tools, supports human-in-the-loop confirmation for destructive actions, persists conversations with LangGraph checkpointing, and streams responses via SSE.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Frontend (Next.js)                                                      │
│                                                                          │
│  SidebarLayout                                                           │
│  └── GlobalAgentChat (mounted once, every dashboard page)                │
│      ├── AgentFAB            (floating button, bottom-right)             │
│      ├── AgentPanel          (compact 400×560px panel)                   │
│      └── AgentSidebar        (full-height, thread list + chat)           │
│                                                                          │
│  Hooks:                                                                  │
│  ├── usePageContext          (auto-detect current page)                   │
│  └── useAgentChatStore       (Zustand + Immer state management)          │
│                                                                          │
│  Service:                                                                │
│  └── agentChatService        (API client for /agent/*)                   │
│                                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│  Backend (FastAPI + LangGraph)                                           │
│                                                                          │
│  /api/v1/agent/                                                          │
│  ├── POST /execute           (async job-based, returns job_id)           │
│  ├── GET  /jobs/{job_id}     (poll job status + results)                 │
│  ├── POST /stream            (SSE streaming alternative)                 │
│  ├── POST /confirm/{job_id}  (resume human-in-the-loop)                  │
│  ├── GET  /threads           (list agent threads)                        │
│  ├── GET  /threads/{id}/messages  (thread messages)                      │
│  ├── GET  /graph/mermaid     (graph structure visualization)             │
│  ├── GET  /graph/trace/{id}  (execution trace as sequence diagram)       │
│  └── GET  /health            (health check)                              │
│                                                                          │
│  LangGraph StateGraph:                                                   │
│  ├── rag_node                (hybrid search retrieval)                   │
│  ├── intent_classifier_node  (keyword-weighted routing)                  │
│  ├── memory_retrieval_node   (cross-conversation memory)                 │
│  ├── [subgraph routing]      (research | writing | data | general)       │
│  ├── tool_node               (parallel execution, semaphore(3))          │
│  ├── interrupt_node          (human-in-the-loop for destructive tools)   │
│  └── memory_save_node        (persist learnings)                         │
│                                                                          │
│  Persistence:                                                            │
│  ├── AsyncPostgresSaver      (LangGraph checkpoint persistence)          │
│  ├── InMemoryStore           (cross-conversation memory)                 │
│  ├── Thread                  (rag_document_scope={"source":"agent"})     │
│  ├── ChatMessage             (user + assistant + tool messages)           │
│  └── Conversation            (parent container)                          │
└──────────────────────────────────────────────────────────────────────────┘
```

## LangGraph Agent Graph

### Graph Flow

```
START
  → rag_node (hybrid search: keyword + semantic, up to 5 docs)
  → intent_classifier_node (weighted keyword classification)
  → memory_retrieval_node (search InMemoryStore for past interactions)
  → [CONDITIONAL ROUTE by intent]
      ├→ research_subgraph (paper discovery, ingestion)
      ├→ writing_subgraph (content creation, synthesis)
      ├→ data_subgraph (entity extraction, knowledge graph)
      └→ llm_node (general QA with full tool binding)
  → [CONDITIONAL CHECK: should_continue]
      ├→ interrupt_node (human-in-the-loop for destructive actions)
      ├→ tool_node (parallel tool execution, max 3 concurrent)
      └→ memory_save_node (persist query + intent + tools_used)
  → END
```

### Intent Classification

Weighted keyword-based routing (not LLM-dependent):

| Intent               | Keywords                                                                            | Tools Available                                                                                      |
| -------------------- | ----------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `research`           | search, find, look up, discover, ingest, import, arxiv, paper                       | search_arxiv, ingest_arxiv_papers, search_documents, add_document_to_project, list_project_documents |
| `writing`            | write, draft, summarize, create note, literature review, export, bibliography, cite | create_draft, create_project_note, export_bibliography, summarize_document, compare_documents        |
| `knowledge_graph`    | extract entities, knowledge graph, entity, relationship, ontology                   | extract_entities, search_knowledge_graph, search_documents, list_project_documents                   |
| `general` (fallback) | —                                                                                   | All 12 tools                                                                                         |

Priority for tie-breaking: writing > knowledge_graph > research.

### State Schema

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]  # LangChain message reducer
    page_context: dict                       # Current UI context
    retrieved_contexts: list                 # RAG results
    tool_executions: list                    # Execution history
    thread_id: str                           # Conversation persistence
    tool_loop_count: int                     # Loop tracking (max 10)
    error_count: int                         # Error threshold (max 3)
    last_error: str
    pending_confirmation: dict               # Human-in-the-loop
    user_confirmed: bool
    intent: str                              # Classified intent
    user_memories: list                      # Cross-conversation memory
```

### Subgraphs

Each subgraph uses `make_filtered_tool_node()` to restrict tools. Out-of-scope tool calls return a descriptive error.

**Research Subgraph** (`subgraphs/research_agent.py`):

- Max 8 tool calls per session
- Guides LLM to use `document_ids` (UUIDs) from ingest response, NOT arXiv paper IDs

**Writing Subgraph** (`subgraphs/writing_agent.py`):

- Calls DraftGenerationService for async draft generation
- Uses fresh `AsyncSessionLocal()` for drafts to avoid rollback conflicts

**Data Subgraph** (`subgraphs/data_agent.py`):

- Entity extraction via transformer NER models (EntityExtractor)
- Knowledge graph traversal via Neo4j (KnowledgeGraphService)

## Tools (12 Total)

| Tool                      | Subgraph | Purpose                                              |
| ------------------------- | -------- | ---------------------------------------------------- |
| `search_arxiv`            | research | Query arXiv with optional category filters           |
| `ingest_arxiv_papers`     | research | Download & index papers into RAG (destructive)       |
| `search_documents`        | general  | Full-text search user's indexed documents            |
| `add_document_to_project` | research | Link document to research project (destructive)      |
| `list_project_documents`  | research | Enumerate project documents                          |
| `create_project_note`     | writing  | Create markdown note in project (destructive)        |
| `summarize_document`      | writing  | LLM-based document summarization                     |
| `compare_documents`       | writing  | Compare 2-5 docs for similarities/themes             |
| `create_draft`            | writing  | Generate literature review from themes (destructive) |
| `export_bibliography`     | writing  | Format citations (bibtex/apa/ieee/mla)               |
| `extract_entities`        | data     | NER extraction from document text                    |
| `search_knowledge_graph`  | data     | Query Neo4j for entities & relationships             |

**Execution details:**

- Parallel execution with `asyncio.Semaphore(3)` (max 3 concurrent)
- 30-second timeout per tool
- Auto project_id injection from page_context when available
- Error handling records `tool_execution` metadata (id, name, args, status, result, duration_ms)

**Destructive tools** (require human confirmation via `interrupt()`):

- `ingest_arxiv_papers`, `add_document_to_project`, `create_project_note`, `create_draft`

## Human-in-the-Loop

```
Tool call flagged as destructive
    → interrupt_node calls interrupt() from LangGraph
    → Graph state saved to checkpoint
    → Client receives status: "awaiting_confirmation"
    → UI shows ConfirmationCard with tool details

User clicks Confirm/Deny
    → POST /confirm/{job_id} with {"confirmed": true/false}
    → _resume_agent_graph runs in background
    → Command(resume={"confirmed": true/false}) unpauses graph
    → If confirmed: tool executes normally
    → If denied: graph returns denial message
```

## Execution Modes

### 1. Job-Based (Polling)

```
POST /execute → {job_id} → GET /jobs/{job_id} (poll) → {status, result}
```

Job statuses: `running` → `awaiting_confirmation` | `completed` | `failed`

### 2. SSE Streaming

```
POST /stream → Server-Sent Events
```

Event types:

- `token` — Streamed text chunks
- `tool_start` — Tool execution begins (includes tool name + args)
- `tool_end` — Tool execution completes (includes result + duration)
- `rag_context` — Retrieved document contexts
- `done` — Stream complete (includes full response)
- `error` — Error occurred

5-minute timeout. Messages persisted after stream completes.

## UI Modes

### 1. Closed (default)

- Only the **FAB button** (Bot icon) is visible, fixed bottom-right
- Unread badge appears when assistant responds while closed
- Open with click or **Cmd+K** / **Ctrl+K**

### 2. Panel Mode

- 400x560px floating panel above the FAB
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
┌─ agentChatStore.sendMessage() ────────────────────────────┐
│  1. Validate: non-empty, not already streaming            │
│  2. Create user AgentMessage, push to messages[]          │
│  3. Clear input, set isStreaming = true                   │
│  4. Build API payload (filter to user/assistant only)     │
│  5. Choose: SSE streaming or job-based polling            │
└───────────────────────┬───────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        ▼                               ▼
┌─ SSE Streaming ──────┐   ┌─ Job-Based Polling ───────────┐
│  POST /stream         │   │  POST /execute → {job_id}     │
│  Events:              │   │  Poll GET /jobs/{job_id}       │
│  ├── token → append   │   │  Until: completed | failed     │
│  ├── tool_start       │   │  Or: awaiting_confirmation     │
│  ├── tool_end         │   │  → Show ConfirmationCard       │
│  ├── rag_context      │   │  → POST /confirm/{job_id}      │
│  └── done → finalize  │   │  → Continue polling            │
└───────────┬───────────┘   └──────────────┬────────────────┘
            └───────────────┬──────────────┘
                            ▼
┌─ agentChatStore (response handling) ──────────────────────┐
│  1. Create assistant AgentMessage with:                   │
│     ├── content (AI response text)                        │
│     ├── citations (from retrieved_contexts)               │
│     └── toolExecutions (from tool_executions)             │
│  2. Push to messages[], set isStreaming = false            │
│  3. Set activeThreadId from response                      │
│  4. If panel closed → set hasUnread = true                │
└───────────────────────────────────────────────────────────┘
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

Context is injected into the LLM system prompt and passed through the graph state so tools can auto-fill `project_id`.

## Checkpointing & Memory

### Checkpointing

- **Primary**: `AsyncPostgresSaver` from `langgraph-checkpoint-postgres`
- **Fallback**: `MemorySaver` if Postgres unavailable
- Normalizes DATABASE_URL: `postgresql+asyncpg://` → `postgresql://` (psycopg v3 requirement)
- Auto-creates checkpoint tables on first init

### Cross-Conversation Memory

- **memory_retrieval_node**: Searches InMemoryStore for past interactions relevant to current query
- **memory_save_node**: Persists condensed memories with MD5 hash of query as key
- Stores: query, intent, tools_used (last 3)
- Backend: LangGraph Store abstraction (swappable: InMemoryStore → PostgreSQL-backed)

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
    → Save user + assistant messages (with tool_executions as JSON)
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

Start an async agent execution job.

**Request:**

```json
{
  "messages": [{ "role": "user", "content": "Find papers about transformers" }],
  "page_context": {
    "type": "project",
    "project_id": "uuid",
    "project_name": "My Research"
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

**Response (202):**

```json
{
  "job_id": "uuid",
  "status": "running"
}
```

### GET /api/v1/agent/jobs/{job_id}

Poll job status and retrieve results.

**Response:**

```json
{
  "status": "completed",
  "result": {
    "message": { "role": "assistant", "content": "Based on your documents..." },
    "model": "gpt-4o",
    "usage": {},
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
    "tool_executions": [
      {
        "id": "uuid",
        "tool_name": "search_arxiv",
        "status": "completed",
        "args": { "query": "transformer architecture" },
        "result": "Found 5 papers...",
        "duration_ms": 1200
      }
    ],
    "thread_id": "uuid",
    "conversation_id": "uuid"
  },
  "confirmation": null
}
```

When `status` is `"awaiting_confirmation"`:

```json
{
  "status": "awaiting_confirmation",
  "result": null,
  "confirmation": {
    "tools": ["ingest_arxiv_papers"],
    "message": "The agent wants to ingest 3 arXiv papers. Proceed?"
  }
}
```

### POST /api/v1/agent/confirm/{job_id}

Resume an interrupted graph after human decision.

**Request:**

```json
{
  "confirmed": true
}
```

**Response (202):**

```json
{
  "status": "running"
}
```

### POST /api/v1/agent/stream

SSE streaming alternative to job polling.

**Request:** Same as `/execute`.

**Response:** Server-Sent Events stream.

```
event: rag_context
data: {"contexts": [...]}

event: token
data: {"content": "Based on "}

event: tool_start
data: {"tool_name": "search_arxiv", "args": {"query": "transformers"}}

event: tool_end
data: {"tool_name": "search_arxiv", "status": "completed", "result": "...", "duration_ms": 1200}

event: token
data: {"content": "your documents..."}

event: done
data: {"message": {...}, "thread_id": "uuid", "tool_executions": [...]}
```

Timeout: 5 minutes.

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
      ],
      "tool_executions": [
        {
          "id": "uuid",
          "tool_name": "search_arxiv",
          "status": "completed",
          "duration_ms": 800
        }
      ]
    }
  ],
  "total": 2
}
```

### GET /api/v1/agent/graph/mermaid

Returns the graph structure as a Mermaid diagram string.

### GET /api/v1/agent/graph/trace/{thread_id}

Returns the execution trace for a specific thread as a Mermaid sequence diagram.

### GET /api/v1/agent/health

Health check endpoint.

## Frontend Components

| Component           | File                                          | Purpose                                                            |
| ------------------- | --------------------------------------------- | ------------------------------------------------------------------ |
| `GlobalAgentChat`   | `components/agent-chat/GlobalAgentChat.tsx`   | Root: mounts FAB + panel/sidebar, keyboard shortcuts, context sync |
| `AgentFAB`          | `components/agent-chat/AgentFAB.tsx`          | Floating action button with unread badge                           |
| `AgentPanel`        | `components/agent-chat/AgentPanel.tsx`        | Compact panel: header + context + messages + input                 |
| `AgentPanelHeader`  | `components/agent-chat/AgentPanelHeader.tsx`  | Panel header with new/clear/expand/close buttons                   |
| `AgentContextBar`   | `components/agent-chat/AgentContextBar.tsx`   | Shows auto-detected page context                                   |
| `AgentMessageList`  | `components/agent-chat/AgentMessageList.tsx`  | Scrollable message display with thinking indicator                 |
| `AgentMessageItem`  | `components/agent-chat/AgentMessageItem.tsx`  | Individual message bubble (user/assistant)                         |
| `ToolExecutionCard` | `components/agent-chat/ToolExecutionCard.tsx` | Expandable card showing running/completed tool calls               |
| `ConfirmationCard`  | `components/agent-chat/ConfirmationCard.tsx`  | Human-in-the-loop confirmation UI                                  |
| `AgentInput`        | `components/agent-chat/AgentInput.tsx`        | Auto-resizing textarea with send button                            |
| `AgentSidebar`      | `components/agent-chat/AgentSidebar.tsx`      | Expanded mode: thread list + chat area                             |
| `AgentThreadList`   | `components/agent-chat/AgentThreadList.tsx`   | Thread list with loading/empty states                              |
| `CitationBadge`     | `components/agent-chat/CitationBadge.tsx`     | Inline citation reference badges                                   |

## State Management

**Store:** `useAgentChatStore` (Zustand + Immer)

| State Field           | Type                               | Description                |
| --------------------- | ---------------------------------- | -------------------------- |
| `uiMode`              | `'closed' \| 'panel' \| 'sidebar'` | Current UI mode            |
| `activeThreadId`      | `string \| null`                   | Active conversation thread |
| `threads`             | `AgentThread[]`                    | Thread list for sidebar    |
| `messages`            | `AgentMessage[]`                   | Messages in current thread |
| `isStreaming`         | `boolean`                          | Whether AI is responding   |
| `inputValue`          | `string`                           | Current input text         |
| `hasUnread`           | `boolean`                          | Unread notification badge  |
| `pageContext`         | `PageContext`                      | Auto-detected page context |
| `pendingConfirmation` | `PendingConfirmation \| null`      | Awaiting human decision    |

**Key methods:** `sendMessage`, `loadThreads`, `confirmAction`, `retryLastMessage`

**Types** (`frontend/src/types/agent-chat.ts`):

- `AgentMessage`: id, role, content, timestamp, citations, toolExecutions, isError
- `ToolExecution`: id, toolName, status (running|completed|failed), result, durationMs
- `PendingConfirmation`: jobId, tools[], message
- `PageContext`: type, projectId, projectName, metadata
- `AgentUIMode`: `'closed' | 'panel' | 'sidebar'`

## Observability

### LangSmith Integration

Auto-enabled if `LANGCHAIN_API_KEY` is set. Project name: `rag-agent`. Uses LangGraph's built-in tracing.

### Prometheus Metrics

| Metric                             | Type      | Labels            |
| ---------------------------------- | --------- | ----------------- |
| `agent_execution_duration_seconds` | Histogram | intent, status    |
| `agent_tool_calls_total`           | Counter   | tool_name, status |
| `agent_token_usage_total`          | Counter   | model, type       |
| `agent_errors_total`               | Counter   | error_type        |

Decorator: `@track_node_execution(node_name)` for timing & error tracking.

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
- **Tool confirmation**: Destructive tools require explicit human approval via interrupt

## Error & Recovery

- **Max errors**: 3 accumulated errors → graph stops gracefully
- **Tool timeout**: 30 seconds per tool
- **Max tool loops**: 10 per session (prevents infinite loops)
- **Savepoint transactions**: Nested `async with db.begin_nested()` for tool side-effects survive rollbacks
- **Job cleanup**: OrderedDict with max 500 jobs (FIFO eviction)

## Database Schema

```
Workspace (owner_id → User)
└── Conversation (workspace_id, title="Agent Chat")
    └── Thread (conversation_id, rag_document_scope={"source":"agent"})
        ├── ChatMessage (role=USER, content, user_id)
        ├── ChatMessage (role=ASSISTANT, content, model_name, tool_executions JSON)
        └── ChatMessage (role=TOOL, tool_name, tool_call_id)

LangGraph Checkpoints (auto-created by AsyncPostgresSaver)
├── checkpoints (thread_id, checkpoint_id, state)
└── checkpoint_writes (thread_id, task_id, channel, value)
```

No new application tables — reuses existing chat schema with the `{"source": "agent"}` marker. LangGraph manages its own checkpoint tables.

## Configuration

**`backend/langgraph.json`:**

```json
{
  "dependencies": ["."],
  "graphs": {
    "agent": "./src/services/agent/graph.py:compile_agent_graph"
  },
  "env": "../.env"
}
```

**LLM Settings:**

- Model: gpt-4o or gpt-4o-mini (configurable per request)
- Temperature: 0.7
- Max tokens: 2048

## Files

### Backend

- `backend/src/services/agent/graph.py` — Main LangGraph StateGraph definition
- `backend/src/services/agent/state.py` — AgentState TypedDict
- `backend/src/services/agent/tools.py` — 12 tool definitions (LangChain `@tool`)
- `backend/src/services/agent/memory.py` — Cross-conversation memory (InMemoryStore)
- `backend/src/services/agent/checkpointer.py` — AsyncPostgresSaver / MemorySaver
- `backend/src/services/agent/observability.py` — LangSmith + Prometheus metrics
- `backend/src/services/agent/subgraphs/research_agent.py` — Research subgraph
- `backend/src/services/agent/subgraphs/writing_agent.py` — Writing subgraph
- `backend/src/services/agent/subgraphs/data_agent.py` — Data subgraph
- `backend/src/api/agent/execute.py` — All endpoints + tool implementations
- `backend/langgraph.json` — LangGraph CLI config

### Frontend

- `frontend/app/(dashboard)/layout.tsx` — Mounts `GlobalAgentChat` globally
- `frontend/src/components/agent-chat/*.tsx` — 13 UI components
- `frontend/src/hooks/usePageContext.ts` — Page context detection
- `frontend/src/store/agentChatStore.ts` — Zustand + Immer store
- `frontend/src/services/agentChatService.ts` — API client
- `frontend/src/types/agent-chat.ts` — TypeScript types

### Tests

- `backend/tests/unit/services/test_agent_bugfixes.py` — Bug fix regression tests
- `backend/tests/unit/services/test_agent_deepeval.py` — LLM evaluation via DeepEval
- `backend/tests/unit/services/test_agent_eval_dataset.py` — Evaluation dataset construction
- `backend/tests/unit/services/test_agent_graph_partial.py` — Partial graph execution & state
- `backend/tests/unit/services/test_agent_integration.py` — End-to-end agent workflows
- `backend/tests/unit/services/test_agent_langsmith.py` — LangSmith tracing integration

Test markers: `@unit`, `@integration`, `@e2e`, `@performance`, `@deepeval`, `@langsmith`
