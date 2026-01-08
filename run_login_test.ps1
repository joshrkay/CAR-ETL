# PowerShell script to run login test with environment variables
# Usage: .\run_login_test.ps1
#
# SECURITY: Credentials must be loaded from .env file
# DO NOT hardcode credentials in this file

Write-Host "Setting up environment variables for login test..." -ForegroundColor Cyan

# Try to load from .env file first
$projectRoot = $PSScriptRoot
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
    Write-Host "ERROR: .env file not found at $envFile" -ForegroundColor Red
    Write-Host "" -ForegroundColor Red
    Write-Host "SECURITY REQUIREMENT: Credentials must be stored in .env file" -ForegroundColor Yellow
    Write-Host "Create a .env file in the project root with:" -ForegroundColor Yellow
    Write-Host "  SUPABASE_URL=your_supabase_url" -ForegroundColor Yellow
    Write-Host "  SUPABASE_ANON_KEY=your_anon_key" -ForegroundColor Yellow
    Write-Host "  SUPABASE_SERVICE_KEY=your_service_key" -ForegroundColor Yellow
    Write-Host "  SUPABASE_JWT_SECRET=your_jwt_secret" -ForegroundColor Yellow
    Write-Host "" -ForegroundColor Yellow
    Write-Host "NEVER commit credentials to version control!" -ForegroundColor Red
    exit 1
}

# Verify required environment variables are set
$requiredVars = @("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_KEY", "SUPABASE_JWT_SECRET")
$missingVars = @()

foreach ($var in $requiredVars) {
    if (-not [Environment]::GetEnvironmentVariable($var, "Process")) {
        $missingVars += $var
    }
}

if ($missingVars.Count -gt 0) {
    Write-Host "ERROR: Missing required environment variables:" -ForegroundColor Red
    foreach ($var in $missingVars) {
        Write-Host "  - $var" -ForegroundColor Red
    }
    Write-Host "" -ForegroundColor Yellow
    Write-Host "Add these variables to your .env file" -ForegroundColor Yellow
    exit 1
}

Write-Host "Running login flow test..." -ForegroundColor Green
python tests/test_real_login.py
