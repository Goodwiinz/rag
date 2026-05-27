"""Add DigitalOcean Knowledge Base columns to organizations and documents

Revision ID: q5w6x7y8z9a0
Revises: p3q4r5s6t7u8, p3s4t5u6v7w8
Create Date: 2026-05-08 13:00:00.000000

Adds nullable columns for DO KB integration. Phase 1 of Qdrant -> DO KB migration.
Also merges the two existing heads (p3q4r5s6t7u8 dashboard indexes and
p3s4t5u6v7w8 prior heads merge) into a single linear history.

- organizations.do_kb_uuid: KB UUID (lazy-provisioned on first ingest)
- organizations.do_kb_provisioned_at: provisioning timestamp
- documents.do_kb_data_source_uuid: KB data source UUID per doc
- documents.do_kb_indexed_at: timestamp when added to KB

All columns nullable so the change is backward compatible. Indexed for lookups
during dual-write and shadow-read phases.
"""

from alembic import op
import sqlalchemy as sa


revision = "q5w6x7y8z9a0"
down_revision = ("p3q4r5s6t7u8", "p3s4t5u6v7w8")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("do_kb_uuid", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("do_kb_provisioned_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_organizations_do_kb_uuid",
        "organizations",
        ["do_kb_uuid"],
        unique=False,
    )

    op.add_column(
        "documents",
        sa.Column("do_kb_data_source_uuid", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("do_kb_indexed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_documents_do_kb_data_source_uuid",
        "documents",
        ["do_kb_data_source_uuid"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_documents_do_kb_data_source_uuid", table_name="documents")
    op.drop_column("documents", "do_kb_indexed_at")
    op.drop_column("documents", "do_kb_data_source_uuid")

    op.drop_index("ix_organizations_do_kb_uuid", table_name="organizations")
    op.drop_column("organizations", "do_kb_provisioned_at")
    op.drop_column("organizations", "do_kb_uuid")
