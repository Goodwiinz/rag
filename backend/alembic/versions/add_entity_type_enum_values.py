"""Add missing EntityType enum values.

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

BASE_VALUES = [
    "person",
    "organization",
    "location",
    "product",
    "concept",
    "date",
    "number",
    "email",
    "phone",
    "url",
    "custom",
]
NEW_VALUES = ["event", "financial", "job_title", "topic", "technology", "research", "document"]
ALL_VALUES = BASE_VALUES + NEW_VALUES


def upgrade() -> None:
    quoted_values = ", ".join(f"'{value}'" for value in ALL_VALUES)

    # Bootstrap the enum on fresh databases, while preserving existing types.
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_type
                WHERE typname = 'entitytype'
            ) THEN
                CREATE TYPE entitytype AS ENUM ({quoted_values});
            END IF;
        END
        $$;
        """
    )

    for value in NEW_VALUES:
        op.execute(
            f"ALTER TYPE entitytype ADD VALUE IF NOT EXISTS '{value}'"
        )


def downgrade() -> None:
    # PostgreSQL does not support removing enum values.
    # A full enum recreation would be needed, which is destructive.
    pass
