# Design Patterns

## Backend

### Service Layer
- Business logic in services/ directory
- API handlers delegate to services
- Example: ChatService, DraftGenerationService, AgentService

### Repository/ORM
- SQLAlchemy 2.0 async (asyncpg)
- selectinload/joinedload for relationships accessed outside async context
- Alembic migrations

### Authorization
- _validate_project_ownership() helper: joins + workspace check, returns 404 for both not-found and unauthorized
- Workspace boundary enforcement on all cross-entity lookups

### Agent
- LangGraph StateGraph with compiled subgraphs
- interrupt() for HITL on destructive operations
- DraftGenerationService uses fresh AsyncSessionLocal() to avoid rollback conflicts
- Every AIMessage with tool_calls must have matching ToolMessages (sanitizer adds placeholders)

### Async Processing
- Draft generation: POST returns 202 + task_id, client polls GET /status/{task_id}
- Agent: POST /execute returns job_id, poll or use SSE /stream

## Frontend

### State Management
- Zustand for global state (chat-store, projectStore, evaluationStore)
- TanStack Query v5 for server state
- Local state for component-specific concerns
- Persist middleware for chat store (only IDs, not data)

### Chat Persistence Hierarchy
- Workspace → Conversation → Thread → Message (with Citations)
- Bridge hook pattern: useChatPersistence maps store → UI types
- Stale data recovery: 404 handling with reinit + retry limits

### Component Patterns
- shadcn/ui primitives with NOUS brand theming
- Functional components with TypeScript
- @/* import aliases for src/app paths

### API Layer
- api-client.ts with interceptors
- postWithLongTimeout for ArXiv (5 min)
- Centralized error handling

## Theme: NOUS Brand
- Erebus #0A0A0E (dark bg), Selene #F7F7F5 (light text), Sol #D4A039 (accent)
- Use CSS vars / Tailwind theme classes — NEVER hardcoded hex
- Inter headings, Source Serif 4 body, JetBrains Mono code
