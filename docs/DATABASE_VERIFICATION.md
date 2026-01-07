# Database Access Verification

## Overview

Verify that the database exists, is accessible, and ready for tenant provisioning.

## Method 1: SQL Verification (Recommended)

Since direct connection from local machine may fail due to DNS issues, use SQL queries in Supabase SQL Editor.

### Steps:

1. **Open Supabase SQL Editor:**
   - Go to: https://app.supabase.com/project/qifioafprrtkoiyylsqa
   - Click **SQL Editor** → **New query**

2. **Run Verification SQL:**
   - Open: `scripts/verify_database_access.sql`
   - Copy all queries
   - Paste into SQL Editor
   - Click **Run**

3. **Check Results:**
   - All checks should show "SUCCESS"
   - Summary report should show:
     - Schemas: 1
     - Tables: 3
     - Tenants: 1 (system_admin)
     - Migrations: 2

### Expected Results:

✅ **Connection Check:** PostgreSQL version displayed  
✅ **Schema Check:** control_plane schema exists  
✅ **Tables Check:** 3 tables (tenants, tenant_databases, system_config)  
✅ **Seed Data Check:** system_admin tenant exists  
✅ **Permissions Check:** Can create databases  
✅ **Alembic Versions:** 2 migrations applied  

## Method 2: Python Script (If Connection Works)

If you can connect from your local machine:

```bash
# Set environment variables
$env:DATABASE_URL="postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres?sslmode=require"
$env:ENCRYPTION_KEY="[GENERATED_KEY]"

# Run verification
python scripts\verify_database_access.py
```

### What It Checks:

1. ✅ **Database Connection** - Can connect to PostgreSQL
2. ✅ **Schema Exists** - control_plane schema present
3. ✅ **Tables Exist** - All required tables created
4. ✅ **Seed Data** - system_admin tenant exists
5. ✅ **Models Work** - SQLAlchemy models can query data
6. ✅ **DB Permissions** - Can create databases (for tenant provisioning)
7. ✅ **Encryption Key** - ENCRYPTION_KEY configured

## Quick Verification Queries

Run these in Supabase SQL Editor for quick checks:

### Check Schema Exists
```sql
SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'control_plane';
```

### Check Tables Exist
```sql
SELECT tablename FROM pg_tables WHERE schemaname = 'control_plane' ORDER BY tablename;
```

### Check Seed Data
```sql
SELECT * FROM control_plane.tenants WHERE name = 'system_admin';
```

### Check Database Permissions
```sql
SELECT has_database_privilege(current_user, 'postgres', 'CREATE') as can_create_db;
```

## Troubleshooting

### Connection Fails (DNS Error)

**Issue:** `could not translate host name to address`

**Solution:** 
- Use SQL verification in Supabase SQL Editor (Method 1)
- Database is accessible from Supabase dashboard
- Connection issue is local DNS/IPv6 resolution

### Schema Missing

**Issue:** `control_plane schema not found`

**Solution:**
- Run migration: `scripts/run_migrations_manually.sql` in Supabase SQL Editor

### Tables Missing

**Issue:** Tables not found in control_plane schema

**Solution:**
- Run migration: `scripts/run_migrations_manually.sql` in Supabase SQL Editor

### Seed Data Missing

**Issue:** system_admin tenant not found

**Solution:**
- Seed data is included in `run_migrations_manually.sql`
- Re-run the migration or manually insert:
  ```sql
  INSERT INTO control_plane.tenants (tenant_id, name, environment, status)
  VALUES (gen_random_uuid(), 'system_admin', 'production', 'active')
  ON CONFLICT (name) DO NOTHING;
  ```

### No CREATE DATABASE Permission

**Issue:** Cannot create databases for tenant provisioning

**Solution:**
- Ensure DATABASE_URL uses a user with CREATE DATABASE privilege
- For Supabase, you may need to use the admin connection string
- Check Supabase dashboard for connection string with elevated permissions

### Encryption Key Missing

**Issue:** `ENCRYPTION_KEY environment variable not set`

**Solution:**
```bash
# Generate key
python scripts/generate_encryption_key.py

# Set environment variable
$env:ENCRYPTION_KEY="[GENERATED_KEY]"
```

## Ready for Tenant Provisioning

Database is ready when:

- ✅ control_plane schema exists
- ✅ All tables exist (tenants, tenant_databases, system_config)
- ✅ Seed data exists (system_admin tenant)
- ✅ Database permissions allow CREATE DATABASE
- ✅ ENCRYPTION_KEY is configured

Once verified, you can use the tenant provisioning API:

```bash
POST /api/v1/tenants
{
  "name": "acme_corp",
  "environment": "production"
}
```
