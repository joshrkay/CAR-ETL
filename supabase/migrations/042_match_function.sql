-- Understanding plane: Vector similarity search function
-- Searches document chunks using cosine similarity on embeddings
-- Enforces tenant isolation and supports document filtering

CREATE OR REPLACE FUNCTION public.match_document_chunks(
  query_embedding vector(1536),
  match_count INT DEFAULT 10,
  filter_tenant_id UUID DEFAULT public.tenant_id(),
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
BEGIN
  RETURN QUERY
  SELECT 
    dc.id,
    dc.document_id,
    dc.content,
    dc.page_numbers,
    1 - (dc.embedding <=> query_embedding) as similarity
  FROM public.document_chunks dc
  WHERE dc.tenant_id = filter_tenant_id
    AND dc.embedding IS NOT NULL
    AND (filter_document_ids IS NULL OR dc.document_id = ANY(filter_document_ids))
  ORDER BY dc.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- Grant execute to authenticated users
GRANT EXECUTE ON FUNCTION public.match_document_chunks(vector(1536), INT, UUID, UUID[]) TO authenticated;
GRANT EXECUTE ON FUNCTION public.match_document_chunks(vector(1536), INT, UUID, UUID[]) TO anon;

-- Note:
-- - <=> operator computes cosine distance (0 = identical, 2 = opposite)
-- - similarity = 1 - distance (1 = identical, -1 = opposite)
-- - SECURITY DEFINER allows function to bypass RLS for internal queries
-- - STABLE indicates function doesn't modify data (allows query optimization)
