-- Fix service role policy for audit_logs table
-- Problem: Service role needs to read audit logs for admin/reporting, but RLS blocks it
-- Solution: Grant SELECT to service_role and create permissive policy
-- Note: Audit logs remain immutable (no UPDATE/DELETE even for service_role)

-- Grant SELECT and INSERT to service_role (for system-generated audit events)
-- Do NOT grant UPDATE or DELETE to maintain immutability
GRANT SELECT, INSERT ON public.audit_logs TO service_role;

-- Create policy for service role to read all audit logs (for admin/reporting)
-- Service role can read across all tenants for compliance/audit purposes
CREATE POLICY "Service role reads audit logs" 
ON public.audit_logs 
FOR SELECT
USING (
  auth.role() = 'service_role' OR
  auth.uid() IS NULL OR
  (current_setting('request.jwt.claims', true)::jsonb ->> 'role') = 'service_role' OR
  current_setting('request.jwt.claims', true) IS NULL
);

-- Service role can insert audit logs (for system events)
-- This allows service role to create audit entries for automated processes
CREATE POLICY "Service role inserts audit logs" 
ON public.audit_logs 
FOR INSERT
WITH CHECK (
  auth.role() = 'service_role' OR
  auth.uid() IS NULL OR
  (current_setting('request.jwt.claims', true)::jsonb ->> 'role') = 'service_role' OR
  current_setting('request.jwt.claims', true) IS NULL
);

-- No UPDATE or DELETE policies for service_role = immutable audit trail
-- Even service role cannot modify or delete audit logs once created
