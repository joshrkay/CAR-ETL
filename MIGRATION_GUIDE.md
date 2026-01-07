# Control Plane Database Migration Guide

## Current Status

✅ **Supabase API Keys:** Configured  
✅ **Migration SQL Files:** Ready  
❌ **Direct Connection:** Failing (DNS/IPv6 issue)  
✅ **Manual Migration:** Available as workaround

## Step-by-Step Manual Migration

### Step 1: Open Supabase SQL Editor

1. Go to: **https://app.supabase.com/project/qifioafprrtkoiyylsqa**
2. Click **SQL Editor** in the left sidebar
3. Click **New query** button

### Step 2: Run the Migration

1. Open the file: `scripts/run_migrations_manually.sql`
2. **Select All** (Ctrl+A) and **Copy** (Ctrl+C)
3. **Paste** into Supabase SQL Editor
4. Click **Run** button (or press Ctrl+Enter)
5. Wait for "Success" message

**Expected Output:**
- Schema `control_plane` created
- 3 enum types created
- 3 tables created (tenants, tenant_databases, system_config)
- Indexes and triggers created
- Seed data inserted (system_admin tenant)
- Verification query shows 3 tables

### Step 3: Mark Migrations as Applied

After the migration succeeds, mark it in Alembic's version table:

1. Open the file: `scripts/mark_migrations_applied.sql`
2. **Select All** (Ctrl+A) and **Copy** (Ctrl+C)
3. **Paste** into Supabase SQL Editor
4. Click **Run** button
5. Verify you see 2 rows in `alembic_version` table

**Expected Output:**
- `alembic_version` table created
- 2 migration versions inserted:
  - `001_control_plane`
  - `002_seed_data`

### Step 4: Verify Migration

Run this query in Supabase SQL Editor to verify everything:

```sql
-- Check schema exists
SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'control_plane';

-- Check tables exist
SELECT tablename FROM pg_tables WHERE schemaname = 'control_plane' ORDER BY tablename;

-- Check seed data
SELECT * FROM control_plane.tenants WHERE name = 'system_admin';

-- Check Alembic versions
SELECT * FROM control_plane.alembic_version ORDER BY version_num;
```

**Expected Results:**
- Schema: `control_plane` exists
- Tables: `tenants`, `tenant_databases`, `system_config`
- Seed: 1 row in `tenants` table (system_admin)
- Versions: 2 rows in `alembic_version` table

## What Gets Created

### Schema: `control_plane`

### Enum Types:
- `tenant_environment` (development, staging, production)
- `tenant_status` (active, inactive, suspended, pending)
- `database_status` (active, inactive, migrating, error)

### Tables:

1. **`tenants`**
   - `tenant_id` (UUID, PK)
   - `name` (VARCHAR, UNIQUE)
   - `environment` (ENUM)
   - `status` (ENUM)
   - `created_at`, `updated_at` (TIMESTAMP)

2. **`tenant_databases`**
   - `id` (UUID, PK)
   - `tenant_id` (UUID, FK → tenants)
   - `connection_string_encrypted` (TEXT)
   - `database_name`, `host`, `port`
   - `status` (ENUM)
   - `created_at`, `updated_at` (TIMESTAMP)

3. **`system_config`**
   - `key` (VARCHAR, PK)
   - `value` (JSONB)
   - `updated_at` (TIMESTAMP)

### Indexes:
- `idx_tenants_status`
- `idx_tenant_databases_tenant_id`
- `idx_tenant_databases_status`

### Triggers:
- Auto-update `updated_at` on all tables

### Seed Data:
- `system_admin` tenant (production, active)

## After Migration

Once the migration is complete:

1. ✅ Control plane schema is ready
2. ✅ You can use database models in your code
3. ✅ Alembic recognizes migrations as applied
4. ✅ Future migrations can be run via Alembic (once connection is fixed)

## Troubleshooting

### Error: "schema already exists"
- **Fix:** This is fine - the migration uses `IF NOT EXISTS`
- Continue with the rest of the SQL

### Error: "type already exists"
- **Fix:** The enum types already exist
- This is fine - continue

### Error: "relation already exists"
- **Fix:** Tables already exist
- This is fine if you're re-running

### Error: "duplicate key value"
- **Fix:** Seed data already exists
- This is fine - the migration uses `ON CONFLICT DO NOTHING`

## Next Steps

After successful migration:

1. **Test Database Models:**
   ```python
   from src.db.connection import get_connection_manager
   from src.db.models.control_plane import Tenant
   
   manager = get_connection_manager()
   with manager.get_session() as session:
       tenant = session.query(Tenant).filter_by(name="system_admin").first()
       print(tenant)
   ```

2. **Continue Development:**
   - Use the control plane models in your application
   - Create new tenants and databases
   - Configure system settings

3. **Future Migrations:**
   - Once connection is fixed, use `alembic upgrade head`
   - Or continue using manual SQL migrations

## Files Reference

- **Migration SQL:** `scripts/run_migrations_manually.sql`
- **Mark Applied:** `scripts/mark_migrations_applied.sql`
- **Verification:** Run queries in Step 4 above
- **Models:** `src/db/models/control_plane.py`
- **Connection:** `src/db/connection.py`
