# NOUS — Infra CODEMAP

> Cluster topology, ArgoCD apps, Helm releases, Compose files, CI runners.
> Last generated: 2026-04-26

## Cluster (DOKS — DigitalOcean Kubernetes)

Three environments, all managed by ArgoCD GitOps:

| Environment | Namespace | ArgoCD app | Notes |
|---|---|---|---|
| dev | `nous-dev` | `nous-dev` | Auto-syncs from `develop` branch |
| staging | `nous-staging` | `nous-staging` | Auto-syncs from `staging` branch |
| prod | `nous-prod` | `nous-prod` | Manual sync gate |

ArgoCD is installed in the `argocd` namespace. All apps are defined under `infrastructure/argocd/applications/`.

**Rule:** Never `kubectl patch` ArgoCD-managed resources directly — selfHeal will revert. All changes must be committed to the relevant branch.

## Helm releases

| Chart | Path | Purpose |
|---|---|---|
| `nous-backend` | `infrastructure/helm/` | FastAPI + Celery workers |
| `nous-frontend` | `infrastructure/helm/` | Next.js app |
| `knowledge-graph-analytics` | `infrastructure/helm/knowledge-graph-analytics/` | Neo4j analytics sidecar |
| `kube-prometheus-stack` | `infrastructure/helm/` (values only) | Prometheus + Grafana |
| `cert-manager` | `infrastructure/helm/` (values only) | TLS cert provisioning |

Helm values per env live in `infrastructure/kubernetes/overlays/<env>/`.

## Kubernetes manifests (`infrastructure/kubernetes/`)

```
kubernetes/
  base/             Base manifests (Deployments, Services, HPA)
  overlays/         Kustomize overlays per env (dev / staging / prod)
  configmaps/       App configuration (non-secret)
  secrets/          ExternalSecret references (DO Secrets Manager)
  manifests/        One-off manifests not managed by Helm
  monitoring/       Prometheus ServiceMonitors, AlertManager rules
  namespace.yaml    Namespace definitions
```

## Terraform (`infrastructure/terraform/`)

Manages the DOKS cluster, load balancers, DNS, managed databases, and DigitalOcean Spaces (S3-compatible).

## CI runners (`infrastructure/arc/` + `infrastructure/runner/`)

Self-hosted GitHub Actions runners on DOKS via Actions Runner Controller (ARC). Runner pod spec in `infrastructure/arc/`. Runner registration config in `infrastructure/runner/`. Both are CI concerns; consolidation target: `infrastructure/ci/`.

## Docker Compose files (`config/docker-compose/`)

| File | Use |
|---|---|
| `docker-compose.development.yml` | Local full-stack dev |
| `docker-compose.yml` | Minimal (backend + DBs only) |
| `docker-compose.prod.yml` | Production-equivalent local test |
| `docker-compose.staging.yml` | Staging-equivalent local test |
| `docker-compose.ci.yml` | CI pipeline (no volumes) |
| `docker-compose.services.yml` | Infrastructure services only (PG, Neo4j, Qdrant, Redis) |
| `docker-compose.observability.yml` | Prometheus + Grafana + AlertManager |
| `docker-compose.security.yml` | Security scanning stack |
| `docker-compose.websocket.yml` | WebSocket testing setup |
| `docker-compose.azure.yml` | Azure OpenAI endpoint variant |
| `docker-compose.graph-services.yml` | Neo4j + graph analytics |
| `docker-compose.backend/` | Backend-only multi-stage build context |
| `docker-compose.frontend/` | Frontend-only multi-stage build context |

Root symlinks (`docker-compose.development.yml`, etc.) point into this directory.

## Key service ports

| Service | Port | Notes |
|---|---|---|
| PostgreSQL | 5432 | DB name: `multimodal_rag_dev`; container: `rag-postgres-1` |
| Neo4j | 7687 (bolt) / 7474 (HTTP) | |
| Qdrant | 6333 | |
| Redis / Valkey | 6379 | Managed cache on DO is Valkey — wire-compatible |
| Backend | 8000 | |
| Frontend | 3000 | |

## Monitoring stack

Prometheus + Grafana + AlertManager run as a sidecar stack.  
Configs: `monitoring/` (root) — Prometheus rules, Grafana dashboards, AlertManager routing.  
k8s manifests: `infrastructure/kubernetes/monitoring/`.  
Helm values: `infrastructure/helm/kube-prometheus-stack-values.yaml`.  
Docs: `docs/operations/monitoring/`.

## Image registry

Docker images are built by Depot (linux/amd64 only) and pushed to GHCR (`ghcr.io/goodwiins/rag`).  
Tags: `develop-YYYYMMDD-<sha>` (develop builds), `staging-*`, `prod-*`.  
CI: `.github/workflows/test-pipeline.yml` builds + pushes; ArgoCD picks up new tags.

## Adding a new service to k8s

1. Add Helm chart or kustomize base manifest under `infrastructure/kubernetes/base/`.
2. Add overlay patches under `infrastructure/kubernetes/overlays/<env>/`.
3. If it needs a secret: add ExternalSecret in `infrastructure/kubernetes/secrets/`.
4. Add a ServiceMonitor in `infrastructure/kubernetes/monitoring/` for Prometheus scraping.
5. Update `infrastructure/argocd/applications/` if it's a new ArgoCD app.
6. Add a Compose entry in the relevant `config/docker-compose/` file for local dev.
