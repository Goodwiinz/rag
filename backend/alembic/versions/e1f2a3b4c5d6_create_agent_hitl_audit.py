"""create agent_hitl_audit (durable HITL approve/reject trail)

Durable complement to the hitl_interrupt_raised / hitl_decision structlog
events: one immutable row per destructive-tool approve/reject decision so
"who approved which action, when" survives log retention for audit queries.
See src/models/agent_hitl_audit.py.

Inspector-guarded create: the model is registered in src/models/__init__, so
Base.metadata.create_all already makes this table on bootstrap-provisioned
databases. Guarding on table presence makes the migration a no-op there and a
real create on migrate-only databases — the same dual-provisioning hazard the
analytics_kpis migration documents.

Revision ID: e1f2a3b4c5d6
Revises: b7d4e9a1c3f2
Create Date: 2026-06-13
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "e1f2a3b4c5d6"
down_revision = "b7d4e9a1c3f2"
branch_labels = None
depends_on = None

_TABLE = "agent_hitl_audit"


def upgrade() -> None:
    bind = op.get_bind()
    if _TABLE in sa.inspect(bind).get_table_names():
        return  # already created via Base.metadata.create_all
    op.create_table(
        _TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("thread_id", sa.String(length=255), nullable=True),
        sa.Column("tool_names", sa.JSON(), nullable=False),
        sa.Column("tool_args", sa.JSON(), nullable=True),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_agent_hitl_audit_thread_id", _TABLE, ["thread_id"]
    )
    op.create_index("ix_agent_hitl_audit_decision", _TABLE, ["decision"])
    op.create_index(
        "idx_agent_hitl_audit_org_created", _TABLE, ["organization_id", "created_at"]
    )
    op.create_index(
        "idx_agent_hitl_audit_user_created", _TABLE, ["user_id", "created_at"]
    )


def downgrade() -> None:
    bind = op.get_bind()
    if _TABLE not in sa.inspect(bind).get_table_names():
        return
    op.drop_table(_TABLE)  # drops its indexes with it
