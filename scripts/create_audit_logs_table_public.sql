-- Create immutable audit_logs table in PUBLIC schema (for Supabase REST API access)
-- Run this in Supabase SQL Editor
-- This version creates the table in 'public' schema so Supabase REST API can access it

-- Create audit_logs table in public schema
CREATE TABLE IF NOT EXISTS public.audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    tenant_id VARCHAR(255) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    action_type VARCHAR(100) NOT NULL,
    resource_id VARCHAR(255),
    request_metadata JSONB NOT NULL DEFAULT '{}',
    retention_until TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for query performance
CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_id ON public.audit_logs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON public.audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action_type ON public.audit_logs(action_type);
CREATE INDEX IF NOT EXISTS idx_audit_logs_retention_until ON public.audit_logs(retention_until);
CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_timestamp ON public.audit_logs(tenant_id, timestamp);

-- Create function to prevent updates (WORM enforcement)
CREATE OR REPLACE FUNCTION public.prevent_audit_log_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Audit logs are immutable. Updates and deletes are not allowed.'
        USING ERRCODE = 'P0001';
END;
$$ LANGUAGE plpgsql;

-- Create trigger to prevent updates
DROP TRIGGER IF EXISTS prevent_audit_log_update ON public.audit_logs;
CREATE TRIGGER prevent_audit_log_update
BEFORE UPDATE ON public.audit_logs
FOR EACH ROW
EXECUTE FUNCTION public.prevent_audit_log_modification();

-- Create trigger to prevent deletes
DROP TRIGGER IF EXISTS prevent_audit_log_delete ON public.audit_logs;
CREATE TRIGGER prevent_audit_log_delete
BEFORE DELETE ON public.audit_logs
FOR EACH ROW
EXECUTE FUNCTION public.prevent_audit_log_modification();

-- Enable Row Level Security (RLS)
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS audit_logs_insert_only ON public.audit_logs;
DROP POLICY IF EXISTS audit_logs_select ON public.audit_logs;
DROP POLICY IF EXISTS audit_logs_no_update ON public.audit_logs;
DROP POLICY IF EXISTS audit_logs_no_delete ON public.audit_logs;

-- Create RLS policy: allow inserts only (no updates/deletes)
CREATE POLICY audit_logs_insert_only
ON public.audit_logs
FOR INSERT
TO authenticated
WITH CHECK (true);

-- Create RLS policy: allow selects (for reading audit logs)
CREATE POLICY audit_logs_select
ON public.audit_logs
FOR SELECT
TO authenticated
USING (true);

-- Explicitly deny updates and deletes via RLS
CREATE POLICY audit_logs_no_update
ON public.audit_logs
FOR UPDATE
TO authenticated
USING (false);

CREATE POLICY audit_logs_no_delete
ON public.audit_logs
FOR DELETE
TO authenticated
USING (false);

-- Verify table was created
SELECT 'audit_logs table created successfully in public schema' AS status;
