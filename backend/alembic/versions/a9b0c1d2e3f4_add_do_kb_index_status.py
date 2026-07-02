"""add do_kb_index_status

Revision ID: a9b0c1d2e3f4
Revises: add_org_id_stance_classifications
Create Date: 2026-07-02

Adds documents.do_kb_index_status to track per-document DO KB indexing health
(indexed | skipped | failed | timeout). Backfills existing indexed documents.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a9b0c1d2e3f4"
down_revision = "add_org_id_stance_classifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("do_kb_index_status", sa.String(length=20), nullable=True),
    )
    op.create_index(
        "ix_documents_do_kb_index_status",
        "documents",
        ["do_kb_index_status"],
        unique=False,
    )
    # Backfill: anything already carrying a data source UUID is indexed.
    op.execute(
        "UPDATE documents SET do_kb_index_status = 'indexed' "
        "WHERE do_kb_data_source_uuid IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_index("ix_documents_do_kb_index_status", table_name="documents")
    op.drop_column("documents", "do_kb_index_status")
