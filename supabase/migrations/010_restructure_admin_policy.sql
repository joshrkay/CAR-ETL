-- Restructure RLS policy to avoid infinite recursion
-- Problem: The "Admin manages users" policy calls check_user_is_admin(),
-- which queries tenant_users, which triggers RLS again, causing recursion.
--
-- Solution: Check admin status from JWT token instead of querying the database.
-- This avoids the recursion because we're not querying tenant_users.

-- Drop the problematic policy
DROP POLICY IF EXISTS "Admin manages users" ON public.tenant_users;

-- Drop the function that causes recursion
DROP FUNCTION IF EXISTS public.check_user_is_admin(uuid) CASCADE;

-- Create a helper function that checks admin status from JWT token
-- This avoids querying tenant_users and thus avoids recursion
CREATE OR REPLACE FUNCTION public.is_admin_from_jwt(target_tenant_id uuid)
RETURNS boolean
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  jwt_tenant_id uuid;
  jwt_roles jsonb;
  is_admin boolean := false;
BEGIN
  -- Extract tenant_id and roles from JWT
  SELECT 
    (current_setting('request.jwt.claims', true)::jsonb 
      -> 'app_metadata' ->> 'tenant_id')::uuid,
    (current_setting('request.jwt.claims', true)::jsonb 
      -> 'app_metadata' -> 'roles')
  INTO jwt_tenant_id, jwt_roles;
  
  -- Check if tenant_id matches and roles contains 'Admin'
  IF jwt_tenant_id = target_tenant_id AND jwt_roles IS NOT NULL THEN
    -- Check if 'Admin' is in the roles array
    SELECT EXISTS (
      SELECT 1 
      FROM jsonb_array_elements_text(jwt_roles) AS role
      WHERE role = 'Admin'
    ) INTO is_admin;
  END IF;
  
  RETURN is_admin;
END;
$$;

-- Grant execute
GRANT EXECUTE ON FUNCTION public.is_admin_from_jwt(uuid) TO authenticated;
GRANT EXECUTE ON FUNCTION public.is_admin_from_jwt(uuid) TO anon;

-- Create policy that checks admin from JWT (no database query = no recursion)
CREATE POLICY "Admin manages users" 
ON public.tenant_users 
FOR ALL
USING (
  tenant_id = public.tenant_id() AND
  public.is_admin_from_jwt(public.tenant_id())
)
WITH CHECK (
  tenant_id = public.tenant_id() AND
  public.is_admin_from_jwt(public.tenant_id())
);

-- The "View tenant users" policy already exists and only allows SELECT
-- The "Service role manages tenant_users" policy already exists for admin operations
