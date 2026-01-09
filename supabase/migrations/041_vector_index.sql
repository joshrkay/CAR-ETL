-- Understanding plane: HNSW index for vector similarity search
-- HNSW (Hierarchical Navigable Small World) index for fast approximate nearest neighbor search
-- Better than IVFFlat for small to medium datasets

-- HNSW index on embedding column using cosine distance
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON public.document_chunks 
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- Note: 
-- - m = 16: Controls the number of connections each node has (higher = more accurate but slower)
-- - ef_construction = 64: Controls index build time vs quality (higher = better quality, slower build)
-- - vector_cosine_ops: Operator class for cosine distance (1 - cosine similarity)
