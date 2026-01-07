-- SQL script to create the control_plane database
-- Run this with: psql -U postgres -f scripts/create_database.sql

-- Create database if it doesn't exist
-- Note: PostgreSQL doesn't support IF NOT EXISTS for CREATE DATABASE
-- So we'll check and create manually, or use the Python script

-- Connect to postgres database first, then run:
CREATE DATABASE control_plane;

-- Optional: Set default encoding and locale
-- CREATE DATABASE control_plane
--   WITH ENCODING 'UTF8'
--   LC_COLLATE='en_US.UTF-8'
--   LC_CTYPE='en_US.UTF-8'
--   TEMPLATE=template0;

-- Grant permissions (adjust user as needed)
-- GRANT ALL PRIVILEGES ON DATABASE control_plane TO your_user;

-- Verify database was created
-- \l control_plane
