"""Model-schema baseline: make the alembic chain runnable from an empty DB.

Revision ID: r6h3_model_baseline
Revises: 258df00ea837
Create Date: 2026-08-22

R6-H3. The historical initial migration (258df00ea837) is a literal ``pass``,
so ~49 model tables (users, organizations, documents, entities, all
evaluation_*/research_*/ab_* families, ...) were only ever created by
``Base.metadata.create_all`` at app boot. The very next real revision in this
chain (f931599b6b5b → a1b2c3d4e5f6) already ALTERs and FKs against users /
organizations / documents — on any migrate-only database (fresh Supabase DR,
CI scratch) that raised UndefinedTable and made ``alembic upgrade head``
un-runnable end-to-end.

This revision sits between them and materializes the full current model
schema with ``Base.metadata.create_all``, which is idempotent per table:
- migrate-only DB: every missing table is created here, before anything FKs.
- create_all-provisioned DB (every live environment): existing tables are
  skipped untouched, so re-stamping is never needed.

Models — not hand-written DDL — stay the single source of truth for these
tables; ``scripts/audit_schema_drift.py`` remains the drift detector for
drift between models and live databases. Later revisions continue to own
additive ALTERs and must stay guarded (IF NOT EXISTS / to_regclass) because
this baseline means both provisioning worlds meet the chain with complete
tables.

downgrade() is a deliberate no-op: dropping the entire schema from a
baseline node would destroy unrelated data on any downgrade walk.
"""

from alembic import op

revision = "r6h3_model_baseline"
down_revision = "258df00ea837"
branch_labels = None
depends_on = None


def upgrade() -> None:
    import logging

    from sqlalchemy.engine.reflection import Inspector

    # Import the full model package so Base.metadata is fully populated
    # (same registration contract as alembic/env.py).
    import src.models  # noqa: F401
    from src.models.base import Base

    bind = op.get_bind()
    inspector = Inspector(bind)
    existing = set(inspector.get_table_names())

    target = set(Base.metadata.tables.keys())
    missing = sorted(target - existing)

    if missing:
        # create_all only emits DDL for `missing` when tables=... is given;
        # passing the whole metadata is equally safe (it skips existing) but
        # listing them keeps the log honest about what this node created.
        logging.getLogger("alembic").info(
            "model baseline creating %d missing tables: %s",
            len(missing),
            ", ".join(missing),
        )
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    # Intentional no-op — see module docstring.
    pass
