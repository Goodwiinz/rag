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