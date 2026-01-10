-- Data plane: Entity duplicates tracking
-- Stores potential duplicate entity pairs for review and merge

CREATE TABLE IF NOT EXISTS public.entity_duplicates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  entity_id_1 UUID NOT NULL REFERENCES public.entities(id),
  entity_id_2 UUID NOT NULL REFERENCES public.entities(id),
  match_score FLOAT NOT NULL,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'merged', 'rejected')),
  reviewed_by UUID REFERENCES auth.users(id),
  reviewed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for query patterns
CREATE INDEX IF NOT EXISTS idx_entity_duplicates_tenant ON public.entity_duplicates(tenant_id);
CREATE INDEX IF NOT EXISTS idx_entity_duplicates_status ON public.entity_duplicates(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_entity_duplicates_entities ON public.entity_duplicates(entity_id_1, entity_id_2);

-- Enable RLS
ALTER TABLE public.entity_duplicates ENABLE ROW LEVEL SECURITY;

-- Policy: Users can SELECT duplicates for their own tenant
CREATE POLICY "Users view own tenant duplicates"
ON public.entity_duplicates
FOR SELECT
USING (tenant_id = public.tenant_id());

-- Policy: Users can INSERT duplicates for their own tenant
CREATE POLICY "Users insert own tenant duplicates"
ON public.entity_duplicates
FOR INSERT
WITH CHECK (tenant_id = public.tenant_id());

-- Policy: Users can UPDATE duplicates for their own tenant
CREATE POLICY "Users update own tenant duplicates"
ON public.entity_duplicates
FOR UPDATE
USING (tenant_id = public.tenant_id())
WITH CHECK (tenant_id = public.tenant_id());

-- Service role policy
CREATE POLICY "Service role manages entity duplicates"
ON public.entity_duplicates
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

GRANT SELECT, INSERT, UPDATE ON public.entity_duplicates TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.entity_duplicates TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.entity_duplicates TO service_role;
