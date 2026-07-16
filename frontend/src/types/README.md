# `src/types/` — Shared TypeScript type definitions

This directory holds all TypeScript interfaces, enums, and Zod schemas used
across the NOUS frontend. Most modules here are still authored by hand against
the FastAPI backend, so keeping them in sync with backend Pydantic models is a
manual discipline: field names follow the backend's snake_case convention, and
any backend schema change must be reflected here.

**Generated types (`generated/api.d.ts`).** As of the audit C5 REST contract
ratchet, request/response shapes can instead be sourced from the backend's
OpenAPI schema via `openapi-typescript`. Run `pnpm generate:api-types` to
rebuild `generated/api.d.ts` from `backend/openapi.json`, and reference schemas
as `components['schemas'][...]`. CI fails if the committed `backend/openapi.json`
drifts from the running app (see `generated/README.md`), so a contract change
and its regenerated types travel together in the same PR. Hand-written modules
migrate **adopt-on-touch**, not all at once: touching a file that owns an
HTTP request/response shape is the trigger to alias it from
`components['schemas'][...]` instead of re-typing it by hand. Adopters so
far: `services/documentAnalyticsApi.ts` (`DocumentStatusResponse`) and
`services/workspaceService.ts` (`types/api/workspace-contract.ts`, re-exported
as compatible domain names from `types/workspace.ts` so existing
store/component imports don't need to change). Where a generated field is
looser than the frontend needs (e.g. a JSONB passthrough column typed as
`Record<string, unknown>[]`) or stricter than the wire contract actually
requires (`openapi-typescript`'s `defaultNonNullable` marks any backend field
with a Pydantic default as required, even though the client may still omit
it), narrow or relax it with an explicit derived type — see the comments in
`types/workspace.ts` for worked examples — never `as unknown as`.

To regenerate after a backend schema change:

```sh
python scripts/ci/generate_openapi.py   # refresh backend/openapi.json
pnpm --dir frontend generate:api-types  # rebuild generated/api.d.ts from it
```

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

**Backend parity.** Types in `document.ts`, `entity.ts`, and `search.ts` are
still hand-mirrored against Pydantic schemas in `backend/src/schemas/`; a
backend schema change must be reflected here in the same PR. `workspace.ts`
has migrated to the adopt-on-touch pattern above — its request/response types
are derived from `generated/api.d.ts` rather than hand-mirrored, so they stay
correct automatically as long as `generated:api-types` is re-run. Where a
field exists under two names in a still-hand-written module (e.g. `file_type`
/ `document_type`, `upload_timestamp` / `created_at`) both are present as
optional to handle the backend's response variations without silent
coercions.

**Runtime validation.** `schemas.ts` provides Zod schemas for the API
boundaries where the backend contract must be verified at runtime (upload
responses, auth tokens, search results). Types are inferred from these schemas
rather than duplicated. All other files contain pure TypeScript interfaces with
no runtime cost.

**Upload field mapping.** `schemas.ts` documents the `FileUploadResponseSchema`
(raw backend shape) versus `DocumentUploadResponseSchema` (transformed frontend
shape) explicitly — the `id` → `upload_id` rename is noted in comments.

**Generated types, adopt-on-touch.** This directory is a mix of generated and
handwritten types, not all handwritten — see the "Generated types" section
above. If you're touching a module that owns an HTTP request/response shape,
adopt the generated alias instead of hand-updating the interface; don't add
new hand-duplicated interfaces for shapes the backend already exposes via
OpenAPI. Modules not yet migrated remain handwritten in the meantime, kept in
sync with `backend/src/schemas/` by manual discipline (see "Backend parity"
above) until they're next touched.
