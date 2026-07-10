"""Composite index for the default document list query.

Revision ID: idx_documents_org_created
Revises: uq_documents_org_checksum
Create Date: 2026-07-06 00:00:01

The default GET /documents runs
``WHERE organization_id = :org AND is_deleted = false ORDER BY created_at DESC``
but no composite index paired organization_id with created_at — Postgres had to
filter via an org-prefixed index and sort separately. This lets the most common
list call walk an index in order.
"""

from alembic import op

revision = "idx_documents_org_created"
down_revision = "uq_documents_org_checksum"
branch_labels = None
depends_on = None

INDEX_NAME = "idx_document_org_created"


def upgrade() -> None:
    # CONCURRENTLY cannot run inside the migration's transaction.
    with op.get_context().autocommit_block():
        op.execute(
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {INDEX_NAME} "
            "ON documents (organization_id, created_at)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}")
