"""Merge divergent heads into a single linear history

Revision ID: p3s4t5u6v7w8
Revises: n9p2q3r4s5t6, o2r3s4t5u6v7
Create Date: 2026-04-20 20:00:00.000000

Resolves the fork where both n9p2q3r4s5t6 (performance indexes)
and o2r3s4t5u6v7 (drop citation uniqueness) descend from m8o1p2q3r4s5.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "p3s4t5u6v7w8"
down_revision = ("n9p2q3r4s5t6", "o2r3s4t5u6v7", "b8f3a1c2d4e5", "f8a9b0c1d2e3")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
