"""Partial unique index backing org-scoped content-hash dedup.

Revision ID: uq_documents_org_checksum
Revises: z8a9b0c1d2e3
Create Date: 2026-07-06 00:00:00

The upload path dedupes via check-then-insert on
(organization_id, checksum_sha256) with only a plain index behind it — two
concurrent uploads of identical content can both pass the check and both
insert. This adds the partial unique index the 409 logic assumes, after
soft-deleting any pre-existing duplicate rows (keep the oldest per org+hash;
soft-delete, never hard DELETE, since documents own storage objects and
cascades).
"""

import sqlalchemy as sa
from alembic import context, op

revision = "uq_documents_org_checksum"
down_revision = "z8a9b0c1d2e3"
branch_labels = None
depends_on = None

INDEX_NAME = "uq_documents_org_checksum_live"


def upgrade() -> None:
    # Soft-delete newer duplicates so the unique index can build. Keep the
    # oldest live row per (org, hash) — that's the one dedup would have 409'd
    # against.
    # R6-M9 guard: skip cleanly when documents is absent. RETURN inside a DO
    # block only exits that block, so the guard has to live in Python. Offline
    # (--sql) proceeds unconditionally: the baseline's DDL earlier in the same
    # script creates documents.
    if not context.is_offline_mode():
        if not sa.inspect(op.get_bind()).has_table("documents"):
            return
    op.execute("""
        UPDATE documents d
        SET is_deleted = true, deleted_at = NOW()
        FROM (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY organization_id, checksum_sha256
                ORDER BY created_at ASC, id ASC
            ) AS rn
            FROM documents
            WHERE is_deleted = false AND checksum_sha256 IS NOT NULL
        ) ranked
        WHERE d.id = ranked.id AND ranked.rn > 1;
        """)
    # CONCURRENTLY cannot run inside the migration's transaction.
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS "
            f"{INDEX_NAME} "
            "ON documents (organization_id, checksum_sha256) "
            "WHERE is_deleted = false AND checksum_sha256 IS NOT NULL"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}")
