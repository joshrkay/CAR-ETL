-- Verification queries for control plane migration
-- Run these in Supabase SQL Editor after migration to verify everything is set up correctly

-- 1. Check schema exists
SELECT 
    'Schema Check' as check_type,
    CASE 
        WHEN EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'control_plane')
        THEN '✓ control_plane schema exists'
        ELSE '✗ control_plane schema missing'
    END as status;

-- 2. Check enum types exist
SELECT 
    'Enum Types Check' as check_type,
    COUNT(*) as enum_count,
    string_agg(typname, ', ') as enum_names
FROM pg_type t
JOIN pg_namespace n ON n.oid = t.typnamespace
WHERE n.nspname = 'control_plane'
AND t.typtype = 'e';

-- 3. Check tables exist
SELECT 
    'Tables Check' as check_type,
    COUNT(*) as table_count,
    string_agg(tablename, ', ' ORDER BY tablename) as table_names
FROM pg_tables
WHERE schemaname = 'control_plane';

-- 4. Check indexes exist
SELECT 
    'Indexes Check' as check_type,
    COUNT(*) as index_count,
    string_agg(indexname, ', ' ORDER BY indexname) as index_names
FROM pg_indexes
WHERE schemaname = 'control_plane';

-- 5. Check seed data (system_admin tenant)
SELECT 
    'Seed Data Check' as check_type,
    COUNT(*) as tenant_count,
    string_agg(name, ', ') as tenant_names
FROM control_plane.tenants;

-- 6. Check Alembic version table
SELECT 
    'Alembic Versions Check' as check_type,
    COUNT(*) as version_count,
    string_agg(version_num, ', ' ORDER BY version_num) as versions
FROM control_plane.alembic_version;

-- 7. Detailed table structure check
SELECT 
    'Table Structure' as check_type,
    table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'control_plane'
ORDER BY table_name, ordinal_position;

-- 8. Summary report
SELECT 
    'SUMMARY' as report_type,
    (SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name = 'control_plane') as schemas,
    (SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'control_plane') as tables,
    (SELECT COUNT(*) FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace WHERE n.nspname = 'control_plane' AND t.typtype = 'e') as enums,
    (SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'control_plane') as indexes,
    (SELECT COUNT(*) FROM control_plane.tenants) as tenants,
    (SELECT COUNT(*) FROM control_plane.alembic_version) as alembic_versions;
