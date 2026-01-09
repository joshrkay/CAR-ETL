-- Control plane: Connectors table
-- Stores OAuth credentials and sync configuration for external data sources
-- Enforces tenant isolation and encrypts sensitive config data

CREATE TABLE IF NOT EXISTS public.connectors (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  type TEXT NOT NULL CHECK (type IN ('sharepoint', 'google_drive')),
  config JSONB NOT NULL,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'error')),
  last_sync_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_connectors_tenant ON public.connectors(tenant_id);
CREATE INDEX IF NOT EXISTS idx_connectors_type ON public.connectors(tenant_id, type);
CREATE INDEX IF NOT EXISTS idx_connectors_status ON public.connectors(tenant_id, status);

-- Enable RLS immediately (no access without policies)
ALTER TABLE public.connectors ENABLE ROW LEVEL SECURITY;

-- Grant permissions
GRANT SELECT, INSERT, UPDATE ON public.connectors TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.connectors TO anon;

-- RLS Policies

-- Policy: Users can SELECT connectors for their own tenant only
CREATE POLICY "Users view own tenant connectors" 
ON public.connectors 
FOR SELECT
USING (tenant_id = public.tenant_id());

-- Policy: Users can INSERT connectors for their own tenant only
CREATE POLICY "Users insert own tenant connectors" 
ON public.connectors 
FOR INSERT
WITH CHECK (tenant_id = public.tenant_id());

-- Policy: Users can UPDATE connectors for their own tenant only
CREATE POLICY "Users update own tenant connectors" 
ON public.connectors 
FOR UPDATE
USING (tenant_id = public.tenant_id())
WITH CHECK (tenant_id = public.tenant_id());

-- Policy: Service role has full access
CREATE POLICY "Service role manages connectors" 
ON public.connectors 
FOR ALL
USING (
  auth.role() = 'service_role' OR
  (current_setting('request.jwt.claims', true)::jsonb ->> 'role') = 'service_role' OR
  current_setting('request.jwt.claims', true) IS NULL
)
WITH CHECK (
  auth.role() = 'service_role' OR
  (current_setting('request.jwt.claims', true)::jsonb ->> 'role') = 'service_role' OR
  current_setting('request.jwt.claims', true) IS NULL
);

-- Grant direct permissions to service_role
GRANT SELECT, INSERT, UPDATE, DELETE ON public.connectors TO service_role;

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_connectors_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER connectors_updated_at
  BEFORE UPDATE ON public.connectors
  FOR EACH ROW
  EXECUTE FUNCTION update_connectors_updated_at();

-- OAuth state storage for callback validation
CREATE TABLE IF NOT EXISTS public.oauth_states (
  state TEXT PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- Index for expiration cleanup
CREATE INDEX IF NOT EXISTS idx_oauth_states_expires ON public.oauth_states(expires_at);

-- Enable RLS
ALTER TABLE public.oauth_states ENABLE ROW LEVEL SECURITY;

-- Service role has full access (for state storage/retrieval)
CREATE POLICY "Service role manages oauth states" 
ON public.oauth_states 
FOR ALL
USING (
  auth.role() = 'service_role' OR
  (current_setting('request.jwt.claims', true)::jsonb ->> 'role') = 'service_role' OR
  current_setting('request.jwt.claims', true) IS NULL
)
WITH CHECK (
  auth.role() = 'service_role' OR
  (current_setting('request.jwt.claims', true)::jsonb ->> 'role') = 'service_role' OR
  current_setting('request.jwt.claims', true) IS NULL
);

GRANT SELECT, INSERT, DELETE ON public.oauth_states TO service_role;
