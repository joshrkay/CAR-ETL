-- Understanding plane: Review Queue
-- Prioritized queue for extractions requiring human review
-- Enforces tenant isolation and implements claim mechanism with auto-release

-- Review Queue Table
CREATE TABLE IF NOT EXISTS public.review_queue (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  document_id UUID NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
  extraction_id UUID NOT NULL REFERENCES public.extractions(id) ON DELETE CASCADE,
  priority INT NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'claimed', 'completed', 'skipped')),
  claimed_by UUID REFERENCES auth.users(id),
  claimed_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
  UNIQUE(extraction_id)  -- One queue item per extraction
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_queue_tenant ON public.review_queue(tenant_id);
CREATE INDEX IF NOT EXISTS idx_queue_extraction ON public.review_queue(extraction_id);
CREATE INDEX IF NOT EXISTS idx_queue_document ON public.review_queue(document_id);

-- Critical index for queue listing (pending items sorted by priority)
CREATE INDEX IF NOT EXISTS idx_queue_pending ON public.review_queue(tenant_id, status, priority DESC)
  WHERE status = 'pending';

-- Index for claimed items (for auto-release)
CREATE INDEX IF NOT EXISTS idx_queue_claimed ON public.review_queue(status, claimed_at)
  WHERE status = 'claimed';

-- Enable RLS immediately (no access without policies)
ALTER TABLE public.review_queue ENABLE ROW LEVEL SECURITY;

-- Grant permissions
GRANT SELECT, INSERT, UPDATE ON public.review_queue TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.review_queue TO anon;

-- RLS Policies

-- Policy: Users can SELECT queue items for their own tenant only
CREATE POLICY "Users view own tenant review queue"
ON public.review_queue
FOR SELECT
USING (tenant_id = public.tenant_id());

-- Policy: Users can INSERT queue items for their own tenant only
CREATE POLICY "Users insert own tenant review queue"
ON public.review_queue
FOR INSERT
WITH CHECK (tenant_id = public.tenant_id());

-- Policy: Users can UPDATE queue items for their own tenant only
CREATE POLICY "Users update own tenant review queue"
ON public.review_queue
FOR UPDATE
USING (tenant_id = public.tenant_id())
WITH CHECK (tenant_id = public.tenant_id());

-- Policy: Service role has full access
CREATE POLICY "Service role manages review queue"
ON public.review_queue
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
GRANT SELECT, INSERT, UPDATE, DELETE ON public.review_queue TO service_role;

-- Function: Calculate priority score for extraction
CREATE OR REPLACE FUNCTION public.calculate_extraction_priority(
  p_extraction_id UUID
)
RETURNS INT
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_priority INT := 0;
  v_confidence FLOAT;
  v_age_hours FLOAT;
  v_critical_field_count INT := 0;
BEGIN
  -- Get extraction overall confidence and age
  SELECT
    COALESCE(overall_confidence, 0),
    EXTRACT(EPOCH FROM (now() - created_at)) / 3600.0
  INTO v_confidence, v_age_hours
  FROM public.extractions
  WHERE id = p_extraction_id;

  -- Lower confidence = higher priority (max 50 points)
  v_priority := v_priority + CAST((1 - v_confidence) * 50 AS INT);

  -- Check critical fields with low confidence (10 points each)
  SELECT COUNT(*)
  INTO v_critical_field_count
  FROM public.extraction_fields
  WHERE extraction_id = p_extraction_id
    AND field_name IN ('base_rent', 'lease_start_date', 'lease_end_date')
    AND confidence < 0.80;

  v_priority := v_priority + (v_critical_field_count * 10);

  -- Age bonus: older extractions get higher priority (max 20 points)
  v_priority := v_priority + LEAST(CAST(v_age_hours AS INT), 20);

  RETURN v_priority;
END;
$$;

-- Grant execute permissions
GRANT EXECUTE ON FUNCTION public.calculate_extraction_priority(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION public.calculate_extraction_priority(UUID) TO anon;
GRANT EXECUTE ON FUNCTION public.calculate_extraction_priority(UUID) TO service_role;

-- Function: Check if extraction should be in review queue
CREATE OR REPLACE FUNCTION public.should_queue_for_review(
  p_extraction_id UUID
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_overall_confidence FLOAT;
  v_parser_used TEXT;
  v_low_confidence_field_count INT;
BEGIN
  -- Get extraction metadata
  SELECT overall_confidence, parser_used
  INTO v_overall_confidence, v_parser_used
  FROM public.extractions
  WHERE id = p_extraction_id;

  -- Rule 1: Overall confidence < 0.85
  IF v_overall_confidence IS NOT NULL AND v_overall_confidence < 0.85 THEN
    RETURN TRUE;
  END IF;

  -- Rule 2: Parser fallback (tika is fallback parser)
  IF v_parser_used = 'tika' THEN
    RETURN TRUE;
  END IF;

  -- Rule 3: Has low confidence fields (any field < 0.70)
  SELECT COUNT(*)
  INTO v_low_confidence_field_count
  FROM public.extraction_fields
  WHERE extraction_id = p_extraction_id
    AND confidence < 0.70;

  IF v_low_confidence_field_count > 0 THEN
    RETURN TRUE;
  END IF;

  -- Rule 4: Entity resolution pending
  -- This would check a flag on the extraction or entities table
  -- For now, we'll skip this check as the schema doesn't have this flag yet

  RETURN FALSE;
END;
$$;

-- Grant execute permissions
GRANT EXECUTE ON FUNCTION public.should_queue_for_review(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION public.should_queue_for_review(UUID) TO anon;
GRANT EXECUTE ON FUNCTION public.should_queue_for_review(UUID) TO service_role;

-- Function: Auto-populate queue when extraction is created/updated
CREATE OR REPLACE FUNCTION public.populate_review_queue()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_should_queue BOOLEAN;
  v_priority INT;
BEGIN
  -- Only process completed extractions
  IF NEW.status != 'completed' THEN
    RETURN NEW;
  END IF;

  -- Check if extraction should be queued
  v_should_queue := public.should_queue_for_review(NEW.id);

  IF v_should_queue THEN
    -- Calculate priority
    v_priority := public.calculate_extraction_priority(NEW.id);

    -- Insert into queue (or update priority if already exists)
    INSERT INTO public.review_queue (
      tenant_id,
      document_id,
      extraction_id,
      priority,
      status
    )
    VALUES (
      NEW.tenant_id,
      NEW.document_id,
      NEW.id,
      v_priority,
      'pending'
    )
    ON CONFLICT (extraction_id) DO UPDATE
    SET priority = EXCLUDED.priority,
        status = CASE
          WHEN review_queue.status = 'completed' THEN review_queue.status
          ELSE 'pending'
        END;
  END IF;

  RETURN NEW;
END;
$$;

-- Grant execute permissions
GRANT EXECUTE ON FUNCTION public.populate_review_queue() TO authenticated;
GRANT EXECUTE ON FUNCTION public.populate_review_queue() TO anon;
GRANT EXECUTE ON FUNCTION public.populate_review_queue() TO service_role;

-- Trigger: Auto-populate queue on extraction insert/update
DROP TRIGGER IF EXISTS trigger_populate_review_queue ON public.extractions;

CREATE TRIGGER trigger_populate_review_queue
  AFTER INSERT OR UPDATE OF status, overall_confidence ON public.extractions
  FOR EACH ROW
  EXECUTE FUNCTION public.populate_review_queue();

-- Function: Auto-release stale claims (30 minute timeout)
CREATE OR REPLACE FUNCTION public.release_stale_claims()
RETURNS INT
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_released_count INT;
BEGIN
  -- Release claims older than 30 minutes
  WITH released AS (
    UPDATE public.review_queue
    SET
      status = 'pending',
      claimed_by = NULL,
      claimed_at = NULL
    WHERE status = 'claimed'
      AND claimed_at < (now() - INTERVAL '30 minutes')
    RETURNING id
  )
  SELECT COUNT(*) INTO v_released_count FROM released;

  RETURN v_released_count;
END;
$$;

-- Grant execute permissions
GRANT EXECUTE ON FUNCTION public.release_stale_claims() TO authenticated;
GRANT EXECUTE ON FUNCTION public.release_stale_claims() TO anon;
GRANT EXECUTE ON FUNCTION public.release_stale_claims() TO service_role;

-- Comment on table and functions
COMMENT ON TABLE public.review_queue IS
  'Prioritized queue for extractions requiring human review. Enforces tenant isolation and 30-minute claim timeout.';

COMMENT ON FUNCTION public.calculate_extraction_priority(UUID) IS
  'Calculates priority score for extraction based on confidence, critical fields, and age.';

COMMENT ON FUNCTION public.should_queue_for_review(UUID) IS
  'Determines if extraction should be added to review queue based on confidence and parser fallback rules.';

COMMENT ON FUNCTION public.populate_review_queue() IS
  'Trigger function that auto-populates review queue when extractions are created or updated.';

COMMENT ON FUNCTION public.release_stale_claims() IS
  'Releases queue items claimed for more than 30 minutes. Should be called periodically.';
