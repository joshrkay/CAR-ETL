# PowerShell script to run RLS test with environment variables
# Usage: .\scripts\run_rls_test.ps1

Write-Host "Setting up environment variables for RLS test..." -ForegroundColor Cyan

# Set your Supabase credentials here (or load from .env file)
$env:SUPABASE_URL = "https://ueqzwqejpjmsspfiypgb.supabase.co"
$env:SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVlcXp3cWVqcGptc3NwZml5cGdiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njc4MTc2MDMsImV4cCI6MjA4MzM5MzYwM30.hMpWP-BVDmp4_A8neru-enes6nFa4Yj5qKUHE3ctWoA"
$env:SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVlcXp3cWVqcGptc3NwZml5cGdiIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NzgxNzYwMywiZXhwIjoyMDgzMzkzNjAzfQ.XiH3V3gP1cVe_-OyK2d-xwwWYVZc6qaNIrxw3BsU1Rw"
$env:SUPABASE_JWT_SECRET = "44138843-a9fe-49e0-a933-042dfe0c7d6f"

Write-Host "Running RLS test..." -ForegroundColor Green
python scripts/test_rls_via_api.py
