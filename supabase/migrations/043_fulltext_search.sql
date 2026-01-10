ALTER TABLE document_chunks
  ADD COLUMN fts tsvector
    GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;

CREATE INDEX IF NOT EXISTS idx_chunks_fts ON document_chunks USING GIN (fts);

CREATE OR REPLACE FUNCTION search_chunks_keyword(
  query_text TEXT,
  match_count INT DEFAULT 20
)
RETURNS TABLE (
  id UUID,
  document_id UUID,
  content TEXT,
  page_numbers INT[],
  rank FLOAT
) 
LANGUAGE plpgsql 
SECURITY DEFINER
STABLE
AS $$
DECLARE
  caller_tenant_id UUID;
BEGIN
  -- SECURITY: Enforce tenant isolation - caller can only query their own tenant
  -- Extract tenant_id from JWT token (cannot be overridden by callers)
  -- Returns default UUID (00000000-0000-0000-0000-000000000000) if no tenant in JWT
  -- This ensures absolute tenant isolation per .cursorrules requirement
  caller_tenant_id := public.tenant_id();
  
  -- Use caller's tenant_id from JWT (never trust parameters for tenant isolation)
  -- If caller_tenant_id is default UUID (no tenant in JWT), query returns no results
  RETURN QUERY
  SELECT
    dc.id,
    dc.document_id,
    dc.content,
    dc.page_numbers,
    ts_rank(dc.fts, websearch_to_tsquery('english', query_text)) as rank
  FROM document_chunks dc
  WHERE dc.tenant_id = caller_tenant_id
    AND dc.fts @@ websearch_to_tsquery('english', query_text)
  ORDER BY rank DESC
  LIMIT match_count;
END;
$$;

-- Grant execute to authenticated users
GRANT EXECUTE ON FUNCTION search_chunks_keyword(TEXT, INT) TO authenticated;
GRANT EXECUTE ON FUNCTION search_chunks_keyword(TEXT, INT) TO anon;

-- Note:
-- - SECURITY DEFINER allows function to bypass RLS for internal queries
-- - STABLE indicates function doesn't modify data (allows query optimization)
-- - Tenant isolation: Always uses tenant_id from JWT token (public.tenant_id())
--   Never accepts tenant_id as parameter to prevent cross-tenant access
