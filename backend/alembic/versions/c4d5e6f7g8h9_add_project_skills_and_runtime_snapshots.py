"""add immutable project skills and agent runtime snapshots

Revision ID: c4d5e6f7g8h9
Revises: b8s2a4t7e0l3
Create Date: 2026-07-19
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c4d5e6f7g8h9"
down_revision = "b8s2a4t7e0l3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_skills",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("normalized_name", sa.String(length=128), nullable=False),
        sa.Column("active_version_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["collections.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "project_id",
            "normalized_name",
            name="uq_project_skills_project_normalized_name",
        ),
    )
    op.create_index("ix_project_skills_id", "project_skills", ["id"])
    op.create_index("ix_project_skills_project_id", "project_skills", ["project_id"])
    op.create_index(
        "ix_project_skills_created_by_id", "project_skills", ["created_by_id"]
    )
    op.create_index(
        "idx_project_skills_project_archived",
        "project_skills",
        ["project_id", "is_archived"],
    )

    op.create_table(
        "project_skill_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("skill_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("parsed_name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["skill_id"], ["project_skills.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "skill_id", "version", name="uq_project_skill_versions_skill_version"
        ),
        sa.CheckConstraint(
            "version > 0", name="ck_project_skill_versions_positive_version"
        ),
    )
    op.create_index("ix_project_skill_versions_id", "project_skill_versions", ["id"])
    op.create_index(
        "ix_project_skill_versions_skill_id", "project_skill_versions", ["skill_id"]
    )
    op.create_index(
        "ix_project_skill_versions_content_hash",
        "project_skill_versions",
        ["content_hash"],
    )
    op.create_index(
        "ix_project_skill_versions_author_id", "project_skill_versions", ["author_id"]
    )

    op.create_table(
        "project_skill_version_scans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scan_state", sa.String(length=16), nullable=False),
        sa.Column(
            "findings",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("scanner_version", sa.String(length=64), nullable=False),
        sa.Column("scanned_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["version_id"], ["project_skill_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["scanned_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "scan_state IN ('pending', 'passed', 'blocked', 'error')",
            name="ck_project_skill_version_scans_state",
        ),
    )
    op.create_index(
        "ix_project_skill_version_scans_id", "project_skill_version_scans", ["id"]
    )
    op.create_index(
        "ix_project_skill_version_scans_version_id",
        "project_skill_version_scans",
        ["version_id"],
    )
    op.create_index(
        "ix_project_skill_version_scans_scanned_by_id",
        "project_skill_version_scans",
        ["scanned_by_id"],
    )
    op.create_index(
        "idx_project_skill_version_scans_version_created",
        "project_skill_version_scans",
        ["version_id", "created_at"],
    )

    op.create_foreign_key(
        "fk_project_skills_active_version",
        "project_skills",
        "project_skill_versions",
        ["active_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "project_skill_change_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("skill_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("proposed_version_id", postgresql.UUID(as_uuid=True)),
        sa.Column("prior_version_id", postgresql.UUID(as_uuid=True)),
        sa.Column("expected_active_version_id", postgresql.UUID(as_uuid=True)),
        sa.Column("requester_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="pending"
        ),
        sa.Column(
            "warning_acknowledged",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("audit_note", sa.Text()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["skill_id"], ["project_skills.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["proposed_version_id"], ["project_skill_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["prior_version_id"], ["project_skill_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["expected_active_version_id"],
            ["project_skill_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["requester_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "action IN ('activate', 'archive', 'restore', 'rollback')",
            name="ck_project_skill_change_requests_action",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'superseded')",
            name="ck_project_skill_change_requests_status",
        ),
    )
    op.create_index(
        "ix_project_skill_change_requests_id", "project_skill_change_requests", ["id"]
    )
    op.create_index(
        "ix_project_skill_change_requests_skill_id",
        "project_skill_change_requests",
        ["skill_id"],
    )
    op.create_index(
        "ix_project_skill_change_requests_requester_id",
        "project_skill_change_requests",
        ["requester_id"],
    )
    op.create_index(
        "ix_project_skill_change_requests_reviewer_id",
        "project_skill_change_requests",
        ["reviewer_id"],
    )
    op.create_index(
        "idx_project_skill_change_requests_skill_status",
        "project_skill_change_requests",
        ["skill_id", "status"],
    )

    op.create_table(
        "agent_runtime_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("project_id", postgresql.UUID(as_uuid=True)),
        sa.Column("user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True)),
        sa.Column("job_id", sa.String(length=36)),
        sa.Column("tool_registry_hash", sa.String(length=64), nullable=False),
        sa.Column("tool_registry_version", sa.String(length=64), nullable=False),
        sa.Column(
            "tool_metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "skill_catalog",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "loaded_skill_versions",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["collections.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["thread_id"], ["threads.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["job_id"], ["agent_runs.job_id"], ondelete="SET NULL"),
    )
    op.create_index("ix_agent_runtime_snapshots_id", "agent_runtime_snapshots", ["id"])
    op.create_index(
        "ix_agent_runtime_snapshots_project_id",
        "agent_runtime_snapshots",
        ["project_id"],
    )
    op.create_index(
        "ix_agent_runtime_snapshots_user_id", "agent_runtime_snapshots", ["user_id"]
    )
    op.create_index(
        "ix_agent_runtime_snapshots_thread_id", "agent_runtime_snapshots", ["thread_id"]
    )
    op.create_index(
        "ix_agent_runtime_snapshots_job_id", "agent_runtime_snapshots", ["job_id"]
    )
    op.create_index(
        "ix_agent_runtime_snapshots_expires_at",
        "agent_runtime_snapshots",
        ["expires_at"],
    )
    op.create_index(
        "idx_agent_runtime_snapshots_project_created",
        "agent_runtime_snapshots",
        ["project_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_project_skill_version_scans_version_created",
        table_name="project_skill_version_scans",
    )
    op.drop_index(
        "ix_project_skill_version_scans_scanned_by_id",
        table_name="project_skill_version_scans",
    )
    op.drop_index(
        "ix_project_skill_version_scans_version_id",
        table_name="project_skill_version_scans",
    )
    op.drop_index(
        "ix_project_skill_version_scans_id", table_name="project_skill_version_scans"
    )
    op.drop_table("project_skill_version_scans")
    op.drop_index(
        "idx_agent_runtime_snapshots_project_created",
        table_name="agent_runtime_snapshots",
    )
    op.drop_index(
        "ix_agent_runtime_snapshots_expires_at", table_name="agent_runtime_snapshots"
    )
    op.drop_index(
        "ix_agent_runtime_snapshots_job_id", table_name="agent_runtime_snapshots"
    )
    op.drop_index(
        "ix_agent_runtime_snapshots_thread_id", table_name="agent_runtime_snapshots"
    )
    op.drop_index(
        "ix_agent_runtime_snapshots_user_id", table_name="agent_runtime_snapshots"
    )
    op.drop_index(
        "ix_agent_runtime_snapshots_project_id", table_name="agent_runtime_snapshots"
    )
    op.drop_index("ix_agent_runtime_snapshots_id", table_name="agent_runtime_snapshots")
    op.drop_table("agent_runtime_snapshots")
    op.drop_index(
        "idx_project_skill_change_requests_skill_status",
        table_name="project_skill_change_requests",
    )
    op.drop_index(
        "ix_project_skill_change_requests_reviewer_id",
        table_name="project_skill_change_requests",
    )
    op.drop_index(
        "ix_project_skill_change_requests_requester_id",
        table_name="project_skill_change_requests",
    )
    op.drop_index(
        "ix_project_skill_change_requests_skill_id",
        table_name="project_skill_change_requests",
    )
    op.drop_index(
        "ix_project_skill_change_requests_id",
        table_name="project_skill_change_requests",
    )
    op.drop_table("project_skill_change_requests")
    op.drop_constraint(
        "fk_project_skills_active_version", "project_skills", type_="foreignkey"
    )
    op.drop_index(
        "ix_project_skill_versions_author_id", table_name="project_skill_versions"
    )
    op.drop_index(
        "ix_project_skill_versions_content_hash", table_name="project_skill_versions"
    )
    op.drop_index(
        "ix_project_skill_versions_skill_id", table_name="project_skill_versions"
    )
    op.drop_index("ix_project_skill_versions_id", table_name="project_skill_versions")
    op.drop_table("project_skill_versions")
    op.drop_index("idx_project_skills_project_archived", table_name="project_skills")
    op.drop_index("ix_project_skills_created_by_id", table_name="project_skills")
    op.drop_index("ix_project_skills_project_id", table_name="project_skills")
    op.drop_index("ix_project_skills_id", table_name="project_skills")
    op.drop_table("project_skills")
