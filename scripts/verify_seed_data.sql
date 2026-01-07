-- SQL queries to verify seed data in Supabase SQL Editor
-- Run these queries directly in Supabase SQL Editor if Python connection fails

-- 1. Check if control_plane schema exists
SELECT 
    'Schema Check' as check_type,
    CASE 
        WHEN EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'control_plane')
        THEN 'SUCCESS: control_plane schema exists'
        ELSE 'ERROR: control_plane schema missing'
    END as status;

-- 2. Check if tenants table exists
SELECT 
    'Table Check' as check_type,
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM pg_tables 
            WHERE schemaname = 'control_plane' AND tablename = 'tenants'
        )
        THEN 'SUCCESS: tenants table exists'
        ELSE 'ERROR: tenants table missing'
    END as status;

-- 3. Check if system_admin tenant exists
SELECT 
    'Seed Data Check' as check_type,
    CASE 
        WHEN EXISTS (SELECT 1 FROM control_plane.tenants WHERE name = 'system_admin')
        THEN 'SUCCESS: system_admin tenant exists'
        ELSE 'ERROR: system_admin tenant missing'
    END as status;

-- 4. Display system_admin tenant details
SELECT 
    tenant_id,
    name,
    environment,
    status,
    created_at,
    updated_at
FROM control_plane.tenants
WHERE name = 'system_admin';

-- 5. Verify expected values
SELECT 
    'Value Verification' as check_type,
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM control_plane.tenants 
            WHERE name = 'system_admin' 
            AND environment = 'production' 
            AND status = 'active'
        )
        THEN 'SUCCESS: All values correct (production, active)'
        ELSE 'WARNING: Values may be incorrect'
    END as status;

-- 6. Count all tenants (should be at least 1)
SELECT 
    'Tenant Count' as check_type,
    COUNT(*) as tenant_count,
    CASE 
        WHEN COUNT(*) >= 1 THEN 'SUCCESS: At least one tenant exists'
        ELSE 'ERROR: No tenants found'
    END as status
FROM control_plane.tenants;

-- 7. List all tenants
SELECT 
    tenant_id,
    name,
    environment,
    status,
    created_at
FROM control_plane.tenants
ORDER BY created_at;
