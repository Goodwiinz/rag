"""Drop global uniqueness for citation DOI and arXiv identifiers.

Revision ID: o2r3s4t5u6v7
Revises: m8o1p2q3r4s5
Create Date: 2026-04-15 17:45:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "o2r3s4t5u6v7"
down_revision = "m8o1p2q3r4s5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # R6-M9 guard: the model baseline already provisions citations with
    # these non-unique partial indexes, so make both halves idempotent.
    op.execute("DROP INDEX IF EXISTS ix_citations_doi")
    op.execute("DROP INDEX IF EXISTS ix_citations_arxiv_id")

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_citations_doi "
        "ON citations (doi) WHERE doi IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_citations_arxiv_id "
        "ON citations (arxiv_id) WHERE arxiv_id IS NOT NULL"
    )


def downgrade() -> None:
    # R6-M10: deliberately do NOT recreate global-unique indexes here.
    # Restoring cross-tenant uniqueness on rollback re-breaks every org
    # citing the same public paper, and the CREATE fails outright once
    # duplicate DOIs exist. The non-unique indexes above are left in place;
    # uniqueness is now enforced per-org by application logic instead.
    pass
