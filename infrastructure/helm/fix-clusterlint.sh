#!/usr/bin/env bash
# Fix DOKS clusterlint issues — 29 findings from production readiness check
#
# Usage:
#   ./infrastructure/helm/fix-clusterlint.sh              # Apply all fixes
#   ./infrastructure/helm/fix-clusterlint.sh --dry-run    # Preview only
#   ./infrastructure/helm/fix-clusterlint.sh --step N     # Run only step N (1-4)
#
# Prerequisites:
#   - kubectl configured for rag-system-cluster
#   - Helm repos added:
#       helm repo add argo https://argoproj.github.io/argo-helm
#       helm repo add jetstack https://charts.jetstack.io
#       helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
#       helm repo update

set -uo pipefail
# NOTE: set -e is intentionally omitted — we handle errors explicitly
# to avoid silent exits when helm/kubectl commands fail during detection.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRY_RUN=false
STEP=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run) DRY_RUN=true; shift ;;
    --step) STEP="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

run_cmd() {
  if $DRY_RUN; then
    echo "  [dry-run] $*"
  else
    "$@"
  fi
}

should_run() {
  [[ -z "$STEP" || "$STEP" == "$1" ]]
}

# Detect a Helm release name in a namespace, returns empty string on failure
detect_helm_release() {
  local ns="$1"
  local filter="$2"
  helm list -n "$ns" --filter "$filter" -q 2>/dev/null | head -1 || true
}

echo "════════════════════════════════════════════════════════════"
echo " NOUS — DOKS Clusterlint Remediation"
echo " Cluster: rag-system-cluster (NYC3, K8s 1.32.13-do.0)"
echo "════════════════════════════════════════════════════════════"
$DRY_RUN && echo " MODE: dry-run"
echo ""

# Verify cluster connection
if ! kubectl cluster-info >/dev/null 2>&1; then
  echo "ERROR: Cannot connect to Kubernetes cluster."
  echo "Run: doctl kubernetes cluster kubeconfig save rag-system-cluster"
  exit 1
fi
echo "Cluster connected."
echo ""

# ─── Step 1: cert-manager (BLOCKING — prevents cluster upgrades) ───
if should_run 1; then
  echo "┌─ Step 1/4: cert-manager — webhook timeout + resource limits"
  echo "│  Fixes: 2 webhook timeout issues (upgrade-blocking) + 3 resource issues"
  echo "│"

  # Detect namespace
  CM_NS=""
  if kubectl get namespace cert-manager --no-headers >/dev/null 2>&1; then
    CM_NS="cert-manager"
  fi

  if [[ -z "$CM_NS" ]]; then
    echo "│  WARNING: cert-manager namespace not found. Skipping."
    echo "└─"
  else
    # Detect current release name
    CM_RELEASE=$(detect_helm_release "$CM_NS" "cert-manager")
    if [[ -z "$CM_RELEASE" ]]; then
      CM_RELEASE="cert-manager"
      echo "│  WARNING: Could not detect Helm release name, using '$CM_RELEASE'"
    fi
    # Pin chart version to match installed version to avoid schema mismatch
    CM_VERSION=$(helm list -n "$CM_NS" --filter "$CM_RELEASE" -o json 2>/dev/null | python3 -c "import sys,json; r=json.load(sys.stdin); print(r[0]['chart'].split('-',2)[-1] if r else '')" 2>/dev/null || true)
    echo "│  Release: $CM_RELEASE  Namespace: $CM_NS  Chart: $CM_VERSION"
    VERSION_FLAG=""
    if [[ -n "$CM_VERSION" ]]; then
      VERSION_FLAG="--version $CM_VERSION"
    fi
    run_cmd helm upgrade "$CM_RELEASE" jetstack/cert-manager \
      -n "$CM_NS" \
      -f "$SCRIPT_DIR/cert-manager-values.yaml" \
      --reuse-values \
      $VERSION_FLAG
    echo "│  Done."
    echo "└─"
  fi
  echo ""
fi

# ─── Step 2: ArgoCD resource limits ───
if should_run 2; then
  echo "┌─ Step 2/4: ArgoCD — resource limits for 8 containers"
  echo "│"

  ARGO_NS="argocd"
  ARGO_RELEASE=$(detect_helm_release "$ARGO_NS" "argo")
  if [[ -z "$ARGO_RELEASE" ]]; then
    # Check if ArgoCD was installed via 1-Click (not Helm-managed)
    if kubectl get namespace argocd >/dev/null 2>&1; then
      echo "│  ArgoCD namespace exists but no Helm release found."
      echo "│  ArgoCD may have been installed via DO 1-Click Marketplace."
      echo "│"
      echo "│  For 1-Click installs, patch resources directly:"
      echo "│    kubectl -n argocd set resources deployment argocd-server --requests=cpu=100m,memory=128Mi --limits=cpu=500m,memory=512Mi"
      echo "│    kubectl -n argocd set resources deployment argocd-repo-server --requests=cpu=100m,memory=128Mi --limits=cpu=500m,memory=512Mi"
      echo "│    kubectl -n argocd set resources statefulset argocd-application-controller --requests=cpu=250m,memory=256Mi --limits=cpu=1000m,memory=1Gi"
      echo "│"
      echo "│  Or convert to Helm-managed:"
      echo "│    helm repo add argo https://argoproj.github.io/argo-helm"
      echo "│    helm install argocd argo/argo-cd -n argocd -f $SCRIPT_DIR/argocd-values.yaml"
    else
      echo "│  WARNING: ArgoCD namespace not found. Skipping."
    fi
    echo "└─"
  else
    ARGO_CHART_VER=$(helm list -n "$ARGO_NS" --filter "$ARGO_RELEASE" -o json 2>/dev/null | python3 -c "import sys,json; r=json.load(sys.stdin); print(r[0]['chart'].split('-',2)[-1] if r else '')" 2>/dev/null || true)
    echo "│  Release: $ARGO_RELEASE  Namespace: $ARGO_NS  Chart: $ARGO_CHART_VER"
    ARGO_VER_FLAG=""
    if [[ -n "$ARGO_CHART_VER" ]]; then
      ARGO_VER_FLAG="--version $ARGO_CHART_VER"
    fi
    run_cmd helm upgrade "$ARGO_RELEASE" argo/argo-cd \
      -n "$ARGO_NS" \
      -f "$SCRIPT_DIR/argocd-values.yaml" \
      --reuse-values \
      $ARGO_VER_FLAG
    echo "│  Done."
    echo "└─"
  fi
  echo ""
fi

# ─── Step 3: kube-prometheus-stack resource limits ───
if should_run 3; then
  echo "┌─ Step 3/4: kube-prometheus-stack — resource limits + Grafana StatefulSet"
  echo "│  Fixes: 8 resource issues + 1 DOBS volume issue"
  echo "│"

  PROM_RELEASE=""
  PROM_NS=""

  # Try common namespaces and release name patterns
  for ns in monitoring prometheus-stack kube-prometheus-stack prometheus default; do
    for filter in "kube-prometheus" "prometheus"; do
      PROM_RELEASE=$(detect_helm_release "$ns" "$filter")
      if [[ -n "$PROM_RELEASE" ]]; then
        PROM_NS="$ns"
        break 2
      fi
    done
  done

  # Fallback: scan all namespaces
  if [[ -z "$PROM_RELEASE" ]]; then
    echo "│  Scanning all namespaces for prometheus release..."
    SCAN_RESULT=$(helm list -A --filter "prometheus" -q 2>/dev/null | head -1 || true)
    if [[ -n "$SCAN_RESULT" ]]; then
      PROM_RELEASE="$SCAN_RESULT"
      PROM_NS=$(helm list -A --filter "prometheus" 2>/dev/null | grep "$PROM_RELEASE" | awk '{print $2}' || true)
    fi
  fi

  if [[ -z "$PROM_RELEASE" ]]; then
    echo "│  WARNING: Could not find kube-prometheus-stack Helm release."
    echo "│"
    echo "│  Manual fix:"
    echo "│    helm list -A | grep prometheus   # find release name and namespace"
    echo "│    helm upgrade <release> prometheus-community/kube-prometheus-stack \\"
    echo "│      -n <namespace> -f $SCRIPT_DIR/kube-prometheus-stack-values.yaml --reuse-values"
    echo "└─"
  else
    PROM_CHART_VER=$(helm list -n "$PROM_NS" --filter "$PROM_RELEASE" -o json 2>/dev/null | python3 -c "import sys,json; r=json.load(sys.stdin); print(r[0]['chart'].split('-',3)[-1] if r else '')" 2>/dev/null || true)
    echo "│  Release: $PROM_RELEASE  Namespace: $PROM_NS  Chart: $PROM_CHART_VER"
    PROM_VER_FLAG=""
    if [[ -n "$PROM_CHART_VER" ]]; then
      PROM_VER_FLAG="--version $PROM_CHART_VER"
    fi
    run_cmd helm upgrade "$PROM_RELEASE" prometheus-community/kube-prometheus-stack \
      -n "$PROM_NS" \
      -f "$SCRIPT_DIR/kube-prometheus-stack-values.yaml" \
      --reuse-values \
      $PROM_VER_FLAG
    echo "│  Done."
    echo "└─"
  fi
  echo ""
fi

# ─── Step 4: Node labels (manual — requires DO console/API) ───
if should_run 4; then
  echo "┌─ Step 4/4: Node labels — move custom labels to node pool"
  echo "│"
  echo "│  Custom labels AND taints on individual nodes (app-pool-v28ul, app-pool-v28ut)"
  echo "│  will be lost on node replacement/upgrade."
  echo "│"
  echo "│  Fix via DO console or API:"
  echo "│    doctl kubernetes cluster node-pool update rag-system-cluster app-pool \\"
  echo "│      --label <key>=<value> \\"
  echo "│      --taint <key>=<value>:<effect>"
  echo "│"

  # Show current custom labels and taints for reference
  echo "│  Current custom labels and taints on nodes:"
  NODES=$(kubectl get nodes -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || true)
  for node in $NODES; do
    echo "│"
    echo "│  Node: $node"

    # Labels
    LABELS=$(kubectl get node "$node" -o jsonpath='{.metadata.labels}' 2>/dev/null || true)
    if [[ -n "$LABELS" ]]; then
      echo "$LABELS" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    custom = {k: v for k, v in d.items()
              if not k.startswith(('beta.kubernetes.io','failure-domain','kubernetes.io',
                                   'node.kubernetes.io','doks.digitalocean.com','topology'))}
    if custom:
        print('│    Labels:')
        for k, v in custom.items():
            print(f'│      {k}={v}')
    else:
        print('│    Labels: (none custom)')
except Exception:
    print('│    Labels: (could not parse)')
" 2>/dev/null || echo "│    Labels: (could not read)"
    else
      echo "│    (node not found or not accessible)"
    fi

    # Taints
    TAINTS=$(kubectl get node "$node" -o jsonpath='{.spec.taints}' 2>/dev/null || true)
    if [[ -n "$TAINTS" && "$TAINTS" != "null" ]]; then
      echo "$TAINTS" | python3 -c "
import sys, json
try:
    taints = json.load(sys.stdin)
    if taints:
        print('│    Taints:')
        for t in taints:
            key = t.get('key', '')
            val = t.get('value', '')
            effect = t.get('effect', '')
            print(f'│      {key}={val}:{effect}')
    else:
        print('│    Taints: (none)')
except Exception:
    print('│    Taints: (could not parse)')
" 2>/dev/null || echo "│    Taints: (could not read)"
    else
      echo "│    Taints: (none)"
    fi
  done
  echo "└─"
  echo ""
fi

# ─── Summary ───
echo "════════════════════════════════════════════════════════════"
echo " Remediation complete."
echo ""
echo " Ignored (safe / DO system components):"
echo "   - doks-telemetry-config-reloader hostpath warnings (4)"
echo "   - wait-for-postgres init container (fixed in app Helm chart)"
echo ""
echo " Re-run clusterlint to verify:"
echo "   DO Console → Kubernetes → rag-system-cluster → Run again"
echo "════════════════════════════════════════════════════════════"
