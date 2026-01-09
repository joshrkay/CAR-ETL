-- Understanding plane: Vector similarity search function
-- Searches document chunks using cosine similarity on embeddings
-- Enforces tenant isolation and supports document filtering

CREATE OR REPLACE FUNCTION public.match_document_chunks(
  query_embedding vector(1536),
  match_count INT DEFAULT 10,
  filter_document_ids UUID[] DEFAULT NULL
)
RETURNS TABLE (
  id UUID,
  document_id UUID,
  content TEXT,
  page_numbers INT[],
  similarity FLOAT
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
    1 - (dc.embedding <=> query_embedding) as similarity
  FROM public.document_chunks dc
  WHERE dc.tenant_id = caller_tenant_id
    AND dc.embedding IS NOT NULL
    AND (filter_document_ids IS NULL OR dc.document_id = ANY(filter_document_ids))
  ORDER BY dc.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- Grant execute to authenticated users
GRANT EXECUTE ON FUNCTION public.match_document_chunks(vector(1536), INT, UUID[]) TO authenticated;
GRANT EXECUTE ON FUNCTION public.match_document_chunks(vector(1536), INT, UUID[]) TO anon;

-- Note:
-- - <=> operator computes cosine distance (0 = identical, 2 = opposite)
-- - similarity = 1 - distance (1 = identical, -1 = opposite)
-- - SECURITY DEFINER allows function to bypass RLS for internal queries
-- - STABLE indicates function doesn't modify data (allows query optimization)
-- - Tenant isolation: Always uses tenant_id from JWT token (public.tenant_id())
--   Never accepts tenant_id as parameter to prevent cross-tenant access