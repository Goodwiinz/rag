# Multimodal RAG System

Multimodal RAG system: Next.js 15 + FastAPI + PostgreSQL/Qdrant/Neo4j/Redis.

## Development Workflow

```sh
# 1. Start services
docker-compose -f docker-compose.development.yml up -d

# 2. Frontend
cd frontend && npm run dev

# 3. Backend (if not using Docker)
cd backend && uvicorn src.main:app --reload --port 8000

# 4. Type-check
cd frontend && npm run type-check

# 5. Test
cd frontend && npm run test          # Frontend
pytest tests/ --cov=src              # Backend

# 6. Lint
cd frontend && npm run lint

# 7. Validate before PR
cd frontend && npm run validate      # lint + type-check + test
```

## Code Style

- **Python**: Black (88), isort, mypy strict, snake_case, structlog
- **TypeScript**: Prettier, ESLint, strict mode, camelCase/PascalCase
- **Imports**: `@/*` aliases for src/app paths
- **Theme**: Vercel Aesthetic / shadcn/ui neutral - Primary: `hsl(var(--primary))`, Background: `hsl(var(--background))`. Clean, minimalist styling. No brutalist effects or scanlines.

## Gotchas

- DB name is `multimodal_rag_dev`, container is `rag-postgres-1` (not `rag-db-dev`)
- WebSocket auth uses `Sec-WebSocket-Protocol` header, NOT URL query params
- SQL injection prevention via validated enums (`src/shared/enums.py`), never raw strings in sort/filter
- CORS uses explicit allowlists, no wildcards
- Document status mapping uses lowercase: 'pending'→'queued', 'completed'→'indexed'
- Documents API is `/api/v1/documents/` (not `/documents` or `/api/documents`)
- Don't name query params same as imported modules (e.g. `status` shadows `fastapi.status`)
- IconButton requires `aria-label`
- ArXiv API endpoints need `postWithLongTimeout` (5 min), not standard timeout

## Connections

- PostgreSQL: `localhost:5432` (postgres/postgres)
- Neo4j: `bolt://localhost:7687`
- Qdrant: `http://localhost:6333`
- Redis: `redis://localhost:6379`
- Backend: `http://localhost:8000`
- Frontend: `http://localhost:3000`

## Branch Strategy

- Feature branches from `develop`
- PRs target `develop`
