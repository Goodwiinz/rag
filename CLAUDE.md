# NOUS — Multimodal Intelligence Platform

Next.js 15 + FastAPI + PostgreSQL / Neo4j / Redis. **One environment so far — `dev`** (no staging/prod yet).
Runs locally via `docker-compose.development.yml`, or deployed to the **DOKS `dev` cluster** (namespace `rag-dev`):
Supabase (Postgres + auth), DO Managed Redis, DO Spaces, in-cluster Neo4j, Vercel frontend, ArgoCD auto-sync from `develop`.

## Development Workflow

```sh
# Start services
docker-compose -f docker-compose.development.yml up -d

# Frontend
cd frontend && npm run dev

# Backend (if not using Docker)
cd backend && uvicorn src.main:app --reload --port 8000

# Type-check / Test / Lint / Validate
cd frontend && npm run type-check
cd frontend && npm run test          # Frontend
pytest tests/ --cov=src              # Backend
cd frontend && npm run lint
cd frontend && npm run validate      # lint + type-check + test
```

## Agent System (LangGraph)

LangGraph StateGraph with intent-based routing to specialized subgraphs.

**Flow:** `rag_node → intent_classifier → memory_retrieval → [route by intent] → tool_node → memory_save → END`

**Subgraphs:**

- **Research**: arXiv search/ingest, document search, project management (max 8 tool loops)
- **Writing**: drafts, notes, bibliography, summarization, document comparison
- **Data**: entity extraction, knowledge graph queries
- **General**: full tool set with LLM routing

**Endpoints** (`/api/v1/agent/`):

- `POST /execute` — Async job-based (returns job_id, poll via `GET /jobs/{job_id}`)
- `POST /stream` — SSE streaming (token, tool_start, tool_end, rag_context, done)
- `POST /confirm/{job_id}` — Resume human-in-the-loop interrupts
- `GET /threads` / `GET /threads/{id}/messages` — Thread management
- `GET /graph/mermaid` / `GET /graph/trace/{thread_id}` — Visualization

**Config:** `backend/langgraph.json` defines graph entry point (`compile_agent_graph`)

## Code Style

- **Python**: Black (88), isort, mypy strict, snake_case, structlog
- **TypeScript**: Prettier, ESLint, strict mode, camelCase/PascalCase
- **Imports**: `@/*` aliases for src/app paths
- **Theme**: NOUS brand — Erebus `#0A0A0E`, Selene `#F7F7F5`, Sol `#D4A039` (accent). Inter headings, Source Serif 4 body. Clean, minimalist. shadcn/ui components.

## Gotchas

- DB: local compose = container `rag-postgres-1` / `multimodal_rag_dev` (not `rag-db-dev`). DOKS `dev` cluster = **Supabase** managed (`SUPABASE_DB_URL` overrides `DATABASE_URL`).
- WebSocket auth uses `Sec-WebSocket-Protocol` header, NOT URL query params
- SQL injection prevention via validated enums (`src/shared/enums.py`), never raw strings in sort/filter
- CORS uses explicit allowlists, no wildcards
- Document status mapping uses lowercase: 'pending'→'queued', 'completed'→'indexed'
- Documents API is `/api/v1/documents/` (not `/documents` or `/api/documents`)
- Don't name query params same as imported modules (e.g. `status` shadows `fastapi.status`)
- IconButton requires `aria-label`
- ArXiv API endpoints need `postWithLongTimeout` (5 min), not standard timeout
- Agent: after arXiv ingest, use `document_ids` (UUIDs) from response, NOT arXiv paper IDs
- Agent: checkpoint URL must be `postgresql://` (psycopg v3), not `postgresql+asyncpg://`
- Agent: every AIMessage with tool_calls must have matching ToolMessages (sanitizer adds placeholders)
- Agent: DraftGenerationService uses fresh `AsyncSessionLocal()` to avoid rollback conflicts
- Agent: destructive tools (ingest, create_note, create_draft) trigger `interrupt()` for human confirmation

## Connections

Only one environment so far: **`dev`**. No staging/prod yet. Two ways to run it:

### Local (`docker-compose.development.yml`)

| Service    | Port | URL                         |
| ---------- | ---- | --------------------------- |
| PostgreSQL | 5432 | postgres:postgres@localhost |
| Neo4j      | 7687 | bolt://localhost:7687       |
| Redis      | 6379 | redis://localhost:6379      |
| Backend    | 8000 | http://localhost:8000       |
| Frontend   | 3000 | http://localhost:3000       |

### DOKS `dev` cluster (namespace `rag-dev`, ArgoCD auto-sync from `develop`)

| Layer          | Provider                     | Notes                                                              |
| -------------- | ---------------------------- | ------------------------------------------------------------------ |
| Postgres       | **Supabase** (managed)       | `SUPABASE_DB_URL` overrides `DATABASE_URL`; pool tuned for pooler  |
| Auth           | **Supabase** (hosted GoTrue) | No backend login/register                                          |
| Redis          | **DO Managed Redis**         | External; in-cluster subchart disabled (`redis.enabled:false`)     |
| Object storage | **DO Spaces** `nyc3`         | `STORAGE_BACKEND=s3`, bucket `rag-system-storage`                  |
| Neo4j          | In-cluster                   | `bolt://nous-dev-knowledge-graph-analytics-neo4j:7687`             |
| Background     | **Celery** worker (HPA 1–5)  | Broker = DO Redis                                                  |
| LLM            | **Azure OpenAI**             | Chat/agent deployment                                              |
| Frontend       | **Vercel**                   | `dev-app.gen-text.app` (API `dev-api.gen-text.app`)                |
| Secrets        | **Infisical** operator       | envFrom `app-secrets`, `*-credentials`                             |
| Retrieval/RAG  | PostgreSQL fulltext          | DO KB (`backend/src/services/do_kb/`) behind `DO_KB_ENABLED` (off) |

> **Qdrant:** the Helm subchart still deploys a pod (`qdrant.enabled:true` in `values-dev.yaml`), but the app sets **no `QDRANT_URL`**, so `QdrantClient` is `None` and Qdrant is never queried — effectively unused. Safe to drop the subchart.

## Branch Strategy

- Feature branches from `develop`
- PRs target `develop`

## Design Context

`PRODUCT.md` (strategic) + `DESIGN.md` (visual) at project root are the source of truth for the impeccable design skill. Register default: `product` (landing+auth are `brand` per-task).

- **Users:** researchers/academics — lit review, arXiv ingest, KG exploration, drafting. Expert, deep-focus, attention on docs not chrome.
- **Personality:** scholarly, warm, confident. Plain sentence-case voice, no hype/shouting/costume.
- **Principles:** provenance over assertion; content over chrome; calm expert voice; honest loading/empty/error/HITL states; density with rhythm.
- **Anti-refs:** cyberpunk/terminal costume (removed, don't reintroduce), SaaS-cream + hero-metric block, AI-slop (gradient text, decorative glass, side-stripe borders, uppercase-mono labels), cold enterprise.
- **A11y:** WCAG 2.1 AA.
