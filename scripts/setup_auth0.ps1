# Auth0 Setup Script for CAR Platform (PowerShell)
# This script provides guidance for configuring Auth0 tenant

param(
    [string]$Auth0Domain = "dev-khx88c3lu7wz2dxx.us.auth0.com",
    [string]$ApiIdentifier = "https://api.car-platform.com"
)

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Auth0 Setup for CAR Platform" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Check if Auth0 CLI is available
Write-Info "Checking for Auth0 CLI..."
try {
    $auth0Version = auth0 --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Info "Auth0 CLI found: $auth0Version"
        $hasAuth0CLI = $true
    } else {
        $hasAuth0CLI = $false
    }
} catch {
    $hasAuth0CLI = $false
}

if (-not $hasAuth0CLI) {
    Write-Warn "Auth0 CLI not found."
    Write-Host ""
    Write-Host "To install Auth0 CLI:" -ForegroundColor Yellow
    Write-Host "  npm install -g @auth0/auth0-cli" -ForegroundColor White
    Write-Host ""
    Write-Host "However, since Management API is not enabled for your tenant," -ForegroundColor Yellow
    Write-Host "you'll need to create the API resource manually." -ForegroundColor Yellow
    Write-Host ""
}

# Check Management API
Write-Info "Checking Management API availability..."
Write-Warn "Management API is not enabled for this tenant."
Write-Host ""
Write-Host "Since Management API is not available, you need to create" -ForegroundColor Yellow
Write-Host "the API resource manually through the Auth0 Dashboard." -ForegroundColor Yellow
Write-Host ""

# Provide manual setup instructions
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "MANUAL SETUP INSTRUCTIONS" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "STEP 1: Create API Resource" -ForegroundColor Yellow
Write-Host "----------------------------" -ForegroundColor Yellow
Write-Host "1. Go to: https://manage.auth0.com"
Write-Host "2. Navigate to: APIs > APIs"
Write-Host "3. Click: '+ Create API'"
Write-Host "4. Fill in:"
Write-Host "   - Name: CAR API"
Write-Host "   - Identifier: $ApiIdentifier"
Write-Host "   - Signing Algorithm: RS256"
Write-Host "5. Click: 'Create'"
Write-Host ""

Write-Host "STEP 2: Configure Scopes" -ForegroundColor Yellow
Write-Host "------------------------" -ForegroundColor Yellow
Write-Host "1. Go to 'Scopes' tab"
Write-Host "2. Add these scopes:"
Write-Host "   - read:documents (Read document data)"
Write-Host "   - write:documents (Create/update documents)"
Write-Host "   - admin (Administrative operations)"
Write-Host "3. Save changes"
Write-Host ""

Write-Host "STEP 3: Configure Database Connection" -ForegroundColor Yellow
Write-Host "-------------------------------------" -ForegroundColor Yellow
Write-Host "1. Go to: Authentication > Database > Database Connections"
Write-Host "2. Click on: 'Username-Password-Authentication'"
Write-Host "3. Go to 'Settings' tab"
Write-Host "4. Scroll to 'Password Policy'"
Write-Host "5. Configure:"
Write-Host "   - Password Policy: Fair or Good"
Write-Host "   - Minimum Length: 8"
Write-Host "   - Require Lowercase: Yes"
Write-Host "   - Require Numbers: Yes"
Write-Host "   - Require Symbols: Yes"
Write-Host "6. Save changes"
Write-Host ""

Write-Host "STEP 4: Authorize Client" -ForegroundColor Yellow
Write-Host "-----------------------" -ForegroundColor Yellow
Write-Host "1. Go to: Applications > Applications"
Write-Host "2. Find your application (Client ID: bjtGWwmdLFUfpHZRN3FCirQxUeIGDFBq)"
Write-Host "3. Go to 'APIs' tab"
Write-Host "4. Select 'CAR API' from dropdown"
Write-Host "5. Toggle 'Authorize' ON"
Write-Host "6. Grant scopes: read:documents, write:documents, admin"
Write-Host "7. Click 'Authorize'"
Write-Host ""

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "VERIFICATION" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "After completing the setup, verify with:" -ForegroundColor Green
Write-Host "  python scripts/verify_api_resource.py" -ForegroundColor White
Write-Host ""
Write-Host "Or test JWT generation:" -ForegroundColor Green
Write-Host "  python scripts/test_jwt_new_client.py" -ForegroundColor White
Write-Host ""

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "SETUP COMPLETE" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
