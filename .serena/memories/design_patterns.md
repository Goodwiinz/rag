# Design Patterns and Guidelines

## Architecture Patterns

### Evaluation-First Development
All features are built with test specifications first:
- Success criteria defined in `src/evaluation/success_criteria.py`
- RAG Triad metrics tracked: Answer Relevancy, Faithfulness, Contextual Relevancy
- DeepEval integration for evaluation benchmarks

### Multi-Agent Architecture
- Agents are specialized: orchestrator, retrieval, graph, vector, QA, synthesis
- Uses CrewAI for agent coordination
- Workflow types: factual_lookup, reasoning, multimodal

### Hybrid Search System
- Parallel execution of vector, graph, and keyword search
- Results combined, deduplicated, and reranked
- Supports filtering by modality and metadata

### Real-time Processing
- WebSocket-based document processing status
- Enterprise-grade connection manager (10,000+ concurrent)
- Event broadcasting with progress tracking

## Backend Patterns

### Service Layer Pattern
- Business logic in `services/` directory
- API handlers delegate to services
- Clear separation of concerns

### Repository Pattern
- Database access through SQLAlchemy models
- Async database sessions with asyncpg

### Middleware Stack
- Request timing
- Logging
- Rate limiting
- CORS handling

## Frontend Patterns

### Component Composition
- Radix UI primitives + shadcn/ui styling
- Compound component pattern for complex UI

### State Management
- Zustand for global state
- TanStack Query for server state
- Local state for component-specific concerns

### API Layer
- Axios client with interceptors
- Centralized error handling
- Type-safe API calls

## Theme: Terminal Observatory
Custom dark theme for specialized pages (Dashboard, Settings, ArXiv):
- `PHOSPHOR_GREEN = '#00ff9f'` - Primary accent
- `AMBER = '#ffb700'` - Warning/secondary accent
- `CYAN = '#00d4ff'` - Info/tertiary accent
- Dark background: `#0a0a0f`
- Dark terminal chrome container with CRT effects
- Monospace typography (JetBrains Mono, system mono)
- Custom toggle switches and form controls
- Consistent across Dashboard, Settings, and ArXiv pages

## Chat Persistence Architecture

### Hierarchy
- **Workspace** → Contains multiple conversations
- **Conversation** → Contains multiple threads
- **Thread** → Contains multiple messages

### State Management
- `chat-store.ts` - Zustand store for chat state
  - Manages workspaces, conversations, threads, messages
  - Handles CRUD operations with backend API
  - Optimistic updates with error recovery

### Bridge Hook Pattern
- `useChatPersistence.ts` - React hook bridging store to UI
  - Maps internal Thread/Message types to UI-friendly formats
  - Provides simplified interface for chat components
  - Handles initialization, message sending, conversation management
  - Auto-creates workspace/conversation/thread as needed

### API Services
- `workspaceService.ts` - Workspace CRUD operations
- Backend endpoints: `/conversations`, `/threads`
- Chat service layer for business logic

## Sidebar Component Pattern
- Collapsible sidebar using shadcn/ui Sidebar primitives
- `group-data-[collapsible=icon]:` classes for collapsed state styling
- Icon centering with `justify-center` in collapsed mode
- Label hiding with `sr-only` class when collapsed

## Session Persistence Pattern (30-day sessions)

### Backend Token Management
- **Access Token**: 30 minutes (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`)
- **Refresh Token**: 7 days default, 30 days with "Remember Me"
- **Config**: `REFRESH_TOKEN_EXPIRE_DAYS`, `REMEMBER_ME_REFRESH_TOKEN_DAYS`
- **Token Rotation**: Refresh tokens are rotated on each refresh for security
- **Key Files**:
  - `backend/src/core/config.py` - Token duration settings
  - `backend/src/core/security.py` - `create_refresh_token(remember_me=True)`
  - `backend/src/services/auth_service.py` - `login_user(remember_me=True)`
  - `backend/src/api/auth.py` - Login endpoint with `remember_me` field

### Frontend Proactive Refresh
- Tokens refresh 5 minutes before expiration (proactive, not reactive)
- Session state persisted in Zustand with localStorage
- On app load, checks token validity and refreshes if needed
- **Key Files**:
  - `frontend/src/stores/authStore.ts` - Session state, proactive refresh timer
  - `frontend/src/hooks/useAuth.tsx` - `login(email, password, rememberMe)`
  - `frontend/src/page-components/auth/LoginPage.tsx` - Remember Me checkbox

### Session Lifecycle
1. User logs in with optional `rememberMe` checkbox
2. Backend issues access token (30min) + refresh token (7/30 days)
3. Frontend stores tokens and schedules proactive refresh
4. 5 minutes before access token expires, frontend refreshes automatically
5. On browser restart, session rehydrates from localStorage
6. If refresh token expired, user is logged out