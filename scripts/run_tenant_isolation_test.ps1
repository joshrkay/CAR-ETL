# PowerShell script to run tenant isolation test
# Usage: .\scripts\run_tenant_isolation_test.ps1

Write-Host "Setting up environment variables for tenant isolation test..." -ForegroundColor Cyan

# Try to load from .env file first
$projectRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $projectRoot ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            $varName = $matches[1].Trim()
            $varValue = $matches[2].Trim()
            # Remove quotes if present
            $varValue = $varValue -replace '^["'']|["'']$', ''
            [Environment]::SetEnvironmentVariable($varName, $varValue, "Process")
        }
    }
    Write-Host "Loaded environment variables from .env" -ForegroundColor Green
} else {
    # Fallback: Set your Supabase credentials here (or load from .env file)
    # These are example values - replace with your actual Supabase credentials
    if (-not $env:SUPABASE_URL) {
        Write-Host "WARNING: .env file not found and SUPABASE_URL not set." -ForegroundColor Yellow
        Write-Host "Please set SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY, and SUPABASE_JWT_SECRET" -ForegroundColor Yellow
        Write-Host "You can either:" -ForegroundColor Yellow
        Write-Host "  1. Create a .env file in the project root" -ForegroundColor Yellow
        Write-Host "  2. Set environment variables in this script" -ForegroundColor Yellow
        exit 1
    }
}

Write-Host "Running tenant isolation test..." -ForegroundColor Green
python scripts/test_tenant_isolation.py
