"""Add missing uq_project_thread unique constraint (repairs ON CONFLICT)

Revision ID: uq_project_thread_constraint
Revises: add_org_id_stance_class
Create Date: 2026-06-30 20:00:00

Background: ``project_threads`` was created out-of-band by SQLAlchemy
``create_all`` (its indexes are auto-named ``ix_project_threads_*`` rather than
the ``idx_project_threads_*`` of migration i4k8l9m0n1o2), so the
``uq_project_thread`` UNIQUE(project_id, thread_id) declared on the model and in
i4k8l9m0n1o2 never physically landed in the DB. Alembic still counts
i4k8l9m0n1o2 as applied (it is an ancestor of the deployed head), so it will
never re-run -- the constraint can only be (re)added by a fresh migration.

Symptom: ``attach_thread_to_project`` upserts with
``ON CONFLICT (project_id, thread_id) DO NOTHING``. Without the matching unique
constraint Postgres raises ``InvalidColumnReferenceError: there is no unique or
exclusion constraint matching the ON CONFLICT specification`` -> every
POST /api/v1/projects/{id}/chat/link returns 500 "Failed to link thread".

Idempotent: only adds the constraint when absent, and de-dupes any
``(project_id, thread_id)`` collisions first so the ADD CONSTRAINT cannot fail.
Safe on DBs where i4k8l9m0n1o2 did create the constraint (it becomes a no-op).
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "uq_project_thread_constraint"
down_revision = "add_org_id_stance_class"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'uq_project_thread'
              AND conrelid = 'public.project_threads'::regclass
          ) THEN
            -- Drop any (project_id, thread_id) duplicates before the unique
            -- constraint is added, keeping a single arbitrary row per pair.
            DELETE FROM public.project_threads a
            USING public.project_threads b
            WHERE a.project_id = b.project_id
              AND a.thread_id = b.thread_id
              AND a.ctid < b.ctid;

            ALTER TABLE public.project_threads
              ADD CONSTRAINT uq_project_thread UNIQUE (project_id, thread_id);
          END IF;
        END $$;
        """
    )


def downgrade():
    op.execute(
        "ALTER TABLE public.project_threads "
        "DROP CONSTRAINT IF EXISTS uq_project_thread"
    )
