# Manual Migration Instructions for Supabase

If you're having connection issues with Alembic, you can run the migrations manually in Supabase SQL Editor.

## Step 1: Open Supabase SQL Editor

1. Go to https://app.supabase.com/project/qifioafprrtkoiyylsqa
2. Click on **SQL Editor** in the left sidebar
3. Click **New query**

## Step 2: Run the Migration SQL

1. Open the file: `scripts/run_migrations_manually.sql`
2. Copy the entire contents
3. Paste into the Supabase SQL Editor
4. Click **Run** (or press Ctrl+Enter)

## Step 3: Verify Migration

After running the SQL, verify the tables were created:

```sql
SELECT 
    schemaname,
    tablename
FROM pg_tables
WHERE schemaname = 'control_plane'
ORDER BY tablename;
```

You should see:
- `control_plane.tenants`
- `control_plane.tenant_databases`
- `control_plane.system_config`

## Step 4: Verify Seed Data

Check that the system_admin tenant was created:

```sql
SELECT * FROM control_plane.tenants WHERE name = 'system_admin';
```

## What This Creates

### Schema: `control_plane`

### Tables:
1. **tenants**
   - tenant_id (UUID, PK)
   - name (VARCHAR, UNIQUE)
   - environment (ENUM)
   - status (ENUM)
   - created_at, updated_at

2. **tenant_databases**
   - id (UUID, PK)
   - tenant_id (UUID, FK)
   - connection_string_encrypted (TEXT)
   - database_name, host, port
   - status (ENUM)
   - created_at, updated_at

3. **system_config**
   - key (VARCHAR, PK)
   - value (JSONB)
   - updated_at

### Indexes:
- idx_tenants_status
- idx_tenant_databases_tenant_id
- idx_tenant_databases_status

### Triggers:
- Auto-update `updated_at` timestamps on all tables

### Seed Data:
- `system_admin` tenant (production, active)

## After Manual Migration

Once the schema is created manually, you can:

1. **Verify in Python:**
   ```python
   from src.db.connection import get_connection_manager
   from src.db.models.control_plane import Tenant
   
   manager = get_connection_manager()
   with manager.get_session() as session:
       tenant = session.query(Tenant).filter_by(name="system_admin").first()
       print(tenant)
   ```

2. **Use the database models** in your application

3. **Future migrations:** You may need to run them manually or fix the connection issue first

## Troubleshooting

### Error: "schema already exists"
- This is fine - the migration uses `IF NOT EXISTS`
- Continue with the rest of the SQL

### Error: "type already exists"
- The enum types already exist
- This is fine - continue

### Error: "relation already exists"
- Tables already exist
- This is fine if you're re-running

## Next Steps

After running the manual migration:
1. The control plane schema is ready
2. You can start using the database models
3. Future schema changes can be done via SQL Editor or by fixing Alembic connection
