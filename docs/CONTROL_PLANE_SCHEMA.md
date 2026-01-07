# Control Plane Database Schema

## Overview

The control plane database schema implements database-per-tenant multi-tenancy for the CAR Platform. It stores tenant metadata and encrypted connection strings for tenant databases.

## Schema Design

### Schema: `control_plane`

All tables are organized under the `control_plane` schema for clear separation from application data.

## Tables

### 1. `tenants`

Stores tenant metadata for multi-tenant architecture.

**Columns:**
- `tenant_id` (UUID, PK) - Unique tenant identifier
- `name` (VARCHAR(255), UNIQUE) - Tenant name (e.g., "system_admin")
- `environment` (ENUM) - Tenant environment: development, staging, production
- `status` (ENUM) - Tenant status: active, inactive, suspended, pending
- `created_at` (TIMESTAMP) - Creation timestamp (auto-set)
- `updated_at` (TIMESTAMP) - Last update timestamp (auto-updated)

**Indexes:**
- `idx_tenants_status` - On `status` column for query performance

**Constraints:**
- Unique constraint on `name`
- Foreign key from `tenant_databases.tenant_id` (CASCADE delete)

**Relationships:**
- One-to-many with `tenant_databases`

### 2. `tenant_databases`

Stores encrypted connection strings and metadata for tenant databases.

**Columns:**
- `id` (UUID, PK) - Unique database record identifier
- `tenant_id` (UUID, FK) - Reference to `tenants.tenant_id`
- `connection_string_encrypted` (TEXT) - Encrypted database connection string
- `database_name` (VARCHAR(255)) - Name of the tenant database
- `host` (VARCHAR(255)) - Database host
- `port` (INTEGER) - Database port (default: 5432)
- `status` (ENUM) - Database status: active, inactive, migrating, error
- `created_at` (TIMESTAMP) - Creation timestamp (auto-set)
- `updated_at` (TIMESTAMP) - Last update timestamp (auto-updated)

**Indexes:**
- `idx_tenant_databases_tenant_id` - On `tenant_id` for join performance
- `idx_tenant_databases_status` - On `status` for query performance

**Constraints:**
- Foreign key to `tenants.tenant_id` with CASCADE delete

**Relationships:**
- Many-to-one with `tenants`

### 3. `system_config`

System-wide configuration key-value store using JSONB for flexible schema.

**Columns:**
- `key` (VARCHAR(255), PK) - Configuration key
- `value` (JSONB) - Configuration value (flexible JSON structure)
- `updated_at` (TIMESTAMP) - Last update timestamp (auto-updated)

**Constraints:**
- Primary key on `key`

## Enum Types

### `tenant_environment`
- `development`
- `staging`
- `production`

### `tenant_status`
- `active`
- `inactive`
- `suspended`
- `pending`

### `database_status`
- `active`
- `inactive`
- `migrating`
- `error`

## Auto-Update Timestamps

All tables with `updated_at` columns have automatic timestamp updates via:

1. **Database Triggers:** PostgreSQL triggers call `control_plane.update_updated_at_column()` function
2. **SQLAlchemy Event Listeners:** Python-level event listeners update `updated_at` before updates

This ensures timestamps are updated whether changes come from SQL or ORM.

## Seed Data

The `system_admin` tenant is automatically created during migration:
- Name: `system_admin`
- Environment: `production`
- Status: `active`

## Indexes

Performance indexes are created on:
- `tenants.status` - For filtering tenants by status
- `tenant_databases.tenant_id` - For efficient joins
- `tenant_databases.status` - For filtering databases by status

## Files

### Models
- `src/db/models/control_plane.py` - SQLAlchemy ORM models

### Migrations
- `alembic/versions/001_control_plane.py` - Initial schema migration
- `alembic/versions/002_seed_data.py` - Seed data migration

### Connection
- `src/db/connection.py` - Database connection manager

## Usage Examples

### Using SQLAlchemy Models

```python
from src.db.connection import get_connection_manager
from src.db.models.control_plane import Tenant, TenantDatabase, SystemConfig

manager = get_connection_manager()

# Query tenants
with manager.get_session() as session:
    tenant = session.query(Tenant).filter_by(name="system_admin").first()
    print(tenant)

# Create new tenant
with manager.get_session() as session:
    new_tenant = Tenant(
        name="acme_corp",
        environment=TenantEnvironment.PRODUCTION,
        status=TenantStatus.ACTIVE
    )
    session.add(new_tenant)
    session.commit()

# Query tenant databases
with manager.get_session() as session:
    databases = session.query(TenantDatabase).filter_by(
        tenant_id=tenant.tenant_id
    ).all()
    for db in databases:
        print(db)
```

## Security Considerations

1. **Encrypted Connection Strings:** `connection_string_encrypted` should be encrypted at rest
2. **Schema Isolation:** Control plane schema is separate from tenant data
3. **CASCADE Delete:** Deleting a tenant automatically removes associated database records
4. **UUID Primary Keys:** Prevent enumeration attacks

## Migration Status

The schema is ready for deployment. Run migrations with:

```bash
python -m alembic upgrade head
```

Or manually via SQL in Supabase SQL Editor (see `MIGRATION_GUIDE.md`).
