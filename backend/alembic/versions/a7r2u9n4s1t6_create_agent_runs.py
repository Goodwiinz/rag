"""create agent_runs (durable Postgres projection of agent jobs)

The agent job store is Redis-only (TTL 1h) — a Redis failover 404s every
poller and orphans HITL confirm state (audit findings X1/D7). This table
projects every job-status transition so run status survives Redis loss; the
poll endpoint falls back to it on a Redis miss. Lease columns are claimed by
the stuck-run sweeper that lands in a follow-up PR. See
src/models/agent_run.py and src/services/agent/agent_run_service.py.

Inspector-guarded create: the model is registered in src/models/__init__, so
Base.metadata.create_all already makes this table on bootstrap-provisioned
databases. Guarding on table presence makes the migration a no-op there and a
real create on migrate-only databases (same pattern as agent_hitl_audit).

Revision ID: a7r2u9n4s1t6
Revises: merge_heads_2026_07_06
Create Date: 2026-07-11
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "a7r2u9n4s1t6"
down_revision = "merge_heads_2026_07_06"
branch_labels = None
depends_on = None

_TABLE = "agent_runs"

# Keep in lockstep with src/shared/enums.py::JobStatus. "error" is
# intentionally absent — writers collapse it to "failed".
_STATUS_CHECK = (
    "status IN ('running', 'awaiting_confirmation', "
    "'completed', 'failed', 'cancelled')"
)


def upgrade() -> None:
    bind = op.get_bind()
    if _TABLE in sa.inspect(bind).get_table_names():
        return  # already created via Base.metadata.create_all
    op.create_table(
        _TABLE,
        sa.Column("job_id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("thread_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("lease_owner", sa.String(length=255), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(_STATUS_CHECK, name="ck_agent_runs_status"),
    )
    op.create_index(
        "idx_agent_runs_org_updated", _TABLE, ["organization_id", "updated_at"]
    )
    op.create_index("idx_agent_runs_status_updated", _TABLE, ["status", "updated_at"])
    op.create_index(
        "uq_agent_runs_idempotency_key",
        _TABLE,
        ["idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if _TABLE not in sa.inspect(bind).get_table_names():
        return
    op.drop_table(_TABLE)  # drops its indexes with it
