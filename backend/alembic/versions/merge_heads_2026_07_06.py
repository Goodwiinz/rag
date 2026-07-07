"""Merge the two divergent migration heads.

Revision ID: merge_heads_2026_07_06
Revises: idx_documents_org_created, quality_metric_type_to_string
Create Date: 2026-07-06 00:00:02

The documents chain (…→ uq_documents_org_checksum → idx_documents_org_created)
and the search-quality chain (…→ quality_metric_type_to_string) diverged,
leaving two heads — `alembic upgrade head` is ambiguous and the deploy
initContainer has to run `upgrade heads`. This no-op merge gives the tree a
single head again.
"""

revision = "merge_heads_2026_07_06"
down_revision = ("idx_documents_org_created", "quality_metric_type_to_string")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
