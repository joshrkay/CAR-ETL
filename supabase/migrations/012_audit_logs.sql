-- Control plane: Audit logging table
-- Immutable audit trail for all platform events
-- Enforces tenant isolation via RLS

CREATE TABLE IF NOT EXISTS public.audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  user_id UUID,
  event_type TEXT NOT NULL,  -- auth.login, document.upload, etc.
  resource_type TEXT,        -- document, user, tenant
  resource_id TEXT,
  action TEXT NOT NULL,      -- create, read, update, delete
  metadata JSONB DEFAULT '{}',
  ip_address INET,
  user_agent TEXT,
  created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_id ON public.audit_logs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON public.audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type ON public.audit_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON public.audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource ON public.audit_logs(resource_type, resource_id) WHERE resource_type IS NOT NULL;

-- Enable RLS
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only INSERT audit logs for their own tenant
-- Uses public.tenant_id() helper to extract tenant_id from JWT
CREATE POLICY "Insert only" 
ON public.audit_logs 
FOR INSERT
WITH CHECK (tenant_id = public.tenant_id());

-- Policy: Users can only SELECT audit logs for their own tenant
CREATE POLICY "Read own tenant" 
ON public.audit_logs 
FOR SELECT
USING (tenant_id = public.tenant_id());

-- No UPDATE or DELETE policies = immutable audit trail
-- Service role can still manage if needed (via service_role key bypass)

-- Grant permissions
GRANT SELECT, INSERT ON public.audit_logs TO authenticated;
GRANT SELECT, INSERT ON public.audit_logs TO anon;
