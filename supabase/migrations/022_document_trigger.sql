-- Ingestion plane: Document processing trigger
-- Automatically enqueues documents for processing after insert
-- Uses SECURITY DEFINER to bypass RLS when inserting into processing_queue

CREATE OR REPLACE FUNCTION public.enqueue_document_processing()
RETURNS TRIGGER 
LANGUAGE plpgsql 
SECURITY DEFINER
AS $$
BEGIN
  INSERT INTO public.processing_queue (tenant_id, document_id)
  VALUES (NEW.tenant_id, NEW.id);
  RETURN NEW;
END;
$$;

-- Grant execute to authenticated users and service_role
GRANT EXECUTE ON FUNCTION public.enqueue_document_processing() TO authenticated;
GRANT EXECUTE ON FUNCTION public.enqueue_document_processing() TO anon;
GRANT EXECUTE ON FUNCTION public.enqueue_document_processing() TO service_role;

-- Create trigger to automatically enqueue documents
DROP TRIGGER IF EXISTS after_document_insert ON public.documents;

CREATE TRIGGER after_document_insert
  AFTER INSERT ON public.documents
  FOR EACH ROW 
  EXECUTE FUNCTION public.enqueue_document_processing();
