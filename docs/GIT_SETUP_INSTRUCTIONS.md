# Git Setup Instructions for Windows

## Issue: Git Not Found

The error indicates Git is not installed or not in your PATH.

---

## Solution 1: Install Git for Windows

1. **Download Git:**
   - Visit: https://git-scm.com/download/win
   - Download the latest version

2. **Install Git:**
   - Run the installer
   - Use default settings (recommended)
   - Ensure "Add Git to PATH" is checked

3. **Restart Terminal:**
   - Close and reopen PowerShell/Command Prompt
   - Or restart your computer

4. **Verify Installation:**
   ```powershell
   git --version
   ```

---

## Solution 2: Use Git from GitHub Desktop

If you have GitHub Desktop installed:

1. Open GitHub Desktop
2. File → Add Local Repository
3. Navigate to: `C:\Users\Computer 2\Downloads\CAR-ETL`
4. Use GitHub Desktop to commit and push

---

## Solution 3: Use Git Bash

If Git is installed but not in PATH:

1. **Find Git Installation:**
   - Usually: `C:\Program Files\Git\bin\git.exe`
   - Or: `C:\Program Files (x86)\Git\bin\git.exe`

2. **Use Full Path:**
   ```powershell
   & "C:\Program Files\Git\bin\git.exe" status
   ```

3. **Or Add to PATH:**
   - System Properties → Environment Variables
   - Add Git bin directory to PATH

---

## After Git is Available

Once Git is working, run these commands to fix the push error:

### Step 1: Check Status
```bash
git status
```

### Step 2: If You See Untracked Files
```bash
# Add all files
git add .

# Commit
git commit -m "feat: initial commit - CAR Platform implementation"
```

### Step 3: Check Branch Name
```bash
git branch
```

### Step 4: Rename to Main (If Needed)
```bash
git branch -M main
```

### Step 5: Push
```bash
git push -u origin main
```

---

## Quick Setup Script

After Git is installed, you can run this sequence:

```bash
# Initialize if needed (only if not already a git repo)
git init

# Add remote (if not already set)
git remote add origin https://github.com/joshrkay/CAR-ETL.git

# Add all files
git add .

# Commit
git commit -m "feat: initial commit - CAR Platform with tenant provisioning, JWT claims, and middleware"

# Set branch to main
git branch -M main

# Push
git push -u origin main
```

---

## Verify Git Installation

After installing Git, verify it works:

```powershell
# Check version
git --version

# Check if repository is initialized
git status
```

---

## Alternative: Manual File Upload

If you can't install Git right now:

1. Go to: https://github.com/joshrkay/CAR-ETL
2. Click "Upload files"
3. Drag and drop your project files
4. Commit directly on GitHub

---

**Next Steps:**
1. Install Git for Windows
2. Restart terminal
3. Run `git status` to check repository state
4. Follow the fix guide in `docs/GIT_PUSH_FIX.md`
