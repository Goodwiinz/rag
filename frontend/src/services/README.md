# Services

This directory is the frontend's API client layer. Every call to the FastAPI backend goes through here — no component or store should reach `fetch` directly. All modules import the singleton `api` from `api-client.ts` and compose typed request/response methods on top of it.

## Key files

| File                            | Purpose                                                                                                                                                                                             |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `api-client.ts`                 | Core `APIClient` class — all HTTP verbs, auth injection, retry with exponential backoff, file upload with optional XHR progress, blob/object-URL fetch. Exported as singleton `api`.                |
| `agentChatService.ts`           | LangGraph agent interactions: job-based execute (`POST /api/v1/agent/execute`), SSE streaming (`streamMessage`, `streamConfirm`), thread listing/messages. Single active chat path.                 |
| `documentService.ts`            | CRUD and upload for `/api/v1/documents/` — single-file and multi-file upload (XHR for per-file progress), list/filter, status polling.                                                              |
| `uploadService.ts`              | Queue-based upload manager with per-item state (`pending`→`completed`), speed tracking, and batch coordination on top of `documentService`.                                                         |
| `searchService.ts`              | Hybrid search (`/api/v1/search/`), query history, suggestions, KG graph data. Maps backend snake_case responses to frontend types.                                                                  |
| `graphService.ts`               | Knowledge graph read and write (`/api/v1/graph/`) — entity nodes, edges, layout, analytics. Delegates all computation to the backend.                                                               |
| `entityService.ts`              | Entity CRUD with a local one-retry wrapper around `api` for transient failures.                                                                                                                     |
| `projectService.ts`             | Research project CRUD (`/api/v1/projects/`).                                                                                                                                                        |
| `workspaceService.ts`           | Workspace, collection, thread, and conversation CRUD (`/api/v2/workspaces/`).                                                                                                                       |
| `researchEngineService.ts`      | Research engine blueprints and runs (`/api/v1/research-engine/`).                                                                                                                                   |
| `scispaceService.ts`            | Extraction matrix, table extraction, tone rewriting, integrity detection (`/research/`). Long-running write and extraction calls use `{ timeout: 300000 }` (5 min).                                 |
| `ragService.ts`                 | RAG context retrieval for in-browser (WebLLM) models — token-budget management and citation formatting, adapts to model size (small/medium/large/cloud).                                            |
| `citationService.ts`            | Citation save/list/delete for research documents.                                                                                                                                                   |
| `threadSearchService.ts`        | Full-text search scoped to a thread's message history.                                                                                                                                              |
| `websocket.ts`                  | `WebSocketManager` — connects with `Sec-WebSocket-Protocol: ['auth', token]` (not URL query param); handles reconnect up to 5 attempts. Used for document-processing and query-status push updates. |
| `websocketService.ts`           | Thin wrapper that initialises `WebSocketManager` from the auth store.                                                                                                                               |
| `realtime-websocket-service.ts` | Realtime collaboration events over WebSocket.                                                                                                                                                       |
| `realtimeWebSocketService.ts`   | Alternate realtime service used by workspace components.                                                                                                                                            |
| `monitoringWebsocketService.ts` | Admin monitoring feed over WebSocket.                                                                                                                                                               |
| `analyticsService.ts`           | Usage and document analytics (`/api/v1/analytics/`).                                                                                                                                                |
| `documentAnalyticsApi.ts`       | Document-level analytics calls distinct from general analytics.                                                                                                                                     |
| `graphAnalyticsService.ts`      | Graph-specific analytics (centrality, communities) via the analytics backend.                                                                                                                       |
| `evaluationService.ts`          | RAG evaluation metrics.                                                                                                                                                                             |
| `diagnosticsService.ts`         | Health and diagnostic endpoints for admin views.                                                                                                                                                    |
| `loggingService.ts`             | Client-side structured log shipping to the backend.                                                                                                                                                 |
| `export-service.ts`             | Document/note export (PDF, Markdown, etc.).                                                                                                                                                         |
| `featureFlags.tsx`              | Feature flag context and hooks — reads from `/api/v1/feature-flags/`.                                                                                                                               |
| `nousCliAuth.ts`                | Auth token exchange for the NOUS CLI (desktop companion).                                                                                                                                           |
| `projectChatService.ts`         | Chat completions scoped to a project context.                                                                                                                                                       |
| `mockDocumentService.ts`        | Drop-in mock of `documentService` for tests and Storybook.                                                                                                                                          |
| `streamingService.ts`           | **Deprecated.** Old v2 SSE path (`/api/v2/threads/{id}/stream`). Do not add new callers; use `agentChatService.streamMessage`.                                                                      |

## HTTP client conventions

`APIClient` (singleton `api`) is constructed with `API_CONFIG.BASE_URL`, derived from `NEXT_PUBLIC_API_BASE_URL`. The default request timeout is 30 s (`API_CONFIG.TIMEOUT_MS`). Every request calls `ensureAuth()`, which reads the current Supabase session via `getSession()` rather than caching the token — this keeps the token fresh across refreshes and sign-outs.

Headers attached to every authenticated request:

```
Authorization: Bearer <supabase_access_token>
Content-Type: application/json       // omitted for FormData
```

The backend derives the tenant/organization from the authenticated user
(`current_user`), so no `X-Organization-ID` header is sent — it was never read
inbound.

For `FormData` bodies (file upload), the client strips `Content-Type` so the browser sets `multipart/form-data` with its own boundary. Upload progress uses `XMLHttpRequest.upload.onprogress`; blob/inline-preview uses `fetchObjectUrl`, which returns an object URL the caller must revoke.

Retries use exponential backoff (default 3 attempts, starting at 1 s). 4xx errors (except 429) are not retried; 5xx and 429 are.

**Long-timeout calls (5 min / 300 000 ms):** arXiv ingest and SciSpace write/extraction calls pass `{ timeout: 300000 }` to `api.post`. Do not use the default client for these.

## SSE streaming

`agentChatService.streamMessage` POSTs to `/api/v1/agent/stream`. It reads the response body as a `ReadableStream`, splits on newlines, and dispatches by `event:` field:

| Event          | Callback                                 |
| -------------- | ---------------------------------------- |
| `token`        | `onToken(content)`                       |
| `tool_start`   | `onToolStart(tool, args)`                |
| `tool_end`     | `onToolEnd(tool, result, isError)`       |
| `rag_context`  | `onRagContext(contexts)`                 |
| `plan`         | `onPlan(steps, reasoning)`               |
| `reflection`   | `onReflection(passed, issues, round)`    |
| `confirmation` | `onConfirmation(threadId, confirmation)` |
| `trace`        | `onTrace(threadId)`                      |
| `done`         | `onDone()`                               |
| `error`        | `onError(message)`                       |

`streamConfirm` uses the same SSE pattern against `/api/v1/agent/stream/confirm` to resume a human-in-the-loop interrupt. Both methods handle `AbortError` silently (cancelled by the caller) and surface the backend `detail` field when the response is not ok.

## WebSocket auth

Browser WebSocket does not allow custom headers. Authentication is passed via the `Sec-WebSocket-Protocol` subprotocol field:

```ts
new WebSocket(url, ['auth', token]);
```

The backend reads the second subprotocol value as the bearer token. The `organization_id` travels as a URL search parameter (non-sensitive). Do not move the token to the URL — it would appear in server logs.
