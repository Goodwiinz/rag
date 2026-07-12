# Decision: Celery worker queue-depth autoscaling (KEDA over prometheus-adapter)

**Status:** Accepted — scaffold merged, operator install + enable deferred to an
explicit human flip.
**Date:** 2026-07-12
**Audit finding:** X5 / P1.6 — the celery-worker HPA scales on CPU + memory only,
which is backlog-blind for I/O-bound LLM/ingestion tasks. A queue of pending jobs
can build up while CPU/RAM stay low and the HPA never scales up.
**Scope:** `dev` (the only actively deployed env). Production is scaffolded but
not promoted.

## Context

The worker in `infrastructure/helm/knowledge-graph-analytics` runs long,
I/O-bound Celery tasks (arXiv ingest, document processing, LLM extraction, agent
turns). Its HPA (`templates/hpa.yaml`) targets CPU and memory utilization. Those
signals lag the thing that actually matters — **how many jobs are waiting** — so
a deep backlog can sit in Redis while the pods look idle and no scale-up fires.

The backlog signal is already exported: PR #1132 added the Prometheus gauge
`celery_queue_depth{queue=...}` (`backend/src/observability/celery_queue_metrics.py`).
But a Prometheus gauge is not something an HPA can read on its own — Kubernetes
HPAs only consume the metrics API. Turning queue depth into a scaling signal
needs an adapter, and there are two ways to build one.

## Options

### A. prometheus-adapter (External metric)

Deploy `prometheus-adapter`, write a rule that surfaces `celery_queue_depth` on
the Kubernetes `external.metrics.k8s.io` API, then add a `- type: External`
metric block to the worker HPA.

- Reuses the gauge we already export (#1132).
- But it is a **three-hop path**: worker → Prometheus scrape → adapter →
  metrics API → HPA. Every hop is a place for staleness or breakage (scrape
  interval, adapter query lag, rule misconfiguration). It also presupposes a
  Prometheus that scrapes the worker; in `dev` the in-cluster Prometheus subchart
  is disabled (`prometheus.enabled: false` in `values-dev.yaml`), so this path
  would require standing up and wiring Prometheus first.

### B. KEDA (Redis list trigger) — CHOSEN

Deploy the KEDA operator, then declare a `ScaledObject` whose `redis` trigger
reads the **length of the Celery Redis lists directly**. KEDA reconciles this
into its own HPA under the hood.

- **Bypasses the Prometheus-format metric entirely.** KEDA's redis scaler does a
  `LLEN` on the queue key — it reads queue depth straight from the broker, the
  same value `celery_queue_depth` is derived from, with no scrape/adapter hops.
  That is strictly simpler and fresher, and it is why we chose it.
- Native scale-to/from a floor, per-trigger targets, and a large catalog of
  scalers if we later want to scale on other signals.
- Cost: one more operator (CRDs + controller) in the cluster.

`celery_queue_depth` (#1132) stays useful regardless — it remains the
**observability** view of the same backlog KEDA scales on (dashboards, alerts),
even though KEDA does not consume it.

## Decision

Scaffold KEDA, gated OFF, and defer the operator install + enable to an explicit
human step.

- `templates/keda-scaledobject.yaml` renders a `ScaledObject` +
  `TriggerAuthentication` for the worker **only when `.Values.keda.enabled`**.
- Triggers: one `redis` list trigger per hot queue — the default `celery` queue
  and `document_processing` — `listLength: 10` (target items per replica).
- `minReplicaCount`/`maxReplicaCount` mirror the plain worker HPA (1–3 base).
- Auth: a `TriggerAuthentication` referencing the **existing** `redis-credentials`
  secret (no new secret). rediss:// TLS maps to the trigger's `enableTLS`.
- Mutual exclusion: when `keda.enabled=true`, the plain CPU/memory worker HPA in
  `templates/hpa.yaml` stops rendering (its guard gains `(not
.Values.keda.enabled)`), because KEDA reconciles its own
  `keda-hpa-<name>` HPA and two controllers must not fight over one Deployment.

Default everywhere is `keda.enabled: false`, so this is inert until KEDA is
installed and the flag is flipped — nothing changes in the cluster on merge.

### Redis credentials caveat

The app consumes Redis as a single `REDIS_URL` (`rediss://…`). KEDA's redis
scaler instead needs **host, port, and password as discrete values** — it does
not parse a connection URL. So before enabling, the `redis-credentials` secret
(populated from the `/redis` Infisical folder) must expose `REDIS_HOST`,
`REDIS_PORT`, and `REDIS_PASSWORD` keys (or repoint `keda.redis.*Key` at
whatever keys exist). `enableTLS: "true"` covers the `rediss://` TLS.

## Install checklist (human, explicit)

1. Install the KEDA operator into its own namespace:
   ```sh
   helm repo add kedacore https://kedacore.github.io/charts
   helm repo update
   helm install keda kedacore/keda --namespace keda --create-namespace
   ```
   Verify the CRDs and controller are up:
   ```sh
   kubectl get crd scaledobjects.keda.sh triggerauthentications.keda.sh
   kubectl -n keda get deploy
   ```
2. Ensure the `redis-credentials` secret in `rag-dev` carries `REDIS_HOST`,
   `REDIS_PORT`, `REDIS_PASSWORD` (add them to the `/redis` Infisical folder if
   absent), or adjust `keda.redis.*Key` in `values-dev.yaml`.
3. Flip `keda.enabled: true` in `values-dev.yaml`, commit, let ArgoCD sync.
4. Verify:
   ```sh
   kubectl -n rag-dev get scaledobject,triggerauthentication
   kubectl -n rag-dev get hpa            # expect keda-hpa-<name>; the plain
                                         # -celery-worker HPA should be gone
   kubectl -n rag-dev describe scaledobject <name>   # triggers ACTIVE/healthy
   ```
   Push a backlog onto `document_processing` and confirm the worker scales up.

## Rollback

Set `keda.enabled: false` (values-only, no image rebuild) and let ArgoCD sync.
The `ScaledObject`/`TriggerAuthentication` are pruned and the plain CPU/memory
worker HPA re-renders unchanged. Uninstalling the operator itself
(`helm uninstall keda -n keda`) is optional and independent.
