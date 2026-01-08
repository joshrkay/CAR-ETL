-- Ingestion plane: Email ingestions table
-- Tracks email ingestion events with tenant isolation

CREATE TABLE IF NOT EXISTS public.email_ingestions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  from_address TEXT NOT NULL,
  to_address TEXT NOT NULL,
  subject TEXT,
  body_document_id UUID REFERENCES public.documents(id) ON DELETE SET NULL,
  attachment_count INT DEFAULT 0,
  received_at TIMESTAMPTZ DEFAULT now() NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_email_ingestions_tenant ON public.email_ingestions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_email_ingestions_from ON public.email_ingestions(from_address, received_at);
CREATE INDEX IF NOT EXISTS idx_email_ingestions_received ON public.email_ingestions(received_at DESC);

-- Enable RLS immediately (no access without policies)
ALTER TABLE public.email_ingestions ENABLE ROW LEVEL SECURITY;

-- Grant permissions
GRANT SELECT, INSERT ON public.email_ingestions TO authenticated;
GRANT SELECT, INSERT ON public.email_ingestions TO anon;

-- RLS Policies

-- Policy: Service role has full access (for webhook ingestion)
CREATE POLICY "Service role manages email ingestions" 
ON public.email_ingestions 
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

-- Policy: Users can view email ingestions for their own tenant only
CREATE POLICY "Users view own tenant email ingestions" 
ON public.email_ingestions 
FOR SELECT
USING (tenant_id = public.tenant_id());

-- Grant direct permissions to service_role
GRANT SELECT, INSERT, UPDATE, DELETE ON public.email_ingestions TO service_role;
