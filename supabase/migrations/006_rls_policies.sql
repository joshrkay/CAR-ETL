-- Control plane: Row-Level Security policies
-- Bulletproof tenant isolation - no cross-tenant access

-- ============================================================
-- TENANTS TABLE POLICIES
-- ============================================================

-- Users can only SELECT their own tenant
-- Must be a member of the tenant via tenant_users
CREATE POLICY "Users view own tenant" 
ON public.tenants 
FOR SELECT
USING (
  id IN (
    SELECT tenant_id 
    FROM public.tenant_users 
    WHERE user_id = auth.uid()
  )
);

-- Only service_role can INSERT/UPDATE/DELETE tenants
-- Regular users cannot create or modify tenants directly
CREATE POLICY "Service role manages tenants" 
ON public.tenants 
FOR ALL
USING (auth.role() = 'service_role')
WITH CHECK (auth.role() = 'service_role');

-- ============================================================
-- TENANT_USERS TABLE POLICIES
-- ============================================================

-- Users can SELECT tenant_users for their own tenant only
-- Uses public.tenant_id() helper to extract from JWT
CREATE POLICY "View tenant users" 
ON public.tenant_users 
FOR SELECT
USING (tenant_id = public.tenant_id());

-- Service role can manage all tenant_users
-- Note: Admin policy is created in 010_restructure_admin_policy.sql
-- to avoid RLS recursion issues
CREATE POLICY "Service role manages tenant_users" 
ON public.tenant_users 
FOR ALL
USING (auth.role() = 'service_role')
WITH CHECK (auth.role() = 'service_role');
