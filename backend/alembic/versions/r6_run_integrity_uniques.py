"""Unique (run_id, step_index) on research_steps + GeneratedDraft uniques.

Revision ID: r6_run_integrity_uniques
Revises: r6_org_quota_guard
Create Date: 2026-08-22

R5-M18: concurrent SSE streams double-inserted steps (duplicate spend).
R5-M20: GeneratedDraft claimed a uniqueness contract in comments that no
constraint enforced — version/is_current races picked arbitrary currents.
"""

from alembic import op

revision = "r6_run_integrity_uniques"
down_revision = "r6_org_quota_guard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF to_regclass('research_steps') IS NOT NULL THEN
                DELETE FROM research_steps a
                USING research_steps b
                WHERE a.ctid < b.ctid
                  AND a.run_id = b.run_id
                  AND a.step_index = b.step_index;

                CREATE UNIQUE INDEX IF NOT EXISTS uq_research_steps_run_idx
                    ON research_steps (run_id, step_index);
            END IF;

            IF to_regclass('generated_drafts') IS NOT NULL THEN
                DELETE FROM generated_drafts a
                USING generated_drafts b
                WHERE a.ctid < b.ctid
                  AND a.project_id = b.project_id
                  AND a.version = b.version;

                CREATE UNIQUE INDEX IF NOT EXISTS uq_generated_drafts_project_version
                    ON generated_drafts (project_id, version);

                -- At most one current draft per project (partial)
                CREATE UNIQUE INDEX IF NOT EXISTS uq_generated_drafts_current
                    ON generated_drafts (project_id) WHERE is_current;
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_generated_drafts_current")
    op.execute("DROP INDEX IF EXISTS uq_generated_drafts_project_version")
    op.execute("DROP INDEX IF EXISTS uq_research_steps_run_idx")
