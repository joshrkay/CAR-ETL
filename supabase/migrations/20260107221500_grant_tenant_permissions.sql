-- Grant permissions to service_role and anon roles for PostgREST
GRANT ALL ON public.tenants TO service_role;
GRANT ALL ON public.tenant_users TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.tenants TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.tenant_users TO service_role;
