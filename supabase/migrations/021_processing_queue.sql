-- Ingestion plane: Processing queue table
-- Queue for document processing with retry logic
-- Enforces tenant isolation via RLS

CREATE TABLE IF NOT EXISTS public.processing_queue (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  document_id UUID NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
  priority INT NOT NULL DEFAULT 0,
  attempts INT NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  max_attempts INT NOT NULL DEFAULT 3 CHECK (max_attempts > 0),
  last_error TEXT,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- Indexes for queue operations
CREATE INDEX IF NOT EXISTS idx_queue_pending ON public.processing_queue(status, priority DESC, created_at ASC) 
  WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_queue_tenant ON public.processing_queue(tenant_id);
CREATE INDEX IF NOT EXISTS idx_queue_document ON public.processing_queue(document_id);
CREATE INDEX IF NOT EXISTS idx_queue_status ON public.processing_queue(tenant_id, status);

-- Enable RLS immediately (no access without policies)
ALTER TABLE public.processing_queue ENABLE ROW LEVEL SECURITY;

-- Grant permissions
GRANT SELECT ON public.processing_queue TO authenticated;
GRANT SELECT ON public.processing_queue TO anon;

-- RLS Policies

-- Policy: Users can SELECT processing queue items for their own tenant only
CREATE POLICY "Users view own tenant queue" 
ON public.processing_queue 
FOR SELECT
USING (tenant_id = public.tenant_id());

-- Policy: Service role has full access (INSERT/UPDATE/DELETE)
-- Regular users cannot insert/update queue items directly
CREATE POLICY "Service role manages queue" 
ON public.processing_queue 
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
GRANT SELECT, INSERT, UPDATE, DELETE ON public.processing_queue TO service_role;
