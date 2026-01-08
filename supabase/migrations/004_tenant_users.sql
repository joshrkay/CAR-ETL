-- Control plane: Tenant Users junction table
-- Links auth.users to tenants with roles

CREATE TABLE IF NOT EXISTS public.tenant_users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  roles text[] NOT NULL DEFAULT '{Viewer}' 
    CHECK (roles <@ ARRAY['Admin', 'Analyst', 'Viewer']),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(tenant_id, user_id)
);

-- Enable RLS immediately (no access without policies)
ALTER TABLE public.tenant_users ENABLE ROW LEVEL SECURITY;

-- Grant usage on schema
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT USAGE ON SCHEMA public TO anon;

-- Grant SELECT only (INSERT/UPDATE/DELETE via policies)
GRANT SELECT ON public.tenant_users TO authenticated;
GRANT SELECT ON public.tenant_users TO anon;
