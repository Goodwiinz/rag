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
    # R6-M9 guard: stance_classifications is provisioned by the model baseline
    # (R6-F8 registered it in Base.metadata) or, on legacy databases, by the
    # out-of-band add_evidence_meter.py script. Single DO block skips
    # everything on any database where neither has run yet.
    op.execute("""
        DO $$
        BEGIN
            IF to_regclass('stance_classifications') IS NULL THEN
                RETURN;
            END IF;
            ALTER TABLE stance_classifications ADD COLUMN IF NOT EXISTS claim_text TEXT;
            ALTER TABLE stance_classifications ADD COLUMN IF NOT EXISTS source_content_hash VARCHAR(64);
            ALTER TABLE stance_classifications ADD COLUMN IF NOT EXISTS inference_model_version VARCHAR(100);
        END
        $$;
    """)


def downgrade() -> None:
    # Same guard as upgrade(): DROP COLUMN IF EXISTS tolerates a missing
    # column, not a missing table, so an unguarded rollback would raise
    # UndefinedTable on exactly the databases upgrade() skipped.
    op.execute("""
        DO $$
        BEGIN
            IF to_regclass('stance_classifications') IS NULL THEN
                RETURN;
            END IF;
            ALTER TABLE stance_classifications DROP COLUMN IF EXISTS inference_model_version;
            ALTER TABLE stance_classifications DROP COLUMN IF EXISTS source_content_hash;
            ALTER TABLE stance_classifications DROP COLUMN IF EXISTS claim_text;
        END
        $$;
    """)
