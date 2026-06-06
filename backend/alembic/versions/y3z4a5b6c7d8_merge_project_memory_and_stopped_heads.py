"""Merge project_memories and chat_messages.stopped migration heads

Revision ID: y3z4a5b6c7d8
Revises: w1x2y3z4a5b6, x2y3z4a5b6c7
Create Date: 2026-06-06 01:00:00.000000

Two feature branches each added a migration off the same parent
(`v0a1b2c3d4e5`):
- `w1x2y3z4a5b6` — create project_memories (PR #614)
- `x2y3z4a5b6c7` — add chat_messages.stopped (PR #615)

That leaves Alembic with two heads. This is a no-op merge that rejoins them so
`alembic upgrade head` resolves to a single revision. No schema changes.

NOTE: only mergeable once BOTH parent revisions are present on the target
branch — i.e. after #614 and #615 have merged. Until then Alembic cannot
resolve the down_revision tuple.
"""

# revision identifiers, used by Alembic.
revision = 'y3z4a5b6c7d8'
down_revision = ('w1x2y3z4a5b6', 'x2y3z4a5b6c7')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
