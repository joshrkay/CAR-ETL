-- Understanding plane: Document chunks table for semantic search
-- Stores document chunks with embeddings for vector similarity search
-- Enforces tenant isolation via RLS
--
-- SECURITY: Content stored in this table MUST be redacted before insertion.
-- Use ChunkStorageService.store_chunks() which enforces redaction (defense in depth).

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Document chunks table
CREATE TABLE IF NOT EXISTS public.document_chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  document_id UUID NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
  extraction_id UUID,  -- Nullable: references future extractions table
  chunk_index INT NOT NULL,
  content TEXT NOT NULL,
  embedding vector(1536),  -- OpenAI text-embedding-3-small
  token_count INT NOT NULL,
  page_numbers INT[],
  section_header TEXT,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
  UNIQUE(document_id, chunk_index)
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_chunks_tenant ON public.document_chunks(tenant_id);
CREATE INDEX IF NOT EXISTS idx_chunks_document ON public.document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_extraction ON public.document_chunks(extraction_id) 
  WHERE extraction_id IS NOT NULL;

-- Enable RLS immediately (no access without policies)
ALTER TABLE public.document_chunks ENABLE ROW LEVEL SECURITY;

-- Grant permissions
GRANT SELECT, INSERT, UPDATE ON public.document_chunks TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.document_chunks TO anon;

-- RLS Policies

-- Policy: Users can SELECT chunks for their own tenant only
CREATE POLICY "Users view own tenant chunks" 
ON public.document_chunks 
FOR SELECT
USING (tenant_id = public.tenant_id());

-- Policy: Users can INSERT chunks for their own tenant only
CREATE POLICY "Users insert own tenant chunks" 
ON public.document_chunks 
FOR INSERT
WITH CHECK (tenant_id = public.tenant_id());

-- Policy: Users can UPDATE chunks for their own tenant only
CREATE POLICY "Users update own tenant chunks" 
ON public.document_chunks 
FOR UPDATE
USING (tenant_id = public.tenant_id())
WITH CHECK (tenant_id = public.tenant_id());

-- Policy: Service role has full access
CREATE POLICY "Service role manages chunks" 
ON public.document_chunks 
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
GRANT SELECT, INSERT, UPDATE, DELETE ON public.document_chunks TO service_role;
