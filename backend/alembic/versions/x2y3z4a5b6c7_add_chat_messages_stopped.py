"""Add stopped flag to chat_messages

Revision ID: x2y3z4a5b6c7
Revises: v0a1b2c3d4e5
Create Date: 2026-06-06 00:30:00.000000

Marks an assistant message the user stopped mid-stream: the stored content is
the partial answer generated before the stop. Lets a reloaded thread render the
"Stopped" marker (the flag was previously session-only).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'x2y3z4a5b6c7'
down_revision = 'v0a1b2c3d4e5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'chat_messages',
        sa.Column(
            'stopped',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column('chat_messages', 'stopped')
