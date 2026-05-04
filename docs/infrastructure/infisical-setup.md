# Infisical Setup — NOUS Platform

Centralized secret management for the NOUS DOKS deployment. Replaces ad-hoc
`kubectl create secret` and the dead AWS Secrets Manager ExternalSecret config
that previously lived in `infrastructure/kubernetes/secrets.yaml`.

## Architecture

```
Infisical Cloud (app.infisical.com)
└── project: nous-platform
    ├── env: dev      ──┐
    ├── env: staging  ──┤  ← machine identity: nous-k8s-operator (Universal Auth)
    └── env: prod     ──┘                       nous-ci-build       (Universal Auth)

K8s cluster (DOKS)
├── ns: infisical-operator   ← Helm release (ArgoCD app)
└── ns: rag-{dev,staging,prod}
    ├── Secret: infisical-universal-auth     ← bootstrapped manually, never in Git
    ├── InfisicalSecret CRDs (Helm-templated, in Git)
    └── Secret: database-credentials, app-secrets, …  ← materialized by operator
```

## Project layout (folders per environment)

Create these folders inside each environment (`dev`, `staging`, `prod`). Each
folder maps 1:1 to a K8s Secret the backend already consumes via `envFrom`.

| Folder              | Materialized as Secret      | Keys (examples)                                              |
| ------------------- | --------------------------- | ------------------------------------------------------------ |
| `/database`         | `database-credentials`      | `DATABASE_URL`, `POSTGRES_USER`, `POSTGRES_PASSWORD`         |
| `/app`              | `app-secrets`               | `SECRET_KEY`, `JWT_SECRET`, `ENCRYPTION_KEY`                 |
| `/spaces`           | `spaces-credentials`        | `S3_ACCESS_KEY`, `S3_SECRET_KEY`                             |
| `/supabase`         | `supabase-credentials`      | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`                  |
| `/redis`            | `redis-credentials`         | `REDIS_URL`, `REDIS_PASSWORD`                                |
| `/azure-openai`     | `azure-openai-credentials`  | `AZURE_OPENAI_CHAT_*` (endpoint, api-key, deployment, ver)   |
| `/langsmith`        | `langsmith-credentials`     | `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`                     |
| `/frontend-build`   | _(not synced to cluster)_   | `NEXT_PUBLIC_*`, `SENTRY_AUTH_TOKEN` — read by GitHub Actions |

The mapping from folder → Secret name is defined in
`infrastructure/helm/knowledge-graph-analytics/values.yaml` under
`infisical.secrets`. Override per env if you want different folders.

## One-time setup

### 1. Create the Infisical project

In https://app.infisical.com:

1. New Project → name: `NOUS Platform`. The slug is auto-generated and visible
   under Project Settings → General (ours resolved to `nous-platform-pl-3-o`).
   To look it up via API:
   `curl -H "Authorization: Bearer $TOKEN" https://app.infisical.com/api/v1/workspace/<id> | jq .workspace.slug`
2. Environments → confirm `dev`, `staging`, `prod` exist (slugs match)
3. In each env, create the folders listed above and populate the keys

### 2. Create machine identities

Org Settings → Access Control → Identities → Create Identity:

- **`nous-k8s-operator`** — Auth Method: Universal Auth. Add to project
  `nous-platform` with a role granting **Read** on Secrets in `dev`, `staging`,
  `prod`.
- **`nous-ci-build`** — Auth Method: Universal Auth. Add to project with **Read**
  on the `/frontend-build` path across all envs.

For each identity, copy the Client ID and generate a Client Secret. Store as:

- `nous-k8s-operator` → bootstrapped into K8s (see below)
- `nous-ci-build` → GitHub repo Secrets `INFISICAL_CLIENT_ID`, `INFISICAL_CLIENT_SECRET`

### 3. Install the operator

The ArgoCD Application at
`infrastructure/argocd/applications/infisical-operator.yaml` is picked up by the
root app and installs the operator into the `infisical-operator` namespace.

To register it on first run:

```bash
kubectl apply -f infrastructure/argocd/applications/infisical-operator.yaml
```

(Subsequent changes flow through ArgoCD on `develop`.)

### 4. Bootstrap the auth Secret per namespace

See `infrastructure/kubernetes/infisical-bootstrap.md`.

### 5. Enable in Helm values

Edit `values-dev.yaml`, `values-staging.yaml`, `values-production.yaml` to set
`infisical.enabled: true` and the matching `envSlug`. ArgoCD picks up the change
on next sync.

### 6. Cut over the old secrets

For each env namespace, after the InfisicalSecret CRDs are healthy and the
Operator-owned Secrets are populated, delete any pre-existing kubectl-created
Secrets with the same names — the InfisicalSecret will recreate them under its
own ownership.

```bash
# Dev only — verify before doing anything destructive
kubectl -n rag-dev get infisicalsecret -o wide
kubectl -n rag-dev describe infisicalsecret infisical-database-credentials | tail -20
```

If the InfisicalSecret status shows synced but the Secret already exists with a
different `ownerReferences`, the operator won't overwrite it (creationPolicy:
Orphan). To hand over ownership:

```bash
kubectl -n rag-dev delete secret database-credentials
# Operator recreates within resyncInterval (default 60s)
```

## CI integration

Build-time `NEXT_PUBLIC_*` vars (which Next.js bakes into the client bundle) are
public-by-design but environment-specific. They live in Infisical
`/frontend-build` and are pulled into GitHub Actions via
`Infisical/secrets-action@v1.0.9`.

`SENTRY_AUTH_TOKEN` (server-side, NOT public) is also fetched from
`/frontend-build` but passed via BuildKit `--mount=type=secret` so it never
appears in image layers.

GitHub repo secrets needed (`Settings → Secrets and variables → Actions`):

- `INFISICAL_CLIENT_ID` — from `nous-ci-build` identity
- `INFISICAL_CLIENT_SECRET` — from `nous-ci-build` identity

After cutover, you can delete `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`,
`NEXT_PUBLIC_SENTRY_DSN`, `SENTRY_AUTH_TOKEN` from GitHub repo secrets — they live
in Infisical now.

## Local development

For `npm run dev` against local services, the Infisical CLI works but is
optional — you can keep using `frontend/.env.local` and `backend/.env`. If you
want consistency with cluster behavior:

```bash
brew install infisical/get-cli/infisical
infisical login
infisical init  # binds the working dir to the nous-platform project + dev env
infisical run -- npm run dev   # in frontend/
infisical run -- uvicorn src.main:app --reload  # in backend/
```

## Troubleshooting

**InfisicalSecret stuck on "creating"**: check the operator logs.
```bash
kubectl -n infisical-operator logs -l control-plane=controller-manager --tail=100
```

**Auth failure**: verify the bootstrap Secret has the right keys
(`clientId`, `clientSecret` — note camelCase, not snake_case).
```bash
kubectl -n rag-dev get secret infisical-universal-auth -o jsonpath='{.data}' | jq 'keys'
# Should show ["clientId","clientSecret"]
```

**Secret not materializing**: confirm the folder path and env slug match
exactly. Slugs are case-sensitive.

**Operator can't reach app.infisical.com**: NetworkPolicy or egress rules. The
operator needs HTTPS egress to `app.infisical.com:443`.
