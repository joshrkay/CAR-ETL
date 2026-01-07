"""Create control plane schema and tables

Revision ID: 001_control_plane
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = '001_control_plane'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create control_plane schema
    op.execute("CREATE SCHEMA IF NOT EXISTS control_plane")
    
    # Create enum types
    op.execute("""
        CREATE TYPE control_plane.tenant_environment AS ENUM (
            'development',
            'staging',
            'production'
        )
    """)
    
    op.execute("""
        CREATE TYPE control_plane.tenant_status AS ENUM (
            'active',
            'inactive',
            'suspended',
            'pending'
        )
    """)
    
    op.execute("""
        CREATE TYPE control_plane.database_status AS ENUM (
            'active',
            'inactive',
            'migrating',
            'error'
        )
    """)
    
    # Create tenants table
    op.create_table(
        'tenants',
        sa.Column('tenant_id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('environment', sa.Enum('development', 'staging', 'production', name='tenant_environment', schema='control_plane'), nullable=False),
        sa.Column('status', sa.Enum('active', 'inactive', 'suspended', 'pending', name='tenant_status', schema='control_plane'), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        schema='control_plane'
    )
    
    # Create unique constraint on tenant name
    op.create_unique_constraint('uq_tenants_name', 'tenants', ['name'], schema='control_plane')
    
    # Create indexes on tenants
    op.create_index('idx_tenants_status', 'tenants', ['status'], schema='control_plane')
    
    # Create tenant_databases table
    op.create_table(
        'tenant_databases',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('connection_string_encrypted', sa.Text(), nullable=False),
        sa.Column('database_name', sa.String(255), nullable=False),
        sa.Column('host', sa.String(255), nullable=False),
        sa.Column('port', sa.Integer(), nullable=False, server_default='5432'),
        sa.Column('status', sa.Enum('active', 'inactive', 'migrating', 'error', name='database_status', schema='control_plane'), nullable=False, server_default='inactive'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        schema='control_plane',
        sa.ForeignKeyConstraint(['tenant_id'], ['control_plane.tenants.tenant_id'], ondelete='CASCADE')
    )
    
    # Create indexes on tenant_databases
    op.create_index('idx_tenant_databases_tenant_id', 'tenant_databases', ['tenant_id'], schema='control_plane')
    op.create_index('idx_tenant_databases_status', 'tenant_databases', ['status'], schema='control_plane')
    
    # Create system_config table
    op.create_table(
        'system_config',
        sa.Column('key', sa.String(255), primary_key=True, nullable=False),
        sa.Column('value', JSONB(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        schema='control_plane'
    )
    
    # Create function to update updated_at timestamp
    op.execute("""
        CREATE OR REPLACE FUNCTION control_plane.update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    
    # Create triggers for updated_at
    op.execute("""
        CREATE TRIGGER update_tenants_updated_at
        BEFORE UPDATE ON control_plane.tenants
        FOR EACH ROW
        EXECUTE FUNCTION control_plane.update_updated_at_column();
    """)
    
    op.execute("""
        CREATE TRIGGER update_tenant_databases_updated_at
        BEFORE UPDATE ON control_plane.tenant_databases
        FOR EACH ROW
        EXECUTE FUNCTION control_plane.update_updated_at_column();
    """)
    
    op.execute("""
        CREATE TRIGGER update_system_config_updated_at
        BEFORE UPDATE ON control_plane.system_config
        FOR EACH ROW
        EXECUTE FUNCTION control_plane.update_updated_at_column();
    """)


def downgrade() -> None:
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS update_system_config_updated_at ON control_plane.system_config")
    op.execute("DROP TRIGGER IF EXISTS update_tenant_databases_updated_at ON control_plane.tenant_databases")
    op.execute("DROP TRIGGER IF EXISTS update_tenants_updated_at ON control_plane.tenants")
    
    # Drop function
    op.execute("DROP FUNCTION IF EXISTS control_plane.update_updated_at_column()")
    
    # Drop tables
    op.drop_table('system_config', schema='control_plane')
    op.drop_table('tenant_databases', schema='control_plane')
    op.drop_table('tenants', schema='control_plane')
    
    # Drop enum types
    op.execute("DROP TYPE IF EXISTS control_plane.database_status")
    op.execute("DROP TYPE IF EXISTS control_plane.tenant_status")
    op.execute("DROP TYPE IF EXISTS control_plane.tenant_environment")
    
    # Drop schema (optional - comment out if you want to keep the schema)
    # op.execute("DROP SCHEMA IF EXISTS control_plane")
