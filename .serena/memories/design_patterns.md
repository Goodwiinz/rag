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
Custom dark theme for specialized pages (e.g., ArXiv):
- `PHOSPHOR_GREEN = '#00ff9f'`
- `AMBER = '#ffb700'`
- `CYAN = '#00d4ff'`
- Dark terminal chrome container
- Monospace typography
