# PowerShell script to set up and push Git repository
# Run this after Git is installed and available in PATH

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Git Repository Setup Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if git is available
try {
    $gitVersion = git --version
    Write-Host "[OK] Git is available: $gitVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Git is not installed or not in PATH" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install Git from: https://git-scm.com/download/win" -ForegroundColor Yellow
    Write-Host "Then restart PowerShell and run this script again." -ForegroundColor Yellow
    exit 1
}

Write-Host ""

# Step 1: Check if repository is initialized
Write-Host "[STEP 1] Checking repository status..." -ForegroundColor Cyan
$gitStatus = git status 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "[INFO] Repository not initialized. Initializing..." -ForegroundColor Yellow
    git init
    Write-Host "[OK] Repository initialized" -ForegroundColor Green
} else {
    Write-Host "[OK] Repository already initialized" -ForegroundColor Green
}

Write-Host ""

# Step 2: Check remote
Write-Host "[STEP 2] Checking remote configuration..." -ForegroundColor Cyan
$remotes = git remote -v

if ($remotes -match "origin") {
    Write-Host "[OK] Remote 'origin' already configured" -ForegroundColor Green
} else {
    Write-Host "[INFO] Adding remote 'origin'..." -ForegroundColor Yellow
    git remote add origin https://github.com/joshrkay/CAR-ETL.git
    Write-Host "[OK] Remote added" -ForegroundColor Green
}

Write-Host ""

# Step 3: Check for uncommitted changes
Write-Host "[STEP 3] Checking for uncommitted changes..." -ForegroundColor Cyan
$status = git status --porcelain

if ($status) {
    Write-Host "[INFO] Found uncommitted changes. Staging files..." -ForegroundColor Yellow
    git add .
    Write-Host "[OK] Files staged" -ForegroundColor Green
    
    Write-Host ""
    Write-Host "[INFO] Creating initial commit..." -ForegroundColor Yellow
    git commit -m "feat: initial commit - CAR Platform with tenant provisioning, JWT claims, and middleware"
    Write-Host "[OK] Commit created" -ForegroundColor Green
} else {
    Write-Host "[INFO] No uncommitted changes found" -ForegroundColor Yellow
    
    # Check if there are any commits
    $commits = git log --oneline -1 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[WARNING] No commits found. Creating initial commit..." -ForegroundColor Yellow
        git add .
        git commit -m "feat: initial commit - CAR Platform with tenant provisioning, JWT claims, and middleware"
        Write-Host "[OK] Initial commit created" -ForegroundColor Green
    } else {
        Write-Host "[OK] Commits exist" -ForegroundColor Green
    }
}

Write-Host ""

# Step 4: Check branch name
Write-Host "[STEP 4] Checking branch name..." -ForegroundColor Cyan
$currentBranch = git branch --show-current

if (-not $currentBranch) {
    Write-Host "[INFO] No branch exists. Creating 'main' branch..." -ForegroundColor Yellow
    git checkout -b main
    Write-Host "[OK] Branch 'main' created" -ForegroundColor Green
} elseif ($currentBranch -ne "main") {
    Write-Host "[INFO] Current branch is '$currentBranch'. Renaming to 'main'..." -ForegroundColor Yellow
    git branch -M main
    Write-Host "[OK] Branch renamed to 'main'" -ForegroundColor Green
} else {
    Write-Host "[OK] Already on 'main' branch" -ForegroundColor Green
}

Write-Host ""

# Step 5: Push to remote
Write-Host "[STEP 5] Pushing to remote..." -ForegroundColor Cyan
Write-Host "[INFO] Pushing 'main' branch to 'origin'..." -ForegroundColor Yellow

try {
    git push -u origin main
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "[SUCCESS] Push completed successfully!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Repository is now available at:" -ForegroundColor Cyan
        Write-Host "https://github.com/joshrkay/CAR-ETL" -ForegroundColor Cyan
    } else {
        Write-Host "[ERROR] Push failed. Check the error message above." -ForegroundColor Red
    }
} catch {
    Write-Host "[ERROR] Push failed: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
