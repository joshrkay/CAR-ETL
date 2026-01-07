"""Create immutable audit_logs table with WORM constraints.

Revision ID: 003_audit_logs
Revises: 002_seed_data
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime

# revision identifiers, used by Alembic.
revision = '003_audit_logs'
down_revision = '002_seed_data'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create audit_logs table with immutability constraints."""
    
    # Create audit_logs table in control_plane schema
    op.create_table(
        'audit_logs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('tenant_id', sa.String(255), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('action_type', sa.String(100), nullable=False),
        sa.Column('resource_id', sa.String(255), nullable=True),
        sa.Column('request_metadata', JSONB, nullable=False, server_default='{}'),
        sa.Column('retention_until', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Schema('control_plane')
    )
    
    # Create indexes for query performance
    op.create_index(
        'idx_audit_logs_tenant_id',
        'control_plane.audit_logs',
        ['tenant_id']
    )
    
    op.create_index(
        'idx_audit_logs_timestamp',
        'control_plane.audit_logs',
        ['timestamp']
    )
    
    op.create_index(
        'idx_audit_logs_action_type',
        'control_plane.audit_logs',
        ['action_type']
    )
    
    op.create_index(
        'idx_audit_logs_retention_until',
        'control_plane.audit_logs',
        ['retention_until']
    )
    
    # Create composite index for common queries
    op.create_index(
        'idx_audit_logs_tenant_timestamp',
        'control_plane.audit_logs',
        ['tenant_id', 'timestamp']
    )
    
    # Create function to prevent updates (WORM enforcement)
    op.execute("""
        CREATE OR REPLACE FUNCTION control_plane.prevent_audit_log_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'Audit logs are immutable. Updates and deletes are not allowed.'
                USING ERRCODE = 'P0001';
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Create trigger to prevent updates
    op.execute("""
        CREATE TRIGGER prevent_audit_log_update
        BEFORE UPDATE ON control_plane.audit_logs
        FOR EACH ROW
        EXECUTE FUNCTION control_plane.prevent_audit_log_modification();
    """)
    
    # Create trigger to prevent deletes
    op.execute("""
        CREATE TRIGGER prevent_audit_log_delete
        BEFORE DELETE ON control_plane.audit_logs
        FOR EACH ROW
        EXECUTE FUNCTION control_plane.prevent_audit_log_modification();
    """)
    
    # Create function to log tampering attempts
    op.execute("""
        CREATE OR REPLACE FUNCTION control_plane.log_tampering_attempt()
        RETURNS TRIGGER AS $$
        DECLARE
            attempt_data JSONB;
        BEGIN
            -- Log the tampering attempt itself
            attempt_data := jsonb_build_object(
                'operation', TG_OP,
                'table_name', TG_TABLE_NAME,
                'attempted_at', CURRENT_TIMESTAMP,
                'old_data', row_to_json(OLD),
                'new_data', row_to_json(NEW)
            );
            
            -- Insert tampering attempt log (this will also be protected by triggers)
            INSERT INTO control_plane.audit_logs (
                user_id,
                tenant_id,
                timestamp,
                action_type,
                resource_id,
                request_metadata,
                retention_until
            ) VALUES (
                'system',
                COALESCE((OLD->>'tenant_id'), 'system'),
                CURRENT_TIMESTAMP,
                'audit.tampering.attempt',
                (OLD->>'id'),
                attempt_data,
                CURRENT_TIMESTAMP + INTERVAL '30 years'
            );
            
            -- Re-raise the exception
            RAISE EXCEPTION 'Audit logs are immutable. Updates and deletes are not allowed.'
                USING ERRCODE = 'P0001';
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Enable Row Level Security (RLS) - only allow inserts, no updates/deletes
    op.execute("ALTER TABLE control_plane.audit_logs ENABLE ROW LEVEL SECURITY")
    
    # Create RLS policy: allow inserts only (no updates/deletes)
    op.execute("""
        CREATE POLICY audit_logs_insert_only
        ON control_plane.audit_logs
        FOR INSERT
        TO authenticated
        WITH CHECK (true);
    """)
    
    # Create RLS policy: allow selects (for reading audit logs)
    op.execute("""
        CREATE POLICY audit_logs_select
        ON control_plane.audit_logs
        FOR SELECT
        TO authenticated
        USING (true);
    """)
    
    # Explicitly deny updates and deletes via RLS
    op.execute("""
        CREATE POLICY audit_logs_no_update
        ON control_plane.audit_logs
        FOR UPDATE
        TO authenticated
        USING (false);
    """)
    
    op.execute("""
        CREATE POLICY audit_logs_no_delete
        ON control_plane.audit_logs
        FOR DELETE
        TO authenticated
        USING (false);
    """)


def downgrade() -> None:
    """Remove audit_logs table and related objects."""
    
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS prevent_audit_log_delete ON control_plane.audit_logs")
    op.execute("DROP TRIGGER IF EXISTS prevent_audit_log_update ON control_plane.audit_logs")
    
    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS control_plane.log_tampering_attempt()")
    op.execute("DROP FUNCTION IF EXISTS control_plane.prevent_audit_log_modification()")
    
    # Drop indexes
    op.drop_index('idx_audit_logs_tenant_timestamp', table_name='audit_logs', schema='control_plane')
    op.drop_index('idx_audit_logs_retention_until', table_name='audit_logs', schema='control_plane')
    op.drop_index('idx_audit_logs_action_type', table_name='audit_logs', schema='control_plane')
    op.drop_index('idx_audit_logs_timestamp', table_name='audit_logs', schema='control_plane')
    op.drop_index('idx_audit_logs_tenant_id', table_name='audit_logs', schema='control_plane')
    
    # Drop RLS policies
    op.execute("DROP POLICY IF EXISTS audit_logs_no_delete ON control_plane.audit_logs")
    op.execute("DROP POLICY IF EXISTS audit_logs_no_update ON control_plane.audit_logs")
    op.execute("DROP POLICY IF EXISTS audit_logs_select ON control_plane.audit_logs")
    op.execute("DROP POLICY IF EXISTS audit_logs_insert_only ON control_plane.audit_logs")
    
    # Drop table
    op.drop_table('audit_logs', schema='control_plane')
