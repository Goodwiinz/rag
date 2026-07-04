# Kubernetes Secrets

Do not commit Kubernetes `Secret` manifests or base64-encoded secret values in
this directory.

Production and staging secrets are managed through Infisical. For local or
break-glass cluster setup, generate secrets at deploy time with
`scripts/setup-secrets.sh` or `kubectl create secret ... --dry-run=client -o yaml`
and pipe the result directly to `kubectl apply -f -`.
