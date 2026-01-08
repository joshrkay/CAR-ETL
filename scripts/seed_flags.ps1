# PowerShell script to seed feature flags
# Run this script to create test feature flags in the database

Write-Host "Seeding Feature Flags..." -ForegroundColor Cyan

# Set environment variables if .env file exists
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^([^#][^=]+)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

# Run the Python script
python scripts/seed_feature_flags.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "`nERROR: Failed to seed feature flags" -ForegroundColor Red
    exit 1
}

Write-Host "`nFeature flags seeded successfully!" -ForegroundColor Green
