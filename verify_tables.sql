-- Run this in Supabase SQL Editor to verify tables exist
-- Go to: https://supabase.com/dashboard/project/ueqzwqejpjmsspfiypgb/sql/new

-- Check if tables exist
SELECT 
    table_name,
    table_type
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_name IN ('tenants', 'tenant_users', 'auth_rate_limits')
ORDER BY table_name;

-- Check if the auth hook function exists
SELECT 
    routine_name,
    routine_type
FROM information_schema.routines
WHERE routine_schema = 'public'
  AND routine_name = 'custom_access_token_hook';

-- Test creating a tenant (should work if tables exist)
-- INSERT INTO public.tenants (slug, name) 
-- VALUES ('test-verify', 'Test Verification')
-- ON CONFLICT (slug) DO NOTHING
-- RETURNING id, slug;
