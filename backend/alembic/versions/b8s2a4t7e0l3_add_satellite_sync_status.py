"""add per-satellite sync status columns to documents

Revision ID: b8s2a4t7e0l3
Revises: a7r2u9n4s1t6
Create Date: 2026-07-12

Audit D1 (P2.1): satellite indexing failures (Neo4j knowledge graph, DO KB)
are warn-and-continue by design, and the document still reaches COMPLETED —
but nothing recorded the satellite outcome, so a Neo4j-failed document was
indistinguishable from a healthy one. Adds:

- documents.neo4j_index_status  (pending | completed | failed, NULL = never
  attempted) + documents.neo4j_indexed_at
- documents.do_kb_sync_status   (pending | completed | failed, NULL = never
  attempted) — the outcome of the data-source registration attempt, distinct
  from do_kb_index_status (KB-side indexing lifecycle after registration).

The scheduled reconciler (src.tasks.reconcile_tasks) selects rows where either
column is 'failed' and re-drives them.

Backfill: documents already carrying a DO KB data-source uuid demonstrably
completed their sync — mark them 'completed' (same predicate the earlier
a9b0c1d2e3f4 do_kb_index_status backfill used). We deliberately do NOT key the
backfill on is_indexed: since #877 that flag records full-text tsvector
searchability, not DO KB state, and DO_KB_ENABLED defaults off — is_indexed
alone would mark never-synced documents 'completed'. Neo4j columns stay NULL
(unknown — honest; the fan-out records truth from now on).
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "b8s2a4t7e0l3"
down_revision = "a7r2u9n4s1t6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent (house to_regclass / IF NOT EXISTS pattern, mirrors
    # a9b0c1d2e3f4_add_do_kb_index_status.py): safe whether run by the deploy
    # initContainer, a manual `alembic upgrade`, or after create_all already
    # made the columns from the model.
    op.execute("""
        DO $$
        BEGIN
            IF to_regclass('public.documents') IS NOT NULL THEN
                ALTER TABLE public.documents
                    ADD COLUMN IF NOT EXISTS neo4j_index_status varchar(20);
                ALTER TABLE public.documents
                    ADD COLUMN IF NOT EXISTS neo4j_indexed_at timestamptz;
                ALTER TABLE public.documents
                    ADD COLUMN IF NOT EXISTS do_kb_sync_status varchar(20);
                CREATE INDEX IF NOT EXISTS ix_documents_neo4j_index_status
                    ON public.documents (neo4j_index_status);
                CREATE INDEX IF NOT EXISTS ix_documents_do_kb_sync_status
                    ON public.documents (do_kb_sync_status);
                -- Backfill only rows already carrying a DO KB data-source UUID
                -- (proof the sync completed). Guarded so a physically-missing
                -- do_kb_data_source_uuid column (stamped-not-run drift) cannot
                -- abort the migration.
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name  = 'documents'
                      AND column_name = 'do_kb_data_source_uuid'
                ) THEN
                    UPDATE public.documents
                        SET do_kb_sync_status = 'completed'
                        WHERE do_kb_data_source_uuid IS NOT NULL
                          AND do_kb_sync_status IS NULL;
                END IF;
            END IF;
        END $$;
        """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_documents_neo4j_index_status")
    op.execute("DROP INDEX IF EXISTS ix_documents_do_kb_sync_status")
    op.execute(
        "ALTER TABLE IF EXISTS public.documents "
        "DROP COLUMN IF EXISTS neo4j_index_status"
    )
    op.execute(
        "ALTER TABLE IF EXISTS public.documents "
        "DROP COLUMN IF EXISTS neo4j_indexed_at"
    )
    op.execute(
        "ALTER TABLE IF EXISTS public.documents "
        "DROP COLUMN IF EXISTS do_kb_sync_status"
    )
