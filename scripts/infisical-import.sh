#!/usr/bin/env bash
# scripts/infisical-import.sh
#
# One-time migration: pull existing K8s Secrets from rag-<env> + frontend
# .env files into the matching folders in the Infisical Cloud project
# (nous-platform). Idempotent: re-running just overwrites with current values.
#
# Prereqs (run once, in this order):
#   1. brew install infisical/get-cli/infisical
#   2. infisical login                              # browser flow
#   3. cd <repo-root> && infisical init             # binds to nous-platform
#   4. kubectl context = do-nyc3-rag-system-cluster
#
# Usage:
#   scripts/infisical-import.sh dev                 # dry-run, prints plan
#   scripts/infisical-import.sh dev --apply         # live push to Infisical
#   scripts/infisical-import.sh staging --apply
#   scripts/infisical-import.sh prod --apply
#
# Frontend secrets are only imported for `dev` (the only env where they exist
# locally). For staging/prod, populate /frontend-build via the Infisical UI or
# infisical CLI manually.
#
# Secrets are streamed via process substitution; nothing is written to disk.

set -euo pipefail

ENV_SLUG="${1:-}"
APPLY="${2:-}"

if [[ -z "$ENV_SLUG" || ! "$ENV_SLUG" =~ ^(dev|staging|prod)$ ]]; then
  echo "usage: $0 <dev|staging|prod> [--apply]" >&2
  exit 2
fi

NS="rag-${ENV_SLUG}"
LIVE=false
[[ "$APPLY" == "--apply" ]] && LIVE=true

# ── pre-flight ────────────────────────────────────────────────────────────
for bin in infisical kubectl jq; do
  command -v "$bin" >/dev/null || { echo "missing: $bin" >&2; exit 1; }
done
[[ -f .infisical.json ]] || {
  echo "no .infisical.json in cwd — run: infisical init" >&2; exit 1; }
kubectl -n "$NS" get ns >/dev/null 2>&1 || {
  echo "cannot access namespace $NS — wrong kube context?" >&2; exit 1; }

mode_label="DRY-RUN"
$LIVE && mode_label="LIVE — will write to Infisical Cloud"
echo "Mode: $mode_label"
echo "Source: $NS  →  Target: infisical env=$ENV_SLUG"
echo

# ── backend: cluster Secrets → Infisical folders ──────────────────────────
SECRETS=(
  "database-credentials:/database"
  "app-secrets:/app"
  "spaces-credentials:/spaces"
  "supabase-credentials:/supabase"
  "redis-credentials:/redis"
  "azure-openai-credentials:/azure-openai"
  "langsmith-credentials:/langsmith"
)

# Pre-create folders (the CLI does NOT auto-create on `secrets set`).
# The create call is idempotent on Infisical's side: already-existing folders
# return a 4xx that we swallow.
ensure_folder() {
  local env="$1" path="$2"
  local name="${path##*/}"
  $LIVE || return 0
  infisical secrets folders create --env="$env" --path=/ --name="$name" \
    --silent >/dev/null 2>&1 || true
}

echo "Ensuring folders exist..."
for entry in "${SECRETS[@]}"; do
  IFS=":" read -r _ folder <<<"$entry"
  ensure_folder "$ENV_SLUG" "$folder"
done
[[ "$ENV_SLUG" == "dev" ]] && ensure_folder dev /frontend-build
echo

for entry in "${SECRETS[@]}"; do
  IFS=":" read -r secret folder <<<"$entry"
  if ! kubectl -n "$NS" get secret "$secret" >/dev/null 2>&1; then
    printf "  skip %-30s (not in %s)\n" "$secret" "$NS"
    continue
  fi
  count=$(kubectl -n "$NS" get secret "$secret" -o json | jq '.data | length')
  printf "  %-30s %2d keys  →  %s\n" "$secret" "$count" "$folder"

  if $LIVE; then
    infisical secrets set --env="$ENV_SLUG" --path="$folder" \
      --file=<(kubectl -n "$NS" get secret "$secret" -o json \
               | jq -r '.data | to_entries[] | "\(.key)=\(.value | @base64d)"') \
      >/dev/null
  fi
done

# ── frontend: local files → /frontend-build (dev only) ────────────────────
if [[ "$ENV_SLUG" == "dev" ]]; then
  echo
  for f in frontend/.env.local frontend/.env.sentry-build-plugin; do
    [[ -f "$f" ]] || { echo "  skip $f (missing)"; continue; }
    count=$(grep -cE '^[A-Z_][A-Z0-9_]*=' "$f" || true)
    printf "  %-40s %2d keys  →  /frontend-build\n" "$f" "$count"
    if $LIVE; then
      infisical secrets set --env=dev --path=/frontend-build --file="$f" >/dev/null
    fi
  done
fi

echo
if $LIVE; then
  echo "Imported. Verify in UI or with:"
  echo "  infisical secrets --env=$ENV_SLUG --path=/database"
else
  echo "Dry-run complete. Re-run with --apply to push."
fi
