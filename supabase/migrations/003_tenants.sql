-- Control plane: Tenants table
-- Multi-tenant schema with bulletproof tenant isolation

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

-- Enable RLS immediately (no access without policies)
ALTER TABLE public.tenants ENABLE ROW LEVEL SECURITY;

-- Grant usage on schema
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT USAGE ON SCHEMA public TO anon;

-- Grant SELECT only (INSERT/UPDATE/DELETE via policies)
GRANT SELECT ON public.tenants TO authenticated;
GRANT SELECT ON public.tenants TO anon;
