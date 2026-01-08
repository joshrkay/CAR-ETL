-- Ingestion plane: Documents table
-- Immutable document metadata with tenant isolation
-- Enforces unique file_hash per tenant to prevent duplicates

CREATE TABLE IF NOT EXISTS public.documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  file_hash TEXT NOT NULL,
  storage_path TEXT NOT NULL,
  original_filename TEXT NOT NULL,
  mime_type TEXT NOT NULL CHECK (mime_type IN (
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'image/png',
    'image/jpeg',
    'text/plain',
    'text/csv'
  )),
  file_size_bytes BIGINT NOT NULL CHECK (file_size_bytes > 0),
  source_type TEXT NOT NULL DEFAULT 'upload' 
    CHECK (source_type IN ('upload', 'email', 'sharepoint', 'google_drive')),
  source_path TEXT,
  parent_id UUID REFERENCES public.documents(id) ON DELETE SET NULL,
  uploaded_by UUID REFERENCES auth.users(id),
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'processing', 'ready', 'failed')),
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT now() NOT NULL,
  UNIQUE(tenant_id, file_hash)
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_documents_tenant ON public.documents(tenant_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON public.documents(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_documents_hash ON public.documents(tenant_id, file_hash);
CREATE INDEX IF NOT EXISTS idx_documents_parent ON public.documents(parent_id) WHERE parent_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_documents_uploaded_by ON public.documents(uploaded_by) WHERE uploaded_by IS NOT NULL;

-- Enable RLS immediately (no access without policies)
ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;

-- Grant permissions
GRANT SELECT, INSERT ON public.documents TO authenticated;
GRANT SELECT, INSERT ON public.documents TO anon;

-- RLS Policies

-- Policy: Users can SELECT documents for their own tenant only
CREATE POLICY "Users view own tenant documents" 
ON public.documents 
FOR SELECT
USING (tenant_id = public.tenant_id());

-- Policy: Users can INSERT documents for their own tenant only
CREATE POLICY "Users insert own tenant documents" 
ON public.documents 
FOR INSERT
WITH CHECK (tenant_id = public.tenant_id());

-- Policy: Service role has full access
CREATE POLICY "Service role manages documents" 
ON public.documents 
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
GRANT SELECT, INSERT, UPDATE, DELETE ON public.documents TO service_role;
