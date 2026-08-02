"""agent_outbox: transactional dispatch-intent record

P0-C (atomic accept). Expand-only — a single new table, no drops, no data
rewrites, safe to run against a live database.

One row per accepted agent submission, written in the SAME transaction as the
user message, the ``agent_runs`` row and the run's ``run.created`` event. The
row is a durable record that the run was *meant* to be dispatched; dispatch
itself is unchanged (the ``/stream`` path still runs the graph in-process and
stamps ``status='dispatched'`` afterwards). No relay/poller reads ``pending``
yet — that is a later work order.

``organization_id`` mirrors ``agent_runs.organization_id`` /
``agent_run_events.organization_id``: nullable (org-less users exist) and
deliberately not a foreign key.

``uq_agent_outbox_run`` makes "at most one dispatch intent per run" a database
invariant, so a retried submission that resolves to an existing run can never
queue a second dispatch for it.

Revision ID: c7d8e9f0a1b2
Revises: f2a3b4c5d6e7
Create Date: 2026-08-02
"""

from alembic import op  # type: ignore[attr-defined]

revision = "c7d8e9f0a1b2"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None

# Kept in sync with ``AGENT_OUTBOX_STATUS_CHECK`` in src/models/agent_outbox.py
# (a contract test asserts both match the AgentOutboxStatus vocabulary).
_STATUS_CHECK = "status IN ('pending', 'dispatched', 'failed')"


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS agent_outbox (
            id uuid PRIMARY KEY,
            run_id varchar(36) NOT NULL
                REFERENCES agent_runs(job_id) ON DELETE CASCADE,
            organization_id uuid,
            kind varchar(64) NOT NULL,
            payload jsonb NOT NULL DEFAULT '{{}}',
            status varchar(16) NOT NULL DEFAULT 'pending',
            dispatched_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            is_deleted boolean NOT NULL DEFAULT false,
            deleted_at timestamptz,
            CONSTRAINT ck_agent_outbox_status CHECK ({_STATUS_CHECK})
        )
        """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_outbox_id ON agent_outbox (id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_outbox_status_created "
        "ON agent_outbox (status, created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_outbox_run ON agent_outbox (run_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_outbox_org_status "
        "ON agent_outbox (organization_id, status)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_outbox_run "
        "ON agent_outbox (run_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent_outbox")
