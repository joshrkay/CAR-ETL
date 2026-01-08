-- Feature flags system
-- Allows per-tenant feature flag overrides with default values

-- Feature flags definition table
CREATE TABLE IF NOT EXISTS public.feature_flags (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text UNIQUE NOT NULL,
  description text,
  enabled_default boolean DEFAULT false NOT NULL,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL
);

-- Tenant-specific feature flag overrides
CREATE TABLE IF NOT EXISTS public.tenant_feature_flags (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  flag_id uuid NOT NULL REFERENCES public.feature_flags(id) ON DELETE CASCADE,
  enabled boolean NOT NULL,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL,
  UNIQUE(tenant_id, flag_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_tenant_feature_flags_tenant_id 
ON public.tenant_feature_flags(tenant_id);

CREATE INDEX IF NOT EXISTS idx_tenant_feature_flags_flag_id 
ON public.tenant_feature_flags(flag_id);

CREATE INDEX IF NOT EXISTS idx_feature_flags_name 
ON public.feature_flags(name);

-- Enable RLS
ALTER TABLE public.feature_flags ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tenant_feature_flags ENABLE ROW LEVEL SECURITY;

-- RLS Policies
-- Service role can manage everything
CREATE POLICY "Service role can manage feature_flags" ON public.feature_flags
  FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role can manage tenant_feature_flags" ON public.tenant_feature_flags
  FOR ALL USING (auth.role() = 'service_role');

-- Authenticated users can read flags (for evaluation)
CREATE POLICY "Users can read feature_flags" ON public.feature_flags
  FOR SELECT USING (auth.role() = 'authenticated' OR auth.role() = 'service_role');

-- Users can read their tenant's feature flag overrides
CREATE POLICY "Users can read their tenant feature flags" ON public.tenant_feature_flags
  FOR SELECT USING (
    auth.role() = 'service_role' OR
    tenant_id IN (
      SELECT tenant_id FROM public.tenant_users WHERE user_id = auth.uid()
    )
  );

-- Grant permissions
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT SELECT ON public.feature_flags TO authenticated;
GRANT SELECT ON public.tenant_feature_flags TO authenticated;

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
CREATE TRIGGER update_feature_flags_updated_at
  BEFORE UPDATE ON public.feature_flags
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_tenant_feature_flags_updated_at
  BEFORE UPDATE ON public.tenant_feature_flags
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();
