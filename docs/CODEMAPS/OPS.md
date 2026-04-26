# NOUS — Ops CODEMAP

> Docker Compose files, monitoring stack, scripts catalog.
> Last generated: 2026-04-26

## Compose files (`config/docker-compose/`)

Root symlinks point here. Use the full path for explicit invocation.

| File | Use case | Notes |
|---|---|---|
| `docker-compose.development.yml` | **Local dev (primary)** | All services + hot-reload |
| `docker-compose.yml` | Backend + DBs only | Lighter alternative |
| `docker-compose.services.yml` | Infrastructure only | PG, Neo4j, Qdrant, Redis — no app |
| `docker-compose.ci.yml` | CI pipeline | No named volumes |
| `docker-compose.prod.yml` | Prod-equivalent local | YAML anchors for secrets |
| `docker-compose.staging.yml` | Staging-equivalent local | |
| `docker-compose.observability.yml` | Prometheus + Grafana + AlertManager | Run alongside dev compose |
| `docker-compose.security.yml` | Security scanning | |
| `docker-compose.websocket.yml` | WebSocket testing | |
| `docker-compose.azure.yml` | Azure OpenAI endpoint | |
| `docker-compose.graph-services.yml` | Neo4j + graph analytics | |

Quick-start:
```sh
docker compose -f config/docker-compose/docker-compose.development.yml up -d
```

## Monitoring stack (`monitoring/`)

Self-contained observability stack — run alongside the app.

| File / Dir | Purpose |
|---|---|
| `prometheus.yml` | Prometheus scrape config |
| `prometheus-rules/` | Recording + alerting rules |
| `alert_rules.yml` | Alert rule definitions |
| `performance_alerts.yml` | Performance-specific alerts |
| `alertmanager.yml` | AlertManager routing + receivers |
| `alertmanager/` | Alertmanager templates |
| `grafana/` | Dashboard JSON exports |
| `grafana-dashboard.json` | Main NOUS dashboard |
| `otel-collector-config.yaml` | OpenTelemetry collector |
| `loki-config.yaml` | Loki log aggregation |
| `filebeat/` + `logstash/` | Log shipping |
| `docker-compose.monitoring.yml` | Monitoring stack compose |

Docs: `docs/operations/monitoring/`

Start monitoring stack:
```sh
docker compose -f monitoring/docker-compose.monitoring.yml up -d
```

## Scripts catalog (`scripts/` — 84 files)

### Active / maintained

| Script | Purpose |
|---|---|
| `deploy.sh` | Full stack deployment (Helm + ArgoCD) |
| `deploy-graph-services.sh` | Deploy Neo4j + graph analytics |
| `deploy_performance_optimizations.sh` | Apply PG + Qdrant optimizations |
| `health-check.sh` | End-to-end health probe (all services) |
| `backup_all_data.sh` | PG + Neo4j + Qdrant full backup |
| `backup-and-recovery.sh` | Backup with recovery test |
| `backup-and-restore.sh` | Backup + restore pipeline |
| `ci/stages.sh` | CI stage detection |
| `ci/detect-changes.sh` | Changed-paths detection for selective CI |
| `sync-to-obsidian.sh` | Push docs/memory to Obsidian vault |
| `Makefile` → `Makefile` (root) | Top-level dev shortcuts |

### Audit-and-delete candidates (pre-CI one-off scripts)

41× `test_*.py` — ad-hoc exploration scripts written before the test suite existed.  
21× `check_*.py` — one-off diagnostic scripts.  
2× `debug_*.py` — debug sessions, not reusable.

These are candidates for deletion once confirmed unused. Audit: `grep -rn "test_\|check_\|debug_" .github/` to confirm CI doesn't reference them.

### Backup directory (`scripts/backup/`)

Periodic backup scripts organized by target (postgres, neo4j, qdrant, storage).

## CI/CD (`.github/workflows/`)

| Workflow | Trigger | Purpose |
|---|---|---|
| `test-pipeline.yml` | push / PR | Lint + type-check + unit + integration tests |
| `build-push.yml` | push to develop/staging/main | Build Docker images + push to GHCR |
| `deploy-*.yml` | manual / tag | Environment-specific deploy |
| `security-scan.yml` | schedule | Dependency + container scanning |
| Additional workflows (up to 8 total) | various | |

CI uses self-hosted Depot runners for fast builds (linux/amd64). Frontend CI uses `pnpm` (not npm) — only `pnpm-lock.yaml` is committed.

## Runbooks and docs

- Monitoring setup → `docs/operations/monitoring/`
- Observability (LangSmith, tracing) → `docs/operations/observability/`
- Oncall / incident response → `docs/operations/`
- k8s manifests for monitoring → `infrastructure/kubernetes/monitoring/`
- Helm values for Prometheus/Grafana → `infrastructure/helm/kube-prometheus-stack-values.yaml`
