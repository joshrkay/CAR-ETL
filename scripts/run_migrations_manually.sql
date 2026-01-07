-- Manual SQL Migration for Control Plane Schema
-- Run this in Supabase SQL Editor if Alembic connection fails
-- Copy and paste this entire file into Supabase SQL Editor and execute

-- Migration 001: Create control plane schema and tables

-- Create control_plane schema
CREATE SCHEMA IF NOT EXISTS control_plane;

-- Create enum types
DO $$ BEGIN
    CREATE TYPE control_plane.tenant_environment AS ENUM (
        'development',
        'staging',
        'production'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE control_plane.tenant_status AS ENUM (
        'active',
        'inactive',
        'suspended',
        'pending'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE control_plane.database_status AS ENUM (
        'active',
        'inactive',
        'migrating',
        'error'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create tenants table
CREATE TABLE IF NOT EXISTS control_plane.tenants (
    tenant_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    environment control_plane.tenant_environment NOT NULL,
    status control_plane.tenant_status NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes on tenants
CREATE INDEX IF NOT EXISTS idx_tenants_status ON control_plane.tenants(status);

-- Create tenant_databases table
CREATE TABLE IF NOT EXISTS control_plane.tenant_databases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES control_plane.tenants(tenant_id) ON DELETE CASCADE,
    connection_string_encrypted TEXT NOT NULL,
    database_name VARCHAR(255) NOT NULL,
    host VARCHAR(255) NOT NULL,
    port INTEGER NOT NULL DEFAULT 5432,
    status control_plane.database_status NOT NULL DEFAULT 'inactive',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes on tenant_databases
CREATE INDEX IF NOT EXISTS idx_tenant_databases_tenant_id ON control_plane.tenant_databases(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_databases_status ON control_plane.tenant_databases(status);

-- Create system_config table
CREATE TABLE IF NOT EXISTS control_plane.system_config (
    key VARCHAR(255) PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION control_plane.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
DROP TRIGGER IF EXISTS update_tenants_updated_at ON control_plane.tenants;
CREATE TRIGGER update_tenants_updated_at
    BEFORE UPDATE ON control_plane.tenants
    FOR EACH ROW
    EXECUTE FUNCTION control_plane.update_updated_at_column();

DROP TRIGGER IF EXISTS update_tenant_databases_updated_at ON control_plane.tenant_databases;
CREATE TRIGGER update_tenant_databases_updated_at
    BEFORE UPDATE ON control_plane.tenant_databases
    FOR EACH ROW
    EXECUTE FUNCTION control_plane.update_updated_at_column();

DROP TRIGGER IF EXISTS update_system_config_updated_at ON control_plane.system_config;
CREATE TRIGGER update_system_config_updated_at
    BEFORE UPDATE ON control_plane.system_config
    FOR EACH ROW
    EXECUTE FUNCTION control_plane.update_updated_at_column();

-- Migration 002: Seed system_admin tenant
INSERT INTO control_plane.tenants (tenant_id, name, environment, status, created_at, updated_at)
VALUES (
    gen_random_uuid(),
    'system_admin',
    'production',
    'active',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
)
ON CONFLICT (name) DO NOTHING;

-- Verify tables were created
SELECT 
    schemaname,
    tablename
FROM pg_tables
WHERE schemaname = 'control_plane'
ORDER BY tablename;
