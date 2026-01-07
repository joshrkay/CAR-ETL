# Control Plane Database Setup

This guide explains how to set up the control plane database for the CAR Platform.

## Prerequisites

### BEFORE Setup

1. **PostgreSQL instance running**
   - PostgreSQL 12+ required
   - Access to create databases and schemas

2. **Create 'control_plane' database**
   ```sql
   CREATE DATABASE control_plane;
   ```

3. **Set DATABASE_URL environment variable**
   ```powershell
   $env:DATABASE_URL="postgresql://user:password@localhost:5432/control_plane"
   ```
   
   Or create a `.env` file:
   ```
   DATABASE_URL=postgresql://user:password@localhost:5432/control_plane
   ```

## Installation

1. **Install dependencies**
   ```powershell
   pip install -r requirements.txt
   ```

2. **Run migrations**
   ```powershell
   alembic upgrade head
   ```

   This will:
   - Create the `control_plane` schema
   - Create all tables (tenants, tenant_databases, system_config)
   - Create indexes
   - Seed the `system_admin` tenant

## Database Schema

### Schema: `control_plane`

#### Table: `tenants`
- `tenant_id` (UUID, PK) - Unique tenant identifier
- `name` (VARCHAR(255), UNIQUE) - Tenant name
- `environment` (ENUM) - development, staging, production
- `status` (ENUM) - active, inactive, suspended, pending
- `created_at` (TIMESTAMP) - Creation timestamp
- `updated_at` (TIMESTAMP) - Last update timestamp (auto-updated)

**Indexes:**
- `idx_tenants_status` on `status`

#### Table: `tenant_databases`
- `id` (UUID, PK) - Unique database connection identifier
- `tenant_id` (UUID, FK) - Reference to tenants.tenant_id
- `connection_string_encrypted` (TEXT) - Encrypted connection string
- `database_name` (VARCHAR(255)) - Database name
- `host` (VARCHAR(255)) - Database host
- `port` (INTEGER) - Database port (default: 5432)
- `status` (ENUM) - active, inactive, migrating, error
- `created_at` (TIMESTAMP) - Creation timestamp
- `updated_at` (TIMESTAMP) - Last update timestamp (auto-updated)

**Indexes:**
- `idx_tenant_databases_tenant_id` on `tenant_id`
- `idx_tenant_databases_status` on `status`

#### Table: `system_config`
- `key` (VARCHAR(255), PK) - Configuration key
- `value` (JSONB) - Configuration value (JSON)
- `updated_at` (TIMESTAMP) - Last update timestamp (auto-updated)

## Usage

### Initialize Database Connection

```python
from src.db.connection import init_db, get_connection_manager

# Initialize with default DATABASE_URL from environment
manager = init_db()

# Or with custom URL
manager = init_db("postgresql://user:pass@host:port/db")
```

### Using Database Sessions

```python
from src.db.connection import get_connection_manager

manager = get_connection_manager()

# Context manager (auto-commits/rollbacks)
with manager.get_session() as session:
    tenant = session.query(Tenant).filter_by(name="system_admin").first()
    print(tenant)

# Direct session (must close manually)
session = manager.get_session_direct()
try:
    # Your code here
    pass
finally:
    session.close()
```

### Working with Models

```python
from src.db.models.control_plane import Tenant, TenantEnvironment, TenantStatus
from src.db.connection import get_connection_manager
import uuid

manager = get_connection_manager()

with manager.get_session() as session:
    # Create a new tenant
    tenant = Tenant(
        tenant_id=uuid.uuid4(),
        name="acme_corp",
        environment=TenantEnvironment.PRODUCTION,
        status=TenantStatus.ACTIVE
    )
    session.add(tenant)
    # Session commits automatically on exit
```

## Migrations

### Create a new migration

```powershell
alembic revision --autogenerate -m "description"
```

### Apply migrations

```powershell
alembic upgrade head
```

### Rollback migration

```powershell
alembic downgrade -1
```

### View migration history

```powershell
alembic history
```

### View current revision

```powershell
alembic current
```

## Seed Data

The `002_seed_data.py` migration automatically creates:
- `system_admin` tenant with:
  - Environment: `production`
  - Status: `active`

## Health Check

```python
from src.db.connection import get_connection_manager

manager = get_connection_manager()
if manager.health_check():
    print("Database connection is healthy")
else:
    print("Database connection failed")
```

## Troubleshooting

### Error: "DATABASE_URL environment variable is required"

**Fix:** Set the DATABASE_URL environment variable:
```powershell
$env:DATABASE_URL="postgresql://user:password@localhost:5432/control_plane"
```

### Error: "relation does not exist"

**Fix:** Run migrations:
```powershell
alembic upgrade head
```

### Error: "schema 'control_plane' does not exist"

**Fix:** The migration should create it automatically. If not:
```sql
CREATE SCHEMA control_plane;
```

### Error: "permission denied"

**Fix:** Ensure your database user has:
- CREATE SCHEMA permission
- CREATE TABLE permission
- CREATE TYPE permission (for enums)

## Next Steps

After setting up the control plane database:
1. Configure tenant-specific databases
2. Set up encryption for connection strings
3. Implement tenant isolation logic
4. Add application-level access controls
