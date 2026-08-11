# NOUS — Multimodal Intelligence Platform

Next.js 16 + FastAPI + PostgreSQL / Neo4j / Redis. **Only `dev` is live** (ArgoCD auto-sync from `develop`, namespace `rag-dev`). `staging` + `production` ArgoCD apps were **retired 2026-04-29 (PR #442)** for cluster memory pressure (DO volume snapshots taken before deletion); their values files remain and the gitops workflow still bumps staging tags nothing consumes.
Runs locally (no Docker; user runs backend/frontend manually) or deployed to the **DOKS cluster**:
Supabase (Postgres + auth), DO Managed Redis, DO Spaces, in-cluster Neo4j, Vercel frontend, ArgoCD auto-sync from `develop`.

## Development Workflow

```sh
# Start services
docker-compose -f docker-compose.development.yml up -d

# Frontend (Node 24 + pnpm 10.18.2, corepack — no npm)
cd frontend && pnpm dev

# Backend (if not using Docker)
cd backend && uvicorn src.main:app --reload --port 8000

# Type-check / Test / Lint / Validate  (subshells: cwd stays at repo root)
(cd frontend && pnpm type-check)
(cd frontend && pnpm test)           # Frontend
pytest tests/ --cov=src              # Backend
(cd frontend && pnpm lint)
(cd frontend && pnpm validate)       # lint + type-check + test
```

Toolchain, quality-ratchet, and API-contract rules are enforced, not just
documented here — see [`docs/engineering/`](docs/engineering/README.md) for
the router/service boundaries, tenant-scope rules, chat state ownership,
and the commands CI actually runs.

## Agent System (LangGraph)

LangGraph StateGraph with intent-based routing to specialized subgraphs.

**Flow:** `preprocessing_node (RAG + classify + memory, parallel) → [route_by_intent] → research|writing|data subgraph | general path → memory_save_node → END`

General path: `planner_node → llm_node → [should_continue] → tool_node → compactor_node → llm_node (loop)`, with `interrupt_node` (HITL) and `reflection_gate` (`revise` loops back to `llm_node`). Authoritative topology = `build_agent_graph` docstring in `backend/src/services/agent/_builders.py`.

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

**Config:** `backend/langgraph.json` points at `src/services/agent/graph.py:create_graph`. In-process runtime compiles via `compile_agent_graph(checkpointer, store)` (`_builders.py`) — cached per `(checkpointer, store)` identity.

## Code Style

- **Python**: Black (88), isort, mypy (CI-blocking on added files; full-tree advisory — see docs/engineering/backend.md), snake_case, structlog
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
- **Tenant scope is mandatory**: every document / content-hash dedup / search-suggestion query MUST filter `organization_id`. Project (Collection) ownership = `Workspace.owner_id` — Collection has **no** `owner_id` (join Workspace). Agent tools + the RAG node must verify project ownership (`_verify_project_ownership` / `_user_owns_project`) before using a client-supplied `project_id`; an unscoped 409/suggestion/filter leaks other tenants' titles/ids.
- **Search count queries must apply the _same_ filters as the result query** (shared `_apply_*_filters` helpers) — a drifted count over-reports `total` + yields phantom `has_more` pages.
- **Storage layout**: `Document.storage_path` = bare object key; `file_path` = `s3://bucket/key` (or `supabase://...`, or a local path). Serving + deleting branch on `storage_backend` — **s3 (DO Spaces) is the deployed default**. Upload commits the object to storage _before_ the DB rows, so any post-upload failure must compensating-delete the object (`_best_effort_delete_object`) + revert quota, else it orphans the object and a PENDING row that content-hash dedup then blocks from re-upload.
- `ThreadSummarizationService` uses the **sync** SQLAlchemy API (`db.query`/`db.commit`) and is shared with the Celery task — drive it from a worker thread (`SessionLocal()` + `asyncio.run`), never hand it the request's `AsyncSession` (`'AsyncSession' has no attribute 'query'` → 500).
- Synthetic-traffic LangSmith runs are filtered by `metadata.synthetic` + `run_name` (`synthetic:<scenario>`), NOT a post-hoc tag — LangSmith rejects `update_run` after a run's final payload ("Duplicate run update… not supported").
- **Config defaults + values-dev.yaml do NOT tell you what dev runs.** Infisical `envFrom` (`app-secrets`, `*-credentials`) overrides both at pod start and is invisible to any repo grep — `DO_KB_ENABLED` reads `False` in `core/config.py` and is absent from values-dev.yaml, yet is `true` live. A flag's absence from a values file is *no information*, not "off". Verify with `kubectl -n rag-dev exec <backend-pod> -- printenv | grep <VAR>`.
- Grep hits are not proof a dependency is live: all 24 `qdrant` hits under `backend/src/` are comments recording its removal. Check for a client construction / URL read before believing one.

## Connections

Only `dev` deploys via ArgoCD (staging/prod apps retired in #442, values scaffolding kept). Two ways to run `dev`:

### Local (`docker-compose.development.yml`)

| Service    | Port | URL                         |
| ---------- | ---- | --------------------------- |
| PostgreSQL | 5432 | postgres:postgres@localhost |
| Neo4j      | 7687 | bolt://localhost:7687       |
| Redis      | 6379 | redis://localhost:6379      |
| Backend    | 8000 | http://localhost:8000       |
| Frontend   | 3000 | http://localhost:3000       |

### DOKS `dev` cluster (namespace `rag-dev`, ArgoCD auto-sync from `develop`)

| Layer          | Provider                     | Notes                                                                                                                                                            |
| -------------- | ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Postgres       | **Supabase** (managed)       | `SUPABASE_DB_URL` overrides `DATABASE_URL`; pool tuned for pooler                                                                                                |
| Auth           | **Supabase** (hosted GoTrue) | No backend login/register                                                                                                                                        |
| Redis          | **DO Managed Redis**         | External; in-cluster subchart disabled (`redis.enabled:false`)                                                                                                   |
| Object storage | **DO Spaces** `nyc3`         | `STORAGE_BACKEND=s3`, bucket `rag-system-storage`                                                                                                                |
| Neo4j          | In-cluster                   | `bolt://nous-dev-knowledge-graph-analytics-neo4j:7687`                                                                                                           |
| Background     | **Celery** worker (HPA 1–5)  | Broker = DO Redis                                                                                                                                                |
| Synthetic load | **CronJob** (`*/20`, dev)    | `scripts.synthetic_traffic --rotate` drives the agent in-process → real `rag-agent-dev` LangSmith traces; gated `syntheticTraffic.enabled` (off in staging/prod) |
| LLM            | **Azure OpenAI**             | Chat/agent deployment                                                                                                                                            |
| Frontend       | **Vercel**                   | `goodwiinz.tech` (+ `www`); backend API ingress `dev-api.gen-text.app`                                                                                           |
| Secrets        | **Infisical** operator       | envFrom `app-secrets`, `*-credentials`                                                                                                                           |
| Retrieval/RAG  | **DO KB** (primary read)     | `DO_KB_ENABLED` + `DO_KB_PRIMARY_READ` both **true** on dev — set via Infisical `/do-kb`, NOT in values-dev.yaml. Postgres hybrid + rerank is the fallback (timeout / no KB / empty result) |

> **Qdrant:** removed. Retrieval migrated Qdrant → DO KB; the app sets no `QDRANT_URL` and never queries Qdrant. The `knowledge-graph-analytics` chart never actually had a Qdrant subchart or pod template — only dead `qdrant.*` values, a never-called `qdrantUrl` helper, and networkpolicy residue, all dropped in #1043. Legacy non-ArgoCD charts/manifests (`deployment/helm/rag-system`, `infrastructure/kubernetes/manifests/databases.yaml`, monitoring/terraform/backup/CI/docker-compose) still carry Qdrant refs; not deployed, cleanup pending.

## Branch Strategy

- Feature branches from `develop`
- PRs target `develop`

## Working Agreement (Claude Code)

Calibrated for Opus 5, which narrates, verifies, and delegates more than earlier
models unless told otherwise.

- **Answer first.** Lead with what happened or what you found; supporting detail
  after. One sentence before the first tool call, then updates only on a real
  finding or a change of direction.
- **Scope.** Deliver what was asked, at the scope intended. Make routine
  judgment calls yourself; check in only when different readings lead to
  materially different work. If the request looks mistaken, say so in a sentence
  and continue as asked rather than quietly narrowing or widening it.
- **Verification is the commands in Development Workflow**, not extra passes.
  `pnpm validate`, `pytest`, `scripts/ci/run_local_ci.sh` are the gate — don't
  add self-review rounds or verifier subagents on top of them.
- **Delegation** is for wide, genuinely independent sweeps (multi-file audits,
  parallel bug hunts). One subagent beats three. Don't delegate what takes a
  handful of tool calls, and don't spawn agents to check your own work.
- **Written deliverables** (audit docs, PR bodies, `docs/`) cover the substance
  without filler sections, redundant summaries, or boilerplate. Length follows
  content — a two-line finding is a two-line finding.
- **Corrections:** flag an earlier statement only when the error changes code,
  conclusions, or decisions. Otherwise fix it and move on.
- Keep responses and caveats short; most of the response goes to the answer.

## Design Context

`PRODUCT.md` (strategic) + `DESIGN.md` (visual) at project root are the source of truth for the impeccable design skill. Register default: `product` (landing+auth are `brand` per-task).

- **Users:** researchers/academics — lit review, arXiv ingest, KG exploration, drafting. Expert, deep-focus, attention on docs not chrome.
- **Personality:** scholarly, warm, confident. Plain sentence-case voice, no hype/shouting/costume.
- **Principles:** provenance over assertion; content over chrome; calm expert voice; honest loading/empty/error/HITL states; density with rhythm.
- **Anti-refs:** cyberpunk/terminal costume (removed, don't reintroduce), SaaS-cream + hero-metric block, AI-slop (gradient text, decorative glass, side-stripe borders, uppercase-mono labels), cold enterprise.
- **A11y:** WCAG 2.1 AA.
