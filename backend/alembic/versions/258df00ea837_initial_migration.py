"""Initial migration

Revision ID: 258df00ea837
Revises: 
Create Date: 2025-10-09 04:24:10.973137

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '258df00ea837'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fixed: This migration was auto-generated incorrectly
    # The entity_relationships table was created in a later migration
    # Making this a no-op to allow migration chain to work
    pass


def downgrade() -> None:
    # Fixed: This migration was auto-generated incorrectly
    # Making this a no-op to allow migration chain to work
    pass