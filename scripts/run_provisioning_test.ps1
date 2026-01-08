# PowerShell script to run tenant provisioning test
# Usage: .\scripts\run_provisioning_test.ps1

Write-Host "Setting up environment variables for tenant provisioning test..." -ForegroundColor Cyan

# Load environment variables from .env file if it exists
$envFile = Join-Path (Split-Path $MyInvocation.MyCommand.Definition) "..\.env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.*)\s*$') {
            $varName = $Matches[1]
            $varValue = $Matches[2]
            # Remove quotes if present
            if ($varValue -match '^"(.*)"$' -or $varValue -match "^'(.*)'$") {
                $varValue = $Matches[1]
            }
            Set-Item -Path "env:$varName" -Value $varValue
            Write-Host "  Set $varName" -ForegroundColor DarkCyan
        }
    }
} else {
    Write-Host "  .env file not found. Ensure environment variables are set manually." -ForegroundColor Yellow
}

Write-Host "Running tenant provisioning test..." -ForegroundColor Green
python scripts/test_tenant_provisioning.py
