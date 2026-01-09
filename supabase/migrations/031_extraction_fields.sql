-- Understanding plane: Extraction fields table
-- Stores key-value pairs extracted from documents
-- Supports manual overrides with audit trail

CREATE TABLE IF NOT EXISTS public.extraction_fields (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  extraction_id UUID NOT NULL REFERENCES public.extractions(id) ON DELETE CASCADE,
  field_name TEXT NOT NULL,
  field_value JSONB NOT NULL,
  raw_value TEXT,
  confidence FLOAT NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  source TEXT NOT NULL CHECK (source IN ('parser', 'llm', 'rule')),
  page_number INT,
  bounding_box JSONB,  -- {x, y, width, height} as percentages
  is_override BOOLEAN DEFAULT false,
  overridden_by UUID REFERENCES auth.users(id),
  overridden_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_fields_extraction ON public.extraction_fields(extraction_id);
CREATE INDEX IF NOT EXISTS idx_fields_name ON public.extraction_fields(extraction_id, field_name);
CREATE INDEX IF NOT EXISTS idx_fields_override ON public.extraction_fields(extraction_id, is_override) 
  WHERE is_override = true;

-- Enable RLS immediately (no access without policies)
ALTER TABLE public.extraction_fields ENABLE ROW LEVEL SECURITY;

-- Grant permissions
GRANT SELECT, INSERT, UPDATE ON public.extraction_fields TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.extraction_fields TO anon;

-- RLS Policies
-- Note: Access is controlled through parent extraction's tenant_id

-- Policy: Users can SELECT fields for extractions in their own tenant only
CREATE POLICY "Users view own tenant extraction fields" 
ON public.extraction_fields 
FOR SELECT
USING (
  EXISTS (
    SELECT 1 FROM public.extractions e
    WHERE e.id = extraction_fields.extraction_id
      AND e.tenant_id = public.tenant_id()
  )
);

-- Policy: Users can INSERT fields for extractions in their own tenant only
CREATE POLICY "Users insert own tenant extraction fields" 
ON public.extraction_fields 
FOR INSERT
WITH CHECK (
  EXISTS (
    SELECT 1 FROM public.extractions e
    WHERE e.id = extraction_fields.extraction_id
      AND e.tenant_id = public.tenant_id()
  )
);

-- Policy: Users can UPDATE fields for extractions in their own tenant only
CREATE POLICY "Users update own tenant extraction fields" 
ON public.extraction_fields 
FOR UPDATE
USING (
  EXISTS (
    SELECT 1 FROM public.extractions e
    WHERE e.id = extraction_fields.extraction_id
      AND e.tenant_id = public.tenant_id()
  )
)
WITH CHECK (
  EXISTS (
    SELECT 1 FROM public.extractions e
    WHERE e.id = extraction_fields.extraction_id
      AND e.tenant_id = public.tenant_id()
  )
);

-- Policy: Service role has full access
CREATE POLICY "Service role manages extraction fields" 
ON public.extraction_fields 
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
GRANT SELECT, INSERT, UPDATE, DELETE ON public.extraction_fields TO service_role;
