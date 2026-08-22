"""Create search_feedback table — real persistence for search-quality feedback.

Revision ID: r6_search_feedback
Revises: add_chat_progress_steps
Create Date: 2026-08-22

R6-L5 / R2-M16. Guarded create: the model is also in Base.metadata, so
fresh databases get the table from r6h3_model_baseline and this revision
must tolerate it existing (the env.py guard layer backstops this too).
"""

from alembic import op
import sqlalchemy as sa

revision = "r6_search_feedback"
down_revision = "add_chat_progress_steps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS search_feedback (
            id SERIAL PRIMARY KEY,
            organization_id VARCHAR(36) NOT NULL,
            user_id VARCHAR(64) NOT NULL,
            query_id VARCHAR(128) NOT NULL,
            query_text TEXT,
            rating INTEGER NOT NULL,
            feedback_text TEXT,
            document_id VARCHAR(36),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_search_feedback_organization_id "
        "ON search_feedback (organization_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_search_feedback_user_id "
        "ON search_feedback (user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_search_feedback_org_created "
        "ON search_feedback (organization_id, created_at)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS search_feedback")
