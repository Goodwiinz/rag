# `src/types/` — Shared TypeScript type definitions

This directory holds all TypeScript interfaces, enums, and Zod schemas used
across the NOUS frontend. Types are authored by hand against the FastAPI backend;
there is no code-generation step. Keeping them in sync with backend Pydantic
models is a manual discipline: field names follow the backend's snake_case
convention, and any backend schema change must be reflected here.

`index.ts` is the public re-export barrel. Prefer importing from `@/types`
rather than from individual modules.

---

## Type modules

| File                     | Domain                          | Key exports                                                                                                                                                               |
| ------------------------ | ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `api.ts`                 | HTTP infrastructure             | `APIResponse<T>`, `APIError`, `APIErrorClass`, `API_CONFIG`                                                                                                               |
| `auth.ts`                | Authentication                  | `User`, `Organization`, `AuthState`, `LoginRequest`, `RegisterRequest`                                                                                                    |
| `document.ts`            | Document management             | `Document`, `DocumentUpload`, `DocumentListResponse`, `DocumentFilters`, `UploadProgress`                                                                                 |
| `upload.ts`              | Upload pipeline                 | `UploadJob`, `UploadSession`, `ProcessingStep`, `QualityMetrics`, `UploadWebSocketMessage`                                                                                |
| `search.ts`              | RAG query + hybrid search       | `SearchRequest`, `SearchResult`, `SearchAnswer`, `SourceReference`, `Entity`, `Relationship`, `HybridSearchConfig`, `QueryIntent`, `QueryRewrite`, `QueryProcessingState` |
| `entity.ts`              | Knowledge graph entities        | `EntityType` (UPPER_CASE enum), `RelationshipType`, `Entity`, `GraphEdge`, `EntityResponse`, `CreateEntityRequest`, `GraphSearchRequest`, `EntityPermissions`             |
| `knowledge-graph.ts`     | KG visualization + analytics    | `KnowledgeGraphData`, `GraphNode`, `GraphEdge`, `GraphLayout`, `NodeAnalytics`, `GraphAnalyticsDashboard`, `GraphVisualizationState`, `WebSocketGraphUpdate`              |
| `graph-api.ts`           | Graph service API contracts     | `GraphLayoutData`, `CentralityMetrics`, `CommunityAnalytics`, `PathAnalytics`, `GraphDashboard`, `VisualizationConfig`, `ImportResult`                                    |
| `workspace.ts`           | Workspace + threads + chat      | `Workspace`, `Conversation`, `Thread`, `ChatMessage`, `Citation`, `ChatCompletionRequest`, `StreamingChatChunk`, `WorkspaceRole` (enum)                                   |
| `thread-search.ts`       | Full-text thread/message search | `ThreadSearchRequest`, `ThreadSearchResponse`, `MessageSearchResult`, `CombinedSearchResult`, `SearchHealthResponse`                                                      |
| `agent-chat.ts`          | Global agent chat overlay       | `AgentMessage`, `AgentThread`, `ToolExecution`, `AgentChatState`, `AgentChatActions`, `PendingConfirmation`, `PlanStep`, `PageContext`                                    |
| `research.ts`            | Research assistant              | `CitationCreate`, `CitationResponse`, `ProjectResponse`, `NoteResponse`, `DraftResponse`, `DraftComparisonResponse`                                                       |
| `schemas.ts`             | Zod runtime validators          | `DocumentSchema`, `UserSchema`, `SearchResultSchema`, `GraphDataSchema`, `EvaluationMetricsSchema` — types inferred via `z.infer<>`                                       |
| `evaluation.ts`          | RAG quality metrics             | Evaluation and metrics types                                                                                                                                              |
| `evidence.ts`            | Evidence provenance             | Evidence and claim types                                                                                                                                                  |
| `chat.ts`                | Generic assistant chat          | `Assistant`, `ChatSession`, `ChatMessage`, `ChatPreferences`, `ASSISTANT_CATEGORIES`                                                                                      |
| `chat-widget.ts`         | Embedded chat widget            | Widget-specific state and config                                                                                                                                          |
| `llm-chat.ts`            | LLM completion wrappers         | Completion request/response types                                                                                                                                         |
| `project-chat.ts`        | Project-scoped chat             | Project chat state types                                                                                                                                                  |
| `analytics.ts`           | Observability + tracking        | `AnalyticsConfig`, `AnalyticsProvider`, React analytics context                                                                                                           |
| `monitoring.ts`          | System monitoring               | Service health and metric types                                                                                                                                           |
| `realtime-processing.ts` | Streaming processing state      | Real-time pipeline event types                                                                                                                                            |
| `scispace.ts`            | SciSpace integration            | Academic search and paper types                                                                                                                                           |
| `ui.ts`                  | Application UI state            | `UIState`, `LayoutConfig`, `WebSocketMessage`, document processing updates                                                                                                |
| `constants.ts`           | Typed constants                 | `UPLOAD_LIMITS`, `UI_CONFIG`, `PERFORMANCE_THRESHOLDS`, `ENTITY_TYPE_COLORS`, `STATUS_COLORS`                                                                             |
| `modules.d.ts`           | Module declarations             | Ambient type overrides for untyped packages                                                                                                                               |

---

## Conventions

**Naming.** Interfaces and type aliases use PascalCase (`ChatMessage`,
`SearchResult`). String literal unions and `const` enums use the casing that
matches the API wire format — snake_case for backend-mirrored fields, camelCase
for frontend-only state. `entity.ts` uses UPPER_CASE string literals for
`EntityType` and `RelationshipType` to match Neo4j node labels; `search.ts`
uses lowercase for the same concept because that API endpoint returns lowercase.
Both shapes coexist deliberately.

**Backend parity.** Types in `document.ts`, `workspace.ts`, `entity.ts`, and
`search.ts` mirror Pydantic schemas in `backend/src/schemas/`. Where a field
exists under two names (e.g. `file_type` / `document_type`, `upload_timestamp`
/ `created_at`) both are present as optional to handle the backend's response
variations without silent coercions.

**Runtime validation.** `schemas.ts` provides Zod schemas for the API
boundaries where the backend contract must be verified at runtime (upload
responses, auth tokens, search results). Types are inferred from these schemas
rather than duplicated. All other files contain pure TypeScript interfaces with
no runtime cost.

**Upload field mapping.** `schemas.ts` documents the `FileUploadResponseSchema`
(raw backend shape) versus `DocumentUploadResponseSchema` (transformed frontend
shape) explicitly — the `id` → `upload_id` rename is noted in comments.

**No generated types.** Unlike projects that run `openapi-typescript` or
`prisma generate`, all types here are handwritten. When the FastAPI backend
changes a schema, the corresponding interface in this directory must be updated
in the same PR.
