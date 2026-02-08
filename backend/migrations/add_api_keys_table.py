"""
Add API keys table for secure public endpoint access
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers
revision = 'api_keys_security_fix'
down_revision = 'head'  # Replace with actual latest revision
branch_labels = None
depends_on = None

def upgrade():
    """Create API keys table"""
    op.create_table(
        'api_keys',
        sa.Column('id', sa.String(), primary_key=True, default=lambda: str(uuid.uuid4())),
        sa.Column('name', sa.String(length=255), nullable=False, comment='Human readable name for the API key'),
        sa.Column('key_hash', sa.String(length=64), nullable=False, unique=True, comment='SHA-256 hash of the API key'),
        sa.Column('key_prefix', sa.String(length=8), nullable=False, comment='First 8 characters for identification'),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True, comment='Whether the API key is active'),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=sa.func.now(), comment='When the API key was created'),
        sa.Column('last_used_at', sa.DateTime(), nullable=True, comment='When the API key was last used'),
        sa.Column('usage_count', sa.Integer(), nullable=False, default=0, comment='Total number of times the API key has been used'),
        sa.Column('rate_limit_per_hour', sa.Integer(), nullable=False, default=100, comment='Maximum requests per hour'),
        sa.Column('allowed_endpoints', sa.Text(), nullable=True, comment='JSON array of allowed endpoints (null = all public endpoints)'),
        sa.Column('created_by', sa.String(length=255), nullable=True, comment='Admin user who created this API key'),
        sa.Column('description', sa.Text(), nullable=True, comment='Description of the API key purpose'),
        sa.Column('expires_at', sa.DateTime(), nullable=True, comment='Optional expiration date'),
        comment='API keys for secure access to public endpoints'
    )
    
    # Create indexes for performance
    op.create_index('idx_api_keys_hash', 'api_keys', ['key_hash'])
    op.create_index('idx_api_keys_active', 'api_keys', ['is_active'])
    op.create_index('idx_api_keys_prefix', 'api_keys', ['key_prefix'])
    op.create_index('idx_api_keys_created_at', 'api_keys', ['created_at'])
    op.create_index('idx_api_keys_last_used', 'api_keys', ['last_used_at'])
    
    # Create API key usage log table for audit trail
    op.create_table(
        'api_key_usage_log',
        sa.Column('id', sa.String(), primary_key=True, default=lambda: str(uuid.uuid4())),
        sa.Column('api_key_id', sa.String(), sa.ForeignKey('api_keys.id'), nullable=False),
        sa.Column('endpoint', sa.String(length=255), nullable=False, comment='API endpoint accessed'),
        sa.Column('method', sa.String(length=10), nullable=False, comment='HTTP method used'),
        sa.Column('client_ip', sa.String(length=45), nullable=True, comment='Client IP address'),
        sa.Column('user_agent', sa.Text(), nullable=True, comment='Client user agent'),
        sa.Column('request_size_bytes', sa.Integer(), nullable=True, comment='Request payload size'),
        sa.Column('response_status', sa.Integer(), nullable=True, comment='HTTP response status'),
        sa.Column('response_time_ms', sa.Float(), nullable=True, comment='Response time in milliseconds'),
        sa.Column('search_query', sa.Text(), nullable=True, comment='Search query for search endpoints'),
        sa.Column('results_count', sa.Integer(), nullable=True, comment='Number of results returned'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='Error message if request failed'),
        sa.Column('accessed_at', sa.DateTime(), nullable=False, default=sa.func.now(), comment='When the API was accessed'),
        comment='Audit log for API key usage'
    )
    
    # Create indexes for usage log
    op.create_index('idx_api_usage_key_id', 'api_key_usage_log', ['api_key_id'])
    op.create_index('idx_api_usage_accessed_at', 'api_key_usage_log', ['accessed_at'])
    op.create_index('idx_api_usage_endpoint', 'api_key_usage_log', ['endpoint'])
    op.create_index('idx_api_usage_client_ip', 'api_key_usage_log', ['client_ip'])


def downgrade():
    """Drop API keys tables"""
    op.drop_index('idx_api_usage_client_ip', 'api_key_usage_log')
    op.drop_index('idx_api_usage_endpoint', 'api_key_usage_log')
    op.drop_index('idx_api_usage_accessed_at', 'api_key_usage_log')
    op.drop_index('idx_api_usage_key_id', 'api_key_usage_log')
    op.drop_table('api_key_usage_log')
    
    op.drop_index('idx_api_keys_last_used', 'api_keys')
    op.drop_index('idx_api_keys_created_at', 'api_keys')
    op.drop_index('idx_api_keys_prefix', 'api_keys')
    op.drop_index('idx_api_keys_active', 'api_keys')
    op.drop_index('idx_api_keys_hash', 'api_keys')
    op.drop_table('api_keys')