"""Create service_account_tokens table

Revision ID: 004_service_account_tokens
Revises: 003_audit_logs_table
Create Date: 2024-01-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = '004_service_account_tokens'
down_revision = '003_audit_logs_table'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create service_account_tokens table
    op.create_table(
        'service_account_tokens',
        sa.Column('token_id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('token_hash', sa.String(255), nullable=False, unique=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('role', sa.String(50), nullable=False),
        sa.Column('created_by', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('last_used', sa.DateTime(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('is_revoked', sa.Boolean(), nullable=False, server_default='false'),
        schema='control_plane',
        sa.ForeignKeyConstraint(['tenant_id'], ['control_plane.tenants.tenant_id'], ondelete='CASCADE')
    )
    
    # Create indexes
    op.create_index('idx_service_account_tokens_tenant_id', 'service_account_tokens', ['tenant_id'], schema='control_plane')
    op.create_index('idx_service_account_tokens_token_hash', 'service_account_tokens', ['token_hash'], schema='control_plane')
    op.create_index('idx_service_account_tokens_is_revoked', 'service_account_tokens', ['is_revoked'], schema='control_plane')
    op.create_index('idx_service_account_tokens_created_at', 'service_account_tokens', ['created_at'], schema='control_plane')


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_service_account_tokens_created_at', table_name='service_account_tokens', schema='control_plane')
    op.drop_index('idx_service_account_tokens_is_revoked', table_name='service_account_tokens', schema='control_plane')
    op.drop_index('idx_service_account_tokens_token_hash', table_name='service_account_tokens', schema='control_plane')
    op.drop_index('idx_service_account_tokens_tenant_id', table_name='service_account_tokens', schema='control_plane')
    
    # Drop table
    op.drop_table('service_account_tokens', schema='control_plane')
