# API layer

This directory contains every FastAPI router for the NOUS backend. All routers are imported and mounted in `src/main.py`; there is no intermediate router aggregator — each subpackage exports one or more `APIRouter` instances that `main.py` calls `app.include_router()` on directly.

## Versioning

Most routes live under `/api/v1`. A handful of newer or real-time paths use `/api/v2`. The prefix is set either inside the router definition (`router = APIRouter(prefix="/api/v1/agent", ...)`) or at the `include_router` call site (`app.include_router(router, prefix="/api/v1")`). When both are present the paths concatenate — double-check `main.py` if a path looks wrong.

## Subpackages

| Subpackage        | What it serves                                                                                                                            | Effective base path(s)                                                                                                          |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `agent`           | LangGraph agent execution (async jobs, SSE streaming, HITL confirm, thread/graph endpoints)                                               | `/api/v1/agent`                                                                                                                 |
| `analytics`       | Knowledge-graph analytics, dashboards, metrics, reports                                                                                   | `/api/v1/analytics/…` (quality, behavior, performance, recommendations)                                                         |
| `arxiv`           | arXiv paper ingest, knowledge-graph integration, change tracking, feature extraction, local PDF processing, Kaggle/LLM bulk ingest        | `/api/v1/arxiv/…` (core, kg, tracking, extraction, local, bulk)                                                                 |
| `auth`            | JWT auth, Supabase session bridge, CLI device-code auth, API-key management, tenant management                                            | `/api/v1/auth`, `/api/v1/cli-auth`, `/api/v1/api-keys`                                                                          |
| `connectors`      | External database connectors                                                                                                              | `/api/v1/connectors`                                                                                                            |
| `diagnostics`     | Retrieval pipeline diagnostics, Sentry smoke test                                                                                         | `/api/v1/diagnostics`, `/api/v1/sentry-debug`                                                                                   |
| `documents`       | Document CRUD, file upload/download, processing status, AI integrity detector, table/math extraction                                      | `/api/v1/documents`, `/api/v1/files`, `/api/v1/processing`, `/api/v1/integrity`, `/api/v1/table-extraction`                     |
| `evidence`        | Evidence agreement meter (stance classification against a claim)                                                                          | `/api/v1/evidence`                                                                                                              |
| `infrastructure`  | Background workers, RAG evaluation                                                                                                        | `/api/v1/workers`, `/api/v1/evaluation`                                                                                         |
| `quality`         | Search/retrieval quality metrics, recommendations, user behaviour, performance dashboard                                                  | `/api/v1/analytics/quality`, `/api/v1/analytics/behavior`, `/api/v1/analytics/performance`, `/api/v1/analytics/recommendations` |
| `realtime`        | WebSocket connections (v1 + v2), real-time document-status SSE, real-time quality metrics                                                 | `/ws/…`, `/api/v2/realtime/…`                                                                                                   |
| `research`        | Research projects, citations, drafts, chat, export, scholarly tone engine, extraction matrix, AI writer, pipeline wizard, project reports | `/api/v1/research/…`, `/api/v1/projects`, `/api/v1/drafts`, `/api/v1/citations`, etc.                                           |
| `research_engine` | Structured research-engine blueprints, runs, steps                                                                                        | `/api/v1/research-engine/…`                                                                                                     |
| `search`          | Hybrid search (Qdrant + PG), knowledge-graph query, multi-agent search (v1 + v2), search quality                                          | `/api/v1/search`, `/api/v1/knowledge-graph`, `/api/v1/multi-agent-search`, `/api/v2/multi-agent-search`                         |
| `security`        | Field-level encryption management, RBAC management, compliance                                                                            | `/api/v1/security/…`, `/api/v1/rbac`                                                                                            |
| `threads`         | Workspaces, threads, messages, SSE streaming chat, full-text thread search, bulk operations                                               | `/api/v2/workspaces`, `/api/v2/threads`, `/api/v2/stream`, `/api/v2/search`                                                     |

## How routers are registered

`src/main.py` is the sole mount point. Each subpackage's `__init__.py` exports its router(s) by name; `main.py` imports them and calls `app.include_router(router, prefix=…)`. Some routers embed the full prefix themselves (e.g. agent, connectors, research projects); others receive it at mount time (e.g. documents gets `/api/v1` prepended, then its internal prefix `/documents` makes the full path `/api/v1/documents/`).

Router ordering matters in one place: `threads_router` (which owns `/api/v2/threads/bulk/*`) must be included before `workspaces_standalone_router` so that bulk routes match before the `/{thread_id}` catch-all. This is documented with a `# CRITICAL` comment in both `main.py` and `threads/__init__.py`.

## Conventions and gotchas

**Query parameter naming** — never name a query parameter `status`. The name shadows `fastapi.status` (the HTTP constants module) within the function body, causing subtle bugs. Use `doc_status`, `filter_status`, or a similar qualified name.

**CORS** — the `CORSMiddleware` configuration in `main.py` reads from `settings.cors_origins_list`, `settings.cors_methods_list`, `settings.cors_headers_list`, and `settings.cors_expose_list`. Wildcard origins (`"*"`) are explicitly prohibited. Adding a new origin requires updating the environment-level config, not the code.

**WebSocket auth** — WebSocket connections authenticate via the `Sec-WebSocket-Protocol` header, not a URL query parameter. The browser-side subprotocol negotiation pattern is required; plain `?token=` in the URL will not work.

**ArXiv timeouts** — arXiv ingest endpoints are slow. Call them with `postWithLongTimeout` (5-minute timeout) from the frontend rather than the standard fetch wrapper.

**Slash redirects** — `redirect_slashes=False` is set on the FastAPI app and on the documents router. Without it, FastAPI's default 307 redirect strips the `Authorization` header on POST requests to paths missing a trailing slash.

**Docs visibility** — `/docs` (Swagger UI) and `/redoc` are only served when `settings.DEBUG` is true. They are disabled in production.

**`/api/v2/` paths** — threads, stream, thread-search, and realtime quality metrics use `/api/v2`. Everything else is `/api/v1` unless noted above.
