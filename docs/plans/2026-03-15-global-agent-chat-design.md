# Global Agent Chat — Design Document

**Date:** 2026-03-15
**Branch:** feat/global-agent-chat
**Status:** Approved

## Summary

Transform the project-scoped Quick Chat widget into a global AI agent available on every page. The agent auto-detects page context, persists conversations, and executes multi-step workflows across the entire system (projects, ArXiv, documents, notes, knowledge graph).

## Architecture

### Core Principle

Extend existing infrastructure — reuse ChatService, thread/message models, `/chat/completions`, and the FAB+panel UI pattern. No new database tables.

### Two UI Modes

1. **Compact panel** (default) — FAB → 400x560px floating panel for quick questions
2. **Expanded sidebar** — Full-height right sidebar (~420px wide) for deep work, thread history, multi-step workflows

### Component Hierarchy

```
SidebarLayout (dashboard layout — mounted once globally)
└── GlobalAgentChat
    ├── AgentFAB (bottom-right, Cmd+K shortcut, unread badge)
    ├── AgentPanel (compact mode, 400x560px)
    │   ├── PanelHeader — title, expand button, thread selector, close
    │   ├── ContextBar — auto-detected page context + override
    │   ├── MessageList — messages, citations, tool execution cards
    │   └── AgentInput — textarea, send, model indicator
    └── AgentSidebar (expanded mode, ~420px right sidebar)
        ├── SidebarHeader — title, collapse, new thread
        ├── ThreadList — past conversations, search, grouped by date
        ├── ContextBar — same as panel
        ├── MessageList — same as panel, more room
        ├── CitationPanel — expandable source references
        └── AgentInput — textarea, model selector, RAG toggle
```

## Context Detection

A `usePageContext` hook reads the current route and page state:

| Page             | Auto-detected Context                      |
| ---------------- | ------------------------------------------ |
| `/projects/[id]` | Project name, documents, notes, active tab |
| `/chat`          | Current workspace, active thread           |
| `/documents`     | Document library, filters                  |
| `/arxiv`         | Search query/results                       |
| `/research`      | Active research sessions                   |
| `/analytics`     | Dashboard metrics                          |
| Other pages      | Minimal (page name only)                   |

Context injected into system prompt. User can override scope.

## Agent Tool System

Backend endpoint: `POST /api/v1/agent/execute`

Uses OpenAI function-calling format with gpt-4o.

### Tool Categories

| Category       | Tools                                                                    |
| -------------- | ------------------------------------------------------------------------ |
| **Search**     | `search_documents`, `search_arxiv`, `search_knowledge_graph`             |
| **Project**    | `list_projects`, `get_project`, `add_document_to_project`, `create_note` |
| **ArXiv**      | `search_arxiv`, `fetch_paper`, `ingest_papers`                           |
| **Documents**  | `list_documents`, `get_document`, `upload_document`                      |
| **Notes**      | `create_note`, `list_notes`, `save_chat_to_note`                         |
| **Navigation** | `navigate_to`                                                            |
| **Analysis**   | `summarize_document`, `compare_documents`, `extract_entities`            |

Multi-step workflows: LLM chains tool calls sequentially, synthesizes results.

## Data Flow

```
User message → useGlobalAgent hook
  → Inject page context
  → POST /api/v1/agent/execute
    → LLM decides: direct answer or tool calls?

    Direct: RAG retrieval → LLM response → SSE stream
    Tools: Execute tools → Collect results → LLM synthesis → SSE stream

  → Messages persisted to Thread/ChatMessage
  → Tool executions as TOOL role messages
  → Citations as Citation records
```

## Persistence — Existing Schema

| Entity        | Table           | Notes                              |
| ------------- | --------------- | ---------------------------------- |
| Conversations | `Thread`        | `source = 'agent'` to distinguish  |
| Messages      | `ChatMessage`   | User/Assistant/Tool roles          |
| Citations     | `Citation`      | Document references                |
| Project links | `ProjectThread` | Auto-link from project pages       |
| Tool calls    | `ChatMessage`   | role=TOOL, tool_name, tool_call_id |

No new database tables. Thread gets `source` metadata field.

## Keyboard Shortcuts

- `Cmd+K` / `Ctrl+K` — Toggle agent panel
- `Escape` — Close panel/sidebar
- `Cmd+Shift+K` — Toggle expanded sidebar

## Migration from Quick Chat

- `ProjectChatWidget` removed from project page
- `GlobalAgentChat` mounted once in `SidebarLayout`
- Existing project chat threads remain accessible
- Chat tab in project detail unchanged
