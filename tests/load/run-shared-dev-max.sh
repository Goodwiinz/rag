#!/usr/bin/env bash
#
# Monitored runner for the maximum shared-dev K6 stress test.
#
# Pulls Supabase credentials from the rag-dev `supabase-credentials` secret
# (never printed), runs the pinned official K6 container against shared dev,
# monitors readiness + the backend pod every 5s, SIGINTs K6 on catastrophic
# conditions (3 consecutive readiness failures or a backend restart), captures
# results under /tmp/rag-stress/<run-id>, and cleans up secrets on exit.
#
#   ./run-shared-dev-max.sh --preflight   # 1 user × 4 iterations, writes marker
#   ./run-shared-dev-max.sh --full        # 34-min ramp to 400 VUs (DISRUPTIVE)
#
# --full refuses to run without a fresh --preflight marker for the same commit.
#
# NOTE: requires kubectl (read access to rag-dev) + docker. Not exercised here;
# run --preflight first and inspect /tmp/rag-stress/<run-id> before --full.

set -euo pipefail

TARGET_URL="https://dev-api.gen-text.app"
NAMESPACE="rag-dev"
SECRET="supabase-credentials"
BACKEND_SELECTOR="app.kubernetes.io/component=backend"
K6_IMAGE="grafana/k6:0.54.0"   # pinned; bump deliberately
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

MODE=""
case "${1:-}" in
  --preflight) MODE="preflight" ;;
  --full)      MODE="full" ;;
  *) echo "usage: $0 --preflight|--full" >&2; exit 2 ;;
esac

RUN_ID="$(date +%Y%m%d-%H%M%S)"
RESULTS_DIR="/tmp/rag-stress/${RUN_ID}"
MARKER_DIR="/tmp/rag-stress/markers"
mkdir -p "$RESULTS_DIR" "$MARKER_DIR"
COMMIT="$(git -C "$SCRIPT_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown)"
PREFLIGHT_MARKER="${MARKER_DIR}/preflight-${COMMIT}.ok"
ENV_FILE="${RESULTS_DIR}/.k6.env"

MON_PID=""
K6_CID=""

cleanup() {
  [[ -n "$MON_PID" ]] && kill "$MON_PID" 2>/dev/null || true
  [[ -n "$K6_CID" ]] && docker rm -f "$K6_CID" >/dev/null 2>&1 || true
  rm -f "$ENV_FILE"
  unset SUPABASE_URL SUPABASE_ANON_KEY SUPABASE_SERVICE_ROLE_KEY
}
trap cleanup EXIT INT TERM

# --- --full gate: require a fresh preflight marker for this commit -----------
if [[ "$MODE" == "full" && ! -f "$PREFLIGHT_MARKER" ]]; then
  echo "refusing --full: no successful preflight marker for commit ${COMMIT}." >&2
  echo "run '$0 --preflight' first." >&2
  exit 3
fi

# --- kubernetes read access -------------------------------------------------
kubectl config current-context >/dev/null
kubectl -n "$NAMESPACE" get pods >/dev/null

# --- read secrets (values never echoed) -------------------------------------
_secret() { kubectl -n "$NAMESPACE" get secret "$SECRET" -o "jsonpath={.data.$1}" | base64 --decode; }
SUPABASE_URL="$(_secret SUPABASE_URL)"
SUPABASE_ANON_KEY="$(_secret SUPABASE_ANON_KEY)"
SUPABASE_SERVICE_ROLE_KEY="$(_secret SUPABASE_SERVICE_ROLE_KEY)"
if [[ -z "$SUPABASE_URL" || -z "$SUPABASE_ANON_KEY" || -z "$SUPABASE_SERVICE_ROLE_KEY" ]]; then
  echo "missing one of SUPABASE_URL / SUPABASE_ANON_KEY / SUPABASE_SERVICE_ROLE_KEY in $SECRET" >&2
  exit 4
fi

# --- health gate ------------------------------------------------------------
curl -fsS --max-time 10 "${TARGET_URL}/health"           >/dev/null || { echo "health check failed" >&2; exit 5; }
curl -fsS --max-time 10 "${TARGET_URL}/health/readiness" >/dev/null || { echo "readiness check failed" >&2; exit 5; }

# --- backend pod + restart baseline -----------------------------------------
BACKEND_POD="$(kubectl -n "$NAMESPACE" get pod -l "$BACKEND_SELECTOR" \
  -o jsonpath='{.items[0].metadata.name}')"
[[ -n "$BACKEND_POD" ]] || { echo "no backend pod found for selector $BACKEND_SELECTOR" >&2; exit 6; }
INITIAL_RESTARTS="$(kubectl -n "$NAMESPACE" get pod "$BACKEND_POD" \
  -o jsonpath='{.status.containerStatuses[0].restartCount}')"
echo "backend pod=$BACKEND_POD initial restarts=$INITIAL_RESTARTS" | tee "${RESULTS_DIR}/baseline.txt"

# --- k6 env file (0600, deleted on exit; keeps secrets out of `ps`) ---------
( umask 077; cat > "$ENV_FILE" <<EOF
SUPABASE_URL=${SUPABASE_URL}
SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}
SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY}
BASE_URL=${TARGET_URL}
RUN_ID=${RUN_ID}
RESULTS_DIR=/results
EOF
)
[[ "$MODE" == "preflight" ]] && echo "PREFLIGHT=1" >> "$ENV_FILE"

# --- monitor: sample every 5s; abort k6 on catastrophic conditions ----------
monitor() {
  local fails=0 ts ready restarts top
  while true; do
    sleep 5
    ts="$(date +%H:%M:%S)"
    if curl -fsS --max-time 4 "${TARGET_URL}/health/readiness" >/dev/null; then
      fails=0; ready=ok
    else
      fails=$((fails + 1)); ready=FAIL
    fi
    restarts="$(kubectl -n "$NAMESPACE" get pod "$BACKEND_POD" \
      -o jsonpath='{.status.containerStatuses[0].restartCount}' 2>/dev/null || echo NA)"
    top="$(kubectl -n "$NAMESPACE" top pod "$BACKEND_POD" --no-headers 2>/dev/null || echo 'top NA')"
    echo "$ts ready=$ready fails=$fails restarts=$restarts $top" >> "${RESULTS_DIR}/monitor.log"
    kubectl -n "$NAMESPACE" get events --field-selector type=Warning \
      --sort-by=.lastTimestamp 2>/dev/null | tail -5 >> "${RESULTS_DIR}/events.log" || true

    if [[ "$fails" -ge 3 ]] || { [[ "$restarts" != NA ]] && [[ "$restarts" -gt "$INITIAL_RESTARTS" ]]; }; then
      echo "$ts CATASTROPHIC: readiness_fails=$fails restarts=$restarts (baseline $INITIAL_RESTARTS) — aborting k6" \
        | tee -a "${RESULTS_DIR}/monitor.log"
      [[ -n "$K6_CID" ]] && docker kill -s INT "$K6_CID" 2>/dev/null || true
      return
    fi
  done
}

# --- launch k6 (secrets via --env-file; results mounted read-write) ---------
echo "starting k6 ($MODE) run=$RUN_ID → $RESULTS_DIR"
K6_CID="$(docker run -d --env-file "$ENV_FILE" \
  -v "${SCRIPT_DIR}:/scripts:ro" -v "${RESULTS_DIR}:/results" \
  "$K6_IMAGE" run /scripts/k6-stress-testing.js)"

monitor &
MON_PID=$!

docker wait "$K6_CID" >/dev/null || true
docker logs "$K6_CID" > "${RESULTS_DIR}/k6.log" 2>&1 || true
kill "$MON_PID" 2>/dev/null || true
MON_PID=""

# --- recovery + final evidence ----------------------------------------------
sleep 10
{
  for i in 1 2 3; do
    if curl -fsS --max-time 5 "${TARGET_URL}/health/readiness" >/dev/null; then
      echo "recovery probe $i ok"
    else
      echo "recovery probe $i FAIL"
    fi
  done
} | tee "${RESULTS_DIR}/recovery.txt"
FINAL_RESTARTS="$(kubectl -n "$NAMESPACE" get pod "$BACKEND_POD" \
  -o jsonpath='{.status.containerStatuses[0].restartCount}' 2>/dev/null || echo NA)"
echo "final restarts=$FINAL_RESTARTS (baseline $INITIAL_RESTARTS)" | tee -a "${RESULTS_DIR}/baseline.txt"

# --- write preflight marker on a clean preflight ----------------------------
if [[ "$MODE" == "preflight" ]]; then
  echo "preflight ok commit=$COMMIT target=$TARGET_URL run=$RUN_ID" > "$PREFLIGHT_MARKER"
  echo "preflight marker: $PREFLIGHT_MARKER"
fi

echo "done — results in $RESULTS_DIR"
