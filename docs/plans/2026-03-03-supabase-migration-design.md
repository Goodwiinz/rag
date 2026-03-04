# Supabase Migration Design

## Goal

Migrate the RAG system from self-hosted Docker infrastructure to the Supabase platform, adopting managed PostgreSQL, Auth, Storage, and Realtime. Reduce infrastructure complexity while keeping Neo4j, Redis/Celery, and Qdrant as external services.

## Decisions

| Decision           | Choice                                                      | Rationale                                                       |
| ------------------ | ----------------------------------------------------------- | --------------------------------------------------------------- |
| Migration approach | Database-first, phased                                      | Each phase independently deployable; lowest risk                |
| ORM strategy       | Keep SQLAlchemy (Phase 1), gradually migrate to supabase-py | Avoid big-bang rewrite of 63 models                             |
| Local dev          | Supabase CLI (`supabase start`)                             | Matches production, replaces Docker PostgreSQL                  |
| Qdrant             | Keep as-is                                                  | Purpose-built vector DB, working well, not worth migration risk |
| Neo4j              | Keep as-is                                                  | No Supabase equivalent for graph database                       |
| Redis/Celery       | Keep as-is                                                  | No Supabase equivalent for task queue or caching                |

## Architecture After Migration

```
Frontend (Next.js)
  ├── @supabase/supabase-js (Auth, Storage, Realtime)
  └── API calls → FastAPI backend

FastAPI Backend
  ├── Supabase PostgreSQL (via SQLAlchemy → supabase-py gradual migration)
  ├── Supabase Auth (JWT validation, user management)
  ├── Supabase Storage (document uploads)
  ├── Redis (Celery broker, caching, rate limiting)
  ├── Neo4j (knowledge graphs)
  ├── Qdrant (vector search)
  └── Celery Workers (document processing, ML tasks)

Supabase Realtime (replaces custom WebSocket server)
  └── Postgres CDC → real-time document status updates
```

## Phase 1 — Database Connection Swap

**Effort:** 1-2 days | **Risk:** Low

Swap PostgreSQL connection from local Docker to Supabase Postgres. Zero changes to models or queries.

### Changes

- Install Supabase CLI, run `supabase init` + `supabase start`
- Update `backend/src/core/database.py`: read Supabase connection strings
- Export current schema, apply via `supabase/migrations/`
- Remove `rag-postgres-1` from `docker-compose.development.yml`
- Add env vars: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
- Handle PgBouncer: set `prepared_statement_cache_size=0` on asyncpg (transaction-mode pooling doesn't support prepared statements)

### What stays the same

- All 63 SQLAlchemy models
- All service layer code and API routes
- Alembic migrations (converted to Supabase migration format)

## Phase 2 — Supabase Auth

**Effort:** 3-5 days | **Risk:** Medium

Replace custom JWT auth with Supabase Auth.

### Changes

- Rewrite 11 auth dependencies to validate Supabase JWT tokens
- User model becomes a profiles table linked to `auth.users` via UUID
- Replace login/register endpoints with Supabase client calls
- Frontend uses `@supabase/supabase-js` auth directly
- Roles stored in `app_metadata` (ADMIN/CONTENT_MANAGER/ANALYST/USER)
- Add Row Level Security (RLS) policies for multi-tenancy
- Update WebSocket auth to validate Supabase JWTs
- Compatibility layer: accept both old and new JWTs during transition

### What stays the same

- API key system (no Supabase equivalent)
- Permission-based access control logic
- Rate limiting (Redis-backed)
- Organization multi-tenancy structure

## Phase 3 — Supabase Storage

**Effort:** 2-3 days | **Risk:** Low

Replace local filesystem with Supabase Storage.

### Changes

- Create buckets: `documents`, `images`, `audio`, `video`, `processed`
- Rewrite `FileService`: filesystem ops → Supabase Storage API
- Document `storage_path` format: `{bucket}/{org_id}/{doc_id}/{filename}`
- RLS policies on buckets for organization-scoped access
- Frontend direct uploads (resumable for large files)
- Migration script: upload existing `uploads/` to Supabase Storage

### What stays the same

- MIME type validation
- Document processing pipeline (workers download from Storage)
- File categorization logic

## Phase 4 — Supabase Realtime

**Effort:** 3-5 days | **Risk:** Medium

Replace custom Redis-backed WebSocket server with Supabase Realtime.

### Changes

- Supabase Realtime channels via Postgres CDC (Change Data Capture)
- Frontend: replace `useWebSocket` hook with Supabase Realtime subscriptions
- Backend: update DB rows instead of pushing WebSocket messages (CDC auto-broadcasts)
- Remove `backend/src/websocket/` directory (~1000 lines)
- Redis role reduced (no longer needed for WebSocket pub/sub)

### What stays the same

- Redis for Celery broker, caching, rate limiting
- Message content/format

## Phase 5 — Gradual supabase-py Migration (Ongoing)

As each service is touched for new features, replace SQLAlchemy queries with `supabase-py` client calls. No deadline — incremental migration over time.

## Infrastructure After Migration

### Removed from Docker

- PostgreSQL container (`rag-postgres-1`)
- Custom WebSocket server

### Still in Docker

- Redis (Celery broker + cache + rate limiting)
- Neo4j (knowledge graphs)
- Qdrant (vector search)
- Celery workers (document processing)

### Added

- Supabase CLI (local dev: `supabase start`)
- Supabase cloud project (production)

## Risks and Mitigations

| Risk                                          | Mitigation                                                                |
| --------------------------------------------- | ------------------------------------------------------------------------- |
| PgBouncer prepared statement incompatibility  | Disable prepared statement cache on asyncpg                               |
| Auth transition breaks existing sessions      | Dual JWT validation during transition period                              |
| Celery workers need network access to Storage | Workers connect to Supabase Storage API via service role key              |
| Supabase Realtime connection limits           | Verify 10K concurrent connection support; fallback to custom WS if needed |
| Schema migration errors                       | Test against Supabase CLI local before production                         |
