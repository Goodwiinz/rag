# Project Structure

## Root Directory
```
RAG_system/
├── backend/           # Python FastAPI backend
├── frontend/          # Next.js TypeScript frontend
├── tests/             # Root-level test organization
├── docs/              # Documentation
├── config/            # Configuration files
├── scripts/           # Utility scripts
├── k8s/               # Kubernetes manifests
├── terraform/         # Infrastructure as code
├── monitoring/        # Monitoring configuration
├── docker-compose.*.yml  # Docker configurations
└── pyproject.toml     # Python tooling config
```

## Backend Structure (backend/src/)
```
backend/src/
├── api/               # FastAPI route handlers
│   ├── auth.py               # Authentication endpoints
│   ├── documents.py          # Document management
│   ├── search.py             # Search endpoints
│   ├── chat.py               # Chat endpoints
│   ├── conversations.py      # Conversation CRUD (NEW)
│   ├── threads.py            # Thread management (NEW)
│   ├── workspaces.py         # Workspace management
│   ├── arxiv*.py             # ArXiv integration
│   ├── websocket*.py         # WebSocket endpoints
│   ├── realtime_*.py         # Real-time status endpoints
│   └── ...                   # Other API modules
├── auth/              # Authentication & authorization
├── cache/             # Redis caching layer
├── config/            # Configuration management
├── core/              # Core business logic
├── database/          # Database connections & sessions
├── evaluation/        # RAG evaluation with DeepEval
├── exceptions/        # Custom exception handlers
├── health/            # Health check endpoints
├── middleware/        # FastAPI middleware
├── migrations/        # Alembic migrations
├── models/            # SQLAlchemy models
├── monitoring/        # Metrics & monitoring
├── observability/     # OpenTelemetry setup
├── schemas/           # Pydantic schemas
├── security/          # Security utilities
├── services/          # Business services layer
│   ├── chat_service.py       # Chat business logic (NEW)
│   ├── auth_service.py       # Authentication service
│   ├── search_service.py     # Search orchestration
│   ├── embedding_service.py  # Vector embeddings
│   ├── arxiv_service.py      # ArXiv integration
│   └── ...                   # Other services
├── shared/            # Shared utilities
├── storage/           # File storage handlers
├── tasks/             # Celery background tasks
├── utils/             # Utility functions
├── websocket/         # WebSocket handlers
└── main.py            # Application entry point
```

## Frontend Structure (frontend/src/)
```
frontend/src/
├── components/        # React components
│   ├── ui/           # shadcn/ui primitives
│   ├── chat/         # Chat interface
│   ├── documents/    # Document management
│   ├── graph/        # Knowledge graph visualization
│   ├── dashboard/    # Dashboard components
│   ├── layout/       # Layout components (AppSidebar, SidebarLayout)
│   ├── auth/         # Authentication UI
│   ├── arxiv/        # ArXiv management components
│   └── ...           # Other feature components
├── hooks/             # Custom React hooks
│   ├── useChatPersistence.ts  # Chat persistence bridge hook
│   ├── useDocuments.ts        # Document management
│   ├── useWebSocket.ts        # WebSocket connections
│   └── ...                    # Other hooks
├── lib/               # Utility libraries
├── stores/            # Zustand stores (legacy)
├── store/             # Zustand stores (new pattern)
│   ├── chat-store.ts          # Chat state management
│   ├── realtime-store.ts      # Real-time processing state
│   ├── sidebar-store.ts       # Sidebar state
│   └── llm-chat-store.ts      # LLM chat state
├── services/          # API service layer
│   ├── apiClient.ts           # Axios client with interceptors
│   ├── workspaceService.ts    # Workspace API
│   └── ...                    # Other services
├── types/             # TypeScript types
├── utils/             # Utility functions
└── styles/            # Global styles
```

## Frontend App Router (frontend/app/)
```
frontend/app/
├── page.tsx           # Landing page
├── layout.tsx         # Root layout
├── globals.css        # Global styles
├── providers.tsx      # Context providers
├── dashboard/         # Dashboard page
├── chat/              # Chat interface
│   └── [id]/         # Dynamic chat routes
├── documents/         # Document management
├── settings/          # Settings page (Terminal Observatory theme)
├── arxiv/             # ArXiv paper management
├── search/            # Search interface
├── analytics/         # Analytics dashboard
├── entities/          # Entity management
├── login/             # Login page
├── register/          # Registration page
└── api/               # API routes
```

## Test Structure
```
tests/
├── specs/             # Specification tests
├── unit/              # Unit tests
├── integration/       # Integration tests
├── e2e/               # End-to-end tests
├── performance/       # Performance tests
├── load/              # Load tests
└── fixtures/          # Test fixtures
```

## Key Entry Points
- Backend: `backend/src/main.py`
- Frontend: `frontend/app/` (Next.js App Router)
- Docker: `docker-compose.development.yml`
