-- Create tenants table
CREATE TABLE IF NOT EXISTS public.tenants (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug text UNIQUE NOT NULL,
  name text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- Create tenant_users junction table
CREATE TABLE IF NOT EXISTS public.tenant_users (
  user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
  tenant_id uuid REFERENCES public.tenants(id) ON DELETE CASCADE,
  roles text[] DEFAULT '{}',
  created_at timestamptz DEFAULT now(),
  PRIMARY KEY (user_id, tenant_id)
);

-- Enable RLS (Row Level Security)
ALTER TABLE public.tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tenant_users ENABLE ROW LEVEL SECURITY;

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_tenant_users_user_id ON public.tenant_users(user_id);
CREATE INDEX IF NOT EXISTS idx_tenant_users_tenant_id ON public.tenant_users(tenant_id);

-- RLS Policies (basic - adjust based on your security requirements)
-- Allow service role to do everything
CREATE POLICY IF NOT EXISTS "Service role can manage tenants" ON public.tenants
  FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY IF NOT EXISTS "Service role can manage tenant_users" ON public.tenant_users
  FOR ALL USING (auth.role() = 'service_role');

-- Allow authenticated users to read their own tenant assignments
CREATE POLICY IF NOT EXISTS "Users can read their own tenant assignments" ON public.tenant_users
  FOR SELECT USING (auth.uid() = user_id);

-- Grant permissions to service_role and anon roles for PostgREST
GRANT ALL ON public.tenants TO service_role;
GRANT ALL ON public.tenant_users TO service_role;
GRANT SELECT ON public.tenants TO anon, authenticated;
GRANT SELECT ON public.tenant_users TO anon, authenticated;
