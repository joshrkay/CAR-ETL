# Fix Git Push Error: "src refspec main does not match any"

## Error
```
error: src refspec main does not match any
error: failed to push some refs to 'https://github.com/joshrkay/CAR-ETL.git'
```

## Common Causes

1. **No commits yet** - You need to make at least one commit before pushing
2. **Branch name mismatch** - Your local branch might be named `master` instead of `main`
3. **No local branch** - The branch doesn't exist locally

---

## Solutions

### Solution 1: Make Initial Commit (Most Common)

If you haven't committed anything yet:

```bash
# Check current status
git status

# Add all files
git add .

# Make initial commit
git commit -m "feat: initial commit - CAR Platform implementation"

# Create and push main branch
git branch -M main
git push -u origin main
```

### Solution 2: Check Current Branch Name

If your branch is named `master`:

```bash
# Check current branch
git branch

# If it shows 'master', rename to 'main'
git branch -M main

# Then push
git push -u origin main
```

### Solution 3: Create Main Branch from Current State

```bash
# Create main branch from current HEAD
git checkout -b main

# Or if you have commits on another branch
git checkout -b main <existing-branch>

# Push the new branch
git push -u origin main
```

### Solution 4: Push Existing Branch with Different Name

If you have commits but branch has different name:

```bash
# Check what branch you're on
git branch

# Push current branch as main
git push -u origin HEAD:main
```

---

## Step-by-Step Fix (Recommended)

### 1. Check Repository Status

```bash
git status
```

**If you see "nothing to commit":**
- You have commits but wrong branch name → Go to Solution 2

**If you see "untracked files":**
- You need to commit first → Go to Solution 1

### 2. Make Initial Commit (If Needed)

```bash
# Stage all files
git add .

# Commit with descriptive message
git commit -m "feat: initial commit - CAR Platform with tenant provisioning and JWT claims"
```

### 3. Ensure Branch is Named 'main'

```bash
# Rename current branch to main (if needed)
git branch -M main
```

### 4. Push to Remote

```bash
# Push and set upstream
git push -u origin main
```

---

## Alternative: Push to Master Branch

If the remote repository uses `master` instead of `main`:

```bash
# Push to master
git push -u origin master
```

Or configure the default branch:

```bash
# Set default branch to main
git config --global init.defaultBranch main
```

---

## Verify After Fix

```bash
# Check branches
git branch -a

# Check remote
git remote -v

# Verify push worked
git log --oneline -5
```

---

## Quick Fix Command Sequence

Copy and paste this sequence:

```bash
# 1. Add all files
git add .

# 2. Commit
git commit -m "feat: initial commit - CAR Platform implementation"

# 3. Ensure branch is main
git branch -M main

# 4. Push
git push -u origin main
```

---

## If You Still Have Issues

### Check Git Configuration

```bash
# Check user name and email
git config user.name
git config user.email

# Set if missing
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

### Check Remote Configuration

```bash
# Check remote URL
git remote -v

# If wrong, update it
git remote set-url origin https://github.com/joshrkay/CAR-ETL.git
```

### Force Push (Use with Caution)

**⚠️ Only use if you're sure and working alone:**

```bash
git push -u origin main --force
```

---

## Common Scenarios

### Scenario 1: New Repository, No Commits
```bash
git add .
git commit -m "Initial commit"
git branch -M main
git push -u origin main
```

### Scenario 2: Existing Commits, Wrong Branch Name
```bash
git branch -M main
git push -u origin main
```

### Scenario 3: Commits on Different Branch
```bash
git checkout -b main
git push -u origin main
```

---

**Status:** ✅ **FIX GUIDE READY**

Follow the steps above to resolve the git push error.
