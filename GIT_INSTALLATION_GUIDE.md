# Git Installation and Setup Guide

## Current Status

❌ **Git is not installed or not in your PATH**

The commands you're trying to run require Git to be installed first.

---

## Step 1: Install Git for Windows

### Download Git
1. Visit: **https://git-scm.com/download/win**
2. Download the latest version (64-bit recommended)
3. Run the installer

### Installation Options
During installation, use these recommended settings:

1. **Select Components:**
   - ✅ Git Bash Here
   - ✅ Git GUI Here
   - ✅ Associate .git* configuration files with the default text editor
   - ✅ Associate .sh files to be run with Bash

2. **Choosing the default editor:**
   - Choose your preferred editor (VS Code, Notepad++, etc.)

3. **Adjusting your PATH environment:**
   - ✅ **Select: "Git from the command line and also from 3rd-party software"**
   - This is IMPORTANT - it adds Git to your PATH

4. **Choosing HTTPS transport backend:**
   - Use the default OpenSSL library

5. **Configuring the line ending conversions:**
   - ✅ **Select: "Checkout Windows-style, commit Unix-style line endings"**

6. **Configuring the terminal emulator:**
   - Use Windows' default console window

7. **Default behavior of `git pull`:**
   - Default (fast-forward or merge)

8. **Credential helper:**
   - Use the default Git Credential Manager

9. **Extra options:**
   - ✅ Enable file system caching
   - ✅ Enable Git Credential Manager

10. **Experimental options:**
    - Leave unchecked for now

### Complete Installation
- Click "Install"
- Wait for installation to complete
- Click "Finish"

---

## Step 2: Verify Installation

### Restart Your Terminal
**IMPORTANT:** Close and reopen PowerShell/Command Prompt after installation.

### Test Git
```powershell
git --version
```

**Expected output:**
```
git version 2.xx.x.windows.x
```

If you see this, Git is installed correctly!

---

## Step 3: Configure Git (First Time Setup)

```powershell
# Set your name
git config --global user.name "Your Name"

# Set your email
git config --global user.email "your.email@example.com"

# Verify configuration
git config --list
```

---

## Step 4: Set Up Your Repository

Once Git is installed and working, run these commands:

### Option A: Use the Setup Script

```powershell
# Run the automated setup script
.\scripts\setup_git_repo.ps1
```

### Option B: Manual Setup

```powershell
# 1. Initialize repository (if needed)
git init

# 2. Add remote
git remote add origin https://github.com/joshrkay/CAR-ETL.git

# 3. Add all files
git add .

# 4. Create initial commit
git commit -m "feat: initial commit - CAR Platform implementation"

# 5. Set branch to main
git branch -M main

# 6. Push to GitHub
git push -u origin main
```

---

## Step 5: Verify Push

After pushing, verify it worked:

```powershell
# Check remote status
git remote -v

# Check branch
git branch -a

# View commit history
git log --oneline -5
```

---

## Troubleshooting

### Issue: Git Still Not Found After Installation

**Solution 1: Restart Terminal**
- Close PowerShell completely
- Reopen PowerShell
- Try `git --version` again

**Solution 2: Add Git to PATH Manually**
1. Find Git installation: Usually `C:\Program Files\Git\bin`
2. Add to PATH:
   - System Properties → Environment Variables
   - Edit "Path" variable
   - Add: `C:\Program Files\Git\bin`
3. Restart terminal

**Solution 3: Use Git Bash**
- Open "Git Bash" from Start Menu
- Git commands will work there
- Navigate to your project: `cd "C:\Users\Computer 2\Downloads\CAR-ETL"`

### Issue: Authentication Required

When pushing, you may need to authenticate:

**Option 1: Personal Access Token**
1. GitHub → Settings → Developer settings → Personal access tokens
2. Generate new token (classic)
3. Select scopes: `repo`
4. Use token as password when pushing

**Option 2: GitHub Desktop**
- Install GitHub Desktop
- Use it to push instead of command line

**Option 3: SSH Keys**
- Set up SSH keys for passwordless authentication

---

## Alternative: Use GitHub Desktop

If you prefer a GUI:

1. **Download:** https://desktop.github.com/
2. **Install** GitHub Desktop
3. **Open** GitHub Desktop
4. **File → Add Local Repository**
5. **Navigate to:** `C:\Users\Computer 2\Downloads\CAR-ETL`
6. **Click** "Publish repository"
7. **Select** "Keep this code private" (if desired)
8. **Click** "Publish repository"

---

## Quick Reference

### Essential Git Commands

```powershell
# Check status
git status

# Add files
git add .

# Commit
git commit -m "Your commit message"

# Push
git push -u origin main

# Pull
git pull

# View history
git log --oneline
```

### Commit Message Format (Following .cursorrules)

```
feat(scope): description

Example:
feat(tenants): add tenant provisioning API
feat(auth): implement JWT claims middleware
fix(encryption): remove hardcoded salt
```

---

## Next Steps After Installation

1. ✅ Install Git
2. ✅ Restart terminal
3. ✅ Verify: `git --version`
4. ✅ Configure: `git config --global user.name` and `user.email`
5. ✅ Run: `.\scripts\setup_git_repo.ps1`
6. ✅ Verify push succeeded

---

**Status:** ⚠️ **GIT INSTALLATION REQUIRED**

Install Git first, then run the commands. See steps above.
