"""add do_kb_index_status

Revision ID: a9b0c1d2e3f4
Revises: repair_invalid_chat_msg_idx
Create Date: 2026-07-02

Adds documents.do_kb_index_status to track per-document DO KB indexing health
(indexed | skipped | failed | timeout). Backfills existing indexed documents.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "a9b0c1d2e3f4"
down_revision = "repair_invalid_chat_msg_idx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent (house to_regclass / IF NOT EXISTS pattern, mirrors
    # b7d4e9a1c3f2_add_organization_id_to_analytics_kpis.py): safe whether run by
    # the deploy initContainer, a manual `alembic upgrade`, or after a raw-SQL apply.
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.documents') IS NOT NULL THEN
                ALTER TABLE public.documents
                    ADD COLUMN IF NOT EXISTS do_kb_index_status varchar(20);
                CREATE INDEX IF NOT EXISTS ix_documents_do_kb_index_status
                    ON public.documents (do_kb_index_status);
                -- Backfill only rows already carrying a DO KB data source UUID.
                -- Guarded so a physically-missing do_kb_data_source_uuid column
                -- (stamped-not-run drift) cannot abort the migration.
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name  = 'documents'
                      AND column_name = 'do_kb_data_source_uuid'
                ) THEN
                    UPDATE public.documents
                        SET do_kb_index_status = 'indexed'
                        WHERE do_kb_data_source_uuid IS NOT NULL
                          AND do_kb_index_status IS NULL;
                END IF;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_documents_do_kb_index_status")
    op.execute(
        "ALTER TABLE IF EXISTS public.documents "
        "DROP COLUMN IF EXISTS do_kb_index_status"
    )
