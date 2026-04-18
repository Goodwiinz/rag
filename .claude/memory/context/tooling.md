# Tooling & Connections

## DigitalOcean Setup

| Resource               | Details                                                                        |
| ---------------------- | ------------------------------------------------------------------------------ |
| **Cluster node**       | `moltbot1241onubuntu-s-2vcpu-4gb-amd-nyc3-01`                                  |
| **Node IP**            | `138.197.36.44` (NYC3)                                                         |
| **Node specs**         | 16 GB RAM / 320 GB disk (K8s worker)                                           |
| **CPU idle**           | ~1.83% — plenty of headroom for CI runners                                     |
| **Spaces bucket**      | `rag-system-storage` (NYC3) — used for S3 storage backend + Docker layer cache |
| **Container registry** | `registry.digitalocean.com/ragsystemregistry`                                  |
| **Domain**             | `gen-text.app` (9 A / 3 NS / 1 SOA records)                                    |
| **K8s version**        | Moltbot 1.24-1 on Ubuntu                                                       |

## GitHub

- **Repo**: `Goodwiinz/rag` (private)
- **Branch strategy**: feature branches from `develop`, PRs target `develop`
- **Active branch**: `claude/implement-todo-item-fgVkL`
- **Actions runner**: self-hosted via ARC in `arc-systems` namespace

## ARC (Actions Runner Controller)

- **Namespace**: `arc-systems`
- **Manifest**: `infrastructure/arc/runner-deployment.yaml`
- **Config**: 1–3 ephemeral pods, DinD, 4 CPU / 8 GB limit
- **Labels**: `[self-hosted, linux]`
- **Install command**:
  ```bash
  helm install arc \
    actions-runner-controller/actions-runner-controller \
    --namespace arc-systems --create-namespace \
    --set authSecret.create=true \
    --set "authSecret.github_token=<PAT>"
  kubectl apply -f infrastructure/arc/runner-deployment.yaml
  ```

## Spaces Docker Cache

- **Bucket**: `rag-system-storage`
- **Prefixes**: `buildcache/backend/`, `buildcache/frontend/`
- **Endpoint**: `https://nyc3.digitaloceanspaces.com`
- **Secrets needed**: `DO_SPACES_ACCESS_KEY`, `DO_SPACES_SECRET_KEY`

## ArgoCD

- **Staging app**: `nous-staging` — manual sync only (`argocd app sync nous-staging`)
- **Production app**: `nous-production` — manual sync (`argocd app sync nous-production`)
- **Manifests**: `infrastructure/argocd/applications/`

## Linear

- **Team**: Goodwiinz
- **Active issues**: GOO-187→GOO-197 (gap analysis)

## Obsidian

- **Vault**: Mysynic @ `/Users/goodwiinz/Documents/claude-memory`
- **Sync**: `./sync-to-obsidian.sh` (macOS only)

## Local Service Ports

| Service    | Port | URL                         |
| ---------- | ---- | --------------------------- |
| PostgreSQL | 5432 | postgres:postgres@localhost |
| Neo4j      | 7687 | bolt://localhost:7687       |
| Qdrant     | 6333 | http://localhost:6333       |
| Redis      | 6379 | redis://localhost:6379      |
| Backend    | 8000 | http://localhost:8000       |
| Frontend   | 3000 | http://localhost:3000       |
