"""Add organization_id to stance_classifications (tenant isolation)

Revision ID: add_org_id_stance_classifications
Revises: e1f2a3b4c5d6
Create Date: 2026-06-29 23:00:00

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
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

# revision identifiers, used by Alembic.
revision = "add_org_id_stance_classifications"
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
    # 1. Add the tenant column.
    op.add_column(
        TABLE,
        sa.Column(
            "organization_id",
            PG_UUID(as_uuid=True),
            nullable=True,
        ),
    )

    # 2. Drop the legacy 3-tuple unique constraint if it exists (left behind by the
    #    standalone migration). IF EXISTS makes this safe whether or not it ran.
    op.execute(
        f"ALTER TABLE {TABLE} DROP CONSTRAINT IF EXISTS {LEGACY_3TUPLE_CONSTRAINT}"
    )

    # 3. Create the new 4-tuple unique index. organization_id is part of the key so two
    #    orgs analyzing the same claim/source/model are independent rows (never collide
    #    or overwrite each other). This is the index the upsert (ON CONFLICT) targets.
    op.execute(
        f"CREATE UNIQUE INDEX IF NOT EXISTS {NEW_4TUPLE_INDEX} "
        f"ON {TABLE} (claim_hash, source_id, model_version, organization_id)"
    )

    # 4. Plain index on organization_id for the scoped /breakdown read path.
    op.execute(f"CREATE INDEX IF NOT EXISTS {ORG_INDEX} ON {TABLE} (organization_id)")


def downgrade():
    op.execute(f"DROP INDEX IF EXISTS {ORG_INDEX}")
    op.execute(f"DROP INDEX IF EXISTS {NEW_4TUPLE_INDEX}")
    op.drop_column(TABLE, "organization_id")
