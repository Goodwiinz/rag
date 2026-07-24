"""add agent_run_events and durable run lifecycle columns

Hermes event runtime, PR 1 of 6 (docs/plans/2026-07-20-hermes-event-runtime-design.md):

- ``agent_run_events``: append-only ordered facts per run, unique (run_id, seq).
- ``agent_runs`` grows correlation FKs (thread/conversation/project/messages/
  snapshot), client idempotency metadata, ``last_event_seq``, lifecycle
  timestamps, structured error/usage/metadata, and ``lease_generation``.
- ``thread_id`` converts String(255) → uuid FK. Invalid strings and dangling
  uuids (the legacy job-id fallback for thread-less runs) are NULLed first —
  losing a legacy correlation must not fail deployment.
- The status CHECK is rebuilt to admit ``queued``/``stopping``.
- One-active-run-per-thread partial unique index; older duplicate non-terminal
  rows are terminalized (``superseded_by_migration``) first so index creation
  cannot fail.
- The global idempotency unique index is re-scoped per user.

Everything is IF NOT EXISTS / to_regclass-guarded: bootstrap-provisioned
databases already have the new shape via Base.metadata.create_all.

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7g8h9
Create Date: 2026-07-20
"""

from alembic import op  # type: ignore[attr-defined]

revision = "d5e6f7a8b9c0"
down_revision = "c4d5e6f7g8h9"
branch_labels = None
depends_on = None

_NEW_STATUS_CHECK = (
    "status IN ('queued', 'running', 'awaiting_confirmation', 'stopping', "
    "'completed', 'failed', 'cancelled')"
)
_ACTIVE_STATUSES = "('queued', 'running', 'awaiting_confirmation', 'stopping')"

_RUN_COLUMNS = [
    ("conversation_id", "uuid"),
    ("project_id", "uuid"),
    ("user_message_id", "uuid"),
    ("assistant_message_id", "uuid"),
    ("runtime_snapshot_id", "uuid"),
    ("client_message_id", "varchar(255)"),
    ("last_event_seq", "integer NOT NULL DEFAULT 0"),
    ("started_at", "timestamptz"),
    ("completed_at", "timestamptz"),
    ("cancel_requested_at", "timestamptz"),
    ("error_code", "varchar(64)"),
    ("usage", "jsonb"),
    ("run_metadata", "jsonb"),
    ("lease_generation", "integer NOT NULL DEFAULT 0"),
]

# FK targets for the new correlation columns (added NOT VALID-free because the
# columns start NULL). thread_id gets its FK after data conversion below.
_RUN_FOREIGN_KEYS = [
    ("fk_agent_runs_conversation_id", "conversation_id", "conversations(id)"),
    ("fk_agent_runs_project_id", "project_id", "collections(id)"),
    ("fk_agent_runs_user_message_id", "user_message_id", "chat_messages(id)"),
    (
        "fk_agent_runs_assistant_message_id",
        "assistant_message_id",
        "chat_messages(id)",
    ),
    (
        "fk_agent_runs_runtime_snapshot_id",
        "runtime_snapshot_id",
        "agent_runtime_snapshots(id)",
    ),
]

_UUID_REGEX = (
    "'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-" "[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'"
)


def upgrade() -> None:
    # ------------------------------------------------------------------
    # agent_run_events (idempotent: bootstrap DBs create it via create_all)
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS agent_run_events (
            id uuid PRIMARY KEY,
            run_id varchar(36) NOT NULL
                REFERENCES agent_runs(job_id) ON DELETE CASCADE,
            seq integer NOT NULL,
            event_type varchar(64) NOT NULL,
            payload jsonb NOT NULL DEFAULT '{}',
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            is_deleted boolean NOT NULL DEFAULT false,
            deleted_at timestamptz,
            CONSTRAINT uq_agent_run_events_run_seq UNIQUE (run_id, seq)
        )
        """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_agent_run_events_id " "ON agent_run_events (id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_run_events_run_seq "
        "ON agent_run_events (run_id, seq)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_run_events_created_at "
        "ON agent_run_events (created_at)"
    )

    # ------------------------------------------------------------------
    # agent_runs: new columns (guarded — table always exists by now)
    # ------------------------------------------------------------------
    op.execute("""
        DO $$
        BEGIN
            IF to_regclass('public.agent_runs') IS NULL THEN
                RAISE EXCEPTION 'agent_runs missing — run a7r2u9n4s1t6 first';
            END IF;
        END $$
        """)
    for name, ddl_type in _RUN_COLUMNS:
        op.execute(
            f'ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS "{name}" {ddl_type}'
        )
    for constraint, column, target in _RUN_FOREIGN_KEYS:
        op.execute(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = '{constraint}'
                ) THEN
                    ALTER TABLE agent_runs
                        ADD CONSTRAINT {constraint}
                        FOREIGN KEY ({column}) REFERENCES {target}
                        ON DELETE SET NULL;
                END IF;
            END $$
            """)

    # ------------------------------------------------------------------
    # thread_id: String(255) → uuid FK, honestly. NULL anything that cannot
    # survive the conversion BEFORE altering the type / adding the FK.
    # ------------------------------------------------------------------
    op.execute(f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'agent_runs'
                  AND column_name = 'thread_id'
                  AND data_type <> 'uuid'
            ) THEN
                -- Non-uuid strings cannot convert.
                UPDATE agent_runs SET thread_id = NULL
                WHERE thread_id IS NOT NULL
                  AND thread_id !~ {_UUID_REGEX};
                -- Dangling uuids (job-id fallback) would violate the FK.
                UPDATE agent_runs SET thread_id = NULL
                WHERE thread_id IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM threads
                      WHERE threads.id = agent_runs.thread_id::uuid
                  );
                ALTER TABLE agent_runs
                    ALTER COLUMN thread_id TYPE uuid
                    USING thread_id::uuid;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'fk_agent_runs_thread_id'
            ) THEN
                ALTER TABLE agent_runs
                    ADD CONSTRAINT fk_agent_runs_thread_id
                    FOREIGN KEY (thread_id) REFERENCES threads(id)
                    ON DELETE SET NULL;
            END IF;
        END $$
        """)

    # ------------------------------------------------------------------
    # Status domain: admit queued/stopping.
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE agent_runs DROP CONSTRAINT IF EXISTS ck_agent_runs_status")
    op.execute(
        f"ALTER TABLE agent_runs ADD CONSTRAINT ck_agent_runs_status "
        f"CHECK ({_NEW_STATUS_CHECK})"
    )

    # ------------------------------------------------------------------
    # One active run per thread. Terminalize older duplicates first so the
    # unique index cannot fail creation; keep the newest non-terminal row.
    # ------------------------------------------------------------------
    op.execute(f"""
        UPDATE agent_runs SET
            status = 'failed',
            error_code = 'superseded_by_migration',
            error = 'Terminalized by migration: another run was active on this thread.',
            updated_at = now()
        WHERE job_id IN (
            SELECT job_id FROM (
                SELECT job_id, ROW_NUMBER() OVER (
                    PARTITION BY thread_id ORDER BY updated_at DESC
                ) AS rn
                FROM agent_runs
                WHERE thread_id IS NOT NULL AND status IN {_ACTIVE_STATUSES}
            ) ranked WHERE ranked.rn > 1
        )
        """)
    op.execute(
        f"CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_runs_active_thread "
        f"ON agent_runs (thread_id) "
        f"WHERE thread_id IS NOT NULL AND status IN {_ACTIVE_STATUSES}"
    )

    # ------------------------------------------------------------------
    # Idempotency uniqueness: global → per-user.
    # ------------------------------------------------------------------
    op.execute("DROP INDEX IF EXISTS uq_agent_runs_idempotency_key")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_runs_user_idempotency_key "
        "ON agent_runs (user_id, idempotency_key) "
        "WHERE idempotency_key IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent_run_events")
    op.execute("DROP INDEX IF EXISTS uq_agent_runs_active_thread")
    op.execute("DROP INDEX IF EXISTS uq_agent_runs_user_idempotency_key")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_runs_idempotency_key "
        "ON agent_runs (idempotency_key) WHERE idempotency_key IS NOT NULL"
    )
    op.execute(
        "ALTER TABLE agent_runs DROP CONSTRAINT IF EXISTS fk_agent_runs_thread_id"
    )
    # Legacy code reads thread_id as a string — restore the varchar shape.
    op.execute(
        "ALTER TABLE agent_runs ALTER COLUMN thread_id TYPE varchar(255) "
        "USING thread_id::text"
    )
    for constraint, _column, _target in _RUN_FOREIGN_KEYS:
        op.execute(f"ALTER TABLE agent_runs DROP CONSTRAINT IF EXISTS {constraint}")
    for name, _ddl_type in _RUN_COLUMNS:
        op.execute(f'ALTER TABLE agent_runs DROP COLUMN IF EXISTS "{name}"')
    # Normalize the new lifecycle states away BEFORE re-adding the old CHECK,
    # else the constraint add fails on live rows.
    op.execute("UPDATE agent_runs SET status = 'running' WHERE status = 'queued'")
    op.execute("UPDATE agent_runs SET status = 'cancelled' WHERE status = 'stopping'")
    op.execute("ALTER TABLE agent_runs DROP CONSTRAINT IF EXISTS ck_agent_runs_status")
    op.execute(
        "ALTER TABLE agent_runs ADD CONSTRAINT ck_agent_runs_status "
        "CHECK (status IN ('running', 'awaiting_confirmation', "
        "'completed', 'failed', 'cancelled'))"
    )
