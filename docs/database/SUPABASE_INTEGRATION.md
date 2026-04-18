# Supabase Integration Guide

## Overview

The RAG system uses Supabase as its managed infrastructure platform, replacing self-hosted Docker PostgreSQL with Supabase-managed PostgreSQL, Auth, and Storage. Neo4j, Redis/Celery, and Qdrant remain as external services.

```
Frontend (Next.js)
  ├── @supabase/supabase-js (Auth, Storage, Realtime)
  └── API calls → FastAPI backend

FastAPI Backend
  ├── Supabase PostgreSQL (via SQLAlchemy, PgBouncer-compatible)
  ├── Supabase Auth (JWT validation, user management)
  ├── Supabase Storage (document/image/audio/video uploads)
  ├── Redis (Celery broker, caching, rate limiting)
  ├── Neo4j (knowledge graphs)
  ├── Qdrant (vector search)
  └── Celery Workers (document processing, ML tasks)
```

## Local Development Setup

### Prerequisites

- [Supabase CLI](https://supabase.com/docs/guides/cli) installed
- Docker Desktop running (Supabase CLI uses Docker internally)

### Start Supabase

```bash
# Initialize (first time only)
cd /path/to/RAG_system
supabase init  # already done — supabase/ directory exists

# Start all Supabase services
supabase start

# View running service URLs and keys
supabase status
```

This starts:

- **API**: http://localhost:54321
- **Database**: postgresql://postgres:postgres@localhost:54322/postgres
- **Studio**: http://localhost:54323 (admin dashboard)
- **Inbucket**: http://localhost:54324 (email testing)
- **Analytics**: http://localhost:54327

### Environment Variables

Copy from `.env.example` and fill with values from `supabase status`:

```bash
# Frontend (.env.local)
NEXT_PUBLIC_SUPABASE_URL=http://localhost:54321
NEXT_PUBLIC_SUPABASE_ANON_KEY=<from supabase status>

# Backend (.env)
SUPABASE_URL=http://localhost:54321
SUPABASE_ANON_KEY=<from supabase status>
SUPABASE_SERVICE_ROLE_KEY=<from supabase status>
SUPABASE_DB_URL=postgresql://postgres:postgres@localhost:54322/postgres
SUPABASE_JWT_SECRET=<from supabase status>

# Optional: enable Supabase Storage (default: false, uses local filesystem)
SUPABASE_STORAGE_ENABLED=true
```

### Docker Integration

Backend containers connect to the host-running Supabase via `host.docker.internal`:

```yaml
# docker-compose.development.yml
environment:
  - SUPABASE_URL=http://host.docker.internal:54321
  - SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY:-}
  - SUPABASE_JWT_SECRET=${SUPABASE_JWT_SECRET:-}
  - SUPABASE_STORAGE_ENABLED=${SUPABASE_STORAGE_ENABLED:-false}
```

## Database

### Connection

The backend prefers `SUPABASE_DB_URL` over `DATABASE_URL`. The connection is configured for Supabase's transaction-mode PgBouncer:

```python
# backend/src/core/database.py
engine = create_async_engine(
    database_url,
    connect_args={
        "prepared_statement_cache_size": 0,  # PgBouncer compatibility
        "statement_cache_size": 0,
    },
    pool_recycle=300,
)
```

**Key file:** `backend/src/core/database.py`

### Migrations

Migrations live in `supabase/migrations/` and are applied via the Supabase CLI:

```bash
# Apply pending migrations
supabase db push

# Create a new migration
supabase migration new <migration_name>

# Reset database (destructive!)
supabase db reset
```

**Current migrations:**

| Migration                                                  | Purpose                                       |
| ---------------------------------------------------------- | --------------------------------------------- |
| `20260303204052_initial_schema.sql`                        | Full schema from 63 SQLAlchemy models         |
| `20260303213041_sync_users_to_auth.sql`                    | Link profiles to `auth.users`                 |
| `20260304232600_enable_rls_all_tables.sql`                 | Enable Row Level Security on all tables       |
| `20260304234900_fix_function_search_path_and_matviews.sql` | Security hardening for functions              |
| `20260305001600_harden_rls_policies.sql`                   | Replace permissive ALL with granular policies |
| `20260305002000_add_fk_indexes_drop_duplicates.sql`        | Performance: add missing FK indexes           |
| `20260305002500_drop_unused_indexes.sql`                   | Cleanup unused indexes                        |

### Row Level Security (RLS)

All 68 tables have RLS enabled. Policy strategy:

- **Backend uses `service_role` key** which bypasses RLS entirely
- **Frontend-accessible tables** have read-only policies for authenticated users
- **Write operations** go through the backend API (service_role), never directly from frontend

```sql
-- Example: read-only for authenticated, writes denied (backend uses service_role)
CREATE POLICY "select_authenticated" ON documents
  FOR SELECT TO authenticated USING (true);

CREATE POLICY "insert_deny" ON documents
  FOR INSERT TO authenticated WITH CHECK (false);
```

**Key file:** `supabase/migrations/20260305001600_harden_rls_policies.sql`

## Authentication

### Architecture

Supabase Auth manages user accounts in `auth.users`. The application links these to profile data via UUID:

```
auth.users (managed by Supabase)
  └── profiles table (linked via auth.users.id)
      └── organization membership, roles, preferences
```

### JWT Validation

The backend validates Supabase JWTs on every authenticated request:

```python
# backend/src/core/security.py
# Uses SUPABASE_JWT_SECRET for local validation
# Caches JWKS keys for production Supabase validation
```

Roles are stored in `app_metadata`: `ADMIN`, `CONTENT_MANAGER`, `ANALYST`, `USER`.

### Frontend Auth

```typescript
// frontend/src/lib/supabase.ts — singleton client
import { createClient } from "@supabase/supabase-js";

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
);
```

The auth store (`frontend/src/stores/authStore.ts`) manages:

- Session persistence with "remember me" (30-day option)
- Proactive token refresh 5 minutes before expiration
- LocalStorage persistence of tokens and user data

**Key files:**

- `frontend/src/lib/supabase.ts` — Client singleton
- `frontend/src/stores/authStore.ts` — Auth state management
- `backend/src/core/security.py` — JWT validation

## Storage

### Overview

Supabase Storage replaces local filesystem uploads. The system supports **dual storage backends** — toggled via `SUPABASE_STORAGE_ENABLED`:

- **`false` (default):** Files saved to local `uploads/` directory
- **`true`:** Files uploaded to Supabase Storage buckets

### Buckets

| Bucket      | File Types                             | Size Limit |
| ----------- | -------------------------------------- | ---------- |
| `documents` | PDF, text, spreadsheets, presentations | 500 MB     |
| `images`    | PNG, JPG, WebP, SVG                    | 500 MB     |
| `audio`     | MP3, WAV, FLAC                         | 500 MB     |
| `video`     | MP4, WebM, AVI                         | 500 MB     |
| `processed` | Processed/extracted content            | 500 MB     |

All buckets are **private** with RLS policies scoped by `organization_id`.

### Storage Path Format

```
{bucket}/{org_id}/{doc_id}/{timestamp}_{hex8}.{ext}
```

Example: `documents/org_abc123/doc_def456/1709000000_a1b2c3d4.pdf`

### Key Classes

**StorageHelper** (`backend/src/core/supabase_client.py`):

```python
helper = StorageHelper()
await helper.upload_file("documents", "org/doc/file.pdf", file_bytes, "application/pdf")
url = await helper.create_signed_url("documents", "org/doc/file.pdf", expires_in=3600)
data = await helper.download_file("documents", "org/doc/file.pdf")
```

**FileService** (`backend/src/services/documents/file_service.py`):

- Maps document types to buckets via `TYPE_TO_BUCKET`
- Generates storage keys with `generate_storage_key()`
- Lazy-loads `StorageHelper` only when storage is enabled

**Storage Utilities** (`backend/src/services/documents/storage_utils.py`):

- `local_file_for_document()` — Context manager that transparently handles local vs Supabase files
- `download_document_bytes()` — Download from either backend
- Checks `document.storage_backend` ('local' or 'supabase') to determine source

### Database Columns

The `documents` table has two storage-related columns:

| Column            | Type          | Description                                    |
| ----------------- | ------------- | ---------------------------------------------- |
| `storage_path`    | VARCHAR(2000) | Supabase Storage key (null for local files)    |
| `storage_backend` | VARCHAR(20)   | `'local'` or `'supabase'` (default: `'local'`) |

### Migrating Existing Files

```bash
# Dry run — see what would be migrated
python backend/migrations/migrate_files_to_storage.py

# Execute migration with verification
python backend/migrations/migrate_files_to_storage.py --execute --verify

# Clean up local files after verified migration
python backend/migrations/migrate_files_to_storage.py --execute --verify --cleanup-local
```

**Key files:**

- `backend/src/core/supabase_client.py` — StorageHelper class
- `backend/src/services/documents/file_service.py` — FileService
- `backend/src/services/documents/storage_utils.py` — Transparent local/Supabase abstraction
- `backend/migrations/setup_supabase_storage.py` — Bucket creation + RLS policies
- `backend/migrations/add_storage_columns.py` — Schema migration
- `backend/migrations/migrate_files_to_storage.py` — File migration script

## Configuration Reference

### Supabase Config

**`supabase/config.toml`:**

| Setting          | Value        | Notes                    |
| ---------------- | ------------ | ------------------------ |
| Project ID       | `RAG_system` |                          |
| API port         | `54321`      | Local dev                |
| DB port          | `54322`      | Direct PostgreSQL access |
| Studio port      | `54323`      | Admin dashboard          |
| Inbucket port    | `54324`      | Email testing            |
| Analytics port   | `54327`      |                          |
| Max file size    | 50 MiB       | Per-upload limit         |
| JWT expiry       | 3600s        | 1 hour                   |
| Auth enabled     | `true`       |                          |
| Storage enabled  | `true`       |                          |
| Realtime enabled | `true`       |                          |

### Backend Config

**`backend/src/core/config.py`:**

```python
SUPABASE_URL: str = "http://localhost:54321"
SUPABASE_ANON_KEY: str = ""
SUPABASE_SERVICE_ROLE_KEY: str = ""
SUPABASE_DB_URL: str = ""
SUPABASE_JWT_SECRET: str = ""
```

## Migration Status

The migration follows a phased approach. Current status:

| Phase   | Description                   | Status   |
| ------- | ----------------------------- | -------- |
| Phase 1 | Database connection swap      | Complete |
| Phase 2 | Supabase Auth                 | Complete |
| Phase 3 | Supabase Storage              | Complete |
| Phase 4 | Supabase Realtime             | Planned  |
| Phase 5 | Gradual supabase-py migration | Ongoing  |

See `docs/plans/2026-03-03-supabase-migration-design.md` for full migration design.

## Gotchas

- **PgBouncer**: Must set `prepared_statement_cache_size=0` on asyncpg — Supabase uses transaction-mode pooling which doesn't support prepared statements
- **Service role vs anon key**: Backend always uses `service_role` (bypasses RLS). Frontend uses `anon_key` (subject to RLS policies). Never expose the service role key to the frontend
- **Local dev**: Run `supabase start` before `docker-compose up` — the backend container connects to Supabase via `host.docker.internal`
- **Storage dual mode**: Check `SUPABASE_STORAGE_ENABLED` flag — when `false`, files save locally even if Supabase is running
- **JWT validation**: The backend caches JWKS keys (`_supabase_jwks_cache`) — restart the backend if you rotate keys
- **Database URL**: `SUPABASE_DB_URL` takes precedence over `DATABASE_URL` in `database.py`
- **Migration format**: Use Supabase CLI migrations (`supabase/migrations/`), not Alembic — the initial schema was exported and converted

## Useful Commands

```bash
# Supabase lifecycle
supabase start              # Start all services
supabase stop               # Stop all services
supabase status             # Show URLs and keys

# Database
supabase db push            # Apply migrations
supabase db reset           # Reset database (destructive)
supabase migration new X    # Create new migration
supabase db diff            # Show pending schema changes

# Storage
supabase storage ls         # List buckets

# Logs
supabase logs               # View service logs

# Studio
open http://localhost:54323  # Open admin dashboard
```

## File Reference

| File                                                 | Purpose                                    |
| ---------------------------------------------------- | ------------------------------------------ |
| `supabase/config.toml`                               | Supabase project configuration             |
| `supabase/migrations/*.sql`                          | Database migrations (7 files)              |
| `backend/src/core/config.py`                         | Supabase env var settings                  |
| `backend/src/core/database.py`                       | Database connection (PgBouncer-compatible) |
| `backend/src/core/security.py`                       | JWT validation + JWKS caching              |
| `backend/src/core/supabase_client.py`                | Supabase client singleton + StorageHelper  |
| `backend/src/services/documents/file_service.py`     | FileService with bucket mapping            |
| `backend/src/services/documents/storage_utils.py`    | Local/Supabase transparent abstraction     |
| `backend/migrations/setup_supabase_storage.py`       | Bucket creation + RLS policies             |
| `backend/migrations/add_storage_columns.py`          | Add storage_path/storage_backend columns   |
| `backend/migrations/migrate_files_to_storage.py`     | Migrate local files to Supabase Storage    |
| `frontend/src/lib/supabase.ts`                       | Frontend Supabase client                   |
| `frontend/src/stores/authStore.ts`                   | Auth state management                      |
| `docs/plans/2026-03-03-supabase-migration-design.md` | Migration design document                  |
