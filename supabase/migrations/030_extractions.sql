-- Understanding plane: Extractions table
-- Tracks document extraction results with versioning support
-- Enforces tenant isolation and maintains extraction history

CREATE TABLE IF NOT EXISTS public.extractions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  document_id UUID NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
  version INT NOT NULL DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'processing'
    CHECK (status IN ('processing', 'completed', 'failed')),
  overall_confidence FLOAT CHECK (overall_confidence BETWEEN 0 AND 1),
  document_type TEXT,  -- lease, rent_roll, financial_statement
  parser_used TEXT,    -- ragflow, unstructured, tika
  is_current BOOLEAN DEFAULT true,
  error_message TEXT,
  extracted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
  UNIQUE(document_id, version)
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_extractions_document ON public.extractions(document_id);
CREATE INDEX IF NOT EXISTS idx_extractions_current ON public.extractions(document_id, is_current) 
  WHERE is_current = true;
CREATE INDEX IF NOT EXISTS idx_extractions_tenant ON public.extractions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_extractions_status ON public.extractions(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_extractions_document_type ON public.extractions(tenant_id, document_type) 
  WHERE document_type IS NOT NULL;

-- Enable RLS immediately (no access without policies)
ALTER TABLE public.extractions ENABLE ROW LEVEL SECURITY;

-- Grant permissions
GRANT SELECT, INSERT, UPDATE ON public.extractions TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.extractions TO anon;

-- RLS Policies

-- Policy: Users can SELECT extractions for their own tenant only
CREATE POLICY "Users view own tenant extractions" 
ON public.extractions 
FOR SELECT
USING (tenant_id = public.tenant_id());

-- Policy: Users can INSERT extractions for their own tenant only
CREATE POLICY "Users insert own tenant extractions" 
ON public.extractions 
FOR INSERT
WITH CHECK (tenant_id = public.tenant_id());

-- Policy: Users can UPDATE extractions for their own tenant only
CREATE POLICY "Users update own tenant extractions" 
ON public.extractions 
FOR UPDATE
USING (tenant_id = public.tenant_id())
WITH CHECK (tenant_id = public.tenant_id());

-- Policy: Service role has full access
CREATE POLICY "Service role manages extractions" 
ON public.extractions 
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
GRANT SELECT, INSERT, UPDATE, DELETE ON public.extractions TO service_role;

-- Version management function
-- Automatically sets previous extraction is_current=false when new extraction is created
CREATE OR REPLACE FUNCTION public.manage_extraction_version()
RETURNS TRIGGER 
LANGUAGE plpgsql 
SECURITY DEFINER
AS $$
DECLARE
  max_version INT;
BEGIN
  -- If this is a new extraction (not an update), manage versioning
  IF TG_OP = 'INSERT' THEN
    -- Get the maximum version for this document
    SELECT COALESCE(MAX(version), 0) INTO max_version
    FROM public.extractions
    WHERE document_id = NEW.document_id AND tenant_id = NEW.tenant_id;
    
    -- Set version to max + 1
    NEW.version := max_version + 1;
    
    -- Set all previous extractions for this document to is_current=false
    UPDATE public.extractions
    SET is_current = false
    WHERE document_id = NEW.document_id 
      AND tenant_id = NEW.tenant_id
      AND id != NEW.id
      AND is_current = true;
  END IF;
  
  RETURN NEW;
END;
$$;

-- Grant execute to authenticated users and service_role
GRANT EXECUTE ON FUNCTION public.manage_extraction_version() TO authenticated;
GRANT EXECUTE ON FUNCTION public.manage_extraction_version() TO anon;
GRANT EXECUTE ON FUNCTION public.manage_extraction_version() TO service_role;

-- Create trigger to automatically manage versioning
DROP TRIGGER IF EXISTS before_extraction_insert ON public.extractions;

CREATE TRIGGER before_extraction_insert
  BEFORE INSERT ON public.extractions
  FOR EACH ROW 
  EXECUTE FUNCTION public.manage_extraction_version();
