-- Control plane: Authentication helper functions
-- Extract tenant_id from JWT claims for RLS policies
-- Note: Created in public schema (auth schema is restricted)

CREATE OR REPLACE FUNCTION public.tenant_id() 
RETURNS uuid 
LANGUAGE sql 
STABLE 
SECURITY DEFINER
AS $$
  SELECT COALESCE(
    (current_setting('request.jwt.claims', true)::jsonb 
      -> 'app_metadata' ->> 'tenant_id')::uuid,
    '00000000-0000-0000-0000-000000000000'::uuid
  );
$$;

-- Grant execute to authenticated users
GRANT EXECUTE ON FUNCTION public.tenant_id() TO authenticated;
GRANT EXECUTE ON FUNCTION public.tenant_id() TO anon;
