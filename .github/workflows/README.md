# CI/CD Workflows

This directory contains GitHub Actions workflows for automated testing and deployment.

## 📁 Files Overview

### **Currently Active**

| File | Purpose | Status |
|------|---------|--------|
| [`ci.yml`](ci.yml) | Main CI/CD pipeline | ✅ **ACTIVE** |

### **Alternative Options**

| File | Purpose | Use When |
|------|---------|----------|
| [`ci-improved.yml`](ci-improved.yml) | Stricter version with quality gates | Want to enforce code quality |
| [`ci-no-docker.yml`](ci-no-docker.yml) | Traditional deployment (no Docker) | Not using Docker |
| [`deploy-staging.yml`](deploy-staging.yml) | Staging environment deployment | Have a staging server |

---

## 🚀 **Current Pipeline (`ci.yml`)**

### What It Does

Runs **4 jobs in parallel** on every push/PR:

```
┌─────────────────────────────────────────────┐
│  Push to GitHub                             │
└────────────────┬────────────────────────────┘
                 │
        ┌────────┴────────────────────┐
        │  Triggers CI/CD Pipeline    │
        └────────┬────────────────────┘
                 │
     ┌───────────┴───────────┬────────────┬──────────────┐
     │                       │            │              │
┌────▼─────┐       ┌────────▼────┐  ┌───▼──────┐  ┌───▼─────────┐
│   Lint   │       │    Test     │  │  Docker  │  │  Security   │
│          │       │             │  │  Build   │  │    Scan     │
│ • flake8 │       │ • pytest    │  │          │  │             │
│ • black  │       │ • coverage  │  │ • backend│  │ • safety    │
│ • isort  │       │ • PostgreSQL│  │ • worker │  │ • bandit    │
│          │       │ • Redis     │  │          │  │             │
└──────────┘       └─────────────┘  └──────────┘  └─────────────┘
     │                    │              │               │
     └────────────────────┴──────────────┴───────────────┘
                          │
                     ✅ All Pass
                          │
                    Ready to Merge
```

### Jobs Breakdown

#### 1. **Lint** (Required)
- **What**: Code quality checks
- **Tools**: flake8, black, isort
- **Time**: ~1-2 minutes
- **Note**: Currently only warns on formatting issues

#### 2. **Test** (Required)
- **What**: Unit tests with coverage
- **Services**: PostgreSQL 14, Redis 7
- **Time**: ~3-5 minutes
- **Coverage**: Reports sent to Codecov (optional)

#### 3. **Docker Build** (/// Optional)
- **What**: Validates Docker images build correctly
- **Builds**: Backend API + Celery Worker
- **Time**: ~2-4 minutes
- **Skip if**: Not using Docker (see `ci-no-docker.yml`)

#### 4. **Security Scan** (Recommended)
- **What**: Check for vulnerabilities
- **Tools**: safety (dependencies), bandit (code)
- **Time**: ~1-2 minutes
- **Note**: Currently doesn't fail build, just warns

---

## 🎯 **Which Workflow Should You Use?**

### Use `ci.yml` (Current) If:
- ✅ Just getting started
- ✅ Want basic CI/CD
- ✅ Using Docker (or might later)
- ✅ Okay with warnings (not strict enforcement)

### Use `ci-improved.yml` If:
- ✅ Want strict code quality enforcement
- ✅ Need coverage thresholds (80% minimum)
- ✅ Want integration tests
- ✅ Production-ready quality gates

### Use `ci-no-docker.yml` If:
- ✅ **NOT** using Docker for deployment
- ✅ Deploying to traditional VPS
- ✅ Want simpler, faster builds
- ✅ Don't need container validation

### Use `deploy-staging.yml` If:
- ✅ Have a staging environment
- ✅ Want auto-deployment on `main` branch
- ✅ Using Docker containers
- ✅ Need preview environments

---

## 🔧 **How to Switch Workflows**

### Option 1: Make `ci-improved.yml` Active

```bash
# Backup current
mv .github/workflows/ci.yml .github/workflows/ci-basic.yml.backup

# Activate improved
mv .github/workflows/ci-improved.yml .github/workflows/ci.yml

# Commit
git add .github/workflows/
git commit -m "Switch to improved CI with strict quality gates"
git push
```

### Option 2: Skip Docker Builds

```bash
# Backup current
mv .github/workflows/ci.yml .github/workflows/ci-with-docker.yml.backup

# Activate no-docker version
mv .github/workflows/ci-no-docker.yml .github/workflows/ci.yml

git add .github/workflows/
git commit -m "Switch to traditional deployment (no Docker)"
git push
```

---

## 📊 **Understanding the Workflow File**

All workflows follow this structure:

```yaml
name: Workflow Name              # What shows in GitHub UI

on:                              # When to run
  push:                          # On code push
    branches: [main, develop]    # Only these branches
  pull_request:                  # On pull requests
  workflow_dispatch:             # Manual trigger button

env:                             # Global variables
  PYTHON_VERSION: '3.11'

jobs:                            # What to run
  job-name:                      # Unique job ID
    runs-on: ubuntu-latest       # Runner type

    services:                    # /// Optional: Docker services
      postgres: ...

    steps:                       # Steps in order
      - name: Step name
        uses: action@version     # Or run: command
```

---

## 🔍 **Understanding Comments**

### Special Comment Markers

- `# Normal comment` - Explanation
- `/// Comment` - **Optional/Ignorable section**
  - If you see `///`, that part can be safely removed
  - Example: `/// This is optional - remove if not needed`

### Example:

```yaml
# This step is required
- name: Run tests
  run: pytest

# /// This step is optional - only for Codecov users
- name: Upload to Codecov
  uses: codecov/codecov-action@v4
```

The `///` marker means: "This is nice to have but not necessary."

---

## 🎓 **Common Customizations**

### 1. Change Python Version

```yaml
env:
  PYTHON_VERSION: '3.12'  # Change from 3.11 to 3.12
```

### 2. Add More Branches

```yaml
on:
  push:
    branches: [main, develop, staging, feature/*]  # Added staging and feature branches
```

### 3. Skip Docker Job

```yaml
# Comment out or delete the entire docker-build job
# docker-build:
#   name: Docker Build Test
#   ...
```

### 4. Make Linting Strict

```yaml
# In ci.yml, change this:
run: black --check src tests || echo "::warning::..."

# To this (fails build if not formatted):
run: black --check src tests
```

### 5. Add Code Coverage Threshold

```yaml
# In test job, change pytest command:
run: pytest tests/ --cov=src --cov-fail-under=80  # Fails if coverage < 80%
```

---

## 🚨 **Troubleshooting**

### Workflow Fails on First Run

**Common issues:**

1. **Missing `requirements.txt`**
   ```bash
   # Make sure this file exists:
   backend/requirements.txt
   ```

2. **Tests not found**
   ```bash
   # Make sure tests directory exists:
   backend/tests/
   ```

3. **Docker build fails**
   ```bash
   # Make sure Dockerfiles exist:
   backend/Dockerfile
   backend/Dockerfile.worker
   ```

### How to View Logs

1. Go to GitHub → Your Repo → **Actions** tab
2. Click on the failed workflow run
3. Click on the failed job (red X)
4. Click on the failed step to see logs

### How to Re-run Failed Jobs

1. Go to the failed workflow run
2. Click **Re-run failed jobs** button (top right)

---

## 📚 **Additional Resources**

- [CI/CD Best Practices](../../CI_CD_BEST_PRACTICES.md) - Complete best practices guide
- [Docker Decision Guide](../../DOCKER_OR_NOT.md) - Should you use Docker?
- [Traditional Deployment](../../DEPLOYMENT_TRADITIONAL.md) - Deploy without Docker
- [GitHub Actions Docs](https://docs.github.com/en/actions) - Official documentation

---

## 🎯 **Quick Start Checklist**

- [ ] Review `ci.yml` to understand what runs
- [ ] Check if all jobs pass on your repo
- [ ] Decide if you need Docker (see DOCKER_OR_NOT.md)
- [ ] Enable branch protection on `main` (require CI to pass)
- [ ] Consider upgrading to `ci-improved.yml` for stricter checks
- [ ] Set up staging deployment if needed

---

**Questions?** Check the [CI/CD Best Practices](../../CI_CD_BEST_PRACTICES.md) guide or open an issue!
