"""add evidence claim and source provenance

Revision ID: evidence_prov_20260816
Revises: i9j0k1l2m3n4
Create Date: 2026-08-16
"""

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

revision = "evidence_prov_20260816"
down_revision = "i9j0k1l2m3n4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stance_classifications", sa.Column("claim_text", sa.Text(), nullable=True)
    )
    op.add_column(
        "stance_classifications",
        sa.Column("source_content_hash", sa.String(64), nullable=True),
    )
    op.add_column(
        "stance_classifications",
        sa.Column("inference_model_version", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("stance_classifications", "inference_model_version")
    op.drop_column("stance_classifications", "source_content_hash")
    op.drop_column("stance_classifications", "claim_text")
