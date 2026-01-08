-- Detailed check for all required database objects
-- Run this in Supabase SQL Editor

-- 1. Check if tables exist
SELECT 
    'TABLE' as object_type,
    table_name,
    'EXISTS' as status
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_name IN ('tenants', 'tenant_users', 'auth_rate_limits')
ORDER BY table_name;

-- 2. Check table structures
SELECT 
    table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('tenants', 'tenant_users', 'auth_rate_limits')
ORDER BY table_name, ordinal_position;

-- 3. Check if the auth hook function exists
SELECT 
    'FUNCTION' as object_type,
    routine_name,
    'EXISTS' as status
FROM information_schema.routines
WHERE routine_schema = 'public'
  AND routine_name = 'custom_access_token_hook';

-- 4. Try to create a test tenant (this will work if tables exist and permissions are correct)
DO $$
DECLARE
    test_tenant_id uuid;
BEGIN
    INSERT INTO public.tenants (slug, name) 
    VALUES ('schema-cache-test', 'Schema Cache Test')
    ON CONFLICT (slug) DO UPDATE SET name = 'Schema Cache Test'
    RETURNING id INTO test_tenant_id;
    
    RAISE NOTICE 'Successfully created/updated test tenant: %', test_tenant_id;
    
    -- Clean up
    DELETE FROM public.tenants WHERE slug = 'schema-cache-test';
    RAISE NOTICE 'Test tenant cleaned up';
END $$;
