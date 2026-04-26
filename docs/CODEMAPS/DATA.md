# NOUS — Data CODEMAP

> Database schemas (PostgreSQL, Neo4j, Qdrant, Redis), migration ordering, seeders.
> Last generated: 2026-04-26

## Data stores

| Store | Port | Purpose |
|---|---|---|
| PostgreSQL (Supabase) | 5432 | Primary relational store — users, documents, threads, projects, analytics |
| Neo4j | 7687 | Knowledge graph — entities, relationships, citations |
| Qdrant | 6333 | Vector store — document embeddings, semantic search |
| Redis / Valkey | 6379 | Cache, Celery broker, WebSocket pub/sub, rate limiting |

## PostgreSQL schema

Managed by **Alembic** (`backend/alembic/`). The canonical migration chain is in `backend/alembic/versions/`.

### Migration chain (selected key revisions)

| Revision | Description |
|---|---|
| `258df00ea837` | Initial schema — users, documents, threads |
| `a1b2c3...` | Thread-centric chat schema |
| `add_api_keys_table` | API key management |
| `add_search_analytics_table` | Search event logging |
| `b2c3d4e5...` | Full-text search for threads (pg_trgm) |
| `c8e2f1a9...` | External citation support |
| `d9f3g4h5...` | Extended citation metadata |
| `e0g4h5i6...` | Citation relationship table |
| `f1h5i6j7...` | Collections + research extensions |
| `f931599b...` | Enhanced document processing columns |
| `g2i6j7k8...` | Project notes |
| `h3j7k8l9...` | Generated drafts |
| `i4k8l9m0...` | Project-thread integration |

Run migrations: `cd backend && alembic upgrade head`  
Create new: `alembic revision --autogenerate -m "describe_change"`  
Roll back one: `alembic downgrade -1`

### Raw SQL migrations (`database/migrations/`)

Legacy SQL files — used for PostgreSQL features (views, triggers, partitioning) that Alembic doesn't autogenerate. Applied manually or via deploy scripts. These have numeric prefix collisions (`001_*`, `007_*`, `008_*`) — **do not rely on filename order; read each file's header comment for application context.**

Key files:

| File | Purpose |
|---|---|
| `006_document_upload_schema.sql` | Document storage columns |
| `007_analytics_schema.sql` | Analytics event tables |
| `009_realtime_status_optimizations.sql` | Realtime status indexes |
| `011_realtime_document_status_enhancements.sql` | Final realtime status schema |
| `012_ai_document_qa_system.sql` | QA system tables |

Also in `database/`:

| File | Purpose |
|---|---|
| `indexing_strategy.sql` | Index creation guidelines + DDL |
| `partitioning_strategy.sql` | Table partitioning (analytics events) |
| `performance_optimization.sql` | PG tuning queries |
| `monitoring_schema.sql` | Monitoring/metrics tables |
| `data_retention_policies.sql` | TTL + cleanup jobs |
| `triggers/` | PG trigger functions |
| `views/` | Materialized + regular views |
| `procedures/` | Stored procedures |

## Neo4j schema

Graph database for the knowledge graph. No migration tool — schema is enforced via:

- Constraints: `database/init_knowledge_graph_db.sql` (Cypher `CREATE CONSTRAINT`)
- Indexes: `database/neo4j_performance.cypher`
- Init script: `database/neo4j-init.cypher`

### Core node labels

| Label | Properties | Purpose |
|---|---|---|
| `Entity` | id, name, type, project_id | Extracted entities (person, org, concept) |
| `Document` | id, title, url, project_id | Ingested documents |
| `Concept` | id, name, description | Domain concepts |
| `Citation` | id, doi, title, authors | Academic citations |

### Core relationships

`MENTIONS`, `RELATES_TO`, `CITES`, `PART_OF`, `AUTHORED_BY`

Qdrant collection config: `database/qdrant_knowledge_graph_collections.json`  
Redis KG cache config: `database/redis_knowledge_graph_config.lua`

## Qdrant collections

| Collection | Dimensions | Distance | Content |
|---|---|---|---|
| `documents` | 1536 (OpenAI) | Cosine | Document chunk embeddings |
| `entities` | 1536 | Cosine | Entity embeddings for semantic KG search |

Optimization config: `database/qdrant_optimization.py`

## Redis / Valkey usage

| Key pattern | TTL | Purpose |
|---|---|---|
| `session:<user_id>` | 24h | Auth session cache |
| `rate:<ip>:<endpoint>` | 60s | Rate limiting counters |
| `ws:room:<thread_id>` | — | WebSocket pub/sub channel |
| `celery:*` | — | Celery task queue / results |
| `kg:cache:<query_hash>` | 5m | KG query result cache |

## Supabase specifics

- Session pooler mode: `pool_size = max_clients`. Default 15 saturates on Nano — bumped to 25.
- Connection string: use `postgresql://` (not `postgresql+asyncpg://`) for Alembic + psycopg v3.
- Storage bucket: documents are stored in Supabase Storage; file paths in `document.storage_path`.

## Seeding / fixtures

Test fixtures: `data/datasets/` — 4 fixture files used in integration tests.  
Dev seed: `backend/scripts/seed_dev_data.py` (if present).

## Adding a new table

1. Create Alembic migration: `cd backend && alembic revision --autogenerate -m "add_<table>"`.
2. Add SQLAlchemy model in `backend/src/models/<domain>.py`.
3. Add Pydantic schema in `backend/src/schemas/<domain>.py`.
4. If the table needs indexing strategy docs, add to `database/indexing/`.
5. If the table has a TTL/retention policy, add to `database/data_retention_policies.sql`.
