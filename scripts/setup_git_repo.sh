#!/bin/bash
# Bash script to set up and push Git repository
# Run this after Git is installed

echo "========================================"
echo "Git Repository Setup Script"
echo "========================================"
echo ""

# Check if git is available
if ! command -v git &> /dev/null; then
    echo "[ERROR] Git is not installed or not in PATH"
    echo ""
    echo "Please install Git and ensure it's in your PATH"
    exit 1
fi

echo "[OK] Git is available: $(git --version)"
echo ""

# Step 1: Check if repository is initialized
echo "[STEP 1] Checking repository status..."
if ! git status &> /dev/null; then
    echo "[INFO] Repository not initialized. Initializing..."
    git init
    echo "[OK] Repository initialized"
else
    echo "[OK] Repository already initialized"
fi

echo ""

# Step 2: Check remote
echo "[STEP 2] Checking remote configuration..."
if git remote | grep -q "origin"; then
    echo "[OK] Remote 'origin' already configured"
else
    echo "[INFO] Adding remote 'origin'..."
    git remote add origin https://github.com/joshrkay/CAR-ETL.git
    echo "[OK] Remote added"
fi

echo ""

# Step 3: Check for uncommitted changes
echo "[STEP 3] Checking for uncommitted changes..."
if [ -n "$(git status --porcelain)" ]; then
    echo "[INFO] Found uncommitted changes. Staging files..."
    git add .
    echo "[OK] Files staged"
    
    echo ""
    echo "[INFO] Creating initial commit..."
    git commit -m "feat: initial commit - CAR Platform with tenant provisioning, JWT claims, and middleware"
    echo "[OK] Commit created"
else
    echo "[INFO] No uncommitted changes found"
    
    # Check if there are any commits
    if ! git log --oneline -1 &> /dev/null; then
        echo "[WARNING] No commits found. Creating initial commit..."
        git add .
        git commit -m "feat: initial commit - CAR Platform with tenant provisioning, JWT claims, and middleware"
        echo "[OK] Initial commit created"
    else
        echo "[OK] Commits exist"
    fi
fi

echo ""

# Step 4: Check branch name
echo "[STEP 4] Checking branch name..."
current_branch=$(git branch --show-current 2>/dev/null)

if [ -z "$current_branch" ]; then
    echo "[INFO] No branch exists. Creating 'main' branch..."
    git checkout -b main
    echo "[OK] Branch 'main' created"
elif [ "$current_branch" != "main" ]; then
    echo "[INFO] Current branch is '$current_branch'. Renaming to 'main'..."
    git branch -M main
    echo "[OK] Branch renamed to 'main'"
else
    echo "[OK] Already on 'main' branch"
fi

echo ""

# Step 5: Push to remote
echo "[STEP 5] Pushing to remote..."
echo "[INFO] Pushing 'main' branch to 'origin'..."

if git push -u origin main; then
    echo ""
    echo "[SUCCESS] Push completed successfully!"
    echo ""
    echo "Repository is now available at:"
    echo "https://github.com/joshrkay/CAR-ETL"
else
    echo "[ERROR] Push failed. Check the error message above."
fi

echo ""
echo "========================================"
