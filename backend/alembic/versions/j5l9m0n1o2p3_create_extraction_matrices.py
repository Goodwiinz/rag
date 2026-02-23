"""Create extraction_matrices and extraction_cells tables (Feature 1: Extraction Matrix)

Revision ID: j5l9m0n1o2p3
Revises: add_org_id_api_keys
Create Date: 2026-02-21 12:00:00.000000

This migration creates tables for the Literature Review Extraction Matrix,
enabling structured data extraction from documents into a comparison grid.

Changes:
- Create extraction_matrices table with JSONB column definitions
- Create extraction_cells table for individual extracted values
- Add indexes on project_id, matrix_id, document_id for fast lookups
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "j5l9m0n1o2p3"
down_revision = "add_org_id_api_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create extraction_matrices table
    op.create_table(
        "extraction_matrices",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("collections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("columns", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
    )

    # Create indexes for extraction_matrices
    op.create_index(
        "ix_extraction_matrices_project_id",
        "extraction_matrices",
        ["project_id"],
    )

    # Create extraction_cells table
    op.create_table(
        "extraction_cells",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "matrix_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("extraction_matrices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("column_name", sa.String(100), nullable=False),
        sa.Column("value", sa.Text, nullable=True),
        sa.Column("citation_snippet", sa.Text, nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
    )

    # Create indexes for extraction_cells
    op.create_index(
        "ix_extraction_cells_matrix_id",
        "extraction_cells",
        ["matrix_id"],
    )
    op.create_index(
        "ix_extraction_cells_document_id",
        "extraction_cells",
        ["document_id"],
    )
    op.create_unique_constraint(
        "uq_cell_matrix_doc_col",
        "extraction_cells",
        ["matrix_id", "document_id", "column_name"],
    )
    op.create_check_constraint(
        "ck_cell_confidence_range",
        "extraction_cells",
        "confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)",
    )


def downgrade() -> None:
    # Drop extraction_cells constraints, indexes and table
    op.drop_constraint("ck_cell_confidence_range", "extraction_cells", type_="check")
    op.drop_constraint("uq_cell_matrix_doc_col", "extraction_cells", type_="unique")
    op.drop_index("ix_extraction_cells_document_id", table_name="extraction_cells")
    op.drop_index("ix_extraction_cells_matrix_id", table_name="extraction_cells")
    op.drop_table("extraction_cells")

    # Drop extraction_matrices indexes and table
    op.drop_index(
        "ix_extraction_matrices_project_id", table_name="extraction_matrices"
    )
    op.drop_table("extraction_matrices")
