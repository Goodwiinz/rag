# GitHub Secrets & Environment Setup Guide

## Overview

The CI/CD pipeline warnings you're seeing are **NOT ERRORS** - they're informational messages indicating that certain GitHub Secrets and Environments need to be configured for deployment features to work.

## ✅ What's Already Working

Your CI/CD pipeline will run successfully for:
- ✅ Code quality checks (linting, formatting)
- ✅ Security scanning
- ✅ Unit and integration tests
- ✅ Docker image building
- ✅ Container security scanning

## 🔧 Optional Setup (For Deployment Features)

The following configurations are **only needed if you want automated deployments**:

### Step 1: Create GitHub Environments

1. Go to your GitHub repository
2. Click **Settings** → **Environments**
3. Click **New environment**
4. Create two environments:
   - `staging`
   - `production`

### Step 2: Add Required Secrets

Go to **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these secrets:

#### For Staging Deployment

| Secret Name | Description | Example Value |
|-------------|-------------|---------------|
| `STAGING_SSH_KEY` | Private SSH key for staging server | `-----BEGIN OPENSSH PRIVATE KEY-----...` |
| `STAGING_HOST` | Staging server hostname/IP | `staging.example.com` or `192.168.1.100` |
| `STAGING_USER` | SSH username | `deploy` or `ubuntu` |
| `STAGING_DEPLOY_PATH` | Path to deployment directory | `/home/deploy/rag-system` |
| `STAGING_API_URL` | Staging API URL for smoke tests | `https://staging-api.example.com` |

#### For Docker Registry (Optional)

| Secret Name | Description | Example Value |
|-------------|-------------|---------------|
| `DOCKER_USERNAME` | Docker Hub username | `your-docker-username` |
| `DOCKER_PASSWORD` | Docker Hub password/token | `dckr_pat_xxx...` |

> **Note**: If you're using GitHub Container Registry (ghcr.io), you don't need Docker Hub credentials. The workflow already uses `${{ secrets.GITHUB_TOKEN }}` for ghcr.io.

### Step 3: Generate SSH Key (If Needed)

If you need to set up SSH access for deployment:

```bash
# Generate a new SSH key pair
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_deploy_key

# Copy the public key to your staging server
ssh-copy-id -i ~/.ssh/github_deploy_key.pub user@staging-server

# Copy the PRIVATE key content to GitHub Secrets as STAGING_SSH_KEY
cat ~/.ssh/github_deploy_key
```

## 🚀 How to Use

### Without Deployment (Current State)

Your pipeline will automatically run on:
- Push to `main`, `develop`, or `staging` branches
- Pull requests to `main` or `develop`
- Release creation

It will execute:
1. ✅ Code quality checks
2. ✅ Security scanning
3. ✅ Tests with coverage enforcement (80% minimum)
4. ✅ Docker image builds
5. ✅ Container security scans

### With Deployment (After Secret Setup)

Once secrets are configured:
- **Staging**: Auto-deploys when pushing to `staging` or `develop` branches
- **Production**: Requires manual approval, triggered by creating a release

## 📝 Disabling Deployment Steps (If Not Needed)

If you don't plan to use automated deployment, you can comment out or remove the deployment jobs:

```yaml
# Comment out these sections if not using deployment:
# - deploy-staging job (lines 470-563)
# - deploy-production job (lines 565-611)
```

Or add a conditional to skip them:

```yaml
deploy-staging:
  if: false  # Temporarily disable
  # ... rest of the job
```

## 🔍 Understanding the Warnings

The VS Code YAML extension shows these as "errors" because it can't validate that secrets exist. This is normal and expected behavior:

| Warning Message | What It Means | Impact |
|----------------|---------------|--------|
| `Context access might be invalid: STAGING_SSH_KEY` | Secret not configured yet | Deployment will skip/fail (tests still run) |
| `Value 'staging' is not valid` | Environment not created yet | Can create environment when needed |
| `Context access might be invalid: code-quality` | Job dependency reference | This is actually fine, just a linter issue |

## ✅ Quick Test Without Secrets

To verify your CI/CD works without deployment:

1. Make a code change
2. Commit and push to a feature branch
3. Create a Pull Request to `develop`
4. Watch the Actions tab - all quality/test jobs should pass
5. Deployment jobs will be skipped (which is fine)

## 📚 Additional Resources

- [GitHub Actions Secrets Documentation](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [GitHub Environments Documentation](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment)
- [SSH Key Setup Guide](https://docs.github.com/en/authentication/connecting-to-github-with-ssh)

## 🎯 Recommended Approach

**For now**: Leave the secrets unconfigured and just use CI/CD for:
- Automated testing
- Code quality enforcement  
- Security scanning
- Docker image builds

**Later**: When you're ready to set up deployment, come back and configure the secrets following this guide.

---

**Questions?** The pipeline is production-ready for CI/CD. Deployment is an optional feature you can enable when needed.
