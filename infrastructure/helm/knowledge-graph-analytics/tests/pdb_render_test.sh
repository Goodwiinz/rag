#!/usr/bin/env bash
#
# Render assertions for the PodDisruptionBudget template (R5-M32).
#
# Dev runs one backend and one Celery worker.  maxUnavailable must therefore be
# used so a voluntary drain can evict the only replica.  Production keeps its
# minAvailable policy and does not inherit the dev override.

set -euo pipefail

HELM="${HELM:-helm}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHART="$(cd "${SCRIPT_DIR}/.." && pwd)"
BASE="${CHART}/values.yaml"

render() {
  local release="$1"
  local overlay="$2"
  "${HELM}" template "${release}" "${CHART}" \
    -f "${BASE}" \
    -f "${CHART}/${overlay}" \
    --show-only templates/pdb.yaml
}

dev_pdb="$(render nous-dev values-dev.yaml)"
dev_max_count="$(grep -c '^  maxUnavailable: 1$' <<<"${dev_pdb}" || true)"
if [[ "${dev_max_count}" -ne 2 ]]; then
  echo "expected maxUnavailable: 1 for dev backend and Celery PDBs; got ${dev_max_count}" >&2
  exit 1
fi
if grep -q '^  minAvailable:' <<<"${dev_pdb}"; then
  echo "dev still renders minAvailable; single-replica workloads remain undrainable" >&2
  exit 1
fi

prod_pdb="$(render nous-production values-production.yaml)"
if [[ "$(grep -c '^  minAvailable: 1$' <<<"${prod_pdb}" || true)" -ne 1 ]]; then
  echo "expected production backend PDB to retain minAvailable: 1" >&2
  exit 1
fi
if grep -q '^  maxUnavailable:' <<<"${prod_pdb}"; then
  echo "production unexpectedly inherited the dev maxUnavailable override" >&2
  exit 1
fi

echo "pdb render test: PASSED"
