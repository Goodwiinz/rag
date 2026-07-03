#!/usr/bin/env bash
set -euo pipefail

NS="${NS:-rag-dev}"
SELECTOR="${SELECTOR:-app.kubernetes.io/component=backend}"
SINCE="${SINCE:-30m}"
OUT_DIR="${OUT_DIR:-/tmp/kg-relationship-quality-loop}"
PYTHON_BIN="${PYTHON_BIN:-}"

mkdir -p "$OUT_DIR"

ts="$(date -u +%Y%m%dT%H%M%SZ)"
log_file="$OUT_DIR/relationship-logs-$ts.log"
summary_file="$OUT_DIR/relationship-summary-$ts.txt"

scan_logs() {
  if command -v rg >/dev/null 2>&1; then
    rg -n "relationship|RELATED_TO|Neo4j|neo4j|knowledge graph|Traceback|ERROR|Exception" "$log_file"
  else
    grep -En "relationship|RELATED_TO|Neo4j|neo4j|knowledge graph|Traceback|ERROR|Exception" "$log_file"
  fi
}

echo "== KG relationship quality loop =="
echo "namespace: $NS"
echo "selector:  $SELECTOR"
echo "since:     $SINCE"
echo "output:    $OUT_DIR"

if command -v kubectl >/dev/null 2>&1; then
  echo "== Collecting Kubernetes logs =="
  if kubectl -n "$NS" logs -l "$SELECTOR" --since="$SINCE" --all-containers=true >"$log_file" 2>&1; then
    {
      echo "Log file: $log_file"
      echo
      echo "Relationship / Neo4j error lines:"
      scan_logs || true
    } >"$summary_file"
    sed -n '1,160p' "$summary_file"
  else
    {
      echo "Log file: $log_file"
      echo
      echo "kubectl log collection failed; inspect the log file for details."
    } >"$summary_file"
    sed -n '1,120p' "$summary_file"
    sed -n '1,120p' "$log_file"
  fi
else
  {
    echo "Log file: not collected"
    echo
    echo "kubectl not found; skipping cluster log collection."
  } >"$summary_file"
  sed -n '1,120p' "$summary_file"
fi

echo "== Running focused relationship tests =="
if [ -z "$PYTHON_BIN" ]; then
  if [ -x backend/.venv/bin/python ]; then
    PYTHON_BIN="backend/.venv/bin/python"
  elif [ -x backend/.test-venv/bin/python ]; then
    PYTHON_BIN="backend/.test-venv/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi

"$PYTHON_BIN" -m pytest \
  backend/tests/services/knowledge_graph/test_relationship_merge_dedupe.py \
  backend/tests/services/knowledge_graph/test_relationship_org_scoping.py \
  backend/tests/unit/services/test_knowledge_graph_hardening.py::TestRelationshipDatetimeCoercion \
  backend/tests/unit/services/test_knowledge_graph_hardening.py::TestTwoEndpointScope \
  -q

echo "== Next loop =="
echo "1. Read $summary_file for new relationship errors."
echo "2. Fix one root cause at a time."
echo "3. Re-run this script."
