ALTER TABLE document_chunks
  ADD COLUMN IF NOT EXISTS fts tsvector
    GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;

CREATE INDEX IF NOT EXISTS idx_chunks_fts ON document_chunks USING GIN(fts);

CREATE OR REPLACE FUNCTION search_chunks_keyword(
  query_text TEXT,
  filter_tenant_id UUID DEFAULT auth.tenant_id(),
  match_count INT DEFAULT 20
)
RETURNS TABLE (
  id UUID,
  document_id UUID,
  content TEXT,
  page_numbers INT[],
  rank FLOAT
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    dc.id,
    dc.document_id,
    dc.content,
    dc.page_numbers,
    ts_rank(dc.fts, websearch_to_tsquery('english', query_text)) as rank
  FROM document_chunks dc
  WHERE dc.tenant_id = filter_tenant_id
    AND dc.fts @@ websearch_to_tsquery('english', query_text)
  ORDER BY rank DESC
  LIMIT match_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
