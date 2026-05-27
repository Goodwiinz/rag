# CI/CD Workflows

CI for this repo is split across Depot CI and GitHub Actions.

## 📁 Workflows

| File                                 | Purpose                    | Triggers            |
| ------------------------------------ | -------------------------- | ------------------- |
| `.depot/workflows/test-pipeline.yml` | Lint, test, security scan  | Push, PR            |
| `docker-build.yml`                   | Build & push Docker images | After tests pass    |
| `deploy.yml`                         | Deploy to DigitalOcean K8s | After build, manual |

## 🔄 Pipeline Flow

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Push/PR   │────▶│ Test Pipeline│────▶│ Docker Build│
└─────────────┘     └──────────────┘     └──────────────┘
                           │                    │
                           ▼                    ▼
                    ┌──────────────┐     ┌─────────────┐
                    │   Staging    │────▶│ Production  │
                    │   Deploy     │     │   Deploy    │
                    └──────────────┘     └─────────────┘
```

Depot CI `test-pipeline.yml` and GitHub Actions `docker-build.yml` are intentionally separate.

- `.depot/workflows/test-pipeline.yml` validates the codebase: linting, unit/integration/frontend/security/E2E/performance checks on Depot CI sandboxes.
- `.github/workflows/docker-build.yml` builds and publishes the deployable backend image after code changes land on `main` or `develop`. The frontend is deployed via Vercel, not from a k8s-bound image.
- `deploy.yml` and `gitops-image-update.yml` depend on the image build stage, so `docker-build.yml` is part of the delivery pipeline rather than duplicate CI.

Depot usage is split by product:

- Depot CI uses explicit sandbox labels in `.depot/workflows/test-pipeline.yml`, with `depot-ubuntu-24.04-8` on the heavier jobs and `depot-ubuntu-24.04` on lighter jobs.
- GitHub Actions image builds in `.github/workflows/docker-build.yml` use Depot GitHub Actions runner labels (`depot-ubuntu-24.04-8`).
- Lighter GitHub summary/deploy orchestration jobs stay on `ubuntu-latest`.

---

## 🧪 Test Pipeline (`.depot/workflows/test-pipeline.yml`)

Runs on every push and PR. **Must pass before Docker build.**

### Jobs

| Job                  | What                     | Time   |
| -------------------- | ------------------------ | ------ |
| `lint-backend`       | Ruff, Black, isort, MyPy | ~2 min |
| `lint-frontend`      | TypeScript, ESLint       | ~1 min |
| `unit-tests`         | pytest (8% coverage min) | ~3 min |
| `security-scan`      | Bandit, Safety           | ~1 min |
| `frontend-tests`     | Jest                     | ~2 min |
| `integration-tests`  | Postgres + Redis         | ~5 min |
| `resilience-tests`   | Circuit breaker tests    | ~2 min |
| `api-contract-tests` | Schemathesis             | ~3 min |
| `performance-tests`  | Benchmarks (main only)   | ~5 min |

---

## 🐳 Docker Build (`docker-build.yml`)

Builds multi-arch images after tests pass.

### What it builds

- `ghcr.io/<repo>/backend:latest`
- Tags: `latest`, branch name, commit SHA

### Features

- Multi-platform: `linux/amd64`, `linux/arm64`
- GHA cache for fast rebuilds
- Bake action for all services

---

## 🚀 Deploy (`deploy.yml`)

Deploys to DigitalOcean Kubernetes using Helm.

### Environments

| Environment | Replicas       | Auto-deploy  | URL                    |
| ----------- | -------------- | ------------ | ---------------------- |
| Staging     | 1              | On main push | staging.yourdomain.com |
| Production  | 3+ (autoscale) | Manual only  | yourdomain.com         |

### Usage

**Auto-deploy to staging:**

```
Push to main → Tests pass → Docker build → Deploy staging
```

**Manual deploy to production:**

```
Actions → Deploy → Run workflow → Select "production"
```

### Required Secrets

| Secret                      | Description   |
| --------------------------- | ------------- |
| `DIGITALOCEAN_ACCESS_TOKEN` | DO API token  |
| `GITHUB_TOKEN`              | Auto-provided |

### Configuration

Update in `deploy.yml`:

```yaml
env:
  CLUSTER_NAME: rag-cluster # Your DOKS cluster name
```

Update URLs in environment settings:

```yaml
environment:
  name: production
  url: https://yourdomain.com
```

---

## 🔧 Setup

### 1. Add GitHub Secrets

```bash
# In GitHub repo → Settings → Secrets → Actions
DIGITALOCEAN_ACCESS_TOKEN=REDACTED_xxxxx
```

### 2. Create Kubernetes Namespaces

```bash
doctl kubernetes cluster kubeconfig save rag-cluster
kubectl create namespace rag-staging
kubectl create namespace rag-production
```

### 3. Configure GitHub Environments

1. Go to Settings → Environments
2. Create `staging` and `production`
3. Add protection rules for `production`:
   - Required reviewers
   - Wait timer (optional)

---

## 🔒 Branch Protection

Recommended settings for `main`:

- ✅ Require status checks: `Test Summary`
- ✅ Require branches to be up to date
- ✅ Require pull request reviews
- ✅ Require conversation resolution

---

## 🐛 Troubleshooting

### Tests fail with "No tests found"

```bash
# Check test markers exist
pytest --collect-only -m "unit"
```

### Docker build times out

- Check GHA cache is working
- Consider reducing platforms (remove arm64 if not needed)

### Deploy fails with "cluster not found"

```bash
# Verify cluster name
doctl kubernetes cluster list
```

### Rollback a bad deploy

```bash
helm rollback rag-production -n rag-production
```

---

## 📚 Related Docs

- [Helm Chart](../../infrastructure/helm/knowledge-graph-analytics/)
- [Kubernetes Config](../../infrastructure/kubernetes/)
- [Docker Compose (local)](../../docker-compose.yml)
