"""Enforce non-negative storage accounting + document the quota invariant.

Revision ID: r6_org_quota_guard
Revises: r6_search_feedback
Create Date: 2026-08-22

R2-M7 companion: quota claims are now conditional UPDATEs; this CHECK keeps
a bug from ever driving storage_used_bytes negative again.
"""

from alembic import op

revision = "r6_org_quota_guard"
down_revision = "r6_search_feedback"
branch_labels = None
depends_on = None

CONSTRAINT = "ck_organizations_storage_nonnegative"


def upgrade() -> None:
    op.execute(f"""
        DO $$
        BEGIN
            IF to_regclass('organizations') IS NOT NULL
               AND NOT EXISTS (
                   SELECT 1 FROM pg_constraint WHERE conname = '{CONSTRAINT}'
               )
            THEN
                ALTER TABLE organizations
                    ADD CONSTRAINT {CONSTRAINT} CHECK (storage_used_bytes >= 0);
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    op.execute(f"ALTER TABLE organizations DROP CONSTRAINT IF EXISTS {CONSTRAINT}")
