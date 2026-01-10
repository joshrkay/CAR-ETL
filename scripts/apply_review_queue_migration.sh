#!/bin/bash
# Script to apply review queue migration to etlai.xyz database

set -e

MIGRATION_FILE="supabase/migrations/060_review_queue.sql"
DATABASE_URL="${DATABASE_URL:-}"

echo "========================================"
echo "Review Queue Migration Application"
echo "========================================"
echo ""

# Check if migration file exists
if [ ! -f "$MIGRATION_FILE" ]; then
    echo "ERROR: Migration file not found: $MIGRATION_FILE"
    exit 1
fi

echo "✓ Migration file found: $MIGRATION_FILE"
echo ""

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "ERROR: DATABASE_URL environment variable is not set"
    echo ""
    echo "Set DATABASE_URL using one of these methods:"
    echo ""
    echo "  1. From Supabase Dashboard:"
    echo "     Go to: Settings → Database → Connection String"
    echo "     Copy the connection string and export it:"
    echo "     export DATABASE_URL='postgresql://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres'"
    echo ""
    echo "  2. For etlai.xyz:"
    echo "     export DATABASE_URL='postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres'"
    echo ""
    exit 1
fi

echo "✓ DATABASE_URL is set"
echo ""

# Test connection
echo "Testing database connection..."
if ! psql "$DATABASE_URL" -c "SELECT 1;" > /dev/null 2>&1; then
    echo "ERROR: Failed to connect to database"
    echo "Please verify your DATABASE_URL is correct"
    exit 1
fi

echo "✓ Database connection successful"
echo ""

# Apply migration
echo "Applying migration..."
echo "--------------------------------------"

if psql "$DATABASE_URL" -f "$MIGRATION_FILE"; then
    echo ""
    echo "========================================"
    echo "✓ Migration applied successfully!"
    echo "========================================"
    echo ""
    echo "The review queue system is now active:"
    echo "  - review_queue table created with RLS policies"
    echo "  - Priority calculation functions deployed"
    echo "  - Auto-population trigger enabled"
    echo "  - Stale claim release mechanism active"
    echo ""
    echo "Verify the migration:"
    echo "  psql \"\$DATABASE_URL\" -c '\\dt review_queue'"
    echo ""
else
    echo ""
    echo "========================================"
    echo "✗ Migration failed"
    echo "========================================"
    echo ""
    echo "Please check the error messages above."
    echo "You can also apply the migration manually:"
    echo "  1. Go to Supabase Dashboard → SQL Editor"
    echo "  2. Copy the contents of: $MIGRATION_FILE"
    echo "  3. Paste and click 'Run'"
    echo ""
    exit 1
fi
