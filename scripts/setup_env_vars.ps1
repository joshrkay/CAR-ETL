# PowerShell script to set up Supabase environment variables
# Run this script to configure your environment

Write-Host "Setting up Supabase environment variables..." -ForegroundColor Green

# Supabase API Keys
$env:SUPABASE_URL = "https://qifioafprrtkoiyylsqa.supabase.co"
$env:SUPABASE_PROJECT_REF = "qifioafprrtkoiyylsqa"
$env:SUPABASE_ANON_KEY = "sb_publishable_PhKpWt7-UWeydaiqe99LDg_OSnuK7a0"
$env:SUPABASE_SERVICE_ROLE_KEY = "sb_secret_SDH3fH1Nl69oxRGNBPy91g_MhFHDYpm"

Write-Host "Supabase API keys configured" -ForegroundColor Green

# Database Connection
# NOTE: You still need to set DATABASE_URL with your PostgreSQL connection string
# Get it from: https://app.supabase.com/project/qifioafprrtkoiyylsqa/settings/database
Write-Host ""
Write-Host "WARNING: DATABASE_URL still needs to be set!" -ForegroundColor Yellow
Write-Host "Get your connection string from:" -ForegroundColor Yellow
Write-Host "https://app.supabase.com/project/qifioafprrtkoiyylsqa/settings/database" -ForegroundColor Cyan
Write-Host ""

# Verify environment variables
Write-Host "Current environment variables:" -ForegroundColor Green
Write-Host "SUPABASE_URL: $env:SUPABASE_URL" -ForegroundColor Gray
Write-Host "SUPABASE_ANON_KEY: $($env:SUPABASE_ANON_KEY.Substring(0, 20))..." -ForegroundColor Gray
Write-Host "SUPABASE_SERVICE_ROLE_KEY: $($env:SUPABASE_SERVICE_ROLE_KEY.Substring(0, 20))..." -ForegroundColor Gray

if ($env:DATABASE_URL) {
    Write-Host "DATABASE_URL: $($env:DATABASE_URL)" -ForegroundColor Green
} else {
    Write-Host "DATABASE_URL: not set" -ForegroundColor Red
}
