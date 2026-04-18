"""Add missing performance indexes — threads, messages, workspaces, research pipeline

Revision ID: n9p2q3r4s5t6
Revises: m8o1p2q3r4s5
Create Date: 2026-04-15 10:00:00.000000

Audit findings: 40-50 missing indexes identified across newer tables that were
added after the initial performance_indexes_n_plus_1_fix migration. Covers:

  Tier 1 — threads, chat_messages, workspaces, collections, processing_jobs
  Tier 2 — research_runs, research_steps, research_sources, research_evidence,
            evaluation_jobs, websocket_connections
  Tier 3 — generated_drafts version/current lookups

All indexes use CONCURRENTLY-safe `op.create_index` (Alembic default).
Run with `--sql` to preview DDL before applying to production.
"""

from alembic import op

revision = "n9p2q3r4s5t6"
down_revision = "m8o1p2q3r4s5"
branch_labels = None
depends_on = None


def upgrade():
    # ──────────────────────────────────────────────────────────────────────
    # TIER 1 — Core chat / workspace tables  (highest query frequency)
    # ──────────────────────────────────────────────────────────────────────

    # threads
    # conversation_id already has a single-column index from the model; add
    # composite so ORDER BY created_at DESC pagination uses index-only scans.
    op.create_index(
        "idx_threads_conversation_created",
        "threads",
        ["conversation_id", "created_at"],
    )
    # created_by_id — FK with no index at all; user's thread listings hit this.
    op.create_index("idx_threads_created_by", "threads", ["created_by_id"])
    # status — filtered on every active-thread listing.
    op.create_index("idx_threads_status", "threads", ["status"])
    # last_message_at — used for ordering conversation thread lists.
    op.create_index("idx_threads_last_message_at", "threads", ["last_message_at"])

    # chat_messages
    # thread_id already has a single-column index; composite enables fast
    # paginated message retrieval without a filesort.
    op.create_index(
        "idx_chat_messages_thread_created",
        "chat_messages",
        ["thread_id", "created_at"],
    )
    # user_id — FK with no index; needed for "messages by user" queries.
    op.create_index("idx_chat_messages_user", "chat_messages", ["user_id"])
    # role — filtered when fetching only user / assistant messages.
    op.create_index("idx_chat_messages_role", "chat_messages", ["role"])

    # workspaces
    # owner_id and organization_id are FKs with no indexes at all.
    op.create_index("idx_workspaces_owner", "workspaces", ["owner_id"])
    op.create_index("idx_workspaces_organization", "workspaces", ["organization_id"])
    # Composite for "active workspaces owned by user" — most common dashboard query.
    op.create_index(
        "idx_workspaces_owner_archived",
        "workspaces",
        ["owner_id", "is_archived"],
    )

    # collections
    # workspace_id already has a single-column index; add composites for the
    # two most common filter patterns.
    op.create_index(
        "idx_collections_workspace_created",
        "collections",
        ["workspace_id", "created_at"],
    )
    op.create_index(
        "idx_collections_workspace_status",
        "collections",
        ["workspace_id", "research_status"],
    )

    # processing_jobs
    # document_id and organization_id have no indexes at all (only job_type,
    # status, priority, and celery_task_id are indexed in the model).
    # The composite leading columns also serve as implicit single-column indexes.
    op.create_index(
        "idx_processing_jobs_document_status",
        "processing_jobs",
        ["document_id", "status"],
    )
    op.create_index(
        "idx_processing_jobs_org_status",
        "processing_jobs",
        ["organization_id", "status"],
    )
    op.create_index(
        "idx_processing_jobs_org_created",
        "processing_jobs",
        ["organization_id", "created_at"],
    )

    # ──────────────────────────────────────────────────────────────────────
    # TIER 2 — Research pipeline + evaluation + WebSocket tables
    # ──────────────────────────────────────────────────────────────────────

    # research_runs — blueprint_id FK and status column both lack indexes.
    op.create_index("idx_research_runs_blueprint", "research_runs", ["blueprint_id"])
    op.create_index("idx_research_runs_status", "research_runs", ["status"])
    op.create_index(
        "idx_research_runs_blueprint_status",
        "research_runs",
        ["blueprint_id", "status"],
    )

    # research_steps — run_id is a FK with NO index (risky for cascade deletes
    # and step listing queries — every query does a full table scan).
    op.create_index("idx_research_steps_run", "research_steps", ["run_id"])
    # Composite covers ordered step retrieval (SELECT … ORDER BY step_index).
    op.create_index(
        "idx_research_steps_run_index",
        "research_steps",
        ["run_id", "step_index"],
    )

    # research_sources — run_id FK with no index.
    op.create_index("idx_research_sources_run", "research_sources", ["run_id"])

    # research_evidence — both FKs have no indexes.
    op.create_index("idx_research_evidence_step", "research_evidence", ["step_id"])
    op.create_index(
        "idx_research_evidence_source", "research_evidence", ["source_id"]
    )

    # evaluation_jobs — individual indexes exist on user_id, organization_id,
    # and status; add composites for the dashboard filter patterns.
    op.create_index(
        "idx_evaluation_jobs_org_status",
        "evaluation_jobs",
        ["organization_id", "status"],
    )
    op.create_index(
        "idx_evaluation_jobs_user_created",
        "evaluation_jobs",
        ["user_id", "created_at"],
    )

    # websocket_connections — connection_status has no index; composite with
    # user_id covers "active connections for user" lookups.
    op.create_index(
        "idx_ws_connections_user_status",
        "websocket_connections",
        ["user_id", "connection_status"],
    )

    # ──────────────────────────────────────────────────────────────────────
    # TIER 3 — Generated drafts version management
    # ──────────────────────────────────────────────────────────────────────

    # generated_drafts — project_id has a single-column index; composites
    # support "latest draft for project" (version DESC) and "current draft"
    # queries that are run on every project page load.
    op.create_index(
        "idx_generated_drafts_project_version",
        "generated_drafts",
        ["project_id", "version"],
    )
    op.create_index(
        "idx_generated_drafts_project_current",
        "generated_drafts",
        ["project_id", "is_current"],
    )


def downgrade():
    # Tier 3
    op.drop_index(
        "idx_generated_drafts_project_current", table_name="generated_drafts"
    )
    op.drop_index(
        "idx_generated_drafts_project_version", table_name="generated_drafts"
    )

    # Tier 2
    op.drop_index(
        "idx_ws_connections_user_status", table_name="websocket_connections"
    )
    op.drop_index("idx_evaluation_jobs_user_created", table_name="evaluation_jobs")
    op.drop_index("idx_evaluation_jobs_org_status", table_name="evaluation_jobs")
    op.drop_index("idx_research_evidence_source", table_name="research_evidence")
    op.drop_index("idx_research_evidence_step", table_name="research_evidence")
    op.drop_index("idx_research_sources_run", table_name="research_sources")
    op.drop_index("idx_research_steps_run_index", table_name="research_steps")
    op.drop_index("idx_research_steps_run", table_name="research_steps")
    op.drop_index(
        "idx_research_runs_blueprint_status", table_name="research_runs"
    )
    op.drop_index("idx_research_runs_status", table_name="research_runs")
    op.drop_index("idx_research_runs_blueprint", table_name="research_runs")

    # Tier 1
    op.drop_index(
        "idx_processing_jobs_org_created", table_name="processing_jobs"
    )
    op.drop_index("idx_processing_jobs_org_status", table_name="processing_jobs")
    op.drop_index(
        "idx_processing_jobs_document_status", table_name="processing_jobs"
    )
    op.drop_index(
        "idx_collections_workspace_status", table_name="collections"
    )
    op.drop_index(
        "idx_collections_workspace_created", table_name="collections"
    )
    op.drop_index("idx_workspaces_owner_archived", table_name="workspaces")
    op.drop_index("idx_workspaces_organization", table_name="workspaces")
    op.drop_index("idx_workspaces_owner", table_name="workspaces")
    op.drop_index("idx_chat_messages_role", table_name="chat_messages")
    op.drop_index("idx_chat_messages_user", table_name="chat_messages")
    op.drop_index(
        "idx_chat_messages_thread_created", table_name="chat_messages"
    )
    op.drop_index("idx_threads_last_message_at", table_name="threads")
    op.drop_index("idx_threads_status", table_name="threads")
    op.drop_index("idx_threads_created_by", table_name="threads")
    op.drop_index(
        "idx_threads_conversation_created", table_name="threads"
    )
