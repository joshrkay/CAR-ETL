-- Control plane: Performance indexes
-- Optimize queries for tenant isolation

-- Tenants table indexes
CREATE INDEX IF NOT EXISTS idx_tenants_slug 
ON public.tenants(slug);

CREATE INDEX IF NOT EXISTS idx_tenants_status 
ON public.tenants(status);

CREATE INDEX IF NOT EXISTS idx_tenants_environment 
ON public.tenants(environment);

-- Tenant users table indexes
CREATE INDEX IF NOT EXISTS idx_tenant_users_user 
ON public.tenant_users(user_id);

CREATE INDEX IF NOT EXISTS idx_tenant_users_tenant 
ON public.tenant_users(tenant_id);

-- Composite index for common query pattern
CREATE INDEX IF NOT EXISTS idx_tenant_users_tenant_user 
ON public.tenant_users(tenant_id, user_id);

-- Index for role lookups
CREATE INDEX IF NOT EXISTS idx_tenant_users_roles 
ON public.tenant_users USING GIN(roles);
