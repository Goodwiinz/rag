# Infisical Bootstrap (one-time, per cluster)

The Infisical operator authenticates to Infisical Cloud via a Universal Auth
machine identity. The operator reads the client_id/client_secret from a single
K8s Secret in each namespace where InfisicalSecrets live (`rag-dev`,
`rag-staging`, `rag-prod`).

This Secret is the **only** secret in the system not managed by Infisical itself.
It is created manually, never committed to Git.

## Prerequisites

1. Infisical Cloud account at https://app.infisical.com
2. Project created — slug recorded (auto-generated, e.g. `nous-platform-pl-3-o`)
3. Environments `dev`, `staging`, `prod` created (slugs match)
4. Folder structure created in each env (see `docs/infrastructure/infisical-setup.md`)
5. Two machine identities created in Org Settings → Access Control → Identities:
   - **`nous-k8s-operator`** — Universal Auth, member of project `nous-platform`
     with role giving read access to all envs
   - **`nous-ci-build`** — Universal Auth, used by GitHub Actions for build-time secrets

## Bootstrap commands

```bash
# Set credentials (from Infisical UI → Identity → Auth Methods → Universal Auth)
export INFISICAL_CLIENT_ID='<machine-identity-client-id>'
export INFISICAL_CLIENT_SECRET='<machine-identity-client-secret>'

# One per target namespace
for ns in rag-dev rag-staging rag-prod; do
  kubectl create namespace "$ns" --dry-run=client -o yaml | kubectl apply -f -
  kubectl create secret generic infisical-universal-auth \
    --namespace "$ns" \
    --from-literal=clientId="$INFISICAL_CLIENT_ID" \
    --from-literal=clientSecret="$INFISICAL_CLIENT_SECRET" \
    --dry-run=client -o yaml | kubectl apply -f -
done

unset INFISICAL_CLIENT_ID INFISICAL_CLIENT_SECRET
```

## Verifying

After ArgoCD syncs the operator + chart:

```bash
# Operator running
kubectl -n infisical-operator get pods

# CRDs synced
kubectl -n rag-dev get infisicalsecrets

# Native K8s Secrets materialized (these are what the backend consumes)
kubectl -n rag-dev get secret database-credentials app-secrets supabase-credentials \
  spaces-credentials redis-credentials azure-openai-credentials -o name

# Sync status on a single CRD
kubectl -n rag-dev describe infisicalsecret infisical-database-credentials
```

## Rotating the bootstrap credential

1. In Infisical UI, generate a new client secret on the `nous-k8s-operator` identity
2. Re-run the `kubectl create secret ... --dry-run=client | kubectl apply -f -` block
3. Operator picks it up on the next reconcile (≤60s)
4. Revoke the old client secret in the UI
