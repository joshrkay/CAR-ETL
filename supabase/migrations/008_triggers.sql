-- Control plane: Auto-update triggers
-- Automatically update updated_at timestamp

-- Function to update updated_at column
CREATE OR REPLACE FUNCTION public.update_updated_at()
RETURNS TRIGGER 
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

-- Trigger for tenants table
CREATE TRIGGER tenants_updated
  BEFORE UPDATE ON public.tenants
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at();

-- Note: tenant_users doesn't have updated_at, so no trigger needed
