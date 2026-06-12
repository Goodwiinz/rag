# Models

SQLAlchemy ORM models for the `multimodal_rag_dev` PostgreSQL database. There are no standalone Pydantic schema files in this directory — request/response schemas live in the relevant API routers under `src/api/`. Every file here defines mapped ORM classes (and, in a few cases, supporting TypeDecorators or association tables).

## Base class and shared infrastructure

`base.py` defines two things everything else depends on:

- **`Base`** — `declarative_base()` instance; all ORM models inherit from it indirectly.
- **`BaseModel(Base)`** — abstract mixin that adds `id` (UUID primary key), `created_at`, `updated_at`, and soft-delete fields (`is_deleted`, `deleted_at`) with `soft_delete()` / `restore()` helpers. Also provides `to_dict()`.
- **`GUID`** — `TypeDecorator` that maps to PostgreSQL's native `UUID` type and `CHAR(36)` on SQLite (used in tests).

`encrypted_fields.py` provides `EncryptedType` and `encrypted_string()` — a `TypeDecorator` that encrypts/decrypts at bind/result time via `src.core.encryption`. Used on `User.first_name` and `User.last_name`.

`utils.py` contains `StringArray`, a cross-dialect type that becomes `ARRAY(TEXT)` on PostgreSQL and `JSON` on SQLite.

## Key files and entities

| File                                       | ORM class(es)                                                 | Table(s)                           | Purpose                                                                                                                                                                                                           |
| ------------------------------------------ | ------------------------------------------------------------- | ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `organization.py`                          | `Organization`                                                | `organizations`                    | Multi-tenant root; owns users and documents; tracks storage quota by tier (free / professional / enterprise)                                                                                                      |
| `user.py`                                  | `User`                                                        | `users`                            | User accounts; role hierarchy (user → analyst → content_manager → admin); bcrypt-hashed password; encrypted first/last name                                                                                       |
| `workspace.py`                             | `Workspace`                                                   | `workspaces`                       | Top-level container owned by an organization; holds conversations and collections                                                                                                                                 |
| `conversation.py`                          | `Conversation`                                                | `conversations`                    | Named project area inside a workspace; groups related threads                                                                                                                                                     |
| `thread.py`                                | `Thread`                                                      | `threads`                          | Granular line of inquiry inside a conversation; owns ordered `ChatMessage` records; tracks `message_count` and `token_count`                                                                                      |
| `chat_message.py`                          | `ChatMessage`                                                 | `chat_messages`                    | Individual messages; roles: `user`, `assistant`, `system`, `tool`                                                                                                                                                 |
| `collection.py`                            | `Collection`                                                  | `collections`                      | Organized document groups inside a workspace; doubles as a research project container                                                                                                                             |
| `document.py`                              | `Document`                                                    | `documents`                        | Core entity: uploaded files of any modality (text, PDF, image, audio, video, spreadsheet, presentation). Tracks processing pipeline state, Qdrant vector IDs, TSVECTOR for full-text search, and SHA-256 checksum |
| `entity.py`                                | `Entity`                                                      | `entities`, `entity_relationships` | NLP-extracted entities with type, confidence, and optional Neo4j graph node ID; self-referential many-to-many through `entity_relationships` association table                                                    |
| `citation.py`                              | `Citation`                                                    | `citations`                        | Provenance records linking RAG-retrieved chunks to `ChatMessage` responses; supports both internal `document_id` and external references (e.g., arXiv IDs)                                                        |
| `generated_draft.py`                       | `GeneratedDraft`                                              | `generated_drafts`                 | Versioned AI-generated literature review drafts attached to a `Collection` (research project); max 10 versions per project                                                                                        |
| `project_note.py`                          | `ProjectNote`                                                 | `project_notes`                    | User-authored markdown notes inside a research project; linkable to specific document UUIDs                                                                                                                       |
| `research_project.py`                      | `ResearchProject`                                             | `research_projects`                | Lightweight research project owned by a user; used by the agent pipeline alongside `Collection`-based projects                                                                                                    |
| `permission.py`                            | `Permission`, `Role`                                          | `permissions`, `roles`             | Fine-grained RBAC; permissions are scoped (read/write/delete/manage/admin) per category (documents, analytics, audit, etc.)                                                                                       |
| `audit.py`                                 | `AuditEvent`                                                  | `audit_events`                     | Immutable compliance log for auth, authorization, and data change events                                                                                                                                          |
| `encrypted_user.py`                        | `EncryptedUserProfile`, `EncryptedOrganizationProfile`        | —                                  | Extended encrypted PII attached 1-to-1 to `User` and `Organization`                                                                                                                                               |
| `user_session.py`                          | `UserSession`                                                 | `user_sessions`                    | Active session tracking (JWT / cookie lifetime)                                                                                                                                                                   |
| `user_quota.py`                            | `UserQuota`                                                   | `user_quotas`                      | Per-user API and storage quota overrides                                                                                                                                                                          |
| `analytics_event.py`                       | `AnalyticsEvent`                                              | `analytics_events`                 | Product analytics events (page views, feature usage)                                                                                                                                                              |
| `ab_testing.py` / `ab_testing_models.py`   | `Experiment`, `Variant`, `Assignment`                         | `experiments`, …                   | A/B experiment definitions and user assignments                                                                                                                                                                   |
| `search.py` / `search_analytics.py`        | `SearchQuery`, `SearchResult`, `SearchSession`, `SearchEvent` | `search_*`                         | Search activity logging and analytics                                                                                                                                                                             |
| `knowledge_graph.py` / `graph.py`          | KG query/result helpers                                       | —                                  | Utility models for Neo4j query results and graph API responses                                                                                                                                                    |
| `vector.py`                                | Qdrant vector helpers                                         | —                                  | Lightweight wrappers for Qdrant payloads and results                                                                                                                                                              |
| `processing.py` / `document_processing.py` | `ProcessingJob`, `ProcessingHistory`, `DocumentVersion`       | `processing_jobs`, …               | Document ingestion pipeline state; supports retry tracking                                                                                                                                                        |

## Conventions

**Status mapping.** `Document.processing_status` uses `ProcessingStatus` enum values (`pending`, `processing`, `completed`, `failed`, `retrying`). The `get_mapped_status()` method and `to_dict()` translate these to frontend-visible strings: `pending → queued`, `completed → indexed`, `retrying → processing`. Always use the mapped form in API responses, never the raw enum value for `pending` or `completed`.

**Enums.** Local Python enums (`PyEnum`) are used for type safety. When bound to SQLAlchemy `Enum(...)` columns, the `values_callable=lambda x: [e.value for e in x]` pattern is used on columns that need lowercase string values stored in the database (e.g., `Thread.status`, `ChatMessage.role`). Shared application enums live in `src/shared/enums.py`.

**Soft delete.** `BaseModel.soft_delete()` sets `is_deleted = True` and records `deleted_at`; hard deletes are never performed on core entities. Queries should always filter `is_deleted == False` explicitly — there is no global query filter.

**Indexes.** Multi-column composite indexes are declared in `__table_args__` with the naming convention `idx_<table>_<columns>` (e.g., `idx_document_org_status`). Single-column indexes use the `index=True` column argument.

**Encrypted fields.** Sensitive PII (names, extended profiles) uses `encrypted_string()` from `encrypted_fields.py`, which wraps `EncryptedType` backed by `src.core.encryption`. The column stores ciphertext as `TEXT`; decryption is transparent at ORM level.

## Migrations

Schema changes are managed with Alembic. Migration files live in `backend/alembic/versions/`. To generate a new revision after changing a model:

```bash
cd backend
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

The `alembic.ini` and `env.py` are configured to import all models via `src.models` before autogenerate inspection. Adding a new model file requires adding its import to `src/models/__init__.py` to ensure Alembic detects it.
