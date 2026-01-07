-- Mark Alembic migrations as applied (if you ran them manually)
-- Run this in Supabase SQL Editor AFTER running run_migrations_manually.sql
-- This tells Alembic that the migrations have already been applied

-- Create alembic_version table if it doesn't exist
CREATE TABLE IF NOT EXISTS control_plane.alembic_version (
    version_num VARCHAR(32) NOT NULL PRIMARY KEY
);

-- Mark migration 001 as applied (revision: 001_control_plane)
INSERT INTO control_plane.alembic_version (version_num)
VALUES ('001_control_plane')
ON CONFLICT (version_num) DO NOTHING;

-- Mark migration 002 as applied (revision: 002_seed_data)
INSERT INTO control_plane.alembic_version (version_num)
VALUES ('002_seed_data')
ON CONFLICT (version_num) DO NOTHING;

-- Verify
SELECT * FROM control_plane.alembic_version ORDER BY version_num;
