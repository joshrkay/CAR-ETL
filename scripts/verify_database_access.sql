-- SQL-based database access verification
-- Run this in Supabase SQL Editor to verify database exists and is accessible
-- https://app.supabase.com/project/qifioafprrtkoiyylsqa

-- ======================================================================
-- Database Access Verification
-- ======================================================================

-- 1. Check PostgreSQL version and connection
SELECT 
    'Connection Check' as check_type,
    version() as postgresql_version,
    current_database() as current_database,
    current_user as current_user;

-- 2. Check if control_plane schema exists
SELECT 
    'Schema Check' as check_type,
    CASE 
        WHEN EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'control_plane')
        THEN 'SUCCESS: control_plane schema exists'
        ELSE 'ERROR: control_plane schema missing - Run migrations first'
    END as status;

-- 3. Check if required tables exist
SELECT 
    'Tables Check' as check_type,
    COUNT(*) as table_count,
    string_agg(tablename, ', ' ORDER BY tablename) as tables_found
FROM pg_tables
WHERE schemaname = 'control_plane';

-- Expected tables: tenants, tenant_databases, system_config

-- 4. Check table structures
SELECT 
    'Table Structure' as check_type,
    table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'control_plane'
ORDER BY table_name, ordinal_position;

-- 5. Check if seed data (system_admin tenant) exists
SELECT 
    'Seed Data Check' as check_type,
    CASE 
        WHEN EXISTS (SELECT 1 FROM control_plane.tenants WHERE name = 'system_admin')
        THEN 'SUCCESS: system_admin tenant exists'
        ELSE 'ERROR: system_admin tenant missing'
    END as status;

-- 6. Display system_admin tenant details
SELECT 
    'System Admin Tenant' as check_type,
    tenant_id,
    name,
    environment,
    status,
    created_at,
    updated_at
FROM control_plane.tenants
WHERE name = 'system_admin';

-- 7. Check database creation permissions
SELECT 
    'Permissions Check' as check_type,
    CASE 
        WHEN has_database_privilege(current_user, 'postgres', 'CREATE')
        THEN 'SUCCESS: Can create databases'
        ELSE 'WARNING: May not have CREATE DATABASE permission'
    END as status,
    current_user as database_user;

-- 8. Count all tenants
SELECT 
    'Tenant Count' as check_type,
    COUNT(*) as total_tenants,
    COUNT(CASE WHEN status = 'active' THEN 1 END) as active_tenants
FROM control_plane.tenants;

-- 9. Check tenant_databases table
SELECT 
    'Tenant Databases' as check_type,
    COUNT(*) as total_databases,
    COUNT(CASE WHEN status = 'active' THEN 1 END) as active_databases
FROM control_plane.tenant_databases;

-- 10. Verify indexes exist
SELECT 
    'Indexes Check' as check_type,
    COUNT(*) as index_count,
    string_agg(indexname, ', ' ORDER BY indexname) as indexes
FROM pg_indexes
WHERE schemaname = 'control_plane';

-- Expected indexes:
-- - idx_tenants_status
-- - idx_tenant_databases_tenant_id
-- - idx_tenant_databases_status

-- 11. Check Alembic version tracking
SELECT 
    'Alembic Versions' as check_type,
    COUNT(*) as migration_count,
    string_agg(version_num, ', ' ORDER BY version_num) as applied_migrations
FROM control_plane.alembic_version;

-- Expected: 001_control_plane, 002_seed_data

-- 12. Summary Report
SELECT 
    'SUMMARY' as report_type,
    (SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name = 'control_plane') as schemas,
    (SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'control_plane') as tables,
    (SELECT COUNT(*) FROM control_plane.tenants) as tenants,
    (SELECT COUNT(*) FROM control_plane.tenant_databases) as tenant_databases,
    (SELECT COUNT(*) FROM control_plane.alembic_version) as migrations_applied,
    CASE 
        WHEN EXISTS (SELECT 1 FROM control_plane.tenants WHERE name = 'system_admin')
        THEN 'YES'
        ELSE 'NO'
    END as seed_data_exists;

-- ======================================================================
-- Verification Complete
-- ======================================================================
-- If all checks show SUCCESS, the database is ready for tenant provisioning.
-- If any show ERROR, review the issues and fix before proceeding.
