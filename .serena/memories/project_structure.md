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
│   ├── layout/       # Layout components
│   ├── auth/         # Authentication UI
│   └── ...           # Other feature components
├── hooks/             # Custom React hooks
├── lib/               # Utility libraries
├── stores/            # Zustand stores
├── types/             # TypeScript types
├── utils/             # Utility functions
└── styles/            # Global styles
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
