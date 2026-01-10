-- Data plane: Entity relationships table
-- Captures graph relationships between entities
-- Enforces tenant isolation

CREATE TABLE IF NOT EXISTS public.entity_relationships (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  from_entity_id UUID NOT NULL,
  to_entity_id UUID NOT NULL,
  relationship_type TEXT NOT NULL,
  attributes JSONB DEFAULT '{}',
  start_date DATE,
  end_date DATE,
  source_document_id UUID REFERENCES public.documents(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
  -- Composite foreign keys to enforce tenant isolation
  -- Ensures from_entity belongs to the same tenant as the relationship
  CONSTRAINT fk_from_entity_tenant 
    FOREIGN KEY (from_entity_id, tenant_id) 
    REFERENCES public.entities(id, tenant_id) 
    ON DELETE CASCADE,
  -- Ensures to_entity belongs to the same tenant as the relationship
  CONSTRAINT fk_to_entity_tenant 
    FOREIGN KEY (to_entity_id, tenant_id) 
    REFERENCES public.entities(id, tenant_id) 
    ON DELETE CASCADE
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_entity_relationships_tenant ON public.entity_relationships(tenant_id);
CREATE INDEX IF NOT EXISTS idx_entity_relationships_from ON public.entity_relationships(from_entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_relationships_to ON public.entity_relationships(to_entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_relationships_type ON public.entity_relationships(tenant_id, relationship_type);

-- Enable RLS immediately (no access without policies)
ALTER TABLE public.entity_relationships ENABLE ROW LEVEL SECURITY;

-- Grant permissions
GRANT SELECT, INSERT, UPDATE ON public.entity_relationships TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.entity_relationships TO anon;

-- RLS Policies

-- Policy: Users can SELECT relationships for their own tenant only
CREATE POLICY "Users view own tenant relationships" 
ON public.entity_relationships 
FOR SELECT
USING (tenant_id = public.tenant_id());

-- Policy: Users can INSERT relationships for their own tenant only
CREATE POLICY "Users insert own tenant relationships" 
ON public.entity_relationships 
FOR INSERT
WITH CHECK (tenant_id = public.tenant_id());

-- Policy: Users can UPDATE relationships for their own tenant only
CREATE POLICY "Users update own tenant relationships" 
ON public.entity_relationships 
FOR UPDATE
USING (tenant_id = public.tenant_id())
WITH CHECK (tenant_id = public.tenant_id());

-- Policy: Service role has full access
CREATE POLICY "Service role manages relationships" 
ON public.entity_relationships 
FOR ALL
USING (
  auth.role() = 'service_role' OR
  (current_setting('request.jwt.claims', true)::jsonb ->> 'role') = 'service_role'
)
WITH CHECK (
  auth.role() = 'service_role' OR
  (current_setting('request.jwt.claims', true)::jsonb ->> 'role') = 'service_role'
);

-- Grant direct permissions to service_role
GRANT SELECT, INSERT, UPDATE, DELETE ON public.entity_relationships TO service_role;
