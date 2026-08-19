# Gotchas

Operational knowledge preserved from the retired root `CLAUDE.md` (removed in #1491).
These are hard-won invariants — verify against code before assuming one has changed.

## Database & environment

- Local compose DB = container `rag-postgres-1` / database `multimodal_rag_dev` (not `rag-db-dev`). DOKS `dev` cluster = **Supabase** managed (`SUPABASE_DB_URL` overrides `DATABASE_URL`).
- Only `dev` is live (ArgoCD auto-sync from `develop`, namespace `rag-dev`). `staging` + `production` ArgoCD apps retired 2026-04-29 (PR #442); their values files remain and the gitops workflow still bumps staging tags nothing consumes.
- Qdrant is removed — retrieval migrated to DO KB (`backend/src/services/do_kb/`, behind `DO_KB_ENABLED`, currently off; live retrieval is PostgreSQL fulltext). Legacy non-ArgoCD charts/manifests still carry dead Qdrant refs; not deployed.

## API

- Documents API is `/api/v1/documents/` (not `/documents` or `/api/documents`).
- WebSocket auth uses the `Sec-WebSocket-Protocol` header, NOT URL query params.
- CORS uses explicit allowlists, no wildcards.
- SQL injection prevention via validated enums (`src/shared/enums.py`) — never raw strings in sort/filter.
- Document status mapping uses lowercase: `'pending'→'queued'`, `'completed'→'indexed'`.
- Don't name query params the same as imported modules (e.g. `status` shadows `fastapi.status`).
- ArXiv API endpoints need `postWithLongTimeout` (5 min), not the standard timeout.
- IconButton requires `aria-label`.

## Tenant scope (mandatory)

- Every document / content-hash dedup / search-suggestion query MUST filter `organization_id`.
- Project (Collection) ownership = `Workspace.owner_id` — Collection has **no** `owner_id` (join Workspace).
- Agent tools + the RAG node must verify project ownership (`_verify_project_ownership` / `_user_owns_project`) before using a client-supplied `project_id`; an unscoped 409/suggestion/filter leaks other tenants' titles/ids.
- `require_admin` is a per-user role, not a tenant boundary.

## Search

- Count queries must apply the _same_ filters as the result query (shared `_apply_*_filters` helpers) — a drifted count over-reports `total` and yields phantom `has_more` pages.

## Storage

- `Document.storage_path` = bare object key; `file_path` = `s3://bucket/key` (or `supabase://...`, or a local path). Serving + deleting branch on `storage_backend` — s3 (DO Spaces) is the deployed default.
- Upload commits the object to storage _before_ the DB rows, so any post-upload failure must compensating-delete the object (`_best_effort_delete_object`) and revert quota, else it orphans the object and a PENDING row that content-hash dedup then blocks from re-upload.

## Agent (LangGraph)

- After arXiv ingest, use `document_ids` (UUIDs) from the response, NOT arXiv paper IDs.
- Checkpoint URL must be `postgresql://` (psycopg v3), not `postgresql+asyncpg://`.
- Every AIMessage with tool_calls must have matching ToolMessages (sanitizer adds placeholders).
- DraftGenerationService uses a fresh `AsyncSessionLocal()` to avoid rollback conflicts.
- Destructive tools (ingest, create_note, create_draft) trigger `interrupt()` for human confirmation.
- `ThreadSummarizationService` uses the **sync** SQLAlchemy API (`db.query`/`db.commit`) and is shared with the Celery task — drive it from a worker thread (`SessionLocal()` + `asyncio.run`), never hand it the request's `AsyncSession` (`'AsyncSession' has no attribute 'query'` → 500).

## Observability

- Synthetic-traffic LangSmith runs are filtered by `metadata.synthetic` + `run_name` (`synthetic:<scenario>`), NOT a post-hoc tag — LangSmith rejects `update_run` after a run's final payload ("Duplicate run update… not supported").
