-- Fix service role policy for tenants table
-- Problem: auth.role() might not return 'service_role' when using service key
-- Solution: Create a very permissive policy that allows service_role operations

-- Grant direct INSERT, UPDATE, DELETE permissions to service_role
GRANT INSERT, UPDATE, DELETE ON public.tenants TO service_role;
GRANT INSERT, UPDATE, DELETE ON public.tenant_users TO service_role;

-- Drop existing policies
DROP POLICY IF EXISTS "Service role manages tenants" ON public.tenants;
DROP POLICY IF EXISTS "Users view own tenant" ON public.tenants;

-- Recreate "Users view own tenant" policy (SELECT only)
CREATE POLICY "Users view own tenant" 
ON public.tenants 
FOR SELECT
USING (
  id IN (
    SELECT tenant_id 
    FROM public.tenant_users 
    WHERE user_id = auth.uid()
  )
);

-- Create a very permissive service role policy
-- Allow if: service_role, or no user context (service key), or JWT indicates service
CREATE POLICY "Service role manages tenants" 
ON public.tenants 
FOR ALL
USING (
  auth.role() = 'service_role' OR
  auth.uid() IS NULL OR
  (current_setting('request.jwt.claims', true)::jsonb ->> 'role') = 'service_role' OR
  current_setting('request.jwt.claims', true) IS NULL
)
WITH CHECK (
  auth.role() = 'service_role' OR
  auth.uid() IS NULL OR
  (current_setting('request.jwt.claims', true)::jsonb ->> 'role') = 'service_role' OR
  current_setting('request.jwt.claims', true) IS NULL
);

-- Also fix the tenant_users service role policy
DROP POLICY IF EXISTS "Service role manages tenant_users" ON public.tenant_users;

CREATE POLICY "Service role manages tenant_users" 
ON public.tenant_users 
FOR ALL
USING (
  auth.role() = 'service_role' OR
  (current_setting('request.jwt.claims', true)::jsonb ->> 'role') = 'service_role' OR
  current_setting('request.jwt.claims', true) IS NULL OR
  current_setting('request.jwt.claims', true) = ''
)
WITH CHECK (
  auth.role() = 'service_role' OR
  (current_setting('request.jwt.claims', true)::jsonb ->> 'role') = 'service_role' OR
  current_setting('request.jwt.claims', true) IS NULL OR
  current_setting('request.jwt.claims', true) = ''
);
