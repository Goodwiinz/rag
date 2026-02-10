"""Add organization_id to api_keys

Revision ID: add_org_id_api_keys
Revises: api_keys_security_fix
Create Date: 2024-05-23 10:00:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_org_id_api_keys'
down_revision = 'api_keys_security_fix'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('api_keys', sa.Column('organization_id', sa.String(), nullable=True))
    op.create_index('idx_api_keys_organization', 'api_keys', ['organization_id'])

def downgrade():
    op.drop_index('idx_api_keys_organization', 'api_keys')
    op.drop_column('api_keys', 'organization_id')
