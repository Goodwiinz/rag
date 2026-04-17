"""Drop global uniqueness for citation DOI and arXiv identifiers.

Revision ID: o2r3s4t5u6v7
Revises: m8o1p2q3r4s5
Create Date: 2026-04-15 17:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "o2r3s4t5u6v7"
down_revision = "m8o1p2q3r4s5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_citations_doi", table_name="citations")
    op.drop_index("ix_citations_arxiv_id", table_name="citations")

    op.create_index(
        "ix_citations_doi",
        "citations",
        ["doi"],
        unique=False,
        postgresql_where=sa.text("doi IS NOT NULL"),
    )
    op.create_index(
        "ix_citations_arxiv_id",
        "citations",
        ["arxiv_id"],
        unique=False,
        postgresql_where=sa.text("arxiv_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_citations_doi", table_name="citations")
    op.drop_index("ix_citations_arxiv_id", table_name="citations")

    op.create_index(
        "ix_citations_doi",
        "citations",
        ["doi"],
        unique=True,
        postgresql_where=sa.text("doi IS NOT NULL"),
    )
    op.create_index(
        "ix_citations_arxiv_id",
        "citations",
        ["arxiv_id"],
        unique=True,
        postgresql_where=sa.text("arxiv_id IS NOT NULL"),
    )
