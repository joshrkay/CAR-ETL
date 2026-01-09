-- Understanding plane: Extraction tables table
-- Stores tabular data extracted from documents (e.g., rent rolls, financial statements)
-- Maintains structure with headers and rows as JSONB

CREATE TABLE IF NOT EXISTS public.extraction_tables (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  extraction_id UUID NOT NULL REFERENCES public.extractions(id) ON DELETE CASCADE,
  table_name TEXT,
  headers JSONB NOT NULL,
  rows JSONB NOT NULL,
  page_number INT,
  confidence FLOAT CHECK (confidence BETWEEN 0 AND 1),
  created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_tables_extraction ON public.extraction_tables(extraction_id);
CREATE INDEX IF NOT EXISTS idx_tables_page ON public.extraction_tables(extraction_id, page_number) 
  WHERE page_number IS NOT NULL;

-- Enable RLS immediately (no access without policies)
ALTER TABLE public.extraction_tables ENABLE ROW LEVEL SECURITY;

-- Grant permissions
GRANT SELECT, INSERT, UPDATE ON public.extraction_tables TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.extraction_tables TO anon;

-- RLS Policies
-- Note: Access is controlled through parent extraction's tenant_id

-- Policy: Users can SELECT tables for extractions in their own tenant only
CREATE POLICY "Users view own tenant extraction tables" 
ON public.extraction_tables 
FOR SELECT
USING (
  EXISTS (
    SELECT 1 FROM public.extractions e
    WHERE e.id = extraction_tables.extraction_id
      AND e.tenant_id = public.tenant_id()
  )
);

-- Policy: Users can INSERT tables for extractions in their own tenant only
CREATE POLICY "Users insert own tenant extraction tables" 
ON public.extraction_tables 
FOR INSERT
WITH CHECK (
  EXISTS (
    SELECT 1 FROM public.extractions e
    WHERE e.id = extraction_tables.extraction_id
      AND e.tenant_id = public.tenant_id()
  )
);

-- Policy: Users can UPDATE tables for extractions in their own tenant only
CREATE POLICY "Users update own tenant extraction tables" 
ON public.extraction_tables 
FOR UPDATE
USING (
  EXISTS (
    SELECT 1 FROM public.extractions e
    WHERE e.id = extraction_tables.extraction_id
      AND e.tenant_id = public.tenant_id()
  )
)
WITH CHECK (
  EXISTS (
    SELECT 1 FROM public.extractions e
    WHERE e.id = extraction_tables.extraction_id
      AND e.tenant_id = public.tenant_id()
  )
);

-- Policy: Service role has full access
CREATE POLICY "Service role manages extraction tables" 
ON public.extraction_tables 
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
GRANT SELECT, INSERT, UPDATE, DELETE ON public.extraction_tables TO service_role;
