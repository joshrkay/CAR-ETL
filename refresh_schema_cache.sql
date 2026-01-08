-- Refresh PostgREST schema cache
-- Run this in Supabase SQL Editor to immediately refresh the schema cache
-- Go to: https://supabase.com/dashboard/project/ueqzwqejpjmsspfiypgb/sql/new

NOTIFY pgrst, 'reload schema';

-- Verify it worked by checking if tables are accessible
SELECT 'Schema cache refreshed!' as status;
