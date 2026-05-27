# NOUS — Backend CODEMAP

> FastAPI app: entry point, package layout, top endpoints, top services, how to add a domain.
> Last generated: 2026-04-26

## Entry point

`backend/src/main.py` (566 LOC) — creates the FastAPI app, wires all routers, middleware, and startup events.

## `src/` package layout

```
src/
  main.py             FastAPI app factory + router wiring
  api/                Route handlers (thin — request/response only)
    agent/            execute, jobs, streaming, tools_impl
    analytics/        behavior, quality metrics, performance dashboard
    arxiv/            arXiv search + ingest
    auth/             JWT, API keys, CLI auth
    connectors/       third-party connector endpoints
    diagnostics/      retrieval diagnostics
    documents/        upload, processing, vectors
    evidence/         evidence meter
    quality/          search quality
    realtime/         document status SSE
    research/         citations, drafts, notes, tone, writer, integrity
    research_engine/  projects, blueprints, runs, steps
    search/           semantic + multi-agent search (v1 + v2)
    security/         encryption, compliance, RBAC
    threads/          thread CRUD, workspace, export
  services/           Business logic (domain-per-folder)
    agent/            LangGraph graph + HITL (see AGENT.md)
    analytics/        event tracking, dashboards
    arxiv/            paper fetch + metadata
    auth/             session, permissions
    connectors/       external integrations
    core/             cross-service utilities
    documents/        ingestion pipeline, processing
    embedding/        vector embedding
    evaluation/       QA evaluation harness
    evidence/         evidence extraction
    ingestion/        document loader, chunker
    knowledge_graph/  Neo4j queries + ingest
    models/           AI model abstraction layer
    processing/       async Celery task wrappers
    quality/          search quality scoring
    research/         research assistant features
    research_engine/  multi-step research pipelines
    sandbox/          safe code execution
    search/           multi-agent search orchestration
    security/         encryption, compliance
    threads/          thread + workspace management
    websocket/        WebSocket event hub
  models/             SQLAlchemy ORM models (62 flat files — domain split pending)
  schemas/            Pydantic request/response schemas
  core/               Cross-cutting infra
    config/           Settings (Pydantic BaseSettings)
    database_optimizations/  Query helpers
    security/         auth helpers, rate limiter
    ...
  config/             App-level config loader
  middleware/         Request logging, CORS, auth middleware
  tasks/              Celery task definitions
  workers/            Celery worker bootstrap
  utils/              Shared utilities
  exceptions/         Custom exception hierarchy
  shared/             Enums, constants (enums.py has SQL-safe sort/filter values)
  observability/      LangSmith + Prometheus hooks
  monitoring/         Health check helpers
  websocket/          WebSocket connection manager (legacy + v2)
  cli/                Click CLI entry point (`nous` binary)
```

## Top endpoints (registered in `main.py`)

| Prefix | Router | Purpose |
|---|---|---|
| `/api/v1/agent/` | agent | Execute, stream, confirm HITL, thread list |
| `/api/v1/documents/` | documents | Upload, status, processing |
| `/api/v1/threads/` | threads | CRUD + workspace management |
| `/api/v1/search/` | search | Semantic + multi-agent search |
| `/api/v1/knowledge-graph/` | knowledge_graph | Node/edge queries |
| `/api/v1/research/` | research | Citations, drafts, notes, writer |
| `/api/v1/research-engine/` | research_engine | Pipeline projects + runs |
| `/api/v1/analytics/` | analytics | Behavior, quality, performance |
| `/api/v1/evidence/` | evidence | Evidence meter |
| `/api/v1/security/` | security | Encryption, compliance, RBAC |
| `/api/v1/evaluation/` | evaluation | QA evaluation |
| `/api/v1/auth/` | auth | Login, refresh, API keys |
| `/health` | health | Liveness + readiness probes |

## Top services

| Module | Key class | Purpose |
|---|---|---|
| `services/agent/graph.py` | `create_graph()` | LangGraph StateGraph — see AGENT.md |
| `services/knowledge_graph/` | `KnowledgeGraphService` | Neo4j CRUD + traversal (1,897 LOC — split pending) |
| `services/search/multi_agent_search_service_v2.py` | `MultiAgentSearchServiceV2` | Orchestrates parallel search agents (1,914 LOC — split pending) |
| `services/documents/` | `DocumentService` | Ingestion pipeline coordinator |
| `services/threads/` | `ThreadService` | Conversation + workspace logic |
| `services/research/` | `ResearchService` | Citations, drafts, bibliography |
| `services/embedding/` | `EmbeddingService` | OpenAI / Azure embedding calls |
| `services/evaluation/` | `EvaluationService` | DeepEval + LangSmith QA runs |

## Database migrations

`backend/alembic/` is the single canonical migration system.  
Run: `cd backend && alembic upgrade head`  
Config: `backend/alembic.ini`, env: `backend/alembic/env.py`

## Adding a new domain

1. Create `src/api/<domain>/router.py` — thin handlers, import service.
2. Create `src/services/<domain>/service.py` — business logic; `repository.py` for DB access.
3. Add ORM models to `src/models/<domain>.py` (until domain split is complete).
4. Add Pydantic schemas to `src/schemas/<domain>.py`.
5. Register router in `src/main.py`: `app.include_router(<domain>_router, prefix="/api/v1")`.
6. Add Alembic migration: `alembic revision --autogenerate -m "add_<domain>"`.
7. Add tests under `tests/unit/api/<domain>/` and `tests/integration/<domain>/`.

## Key gotchas

- Never use raw strings for SQL sort/filter — use `src/shared/enums.py` validated enums.
- Don't name query params same as imported modules (e.g. `status` shadows `fastapi.status`).
- Agent checkpoint URL must be `postgresql://` (psycopg v3), not `postgresql+asyncpg://`.
- Destructive tools trigger `interrupt()` — pair every tool-call AIMessage with a ToolMessage.
