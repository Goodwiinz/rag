# NOUS Platform — Project Memory

## Identity

- **Name**: NOUS (νοῦς — mind/intellect)
- **Repo**: goodwiinz/rag (GitHub)
- **Branch strategy**: feature branches from `develop`, PRs target `develop`
- **Active branch**: `claude/implement-todo-item-fgVkL`

## Stack

| Layer      | Tech                                                              |
| ---------- | ----------------------------------------------------------------- |
| Frontend   | Next.js 15 + TypeScript + shadcn/ui + Zustand + TanStack Query v5 |
| Backend    | FastAPI + Python 3.11 + LangGraph agent                           |
| Primary DB | PostgreSQL (`multimodal_rag_dev`, container: `rag-postgres-1`)    |
| Vector DB  | Qdrant (port 6333)                                                |
| Graph DB   | Neo4j (bolt://localhost:7687)                                     |
| Cache      | Redis (port 6379)                                                 |
| Queue      | Celery (Redis broker)                                             |
| Infra      | Kubernetes (DOKS, NYC3) + Helm + ArgoCD                           |
| Registry   | registry.digitalocean.com/ragsystemregistry                       |
| Storage    | DO Spaces — `rag-system-storage` (NYC3)                           |
| Domain     | gen-text.app                                                      |

## Infrastructure — Key Files

```
infrastructure/
├── helm/knowledge-graph-analytics/    # Main Helm chart
│   ├── templates/
│   │   ├── backend-deployment.yaml
│   │   ├── frontend-deployment.yaml
│   │   ├── celery-beat-deployment.yaml
│   │   ├── hpa.yaml                   # HPA for backend, frontend, celery-worker
│   │   ├── pdb.yaml                   # PDB for backend, frontend, celery-worker
│   │   ├── neo4j-secret.yaml          # NEW — K8s Secret for NEO4J_AUTH
│   │   └── neo4j-statefulset.yaml
│   ├── values-production.yaml         # Production overrides
│   ├── values-staging.yaml
│   └── values-dev.yaml
├── argocd/applications/
│   ├── staging.yaml                   # Manual sync (removed automated block)
│   └── production.yaml
└── arc/
    └── runner-deployment.yaml         # NEW — ARC self-hosted GitHub runner
```

## CI/CD

- **Workflows**: `.github/workflows/`
  - `docker-build.yml` — builds backend + frontend images; self-hosted runner on DO cluster; Docker layer cache in DO Spaces (`rag-system-storage`)
  - `gitops-image-update.yml` — auto-updates Helm values on push to develop/main
  - `deploy.yml` — Helm deploy to staging/production via doctl
  - `test-pipeline.yml` — full test suite
  - `fast-ci.yml` — quick lint/type-check on PRs
  - `workflow-lint.yml` — actionlint validation

- **Self-hosted runner**: ARC (actions-runner-controller) — `RunnerDeployment` in `arc-systems` namespace, DinD enabled, 4 CPU / 8 GB limit, ephemeral pods, auto-scales 1–3

- **Required secrets** (GitHub → Settings → Secrets → Actions):
  - `DO_REGISTRY_TOKEN` — DO container registry
  - `DO_SPACES_ACCESS_KEY` — Spaces key ID (for Docker cache)
  - `DO_SPACES_SECRET_KEY` — Spaces secret (for Docker cache)
  - `DIGITALOCEAN_ACCESS_TOKEN` — doctl auth
  - `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` — frontend build args

## Caching Architecture (7 layers, all Redis-backed)

| Cache            | File                                                        | Key prefix      |
| ---------------- | ----------------------------------------------------------- | --------------- |
| Analytics        | `backend/src/cache/analytics_cache.py`                      | `analytics:`    |
| LLM response     | `backend/src/services/infrastructure/llm_response_cache.py` | `llm_cache:`    |
| Search           | `backend/src/services/search/cache.py`                      | `search_cache:` |
| WebSocket        | (in-memory + Redis pub/sub)                                 | —               |
| Evidence         | `backend/src/services/evidence/cache.py`                    | —               |
| Knowledge graph  | `backend/src/services/core/cache.py`                        | —               |
| Core (decorated) | `backend/src/core/caching.py`                               | `rag:`          |

**Hardening shipped (2026-04-15)**:

- Stampede protection: Redis NX lock in `@cached` decorator (30s TTL, 500ms poll)
- TTL jitter ±15% on every `setex()` across all 7 layers
- gzip compression for payloads >1 KB (`gz:` prefix in `serialize_value`)
- Prometheus metrics: `cache_hits_total`, `cache_misses_total`, `cache_errors_total`, `cache_hit_rate`
- Search key hash: 16 → 32 hex chars (closed birthday-paradox risk)
- `backend/src/core/cache_warmup.py` — `warm_critical_caches()` background task on startup

## Kubernetes — Key Gotchas

- `redis-credentials` Secret **must** be in `envFrom` of backend deployment — without it all 7 caches silently fall back to `redis://localhost:6379`
- Neo4j password stored in `nous-<env>-knowledge-graph-analytics-neo4j-credentials` Secret (not plaintext in values)
- K8s probe `httpHeaders` with `Host: localhost` removed — unnecessary, pods connect by IP
- Backend container `securityContext`: `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]`
- Staging ArgoCD sync is **manual** (removed `automated` block) — run `argocd app sync nous-staging` explicitly
- Production HPA: backend 2–6 replicas (70% CPU / 80% mem), frontend 2–4 replicas
- Celery worker HPA: 1–6 replicas, scale-down 600s stabilization window (25% max reduction per 120s)

## Agent System (LangGraph)

- **Graph**: `backend/src/services/agent/graph.py`
- **Endpoints**: `backend/src/api/agent/execute.py`
- **Subgraphs**: research, writing, data, general
- **Checkpointing**: AsyncPostgresSaver (postgresql:// — psycopg v3)
- **HITL**: `interrupt()` for destructive tools (ingest, create_note, create_draft)
- **Streaming**: SSE `/api/v1/agent/stream` — events: token, tool_start, tool_end, rag_context, done, error

## Gotchas (carry-forward from CLAUDE.md)

- DB name: `multimodal_rag_dev`, container: `rag-postgres-1`
- WebSocket auth: `Sec-WebSocket-Protocol` header (not URL query param)
- Documents API: `/api/v1/documents/` (trailing slash)
- Status mapping: `'pending'→'queued'`, `'completed'→'indexed'`
- ArXiv endpoints need `postWithLongTimeout` (5 min)
- Agent checkpoint URL: `postgresql://` not `postgresql+asyncpg://`
- Agent: every AIMessage with tool_calls needs matching ToolMessages
