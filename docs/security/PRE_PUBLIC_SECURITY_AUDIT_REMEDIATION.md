# Pre-Public Security Audit Remediation

This runbook addresses the CRITICAL findings from `SECURITY_AUDIT_PRE_PUBLIC.md`
before the repository is made public.

## Scope

The CRITICAL findings were historical secret exposures in committed Terraform
state and variable files:

- DigitalOcean API token
- DigitalOcean Spaces access key and secret
- DigitalOcean managed database passwords and connection URIs
- Kubernetes cluster admin credentials from kubeconfig/state
- Personal email embedded in Docker registry auth metadata

Merging repository guardrails is necessary but not sufficient. The exposed
credentials must be rotated in the upstream providers and the historical blobs
must be removed from all public refs before visibility changes.

## Required Remediation

1. Rotate the leaked DigitalOcean API token.
   - Revoke the exposed token in the DigitalOcean control panel.
   - Issue a new token with least-privilege scopes for deployment automation.
   - Update GitHub Actions, deployment systems, and local secret stores with the
     replacement token.

2. Rotate DigitalOcean Spaces credentials.
   - Regenerate the affected Spaces key pair.
   - Update object-storage consumers and deployment secrets.
   - Verify reads and writes against the production bucket after rotation.

3. Rotate database passwords and connection URIs.
   - Rotate every affected managed database user password.
   - Replace any connection URI that included an exposed password.
   - Restart workloads that cache database credentials.

4. Regenerate Kubernetes administrative credentials.
   - Revoke or rotate exposed kubeconfig/admin credentials.
   - Reissue deployment credentials with the minimum required RBAC.
   - Confirm old credentials no longer authenticate to the cluster.

5. Rewrite repository history before public release.
   - The critical files were removed from the current tree, but old commits can
     still expose them until all public refs are rewritten.
   - Coordinate a maintenance window because every clone must be refreshed after
     the force-push.

## History Rewrite Procedure

Use a mirror clone so branches and tags are rewritten consistently:

```bash
git clone --mirror git@github.com:Goodwiinz/rag.git rag-sanitized.git
cd rag-sanitized.git
git filter-repo --force --invert-paths \
  --path infrastructure/digitalocean/terraform/terraform.tfstate \
  --path infrastructure/digitalocean/terraform/terraform.tfvars \
  --path infrastructure/digitalocean/terraform/.terraform/
```

Verify the sensitive Terraform artifacts no longer exist in any ref:

```bash
git rev-list --objects --all | rg 'infrastructure/digitalocean/terraform/(terraform\.tfstate|terraform\.tfvars|\.terraform/)'
gitleaks git . --redact --config /path/to/rag/.gitleaks.toml --log-opts="--all"
```

The first command must produce no output. The second command must produce no
findings for the CRITICAL classes listed above.

After verification, force-push the sanitized refs:

```bash
git push --force --mirror origin
```

Then require every contributor and automation clone to reclone or hard-reset to
the rewritten refs. GitHub support may also need to clear cached views for any
deleted sensitive blobs referenced by old pull requests.

## Repository Guardrails Added

- `.gitignore` blocks Terraform state, local Terraform variables, local
  Terraform working directories, and local agent/tool state directories.
- `.gitleaks.toml` extends default secret scanning with rules for the critical
  DigitalOcean, Spaces, AVNS database, and Kubernetes credential classes.
- `.pre-commit-config.yaml` runs `gitleaks git --staged` before commits.
- `.github/workflows/secret-scan.yml` scans the checked-out tree on pull
  requests and protected branch pushes.
- `backend/tests/security/test_pre_public_security_audit_guards.py` keeps these
  controls from being removed silently.

## Public Release Gate

Do not make the repository public until all of the following are complete:

- All five credential classes above have been rotated or revoked.
- The history rewrite has been force-pushed to every branch/tag that will remain
  reachable.
- A full-history gitleaks scan of the sanitized mirror passes.
- Current-tree CI secret scanning passes on the release branch.
