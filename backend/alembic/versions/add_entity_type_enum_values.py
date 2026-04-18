"""Add missing EntityType enum values

Revision ID: f8a9b0c1d2e3
Revises: None (standalone migration)
Create Date: 2026-03-30
"""

from alembic import op


# revision identifiers
revision = "f8a9b0c1d2e3"
down_revision = None
branch_labels = None
depends_on = None

NEW_VALUES = ["event", "financial", "job_title", "topic", "technology", "research", "document"]


def upgrade() -> None:
    for value in NEW_VALUES:
        op.execute(
            f"ALTER TYPE entitytype ADD VALUE IF NOT EXISTS '{value}'"
        )


def downgrade() -> None:
    # PostgreSQL does not support removing enum values.
    # A full enum recreation would be needed, which is destructive.
    pass
