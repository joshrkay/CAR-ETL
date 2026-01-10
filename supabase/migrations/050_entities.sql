-- Data plane: Entities table
-- Polymorphic entity registry with hierarchy support
-- Enforces tenant isolation

CREATE TABLE IF NOT EXISTS public.entities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  entity_type TEXT NOT NULL CHECK (entity_type IN (
    'portfolio', 'asset', 'tenant', 'landlord', 'lease'
  )),
  name TEXT NOT NULL,
  canonical_name TEXT NOT NULL,
  external_id TEXT,
  parent_id UUID REFERENCES public.entities(id) ON DELETE SET NULL,
  attributes JSONB NOT NULL DEFAULT '{}',
  source_document_id UUID REFERENCES public.documents(id) ON DELETE SET NULL,
  confidence FLOAT CHECK (confidence BETWEEN 0 AND 1),
  status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
  created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- Unique constraint for composite foreign key references (tenant isolation)
ALTER TABLE public.entities ADD CONSTRAINT entities_id_tenant_unique UNIQUE (id, tenant_id);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_entities_tenant_type ON public.entities(tenant_id, entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_canonical ON public.entities(tenant_id, canonical_name);
CREATE INDEX IF NOT EXISTS idx_entities_parent ON public.entities(parent_id) WHERE parent_id IS NOT NULL;

-- Enable RLS immediately (no access without policies)
ALTER TABLE public.entities ENABLE ROW LEVEL SECURITY;

-- Grant permissions
GRANT SELECT, INSERT, UPDATE ON public.entities TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.entities TO anon;

-- RLS Policies

-- Policy: Users can SELECT entities for their own tenant only
CREATE POLICY "Users view own tenant entities" 
ON public.entities 
FOR SELECT
USING (tenant_id = public.tenant_id());

-- Policy: Users can INSERT entities for their own tenant only
CREATE POLICY "Users insert own tenant entities" 
ON public.entities 
FOR INSERT
WITH CHECK (tenant_id = public.tenant_id());

-- Policy: Users can UPDATE entities for their own tenant only
CREATE POLICY "Users update own tenant entities" 
ON public.entities 
FOR UPDATE
USING (tenant_id = public.tenant_id())
WITH CHECK (tenant_id = public.tenant_id());

-- Policy: Service role has full access
CREATE POLICY "Service role manages entities" 
ON public.entities 
FOR ALL
TO service_role
USING (
  auth.role() = 'service_role' OR
  (current_setting('request.jwt.claims', true)::jsonb ->> 'role') = 'service_role'
)
WITH CHECK (
  auth.role() = 'service_role' OR
  (current_setting('request.jwt.claims', true)::jsonb ->> 'role') = 'service_role'
);

-- Grant direct permissions to service_role
GRANT SELECT, INSERT, UPDATE, DELETE ON public.entities TO service_role;
