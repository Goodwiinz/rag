"""Add organization_id to stance_classifications (tenant isolation)

Revision ID: add_org_id_stance_class
Revises: e1f2a3b4c5d6
Create Date: 2026-06-29 23:00:00

NOTE: the revision id MUST stay <= 32 chars. ``alembic_version.version_num`` is
``VARCHAR(32)``, so a longer id raises StringDataRightTruncation on the version
stamp and crash-loops the migration init container (the original 33-char id
``add_org_id_stance_classifications`` did exactly this, blocking every deploy
past e1f2a3b4c5d6).

Closes a cross-tenant information disclosure: /api/v1/evidence/breakdown was scoped
only by claim_hash + model_version (a deterministic SHA-256 of public claim text),
so any authenticated user could read another org's justification_excerpt by computing
the hash. This adds an organization_id column and makes it part of the uniqueness key
so two orgs analyzing the same claim are independent rows that never collide.

Idempotent: safe whether or not the legacy standalone add_evidence_meter.py migration
(which created a 3-tuple UNIQUE(claim_hash, source_id, model_version)) was ever run.
The old 3-tuple constraint is dropped if present so the new 4-tuple one can be created.

Known data-visibility change: existing rows have NULL organization_id and are
unreadable under the new strict `organization_id == <user.org>` filter. There is no
external consumer of this table and no audit trail mapping old rows to an owner org, so
they are fail-closed and simply regenerate on the next /meter or /classify analysis
(which now stamps the caller's org). The /breakdown read also rejects users with no org
explicitly (NULL-org users never see any classifications). See memory/nous-loop-ticks.md.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "add_org_id_stance_class"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None

TABLE = "stance_classifications"
# Name of the legacy 3-tuple constraint created by the (non-Alembic, standalone)
# add_evidence_meter.py script, IF it was ever run manually. Postgres names a
# table-inline UNIQUE(a,b,c) as "<table>_<a>_<b>_<c>_key".
LEGACY_3TUPLE_CONSTRAINT = (
    "stance_classifications_claim_hash_source_id_model_version_key"
)
NEW_4TUPLE_INDEX = "ux_stance_classifications_org_claim_src_model"
ORG_INDEX = "ix_stance_classifications_organization_id"


def upgrade():
    # R6-M9 guard: this table originates from the out-of-band standalone
    # add_evidence_meter.py script and is NOT in Base.metadata, so even the
    # model baseline cannot provision it. One DO block skips every statement
    # when the table is absent — the feature simply does not exist on
    # databases that never ran the script.
    op.execute("""
        DO $$
        BEGIN
            IF to_regclass('stance_classifications') IS NULL THEN
                RETURN;
            END IF;
            -- 1. tenant column (idempotent: create_all-era DBs already have it)
            ALTER TABLE stance_classifications ADD COLUMN IF NOT EXISTS organization_id UUID;

            -- 2. legacy 3-tuple constraint from the standalone script, if any
            ALTER TABLE stance_classifications
                DROP CONSTRAINT IF EXISTS stance_classifications_claim_hash_source_id_model_version_key;

            -- 3. 4-tuple unique index the upsert targets
            CREATE UNIQUE INDEX IF NOT EXISTS ux_stance_classifications_org_claim_src_model
                ON stance_classifications (claim_hash, source_id, model_version, organization_id);

            -- 4. plain index for the scoped /breakdown read path
            CREATE INDEX IF NOT EXISTS ix_stance_classifications_organization_id
                ON stance_classifications (organization_id);
        END
        $$;
    """)


def downgrade():
    op.execute(f"DROP INDEX IF EXISTS {ORG_INDEX}")
    op.execute(f"DROP INDEX IF EXISTS {NEW_4TUPLE_INDEX}")
    op.execute(f"ALTER TABLE {TABLE} DROP COLUMN IF EXISTS organization_id")
