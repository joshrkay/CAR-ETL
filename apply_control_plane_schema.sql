-- Apply control plane schema manually
-- Copy and paste this entire file into Supabase SQL Editor
-- https://supabase.com/dashboard/project/ueqzwqejpjmsspfiypgb/sql/new

-- ============================================================
-- TENANTS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS public.tenants (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL CHECK (char_length(name) BETWEEN 2 AND 100),
  slug text UNIQUE NOT NULL CHECK (slug ~ '^[a-z0-9][a-z0-9-]*[a-z0-9]$'),
  environment text NOT NULL DEFAULT 'prod' 
    CHECK (environment IN ('prod', 'staging', 'dev')),
  status text NOT NULL DEFAULT 'active' 
    CHECK (status IN ('active', 'inactive', 'suspended')),
  settings jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Enable RLS immediately
ALTER TABLE public.tenants ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- TENANT USERS JUNCTION TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS public.tenant_users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  roles text[] NOT NULL DEFAULT '{Viewer}' 
    CHECK (roles <@ ARRAY['Admin', 'Analyst', 'Viewer']),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(tenant_id, user_id)
);

-- Enable RLS immediately
ALTER TABLE public.tenant_users ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- AUTH HELPER FUNCTION
-- ============================================================
-- Create in public schema (auth schema is restricted)
CREATE OR REPLACE FUNCTION public.tenant_id() 
RETURNS uuid 
LANGUAGE sql 
STABLE 
SECURITY DEFINER
AS $$
  SELECT
    (current_setting('request.jwt.claims', true)::jsonb
      -> 'app_metadata' ->> 'tenant_id')::uuid;
$$;

-- ============================================================
-- GRANTS
-- ============================================================
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT USAGE ON SCHEMA public TO anon;
GRANT SELECT ON public.tenants TO authenticated;
GRANT SELECT ON public.tenants TO anon;
GRANT SELECT ON public.tenant_users TO authenticated;
GRANT SELECT ON public.tenant_users TO anon;
GRANT EXECUTE ON FUNCTION public.tenant_id() TO authenticated;
GRANT EXECUTE ON FUNCTION public.tenant_id() TO anon;

-- ============================================================
-- RLS POLICIES (drop existing if any)
-- ============================================================
DROP POLICY IF EXISTS "Users view own tenant" ON public.tenants;
DROP POLICY IF EXISTS "Service role manages tenants" ON public.tenants;
DROP POLICY IF EXISTS "View tenant users" ON public.tenant_users;
DROP POLICY IF EXISTS "Admin manages users" ON public.tenant_users;
DROP POLICY IF EXISTS "Service role manages tenant_users" ON public.tenant_users;

-- Tenants: Users can only SELECT their own tenant
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

-- Tenants: Only service_role can modify
CREATE POLICY "Service role manages tenants" 
ON public.tenants 
FOR ALL
USING (auth.role() = 'service_role')
WITH CHECK (auth.role() = 'service_role');

-- Tenant users: Users can SELECT their tenant's users
CREATE POLICY "View tenant users" 
ON public.tenant_users 
FOR SELECT
USING (tenant_id = public.tenant_id());

-- Tenant users: Admins can manage users in their tenant
-- Use JWT-based check to avoid RLS recursion
-- This function reads admin status from JWT token instead of querying tenant_users
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

-- Grant execute to authenticated users
GRANT EXECUTE ON FUNCTION public.is_admin_from_jwt(uuid) TO authenticated;
GRANT EXECUTE ON FUNCTION public.is_admin_from_jwt(uuid) TO anon;

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

-- Tenant users: Service role can manage all
CREATE POLICY "Service role manages tenant_users" 
ON public.tenant_users 
FOR ALL
USING (auth.role() = 'service_role')
WITH CHECK (auth.role() = 'service_role');

-- ============================================================
-- INDEXES
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_tenants_slug ON public.tenants(slug);
CREATE INDEX IF NOT EXISTS idx_tenants_status ON public.tenants(status);
CREATE INDEX IF NOT EXISTS idx_tenants_environment ON public.tenants(environment);
CREATE INDEX IF NOT EXISTS idx_tenant_users_user ON public.tenant_users(user_id);
CREATE INDEX IF NOT EXISTS idx_tenant_users_tenant ON public.tenant_users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_users_tenant_user ON public.tenant_users(tenant_id, user_id);
CREATE INDEX IF NOT EXISTS idx_tenant_users_roles ON public.tenant_users USING GIN(roles);

-- ============================================================
-- TRIGGERS
-- ============================================================
CREATE OR REPLACE FUNCTION public.update_updated_at()
RETURNS TRIGGER 
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS tenants_updated ON public.tenants;
CREATE TRIGGER tenants_updated
  BEFORE UPDATE ON public.tenants
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at();

-- ============================================================
-- REFRESH POSTGREST SCHEMA CACHE
-- ============================================================
NOTIFY pgrst, 'reload schema';

-- Verify tables exist
SELECT 'Tables created successfully!' as status;
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_name IN ('tenants', 'tenant_users');
