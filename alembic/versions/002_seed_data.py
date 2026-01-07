"""Seed system_admin tenant

Revision ID: 002_seed_data
Revises: 001_control_plane
Create Date: 2024-01-01 00:01:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

# revision identifiers, used by Alembic.
revision = '002_seed_data'
down_revision = '001_control_plane'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Insert system_admin tenant
    system_admin_tenant_id = uuid.uuid4()
    
    op.execute(f"""
        INSERT INTO control_plane.tenants (tenant_id, name, environment, status, created_at, updated_at)
        VALUES (
            '{system_admin_tenant_id}',
            'system_admin',
            'production',
            'active',
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (name) DO NOTHING
    """)


def downgrade() -> None:
    # Remove system_admin tenant
    op.execute("""
        DELETE FROM control_plane.tenants
        WHERE name = 'system_admin'
    """)
