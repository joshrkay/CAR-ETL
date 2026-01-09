-- Document Source Deletions tracking
-- Immutable log of when source files are deleted from external systems
-- Preserves document immutability while tracking source lifecycle

CREATE TABLE IF NOT EXISTS public.document_source_deletions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  document_id UUID NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
  source_type TEXT NOT NULL
    CHECK (source_type IN ('sharepoint', 'google_drive', 'email')),
  source_path TEXT NOT NULL,
  deletion_reason TEXT NOT NULL,
  detected_at TIMESTAMPTZ DEFAULT now() NOT NULL,
  UNIQUE(document_id, source_type)  -- One deletion record per document per source
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_document_deletions_document ON public.document_source_deletions(document_id);
CREATE INDEX IF NOT EXISTS idx_document_deletions_tenant ON public.document_source_deletions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_document_deletions_detected ON public.document_source_deletions(detected_at);

-- Enable RLS immediately (no access without policies)
ALTER TABLE public.document_source_deletions ENABLE ROW LEVEL SECURITY;

-- Grant permissions
GRANT SELECT, INSERT ON public.document_source_deletions TO authenticated;
GRANT SELECT, INSERT ON public.document_source_deletions TO anon;

-- RLS Policies

-- Policy: Users can SELECT deletions for their own tenant only
CREATE POLICY "Users view own tenant deletions"
ON public.document_source_deletions
FOR SELECT
USING (tenant_id = public.tenant_id());

-- Policy: Users can INSERT deletions for their own tenant only
CREATE POLICY "Users insert own tenant deletions"
ON public.document_source_deletions
FOR INSERT
WITH CHECK (tenant_id = public.tenant_id());

-- Policy: Service role has full access
CREATE POLICY "Service role manages deletions"
ON public.document_source_deletions
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
GRANT SELECT, INSERT, UPDATE, DELETE ON public.document_source_deletions TO service_role;

-- Comment on table
COMMENT ON TABLE public.document_source_deletions IS
  'Immutable log of source file deletions. Documents table remains unchanged to preserve ingestion history.';
