# agent-chat components

UI layer for the NOUS LangGraph agent. Distinct from `components/chat/`, which handles the document-centric RAG chat with model selection, slash commands, and citation panels. `agent-chat` drives the agentic interface: SSE streaming from `/api/v1/agent/stream`, live tool-call rendering, human-in-the-loop (HITL) confirmation, and thread management backed by `/api/v1/agent/threads`.

## Key components

| Component               | What it renders                                                                                                                                                                                                                                                  |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GlobalAgentChat`       | Root mount point. Manages the two layout modes (floating panel / side-docked sidebar), drag-to-resize, viewport-aware auto-collapse, and keyboard shortcuts (`Cmd/Ctrl+K`, `Escape`). Reads from `useAgentChatStore`; injects page context via `usePageContext`. |
| `AgentSidebar`          | Side-docked layout: 200 px thread list column + full chat area. Loads thread list on mount; switches active thread via `selectThread` + `loadThreadMessages`.                                                                                                    |
| `AgentPanel`            | Floating panel layout. Thinner chrome than `AgentSidebar`; includes a focus trap for keyboard accessibility.                                                                                                                                                     |
| `AgentMessageList`      | Scrolling message feed. Appends a three-dot thinking indicator when `isStreaming` and the latest assistant message has no content yet. Inlines `ConfirmationCard` at the bottom when `pendingConfirmation` is set.                                               |
| `AgentMessageItem`      | Single message row. User messages render as plain text; assistant messages pass through `AgentMarkdownRenderer`. Renders a collapsible inline execution-plan snapshot (`message.plan`, expanded while streaming) above the content. Batches consecutive identical tool calls into a collapsible `ToolExecutionGroupCard`. Shows copy and retry affordances on hover. |
| `ToolExecutionCard`     | One tool call: status icon (spinner / check / error), display name, duration, collapsible result or error detail.                                                                                                                                                |
| `ConfirmationCard`      | HITL prompt. Amber-bordered card listing the destructive tools about to execute; exposes Confirm / Cancel buttons wired to `confirmAction(true/false)` in the store.                                                                                             |
| `AgentPlanPanel`        | Live execution-plan side panel (full-page sidebar layout only, `lg+`). Renders the `Plan` component read-only; auto-clears when the turn ends. Status mapping shared with the inline plan via `planMapping.ts`.                                                  |
| `AgentMarkdownRenderer` | Markdown with syntax-highlighted code blocks (dynamically loaded Prism) and inline citation badges. When `[N]` patterns are present, segments the content and renders each `[N]` as an `AgentCitationBadge`.                                                     |
| `AgentCitationBadge`    | Inline `[N]` badge with a `HoverCard` showing document title, relevance score, snippet preview, and a link to `/documents/:id`. Score colour shifts green → yellow → red.                                                                                        |
| `AgentContextBar`       | Thin strip below the header showing current page context (project name, document, search, etc.) derived from `usePageContext`. Hidden when context is `unknown`.                                                                                                 |
| `AgentThreadList`       | Scrollable list of past threads with relative timestamps. Skeleton placeholder while loading.                                                                                                                                                                    |
| `AgentInput`            | Auto-grow textarea. Sends on `Enter` (no modifier); `Shift+Enter` inserts a newline. Shows a Stop button while streaming.                                                                                                                                        |
| `AgentFAB`              | Floating action button. Opens the panel; hidden while the sidebar is docked.                                                                                                                                                                                     |
| `AgentPanelHeader`      | Panel-mode header bar: expand-to-sidebar, new thread, clear, close.                                                                                                                                                                                              |

## SSE event handling

Messages are sent via `useAgentChatStore.sendMessage()`, which calls `agentChatService.streamMessage()`. The store processes events as they arrive:

- `token` — appended to the streaming assistant message; a pulsing cursor in `AgentMessageItem` marks the live tail.
- `tool_start` — creates a `ToolExecution` record with `status: 'running'`; triggers the tool-name indicator in the thinking row.
- `tool_end` — updates the record with `status: 'completed' | 'failed'`, result, and duration.
- `rag_context` — attaches `AgentCitation[]` to the message; rendered inline by `AgentMarkdownRenderer` as `[N]` badges.
- `done` — marks `isStreaming = false`, finalises the message.
- `error` — sets `isError = true`; the message row gains a red left border and a Retry button.

SSE is primary; the store falls back to long-poll job status if the SSE connection fails.

## HITL confirmation flow

Destructive tools (`ingest_arxiv_papers`, `add_document_to_project`, `create_project_note`, `create_draft`) trigger an `interrupt()` on the backend. The SSE stream emits a confirmation payload, which the store writes to `pendingConfirmation`. `AgentMessageList` renders a `ConfirmationCard` at the bottom of the feed. On Confirm, the store calls `agentChatService.streamConfirm({ thread_id, confirmed: true })` (with a durable `completeDurableConfirmation` fallback for the polling path); on Cancel, `confirmed: false` aborts the pending action. Nested confirmations (e.g. arXiv ingest confirmed → add-to-project also needs confirm) are handled by re-setting `pendingConfirmation` from within the confirm handler.

## State sources

All live state (messages, streaming flag, active thread, pending confirmation, page context, sidebar width) lives in `useAgentChatStore` (`/store/agentChatStore.ts`), a Zustand store with no persistence except sidebar width (saved to `localStorage`). Thread metadata is fetched from the REST API on sidebar mount. Page context is read from the URL and DOM via `usePageContext` (`/hooks/usePageContext.ts`).
