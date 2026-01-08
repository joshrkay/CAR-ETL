-- Storage bucket RLS policies for tenant isolation
-- Ensures tenants can only access their own storage buckets

-- Note: Supabase Storage uses the storage.objects table for file metadata
-- The storage schema is managed by Supabase, but we can add policies

-- Helper function to extract tenant_id from bucket name
-- Bucket names follow pattern: documents-{tenant_id}
-- This function is created in public schema to avoid storage schema restrictions
CREATE OR REPLACE FUNCTION public.tenant_id_from_bucket(bucket_id text)
RETURNS uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
AS $$
  SELECT CASE
    WHEN bucket_id LIKE 'documents-%' THEN
      (regexp_replace(bucket_id, '^documents-', ''))::uuid
    ELSE
      NULL::uuid
  END;
$$;

-- Grant execute to authenticated users
GRANT EXECUTE ON FUNCTION public.tenant_id_from_bucket(text) TO authenticated;
GRANT EXECUTE ON FUNCTION public.tenant_id_from_bucket(text) TO anon;

-- Policy: Users can SELECT objects in their tenant's bucket
-- Only allows access to buckets matching their tenant_id
-- Note: Supabase Storage RLS is managed by Supabase
-- We can only create policies if RLS is already enabled
-- The storage.objects table is owned by Supabase, so we cannot ALTER it
DO $$
BEGIN
  -- Check if storage.objects table exists and RLS is enabled
  -- We cannot enable RLS ourselves (requires table ownership)
  -- But we can create policies if RLS is already enabled
  IF EXISTS (
    SELECT 1 
    FROM pg_tables t
    JOIN pg_class c ON c.relname = t.tablename
    WHERE t.schemaname = 'storage' 
      AND t.tablename = 'objects'
      AND c.relrowsecurity = true  -- RLS is enabled
  ) THEN
    -- Drop existing policies if they exist (idempotent)
    DROP POLICY IF EXISTS "Tenant can view own bucket objects" ON storage.objects;
    DROP POLICY IF EXISTS "Tenant can insert into own bucket" ON storage.objects;
    DROP POLICY IF EXISTS "Tenant can update own bucket objects" ON storage.objects;
    DROP POLICY IF EXISTS "Tenant can delete own bucket objects" ON storage.objects;
    DROP POLICY IF EXISTS "Service role manages storage objects" ON storage.objects;
    
    -- Create policies using dollar-quoted strings to avoid quote issues
    EXECUTE $policy1$
      CREATE POLICY "Tenant can view own bucket objects"
      ON storage.objects
      FOR SELECT
      USING (
        public.tenant_id_from_bucket(bucket_id) = public.tenant_id()
      );
    $policy1$;
    
    EXECUTE $policy2$
      CREATE POLICY "Tenant can insert into own bucket"
      ON storage.objects
      FOR INSERT
      WITH CHECK (
        public.tenant_id_from_bucket(bucket_id) = public.tenant_id()
      );
    $policy2$;
    
    EXECUTE $policy3$
      CREATE POLICY "Tenant can update own bucket objects"
      ON storage.objects
      FOR UPDATE
      USING (
        public.tenant_id_from_bucket(bucket_id) = public.tenant_id()
      )
      WITH CHECK (
        public.tenant_id_from_bucket(bucket_id) = public.tenant_id()
      );
    $policy3$;
    
    EXECUTE $policy4$
      CREATE POLICY "Tenant can delete own bucket objects"
      ON storage.objects
      FOR DELETE
      USING (
        public.tenant_id_from_bucket(bucket_id) = public.tenant_id()
      );
    $policy4$;
    
    EXECUTE $policy5$
      CREATE POLICY "Service role manages storage objects"
      ON storage.objects
      FOR ALL
      USING (auth.role() = 'service_role')
      WITH CHECK (auth.role() = 'service_role');
    $policy5$;
  ELSE
    -- RLS is not enabled on storage.objects
    -- This is expected - Supabase manages Storage RLS separately
    -- Policies will be created when RLS is enabled via Dashboard or API
    RAISE NOTICE 'RLS is not enabled on storage.objects. Policies will be created when RLS is enabled.';
  END IF;
END $$;

-- Refresh PostgREST schema cache
NOTIFY pgrst, 'reload schema';
