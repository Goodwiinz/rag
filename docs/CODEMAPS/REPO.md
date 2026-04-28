# NOUS — Repo CODEMAP

> One-screen overview of every top-level directory. Update whenever the repo layout changes.
> Last generated: 2026-04-26

## Top-level layout

```
RAG_system/
  backend/          FastAPI app, LangGraph agent, Celery workers
  frontend/         Next.js 15 + React UI; CLI at frontend/cli/
  infrastructure/   Terraform, k8s manifests, Helm charts, ArgoCD, CI runners
  ops/              [planned] ops-time tools: scripts, compose, monitoring infra
  config/           docker-compose variants (symlinked to root), env templates
  database/         Raw SQL migrations + schema documentation
  deployment/       Deployment scripts, Helm overrides, GitHub Actions helpers
  monitoring/       Prometheus/Grafana/AlertManager configs + docker-compose stack
  docs/             Architecture, API reference, deployment guides, CODEMAPS
  security/         Security audit reports, compliance docs
  brand/            Logo, design assets, landing page
  scripts/          Root-level utility/CI scripts (87 files; see OPS.md)
  notebooks/        Jupyter exploration notebooks
  evals/            Evaluation datasets and harness configs
  .github/          CI/CD workflows (8 workflows)
  .claude/          Claude Code agent config, skills, plans
```

## Entry points

| Concern | File |
|---|---|
| Backend app | `backend/src/main.py` |
| Agent graph | `backend/src/services/agent/graph.py` |
| LangGraph config | `backend/langgraph.json` |
| Frontend | `frontend/app/layout.tsx` |
| CLI | `frontend/cli/index.ts` |
| API rewrites | `frontend/next.config.js` → `rewrites()` |
| Dev environment | `docker-compose.development.yml` (symlink → `config/docker-compose/`) |
| CI entry | `.github/workflows/test-pipeline.yml` |

## Ownership map

| Area | Team/Owner |
|---|---|
| Backend API + agent | Backend |
| Knowledge graph (Neo4j) | Backend |
| Frontend UI | Frontend |
| CLI | Full-stack |
| Infra / k8s | Platform |
| CI/CD | Platform |

## Key docs

- Architecture overview → `docs/architecture/`
- API reference → `docs/api/`
- Deployment guide → `docs/deployment/`
- Operations runbooks → `docs/operations/`
- Database schema → `docs/database/`
- This CODEMAP index → `docs/CODEMAPS/`
