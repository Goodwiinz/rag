#!/usr/bin/env bash
#
# Render-assertion test for templates/networkpolicy.yaml (audit finding X6).
#
# Guards the contract that makes this policy safe to enable on a live cluster:
#   * scoped to the BACKEND pods only (Neo4j/celery share selectorLabels, so a
#     broader selector would default-deny their ingress and break bolt:7687);
#   * dev/staging default = ingress-only when enabled (egress lockdown deferred);
#   * production = ingress + egress;
#   * the allowed ingress port is the POD port (targetPort 8000), not the
#     Service port (80) — matching .service.port would block all ingress.
#
# Requires the `helm` binary (override with HELM=/path/to/helm). No cluster.
#
set -euo pipefail

HELM="${HELM:-helm}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHART="$(cd "${SCRIPT_DIR}/.." && pwd)"
BASE="${CHART}/values.yaml"

fail=0
pass() { printf '  ok   - %s\n' "$1"; }
die()  { printf '  FAIL - %s\n' "$1" >&2; fail=1; }

# render <name> <extra helm args...>  -> full manifest stream on stdout
render() {
  local name="$1"; shift
  "${HELM}" template "${name}" "${CHART}" -f "${BASE}" "$@"
}

echo "networkpolicy render test (chart: ${CHART})"

# ── 1. dev default: policy DISABLED -> nothing rendered ──────────────────────
dev_default="$(render nous-dev -f "${CHART}/values-dev.yaml")"
if [ "$(printf '%s\n' "${dev_default}" | grep -c '^kind: NetworkPolicy$')" -eq 0 ]; then
  pass "dev default renders no NetworkPolicy (enabled:false)"
else
  die "dev default rendered a NetworkPolicy but enabled:false"
fi

# ── 2. dev enabled: INGRESS-ONLY on the backend, pod port 8000 ───────────────
dev_np="$(render nous-dev -f "${CHART}/values-dev.yaml" --set networkPolicy.enabled=true \
  --show-only templates/networkpolicy.yaml)"

grep -q 'app.kubernetes.io/component: backend' <<<"${dev_np}" \
  && pass "dev policy scoped to component=backend" \
  || die "dev policy missing component=backend scope"

# The only podSelector/label scope must be backend — never neo4j.
if grep -q 'component: neo4j' <<<"${dev_np}"; then
  die "dev policy references neo4j (must not select/deny the Neo4j pod)"
else
  pass "dev policy does not touch Neo4j"
fi

grep -qE '^\s+- Ingress$' <<<"${dev_np}" \
  && pass "dev policyTypes includes Ingress" \
  || die "dev policyTypes missing Ingress"

if grep -qE '^\s+- Egress$' <<<"${dev_np}"; then
  die "dev policy default-denies egress (egress lockdown must be deferred)"
else
  pass "dev policy is ingress-only (no Egress)"
fi

grep -q 'kubernetes.io/metadata.name: ingress-nginx' <<<"${dev_np}" \
  && pass "dev policy allows ingress-nginx namespace" \
  || die "dev policy missing ingress-nginx allow"

grep -q 'kubernetes.io/metadata.name: monitoring' <<<"${dev_np}" \
  && pass "dev policy allows Prometheus (monitoring namespace)" \
  || die "dev policy missing Prometheus allow"

if grep -qE '^\s+port: 8000$' <<<"${dev_np}" && ! grep -qE '^\s+port: 80$' <<<"${dev_np}"; then
  pass "dev ingress port is the pod port 8000 (not Service port 80)"
else
  die "dev ingress port wrong — must be pod targetPort 8000, not Service port 80"
fi

# ── 3. production: INGRESS + EGRESS, egress covers DNS/Neo4j/HTTPS ────────────
prod_np="$(render nous-prod -f "${CHART}/values-production.yaml" \
  --show-only templates/networkpolicy.yaml)"

grep -qE '^\s+- Ingress$' <<<"${prod_np}" \
  && grep -qE '^\s+- Egress$' <<<"${prod_np}" \
  && pass "prod policyTypes includes Ingress + Egress" \
  || die "prod policy missing Ingress/Egress"

for want in "port: 53" "port: 7687" "port: 443"; do
  grep -qE "^\s+${want}$" <<<"${prod_np}" \
    && pass "prod egress allows ${want}" \
    || die "prod egress missing ${want}"
done

grep -q 'component: neo4j' <<<"${prod_np}" \
  && pass "prod egress targets Neo4j by component selector" \
  || die "prod egress missing Neo4j selector"

if [ "${fail}" -ne 0 ]; then
  echo "networkpolicy render test: FAILED" >&2
  exit 1
fi
echo "networkpolicy render test: PASSED"
