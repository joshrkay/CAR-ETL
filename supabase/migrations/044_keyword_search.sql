-- Understanding plane: Keyword search for document chunks
-- Adds full-text search capability using PostgreSQL FTS (tsvector/tsquery)
-- Works alongside vector search for hybrid search functionality

-- Add tsvector column for full-text search
ALTER TABLE public.document_chunks
ADD COLUMN IF NOT EXISTS content_tsv tsvector;

-- Create GIN index for fast full-text search
CREATE INDEX IF NOT EXISTS idx_chunks_content_tsv
ON public.document_chunks USING GIN(content_tsv);

-- Function to update tsvector column
CREATE OR REPLACE FUNCTION public.update_chunk_tsv()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  -- Generate tsvector from content using English dictionary
  -- Weight 'A' gives content highest importance
  NEW.content_tsv := setweight(to_tsvector('english', COALESCE(NEW.content, '')), 'A');

  -- Add section header with lower weight if present
  IF NEW.section_header IS NOT NULL THEN
    NEW.content_tsv := NEW.content_tsv ||
      setweight(to_tsvector('english', NEW.section_header), 'B');
  END IF;

  RETURN NEW;
END;
$$;

-- Trigger to automatically update tsvector on insert/update
DROP TRIGGER IF EXISTS trg_update_chunk_tsv ON public.document_chunks;
CREATE TRIGGER trg_update_chunk_tsv
  BEFORE INSERT OR UPDATE OF content, section_header
  ON public.document_chunks
  FOR EACH ROW
  EXECUTE FUNCTION public.update_chunk_tsv();

-- Backfill existing chunks (if any)
UPDATE public.document_chunks
SET content_tsv = setweight(to_tsvector('english', COALESCE(content, '')), 'A')
WHERE content_tsv IS NULL;

-- Keyword search function
-- Returns chunks ranked by text relevance (ts_rank)
CREATE OR REPLACE FUNCTION public.match_document_chunks_keyword(
  query_text TEXT,
  match_count INT DEFAULT 10,
  filter_document_ids UUID[] DEFAULT NULL
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
  search_query tsquery;
BEGIN
  -- SECURITY: Enforce tenant isolation - caller can only query their own tenant
  caller_tenant_id := public.tenant_id();

  -- Parse query text into tsquery
  -- Use plainto_tsquery for user-friendly query parsing (handles spaces, punctuation)
  search_query := plainto_tsquery('english', query_text);

  -- Return results ranked by text relevance
  RETURN QUERY
  SELECT
    dc.id,
    dc.document_id,
    dc.content,
    dc.page_numbers,
    ts_rank(dc.content_tsv, search_query) as rank
  FROM public.document_chunks dc
  WHERE dc.tenant_id = caller_tenant_id
    AND dc.content_tsv @@ search_query
    AND (filter_document_ids IS NULL OR dc.document_id = ANY(filter_document_ids))
  ORDER BY rank DESC
  LIMIT match_count;
END;
$$;

-- Grant execute permissions
GRANT EXECUTE ON FUNCTION public.match_document_chunks_keyword(TEXT, INT, UUID[]) TO authenticated;
GRANT EXECUTE ON FUNCTION public.match_document_chunks_keyword(TEXT, INT, UUID[]) TO anon;

-- Note:
-- - tsvector stores lexemes (normalized word forms) for efficient search
-- - GIN index provides O(log n) search performance
-- - ts_rank scores documents by relevance (higher = more relevant)
-- - plainto_tsquery converts plain text to tsquery (user-friendly)
-- - @@ operator performs full-text match
-- - Tenant isolation: Always uses tenant_id from JWT token
